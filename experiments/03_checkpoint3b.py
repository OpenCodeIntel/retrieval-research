"""
Experiment 03 - CHECKPOINT 3b: Smarter Fusion
==============================================
Instead of RRF (which hurt results), try:
1. Score-based linear fusion (like exp02)
2. Cascade: Summary for recall → Hybrid for ranking
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

def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def check_hit(results, expected_names, k):
    top_k_names = [r[0]['name'].lower() for r in results[:k]]
    return any(exp.lower() in name or name in exp.lower() 
               for exp in expected_names 
               for name in top_k_names)

class CodeTokenizer:
    STOPWORDS = {'the','a','an','is','are','was','were','be','been','being','have','has','had','do','does','did','will','would','could','should','may','might','must','shall','can','need','to','of','in','for','on','with','at','by','from','as','into','through','during','before','after','above','below','between','under','again','then','once','here','there','when','where','why','how','all','each','few','more','most','other','some','such','no','nor','not','only','own','same','so','than','too','very','just','and','but','if','or','because','until','while','this','that','these','those','it','function','const','let','var','return','export','import','default','type','interface','class'}
    
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
        self.documents, self.doc_tokens, self.doc_lengths = [], [], []
        self.inverted_index = defaultdict(dict)
        self.doc_freqs = defaultdict(int)
        self.avg_doc_length = 0
        self.num_docs = 0
    
    def index(self, documents):
        self.documents = documents
        self.num_docs = len(documents)
        total = 0
        for doc_id, doc in enumerate(documents):
            tokens = CodeTokenizer.tokenize(f"{doc['name']} {doc['code']}")
            self.doc_tokens.append(tokens)
            self.doc_lengths.append(len(tokens))
            total += len(tokens)
            tf = defaultdict(int)
            for t in tokens: tf[t] += 1
            for t, f in tf.items():
                self.inverted_index[t][doc_id] = f
                self.doc_freqs[t] += 1
        self.avg_doc_length = total / self.num_docs if self.num_docs else 0
    
    def search(self, query, top_k=50):
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
    """
    Simple linear fusion: final = α*code_semantic + β*summary_semantic + γ*bm25
    Scores are normalized before fusion.
    """
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
            await asyncio.sleep(21)
            r = await voyage_client.embed(texts=texts[i:i+50], model="voyage-code-3", input_type="document")
            embs.extend(r.embeddings)
        return embs
    
    def _normalize(self, scores):
        if not scores: return {}
        vals = [s for _, s in scores]
        mn, mx = min(vals), max(vals)
        rng = mx - mn if mx > mn else 1
        return {f['name']: (s - mn) / rng for f, s in scores}
    
    async def search(self, query, alpha=0.4, beta=0.4, gamma=0.2):
        """alpha=code_semantic, beta=summary_semantic, gamma=bm25"""
        await asyncio.sleep(21)
        r = await voyage_client.embed(texts=[query], model="voyage-code-3", input_type="query")
        q_emb = r.embeddings[0]
        
        # Get all scores
        bm25_raw = self.bm25.search(query, 100)
        code_raw = [(f, cosine_similarity(q_emb, e)) for f, e in zip(self.functions, self.code_embs)]
        summ_raw = [(f, cosine_similarity(q_emb, e)) for f, e in zip(self.functions, self.summary_embs)]
        
        # Normalize
        bm25_n = self._normalize(bm25_raw)
        code_n = self._normalize(code_raw)
        summ_n = self._normalize(summ_raw)
        
        # Combine
        combined = {}
        for f in self.functions:
            name = f['name']
            combined[name] = (
                alpha * code_n.get(name, 0) +
                beta * summ_n.get(name, 0) +
                gamma * bm25_n.get(name, 0)
            )
        
        lookup = {f['name']: f for f in self.functions}
        results = [(lookup[n], s) for n, s in combined.items()]
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:10]
    
    async def batch_search(self, queries, alpha=0.4, beta=0.4, gamma=0.2):
        await asyncio.sleep(21)
        r = await voyage_client.embed(texts=queries, model="voyage-code-3", input_type="query")
        q_embs = r.embeddings
        
        all_results = []
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
            all_results.append(results[:10])
        
        return all_results


async def run():
    print("=" * 70)
    print("CHECKPOINT 3b: Linear Fusion (Code + Summary + BM25)")
    print("=" * 70)
    
    # Load
    with open(Path(__file__).parent.parent / "results" / "exp03_summaries.json") as f:
        functions = json.load(f)['functions']
    print(f"📦 Loaded {len(functions)} functions\n")
    
    # Index
    engine = LinearFusionEngine()
    await engine.index(functions)
    
    # Test configs: (alpha=code, beta=summary, gamma=bm25)
    configs = [
        ("code70_sum20_bm10", 0.7, 0.2, 0.1),
        ("code50_sum30_bm20", 0.5, 0.3, 0.2),
        ("code40_sum40_bm20", 0.4, 0.4, 0.2),
        ("code30_sum50_bm20", 0.3, 0.5, 0.2),
        ("code60_sum30_bm10", 0.6, 0.3, 0.1),
        ("code50_sum40_bm10", 0.5, 0.4, 0.1),
    ]
    
    results = {}
    queries = [q[0] for q in GROUND_TRUTH]
    prev_best = 0.714
    
    for name, alpha, beta, gamma in configs:
        print(f"\n{'─'*60}")
        print(f"{name}: code={alpha}, summary={beta}, bm25={gamma}")
        print(f"{'─'*60}")
        
        search_results = await engine.batch_search(queries, alpha, beta, gamma)
        
        hits = []
        for i, (q, exp, _) in enumerate(GROUND_TRUTH):
            res = search_results[i]
            h1 = check_hit(res, exp, 1)
            h3 = check_hit(res, exp, 3)
            hits.append({'hit@1': h1, 'hit@3': h3, 'top': res[0][0]['name']})
            status = "✅" if h1 else ("⚠️" if h3 else "❌")
            print(f"  {status} {q[:38]}... → {res[0][0]['name']}")
        
        h1 = sum(h['hit@1'] for h in hits) / len(hits)
        h3 = sum(h['hit@3'] for h in hits) / len(hits)
        results[name] = {'hit@1': h1, 'hit@3': h3, 'params': (alpha, beta, gamma)}
        print(f"\n  📊 Hit@1={h1:.1%}, Hit@3={h3:.1%}, vs_hybrid={h1-prev_best:+.1%}")
    
    # Summary
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print(f"\n{'Config':<25} {'Hit@1':<10} {'Hit@3':<10} {'vs Hybrid'}")
    print("-" * 55)
    print(f"{'hybrid-α0.7 (baseline)':<25} {'71.4%':<10} {'95.2%':<10} {'--'}")
    
    for name in sorted(results.keys(), key=lambda x: results[x]['hit@1'], reverse=True):
        r = results[name]
        print(f"{name:<25} {r['hit@1']:<10.1%} {r['hit@3']:<10.1%} {r['hit@1']-prev_best:+.1%}")
    
    best = max(results.keys(), key=lambda x: results[x]['hit@1'])
    print(f"\n🏆 Best: {best} with {results[best]['hit@1']:.1%} Hit@1")
    
    # Save
    with open(Path(__file__).parent.parent / "results" / f"exp03_cp3b_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
        json.dump({'results': results, 'best': best}, f, indent=2)
    
    print("\n✅ CHECKPOINT 3b COMPLETE!")


if __name__ == "__main__":
    asyncio.run(run())
