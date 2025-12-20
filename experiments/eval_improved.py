"""
Full evaluation with IMPROVED search engine
"""

import json
import sys
sys.path.insert(0, 'experiments')

from comprehensive_test_suite import COMPREHENSIVE_GROUND_TRUTH
from improved_search_engine import ImprovedFusionEngine
from collections import defaultdict

def check_hit(results, expected, k):
    top_k_names = [r[0]['name'].lower() for r in results[:k]]
    return any(
        exp.lower() in name or name in exp.lower()
        for exp in expected
        for name in top_k_names
    )

def run_evaluation():
    # Load functions
    with open('results/exp03_summaries.json') as f:
        data = json.load(f)
    
    functions = data['functions']
    engine = ImprovedFusionEngine(functions)
    
    results_by_category = defaultdict(list)
    all_results = []
    
    for query, expected, category in COMPREHENSIVE_GROUND_TRUTH:
        results = engine.search(query, top_k=10)
        
        hit1 = check_hit(results, expected, 1)
        hit3 = check_hit(results, expected, 3)
        hit5 = check_hit(results, expected, 5)
        
        result = {
            'query': query,
            'expected': expected,
            'category': category,
            'hit@1': hit1,
            'hit@3': hit3,
            'hit@5': hit5,
            'top_result': results[0][0]['name'],
            'top_3': [r[0]['name'] for r in results[:3]],
        }
        
        all_results.append(result)
        results_by_category[category].append(result)
    
    # Print results
    print("=" * 70)
    print("📊 IMPROVED ENGINE - COMPREHENSIVE EVALUATION")
    print("=" * 70)
    
    total = len(all_results)
    hit1 = sum(1 for r in all_results if r['hit@1'])
    hit3 = sum(1 for r in all_results if r['hit@3'])
    hit5 = sum(1 for r in all_results if r['hit@5'])
    
    print(f"\n🎯 OVERALL ({total} queries)")
    print(f"   Hit@1: {hit1}/{total} = {hit1/total*100:.1f}%")
    print(f"   Hit@3: {hit3}/{total} = {hit3/total*100:.1f}%")
    print(f"   Hit@5: {hit5}/{total} = {hit5/total*100:.1f}%")
    
    # Compare with old
    print(f"\n📈 vs OLD ENGINE:")
    print(f"   Hit@1: 87.7% → {hit1/total*100:.1f}% ({(hit1/total - 0.877)*100:+.1f}%)")
    print(f"   Hit@3: 98.5% → {hit3/total*100:.1f}% ({(hit3/total - 0.985)*100:+.1f}%)")
    
    # Per category
    print(f"\n📁 BY CATEGORY:")
    
    for category in sorted(results_by_category.keys()):
        cat_results = results_by_category[category]
        cat_total = len(cat_results)
        cat_hit1 = sum(1 for r in cat_results if r['hit@1'])
        cat_hit3 = sum(1 for r in cat_results if r['hit@3'])
        
        status = "✅" if cat_hit1/cat_total >= 0.8 else ("⚠️" if cat_hit1/cat_total >= 0.6 else "❌")
        print(f"   {status} {category}: {cat_hit1}/{cat_total} ({cat_hit1/cat_total*100:.0f}%)")
    
    # Show remaining failures
    failures = [r for r in all_results if not r['hit@1']]
    print(f"\n❌ REMAINING FAILURES ({len(failures)}):")
    for f in failures:
        in_top3 = "✓ in top3" if f['hit@3'] else "✗ NOT in top3"
        print(f"   • \"{f['query'][:40]}...\" → {f['top_result']} ({in_top3})")
    
    return all_results, results_by_category

if __name__ == "__main__":
    import os
    os.chdir('.')
    run_evaluation()
