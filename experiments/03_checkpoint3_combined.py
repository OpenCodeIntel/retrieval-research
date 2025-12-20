"""
Experiment 03 - CHECKPOINT 3: Combined Approach
================================================
Fuse Hybrid (BM25 + Semantic on code) with Summary embeddings

Insight from analysis:
- Hybrid wins on: exact keyword matches (setState, useStore)  
- Summary wins on: conceptual matches (devtools, subscribe)
- Combined potential: 81% Hit@1!

Strategy: RRF fusion of both result sets
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
# UTILITIES
# =============================================================================

def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def check_hit(results, expected_names, k):
    top_k_names = [r[0]['name'].lower() for r in results[:k]]
    return any(exp.lower() in name or name in exp.lower() 
               for exp in expected_names 
               for name in top_k_names)


# =============================================================================
# BM25 (from exp02)
# =============================================================================

class CodeTokenizer:
    STOPWORDS = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'could', 'should', 'may', 'might', 'must', 'shall',
        'can', 'need', 'to', 'of', 'in', 'for', 'on', 'with', 'at',
        'by', 'from', 'as', 'into', 'through', 'during', 'before',
        'after', 'above', 'below', 'between', 'under', 'again',
        'then', 'once', 'here', 'there', 'when', 'where', 'why',
        'how', 'all', 'each', 'few', 'more', 'most', 'other', 'some',
        'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so',
        'than', 'too', 'very', 'just', 'and', 'but', 'if', 'or',
        'because', 'until', 'while', 'this', 'that', 'these', 'those',
        'it', 'function', 'const', 'let', 'var', 'return', 'export',
        'import', 'default', 'type', 'interface', 'class',
    }
    
    @staticmethod
    def split_camel_case(text):
        result = re.sub('([A-Z])', r' \1', text)
        return result.lower().split()
    
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
                parts = cls.split_camel_case(word)
                tokens.extend([p for p in parts if len(p) >= 2 and p not in cls.STOPWORDS])
        return tokens


class BM25Index:
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.tokenizer = CodeTokenizer()
        self.documents = []
        self.doc_tokens = []
        self.doc_lengths = []
        self.avg_doc_length = 0
        self.inverted_index = defaultdict(dict)
        self.doc_freqs = defaultdict(int)
        self.num_docs = 0
    
    def index(self, documents):
        self.documents = documents
        self.num_docs = len(documents)
        total_length = 0
        
        for doc_id, doc in enumerate(documents):
            text = f"{doc['name']} {doc['code']}"
            tokens = self.tokenizer.tokenize(text)
            self.doc_tokens.append(tokens)
            self.doc_lengths.append(len(tokens))
            total_length += len(tokens)
            
            term_freqs = defaultdict(int)
            for token in tokens:
                term_freqs[token] += 1
            
            for term, freq in term_freqs.items():
                self.inverted_index[term][doc_id] = freq
                self.doc_freqs[term] += 1
        
        self.avg_doc_length = total_length / self.num_docs if self.num_docs > 0 else 0
    
    def _idf(self, term):
        doc_freq = self.doc_freqs.get(term, 0)
        if doc_freq == 0:
            return 0
        return math.log((self.num_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1)
    
    def search(self, query, top_k=50):
        query_tokens = self.tokenizer.tokenize(query)
        scores = []
        
        for doc_id in range(self.num_docs):
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
            
            if score > 0:
                scores.append((self.documents[doc_id], score))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# =============================================================================
# COMBINED SEARCH ENGINE
# =============================================================================

class CombinedSearchEngine:
    """
    Combines:
    1. BM25 on code (keyword matching)
    2. Semantic on code (Voyage embeddings)  
    3. Semantic on summaries (LLM-generated descriptions)
    
    Uses RRF fusion to combine all three.
    """
    
    def __init__(self):
        self.bm25 = BM25Index()
        self.code_embeddings = []
        self.summary_embeddings = []
        self.functions = []
    
    async def index(self, functions_with_summaries):
        """Index with all three methods."""
        self.functions = functions_with_summaries
        
        # 1. BM25 on code
        print("   [1/3] Building BM25 index on code...")
        self.bm25.index(functions_with_summaries)
        
        # 2. Semantic embeddings on code
        print("   [2/3] Embedding code with Voyage...")
        code_texts = [f"Function: {f['name']}\n\n{f['code']}" for f in functions_with_summaries]
        self.code_embeddings = await self._embed_batch(code_texts)
        
        # 3. Semantic embeddings on summaries
        print("   [3/3] Embedding summaries with Voyage...")
        summary_texts = [f['summary'] for f in functions_with_summaries]
        self.summary_embeddings = await self._embed_batch(summary_texts)
        
        print(f"   ✅ Indexed {len(self.functions)} functions with 3 methods")
    
    async def _embed_batch(self, texts):
        embeddings = []
        batch_size = 50
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            await asyncio.sleep(21)  # Rate limit
            response = await voyage_client.embed(
                texts=batch,
                model="voyage-code-3",
                input_type="document"
            )
            embeddings.extend(response.embeddings)
        return embeddings
    
    async def search(self, query, top_k=10, weights=None):
        """
        Search using all three methods and fuse with RRF.
        
        weights: dict with keys 'bm25', 'code_semantic', 'summary_semantic'
        """
        if weights is None:
            weights = {'bm25': 1.0, 'code_semantic': 1.0, 'summary_semantic': 1.0}
        
        # Get query embedding
        await asyncio.sleep(21)
        response = await voyage_client.embed(
            texts=[query],
            model="voyage-code-3",
            input_type="query"
        )
        query_emb = response.embeddings[0]
        
        # 1. BM25 results
        bm25_results = self.bm25.search(query, top_k=50)
        
        # 2. Code semantic results
        code_scores = [(f, cosine_similarity(query_emb, emb)) 
                       for f, emb in zip(self.functions, self.code_embeddings)]
        code_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 3. Summary semantic results
        summary_scores = [(f, cosine_similarity(query_emb, emb))
                          for f, emb in zip(self.functions, self.summary_embeddings)]
        summary_scores.sort(key=lambda x: x[1], reverse=True)
        
        # RRF Fusion
        k = 60  # Standard RRF constant
        rrf_scores = defaultdict(float)
        
        # Add BM25 contribution
        for rank, (func, _) in enumerate(bm25_results):
            rrf_scores[func['name']] += weights['bm25'] / (k + rank)
        
        # Add code semantic contribution
        for rank, (func, _) in enumerate(code_scores[:50]):
            rrf_scores[func['name']] += weights['code_semantic'] / (k + rank)
        
        # Add summary semantic contribution
        for rank, (func, _) in enumerate(summary_scores[:50]):
            rrf_scores[func['name']] += weights['summary_semantic'] / (k + rank)
        
        # Build final results
        func_lookup = {f['name']: f for f in self.functions}
        final_results = [(func_lookup[name], score) for name, score in rrf_scores.items()]
        final_results.sort(key=lambda x: x[1], reverse=True)
        
        return final_results[:top_k]
    
    async def batch_search(self, queries, top_k=10, weights=None):
        """Batch search for efficiency."""
        if weights is None:
            weights = {'bm25': 1.0, 'code_semantic': 1.0, 'summary_semantic': 1.0}
        
        # Get all query embeddings at once
        await asyncio.sleep(21)
        response = await voyage_client.embed(
            texts=queries,
            model="voyage-code-3",
            input_type="query"
        )
        query_embs = response.embeddings
        
        k = 60
        all_results = []
        
        for query, query_emb in zip(queries, query_embs):
            # 1. BM25
            bm25_results = self.bm25.search(query, top_k=50)
            
            # 2. Code semantic
            code_scores = [(f, cosine_similarity(query_emb, emb))
                           for f, emb in zip(self.functions, self.code_embeddings)]
            code_scores.sort(key=lambda x: x[1], reverse=True)
            
            # 3. Summary semantic
            summary_scores = [(f, cosine_similarity(query_emb, emb))
                              for f, emb in zip(self.functions, self.summary_embeddings)]
            summary_scores.sort(key=lambda x: x[1], reverse=True)
            
            # RRF
            rrf_scores = defaultdict(float)
            
            for rank, (func, _) in enumerate(bm25_results):
                rrf_scores[func['name']] += weights['bm25'] / (k + rank)
            
            for rank, (func, _) in enumerate(code_scores[:50]):
                rrf_scores[func['name']] += weights['code_semantic'] / (k + rank)
            
            for rank, (func, _) in enumerate(summary_scores[:50]):
                rrf_scores[func['name']] += weights['summary_semantic'] / (k + rank)
            
            func_lookup = {f['name']: f for f in self.functions}
            final = [(func_lookup[name], score) for name, score in rrf_scores.items()]
            final.sort(key=lambda x: x[1], reverse=True)
            all_results.append(final[:top_k])
        
        return all_results


# =============================================================================
# EVALUATION
# =============================================================================

async def run_checkpoint_3():
    """Evaluate combined approach."""
    print("=" * 70)
    print("EXPERIMENT 03 - CHECKPOINT 3: Combined Approach")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Target: >80% Hit@1 by combining Hybrid + Summary")
    
    # Load summaries
    summaries_file = Path(__file__).parent.parent / "results" / "exp03_summaries.json"
    with open(summaries_file) as f:
        data = json.load(f)
    functions = data['functions']
    print(f"\n📦 Loaded {len(functions)} functions with summaries")
    
    # Build combined engine
    print("\n" + "─" * 60)
    print("Building Combined Index (BM25 + Code Semantic + Summary Semantic)")
    print("─" * 60)
    
    engine = CombinedSearchEngine()
    await engine.index(functions)
    
    # Test different weight configurations
    weight_configs = [
        {'name': 'equal', 'bm25': 1.0, 'code_semantic': 1.0, 'summary_semantic': 1.0},
        {'name': 'bm25_heavy', 'bm25': 2.0, 'code_semantic': 1.0, 'summary_semantic': 1.0},
        {'name': 'summary_heavy', 'bm25': 1.0, 'code_semantic': 1.0, 'summary_semantic': 2.0},
        {'name': 'no_bm25', 'bm25': 0.0, 'code_semantic': 1.0, 'summary_semantic': 1.0},
        {'name': 'code_heavy', 'bm25': 1.0, 'code_semantic': 2.0, 'summary_semantic': 1.0},
    ]
    
    results = {}
    all_queries = [q[0] for q in GROUND_TRUTH]
    
    for config in weight_configs:
        weights = {k: v for k, v in config.items() if k != 'name'}
        name = config['name']
        
        print(f"\n{'─' * 60}")
        print(f"Testing: {name.upper()}")
        print(f"Weights: BM25={weights['bm25']}, Code={weights['code_semantic']}, Summary={weights['summary_semantic']}")
        print(f"{'─' * 60}")
        
        search_results = await engine.batch_search(all_queries, top_k=10, weights=weights)
        
        config_results = []
        for i, (query, expected, category) in enumerate(GROUND_TRUTH):
            res = search_results[i]
            
            hit_1 = check_hit(res, expected, 1)
            hit_3 = check_hit(res, expected, 3)
            hit_5 = check_hit(res, expected, 5)
            top_result = res[0][0]['name'] if res else 'N/A'
            
            config_results.append({
                'query': query,
                'expected': expected,
                'hit@1': hit_1,
                'hit@3': hit_3,
                'hit@5': hit_5,
                'top_result': top_result,
            })
            
            status = "✅" if hit_1 else ("⚠️" if hit_3 else "❌")
            print(f"   {status} \"{query[:35]}...\" → {top_result}")
        
        total = len(config_results)
        metrics = {
            'hit@1': sum(r['hit@1'] for r in config_results) / total,
            'hit@3': sum(r['hit@3'] for r in config_results) / total,
            'hit@5': sum(r['hit@5'] for r in config_results) / total,
        }
        
        results[name] = {'metrics': metrics, 'details': config_results, 'weights': weights}
        print(f"\n   📊 {name}: Hit@1={metrics['hit@1']:.1%}, Hit@3={metrics['hit@3']:.1%}")
    
    # Comparison
    print("\n" + "=" * 70)
    print("FINAL COMPARISON")
    print("=" * 70)
    
    prev_best = 0.714  # Hybrid from exp02
    
    print(f"\n{'Config':<20} {'Hit@1':<10} {'Hit@3':<10} {'Hit@5':<10} {'vs Hybrid':<12}")
    print("─" * 62)
    print(f"{'hybrid (prev)':<20} {prev_best:<10.1%} {'95.2%':<10} {'95.2%':<10} {'baseline':<12}")
    
    for name, data in sorted(results.items(), key=lambda x: x[1]['metrics']['hit@1'], reverse=True):
        m = data['metrics']
        diff = m['hit@1'] - prev_best
        print(f"{name:<20} {m['hit@1']:<10.1%} {m['hit@3']:<10.1%} {m['hit@5']:<10.1%} {diff:+.1%}")
    
    # Winner
    best_name = max(results.keys(), key=lambda x: results[x]['metrics']['hit@1'])
    best = results[best_name]
    
    print("\n" + "=" * 70)
    print(f"🏆 BEST CONFIG: {best_name}")
    print(f"   Hit@1: {best['metrics']['hit@1']:.1%}")
    print(f"   Hit@3: {best['metrics']['hit@3']:.1%}")
    print(f"   Improvement: {best['metrics']['hit@1'] - prev_best:+.1%}")
    print("=" * 70)
    
    if best['metrics']['hit@1'] >= 0.80:
        print("✅ TARGET ACHIEVED! >80% Hit@1")
    elif best['metrics']['hit@1'] > prev_best:
        print("⚠️  IMPROVED over hybrid, but below 80%")
    else:
        print("❌ No improvement")
    
    # Save
    output = {
        'timestamp': datetime.now().isoformat(),
        'experiment': '03_checkpoint3_combined',
        'results': {k: {'metrics': v['metrics'], 'weights': v['weights']} for k, v in results.items()},
        'best': best_name,
        'best_hit1': best['metrics']['hit@1'],
    }
    
    results_dir = Path(__file__).parent.parent / "results"
    filename = results_dir / f"exp03_cp3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(filename, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Saved: {filename}")
    print("\n✅ CHECKPOINT 3 COMPLETE!")


if __name__ == "__main__":
    asyncio.run(run_checkpoint_3())
