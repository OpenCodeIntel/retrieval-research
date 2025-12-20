"""
Python-Optimized Search Engine v3
=================================
Key insight: Python has many duplicate function names across files.
Solution: Prefer unique/rare names over common ones.
"""

import json
import numpy as np
from collections import defaultdict, Counter
import math
import re


class PythonTokenizer:
    STOPWORDS = {
        'the', 'a', 'an', 'is', 'are', 'to', 'of', 'in', 'for', 'on', 'with',
        'at', 'by', 'from', 'as', 'and', 'but', 'if', 'or', 'this', 'that',
        'it', 'def', 'self', 'class', 'return', 'none', 'true', 'false'
    }
    
    @classmethod
    def tokenize(cls, text):
        tokens = []
        words = re.findall(r'[a-zA-Z][a-zA-Z0-9]*', text)
        
        for word in words:
            word_lower = word.lower()
            if word_lower in cls.STOPWORDS or len(word_lower) < 2:
                continue
            
            tokens.append(word_lower)
            
            if '_' in word:
                parts = word.lower().split('_')
                for p in parts:
                    if len(p) >= 2 and p not in cls.STOPWORDS:
                        tokens.append(p)
        
        return tokens


class BM25Index:
    def __init__(self, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.doc_lengths = []
        self.inverted_index = defaultdict(dict)
        self.doc_freqs = defaultdict(int)
        self.avg_doc_length, self.num_docs = 0, 0
    
    def index(self, documents):
        self.num_docs = len(documents)
        total = 0
        
        for doc_id, doc in enumerate(documents):
            text = f"{doc['name']} {doc.get('code', '')} {doc.get('summary', '')}"
            tokens = PythonTokenizer.tokenize(text)
            self.doc_lengths.append(len(tokens))
            total += len(tokens)
            
            tf = defaultdict(int)
            for t in tokens:
                tf[t] += 1
            for t, f in tf.items():
                self.inverted_index[t][doc_id] = f
                self.doc_freqs[t] += 1
        
        self.avg_doc_length = total / self.num_docs if self.num_docs else 0
    
    def get_scores(self, query):
        tokens = PythonTokenizer.tokenize(query)
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
    return (scores - mn) / (mx - mn) if mx > mn else np.ones_like(scores)


class PythonSearchEngineV3:
    """
    Python Search v3 - Uniqueness-based ranking
    
    Key innovations:
    1. Count function name frequency - penalize common names
    2. Boost rare/unique function names
    3. Give higher weight to summary matching
    4. Consider file context (specific files > generic)
    """
    
    def __init__(self, functions):
        self.functions = functions
        self.bm25 = BM25Index()
        self.bm25.index(functions)
        
        # Count name frequencies
        name_counts = Counter(f['name'].lower() for f in functions)
        
        # Calculate uniqueness score (rarer = higher)
        max_count = max(name_counts.values()) if name_counts else 1
        self.name_uniqueness = {}
        
        for i, func in enumerate(functions):
            name = func['name'].lower()
            count = name_counts[name]
            
            # Uniqueness = 1.0 for unique, lower for common
            # Using log to smooth
            self.name_uniqueness[i] = 1.0 / (1.0 + math.log(count))
        
        # Pre-compute name tokens
        self.name_tokens = {
            i: set(PythonTokenizer.tokenize(f['name']))
            for i, f in enumerate(functions)
        }
        
        # File specificity (some files are more "core")
        file_counts = Counter(f.get('file', '').split('/')[-1] for f in functions)
        self.file_specificity = {}
        for i, func in enumerate(functions):
            filename = func.get('file', '').split('/')[-1]
            # Files with fewer functions are more specific
            self.file_specificity[i] = 1.0 / (1.0 + math.log(file_counts.get(filename, 1)))
    
    def search(self, query, top_k=10):
        bm25_scores = self.bm25.get_scores(query)
        query_tokens = set(PythonTokenizer.tokenize(query))
        
        name_scores = np.zeros(len(self.functions))
        summary_scores = np.zeros(len(self.functions))
        
        for i, func in enumerate(self.functions):
            name = func['name']
            name_lower = name.lower()
            uniqueness = self.name_uniqueness[i]
            
            # Skip dunder methods unless explicitly queried
            if name.startswith('__') and '__' not in query:
                continue
            
            # 1. Exact name match (with uniqueness boost)
            for token in query_tokens:
                if token in name_lower or name_lower in token:
                    name_scores[i] += 2.0 * uniqueness
            
            # 2. Token overlap (with uniqueness)
            overlap = len(query_tokens & self.name_tokens[i])
            name_scores[i] += overlap * 0.5 * uniqueness
            
            # 3. Summary matching (KEY for Python!)
            if 'summary' in func and func['summary']:
                summary_lower = func['summary'].lower()
                
                # Count how many query tokens appear in summary
                matches = sum(1 for t in query_tokens if t in summary_lower and len(t) > 2)
                
                # Bonus for consecutive/phrase matches
                query_str = ' '.join(sorted(query_tokens))
                if query_str in summary_lower:
                    matches += 2
                
                summary_scores[i] = matches * uniqueness
        
        # Combine: 25% BM25, 25% name, 50% summary
        # Python docstrings are descriptive - trust them!
        final_scores = (
            normalize(bm25_scores) * 0.25 +
            normalize(name_scores) * 0.25 +
            normalize(summary_scores) * 0.50
        )
        
        ranked_idx = np.argsort(final_scores)[::-1][:top_k]
        return [(self.functions[i], final_scores[i]) for i in ranked_idx]


def check_hit(results, expected, k):
    top_k_names = [r[0]['name'].lower() for r in results[:k]]
    return any(
        exp.lower() in name or name in exp.lower()
        for exp in expected
        for name in top_k_names
    )


if __name__ == "__main__":
    import os
    os.chdir('.')
    
    print("🧪 Python Engine v3 - Uniqueness Based")
    print("=" * 50)
    
    # Test on Click
    with open('results/click_summaries.json') as f:
        data = json.load(f)
    
    engine = PythonSearchEngineV3(data['functions'])
    
    tests = [
        ("print to terminal", ["echo", "secho"]),
        ("create cli command", ["command", "add_command"]),
        ("get command by name", ["get_command", "resolve_command"]),
        ("add option to command", ["add_option", "option"]),
        ("prompt user for input", ["prompt", "prompt_func"]),
        ("format command help", ["format_help", "get_help"]),
    ]
    
    hits = 0
    for q, exp in tests:
        results = engine.search(q)
        top = [r[0]['name'] for r in results[:3]]
        hit = check_hit(results, exp, 1)
        if hit: hits += 1
        print(f"  {'✅' if hit else '❌'} \"{q}\" → {top}")
    
    print(f"\nQuick test: {hits}/{len(tests)} = {hits/len(tests)*100:.0f}%")
