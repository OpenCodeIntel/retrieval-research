"""
Full Pipeline for JavaScript Codebase Evaluation
=================================================

1. Extract functions using JS/TS extractor
2. Generate LLM summaries  
3. Build indices (BM25 + Voyage embeddings)
4. Evaluate with RRF + Reranking

Usage:
    python3 scripts/evaluate_js_codebase.py zustand
"""

import json
import sys
import os
import re
from pathlib import Path
from typing import List, Dict, Any
import time

import numpy as np
from rank_bm25 import BM25Okapi
import voyageai
from openai import OpenAI

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.extractors.javascript import JavaScriptExtractor
from src.extractors.base import ExtractedFunction

# Initialize clients
voyage_client = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))

# OpenAI is optional - only for summary generation
openai_client = None
if os.getenv("OPENAI_API_KEY"):
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
else:
    print("⚠️  OPENAI_API_KEY not set - will use docstrings instead of LLM summaries")


def tokenize(text: str) -> List[str]:
    """Tokenize for BM25."""
    text = text.lower()
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = text.replace('_', ' ').replace('.', ' ')
    return re.findall(r'\b\w+\b', text)


def extract_functions(codebase: str) -> List[ExtractedFunction]:
    """Extract all functions from codebase."""
    repo_path = ROOT / f"test_repos/{codebase}"
    
    if not repo_path.exists():
        raise ValueError(f"Repository not found: {repo_path}")
    
    print(f"📂 Extracting from {repo_path}...")
    
    extractor = JavaScriptExtractor(str(repo_path), language="typescript")
    functions = extractor.extract_all()
    
    print(f"   Found {len(functions)} functions")
    return functions


def generate_summary(func: ExtractedFunction) -> str:
    """Generate LLM summary for a function."""
    # If no OpenAI client, use docstring as fallback
    if openai_client is None:
        return func.docstring or func.signature
    
    prompt = f"""Analyze this {func.language} function and provide a concise 1-2 sentence summary of what it does.

Function: {func.qualified_name}
Signature: {func.signature}
{f'Class: {func.class_name}' if func.class_name else ''}
{f'Class description: {func.class_docstring[:200]}' if func.class_docstring else ''}
{f'Docstring: {func.docstring[:300]}' if func.docstring else ''}

Code:
```{func.language}
{func.code[:1500]}
```

Summary (1-2 sentences, focus on WHAT it does and WHY someone would use it):"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"   Error generating summary for {func.name}: {e}")
        return func.docstring or func.signature


def generate_summaries(functions: List[ExtractedFunction], codebase: str) -> List[ExtractedFunction]:
    """Generate summaries for all functions."""
    output_path = ROOT / f"results/{codebase}_v2_summaries.json"
    
    # Check if we already have summaries
    if output_path.exists():
        print(f"📄 Loading existing summaries from {output_path}...")
        with open(output_path) as f:
            data = json.load(f)
        
        # Reconstruct functions with summaries
        functions_with_summaries = []
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
                language=fd.get('language', 'typescript'),
                summary=fd.get('summary'),
            )
            functions_with_summaries.append(func)
        
        print(f"   Loaded {len(functions_with_summaries)} functions with summaries")
        return functions_with_summaries
    
    # Generate new summaries
    print(f"🤖 Generating summaries for {len(functions)} functions...")
    start_time = time.time()
    
    for i, func in enumerate(functions):
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            remaining = (len(functions) - i - 1) / rate
            print(f"   Progress: {i+1}/{len(functions)} ({rate:.1f}/sec, ~{remaining:.0f}s remaining)")
        
        func.summary = generate_summary(func)
    
    elapsed = time.time() - start_time
    print(f"   ✅ Generated {len(functions)} summaries in {elapsed:.1f}s")
    
    # Save results
    save_functions(functions, codebase)
    
    return functions


def save_functions(functions: List[ExtractedFunction], codebase: str):
    """Save extracted functions with summaries."""
    output_path = ROOT / f"results/{codebase}_v2_summaries.json"
    
    data = {
        'codebase': codebase,
        'count': len(functions),
        'functions': [
            {
                'name': f.name,
                'qualified_name': f.qualified_name,
                'file_path': f.file_path,
                'code': f.code,
                'signature': f.signature,
                'class_name': f.class_name,
                'class_docstring': f.class_docstring,
                'docstring': f.docstring,
                'decorators': f.decorators,
                'is_method': f.is_method,
                'is_dunder': f.is_dunder,
                'language': f.language,
                'summary': f.summary,
            }
            for f in functions
        ]
    }
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"   💾 Saved to {output_path}")


def build_indices(functions: List[ExtractedFunction]):
    """Build search indices."""
    print("🔨 Building indices...")
    
    # BM25
    corpus = []
    for func in functions:
        text = " ".join([
            func.qualified_name, func.name, func.signature,
            func.docstring or "", func.summary or "", " ".join(func.decorators)
        ])
        corpus.append(tokenize(text))
    bm25 = BM25Okapi(corpus)
    
    # Code embeddings (batched)
    contexts = [func.full_context for func in functions]
    code_emb = []
    for i in range(0, len(contexts), 50):
        batch = contexts[i:i+50]
        result = voyage_client.embed(batch, model="voyage-code-3", input_type="document")
        code_emb.extend(result.embeddings)
    code_emb = np.array(code_emb)
    
    # Summary embeddings (batched)
    summaries = [func.summary or func.signature for func in functions]
    summary_emb = []
    for i in range(0, len(summaries), 50):
        batch = summaries[i:i+50]
        result = voyage_client.embed(batch, model="voyage-code-3", input_type="document")
        summary_emb.extend(result.embeddings)
    summary_emb = np.array(summary_emb)
    
    print(f"   ✅ Built indices for {len(functions)} functions")
    return bm25, code_emb, summary_emb


def search_rrf(
    query: str, 
    functions: List[ExtractedFunction], 
    bm25, 
    code_emb: np.ndarray, 
    summary_emb: np.ndarray,
    top_k: int = 10,
    k: int = 60
) -> List[tuple]:
    """Search with RRF fusion."""
    n = len(functions)
    
    # BM25 ranking
    q_tok = tokenize(query)
    bm25_scores = bm25.get_scores(q_tok)
    bm25_ranks = np.argsort(np.argsort(-bm25_scores))
    
    # Semantic rankings
    q_emb = voyage_client.embed([query], model="voyage-code-3", input_type="query").embeddings[0]
    code_scores = np.dot(code_emb, q_emb)
    code_ranks = np.argsort(np.argsort(-code_scores))
    summary_scores = np.dot(summary_emb, q_emb)
    summary_ranks = np.argsort(np.argsort(-summary_scores))
    
    # RRF
    rrf = np.array([
        1/(k+bm25_ranks[i]) + 1/(k+code_ranks[i]) + 1/(k+summary_ranks[i]) 
        for i in range(n)
    ])
    
    top_indices = np.argsort(-rrf)[:top_k]
    return [(functions[i], rrf[i]) for i in top_indices]


def rerank(query: str, candidates: List[tuple]) -> List[tuple]:
    """Rerank with Voyage."""
    docs = [f"{f.qualified_name}: {f.summary or f.docstring or f.signature}" for f, _ in candidates]
    
    try:
        result = voyage_client.rerank(
            query=query,
            documents=docs,
            model="rerank-2",
            top_k=len(candidates)
        )
        
        reranked = []
        for r in result.results:
            func, old_score = candidates[r.index]
            reranked.append((func, r.relevance_score))
        
        return reranked
    except Exception as e:
        print(f"   Rerank error: {e}")
        return candidates


def create_default_queries(functions: List[ExtractedFunction], codebase: str) -> List[Dict]:
    """Create default queries based on extracted functions."""
    queries_path = ROOT / f"evals/{codebase}_queries.json"
    
    if queries_path.exists():
        print(f"📄 Loading existing queries from {queries_path}...")
        with open(queries_path) as f:
            return json.load(f)
    
    print(f"📝 Creating sample queries for {codebase}...")
    
    # Generate queries for important-looking functions
    queries = []
    
    # Pick diverse functions
    seen_names = set()
    for func in functions:
        if func.is_dunder:
            continue
        if func.name in seen_names:
            continue
        if len(func.name) < 3:
            continue
        
        seen_names.add(func.name)
        
        # Create a natural language query from the function
        # This is a simple heuristic - ideally we'd have human-written queries
        name_parts = re.findall(r'[A-Z][a-z]*|[a-z]+', func.name)
        query_text = " ".join(name_parts).lower()
        
        if func.class_name:
            query_text = f"{query_text} in {func.class_name}"
        
        queries.append({
            'query': query_text,
            'expected': [func.name, func.qualified_name]
        })
        
        if len(queries) >= 50:
            break
    
    # Save queries
    with open(queries_path, 'w') as f:
        json.dump(queries, f, indent=2)
    
    print(f"   Created {len(queries)} queries, saved to {queries_path}")
    print(f"   ⚠️  These are auto-generated - edit manually for better evaluation!")
    
    return queries


def is_match(expected_list: List[str], func: ExtractedFunction) -> bool:
    """Check if function matches expected."""
    for exp in expected_list:
        exp_lower = exp.lower()
        if exp_lower == func.name.lower():
            return True
        if exp_lower == func.qualified_name.lower():
            return True
        if exp_lower in func.qualified_name.lower():
            return True
    return False


def evaluate(
    functions: List[ExtractedFunction],
    queries: List[Dict],
    bm25,
    code_emb: np.ndarray,
    summary_emb: np.ndarray,
    use_rerank: bool = True
) -> Dict[str, Any]:
    """Run evaluation."""
    print(f"\n🔬 Evaluating {'with' if use_rerank else 'without'} reranking...")
    
    hits = 0
    results = []
    
    for item in queries:
        query = item['query']
        expected = item['expected']
        expected_list = expected if isinstance(expected, list) else [expected]
        
        # Search
        candidates = search_rrf(query, functions, bm25, code_emb, summary_emb, top_k=10)
        
        # Optional reranking
        if use_rerank:
            candidates = rerank(query, candidates)
        
        # Check hit
        top_func = candidates[0][0]
        hit = is_match(expected_list, top_func)
        if hit:
            hits += 1
        
        results.append({
            'query': query,
            'expected': expected_list,
            'got': top_func.qualified_name,
            'hit': hit
        })
    
    return {
        'hits': hits,
        'total': len(queries),
        'hit_at_1': hits / len(queries),
        'results': results
    }


def main():
    codebase = sys.argv[1] if len(sys.argv) > 1 else "zustand"
    
    print("=" * 70)
    print(f"🚀 JAVASCRIPT CODEBASE EVALUATION - {codebase.upper()}")
    print("=" * 70)
    
    # Step 1: Extract functions
    functions = extract_functions(codebase)
    
    if len(functions) == 0:
        print("❌ No functions extracted!")
        return
    
    # Step 2: Generate summaries
    functions = generate_summaries(functions, codebase)
    
    # Step 3: Build indices
    bm25, code_emb, summary_emb = build_indices(functions)
    
    # Step 4: Load or create queries
    queries = create_default_queries(functions, codebase)
    
    # Step 5: Evaluate
    print("\n" + "=" * 70)
    print("📊 EVALUATION RESULTS")
    print("=" * 70)
    
    # Without reranking
    baseline = evaluate(functions, queries, bm25, code_emb, summary_emb, use_rerank=False)
    print(f"\n   RRF Only:        {baseline['hits']}/{baseline['total']} = {baseline['hit_at_1']*100:.1f}%")
    
    # With reranking
    reranked = evaluate(functions, queries, bm25, code_emb, summary_emb, use_rerank=True)
    print(f"   RRF + Rerank:    {reranked['hits']}/{reranked['total']} = {reranked['hit_at_1']*100:.1f}%")
    
    delta = reranked['hits'] - baseline['hits']
    print(f"   Delta:           {delta:+d} queries")
    
    # Show failures
    failures = [r for r in reranked['results'] if not r['hit']]
    if failures:
        print(f"\n❌ FAILURES ({len(failures)}):")
        for f in failures[:10]:
            print(f"   \"{f['query']}\"")
            print(f"      Expected: {f['expected'][0]} | Got: {f['got']}")


if __name__ == "__main__":
    main()
