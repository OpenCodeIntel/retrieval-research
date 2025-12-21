"""
Evaluate human-written queries against a codebase.
Uses same search approach as evaluate_codebase.py
"""
import json
import sys
import re
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi
import voyageai

ROOT = Path(__file__).parent.parent

# Initialize Voyage client
voyage_client = voyageai.Client()


@dataclass
class FunctionData:
    name: str
    qualified_name: str
    file_path: str
    code: str
    signature: str
    summary: str = None
    docstring: str = None
    
    @property
    def full_context(self):
        return f"{self.qualified_name}\n{self.signature}\n{self.code[:500]}"


def tokenize(text: str) -> List[str]:
    """Simple tokenization."""
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = re.sub(r'[_\-./]', ' ', text)
    return text.lower().split()


def build_indices(functions: List[FunctionData]):
    """Build search indices."""
    # BM25
    corpus = []
    for func in functions:
        text = " ".join([
            func.qualified_name, func.name, func.signature,
            func.docstring or "", func.summary or ""
        ])
        corpus.append(tokenize(text))
    bm25 = BM25Okapi(corpus)
    
    # Code embeddings
    contexts = [func.full_context for func in functions]
    code_emb = []
    for i in range(0, len(contexts), 50):
        batch = contexts[i:i+50]
        result = voyage_client.embed(batch, model="voyage-code-3", input_type="document")
        code_emb.extend(result.embeddings)
    code_emb = np.array(code_emb)
    
    # Summary embeddings
    summaries = [func.summary or func.signature for func in functions]
    summary_emb = []
    for i in range(0, len(summaries), 50):
        batch = summaries[i:i+50]
        result = voyage_client.embed(batch, model="voyage-code-3", input_type="document")
        summary_emb.extend(result.embeddings)
    summary_emb = np.array(summary_emb)
    
    return bm25, code_emb, summary_emb


def search_rrf(query, functions, bm25, code_emb, summary_emb, top_k=10, k=60):
    """Search with RRF fusion."""
    n = len(functions)
    
    q_tok = tokenize(query)
    bm25_scores = bm25.get_scores(q_tok)
    bm25_ranks = np.argsort(np.argsort(-bm25_scores))
    
    q_emb = voyage_client.embed([query], model="voyage-code-3", input_type="query").embeddings[0]
    code_scores = np.dot(code_emb, q_emb)
    code_ranks = np.argsort(np.argsort(-code_scores))
    summary_scores = np.dot(summary_emb, q_emb)
    summary_ranks = np.argsort(np.argsort(-summary_scores))
    
    rrf = np.array([
        1/(k+bm25_ranks[i]) + 1/(k+code_ranks[i]) + 1/(k+summary_ranks[i]) 
        for i in range(n)
    ])
    
    top_indices = np.argsort(-rrf)[:top_k]
    return [(functions[i], rrf[i]) for i in top_indices]


def rerank(query, candidates):
    """Rerank with Voyage."""
    docs = [f"{f.qualified_name}: {f.summary or f.docstring or f.signature}" for f, _ in candidates]
    
    result = voyage_client.rerank(
        query=query,
        documents=docs,
        model="rerank-2",
        top_k=len(candidates)
    )
    
    reranked = []
    for r in result.results:
        func, _ = candidates[r.index]
        reranked.append((func, r.relevance_score))
    return reranked


def evaluate_human_queries(codebase: str):
    """Run human queries against search engine."""
    
    # Load summaries
    summaries_path = ROOT / f"results/{codebase}_v2_summaries.json"
    if not summaries_path.exists():
        print(f"❌ Summaries not found: {summaries_path}")
        return
    
    with open(summaries_path) as f:
        data = json.load(f)
    
    # Load human queries
    queries_path = ROOT / f"evals/{codebase}_human_queries.json"
    if not queries_path.exists():
        print(f"❌ Human queries not found: {queries_path}")
        return
    
    with open(queries_path) as f:
        queries_data = json.load(f)
    
    # Convert to FunctionData
    functions = [
        FunctionData(
            name=fd['name'],
            qualified_name=fd['qualified_name'],
            file_path=fd['file_path'],
            code=fd['code'],
            signature=fd['signature'],
            summary=fd.get('summary'),
            docstring=fd.get('docstring')
        )
        for fd in data['functions']
    ]
    
    print(f"📂 Loaded {len(functions)} functions from {codebase}")
    print(f"🔍 Testing {len(queries_data['queries'])} human queries")
    print(f"🔨 Building indices...")
    
    bm25, code_emb, summary_emb = build_indices(functions)
    
    # Evaluate
    results = {
        'rrf_only': {'correct': 0, 'total': 0},
        'with_rerank': {'correct': 0, 'total': 0},
        'by_difficulty': {
            'easy': {'correct': 0, 'total': 0},
            'medium': {'correct': 0, 'total': 0},
            'hard': {'correct': 0, 'total': 0}
        },
        'failures': []
    }
    
    print("\n" + "=" * 70)
    print("EVALUATION RESULTS")
    print("=" * 70 + "\n")
    
    for q in queries_data['queries']:
        query = q['query']
        expected_list = q['expected']
        difficulty = q.get('difficulty', 'medium')
        
        results['rrf_only']['total'] += 1
        results['with_rerank']['total'] += 1
        results['by_difficulty'][difficulty]['total'] += 1
        
        # Search without reranking
        rrf_results = search_rrf(query, functions, bm25, code_emb, summary_emb, top_k=10)
        rrf_top = rrf_results[0][0].qualified_name if rrf_results else None
        rrf_hit = any(exp in (rrf_top or '') for exp in expected_list)
        
        # Search with reranking
        rerank_results = rerank(query, rrf_results)
        rerank_top = rerank_results[0][0].qualified_name if rerank_results else None
        rerank_hit = any(exp in (rerank_top or '') for exp in expected_list)
        
        if rrf_hit:
            results['rrf_only']['correct'] += 1
        if rerank_hit:
            results['with_rerank']['correct'] += 1
            results['by_difficulty'][difficulty]['correct'] += 1
        
        # Print result
        status = "✅" if rerank_hit else "❌"
        print(f"{status} [{difficulty:6}] \"{query}\"")
        if not rerank_hit:
            print(f"   Expected: {expected_list}")
            print(f"   Got: {rerank_top}")
            results['failures'].append({
                'query': query,
                'expected': expected_list,
                'got': rerank_top,
                'difficulty': difficulty
            })
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    rrf_pct = results['rrf_only']['correct'] / results['rrf_only']['total'] * 100
    rerank_pct = results['with_rerank']['correct'] / results['with_rerank']['total'] * 100
    
    print(f"\n📊 Overall Results:")
    print(f"   RRF Only:     {results['rrf_only']['correct']}/{results['rrf_only']['total']} = {rrf_pct:.1f}%")
    print(f"   + Reranking:  {results['with_rerank']['correct']}/{results['with_rerank']['total']} = {rerank_pct:.1f}%")
    print(f"   Improvement:  +{rerank_pct - rrf_pct:.1f}%")
    
    print(f"\n📊 By Difficulty:")
    for diff in ['easy', 'medium', 'hard']:
        d = results['by_difficulty'][diff]
        if d['total'] > 0:
            pct = d['correct'] / d['total'] * 100
            print(f"   {diff:6}: {d['correct']}/{d['total']} = {pct:.1f}%")
    
    print(f"\n❌ Failures: {len(results['failures'])}")
    
    return results


if __name__ == "__main__":
    codebase = sys.argv[1] if len(sys.argv) > 1 else "fiber"
    evaluate_human_queries(codebase)
