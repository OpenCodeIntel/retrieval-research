"""
Test Voyage Reranker
====================

Uses Voyage's rerank-2 model to rerank top RRF results.
This is a learned model, should be more robust than heuristics.
"""

import json
import sys
import os
import re
from pathlib import Path
import numpy as np
from rank_bm25 import BM25Okapi
import voyageai

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.extractors.base import ExtractedFunction

voyage_client = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))


def tokenize(text):
    text = text.lower()
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = text.replace('_', ' ').replace('.', ' ')
    return re.findall(r'\b\w+\b', text)


def load_data(codebase):
    with open(ROOT / f"results/{codebase}_v2_summaries.json") as f:
        data = json.load(f)
    
    functions = []
    for fd in data['functions']:
        func = ExtractedFunction(
            name=fd['name'], qualified_name=fd['qualified_name'],
            file_path=fd['file_path'], code=fd['code'], signature=fd['signature'],
            class_name=fd.get('class_name'), class_docstring=fd.get('class_docstring'),
            docstring=fd.get('docstring'), decorators=fd.get('decorators', []),
            is_method=fd.get('is_method', False), is_dunder=fd.get('is_dunder', False),
            language='python', summary=fd.get('summary'),
        )
        functions.append(func)
    return functions


def build_indices(functions):
    corpus = [tokenize(" ".join([f.qualified_name, f.name, f.signature, f.docstring or "", f.summary or ""])) for f in functions]
    bm25 = BM25Okapi(corpus)
    
    # Batch embeddings to avoid token limit
    contexts = [f.full_context for f in functions]
    code_emb = []
    for i in range(0, len(contexts), 50):
        batch = contexts[i:i+50]
        result = voyage_client.embed(batch, model="voyage-code-3", input_type="document")
        code_emb.extend(result.embeddings)
    code_emb = np.array(code_emb)
    
    summaries = [f.summary or f.signature for f in functions]
    summary_emb = []
    for i in range(0, len(summaries), 50):
        batch = summaries[i:i+50]
        result = voyage_client.embed(batch, model="voyage-code-3", input_type="document")
        summary_emb.extend(result.embeddings)
    summary_emb = np.array(summary_emb)
    
    return bm25, code_emb, summary_emb


def get_rrf_scores(query, functions, bm25, code_emb, summary_emb, k=60):
    q_tok = tokenize(query)
    bm25_scores = bm25.get_scores(q_tok)
    bm25_ranks = np.argsort(np.argsort(-bm25_scores))
    
    q_emb = voyage_client.embed([query], model="voyage-code-3", input_type="query").embeddings[0]
    code_scores = np.dot(code_emb, q_emb)
    code_ranks = np.argsort(np.argsort(-code_scores))
    summary_scores = np.dot(summary_emb, q_emb)
    summary_ranks = np.argsort(np.argsort(-summary_scores))
    
    rrf = np.array([1/(k+bm25_ranks[i]) + 1/(k+code_ranks[i]) + 1/(k+summary_ranks[i]) for i in range(len(functions))])
    return rrf


def is_match(expected_list, func):
    for exp in expected_list:
        exp_lower = exp.lower()
        if exp_lower == func.name.lower():
            return True
        if exp_lower == func.qualified_name.lower():
            return True
        if exp_lower in func.qualified_name.lower():
            return True
    return False


def main():
    codebase = sys.argv[1] if len(sys.argv) > 1 else "requests"
    top_n = int(sys.argv[2]) if len(sys.argv) > 2 else 10  # How many to rerank
    
    print("=" * 70)
    print(f"🔬 VOYAGE RERANKER TEST - {codebase.upper()}")
    print(f"   Reranking top {top_n} results")
    print("=" * 70)
    
    print("\n📦 Loading data...")
    functions = load_data(codebase)
    
    with open(ROOT / f"evals/{codebase}_queries.json") as f:
        queries = json.load(f)
    
    print(f"   {len(functions)} functions, {len(queries)} queries")
    
    print("\n🔨 Building indices...")
    bm25, code_emb, summary_emb = build_indices(functions)
    
    print("\n🔬 Evaluating...")
    
    baseline_hits = 0
    reranked_hits = 0
    improvements = []
    regressions = []
    
    for item in queries:
        query = item['query']
        expected = item['expected']
        expected_list = expected if isinstance(expected, list) else [expected]
        
        # Get RRF scores and top N
        rrf_scores = get_rrf_scores(query, functions, bm25, code_emb, summary_emb)
        top_indices = np.argsort(-rrf_scores)[:top_n]
        top_funcs = [functions[i] for i in top_indices]
        
        # Baseline (top 1 from RRF)
        baseline_top = top_funcs[0]
        baseline_hit = is_match(expected_list, baseline_top)
        if baseline_hit:
            baseline_hits += 1
        
        # Rerank with Voyage
        # Create documents for reranking - use summary + qualified name
        docs = [f"{f.qualified_name}: {f.summary or f.docstring or f.signature}" for f in top_funcs]
        
        try:
            rerank_result = voyage_client.rerank(
                query=query,
                documents=docs,
                model="rerank-2",
                top_k=1
            )
            
            # Get the top result after reranking
            reranked_idx = rerank_result.results[0].index
            reranked_top = top_funcs[reranked_idx]
        except Exception as e:
            print(f"   Rerank error: {e}")
            reranked_top = baseline_top
        
        reranked_hit = is_match(expected_list, reranked_top)
        if reranked_hit:
            reranked_hits += 1
        
        # Track changes
        if reranked_hit and not baseline_hit:
            improvements.append({
                'query': query,
                'expected': expected_list[0],
                'baseline': baseline_top.qualified_name,
                'reranked': reranked_top.qualified_name,
            })
        elif baseline_hit and not reranked_hit:
            regressions.append({
                'query': query,
                'expected': expected_list[0],
                'baseline': baseline_top.qualified_name,
                'reranked': reranked_top.qualified_name,
            })
    
    # Results
    print("\n" + "=" * 70)
    print("📊 RESULTS")
    print("=" * 70)
    
    print(f"\n   Baseline RRF:      {baseline_hits}/{len(queries)} = {baseline_hits/len(queries)*100:.1f}%")
    print(f"   + Voyage Rerank:   {reranked_hits}/{len(queries)} = {reranked_hits/len(queries)*100:.1f}%")
    print(f"   Delta:             {reranked_hits - baseline_hits:+d} queries")
    
    if improvements:
        print(f"\n✅ IMPROVEMENTS ({len(improvements)}):")
        for imp in improvements:
            print(f"   \"{imp['query']}\"")
            print(f"      {imp['baseline']} → {imp['reranked']} ✓")
    
    if regressions:
        print(f"\n❌ REGRESSIONS ({len(regressions)}):")
        for reg in regressions:
            print(f"   \"{reg['query']}\"")
            print(f"      {reg['baseline']} → {reg['reranked']} ✗")
    
    # Summary
    print("\n" + "=" * 70)
    if reranked_hits > baseline_hits:
        print(f"🎉 Reranking improved accuracy by {reranked_hits - baseline_hits} queries!")
    elif reranked_hits < baseline_hits:
        print(f"⚠️  Reranking decreased accuracy by {baseline_hits - reranked_hits} queries")
    else:
        print("➡️  Reranking had no net effect")


if __name__ == "__main__":
    main()
