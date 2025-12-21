"""
Ablation Study: Test contribution of each component in Triple Fusion.

Components:
1. BM25 (lexical search)
2. Code Embeddings (Voyage-code-3 on code)  
3. Summary Embeddings (Voyage-code-3 on summaries)
4. Reranking (Voyage rerank-2)

Configurations to test:
- Full system (all components)
- Remove one component at a time
- Single component only
"""
import json
import sys
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Tuple
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

def build_all_indices(functions):
    """Build all indices once, reuse for different configurations."""
    # BM25
    corpus = []
    for func in functions:
        text = " ".join([func.qualified_name, func.name, func.signature, func.docstring or "", func.summary or ""])
        corpus.append(tokenize(text))
    bm25 = BM25Okapi(corpus)
    
    # Code embeddings
    contexts = [func.full_context for func in functions]
    code_emb = []
    for i in range(0, len(contexts), 50):
        batch = contexts[i:i+50]
        result = voyage_client.embed(batch, model="voyage-code-3", input_type="document")
        code_emb.extend(result.embeddings)
    code_emb = np.array(code_emb)
    
    # Summary embeddings
    summaries = [func.summary or func.signature for func in functions]
    summary_emb = []
    for i in range(0, len(summaries), 50):
        batch = summaries[i:i+50]
        result = voyage_client.embed(batch, model="voyage-code-3", input_type="document")
        summary_emb.extend(result.embeddings)
    summary_emb = np.array(summary_emb)
    
    return bm25, code_emb, summary_emb

def search_configurable(
    query: str, 
    functions: List[FunctionData],
    bm25, code_emb, summary_emb,
    use_bm25: bool = True,
    use_code_emb: bool = True,
    use_summary_emb: bool = True,
    top_k: int = 10,
    k: int = 60
) -> List[Tuple[FunctionData, float]]:
    """Search with configurable components."""
    n = len(functions)
    
    # Get query embedding (needed for code/summary)
    q_emb = None
    if use_code_emb or use_summary_emb:
        q_emb = voyage_client.embed([query], model="voyage-code-3", input_type="query").embeddings[0]
    
    # Calculate scores for enabled components
    scores = []
    
    if use_bm25:
        q_tok = tokenize(query)
        bm25_scores = bm25.get_scores(q_tok)
        bm25_ranks = np.argsort(np.argsort(-bm25_scores))
        scores.append(bm25_ranks)
    
    if use_code_emb:
        code_scores = np.dot(code_emb, q_emb)
        code_ranks = np.argsort(np.argsort(-code_scores))
        scores.append(code_ranks)
    
    if use_summary_emb:
        summary_scores = np.dot(summary_emb, q_emb)
        summary_ranks = np.argsort(np.argsort(-summary_scores))
        scores.append(summary_ranks)
    
    # RRF fusion
    if len(scores) == 0:
        return []
    
    rrf = np.zeros(n)
    for ranks in scores:
        rrf += np.array([1/(k + ranks[i]) for i in range(n)])
    
    top_indices = np.argsort(-rrf)[:top_k]
    return [(functions[i], rrf[i]) for i in top_indices]

def rerank(query: str, candidates: List[Tuple[FunctionData, float]]) -> List[Tuple[FunctionData, float]]:
    """Rerank candidates using Voyage rerank-2."""
    if not candidates:
        return []
    docs = [f"{f.qualified_name}: {f.summary or f.docstring or f.signature}" for f, _ in candidates]
    result = voyage_client.rerank(query=query, documents=docs, model="rerank-2", top_k=len(candidates))
    return [(candidates[r.index][0], r.relevance_score) for r in result.results]

def evaluate_configuration(
    name: str,
    queries: List[Dict],
    functions: List[FunctionData],
    bm25, code_emb, summary_emb,
    use_bm25: bool = True,
    use_code_emb: bool = True,
    use_summary_emb: bool = True,
    use_rerank: bool = True
) -> Dict:
    """Evaluate a specific configuration."""
    correct = 0
    total = len(queries)
    
    for q in queries:
        query = q['query']
        expected_list = q['expected']
        
        # Search
        results = search_configurable(
            query, functions, bm25, code_emb, summary_emb,
            use_bm25=use_bm25,
            use_code_emb=use_code_emb,
            use_summary_emb=use_summary_emb
        )
        
        # Optionally rerank
        if use_rerank and results:
            results = rerank(query, results)
        
        # Check hit
        if results:
            top1_name = results[0][0].qualified_name
            hit = any(exp in top1_name for exp in expected_list)
            if hit:
                correct += 1
    
    accuracy = correct / total * 100 if total > 0 else 0
    return {
        'name': name,
        'correct': correct,
        'total': total,
        'accuracy': accuracy
    }

def run_ablation_study(codebase: str):
    """Run full ablation study on a codebase."""
    
    # Load data
    summaries_path = ROOT / f"results/{codebase}_v2_summaries.json"
    
    # Try human queries first, fall back to auto
    human_queries_path = ROOT / f"evals/{codebase}_human_queries.json"
    auto_queries_path = ROOT / f"evals/{codebase}_queries.json"
    
    if human_queries_path.exists():
        queries_path = human_queries_path
        query_type = "human"
    else:
        queries_path = auto_queries_path
        query_type = "auto"
    
    with open(summaries_path) as f:
        data = json.load(f)
    with open(queries_path) as f:
        queries_data = json.load(f)
    
    # Handle both formats: {"queries": [...]} and [...]
    if isinstance(queries_data, list):
        queries_data = {"queries": queries_data}
    
    functions = [FunctionData(
        name=fd['name'], qualified_name=fd['qualified_name'], file_path=fd['file_path'],
        code=fd['code'], signature=fd['signature'], summary=fd.get('summary'), docstring=fd.get('docstring')
    ) for fd in data['functions']]
    
    queries = queries_data['queries']
    
    print(f"=" * 70)
    print(f"ABLATION STUDY: {codebase.upper()}")
    print(f"=" * 70)
    print(f"📂 Functions: {len(functions)}")
    print(f"🔍 Queries: {len(queries)} ({query_type})")
    print(f"\n🔨 Building indices (one-time)...")
    
    bm25, code_emb, summary_emb = build_all_indices(functions)
    
    print(f"✅ Indices ready\n")
    
    # Define configurations to test
    configurations = [
        # Full system
        ("Full System (BM25 + Code + Summary + Rerank)", True, True, True, True),
        
        # Remove reranking
        ("Without Reranking", True, True, True, False),
        
        # Remove one retrieval component
        ("Without BM25", False, True, True, True),
        ("Without Code Embeddings", True, False, True, True),
        ("Without Summary Embeddings", True, True, False, True),
        
        # Two components only (+ rerank)
        ("BM25 + Code Only", True, True, False, True),
        ("BM25 + Summary Only", True, False, True, True),
        ("Code + Summary Only", False, True, True, True),
        
        # Single component only (+ rerank)
        ("BM25 Only", True, False, False, True),
        ("Code Embeddings Only", False, True, False, True),
        ("Summary Embeddings Only", False, False, True, True),
        
        # Single component WITHOUT rerank
        ("BM25 Only (no rerank)", True, False, False, False),
        ("Code Embeddings Only (no rerank)", False, True, False, False),
        ("Summary Embeddings Only (no rerank)", False, False, True, False),
    ]
    
    results = []
    
    print("Running configurations...\n")
    
    for name, use_bm25, use_code, use_summary, use_rerank in configurations:
        result = evaluate_configuration(
            name, queries, functions,
            bm25, code_emb, summary_emb,
            use_bm25=use_bm25,
            use_code_emb=use_code,
            use_summary_emb=use_summary,
            use_rerank=use_rerank
        )
        results.append(result)
        print(f"  {result['accuracy']:5.1f}%  {name}")
    
    # Print summary table
    print(f"\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    
    # Sort by accuracy
    results_sorted = sorted(results, key=lambda x: x['accuracy'], reverse=True)
    
    print(f"\n{'Configuration':<45} {'Accuracy':>10} {'Delta':>10}")
    print("-" * 70)
    
    full_accuracy = results[0]['accuracy']  # First config is full system
    
    for r in results_sorted:
        delta = r['accuracy'] - full_accuracy
        delta_str = f"{delta:+.1f}%" if delta != 0 else "baseline"
        print(f"{r['name']:<45} {r['accuracy']:>9.1f}% {delta_str:>10}")
    
    # Key insights
    print(f"\n" + "=" * 70)
    print("KEY INSIGHTS")
    print("=" * 70)
    
    # Find contribution of each component
    full = results[0]['accuracy']
    no_rerank = results[1]['accuracy']
    no_bm25 = results[2]['accuracy']
    no_code = results[3]['accuracy']
    no_summary = results[4]['accuracy']
    
    print(f"\n📊 Component Contributions (what happens when removed):")
    print(f"   Reranking:          {full - no_rerank:+.1f}% impact")
    print(f"   BM25:               {full - no_bm25:+.1f}% impact")
    print(f"   Code Embeddings:    {full - no_code:+.1f}% impact")
    print(f"   Summary Embeddings: {full - no_summary:+.1f}% impact")
    
    # Best single component
    bm25_only = next(r for r in results if r['name'] == "BM25 Only")
    code_only = next(r for r in results if r['name'] == "Code Embeddings Only")
    summary_only = next(r for r in results if r['name'] == "Summary Embeddings Only")
    
    print(f"\n📊 Single Component Performance (with rerank):")
    print(f"   BM25 Only:          {bm25_only['accuracy']:.1f}%")
    print(f"   Code Emb Only:      {code_only['accuracy']:.1f}%")
    print(f"   Summary Emb Only:   {summary_only['accuracy']:.1f}%")
    
    print(f"\n📊 Fusion Benefit:")
    best_single = max(bm25_only['accuracy'], code_only['accuracy'], summary_only['accuracy'])
    print(f"   Best single component: {best_single:.1f}%")
    print(f"   Full fusion system:    {full:.1f}%")
    print(f"   Fusion benefit:        +{full - best_single:.1f}%")
    
    return results

if __name__ == "__main__":
    codebase = sys.argv[1] if len(sys.argv) > 1 else "gorm"
    run_ablation_study(codebase)
