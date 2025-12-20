"""
Experiment 04.7: LLM Listwise Reranking
=======================================
Use GPT-4o-mini to rerank top candidates in a single pass.

This is the most promising approach based on research:
- Listwise reranking outperforms pointwise and pairwise
- LLMs understand code semantics natively
- With summaries, LLM can make informed decisions
- Single API call per query = efficient

Expected: This should beat 81% baseline significantly.
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime
from dotenv import load_dotenv

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from _shared import (
    GROUND_TRUTH,
    load_functions_with_summaries,
    FusionEngine,
    evaluate_results,
    print_results,
    save_results,
)

import openai

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# =============================================================================
# LLM LISTWISE RERANKER
# =============================================================================

RERANK_PROMPT = """You are a code search expert. Given a search query and a list of code functions, rank them by relevance.

QUERY: "{query}"

CANDIDATES:
{candidates}

TASK: Rank these functions from MOST to LEAST relevant to the query.

Return ONLY the ranking as comma-separated numbers (e.g., "3,1,5,2,4" if function 3 is most relevant).

RANKING:"""


def format_candidate(idx: int, func: Dict) -> str:
    """Format a candidate function for the prompt."""
    summary = func.get('summary', 'No description available.')
    # Truncate code to avoid token limits
    code_preview = func['code'][:300].replace('\n', ' ').strip()
    if len(func['code']) > 300:
        code_preview += "..."
    
    return f"{idx}. {func['name']}\n   Summary: {summary}\n   Code: {code_preview}"


def parse_ranking(response: str, num_candidates: int) -> List[int]:
    """Parse the LLM's ranking response into indices."""
    try:
        # Extract numbers from response
        import re
        numbers = re.findall(r'\d+', response)
        ranking = [int(n) for n in numbers if 1 <= int(n) <= num_candidates]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_ranking = []
        for n in ranking:
            if n not in seen:
                seen.add(n)
                unique_ranking.append(n)
        
        # Add any missing indices at the end
        for i in range(1, num_candidates + 1):
            if i not in seen:
                unique_ranking.append(i)
        
        return unique_ranking
    except Exception as e:
        print(f"  ⚠️ Failed to parse ranking: {response[:50]}... Error: {e}")
        return list(range(1, num_candidates + 1))


def rerank_with_llm(query: str, candidates: List[Tuple[Dict, float]], 
                    model: str = "gpt-4o-mini") -> List[Tuple[Dict, float]]:
    """Rerank candidates using LLM listwise ranking."""
    if not candidates:
        return []
    
    # Format candidates for prompt
    candidate_texts = [format_candidate(i+1, func) for i, (func, _) in enumerate(candidates)]
    candidates_str = "\n\n".join(candidate_texts)
    
    prompt = RERANK_PROMPT.format(query=query, candidates=candidates_str)
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=50,
        )
        
        ranking_text = response.choices[0].message.content.strip()
        ranking = parse_ranking(ranking_text, len(candidates))
        
        # Reorder candidates based on ranking
        reranked = []
        for idx in ranking:
            if 1 <= idx <= len(candidates):
                func, old_score = candidates[idx - 1]
                # Assign new score based on position
                new_score = len(ranking) - len(reranked)
                reranked.append((func, new_score))
        
        return reranked
    
    except Exception as e:
        print(f"  ⚠️ LLM rerank failed: {e}")
        return candidates


# =============================================================================
# MAIN EXPERIMENT
# =============================================================================

def run_experiment(top_k: int = 5, model: str = "gpt-4o-mini"):
    """Run the LLM listwise reranking experiment."""
    print("=" * 70)
    print("EXPERIMENT 04.7: LLM Listwise Reranking")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Model: {model}")
    print(f"Candidates per query: {top_k}")
    
    # Load data
    functions = load_functions_with_summaries()
    print(f"📦 Loaded {len(functions)} functions with summaries")
    
    # Initialize fusion engine
    engine = FusionEngine(functions)
    print("✅ Fusion engine ready\n")
    
    # Process each query
    results_per_query = []
    total_cost = 0
    
    for i, (query, expected, category) in enumerate(GROUND_TRUTH):
        print(f"[{i+1}/{len(GROUND_TRUTH)}] {query[:50]}...")
        
        # Step 1: Get initial candidates from fusion
        candidates = engine.search(query, top_k=top_k)
        
        # Step 2: Rerank with LLM
        reranked = rerank_with_llm(query, candidates, model)
        
        # Store results
        results_per_query.append(reranked)
        
        # Check if hit
        top_result = reranked[0][0]['name'] if reranked else 'N/A'
        is_hit = any(
            exp.lower() in top_result.lower() or top_result.lower() in exp.lower()
            for exp in expected
        )
        status = "✅" if is_hit else "❌"
        print(f"  {status} → {top_result}")
    
    # Evaluate
    metrics = evaluate_results(results_per_query)
    
    # Print results
    print_results(f"llm_listwise_{model}", metrics)
    
    # Save results
    save_results(f"llm_listwise_top{top_k}", metrics)
    
    # Summary
    print("\n" + "=" * 70)
    if metrics['hit@1'] >= 0.90:
        print("🏆 TARGET ACHIEVED! 90%+ Hit@1")
    elif metrics['hit@1'] > 0.81:
        print(f"📈 IMPROVEMENT! {metrics['hit@1']:.1%} vs 81% baseline")
    else:
        print(f"⚠️ No improvement: {metrics['hit@1']:.1%}")
    print("=" * 70)
    
    return metrics


if __name__ == "__main__":
    # Test with different top_k values
    results = {}
    
    for top_k in [5, 10]:
        print(f"\n{'#' * 70}")
        print(f"Testing with top_k = {top_k}")
        print(f"{'#' * 70}\n")
        
        metrics = run_experiment(top_k=top_k)
        results[f"top_{top_k}"] = metrics
    
    # Compare
    print("\n\n" + "=" * 70)
    print("COMPARISON: LLM Listwise Reranking")
    print("=" * 70)
    print(f"\n{'Config':<20} {'Hit@1':<12} {'Hit@3':<12} {'MRR':<12}")
    print("-" * 56)
    print(f"{'Baseline (no rerank)':<20} {'81.0%':<12} {'100%':<12} {'N/A':<12}")
    
    for name, m in results.items():
        print(f"{name:<20} {m['hit@1']:<12.1%} {m['hit@3']:<12.1%} {m['mrr']:<12.3f}")
    
    print("\n✅ EXPERIMENT COMPLETE!")
