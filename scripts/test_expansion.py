"""
Test Query Expansion Impact on Search
=====================================

Tests if expanding queries improves Hit@1 on failing cases.
"""

import json
import sys
import os
import re
from pathlib import Path
from typing import List, Dict

import numpy as np
from rank_bm25 import BM25Okapi
import voyageai

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.extractors.base import ExtractedFunction
from src.search.query_expansion import expand_query

voyage_client = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))


def tokenize(text: str) -> List[str]:
    text = text.lower()
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = text.replace('_', ' ').replace('.', ' ')
    return re.findall(r'\b\w+\b', text)


def load_data(codebase: str):
    """Load functions and build indices."""
    with open(ROOT / f"results/{codebase}_v2_summaries.json") as f:
        data = json.load(f)
    
    functions = []
    for fd in data['functions']:
        func = ExtractedFunction(
            name=fd['name'],
            qualified_name=fd['qualified_name'],
            file_path=fd['file_path'],
            code=fd['code'],
            signature=fd['signature'],
            class_name=fd.get('class_name'),
            class_docstring=fd.get('class_docstring'),
            docstring=fd.get('docstring'),
            decorators=fd.get('decorators', []),
            is_method=fd.get('is_method', False),
            is_dunder=fd.get('is_dunder', False),
            language='python',
            summary=fd.get('summary'),
        )
        functions.append(func)
    
    # Build BM25
    corpus = []
    for func in functions:
        text = " ".join([
            func.qualified_name, func.name, func.signature,
            func.docstring or "", func.summary or "", " ".join(func.decorators)
        ])
        corpus.append(tokenize(text))
    bm25 = BM25Okapi(corpus)
    
    # Build embeddings
    contexts = [f.full_context for f in functions]
    summaries = [f.summary or f.signature for f in functions]
    
    code_emb = []
    for i in range(0, len(contexts), 100):
        batch = contexts[i:i+100]
        result = voyage_client.embed(batch, model="voyage-code-3", input_type="document")
        code_emb.extend(result.embeddings)
    code_emb = np.array(code_emb)
    
    summary_emb = []
    for i in range(0, len(summaries), 100):
        batch = summaries[i:i+100]
        result = voyage_client.embed(batch, model="voyage-code-3", input_type="document")
        summary_emb.extend(result.embeddings)
    summary_emb = np.array(summary_emb)
    
    return functions, bm25, code_emb, summary_emb


def rrf_search(query: str, functions, bm25, code_emb, summary_emb, k=60):
    """Standard RRF search."""
    n = len(functions)
    
    # BM25
    bm25_scores = bm25.get_scores(tokenize(query))
    bm25_ranks = np.argsort(np.argsort(-bm25_scores))
    
    # Semantic
    q_emb = voyage_client.embed([query], model="voyage-code-3", input_type="query").embeddings[0]
    code_scores = np.dot(code_emb, q_emb)
    code_ranks = np.argsort(np.argsort(-code_scores))
    summary_scores = np.dot(summary_emb, q_emb)
    summary_ranks = np.argsort(np.argsort(-summary_scores))
    
    # RRF
    rrf = np.zeros(n)
    for i in range(n):
        rrf[i] = 1/(k+bm25_ranks[i]) + 1/(k+code_ranks[i]) + 1/(k+summary_ranks[i])
    
    return rrf


def expanded_rrf_search(query: str, functions, bm25, code_emb, summary_emb, k=60):
    """RRF search with query expansion."""
    expanded_queries = expand_query(query)
    n = len(functions)
    
    # Combine RRF scores from all expanded queries
    combined_rrf = np.zeros(n)
    
    for i, eq in enumerate(expanded_queries):
        weight = 1.0 if i == 0 else 0.3  # Original query weighted more
        rrf_scores = rrf_search(eq, functions, bm25, code_emb, summary_emb, k)
        combined_rrf += weight * rrf_scores
    
    return combined_rrf


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
    
    print("=" * 70)
    print(f"🧪 QUERY EXPANSION TEST - {codebase.upper()}")
    print("=" * 70)
    
    print(f"\n📦 Loading data...")
    functions, bm25, code_emb, summary_emb = load_data(codebase)
    
    with open(ROOT / f"evals/{codebase}_queries.json") as f:
        queries = json.load(f)
    
    print(f"   {len(functions)} functions, {len(queries)} queries")
    
    # Test both approaches
    print(f"\n🔬 Running comparison...")
    
    baseline_hits = 0
    expanded_hits = 0
    improvements = []
    regressions = []
    
    for item in queries:
        query = item['query']
        expected = item['expected']
        expected_list = expected if isinstance(expected, list) else [expected]
        
        # Baseline
        baseline_rrf = rrf_search(query, functions, bm25, code_emb, summary_emb)
        baseline_top = functions[np.argmax(baseline_rrf)]
        baseline_hit = is_match(expected_list, baseline_top)
        if baseline_hit:
            baseline_hits += 1
        
        # Expanded
        expanded_rrf = expanded_rrf_search(query, functions, bm25, code_emb, summary_emb)
        expanded_top = functions[np.argmax(expanded_rrf)]
        expanded_hit = is_match(expected_list, expanded_top)
        if expanded_hit:
            expanded_hits += 1
        
        # Track changes
        if expanded_hit and not baseline_hit:
            improvements.append((query, expected_list[0], expanded_top.qualified_name))
        elif baseline_hit and not expanded_hit:
            regressions.append((query, expected_list[0], expanded_top.qualified_name))
    
    # Results
    print("\n" + "=" * 70)
    print("📊 RESULTS")
    print("=" * 70)
    
    print(f"\n   Baseline RRF:     {baseline_hits}/{len(queries)} = {baseline_hits/len(queries)*100:.1f}%")
    print(f"   Expanded RRF:     {expanded_hits}/{len(queries)} = {expanded_hits/len(queries)*100:.1f}%")
    print(f"   Delta:            {expanded_hits - baseline_hits:+d} queries")
    
    if improvements:
        print(f"\n✅ IMPROVEMENTS ({len(improvements)}):")
        for q, exp, got in improvements:
            print(f"   \"{q[:40]}\" → {got}")
    
    if regressions:
        print(f"\n❌ REGRESSIONS ({len(regressions)}):")
        for q, exp, got in regressions:
            print(f"   \"{q[:40]}\" → expected {exp}, got {got}")


if __name__ == "__main__":
    main()
