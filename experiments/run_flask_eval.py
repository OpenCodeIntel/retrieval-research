"""
Evaluate Code Search on Flask
=============================
Python web framework - 237 functions
FIRST Python codebase with full summaries!
"""

import json
import numpy as np
from collections import defaultdict
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from flask_test_suite import FLASK_GROUND_TRUTH

# =============================================================================
# Search Engine (same as other evals)
# =============================================================================

class CodeTokenizer:
    STOPWORDS = {'the','a','an','is','are','to','of','in','for','on','with','at','by','from','as','and','but','if','or','this','that','it','function','const','let','var','return','def','self','class'}
    
    @classmethod
    def tokenize(cls, text):
        tokens = []
        words = re.findall(r'[a-zA-Z][a-zA-Z0-9]*', text)
        for word in words:
            word_lower = word.lower()
            if word_lower in cls.STOPWORDS or len(word_lower) < 2:
                continue
            tokens.append(word_lower)
            # Split camelCase and snake_case
            if re.search(r'[a-z][A-Z]', word):
                parts = re.sub('([A-Z])', r' \1', word).lower().split()
                tokens.extend([p for p in parts if len(p) >= 2 and p not in cls.STOPWORDS])
            if '_' in word:
                parts = word.lower().split('_')
                tokens.extend([p for p in parts if len(p) >= 2 and p not in cls.STOPWORDS])
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
            text = f"{doc['name']} {doc.get('code', '')} {doc.get('summary', '')}"
            tokens = CodeTokenizer.tokenize(text)
            self.doc_lengths.append(len(tokens))
            total += len(tokens)
            tf = defaultdict(int)
            for t in tokens: tf[t] += 1
            for t, f in tf.items():
                self.inverted_index[t][doc_id] = f
                self.doc_freqs[t] += 1
        self.avg_doc_length = total / self.num_docs if self.num_docs else 0
    
    def get_scores(self, query):
        tokens = CodeTokenizer.tokenize(query)
        scores = np.zeros(self.num_docs)
        for doc_id in range(self.num_docs):
            dl = self.doc_lengths[doc_id]
            for t in tokens:
                if t not in self.inverted_index or doc_id not in self.inverted_index[t]: continue
                tf = self.inverted_index[t][doc_id]
                df = self.doc_freqs.get(t, 0)
                idf = math.log((self.num_docs - df + 0.5) / (df + 0.5) + 1) if df else 0
                scores[doc_id] += idf * (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * dl / self.avg_doc_length))
        return scores


def normalize(scores):
    mn, mx = scores.min(), scores.max()
    return (scores - mn) / (mx - mn) if mx > mn else np.ones_like(scores)


class FlaskSearchEngine:
    def __init__(self, functions):
        self.functions = functions
        self.bm25 = BM25Index()
        self.bm25.index(functions)
        self.name_tokens = {i: set(CodeTokenizer.tokenize(f['name'])) for i, f in enumerate(functions)}
    
    def search(self, query, top_k=10):
        bm25_scores = self.bm25.get_scores(query)
        query_tokens = set(CodeTokenizer.tokenize(query))
        name_boost = np.zeros(len(self.functions))
        
        for i, func in enumerate(self.functions):
            name_lower = func['name'].lower()
            query_lower = query.lower()
            
            if name_lower in query_lower or query_lower in name_lower:
                name_boost[i] = 2.0
            
            overlap = len(query_tokens & self.name_tokens[i])
            if overlap > 0:
                name_boost[i] += overlap * 0.5
            
            if 'summary' in func:
                summary_lower = func['summary'].lower()
                for token in query_tokens:
                    if token in summary_lower:
                        name_boost[i] += 0.3
        
        final_scores = normalize(bm25_scores) * 0.4 + normalize(name_boost) * 0.6
        ranked_idx = np.argsort(final_scores)[::-1][:top_k]
        return [(self.functions[i], final_scores[i]) for i in ranked_idx]


def check_hit(results, expected, k):
    top_k_names = [r[0]['name'].lower() for r in results[:k]]
    return any(
        exp.lower() in name or name in exp.lower()
        for exp in expected
        for name in top_k_names
    )


def evaluate():
    with open('results/flask_summaries.json') as f:
        data = json.load(f)
    
    functions = data['functions']
    print(f"✅ Loaded {len(functions)} Flask functions")
    
    engine = FlaskSearchEngine(functions)
    
    results_by_category = defaultdict(list)
    all_results = []
    
    for query, expected, category in FLASK_GROUND_TRUTH:
        results = engine.search(query, top_k=10)
        
        hit1 = check_hit(results, expected, 1)
        hit3 = check_hit(results, expected, 3)
        hit5 = check_hit(results, expected, 5)
        
        result = {
            'query': query,
            'expected': expected,
            'category': category,
            'hit@1': hit1,
            'hit@3': hit3,
            'hit@5': hit5,
            'top_result': results[0][0]['name'],
            'top_3': [r[0]['name'] for r in results[:3]],
        }
        
        all_results.append(result)
        results_by_category[category].append(result)
    
    return all_results, results_by_category


def print_results(all_results, by_category):
    print("\n" + "=" * 70)
    print("📊 FLASK CODE SEARCH EVALUATION (PYTHON)")
    print("=" * 70)
    
    total = len(all_results)
    hit1 = sum(1 for r in all_results if r['hit@1'])
    hit3 = sum(1 for r in all_results if r['hit@3'])
    hit5 = sum(1 for r in all_results if r['hit@5'])
    
    print(f"\n🎯 OVERALL METRICS ({total} queries)")
    print(f"   Hit@1: {hit1}/{total} = {hit1/total*100:.1f}%")
    print(f"   Hit@3: {hit3}/{total} = {hit3/total*100:.1f}%")
    print(f"   Hit@5: {hit5}/{total} = {hit5/total*100:.1f}%")
    
    print(f"\n📁 BY CATEGORY:")
    for category in sorted(by_category.keys()):
        cat_results = by_category[category]
        cat_total = len(cat_results)
        cat_hit1 = sum(1 for r in cat_results if r['hit@1'])
        
        pct = cat_hit1/cat_total*100
        status = "✅" if pct >= 70 else ("⚠️" if pct >= 50 else "❌")
        print(f"   {status} {category}: {cat_hit1}/{cat_total} = {pct:.0f}%")
    
    failures = [r for r in all_results if not r['hit@1']]
    return failures


if __name__ == "__main__":
    import os
    os.chdir('.')
    
    all_results, by_category = evaluate()
    failures = print_results(all_results, by_category)
    
    print(f"\n❌ Failures: {len(failures)}/{len(all_results)}")
    print("\nSample failures:")
    for f in failures[:5]:
        print(f"   - \"{f['query'][:35]}...\" → {f['top_result']} (expected: {f['expected'][0]})")
    
    output = {
        'codebase': 'flask',
        'language': 'python',
        'total_queries': len(FLASK_GROUND_TRUTH),
        'total_functions': 237,
        'hit@1': sum(1 for r in all_results if r['hit@1']) / len(all_results),
        'hit@3': sum(1 for r in all_results if r['hit@3']) / len(all_results),
        'hit@5': sum(1 for r in all_results if r['hit@5']) / len(all_results),
        'by_category': {
            cat: {
                'hit@1': sum(1 for r in results if r['hit@1']) / len(results),
                'count': len(results)
            }
            for cat, results in by_category.items()
        },
        'all_results': all_results,
    }
    
    with open('results/flask_evaluation.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Results saved to results/flask_evaluation.json")
