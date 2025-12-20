"""
Evaluate Python Search with V2 Extraction + Summaries
======================================================

Run AFTER generate_summaries.py completes.

Usage:
    cd .
    python3 scripts/evaluate_python_v2.py flask

Compares: OLD system vs NEW system (with summaries)
"""

import json
import sys
from pathlib import Path
from dotenv import load_dotenv

# Setup paths
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from src.extractors.base import ExtractedFunction
from src.search.python_optimized import PythonOptimizedSearch, run_evaluation


def load_functions_with_summaries(codebase: str):
    """Load functions from v2 summaries file."""
    path = ROOT / f"results/{codebase}_v2_summaries.json"
    
    with open(path) as f:
        data = json.load(f)
    
    # Convert dicts back to ExtractedFunction objects
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
            is_static=fd.get('is_static', False),
            is_classmethod=fd.get('is_classmethod', False),
            is_property=fd.get('is_property', False),
            is_private=fd.get('is_private', False),
            is_dunder=fd.get('is_dunder', False),
            language=fd.get('language', 'python'),
            start_line=fd.get('start_line', 0),
            end_line=fd.get('end_line', 0),
            summary=fd.get('summary'),
        )
        functions.append(func)
    
    return functions, data


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 evaluate_python_v2.py <codebase>")
        sys.exit(1)
    
    codebase = sys.argv[1].lower()
    
    print("=" * 60)
    print(f"🧪 EVALUATING {codebase.upper()} - V2 System")
    print("=" * 60)
    
    # Load functions with summaries
    print(f"\n📦 Loading {codebase}_v2_summaries.json...")
    try:
        functions, data = load_functions_with_summaries(codebase)
    except FileNotFoundError:
        print(f"❌ File not found! Run generate_summaries.py first:")
        print(f"   python3 scripts/generate_summaries.py {codebase}")
        sys.exit(1)
    
    with_summary = sum(1 for f in functions if f.summary)
    print(f"   {len(functions)} functions, {with_summary} with summaries")
    
    # Build search engine
    print("\n🔧 Building search engine...")
    search = PythonOptimizedSearch(functions, embedding_provider="openai")
    
    # Load queries
    queries_path = ROOT / f"evals/{codebase}_queries.json"
    try:
        with open(queries_path) as f:
            queries = json.load(f)
    except FileNotFoundError:
        print(f"❌ No queries found at {queries_path}")
        sys.exit(1)
    
    print(f"\n📋 {len(queries)} queries loaded")
    
    # Evaluate
    print("\n" + "=" * 60)
    print("📊 EVALUATION")
    print("=" * 60 + "\n")
    
    results = run_evaluation(search, queries, verbose=True)
    
    # Load old results for comparison
    old_path = ROOT / f"results/{codebase}_evaluation.json"
    try:
        with open(old_path) as f:
            old_data = json.load(f)
        old_hit = old_data.get('hit@1', 0) * 100
    except:
        old_hit = None
    
    # Summary
    print("\n" + "=" * 60)
    print("📈 COMPARISON")
    print("=" * 60)
    if old_hit:
        print(f"   OLD system: {old_hit:.1f}%")
    print(f"   NEW system: {results['hit_at_1']*100:.1f}%")
    if old_hit:
        diff = results['hit_at_1']*100 - old_hit
        emoji = "📈" if diff > 0 else "📉" if diff < 0 else "➡️"
        print(f"   {emoji} Difference: {diff:+.1f}%")


if __name__ == "__main__":
    main()
