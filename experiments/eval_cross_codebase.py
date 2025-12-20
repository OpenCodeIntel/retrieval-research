"""
Evaluate search across multiple codebases
"""

import json
import numpy as np
from collections import defaultdict
import math
import re

# =============================================================================
# Search Engine (same optimal config)
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
        words = re.findall(r'[a-zA-Z][a-zA-Z0-9_]*', text)
        for word in words:
            word_lower = word.lower()
            if word_lower in cls.STOPWORDS or len(word_lower) < 2:
                continue
            tokens.append(word_lower)
        return tokens


class BM25Index:
    def __init__(self, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.documents, self.doc_lengths = [], []
        self.inverted_index = defaultdict(dict)
        self.doc_freqs = defaultdict(int)
        self.avg_doc_length, self.num_docs = 0, 0
    
    def index(self, documents):
        self.documents = documents
        self.num_docs = len(documents)
        total = 0
        for doc_id, doc in enumerate(documents):
            text = f"{doc['name']} {doc.get('code', '')}"
            tokens = CodeTokenizer.tokenize(text)
            self.doc_lengths.append(len(tokens))
            total += len(tokens)
            tf = defaultdict(int)
            for t in tokens: tf[t] += 1
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


def normalize(scores):
    mn, mx = scores.min(), scores.max()
    return (scores - mn) / (mx - mn) if mx > mn else np.zeros_like(scores)


# Optimal config
GENERIC_PENALTY = 0.6
BM25_WEIGHT = 0.5
NAME_BOOST = 5.0

GENERIC = {'state', 'r', 'arg', 'next', 'prev', 'api', 'slice', 'then', 'catch', 'str', 'parsed', 'options', 'listener', 'app', 'req', 'res', 'err', 'fn', 'cb'}


class SearchEngine:
    def __init__(self, functions):
        self.functions = functions
        self.bm25 = BM25Index()
        self.bm25.index(functions)
        self.name_tokens = {i: set(CodeTokenizer.tokenize(f['name'])) for i, f in enumerate(functions)}
    
    def search(self, query, top_k=10):
        bm25_scores = self.bm25.get_scores(query)
        query_lower = query.lower()
        query_tokens = set(CodeTokenizer.tokenize(query))
        
        smart_scores = np.zeros(len(self.functions))
        
        for i, func in enumerate(self.functions):
            name = func['name']
            name_lower = name.lower()
            
            score = 0.0
            
            # Exact name match
            if name_lower in query_lower:
                score += NAME_BOOST
            
            # Token overlap
            overlap = len(query_tokens & self.name_tokens[i])
            score += overlap * 0.5
            
            # Generic penalty
            if name_lower in GENERIC:
                score *= GENERIC_PENALTY
            
            smart_scores[i] = score
        
        final_scores = normalize(bm25_scores) * BM25_WEIGHT + normalize(smart_scores) * (1 - BM25_WEIGHT)
        ranked_idx = np.argsort(final_scores)[::-1][:top_k]
        return [(self.functions[i], final_scores[i]) for i in ranked_idx]


# =============================================================================
# Test queries
# =============================================================================

EXPRESS_QUERIES = [
    ("create a new route", ["Router", "route", "get", "post"]),
    ("handle GET request", ["get", "route"]),
    ("handle POST request", ["post", "route"]),
    ("add middleware to app", ["use", "middleware"]),
    ("parse JSON body", ["json", "bodyParser"]),
    ("serve static files", ["static", "serveStatic"]),
    ("set response header", ["set", "header", "setHeader"]),
    ("send JSON response", ["json", "send"]),
    ("redirect to another URL", ["redirect", "location"]),
    ("render a view template", ["render", "view"]),
    ("handle errors", ["error", "errorHandler"]),
    ("get request parameters", ["param", "params"]),
    ("get query string", ["query"]),
    ("create express application", ["express", "createApplication"]),
    ("listen on port", ["listen"]),
]

LODASH_QUERIES = [
    ("get first element of array", ["first", "head"]),
    ("get last element of array", ["last"]),
    ("flatten nested array", ["flatten", "flattenDeep"]),
    ("remove duplicates from array", ["uniq", "unique", "uniqBy"]),
    ("sort array of objects", ["sortBy", "orderBy"]),
    ("filter array elements", ["filter"]),
    ("map over array", ["map"]),
    ("reduce array to value", ["reduce"]),
    ("find element in array", ["find", "findIndex"]),
    ("chunk array into groups", ["chunk"]),
    ("merge objects together", ["merge", "assign"]),
    ("pick specific properties", ["pick"]),
    ("omit specific properties", ["omit"]),
    ("get nested property value", ["get"]),
    ("clone object deeply", ["cloneDeep", "clone"]),
    ("check if object is empty", ["isEmpty"]),
    ("get all object keys", ["keys"]),
    ("convert to camel case", ["camelCase"]),
    ("debounce function calls", ["debounce"]),
    ("throttle function calls", ["throttle"]),
]


def check_hit(results, expected, k):
    top_k_names = [r[0]['name'].lower() for r in results[:k]]
    return any(exp.lower() in name or name in exp.lower() for exp in expected for name in top_k_names)


def evaluate_codebase(name, functions, queries):
    """Evaluate search on a codebase"""
    print(f"\n{'='*70}")
    print(f"📦 {name.upper()} - {len(functions)} functions, {len(queries)} queries")
    print(f"{'='*70}")
    
    engine = SearchEngine(functions)
    
    hits1, hits3, hits5 = 0, 0, 0
    failures = []
    
    for query, expected in queries:
        results = engine.search(query, top_k=10)
        
        h1 = check_hit(results, expected, 1)
        h3 = check_hit(results, expected, 3)
        h5 = check_hit(results, expected, 5)
        
        if h1: hits1 += 1
        if h3: hits3 += 1
        if h5: hits5 += 1
        
        if not h1:
            failures.append({
                'query': query,
                'expected': expected,
                'got': results[0][0]['name'],
                'top_3': [r[0]['name'] for r in results[:3]],
                'hit@3': h3
            })
    
    total = len(queries)
    print(f"\n🎯 RESULTS:")
    print(f"   Hit@1: {hits1}/{total} = {hits1/total*100:.1f}%")
    print(f"   Hit@3: {hits3}/{total} = {hits3/total*100:.1f}%")
    print(f"   Hit@5: {hits5}/{total} = {hits5/total*100:.1f}%")
    
    if failures:
        print(f"\n❌ FAILURES ({len(failures)}):")
        for f in failures[:5]:
            marker = "✓ top3" if f['hit@3'] else "✗"
            print(f"   • \"{f['query'][:35]}...\" → {f['got']} ({marker})")
            print(f"     Expected: {f['expected'][0]}, Top3: {f['top_3']}")
    
    return {
        'hit@1': hits1/total,
        'hit@3': hits3/total,
        'hit@5': hits5/total,
        'failures': failures
    }


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import os
    os.chdir('.')
    
    results = {}
    
    # Test Express
    try:
        with open('results/express_functions.json') as f:
            express_data = json.load(f)
        results['express'] = evaluate_codebase('Express', express_data['functions'], EXPRESS_QUERIES)
    except Exception as e:
        print(f"Express error: {e}")
    
    # Test Lodash
    try:
        with open('results/lodash_functions.json') as f:
            lodash_data = json.load(f)
        results['lodash'] = evaluate_codebase('Lodash', lodash_data['functions'], LODASH_QUERIES)
    except Exception as e:
        print(f"Lodash error: {e}")
    
    # Test Zustand (our original)
    try:
        with open('results/exp03_summaries.json') as f:
            zustand_data = json.load(f)
        
        import sys
        sys.path.insert(0, 'experiments')
        from comprehensive_test_suite import COMPREHENSIVE_GROUND_TRUTH
        
        zustand_queries = [(q, e) for q, e, _ in COMPREHENSIVE_GROUND_TRUTH]
        results['zustand'] = evaluate_codebase('Zustand', zustand_data['functions'], zustand_queries)
    except Exception as e:
        print(f"Zustand error: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 CROSS-CODEBASE SUMMARY")
    print("=" * 70)
    
    print(f"\n{'Codebase':<12} {'Hit@1':<10} {'Hit@3':<10} {'Hit@5'}")
    print("-" * 45)
    for name, res in results.items():
        print(f"{name:<12} {res['hit@1']*100:.1f}%      {res['hit@3']*100:.1f}%      {res['hit@5']*100:.1f}%")
    
    avg_hit1 = sum(r['hit@1'] for r in results.values()) / len(results)
    print("-" * 45)
    print(f"{'AVERAGE':<12} {avg_hit1*100:.1f}%")
    
    # Save
    with open('results/cross_codebase_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Saved to results/cross_codebase_results.json")
