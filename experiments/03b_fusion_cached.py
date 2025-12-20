"""
Experiment 03b: Cached Embeddings + Fusion Strategy
====================================================
No more API rate limit pain! 🎉

This script:
1. Loads/creates cached embeddings (one-time API cost)
2. Tests fusion strategies INSTANTLY (no API calls)
"""

import asyncio
import os
import sys
import json
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

import voyageai

voyage_client = voyageai.AsyncClient(api_key=os.getenv("VOYAGE_API_KEY"))

CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)


# =============================================================================
# GROUND TRUTH
# =============================================================================

GROUND_TRUTH = [
    ("update the store state", ["setState", "set"], "state"),
    ("get current state value", ["getState", "get"], "state"),
    ("listen for state changes", ["subscribe", "subscribeWithSelector"], "state"),
    ("create a new store", ["createStore", "create", "createStoreImpl"], "state"),
    ("save state to localStorage", ["persist", "setItem", "persistImpl"], "persist"),
    ("load saved state from storage", ["hydrate", "rehydrate", "getItem"], "persist"),
    ("clear persisted data", ["clearStorage", "removeItem"], "persist"),
    ("migrate old stored state version", ["migrate", "migration"], "persist"),
    ("custom storage adapter", ["createJSONStorage", "StateStorage"], "persist"),
    ("combine multiple stores", ["combine"], "middleware"),
    ("redux devtools integration", ["devtools"], "middleware"),
    ("use immer for immutable updates", ["immer"], "middleware"),
    ("subscribe to specific state slice", ["subscribeWithSelector"], "middleware"),
    ("use store in react component", ["useStore", "create", "useStoreWithEqualityFn"], "react"),
    ("shallow comparison for selectors", ["shallow", "useShallow"], "react"),
    ("avoid unnecessary rerenders", ["shallow", "useShallow", "equalityFn"], "react"),
    ("check if state objects are equal", ["shallow", "is", "Object.is"], "comparison"),
    ("merge new state with existing", ["merge", "assign", "Object.assign"], "state"),
    ("notify all listeners of change", ["listeners", "forEach", "notify"], "state"),
    ("handle storage not available", ["storage", "catch", "undefined"], "error"),
    ("server side rendering safe", ["ssrSafe", "skipHydration"], "ssr"),
]


# =============================================================================
# EMBEDDING CACHE
# =============================================================================

async def get_or_create_embeddings(texts: List[str], cache_name: str) -> np.ndarray:
    """Get embeddings from cache or create them."""
    cache_file = CACHE_DIR / f"{cache_name}.npy"
    
    if cache_file.exists():
        print(f"   📂 Loading cached {cache_name}...")
        return np.load(cache_file)
    
    print(f"   🔄 Creating {cache_name} embeddings (one-time)...")
    
    embeddings = []
    batch_size = 50
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        print(f"      Batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}...")
        
        await asyncio.sleep(21)  # Rate limit
        response = await voyage_client.embed(
            texts=batch,
            model="voyage-code-3",
            input_type="document"
        )
        embeddings.extend(response.embeddings)
    
    embeddings = np.array(embeddings)
    np.save(cache_file, embeddings)
    print(f"   💾 Cached to {cache_file}")
    
    return embeddings


async def get_query_embeddings() -> np.ndarray:
    """Get query embeddings from cache or create them."""
    cache_file = CACHE_DIR / "query_embeddings.npy"
    
    if cache_file.exists():
        print(f"   📂 Loading cached query embeddings...")
        return np.load(cache_file)
    
    print(f"   🔄 Creating query embeddings (one-time)...")
    
    queries = [q[0] for q in GROUND_TRUTH]
    
    await asyncio.sleep(21)
    response = await voyage_client.embed(
        texts=queries,
        model="voyage-code-3",
        input_type="query"
    )
    
    embeddings = np.array(response.embeddings)
    np.save(cache_file, embeddings)
    print(f"   💾 Cached to {cache_file}")
    
    return embeddings


# =============================================================================
# BM25 (No API needed - runs locally)
# =============================================================================

import re
import math
from collections import defaultdict

class CodeTokenizer:
    STOPWORDS = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'could', 'should', 'to', 'of', 'in', 'for', 'on',
        'with', 'at', 'by', 'from', 'as', 'into', 'through', 'and',
        'but', 'if', 'or', 'because', 'this', 'that', 'it',
        'function', 'const', 'let', 'var', 'return', 'export',
        'import', 'default', 'type', 'interface', 'class',
    }
    
    @classmethod
    def tokenize(cls, text: str) -> List[str]:
        tokens = []
        words = re.findall(r'[a-zA-Z][a-zA-Z0-9]*', text)
        
        for word in words:
            word_lower = word.lower()
            if word_lower in cls.STOPWORDS or len(word_lower) < 2:
                continue
            tokens.append(word_lower)
            
            # Split camelCase
            if re.search(r'[a-z][A-Z]', word):
                parts = re.sub('([A-Z])', r' \1', word).lower().split()
                tokens.extend([p for p in parts if len(p) >= 2 and p not in cls.STOPWORDS])
        
        return tokens


class BM25:
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.doc_tokens = []
        self.doc_lengths = []
        self.avg_doc_length = 0
        self.inverted_index = defaultdict(dict)
        self.doc_freqs = defaultdict(int)
        self.num_docs = 0
    
    def index(self, documents: List[Dict]):
        self.num_docs = len(documents)
        total_length = 0
        
        for doc_id, doc in enumerate(documents):
            text = f"{doc['name']} {doc['code']}"
            tokens = CodeTokenizer.tokenize(text)
            
            self.doc_tokens.append(tokens)
            self.doc_lengths.append(len(tokens))
            total_length += len(tokens)
            
            term_freqs = defaultdict(int)
            for token in tokens:
                term_freqs[token] += 1
            
            for term, freq in term_freqs.items():
                self.inverted_index[term][doc_id] = freq
                self.doc_freqs[term] += 1
        
        self.avg_doc_length = total_length / self.num_docs
    
    def _idf(self, term: str) -> float:
        doc_freq = self.doc_freqs.get(term, 0)
        if doc_freq == 0:
            return 0
        return math.log((self.num_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1)
    
    def score(self, doc_id: int, query_tokens: List[str]) -> float:
        score = 0.0
        doc_length = self.doc_lengths[doc_id]
        
        for token in query_tokens:
            if token not in self.inverted_index or doc_id not in self.inverted_index[token]:
                continue
            
            tf = self.inverted_index[token][doc_id]
            idf = self._idf(token)
            
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_length / self.avg_doc_length)
            score += idf * (numerator / denominator)
        
        return score
    
    def get_all_scores(self, query: str) -> np.ndarray:
        """Get BM25 scores for all documents."""
        query_tokens = CodeTokenizer.tokenize(query)
        scores = np.array([self.score(i, query_tokens) for i in range(self.num_docs)])
        return scores


# =============================================================================
# FUSION SEARCH ENGINE
# =============================================================================

def cosine_similarity_batch(query_emb: np.ndarray, doc_embs: np.ndarray) -> np.ndarray:
    """Cosine similarity between query and all docs (vectorized)."""
    query_norm = query_emb / np.linalg.norm(query_emb)
    doc_norms = doc_embs / np.linalg.norm(doc_embs, axis=1, keepdims=True)
    return np.dot(doc_norms, query_norm)


def normalize_scores(scores: np.ndarray) -> np.ndarray:
    """Min-max normalize to [0, 1]."""
    min_s, max_s = scores.min(), scores.max()
    if max_s - min_s > 0:
        return (scores - min_s) / (max_s - min_s)
    return np.ones_like(scores)


class FusionEngine:
    """
    Combines multiple signals:
    - BM25 on code
    - Semantic on code  
    - Semantic on summaries
    """
    
    def __init__(self, functions: List[Dict], 
                 code_embeddings: np.ndarray,
                 summary_embeddings: np.ndarray,
                 query_embeddings: np.ndarray):
        
        self.functions = functions
        self.code_embs = code_embeddings
        self.summary_embs = summary_embeddings
        self.query_embs = query_embeddings
        
        # Build BM25 index
        self.bm25 = BM25()
        self.bm25.index(functions)
    
    def search(self, query_idx: int, 
               bm25_weight: float = 0.3,
               code_semantic_weight: float = 0.3,
               summary_semantic_weight: float = 0.4) -> List[tuple]:
        """
        Search with configurable fusion weights.
        
        Returns: List of (function, score) tuples, sorted by score desc
        """
        query = GROUND_TRUTH[query_idx][0]
        query_emb = self.query_embs[query_idx]
        
        # Get scores from each source
        bm25_scores = normalize_scores(self.bm25.get_all_scores(query))
        code_scores = normalize_scores(cosine_similarity_batch(query_emb, self.code_embs))
        summary_scores = normalize_scores(cosine_similarity_batch(query_emb, self.summary_embs))
        
        # Fuse
        final_scores = (
            bm25_weight * bm25_scores +
            code_semantic_weight * code_scores +
            summary_semantic_weight * summary_scores
        )
        
        # Sort and return
        ranked_indices = np.argsort(final_scores)[::-1]
        return [(self.functions[i], final_scores[i]) for i in ranked_indices]


# =============================================================================
# EVALUATION
# =============================================================================

def check_hit(results: List[tuple], expected_names: List[str], k: int) -> bool:
    top_k_names = [r[0]['name'].lower() for r in results[:k]]
    return any(exp.lower() in name or name in exp.lower() 
               for exp in expected_names 
               for name in top_k_names)


def evaluate_config(engine: FusionEngine, bm25_w: float, code_w: float, summary_w: float) -> Dict:
    """Evaluate a specific weight configuration."""
    results = []
    
    for i, (query, expected, category) in enumerate(GROUND_TRUTH):
        search_results = engine.search(i, bm25_w, code_w, summary_w)
        
        results.append({
            'query': query,
            'expected': expected,
            'hit@1': check_hit(search_results, expected, 1),
            'hit@3': check_hit(search_results, expected, 3),
            'hit@5': check_hit(search_results, expected, 5),
            'top_result': search_results[0][0]['name'],
        })
    
    total = len(results)
    return {
        'hit@1': sum(r['hit@1'] for r in results) / total,
        'hit@3': sum(r['hit@3'] for r in results) / total,
        'hit@5': sum(r['hit@5'] for r in results) / total,
        'details': results
    }


# =============================================================================
# MAIN
# =============================================================================

async def main():
    print("=" * 70)
    print("EXPERIMENT 03b: FUSION SEARCH (Cached - No Rate Limits!)")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load functions with summaries
    summaries_file = Path(__file__).parent.parent / "results" / "exp03_summaries.json"
    with open(summaries_file) as f:
        data = json.load(f)
    functions = data['functions']
    print(f"📦 Loaded {len(functions)} functions")
    
    # Prepare texts for embedding
    code_texts = [f"Function: {f['name']}\n\n{f['code']}" for f in functions]
    summary_texts = [f['summary'] for f in functions]
    
    # Get/create embeddings (cached!)
    print("\n📦 Loading embeddings...")
    code_embs = await get_or_create_embeddings(code_texts, "code_embeddings")
    summary_embs = await get_or_create_embeddings(summary_texts, "summary_embeddings")
    query_embs = await get_query_embeddings()
    
    print(f"   ✅ Code embeddings: {code_embs.shape}")
    print(f"   ✅ Summary embeddings: {summary_embs.shape}")
    print(f"   ✅ Query embeddings: {query_embs.shape}")
    
    # Create fusion engine
    engine = FusionEngine(functions, code_embs, summary_embs, query_embs)
    
    # ==========================================================================
    # TEST MANY CONFIGURATIONS INSTANTLY!
    # ==========================================================================
    print("\n" + "=" * 70)
    print("TESTING FUSION CONFIGURATIONS (Instant - No API calls!)")
    print("=" * 70)
    
    configs = [
        # (bm25, code_semantic, summary_semantic, name)
        (0.0, 1.0, 0.0, "code_only (baseline)"),
        (0.0, 0.0, 1.0, "summary_only"),
        (0.3, 0.7, 0.0, "hybrid_no_summary (prev best)"),
        (0.2, 0.4, 0.4, "balanced_fusion"),
        (0.3, 0.3, 0.4, "summary_heavy"),
        (0.2, 0.5, 0.3, "code_heavy"),
        (0.1, 0.3, 0.6, "very_summary_heavy"),
        (0.4, 0.3, 0.3, "bm25_heavy"),
        (0.2, 0.2, 0.6, "summary_dominant"),
        (0.15, 0.35, 0.5, "tuned_fusion"),
    ]
    
    results = {}
    
    print(f"\n{'Config':<30} {'Hit@1':<10} {'Hit@3':<10} {'Hit@5':<10}")
    print("-" * 60)
    
    for bm25_w, code_w, summary_w, name in configs:
        metrics = evaluate_config(engine, bm25_w, code_w, summary_w)
        results[name] = {
            'weights': (bm25_w, code_w, summary_w),
            'metrics': metrics
        }
        print(f"{name:<30} {metrics['hit@1']:<10.1%} {metrics['hit@3']:<10.1%} {metrics['hit@5']:<10.1%}")
    
    # Find best
    best_name = max(results.keys(), key=lambda x: (results[x]['metrics']['hit@1'], results[x]['metrics']['hit@3']))
    best = results[best_name]
    
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"\n🏆 Best Config: {best_name}")
    print(f"   Weights: BM25={best['weights'][0]}, Code={best['weights'][1]}, Summary={best['weights'][2]}")
    print(f"   Hit@1: {best['metrics']['hit@1']:.1%}")
    print(f"   Hit@3: {best['metrics']['hit@3']:.1%}")
    print(f"   Hit@5: {best['metrics']['hit@5']:.1%}")
    
    prev_best = 0.714
    improvement = best['metrics']['hit@1'] - prev_best
    print(f"\n📈 vs Previous Best (71.4%): {improvement:+.1%}")
    
    # Show details for best config
    print("\n" + "=" * 70)
    print(f"DETAILED RESULTS: {best_name}")
    print("=" * 70)
    
    for item in best['metrics']['details']:
        status = "✅" if item['hit@1'] else ("⚠️" if item['hit@3'] else "❌")
        print(f"{status} \"{item['query'][:40]}...\" → {item['top_result']}")
    
    # Save results
    output_file = Path(__file__).parent.parent / "results" / f"exp03b_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    def convert(obj):
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert(i) for i in obj]
        return obj
    
    with open(output_file, 'w') as f:
        json.dump(convert({
            'timestamp': datetime.now().isoformat(),
            'experiment': '03b_fusion_cached',
            'results': {k: {'weights': v['weights'], 'hit@1': v['metrics']['hit@1'], 
                           'hit@3': v['metrics']['hit@3'], 'hit@5': v['metrics']['hit@5']} 
                       for k, v in results.items()},
            'best': best_name,
        }), f, indent=2)
    
    print(f"\n💾 Saved: {output_file}")
    print("\n✅ EXPERIMENT COMPLETE!")


if __name__ == "__main__":
    asyncio.run(main())
