"""
Evaluate with Voyage Embeddings (Code-Specific)
================================================

Voyage-code-3 is specifically trained for code search.
This script tests if it closes the gap with OLD system (64%).

⚠️  RATE LIMIT: Voyage free tier = 3 RPM (requests per minute)
    This script will take ~20-30 minutes for Flask (356 functions)
    It waits 25 seconds between batches to avoid rate limits.

Usage:
    cd .
    
    # First, set your Voyage API key:
    export VOYAGE_API_KEY="your-voyage-api-key"
    
    # Then run:
    python3 scripts/evaluate_voyage.py flask

Output: Prints Hit@1 comparison with OLD system
"""

import json
import sys
import os
import time
from pathlib import Path

# Setup paths
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Check for API key FIRST
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
if not VOYAGE_API_KEY:
    print("❌ ERROR: VOYAGE_API_KEY not set!")
    print("\nRun this first:")
    print('  export VOYAGE_API_KEY="your-voyage-api-key"')
    print("\nThen run again:")
    print("  python3 scripts/evaluate_voyage.py flask")
    sys.exit(1)

import voyageai
import numpy as np
from rank_bm25 import BM25Okapi
import re

from src.extractors.base import ExtractedFunction


def load_functions(codebase: str):
    """Load functions from v2 summaries."""
    path = ROOT / f"results/{codebase}_v2_summaries.json"
    
    with open(path) as f:
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
    
    return functions


def embed_with_voyage(texts, voyage_client, batch_size=50):
    """Embed texts with Voyage, handling rate limits."""
    embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        
        print(f"      Embedding {i+1}-{min(i+batch_size, len(texts))}/{len(texts)}...")
        
        try:
            result = voyage_client.embed(
                batch,
                model="voyage-code-3",
                input_type="document"
            )
            embeddings.extend(result.embeddings)
        except Exception as e:
            print(f"      ⚠️ Error: {e}")
            print(f"      Waiting 60s and retrying...")
            time.sleep(60)
            result = voyage_client.embed(
                batch,
                model="voyage-code-3",
                input_type="document"
            )
            embeddings.extend(result.embeddings)
        
        # Rate limit: wait between batches
        if i + batch_size < len(texts):
            print(f"      ⏳ Waiting 25s for rate limit...")
            time.sleep(25)
    
    return embeddings


def tokenize(text):
    """Tokenize for BM25."""
    text = text.lower()
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = text.replace('_', ' ').replace('.', ' ')
    return re.findall(r'\b\w+\b', text)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 evaluate_voyage.py <codebase>")
        print("Example: python3 evaluate_voyage.py flask")
        sys.exit(1)
    
    codebase = sys.argv[1].lower()
    
    print("=" * 60)
    print(f"🚀 VOYAGE EMBEDDINGS EVALUATION - {codebase.upper()}")
    print("=" * 60)
    print(f"\n⚠️  This will take ~20-30 minutes due to rate limits")
    print(f"    Go grab a coffee! ☕\n")
    
    # Load functions
    print(f"📦 Loading {codebase} functions...")
    try:
        functions = load_functions(codebase)
    except FileNotFoundError:
        print(f"❌ File not found! Run generate_summaries.py first:")
        print(f"   python3 scripts/generate_summaries.py {codebase}")
        sys.exit(1)
    
    print(f"   {len(functions)} functions loaded")
    
    # Setup Voyage client
    print(f"\n🔌 Connecting to Voyage AI...")
    voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
    
    # Build BM25 index
    print(f"\n📚 Building BM25 index...")
    corpus = []
    for func in functions:
        text_parts = [
            func.qualified_name,
            func.name,
            func.signature,
            func.docstring or "",
            func.class_docstring or "",
            func.summary or "",
            " ".join(func.decorators),
        ]
        corpus.append(tokenize(" ".join(text_parts)))
    bm25 = BM25Okapi(corpus)
    print(f"   ✅ BM25 ready")
    
    # Build embeddings with Voyage
    print(f"\n🧠 Building Voyage embeddings (this takes time)...")
    contexts = []
    for func in functions:
        if func.summary:
            ctx = f"{func.signature}\n{func.summary}"
        else:
            ctx = func.full_context
        contexts.append(ctx)
    
    embeddings = embed_with_voyage(contexts, voyage_client)
    embeddings = np.array(embeddings)
    print(f"   ✅ Embedded {len(embeddings)} functions")
    
    # Load queries
    print(f"\n📋 Loading queries...")
    queries_path = ROOT / f"evals/{codebase}_queries.json"
    try:
        with open(queries_path) as f:
            queries = json.load(f)
    except FileNotFoundError:
        print(f"❌ No queries at {queries_path}")
        sys.exit(1)
    print(f"   {len(queries)} queries")
    
    # Evaluate
    print(f"\n🎯 Running evaluation...")
    print("-" * 60)
    
    hits = 0
    bm25_weight = 0.4
    semantic_weight = 0.6
    
    for item in queries:
        query = item['query']
        expected = item['expected']
        expected_list = expected if isinstance(expected, list) else [expected]
        
        # BM25 scores
        query_tokens = tokenize(query)
        bm25_scores = bm25.get_scores(query_tokens)
        if bm25_scores.max() > 0:
            bm25_scores = bm25_scores / bm25_scores.max()
        
        # Voyage semantic scores
        query_emb = voyage_client.embed(
            [query],
            model="voyage-code-3",
            input_type="query"
        ).embeddings[0]
        
        semantic_scores = np.dot(embeddings, query_emb)
        semantic_scores = (semantic_scores - semantic_scores.min()) / (semantic_scores.max() - semantic_scores.min() + 1e-8)
        
        # Combine
        combined = (bm25_weight * bm25_scores) + (semantic_weight * semantic_scores)
        
        # Get top result
        top_idx = np.argmax(combined)
        top_func = functions[top_idx]
        
        # Check hit
        is_hit = any(
            exp == top_func.name or 
            exp == top_func.qualified_name or 
            exp in top_func.qualified_name
            for exp in expected_list
        )
        
        if is_hit:
            hits += 1
            status = "✅"
        else:
            status = "❌"
        
        print(f"{status} {query[:45]}")
        print(f"   Expected: {expected_list[0]} | Got: {top_func.qualified_name}")
        
        # Small delay for query embedding rate limit
        time.sleep(0.5)
    
    # Results
    hit_rate = hits / len(queries)
    
    print("\n" + "=" * 60)
    print(f"🎯 VOYAGE Hit@1: {hit_rate*100:.1f}% ({hits}/{len(queries)})")
    print("=" * 60)
    
    # Load old results for comparison
    try:
        with open(ROOT / f"results/{codebase}_evaluation.json") as f:
            old_data = json.load(f)
        old_hit = old_data.get('hit@1', 0) * 100
        
        print(f"\n📊 COMPARISON:")
        print(f"   OLD system (Voyage+RRF): {old_hit:.1f}%")
        print(f"   NEW+OpenAI:              54-56%")
        print(f"   NEW+Voyage:              {hit_rate*100:.1f}%")
        
        diff = hit_rate*100 - old_hit
        emoji = "📈" if diff > 0 else "📉" if diff < 0 else "➡️"
        print(f"   {emoji} vs OLD: {diff:+.1f}%")
    except:
        pass
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
