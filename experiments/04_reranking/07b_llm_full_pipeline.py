"""
Experiment 04.7b: LLM Full Pipeline (Retrieve + Rerank)
=======================================================
Use GPT-4o-mini for BOTH retrieval and reranking.

This avoids the Voyage API rate limit problem by using
the LLM to understand code semantics directly.

Pipeline:
1. Get ALL functions with summaries
2. Ask LLM to find top 10 most relevant
3. Ask LLM to rerank those 10

This is slower but gives us TRUE performance without API limits.
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from _shared import (
    GROUND_TRUTH,
    load_functions_with_summaries,
    evaluate_results,
    print_results,
    save_results,
)

import openai
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# =============================================================================
# LLM RETRIEVAL (Stage 1)
# =============================================================================

def build_function_index(functions: List[Dict]) -> str:
    """Build a compact index of all functions for the LLM."""
    lines = []
    for i, func in enumerate(functions):
        name = func['name']
        summary = func.get('summary', '')[:100]  # Truncate summary
        lines.append(f"{i+1}. {name}: {summary}")
    return "\n".join(lines)


RETRIEVAL_PROMPT = """You are a code search expert. Given a search query, identify the MOST relevant functions from this codebase.

SEARCH QUERY: "{query}"

FUNCTION INDEX:
{index}

TASK: Return the numbers of the TOP 10 most relevant functions, in order of relevance.
Return ONLY comma-separated numbers (e.g., "42,17,89,3,56,12,78,23,45,91").

TOP 10:"""


def retrieve_with_llm(query: str, functions: List[Dict], index_text: str, 
                      top_k: int = 10) -> List[Dict]:
    """Use LLM to retrieve top-k relevant functions."""
    prompt = RETRIEVAL_PROMPT.format(query=query, index=index_text)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=100,
        )
        
        text = response.choices[0].message.content.strip()
        
        # Parse numbers
        import re
        numbers = re.findall(r'\d+', text)
        indices = [int(n) - 1 for n in numbers if 1 <= int(n) <= len(functions)]
        
        # Remove duplicates
        seen = set()
        unique = []
        for idx in indices:
            if idx not in seen:
                seen.add(idx)
                unique.append(idx)
        
        # Get functions
        return [functions[i] for i in unique[:top_k]]
    
    except Exception as e:
        print(f"  ⚠️ Retrieval error: {e}")
        return functions[:top_k]


# =============================================================================
# LLM RERANKING (Stage 2)
# =============================================================================

RERANK_PROMPT = """You are a code search expert. Given a search query and candidate functions, rank them by relevance.

QUERY: "{query}"

CANDIDATES:
{candidates}

Rank these from MOST to LEAST relevant. Return ONLY comma-separated numbers.

RANKING:"""


def format_candidate_detailed(idx: int, func: Dict) -> str:
    """Format candidate with more detail for reranking."""
    name = func['name']
    summary = func.get('summary', 'No description.')
    code = func['code'][:400].replace('\n', ' ')
    return f"{idx}. {name}\n   {summary}\n   Code: {code}..."


def rerank_with_llm(query: str, candidates: List[Dict]) -> List[Tuple[Dict, float]]:
    """Rerank candidates using LLM."""
    if not candidates:
        return []
    
    candidate_texts = [format_candidate_detailed(i+1, f) for i, f in enumerate(candidates)]
    prompt = RERANK_PROMPT.format(query=query, candidates="\n\n".join(candidate_texts))
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=50,
        )
        
        text = response.choices[0].message.content.strip()
        
        import re
        numbers = re.findall(r'\d+', text)
        ranking = [int(n) for n in numbers if 1 <= int(n) <= len(candidates)]
        
        # Remove duplicates and add missing
        seen = set()
        unique = []
        for n in ranking:
            if n not in seen:
                seen.add(n)
                unique.append(n)
        for i in range(1, len(candidates) + 1):
            if i not in seen:
                unique.append(i)
        
        # Build result
        return [(candidates[idx-1], len(candidates) - i) for i, idx in enumerate(unique)]
    
    except Exception as e:
        print(f"  ⚠️ Rerank error: {e}")
        return [(f, len(candidates) - i) for i, f in enumerate(candidates)]


# =============================================================================
# MAIN
# =============================================================================

def run_experiment():
    print("=" * 70)
    print("EXPERIMENT 04.7b: LLM Full Pipeline (Retrieve + Rerank)")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Model: gpt-4o-mini for both stages")
    
    # Load data
    functions = load_functions_with_summaries()
    print(f"📦 Loaded {len(functions)} functions")
    
    # Build index once
    print("Building function index...")
    index_text = build_function_index(functions)
    print(f"✅ Index built ({len(index_text)} chars)\n")
    
    # Process queries
    results_per_query = []
    
    for i, (query, expected, category) in enumerate(GROUND_TRUTH):
        print(f"[{i+1}/{len(GROUND_TRUTH)}] {query[:50]}...")
        
        # Stage 1: Retrieve
        candidates = retrieve_with_llm(query, functions, index_text, top_k=10)
        print(f"  Retrieved: {[f['name'] for f in candidates[:3]]}...")
        
        # Stage 2: Rerank
        reranked = rerank_with_llm(query, candidates)
        results_per_query.append(reranked)
        
        # Check
        top = reranked[0][0]['name'] if reranked else 'N/A'
        hit = any(exp.lower() in top.lower() or top.lower() in exp.lower() for exp in expected)
        print(f"  {'✅' if hit else '❌'} Final: {top}")
    
    # Evaluate
    metrics = evaluate_results(results_per_query)
    print_results("llm_full_pipeline", metrics)
    save_results("llm_full_pipeline", metrics)
    
    # Summary
    print("\n" + "=" * 70)
    if metrics['hit@1'] >= 0.90:
        print("🏆 TARGET ACHIEVED! 90%+ Hit@1")
    elif metrics['hit@1'] > 0.81:
        print(f"📈 IMPROVEMENT! {metrics['hit@1']:.1%} vs 81% baseline")
    else:
        print(f"Result: {metrics['hit@1']:.1%} Hit@1")
    print("=" * 70)
    
    return metrics


if __name__ == "__main__":
    run_experiment()
