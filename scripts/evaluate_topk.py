"""
Evaluate human queries with Hit@K analysis.
Shows top 5 results to see if correct answer is in there.
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

def evaluate_with_topk(codebase: str):
    summaries_path = ROOT / f"results/{codebase}_v2_summaries.json"
    queries_path = ROOT / f"evals/{codebase}_human_queries.json"
    
    with open(summaries_path) as f:
        data = json.load(f)
    with open(queries_path) as f:
        queries_data = json.load(f)
    
    functions = [FunctionData(
        name=fd['name'], qualified_name=fd['qualified_name'], file_path=fd['file_path'],
        code=fd['code'], signature=fd['signature'], summary=fd.get('summary'), docstring=fd.get('docstring')
    ) for fd in data['functions']]
    
    print(f"📂 Loaded {len(functions)} functions from {codebase}")
    print(f"🔍 Testing {len(queries_data['queries'])} human queries")
    print(f"🔨 Building indices...")
    
    bm25, code_emb, summary_emb = build_indices(functions)
    
    hit_at = {1: 0, 3: 0, 5: 0}
    total = len(queries_data['queries'])
    
    print("\n" + "=" * 80)
    print("TOP-5 ANALYSIS")
    print("=" * 80 + "\n")
    
    for q in queries_data['queries']:
        query = q['query']
        expected_list = q['expected']
        
        rrf_results = search_rrf(query, functions, bm25, code_emb, summary_emb, top_k=10)
        rerank_results = rerank(query, rrf_results)
        
        top5_names = [r[0].qualified_name for r in rerank_results[:5]]
        
        # Check hits at different K
        for k in [1, 3, 5]:
            topk_names = [r[0].qualified_name for r in rerank_results[:k]]
            if any(any(exp in name for exp in expected_list) for name in topk_names):
                hit_at[k] += 1
        
        # Show results
        hit1 = any(any(exp in name for exp in expected_list) for name in top5_names[:1])
        hit5 = any(any(exp in name for exp in expected_list) for name in top5_names)
        
        status = "✅" if hit1 else ("🟡" if hit5 else "❌")
        print(f"{status} \"{query}\"")
        print(f"   Expected: {expected_list}")
        print(f"   Top 5 results:")
        for i, name in enumerate(top5_names, 1):
            marker = "👈" if any(exp in name for exp in expected_list) else ""
            print(f"      {i}. {name} {marker}")
        print()
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\n📊 Hit@K Results:")
    print(f"   Hit@1: {hit_at[1]}/{total} = {hit_at[1]/total*100:.1f}%")
    print(f"   Hit@3: {hit_at[3]}/{total} = {hit_at[3]/total*100:.1f}%")
    print(f"   Hit@5: {hit_at[5]}/{total} = {hit_at[5]/total*100:.1f}%")

if __name__ == "__main__":
    codebase = sys.argv[1] if len(sys.argv) > 1 else "fastapi"
    evaluate_with_topk(codebase)
