"""
Evaluate human queries on FILTERED codebase (core only, no examples).
"""
import json
import sys
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List

import numpy as np
from rank_bm25 import BM25Okapi
import voyageai

ROOT = Path(__file__).parent.parent
voyage_client = voyageai.Client()

@dataclass
class FunctionData:
    name: str
    qualified_name: str
    file_path: str
    code: str
    signature: str
    summary: str = None
    docstring: str = None
    
    @property
    def full_context(self):
        return f"{self.qualified_name}\n{self.signature}\n{self.code[:500]}"

def tokenize(text: str) -> List[str]:
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = re.sub(r'[_\-./]', ' ', text)
    return text.lower().split()

def build_indices(functions):
    corpus = []
    for func in functions:
        text = " ".join([func.qualified_name, func.name, func.signature, func.docstring or "", func.summary or ""])
        corpus.append(tokenize(text))
    bm25 = BM25Okapi(corpus)
    
    contexts = [func.full_context for func in functions]
    code_emb = []
    for i in range(0, len(contexts), 50):
        batch = contexts[i:i+50]
        result = voyage_client.embed(batch, model="voyage-code-3", input_type="document")
        code_emb.extend(result.embeddings)
    code_emb = np.array(code_emb)
    
    summaries = [func.summary or func.signature for func in functions]
    summary_emb = []
    for i in range(0, len(summaries), 50):
        batch = summaries[i:i+50]
        result = voyage_client.embed(batch, model="voyage-code-3", input_type="document")
        summary_emb.extend(result.embeddings)
    summary_emb = np.array(summary_emb)
    
    return bm25, code_emb, summary_emb

def search_rrf(query, functions, bm25, code_emb, summary_emb, top_k=10, k=60):
    n = len(functions)
    q_tok = tokenize(query)
    bm25_scores = bm25.get_scores(q_tok)
    bm25_ranks = np.argsort(np.argsort(-bm25_scores))
    
    q_emb = voyage_client.embed([query], model="voyage-code-3", input_type="query").embeddings[0]
    code_scores = np.dot(code_emb, q_emb)
    code_ranks = np.argsort(np.argsort(-code_scores))
    summary_scores = np.dot(summary_emb, q_emb)
    summary_ranks = np.argsort(np.argsort(-summary_scores))
    
    rrf = np.array([1/(k+bm25_ranks[i]) + 1/(k+code_ranks[i]) + 1/(k+summary_ranks[i]) for i in range(n)])
    top_indices = np.argsort(-rrf)[:top_k]
    return [(functions[i], rrf[i]) for i in top_indices]

def rerank(query, candidates):
    docs = [f"{f.qualified_name}: {f.summary or f.docstring or f.signature}" for f, _ in candidates]
    result = voyage_client.rerank(query=query, documents=docs, model="rerank-2", top_k=len(candidates))
    return [(candidates[r.index][0], r.relevance_score) for r in result.results]

def evaluate_filtered(codebase: str, include_paths: list = None, exclude_paths: list = None):
    summaries_path = ROOT / f"results/{codebase}_v2_summaries.json"
    queries_path = ROOT / f"evals/{codebase}_human_queries.json"
    
    with open(summaries_path) as f:
        data = json.load(f)
    with open(queries_path) as f:
        queries_data = json.load(f)
    
    # Filter functions
    all_functions = data['functions']
    
    if include_paths:
        all_functions = [f for f in all_functions if any(f['file_path'].startswith(p) for p in include_paths)]
    if exclude_paths:
        all_functions = [f for f in all_functions if not any(f['file_path'].startswith(p) for p in exclude_paths)]
    
    functions = [FunctionData(
        name=fd['name'], qualified_name=fd['qualified_name'], file_path=fd['file_path'],
        code=fd['code'], signature=fd['signature'], summary=fd.get('summary'), docstring=fd.get('docstring')
    ) for fd in all_functions]
    
    print(f"📂 Loaded {len(functions)} functions from {codebase} (filtered)")
    if include_paths:
        print(f"   ✅ Include: {include_paths}")
    if exclude_paths:
        print(f"   ❌ Exclude: {exclude_paths}")
    print(f"🔍 Testing {len(queries_data['queries'])} human queries")
    print(f"🔨 Building indices...")
    
    bm25, code_emb, summary_emb = build_indices(functions)
    
    results = {'correct': 0, 'total': 0, 'failures': []}
    
    print("\n" + "=" * 80)
    print("EVALUATION RESULTS (FILTERED)")
    print("=" * 80)
    
    for q in queries_data['queries']:
        query = q['query']
        expected_list = q['expected']
        difficulty = q.get('difficulty', 'medium')
        
        rrf_results = search_rrf(query, functions, bm25, code_emb, summary_emb, top_k=10)
        rerank_results = rerank(query, rrf_results)
        
        top1_name = rerank_results[0][0].qualified_name if rerank_results else ""
        hit = any(exp in top1_name for exp in expected_list)
        
        results['total'] += 1
        if hit:
            results['correct'] += 1
            print(f"✅ [{difficulty:6}] \"{query}\"")
        else:
            results['failures'].append({
                'query': query,
                'expected': expected_list,
                'got': top1_name
            })
            print(f"❌ [{difficulty:6}] \"{query}\"")
            print(f"   Expected: {expected_list}")
            print(f"   Got: {top1_name}")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    accuracy = results['correct'] / results['total'] * 100
    print(f"\n📊 Overall Results:")
    print(f"   Accuracy: {results['correct']}/{results['total']} = {accuracy:.1f}%")
    print(f"❌ Failures: {len(results['failures'])}")

if __name__ == "__main__":
    import sys
    codebase = sys.argv[1] if len(sys.argv) > 1 else "fastapi"
    
    if codebase == "fastapi":
        evaluate_filtered(codebase, include_paths=["fastapi/"])
    elif codebase == "lodash":
        evaluate_filtered(codebase, exclude_paths=["test/", "vendor/"])
    elif codebase == "express":
        evaluate_filtered(codebase, include_paths=["lib/"])
    else:
        evaluate_filtered(codebase)
