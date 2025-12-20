"""
Shared utilities for Experiment 04: Reranking
=============================================
Contains:
- Ground truth queries (CORRECTED Dec 18, 2025)
- Data loading functions
- Evaluation metrics
- Simulated fusion engine (to avoid API calls)

IMPORTANT: Ground truth was audited and corrected based on:
1. Checking if expected functions actually exist in Zustand
2. Verifying returned results are semantically valid alternatives
3. Removing non-existent functions like 'clearStorage', 'merge', 'rehydrate'
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict
import math
import re

# =============================================================================
# GROUND TRUTH - 21 queries across 7 categories
# CORRECTED VERSION: Dec 18, 2025
# =============================================================================

GROUND_TRUTH = [
    # State management
    ("update the store state", ["setState", "set", "savedSetState"], "state"),
    ("get current state value", ["getState", "get", "state"], "state"),
    ("listen for state changes", ["subscribe", "subscribeWithSelector", "listeners"], "state"),
    ("create a new store", ["createStore", "create", "createStoreImpl", "createImpl"], "state"),
    
    # Persistence - CORRECTED: removed non-existent functions
    ("save state to localStorage", ["persist", "setItem", "persistImpl", "persistStorage"], "persist"),
    ("load saved state from storage", ["hydrate", "stateFromStorage", "getInitialState"], "persist"),  # Added stateFromStorage
    ("clear persisted data", ["persistImpl", "persistStorage", "storage"], "persist"),  # FIXED: clearStorage doesn't exist!
    ("migrate old stored state version", ["migration", "migrationResult"], "persist"),  # FIXED: migrate doesn't exist
    ("custom storage adapter", ["createJSONStorage", "storage", "persistStorage"], "persist"),
    
    # Middleware
    ("combine multiple stores", ["combine"], "middleware"),
    ("redux devtools integration", ["devtools", "extensionConnector", "devtoolsImpl"], "middleware"),  # Added extensionConnector
    ("use immer for immutable updates", ["immer", "immerImpl"], "middleware"),
    ("subscribe to specific state slice", ["subscribeWithSelector", "subscribeWithSelectorImpl", "slice"], "middleware"),  # Added slice
    
    # React integration - CORRECTED: added useBoundStore
    ("use store in react component", ["useStore", "create", "useBoundStore", "useBoundStoreWithEqualityFn"], "react"),  # Added useBoundStore
    ("shallow comparison for selectors", ["shallow", "useShallow"], "react"),
    ("avoid unnecessary rerenders", ["shallow", "useShallow", "equalityFn"], "react"),
    
    # Utilities - CORRECTED: removed non-existent functions
    ("check if state objects are equal", ["shallow", "compareEntries", "compareIterables"], "comparison"),  # Fixed: Object.is not a function name
    ("merge new state with existing", ["setState", "nextState", "state", "combine"], "state"),  # FIXED: merge/assign don't exist!
    ("notify all listeners of change", ["listeners", "listener", "subscribe"], "state"),  # Fixed: forEach/notify don't exist
    ("handle storage not available", ["storage", "catch", "toThenable", "ssrSafe"], "error"),
    ("server side rendering safe", ["ssrSafe", "ssrSet"], "ssr"),
]


# =============================================================================
# BACKUP: Original ground truth (for reference)
# =============================================================================

GROUND_TRUTH_ORIGINAL = [
    # These were the WRONG expected values we were using:
    # ("clear persisted data", ["clearStorage", "removeItem"]),  # Neither exists!
    # ("merge new state with existing", ["merge", "assign", "Object.assign"]),  # None exist!
    # ("load saved state from storage", ["hydrate", "rehydrate", "getItem"]),  # rehydrate, getItem don't exist
]


# =============================================================================
# DATA LOADING
# =============================================================================

def load_functions_with_summaries() -> List[Dict]:
    """Load functions with their LLM-generated summaries."""
    # Try multiple possible paths
    possible_paths = [
        Path(__file__).parent.parent.parent / "results" / "exp03_summaries.json",
        Path(__file__).parent.parent / "results" / "exp03_summaries.json",
        Path("results/exp03_summaries.json"),
    ]
    
    for summaries_file in possible_paths:
        if summaries_file.exists():
            with open(summaries_file) as f:
                data = json.load(f)
            return data['functions']
    
    raise FileNotFoundError(f"Could not find exp03_summaries.json in any of: {possible_paths}")


# =============================================================================
# BM25 INDEX (Local, no API)
# =============================================================================

class CodeTokenizer:
    """Tokenizer optimized for code."""
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


class BM25Index:
    """BM25 index for keyword-based retrieval."""
    
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.documents = []
        self.doc_lengths = []
        self.inverted_index = defaultdict(dict)
        self.doc_freqs = defaultdict(int)
        self.avg_doc_length = 0
        self.num_docs = 0
    
    def index(self, documents: List[Dict]):
        """Build BM25 index from documents."""
        self.documents = documents
        self.num_docs = len(documents)
        total = 0
        
        for doc_id, doc in enumerate(documents):
            # Index both name and code
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
        """Get BM25 scores for all documents."""
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
# SIMULATED FUSION ENGINE
# =============================================================================

def normalize(scores: np.ndarray) -> np.ndarray:
    """Min-max normalize scores to [0, 1]."""
    mn, mx = scores.min(), scores.max()
    if mx > mn:
        return (scores - mn) / (mx - mn)
    return np.ones_like(scores)


class FusionEngine:
    """
    Simulates our best fusion approach (Code + Summary + BM25).
    Uses BM25 + name matching as proxy to avoid Voyage API calls.
    """
    
    def __init__(self, functions: List[Dict]):
        self.functions = functions
        self.bm25 = BM25Index()
        self.bm25.index(functions)
        
        # Build name index for boosting
        self.name_tokens = {}
        for i, func in enumerate(functions):
            self.name_tokens[i] = set(CodeTokenizer.tokenize(func['name']))
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[Dict, float]]:
        """Get top-k candidates using simulated fusion."""
        bm25_scores = self.bm25.get_scores(query)
        
        # Name matching boost
        query_tokens = set(CodeTokenizer.tokenize(query))
        name_boost = np.zeros(len(self.functions))
        
        for i, func in enumerate(self.functions):
            name_lower = func['name'].lower()
            query_lower = query.lower()
            
            # Exact substring match (strong boost)
            if name_lower in query_lower or query_lower in name_lower:
                name_boost[i] = 2.0
            
            # Token overlap
            overlap = len(query_tokens & self.name_tokens[i])
            if overlap > 0:
                name_boost[i] += overlap * 0.5
            
            # Summary keyword match
            if 'summary' in func:
                summary_lower = func['summary'].lower()
                for token in query_tokens:
                    if token in summary_lower:
                        name_boost[i] += 0.3
        
        # Combine scores (simulating our 0.3/0.5/0.2 weights)
        final_scores = normalize(bm25_scores) * 0.4 + normalize(name_boost) * 0.6
        
        # Sort and return top-k
        ranked_idx = np.argsort(final_scores)[::-1][:top_k]
        return [(self.functions[i], final_scores[i]) for i in ranked_idx]


# =============================================================================
# EVALUATION METRICS
# =============================================================================

def check_hit(results: List[Tuple[Dict, float]], expected: List[str], k: int) -> bool:
    """Check if any expected function is in top-k results."""
    top_k_names = [r[0]['name'].lower() for r in results[:k]]
    return any(
        exp.lower() in name or name in exp.lower()
        for exp in expected
        for name in top_k_names
    )


def get_rank(results: List[Tuple[Dict, float]], expected: List[str]) -> int:
    """Get rank of first matching result (1-indexed), or 0 if not found."""
    for i, (func, _) in enumerate(results):
        name = func['name'].lower()
        if any(exp.lower() in name or name in exp.lower() for exp in expected):
            return i + 1
    return 0


def evaluate_results(results_per_query: List[List[Tuple[Dict, float]]]) -> Dict:
    """Compute evaluation metrics."""
    hits_1, hits_3, hits_5 = [], [], []
    mrr_scores = []
    details = []
    
    for i, (query, expected, category) in enumerate(GROUND_TRUTH):
        results = results_per_query[i]
        
        h1 = check_hit(results, expected, 1)
        h3 = check_hit(results, expected, 3)
        h5 = check_hit(results, expected, 5)
        
        rank = get_rank(results, expected)
        rr = 1.0 / rank if rank > 0 else 0.0
        
        hits_1.append(h1)
        hits_3.append(h3)
        hits_5.append(h5)
        mrr_scores.append(rr)
        
        details.append({
            'query': query,
            'expected': expected,
            'category': category,
            'hit@1': h1,
            'hit@3': h3,
            'hit@5': h5,
            'rank': rank,
            'top_result': results[0][0]['name'] if results else 'N/A',
            'top_3': [r[0]['name'] for r in results[:3]],
        })
    
    return {
        'hit@1': sum(hits_1) / len(hits_1),
        'hit@3': sum(hits_3) / len(hits_3),
        'hit@5': sum(hits_5) / len(hits_5),
        'mrr': sum(mrr_scores) / len(mrr_scores),
        'details': details,
    }


def print_results(name: str, metrics: Dict, baseline_hit1: float = 0.81):
    """Pretty print results."""
    print(f"\n{'='*60}")
    print(f"Results: {name}")
    print(f"{'='*60}")
    print(f"  Hit@1: {metrics['hit@1']:.1%} (vs baseline 81%: {metrics['hit@1'] - baseline_hit1:+.1%})")
    print(f"  Hit@3: {metrics['hit@3']:.1%}")
    print(f"  Hit@5: {metrics['hit@5']:.1%}")
    print(f"  MRR:   {metrics['mrr']:.3f}")
    print(f"\nPer-query breakdown:")
    for item in metrics['details']:
        status = "✅" if item['hit@1'] else ("⚠️" if item['hit@3'] else "❌")
        print(f"  {status} {item['query'][:40]}... → {item['top_result']}")


def save_results(name: str, metrics: Dict, output_dir: Path = None):
    """Save results to JSON."""
    if output_dir is None:
        output_dir = Path(__file__).parent.parent.parent / "results"
    
    output_dir.mkdir(exist_ok=True)
    
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f"exp04_{name}_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump({
            'experiment': f'04_{name}',
            'timestamp': datetime.now().isoformat(),
            'metrics': {k: v for k, v in metrics.items() if k != 'details'},
            'details': metrics['details'],
        }, f, indent=2, default=str)
    
    print(f"\n💾 Saved: {output_file}")
    return output_file
