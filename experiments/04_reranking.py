"""
Experiment 04: Cross-Encoder Reranking (Optimized for Rate Limits)
===================================================================
Target: Push from 80.95% to 85-90% Hit@1

OPTIMIZED VERSION:
- Reuses the LinearFusionEngine from 03_checkpoint3b.py
- Only adds reranking on top
- Minimizes API calls

Strategy:
1. Use best fusion (code30_sum50_bm20) to get top 30 candidates  
2. Use Voyage rerank-2 to reorder them
3. One rerank call per query (21 total)
"""

import asyncio
import os
import sys
import json
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from collections import defaultdict
import math
import re
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

import voyageai

voyage_client = voyageai.AsyncClient(api_key=os.getenv("VOYAGE_API_KEY"))

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
# UTILITIES (copied from 03_checkpoint3b for self-contained)
# =============================================================================

def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def check_hit(results, expected_names, k):
    top_k_names = [r[0]['name'].lower() for r in results[:k]]
    return any(exp.lower() in name or name in exp.lower() 
               for exp in expected_names 
               for name in top_k_names)

class CodeTokenizer:
    STOPWORDS = {'the','a','an','is','are','was','were','be','been','being','have','has','had',
                 'do','does','did','will','would','could','should','to','of','in','for','on',
                 'with','at','by','from','as','into','through','and','but','if','or','because',
                 'this','that','it','function','const','let','var','return','export','import',
                 'default','type','interface','class'}
    
    @classmethod
    def tokenize(cls, text):
        tokens = []
        words = re.findall(r'[a-zA-Z][a-zA-Z0-9]*', text)
        for word in words:
            word_lower = word.lower()
            if word_lower in cls.STOPWORDS or len(word_lower) < 2:
                continue
            tokens.append(word_lower)
            if re.search(r'[a-z][A-Z]', word):
                parts = re.sub('([A-Z])', r' \1', word).lower().split()
                tokens.extend([p for p in parts if len(p) >= 2 and p not in cls.STOPWORDS])
        return tokens


class BM25Index:
    def __init__(self):
        self.k1, self.b = 1.5, 0.75
        self.documents, self.doc_lengths = [], []
        self.inverted_index = defaultdict(dict)
        self.doc_freqs = defaultdict(int)
        self.avg_doc_length, self.num_docs = 0, 0
    
    def index(self, documents):
        self.documents = documents
        self.num_docs = len(documents)
        total = 0
        for doc_id, doc in enumerate(documents):
            tokens = CodeTokenizer.tokenize(f"{doc['name']} {doc['code']}")
            self.doc_lengths.append(len(tokens))
            total += len(tokens)
            tf = defaultdict(int)
            for t in tokens: tf[t] += 1
            for t, f in tf.items():
                self.inverted_index[t][doc_id] = f
                self.doc_freqs[t] += 1
        self.avg_doc_length = total / self.num_docs if self.num_docs else 0
    
    def search(self, query, top_k=100):
        tokens = CodeTokenizer.tokenize(query)
        scores = []
        for doc_id in range(self.num_docs):
            score = 0.0
            dl = self.doc_lengths[doc_id]
            for t in tokens:
                if t not in self.inverted_index or doc_id not in self.inverted_index[t]:
                    continue
                tf = self.inverted_index[t][doc_id]
                df = self.doc_freqs.get(t, 0)
                idf = math.log((self.num_docs - df + 0.5) / (df + 0.5) + 1) if df else 0
                score += idf * (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * dl / self.avg_doc_length))
            if score > 0:
                scores.append((self.documents[doc_id], score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class LinearFusionEngine:
    """Fusion engine with batch operations to minimize API calls"""
    
    def __init__(self):
        self.bm25 = BM25Index()
        self.code_embs = []
        self.summary_embs = []
        self.functions = []
    
    async def index(self, functions):
        self.functions = functions
        print("   BM25...", end=" ")
        self.bm25.index(functions)
        print("✓")
        
        print("   Code embeddings...", end=" ", flush=True)
        texts = [f"Function: {f['name']}\n\n{f['code']}" for f in functions]
        self.code_embs = await self._embed(texts)
        print("✓")
        
        print("   Summary embeddings...", end=" ", flush=True)
        texts = [f['summary'] for f in functions]
        self.summary_embs = await self._embed(texts)
        print("✓")
    
    async def _embed(self, texts):
        embs = []
        for i in range(0, len(texts), 50):
            await asyncio.sleep(21)  # Rate limit: 3 RPM
            r = await voyage_client.embed(texts=texts[i:i+50], model="voyage-code-3", input_type="document")
            embs.extend(r.embeddings)
        return embs
    
    def _normalize(self, scores):
        if not scores: return {}
        vals = [s for _, s in scores]
        mn, mx = min(vals), max(vals)
        rng = mx - mn if mx > mn else 1
        return {f['name']: (s - mn) / rng for f, s in scores}
    
    async def batch_search_all(self, queries, top_k=30, alpha=0.3, beta=0.5, gamma=0.2):
        """
        Search all queries in one batch (single API call for query embeddings!)
        Returns dict: query -> list of (func, score) tuples
        """
        print(f"   Embedding {len(queries)} queries...", end=" ", flush=True)
        await asyncio.sleep(21)
        r = await voyage_client.embed(texts=queries, model="voyage-code-3", input_type="query")
        q_embs = r.embeddings
        print("✓")
        
        all_results = {}
        for query, q_emb in zip(queries, q_embs):
            bm25_raw = self.bm25.search(query, 100)
            code_raw = [(f, cosine_similarity(q_emb, e)) for f, e in zip(self.functions, self.code_embs)]
            summ_raw = [(f, cosine_similarity(q_emb, e)) for f, e in zip(self.functions, self.summary_embs)]
            
            bm25_n = self._normalize(bm25_raw)
            code_n = self._normalize(code_raw)
            summ_n = self._normalize(summ_raw)
            
            combined = {}
            for f in self.functions:
                name = f['name']
                combined[name] = alpha * code_n.get(name, 0) + beta * summ_n.get(name, 0) + gamma * bm25_n.get(name, 0)
            
            lookup = {f['name']: f for f in self.functions}
            results = [(lookup[n], s) for n, s in combined.items()]
            results.sort(key=lambda x: x[1], reverse=True)
            all_results[query] = results[:top_k]
        
        return all_results


# =============================================================================
# RERANKER
# =============================================================================

async def rerank_single(query: str, candidates: List[tuple], top_k: int = 10) -> List[tuple]:
    """
    Rerank a single query's candidates using Voyage rerank-2
    
    Args:
        query: Search query
        candidates: List of (function_dict, initial_score) tuples
        top_k: Number of results to return
    
    Returns:
        Reranked list of (function_dict, rerank_score) tuples
    """
    if not candidates:
        return []
    
    # Prepare documents: summary + name + code snippet
    documents = []
    for func, _ in candidates:
        doc_text = f"Function: {func['name']}\n\nDescription: {func['summary']}\n\nCode:\n{func['code'][:500]}"
        documents.append(doc_text)
    
    await asyncio.sleep(21)  # Rate limit
    
    try:
        response = await voyage_client.rerank(
            query=query,
            documents=documents,
            model="rerank-2",
            top_k=top_k
        )
        
        # Map back to functions
        results = []
        for item in response.results:
            func = candidates[item.index][0]
            results.append((func, item.relevance_score))
        
        return results
        
    except Exception as e:
        print(f"   ⚠️ Rerank error: {e}")
        return candidates[:top_k]


# =============================================================================
# MAIN
# =============================================================================

async def main():
    print("=" * 70)
    print("EXPERIMENT 04: Cross-Encoder Reranking")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target: >85% Hit@1 (up from 80.95%)\n")
    
    # Load functions
    summaries_file = Path(__file__).parent.parent / "results" / "exp03_summaries.json"
    with open(summaries_file) as f:
        functions = json.load(f)['functions']
    print(f"📦 Loaded {len(functions)} functions\n")
    
    # Initialize and index
    engine = LinearFusionEngine()
    print("📊 Indexing (this takes ~2 min due to rate limits)...")
    await engine.index(functions)
    
    # Get all queries
    queries = [q[0] for q in GROUND_TRUTH]
    
    # ==========================================================================
    # STAGE 1: Get fusion results for all queries (ONE API call)
    # ==========================================================================
    print("\n" + "=" * 70)
    print("STAGE 1: Fusion Retrieval (best config: code30_sum50_bm20)")
    print("=" * 70)
    
    # Get top 30 candidates for each query
    fusion_results = await engine.batch_search_all(queries, top_k=30, alpha=0.3, beta=0.5, gamma=0.2)
    
    # Evaluate baseline (no reranking)
    baseline_hits = {'hit@1': 0, 'hit@3': 0, 'hit@5': 0}
    baseline_details = []
    
    for query, expected, category in GROUND_TRUTH:
        candidates = fusion_results[query]
        h1 = check_hit(candidates, expected, 1)
        h3 = check_hit(candidates, expected, 3)
        h5 = check_hit(candidates, expected, 5)
        
        baseline_hits['hit@1'] += h1
        baseline_hits['hit@3'] += h3
        baseline_hits['hit@5'] += h5
        baseline_details.append({
            'query': query, 'expected': expected,
            'hit@1': h1, 'hit@3': h3, 'hit@5': h5,
            'top_result': candidates[0][0]['name']
        })
        
        status = "✅" if h1 else ("⚠️" if h3 else "❌")
        print(f"   {status} \"{query[:40]}...\" → {candidates[0][0]['name']}")
    
    total = len(GROUND_TRUTH)
    baseline_metrics = {
        'hit@1': baseline_hits['hit@1'] / total,
        'hit@3': baseline_hits['hit@3'] / total,
        'hit@5': baseline_hits['hit@5'] / total,
    }
    
    print(f"\n📊 Baseline (Fusion only): Hit@1={baseline_metrics['hit@1']:.1%}, Hit@3={baseline_metrics['hit@3']:.1%}")
    
    # ==========================================================================
    # STAGE 2: Rerank each query (21 API calls, ~7 min at 3 RPM)
    # ==========================================================================
    print("\n" + "=" * 70)
    print("STAGE 2: Reranking with Voyage rerank-2")
    print("=" * 70)
    print("⏳ This will take ~7-8 min due to API rate limits (21 queries × 21s)...")
    print("   (Rate limit: 3 requests per minute)\n")
    
    rerank_hits = {'hit@1': 0, 'hit@3': 0, 'hit@5': 0}
    rerank_details = []
    
    for i, (query, expected, category) in enumerate(GROUND_TRUTH):
        candidates = fusion_results[query]
        
        # Rerank top 30 → get top 10
        reranked = await rerank_single(query, candidates, top_k=10)
        
        h1 = check_hit(reranked, expected, 1)
        h3 = check_hit(reranked, expected, 3)
        h5 = check_hit(reranked, expected, 5)
        
        rerank_hits['hit@1'] += h1
        rerank_hits['hit@3'] += h3
        rerank_hits['hit@5'] += h5
        
        rerank_details.append({
            'query': query, 'expected': expected,
            'hit@1': h1, 'hit@3': h3, 'hit@5': h5,
            'top_result': reranked[0][0]['name'] if reranked else 'N/A',
            'top_score': reranked[0][1] if reranked else 0,
        })
        
        status = "✅" if h1 else ("⚠️" if h3 else "❌")
        print(f"   [{i+1}/{total}] {status} \"{query[:35]}...\" → {reranked[0][0]['name'] if reranked else 'N/A'}")
    
    rerank_metrics = {
        'hit@1': rerank_hits['hit@1'] / total,
        'hit@3': rerank_hits['hit@3'] / total,
        'hit@5': rerank_hits['hit@5'] / total,
    }
    
    print(f"\n📊 With Reranking: Hit@1={rerank_metrics['hit@1']:.1%}, Hit@3={rerank_metrics['hit@3']:.1%}")
    
    # ==========================================================================
    # COMPARISON
    # ==========================================================================
    print("\n" + "=" * 70)
    print("RESULTS COMPARISON")
    print("=" * 70)
    
    prev_best = 0.8095
    
    print(f"\n{'Method':<25} {'Hit@1':<10} {'Hit@3':<10} {'Hit@5':<10} {'vs Exp03':<12}")
    print("-" * 67)
    print(f"{'Exp03 Best (80.95%)':<25} {'80.95%':<10} {'100%':<10} {'100%':<10} {'baseline':<12}")
    print(f"{'Fusion (this run)':<25} {baseline_metrics['hit@1']:<10.1%} {baseline_metrics['hit@3']:<10.1%} {baseline_metrics['hit@5']:<10.1%} {baseline_metrics['hit@1']-prev_best:+.1%}")
    print(f"{'Fusion + Rerank':<25} {rerank_metrics['hit@1']:<10.1%} {rerank_metrics['hit@3']:<10.1%} {rerank_metrics['hit@5']:<10.1%} {rerank_metrics['hit@1']-prev_best:+.1%}")
    
    # Show what changed
    print("\n" + "=" * 70)
    print("DETAILED CHANGES (Reranking Impact)")
    print("=" * 70)
    
    improved = []
    regressed = []
    same = []
    
    for b, r in zip(baseline_details, rerank_details):
        if r['hit@1'] and not b['hit@1']:
            improved.append((b['query'], b['top_result'], r['top_result']))
        elif b['hit@1'] and not r['hit@1']:
            regressed.append((b['query'], b['top_result'], r['top_result']))
        else:
            same.append(b['query'])
    
    if improved:
        print(f"\n✅ IMPROVED by reranking ({len(improved)}):")
        for q, old, new in improved:
            print(f"   \"{q[:40]}...\": {old} → {new}")
    
    if regressed:
        print(f"\n❌ REGRESSED by reranking ({len(regressed)}):")
        for q, old, new in regressed:
            print(f"   \"{q[:40]}...\": {old} → {new}")
    
    print(f"\n➡️  Same result: {len(same)} queries")
    
    # Final verdict
    print("\n" + "=" * 70)
    print("FINAL VERDICT")
    print("=" * 70)
    
    improvement = rerank_metrics['hit@1'] - prev_best
    
    if rerank_metrics['hit@1'] >= 0.85:
        print(f"\n🏆 TARGET ACHIEVED! {rerank_metrics['hit@1']:.1%} Hit@1 (target was >85%)")
    elif rerank_metrics['hit@1'] > prev_best:
        print(f"\n⚠️ IMPROVEMENT: {rerank_metrics['hit@1']:.1%} Hit@1 ({improvement:+.1%} vs 80.95%)")
        print(f"   But below 85% target")
    else:
        print(f"\n❌ NO IMPROVEMENT: Reranking didn't help on this dataset")
    
    # Save
    output = {
        'timestamp': datetime.now().isoformat(),
        'experiment': '04_reranking',
        'target': '>85% Hit@1',
        'previous_best': prev_best,
        'baseline_metrics': baseline_metrics,
        'rerank_metrics': rerank_metrics,
        'improvement': improvement,
        'improved_queries': improved,
        'regressed_queries': regressed,
    }
    
    results_dir = Path(__file__).parent.parent / "results"
    filename = results_dir / f"exp04_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(filename, 'w') as f:
        json.dump(output, f, indent=2, default=float)
    
    print(f"\n💾 Results saved: {filename}")
    print("\n✅ EXPERIMENT 04 COMPLETE!")


if __name__ == "__main__":
    asyncio.run(main())
