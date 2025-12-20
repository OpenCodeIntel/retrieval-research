"""
Evaluate Python Search Engine v2 on all Python codebases
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from python_search_engine import PythonSearchEngineV2, check_hit

def run_evaluation(summaries_file, test_suite_module, name):
    """Run evaluation on a Python codebase"""
    
    with open(summaries_file) as f:
        data = json.load(f)
    
    functions = data['functions']
    engine = PythonSearchEngineV2(functions)
    
    # Import ground truth
    exec(f"from {test_suite_module} import {test_suite_module.upper().replace('_TEST_SUITE', '')}_GROUND_TRUTH as GT", globals())
    ground_truth = GT
    
    results_by_cat = defaultdict(list)
    all_results = []
    
    for query, expected, category in ground_truth:
        results = engine.search(query, top_k=10)
        hit1 = check_hit(results, expected, 1)
        hit3 = check_hit(results, expected, 3)
        hit5 = check_hit(results, expected, 5)
        
        result = {
            'query': query, 'expected': expected, 'category': category,
            'hit@1': hit1, 'hit@3': hit3, 'hit@5': hit5,
            'top_result': results[0][0]['name'],
            'top_3': [r[0]['name'] for r in results[:3]],
        }
        all_results.append(result)
        results_by_cat[category].append(result)
    
    return all_results, results_by_cat


if __name__ == "__main__":
    import os
    os.chdir('.')
    
    print("=" * 70)
    print("📊 PYTHON SEARCH ENGINE v2 - FULL EVALUATION")
    print("=" * 70)
    
    # Click evaluation
    print("\n" + "=" * 50)
    print("🐍 CLICK (CLI Framework)")
    print("=" * 50)
    
    from click_test_suite import CLICK_GROUND_TRUTH
    
    with open('results/click_summaries.json') as f:
        click_data = json.load(f)
    
    engine = PythonSearchEngineV2(click_data['functions'])
    
    click_results = []
    for query, expected, category in CLICK_GROUND_TRUTH:
        results = engine.search(query, top_k=10)
        hit1 = check_hit(results, expected, 1)
        click_results.append({'hit@1': hit1, 'hit@3': check_hit(results, expected, 3)})
    
    hit1 = sum(1 for r in click_results if r['hit@1'])
    hit3 = sum(1 for r in click_results if r['hit@3'])
    total = len(click_results)
    
    print(f"Hit@1: {hit1}/{total} = {hit1/total*100:.1f}%")
    print(f"Hit@3: {hit3}/{total} = {hit3/total*100:.1f}%")
    
    # Requests evaluation
    print("\n" + "=" * 50)
    print("🐍 REQUESTS (HTTP Library)")
    print("=" * 50)
    
    from requests_test_suite import REQUESTS_GROUND_TRUTH
    
    with open('results/requests_summaries.json') as f:
        requests_data = json.load(f)
    
    engine = PythonSearchEngineV2(requests_data['functions'])
    
    requests_results = []
    for query, expected, category in REQUESTS_GROUND_TRUTH:
        results = engine.search(query, top_k=10)
        hit1 = check_hit(results, expected, 1)
        requests_results.append({'hit@1': hit1, 'hit@3': check_hit(results, expected, 3)})
    
    hit1 = sum(1 for r in requests_results if r['hit@1'])
    hit3 = sum(1 for r in requests_results if r['hit@3'])
    total = len(requests_results)
    
    print(f"Hit@1: {hit1}/{total} = {hit1/total*100:.1f}%")
    print(f"Hit@3: {hit3}/{total} = {hit3/total*100:.1f}%")
    
    # Flask evaluation
    print("\n" + "=" * 50)
    print("🐍 FLASK (Web Framework)")
    print("=" * 50)
    
    from flask_test_suite import FLASK_GROUND_TRUTH
    
    with open('results/flask_summaries.json') as f:
        flask_data = json.load(f)
    
    engine = PythonSearchEngineV2(flask_data['functions'])
    
    flask_results = []
    for query, expected, category in FLASK_GROUND_TRUTH:
        results = engine.search(query, top_k=10)
        hit1 = check_hit(results, expected, 1)
        flask_results.append({'hit@1': hit1, 'hit@3': check_hit(results, expected, 3)})
    
    hit1 = sum(1 for r in flask_results if r['hit@1'])
    hit3 = sum(1 for r in flask_results if r['hit@3'])
    total = len(flask_results)
    
    print(f"Hit@1: {hit1}/{total} = {hit1/total*100:.1f}%")
    print(f"Hit@3: {hit3}/{total} = {hit3/total*100:.1f}%")
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 COMPARISON: Old Engine vs Python Engine v2")
    print("=" * 70)
    
    print("""
| Codebase | Old Hit@1 | New Hit@1 | Improvement |
|----------|-----------|-----------|-------------|""")
    
    old_scores = {'click': 60.0, 'requests': 68.0, 'flask': 64.0}
    
    for name, old in old_scores.items():
        if name == 'click':
            new = sum(1 for r in click_results if r['hit@1']) / len(click_results) * 100
        elif name == 'requests':
            new = sum(1 for r in requests_results if r['hit@1']) / len(requests_results) * 100
        else:
            new = sum(1 for r in flask_results if r['hit@1']) / len(flask_results) * 100
        
        diff = new - old
        sign = "+" if diff > 0 else ""
        print(f"| {name:8} | {old:8.1f}% | {new:8.1f}% | {sign}{diff:+.1f}%      |")
