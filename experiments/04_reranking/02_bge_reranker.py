"""
Experiment 04.2: BGE Reranker (Local)
=====================================
Use BAAI/bge-reranker-v2-m3 for local reranking.

Why BGE:
- Free, no API limits
- Fast inference
- Multilingual support
- Widely used in production

Expected: Better than MS-MARCO (which failed), but may not be code-specific.
"""

import sys
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from _shared import (
    GROUND_TRUTH,
    load_functions_with_summaries,
    FusionEngine,
    evaluate_results,
    print_results,
    save_results,
)

print("Loading BGE reranker model...")
from sentence_transformers import CrossEncoder

# BGE reranker models (choose one):
# - 'BAAI/bge-reranker-v2-m3' - Multilingual, lightweight (568M)
# - 'BAAI/bge-reranker-large' - English-focused, larger
# - 'BAAI/bge-reranker-base' - Smaller, faster

MODEL_NAME = 'BAAI/bge-reranker-v2-m3'
reranker = CrossEncoder(MODEL_NAME, max_length=512)
print(f"✅ Loaded: {MODEL_NAME}\n")


# =============================================================================
# BGE RERANKER
# =============================================================================

def rerank_with_bge(query: str, candidates: List[Tuple[Dict, float]], 
                    use_summary: bool = True) -> List[Tuple[Dict, float]]:
    """Rerank candidates using BGE cross-encoder."""
    if not candidates:
        return []
    
    # Build query-document pairs
    pairs = []
    for func, _ in candidates:
        # Build document text
        doc_parts = [f"Function: {func['name']}"]
        if use_summary and 'summary' in func:
            doc_parts.append(f"Description: {func['summary']}")
        # Add truncated code
        code_preview = func['code'][:400]
        doc_parts.append(f"Code: {code_preview}")
        
        doc_text = "\n".join(doc_parts)
        pairs.append([query, doc_text])
    
    # Score all pairs
    scores = reranker.predict(pairs)
    
    # Rerank by score
    reranked = [(candidates[i][0], float(scores[i])) for i in range(len(candidates))]
    reranked.sort(key=lambda x: x[1], reverse=True)
    
    return reranked


# =============================================================================
# MAIN EXPERIMENT
# =============================================================================

def run_experiment(top_k: int = 10, use_summary: bool = True):
    """Run the BGE reranking experiment."""
    print("=" * 70)
    print("EXPERIMENT 04.2: BGE Reranker")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Model: {MODEL_NAME}")
    print(f"Candidates per query: {top_k}")
    print(f"Use summaries: {use_summary}")
    
    # Load data
    functions = load_functions_with_summaries()
    print(f"📦 Loaded {len(functions)} functions with summaries")
    
    # Initialize fusion engine
    engine = FusionEngine(functions)
    print("✅ Fusion engine ready\n")
    
    # Process each query
    results_per_query = []
    
    for i, (query, expected, category) in enumerate(GROUND_TRUTH):
        print(f"[{i+1}/{len(GROUND_TRUTH)}] {query[:50]}...", end=" ")
        
        # Step 1: Get initial candidates from fusion
        candidates = engine.search(query, top_k=top_k)
        
        # Step 2: Rerank with BGE
        reranked = rerank_with_bge(query, candidates, use_summary)
        
        # Store results
        results_per_query.append(reranked)
        
        # Check if hit
        top_result = reranked[0][0]['name'] if reranked else 'N/A'
        is_hit = any(
            exp.lower() in top_result.lower() or top_result.lower() in exp.lower()
            for exp in expected
        )
        status = "✅" if is_hit else "❌"
        print(f"{status} → {top_result}")
    
    # Evaluate
    metrics = evaluate_results(results_per_query)
    
    # Print results
    config_name = f"bge_{'with' if use_summary else 'no'}_summary"
    print_results(config_name, metrics)
    
    # Save results
    save_results(f"bge_top{top_k}_summary{use_summary}", metrics)
    
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
    results = {}
    
    # Test different configurations
    configs = [
        {"top_k": 10, "use_summary": True},
        {"top_k": 10, "use_summary": False},
        {"top_k": 20, "use_summary": True},
    ]
    
    for config in configs:
        print(f"\n{'#' * 70}")
        print(f"Testing: top_k={config['top_k']}, use_summary={config['use_summary']}")
        print(f"{'#' * 70}\n")
        
        metrics = run_experiment(**config)
        results[f"top{config['top_k']}_sum{config['use_summary']}"] = metrics
    
    # Compare
    print("\n\n" + "=" * 70)
    print("COMPARISON: BGE Reranker Configurations")
    print("=" * 70)
    print(f"\n{'Config':<25} {'Hit@1':<12} {'Hit@3':<12} {'MRR':<12}")
    print("-" * 61)
    print(f"{'Baseline (no rerank)':<25} {'81.0%':<12} {'100%':<12} {'N/A':<12}")
    
    for name, m in results.items():
        print(f"{name:<25} {m['hit@1']:<12.1%} {m['hit@3']:<12.1%} {m['mrr']:<12.3f}")
    
    print("\n✅ EXPERIMENT COMPLETE!")
