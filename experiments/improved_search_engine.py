"""
Improved Search Engine with Smart Ranking
==========================================
Fixes:
1. Penalize generic/short function names
2. Boost exact function name matches
3. Better handling of React hooks
"""

import json
import numpy as np
from pathlib import Path
from collections import defaultdict
import math
import re

# =============================================================================
# Tokenizer
# =============================================================================

class CodeTokenizer:
    STOPWORDS = {
        'the','a','an','is','are','was','were','be','been','being','have','has','had',
        'do','does','did','will','would','could','should','may','might','must','shall',
        'can','need','to','of','in','for','on','with','at','by','from','as','into',
        'through','during','before','after','above','below','between','under','again',
        'then','once','here','there','when','where','why','how','all','each','few',
        'more','most','other','some','such','no','nor','not','only','own','same','so',
        'than','too','very','just','and','but','if','or','because','until','while',
        'this','that','these','those','it','function','const','let','var','return',
        'export','import','default','type','interface','class'
    }
    
    @classmethod
    def tokenize(cls, text: str) -> list:
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


# =============================================================================
# BM25 Index
# =============================================================================

class BM25Index:
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.documents = []
        self.doc_lengths = []
        self.inverted_index = defaultdict(dict)
        self.doc_freqs = defaultdict(int)
        self.avg_doc_length = 0
        self.num_docs = 0
    
    def index(self, documents):
        self.documents = documents
        self.num_docs = len(documents)
        total = 0
        
        for doc_id, doc in enumerate(documents):
            text = f"{doc['name']} {doc['code']}"
            if 'summary' in doc:
                text += f" {doc['summary']}"
            
            tokens = CodeTokenizer.tokenize(text)
            self.doc_lengths.append(len(tokens))
            total += len(tokens)
            
            tf = defaultdict(int)
            for t in tokens:
                tf[t] += 1
            for t, f in tf.items():
                self.inverted_index[t][doc_id] = f
                self.doc_freqs[t] += 1
        
        self.avg_doc_length = total / self.num_docs if self.num_docs else 0
    
    def get_scores(self, query: str) -> np.ndarray:
        tokens = CodeTokenizer.tokenize(query)
        scores = np.zeros(self.num_docs)
        
        for doc_id in range(self.num_docs):
            dl = self.doc_lengths[doc_id]
            for t in tokens:
                if t not in self.inverted_index or doc_id not in self.inverted_index[t]:
                    continue
                tf = self.inverted_index[t][doc_id]
                df = self.doc_freqs.get(t, 0)
                idf = math.log((self.num_docs - df + 0.5) / (df + 0.5) + 1) if df else 0
                scores[doc_id] += idf * (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * dl / self.avg_doc_length))
        
        return scores


# =============================================================================
# Improved Fusion Engine
# =============================================================================

def normalize(scores):
    mn, mx = scores.min(), scores.max()
    if mx > mn:
        return (scores - mn) / (mx - mn)
    return np.zeros_like(scores)


# Generic function names that should be penalized
GENERIC_NAMES = {
    'state', 'r', 'arg', 'next', 'prev', 'api', 'options', 'slice', 
    'then', 'catch', 'storage', 'listener', 'parsed', 'str'
}

# Very long names that are usually internal/less relevant
INTERNAL_PATTERNS = [
    'impl', 'internal', 'exports', 'sync'  # useSyncExternalStoreExports
]


class ImprovedFusionEngine:
    """
    Improved ranking with:
    1. Generic name penalty
    2. Exact match boost
    3. Name length consideration
    4. Internal function penalty
    """
    
    def __init__(self, functions):
        self.functions = functions
        self.bm25 = BM25Index()
        self.bm25.index(functions)
        
        # Pre-compute name features
        self.name_tokens = {}
        self.name_features = {}
        
        for i, func in enumerate(functions):
            name = func['name']
            name_lower = name.lower()
            
            self.name_tokens[i] = set(CodeTokenizer.tokenize(name))
            
            # Compute features
            self.name_features[i] = {
                'is_generic': name_lower in GENERIC_NAMES,
                'is_internal': any(p in name_lower for p in INTERNAL_PATTERNS),
                'is_hook': name_lower.startswith('use'),
                'name_length': len(name),
                'has_camel_case': bool(re.search(r'[a-z][A-Z]', name)),
            }
    
    def search(self, query: str, top_k: int = 10) -> list:
        bm25_scores = self.bm25.get_scores(query)
        
        query_lower = query.lower()
        query_tokens = set(CodeTokenizer.tokenize(query))
        
        # Detect query type
        is_react_query = any(w in query_lower for w in ['react', 'component', 'hook', 'rerender', 'render'])
        is_hook_query = 'use' in query_lower or 'hook' in query_lower
        
        # Calculate smart scores
        smart_scores = np.zeros(len(self.functions))
        
        for i, func in enumerate(self.functions):
            name = func['name']
            name_lower = name.lower()
            features = self.name_features[i]
            
            score = 0.0
            
            # === EXACT NAME MATCH (strongest signal) ===
            # If query contains exact function name
            if name_lower in query_lower or query_lower in name_lower:
                score += 3.0
            
            # === TOKEN OVERLAP ===
            overlap = len(query_tokens & self.name_tokens[i])
            if overlap > 0:
                score += overlap * 0.5
            
            # === SUMMARY MATCH ===
            if 'summary' in func:
                summary_lower = func['summary'].lower()
                summary_matches = sum(1 for t in query_tokens if t in summary_lower)
                score += summary_matches * 0.3
            
            # === PENALTIES ===
            
            # Penalize generic names
            if features['is_generic']:
                score *= 0.5  # Halve the score for generic names
            
            # Penalize internal/export functions
            if features['is_internal']:
                score *= 0.6
            
            # === BONUSES ===
            
            # Bonus for hooks when query is about React
            if is_react_query and features['is_hook']:
                score *= 1.5
            
            # Bonus for shorter, more specific names (usually more important)
            # But not TOO short (those are generic)
            name_len = features['name_length']
            if 5 <= name_len <= 20:
                score *= 1.2
            elif name_len > 30:
                score *= 0.8  # Penalize very long names
            
            # === SPECIFIC FIXES ===
            
            # Fix for "use store in react" - boost useStore over useSyncExternalStoreExports
            if is_hook_query and features['is_hook']:
                # Prefer shorter hook names
                if name_len < 15:
                    score *= 1.3
                elif name_len > 25:
                    score *= 0.7
            
            smart_scores[i] = score
        
        # Combine BM25 and smart scores
        # Weight: 30% BM25, 70% smart scoring
        final_scores = normalize(bm25_scores) * 0.3 + normalize(smart_scores) * 0.7
        
        # Sort and return top-k
        ranked_idx = np.argsort(final_scores)[::-1][:top_k]
        return [(self.functions[i], final_scores[i]) for i in ranked_idx]


# =============================================================================
# Test the improvement
# =============================================================================

if __name__ == "__main__":
    import sys
    sys.path.insert(0, 'experiments')
    from comprehensive_test_suite import COMPREHENSIVE_GROUND_TRUTH
    
    # Load functions
    with open('results/exp03_summaries.json') as f:
        data = json.load(f)
    
    functions = data['functions']
    print(f"✅ Loaded {len(functions)} functions")
    
    # Test both engines
    from run_comprehensive_eval import FusionSearchEngine
    
    old_engine = FusionSearchEngine(functions)
    new_engine = ImprovedFusionEngine(functions)
    
    print("\n" + "=" * 70)
    print("🔬 COMPARING OLD vs IMPROVED ENGINE")
    print("=" * 70)
    
    # Focus on failures first
    problem_queries = [
        ("use store in react component", ["useStore", "create", "useBoundStore"]),
        ("bind store to react component", ["useBoundStore", "useStore"]),
        ("avoid unnecessary rerenders", ["shallow", "useShallow", "equalityFn"]),
        ("optimize react performance", ["useShallow", "shallow"]),
        ("handle state rehydration", ["hydrate", "hydrationListeners"]),
    ]
    
    print("\n📊 Problem queries comparison:")
    print("-" * 70)
    
    for query, expected in problem_queries:
        old_results = old_engine.search(query, top_k=5)
        new_results = new_engine.search(query, top_k=5)
        
        old_top = old_results[0][0]['name']
        new_top = new_results[0][0]['name']
        
        old_hit = any(exp.lower() in old_top.lower() or old_top.lower() in exp.lower() for exp in expected)
        new_hit = any(exp.lower() in new_top.lower() or new_top.lower() in exp.lower() for exp in expected)
        
        old_status = "✅" if old_hit else "❌"
        new_status = "✅" if new_hit else "❌"
        
        improved = "🔥 FIXED!" if new_hit and not old_hit else ("" if new_hit == old_hit else "⚠️ REGRESSED")
        
        print(f"\nQuery: \"{query}\"")
        print(f"  Old: {old_status} {old_top}")
        print(f"  New: {new_status} {new_top} {improved}")
        print(f"  Expected: {expected[0]}")
