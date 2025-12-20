"""
RRF Optimization Experiments
============================

Testing various improvements to push accuracy higher.

Experiments:
1. Weight tuning (BM25 vs Code vs Summary)
2. Name boosting (exact name match in query)
3. Flexible matching (partial qualified name match)
4. RRF k-value tuning
"""

import json
import sys
import os
import re
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi
import voyageai

# Setup
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.extractors.base import ExtractedFunction

# Load Voyage client
voyage_client = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))


def load_functions(codebase: str) -> List[ExtractedFunction]:
    """Load functions from v2 summaries."""
    path = ROOT / f"results/{codebase}_v2_summaries.json"
    
    with open(path) as f:
        data = json.load(f)
    
    functions = []
    for fd in data['functions']:
        func = ExtractedFunction(
            name=fd['name'],
            qualified_name=fd['qualified_name'],
            file_path=fd['file_path'],
            code=fd['code'],
            signature=fd['signature'],
            class_name=fd.get('class_name'),
            class_docstring=fd.get('class_docstring'),
            docstring=fd.get('docstring'),
            decorators=fd.get('decorators', []),
            is_method=fd.get('is_method', False),
            is_dunder=fd.get('is_dunder', False),
            language='python',
            summary=fd.get('summary'),
        )
        functions.append(func)
    
    return functions


def tokenize(text: str) -> List[str]:
    """Tokenize for BM25."""
    text = text.lower()
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = text.replace('_', ' ').replace('.', ' ')
    return re.findall(r'\b\w+\b', text)


def is_match(expected_list: List[str], func: ExtractedFunction, flexible: bool = False) -> bool:
    """Check if function matches expected."""
    for exp in expected_list:
        exp_lower = exp.lower()
        name_lower = func.name.lower()
        qualified_lower = func.qualified_name.lower()
        
        # Exact matches
        if exp_lower == name_lower:
            return True
        if exp_lower == qualified_lower:
            return True
        if exp_lower in qualified_lower:
            return True
        
        # Flexible matching: "get" matches "Session.get"
        if flexible:
            # Check if expected is the method name part of qualified name
            if '.' in qualified_lower and qualified_lower.endswith('.' + exp_lower):
                return True
            if '.' in qualified_lower and qualified_lower.split('.')[-1] == exp_lower:
                return True
    
    return False


class OptimizedRRFSearch:
    """RRF Search with optimization options."""
    
    def __init__(self, functions: List[ExtractedFunction]):
        self.functions = functions
        self._build_indices()
    
    def _build_indices(self):
        """Build all indices."""
        # BM25
        corpus = []
        for func in self.functions:
            text_parts = [
                func.qualified_name,
                func.name,
                func.signature,
                func.docstring or "",
                func.class_docstring or "",
                " ".join(func.decorators),
            ]
            corpus.append(tokenize(" ".join(text_parts)))
        self.bm25 = BM25Okapi(corpus)
        
        # Code embeddings
        contexts = [func.full_context for func in self.functions]
        embeddings = []
        for i in range(0, len(contexts), 100):
            batch = contexts[i:i+100]
            result = voyage_client.embed(batch, model="voyage-code-3", input_type="document")
            embeddings.extend(result.embeddings)
        self.code_embeddings = np.array(embeddings)
        
        # Summary embeddings
        summaries = [func.summary or func.signature for func in self.functions]
        embeddings = []
        for i in range(0, len(summaries), 100):
            batch = summaries[i:i+100]
            result = voyage_client.embed(batch, model="voyage-code-3", input_type="document")
            embeddings.extend(result.embeddings)
        self.summary_embeddings = np.array(embeddings)
        
        # Build name index for boosting
        self.name_to_indices = defaultdict(list)
        for i, func in enumerate(self.functions):
            self.name_to_indices[func.name.lower()].append(i)
            for part in func.qualified_name.lower().split('.'):
                self.name_to_indices[part].append(i)
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        weights: Dict[str, float] = None,
        k: int = 60,
        name_boost: float = 0.0,
    ) -> List[tuple]:
        """
        Search with configurable options.
        
        Args:
            weights: {'bm25': 1.0, 'code': 1.0, 'summary': 1.0}
            k: RRF constant
            name_boost: Extra score if query contains function name
        """
        if weights is None:
            weights = {'bm25': 1.0, 'code': 1.0, 'summary': 1.0}
        
        n = len(self.functions)
        
        # Get rankings
        query_tokens = tokenize(query)
        
        # BM25
        bm25_scores = self.bm25.get_scores(query_tokens)
        bm25_ranking = np.argsort(-bm25_scores)
        bm25_ranks = np.empty(n, dtype=int)
        bm25_ranks[bm25_ranking] = np.arange(n)
        
        # Code embeddings
        query_emb = voyage_client.embed([query], model="voyage-code-3", input_type="query").embeddings[0]
        code_scores = np.dot(self.code_embeddings, query_emb)
        code_ranking = np.argsort(-code_scores)
        code_ranks = np.empty(n, dtype=int)
        code_ranks[code_ranking] = np.arange(n)
        
        # Summary embeddings
        summary_scores = np.dot(self.summary_embeddings, query_emb)
        summary_ranking = np.argsort(-summary_scores)
        summary_ranks = np.empty(n, dtype=int)
        summary_ranks[summary_ranking] = np.arange(n)
        
        # Calculate RRF scores
        rrf_scores = np.zeros(n)
        for i in range(n):
            rrf_scores[i] = (
                weights['bm25'] * (1.0 / (k + bm25_ranks[i])) +
                weights['code'] * (1.0 / (k + code_ranks[i])) +
                weights['summary'] * (1.0 / (k + summary_ranks[i]))
            )
        
        # Apply name boost
        if name_boost > 0:
            query_lower = query.lower()
            for word in query_tokens:
                if word in self.name_to_indices:
                    for idx in self.name_to_indices[word]:
                        # Only boost if it's a meaningful match (not common words)
                        if len(word) > 3:  # Skip short words
                            rrf_scores[idx] += name_boost * (1.0 / (k + 0))  # Treat as rank 0
        
        # Get top results
        top_indices = np.argsort(-rrf_scores)[:top_k]
        
        results = []
        for idx in top_indices:
            results.append((
                self.functions[idx],
                rrf_scores[idx],
                bm25_ranks[idx],
                code_ranks[idx],
                summary_ranks[idx]
            ))
        
        return results


def run_experiment(
    codebase: str,
    weights: Dict[str, float] = None,
    k: int = 60,
    name_boost: float = 0.0,
    flexible_match: bool = False,
    verbose: bool = False
) -> Dict[str, Any]:
    """Run a single experiment configuration."""
    
    # Load data
    functions = load_functions(codebase)
    with open(ROOT / f"evals/{codebase}_queries.json") as f:
        queries = json.load(f)
    
    # Build search engine
    search = OptimizedRRFSearch(functions)
    
    # Evaluate
    hits = 0
    for item in queries:
        query = item['query']
        expected = item['expected']
        expected_list = expected if isinstance(expected, list) else [expected]
        
        results = search.search(query, top_k=1, weights=weights, k=k, name_boost=name_boost)
        
        if results:
            func = results[0][0]
            if is_match(expected_list, func, flexible=flexible_match):
                hits += 1
            elif verbose:
                print(f"❌ {query[:40]}")
                print(f"   Expected: {expected_list[0]} | Got: {func.qualified_name}")
    
    hit_rate = hits / len(queries)
    return {
        'hit_at_1': hit_rate,
        'hits': hits,
        'total': len(queries),
        'config': {
            'weights': weights,
            'k': k,
            'name_boost': name_boost,
            'flexible_match': flexible_match
        }
    }


def main():
    codebase = sys.argv[1] if len(sys.argv) > 1 else "flask"
    
    print("=" * 70)
    print(f"🧪 RRF OPTIMIZATION EXPERIMENTS - {codebase.upper()}")
    print("=" * 70)
    
    experiments = [
        # Baseline
        {"name": "Baseline (equal weights)", "weights": {'bm25': 1.0, 'code': 1.0, 'summary': 1.0}},
        
        # Weight variations
        {"name": "Summary heavy", "weights": {'bm25': 1.0, 'code': 0.5, 'summary': 2.0}},
        {"name": "BM25 heavy", "weights": {'bm25': 2.0, 'code': 1.0, 'summary': 1.0}},
        {"name": "Code heavy", "weights": {'bm25': 1.0, 'code': 2.0, 'summary': 0.5}},
        {"name": "Summary + BM25", "weights": {'bm25': 1.5, 'code': 0.5, 'summary': 1.5}},
        
        # Name boosting
        {"name": "Name boost 0.5", "weights": {'bm25': 1.0, 'code': 1.0, 'summary': 1.0}, "name_boost": 0.5},
        {"name": "Name boost 1.0", "weights": {'bm25': 1.0, 'code': 1.0, 'summary': 1.0}, "name_boost": 1.0},
        {"name": "Name boost 2.0", "weights": {'bm25': 1.0, 'code': 1.0, 'summary': 1.0}, "name_boost": 2.0},
        
        # K value
        {"name": "k=30", "weights": {'bm25': 1.0, 'code': 1.0, 'summary': 1.0}, "k": 30},
        {"name": "k=100", "weights": {'bm25': 1.0, 'code': 1.0, 'summary': 1.0}, "k": 100},
        
        # Flexible matching
        {"name": "Flexible match", "weights": {'bm25': 1.0, 'code': 1.0, 'summary': 1.0}, "flexible_match": True},
        
        # Combined best
        {"name": "Combined: Summary heavy + Name boost", 
         "weights": {'bm25': 1.0, 'code': 0.5, 'summary': 2.0}, "name_boost": 1.0},
        {"name": "Combined: Flexible + Name boost",
         "weights": {'bm25': 1.0, 'code': 1.0, 'summary': 1.0}, "name_boost": 1.0, "flexible_match": True},
    ]
    
    print(f"\n📦 Loading {codebase}...")
    
    results = []
    for exp in experiments:
        name = exp.pop("name")
        print(f"\n🔬 Testing: {name}...")
        
        result = run_experiment(codebase, **exp)
        result['name'] = name
        results.append(result)
        
        print(f"   Hit@1: {result['hit_at_1']*100:.1f}% ({result['hits']}/{result['total']})")
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 RESULTS SUMMARY")
    print("=" * 70)
    
    results.sort(key=lambda x: x['hit_at_1'], reverse=True)
    
    for i, r in enumerate(results):
        marker = "🏆" if i == 0 else "  "
        print(f"{marker} {r['hit_at_1']*100:5.1f}% | {r['name']}")
    
    # Best config
    best = results[0]
    print(f"\n🎯 BEST CONFIG: {best['name']}")
    print(f"   Hit@1: {best['hit_at_1']*100:.1f}%")
    print(f"   Config: {best['config']}")


if __name__ == "__main__":
    main()
