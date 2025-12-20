"""
Full evaluation of Python Engine v3 on all Python codebases
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from python_search_engine import PythonSearchEngineV3, check_hit

import os
os.chdir('.')

print("=" * 70)
print("📊 PYTHON SEARCH ENGINE v3 - FULL EVALUATION")
print("=" * 70)

results_summary = {}

# CLICK
print("\n🐍 CLICK")
from click_test_suite import CLICK_GROUND_TRUTH
with open('results/click_summaries.json') as f:
    engine = PythonSearchEngineV3(json.load(f)['functions'])

hits = {'@1': 0, '@3': 0, '@5': 0}
for q, exp, cat in CLICK_GROUND_TRUTH:
    res = engine.search(q)
    if check_hit(res, exp, 1): hits['@1'] += 1
    if check_hit(res, exp, 3): hits['@3'] += 1
    if check_hit(res, exp, 5): hits['@5'] += 1

total = len(CLICK_GROUND_TRUTH)
print(f"  Hit@1: {hits['@1']}/{total} = {hits['@1']/total*100:.1f}%")
print(f"  Hit@3: {hits['@3']}/{total} = {hits['@3']/total*100:.1f}%")
results_summary['click'] = hits['@1']/total*100

# REQUESTS
print("\n🐍 REQUESTS")
from requests_test_suite import REQUESTS_GROUND_TRUTH
with open('results/requests_summaries.json') as f:
    engine = PythonSearchEngineV3(json.load(f)['functions'])

hits = {'@1': 0, '@3': 0, '@5': 0}
for q, exp, cat in REQUESTS_GROUND_TRUTH:
    res = engine.search(q)
    if check_hit(res, exp, 1): hits['@1'] += 1
    if check_hit(res, exp, 3): hits['@3'] += 1
    if check_hit(res, exp, 5): hits['@5'] += 1

total = len(REQUESTS_GROUND_TRUTH)
print(f"  Hit@1: {hits['@1']}/{total} = {hits['@1']/total*100:.1f}%")
print(f"  Hit@3: {hits['@3']}/{total} = {hits['@3']/total*100:.1f}%")
results_summary['requests'] = hits['@1']/total*100

# FLASK
print("\n🐍 FLASK")
from flask_test_suite import FLASK_GROUND_TRUTH
with open('results/flask_summaries.json') as f:
    engine = PythonSearchEngineV3(json.load(f)['functions'])

hits = {'@1': 0, '@3': 0, '@5': 0}
for q, exp, cat in FLASK_GROUND_TRUTH:
    res = engine.search(q)
    if check_hit(res, exp, 1): hits['@1'] += 1
    if check_hit(res, exp, 3): hits['@3'] += 1
    if check_hit(res, exp, 5): hits['@5'] += 1

total = len(FLASK_GROUND_TRUTH)
print(f"  Hit@1: {hits['@1']}/{total} = {hits['@1']/total*100:.1f}%")
print(f"  Hit@3: {hits['@3']}/{total} = {hits['@3']/total*100:.1f}%")
results_summary['flask'] = hits['@1']/total*100

# Summary
print("\n" + "=" * 70)
print("📊 COMPARISON: Original vs Python Engine v3")
print("=" * 70)

old = {'click': 60.0, 'requests': 68.0, 'flask': 64.0}

print("\n| Codebase | Original | v3      | Change  |")
print("|----------|----------|---------|---------|")
for name in ['click', 'requests', 'flask']:
    o = old[name]
    n = results_summary[name]
    diff = n - o
    sign = "+" if diff > 0 else ""
    print(f"| {name:8} | {o:7.1f}% | {n:6.1f}% | {sign}{diff:+.1f}%  |")

avg_old = sum(old.values()) / len(old)
avg_new = sum(results_summary.values()) / len(results_summary)
print(f"| {'AVERAGE':8} | {avg_old:7.1f}% | {avg_new:6.1f}% | {avg_new-avg_old:+.1f}%  |")
