"""
Comprehensive Evaluation: Test 55 queries on Zustand codebase
=============================================================
"""

import json
import numpy as np
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from comprehensive_test_suite import COMPREHENSIVE_GROUND_TRUTH
from collections import defaultdict
import math
import re

# =============================================================================
# BM25 Implementation
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
# Fusion Search Engine
# =============================================================================

def normalize(scores):
    mn, mx = scores.min(), scores.max()
    if mx > mn:
        return (scores - mn) / (mx - mn)
    return np.ones_like(scores)


class FusionSearchEngine:
    def __init__(self, functions):
        self.functions = functions
        self.bm25 = BM25Index()
        self.bm25.index(functions)
        
        self.name_tokens = {}
        for i, func in enumerate(functions):
            self.name_tokens[i] = set(CodeTokenizer.tokenize(func['name']))
    
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


# =============================================================================
# Evaluation
# =============================================================================

def check_hit(results, expected, k):
    top_k_names = [r[0]['name'].lower() for r in results[:k]]
    return any(
        exp.lower() in name or name in exp.lower()
        for exp in expected
        for name in top_k_names
    )


def evaluate_comprehensive():
    # Load functions
    with open('results/exp03_summaries.json') as f:
        data = json.load(f)
    
    functions = data['functions']
    print(f"✅ Loaded {len(functions)} functions")
    
    # Create search engine
    engine = FusionSearchEngine(functions)
    
    # Run evaluation
    results_by_category = defaultdict(list)
    all_results = []
    
    for query, expected, category in COMPREHENSIVE_GROUND_TRUTH:
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


def print_results(all_results, results_by_category):
    print("\n" + "=" * 70)
    print("📊 COMPREHENSIVE EVALUATION RESULTS")
    print("=" * 70)
    
    # Overall metrics
    total = len(all_results)
    hit1 = sum(1 for r in all_results if r['hit@1'])
    hit3 = sum(1 for r in all_results if r['hit@3'])
    hit5 = sum(1 for r in all_results if r['hit@5'])
    
    print(f"\n🎯 OVERALL METRICS ({total} queries)")
    print(f"   Hit@1: {hit1}/{total} = {hit1/total*100:.1f}%")
    print(f"   Hit@3: {hit3}/{total} = {hit3/total*100:.1f}%")
    print(f"   Hit@5: {hit5}/{total} = {hit5/total*100:.1f}%")
    
    # Per-category breakdown
    print(f"\n📁 BY CATEGORY:")
    for category in sorted(results_by_category.keys()):
        cat_results = results_by_category[category]
        cat_total = len(cat_results)
        cat_hit1 = sum(1 for r in cat_results if r['hit@1'])
        cat_hit3 = sum(1 for r in cat_results if r['hit@3'])
        
        status = "✅" if cat_hit1/cat_total >= 0.8 else ("⚠️" if cat_hit1/cat_total >= 0.5 else "❌")
        print(f"\n   {status} {category}: {cat_hit1}/{cat_total} Hit@1 ({cat_hit1/cat_total*100:.0f}%), {cat_hit3}/{cat_total} Hit@3")
        
        # Show failures
        failures = [r for r in cat_results if not r['hit@1']]
        for f in failures[:3]:  # Show first 3 failures
            print(f"      ❌ \"{f['query'][:40]}...\" → {f['top_result']} (expected: {f['expected'][0]})")
    
    # Summary
    print(f"\n" + "=" * 70)
    print(f"📈 SUMMARY")
    print(f"=" * 70)
    
    if hit1/total >= 0.9:
        print(f"\n   🏆 EXCELLENT! {hit1/total*100:.1f}% Hit@1 accuracy")
    elif hit1/total >= 0.7:
        print(f"\n   ✅ GOOD! {hit1/total*100:.1f}% Hit@1 accuracy")
    else:
        print(f"\n   ⚠️ NEEDS WORK: {hit1/total*100:.1f}% Hit@1 accuracy")
    
    # Return failures for analysis
    failures = [r for r in all_results if not r['hit@1']]
    return failures


if __name__ == "__main__":
    import os
    os.chdir('.')
    
    all_results, by_category = evaluate_comprehensive()
    failures = print_results(all_results, by_category)
    
    # Save results
    output = {
        'total_queries': len(COMPREHENSIVE_GROUND_TRUTH),
        'hit@1': sum(1 for r in all_results if r['hit@1']) / len(all_results),
        'hit@3': sum(1 for r in all_results if r['hit@3']) / len(all_results),
        'hit@5': sum(1 for r in all_results if r['hit@5']) / len(all_results),
        'by_category': {
            cat: {
                'hit@1': sum(1 for r in results if r['hit@1']) / len(results),
                'hit@3': sum(1 for r in results if r['hit@3']) / len(results),
                'count': len(results)
            }
            for cat, results in by_category.items()
        },
        'failures': failures,
        'all_results': all_results,
    }
    
    with open('results/comprehensive_evaluation.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Results saved to results/comprehensive_evaluation.json")
