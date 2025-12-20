"""
Generate LLM Summaries for Python Functions
============================================

This script generates natural language summaries for all extracted functions.
Run this locally - takes ~10-15 mins for Flask (356 functions).

Usage:
    cd .
    python3 scripts/generate_summaries.py flask

Output: results/{codebase}_v2_summaries.json
"""

import json
import sys
import os
import time
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Setup paths
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from src.extractors import extract_repo

# Config
REPOS = {
    "flask": ROOT / "test_repos/flask/src/flask",
    "requests": ROOT / "test_repos/requests/src/requests",
    "click": ROOT / "test_repos/click/src/click",
}

SUMMARY_PROMPT = """You are a code documentation expert. Generate a concise 1-2 sentence summary of what this Python function/method does.

Focus on:
- What the function DOES (not how)
- Key parameters and return values
- When/why you'd use it

{class_context}

Code:
```python
{code}
```

Summary (1-2 sentences, no markdown):"""


def generate_summary(client: OpenAI, func: dict) -> str:
    """Generate summary for a single function."""
    
    # Build class context if method
    class_context = ""
    if func.get('class_name') and func.get('class_docstring'):
        class_context = f"This is a method of class `{func['class_name']}`: {func['class_docstring'][:200]}"
    
    # Build code snippet (truncate if too long)
    code = func.get('code', func.get('signature', ''))
    if len(code) > 1500:
        code = code[:1500] + "\n# ... (truncated)"
    
    prompt = SUMMARY_PROMPT.format(
        class_context=class_context,
        code=code
    )
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"      ⚠️ Error: {e}")
        return ""


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate_summaries.py <codebase>")
        print(f"Available: {', '.join(REPOS.keys())}")
        sys.exit(1)
    
    codebase = sys.argv[1].lower()
    if codebase not in REPOS:
        print(f"❌ Unknown codebase: {codebase}")
        print(f"Available: {', '.join(REPOS.keys())}")
        sys.exit(1)
    
    repo_path = REPOS[codebase]
    
    print("=" * 60)
    print(f"🚀 GENERATING SUMMARIES FOR {codebase.upper()}")
    print("=" * 60)
    
    # Extract functions
    print(f"\n📦 Extracting from {repo_path}...")
    functions = extract_repo(str(repo_path))
    print(f"   Found {len(functions)} functions")
    
    # Convert to dicts for JSON
    func_dicts = [f.to_dict() for f in functions]
    
    # Setup OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Generate summaries
    print(f"\n🧠 Generating summaries...")
    print(f"   This will take ~{len(functions) // 20} minutes\n")
    
    start_time = time.time()
    
    for i, func in enumerate(func_dicts):
        # Skip dunders (optional - they rarely help search)
        if func.get('is_dunder') and func['name'] not in ['__init__', '__call__']:
            func['summary'] = f"Dunder method {func['name']} for {func.get('class_name', 'module')}"
            continue
        
        # Generate summary
        summary = generate_summary(client, func)
        func['summary'] = summary
        
        # Progress
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            remaining = (len(func_dicts) - i - 1) / rate
            print(f"   [{i+1}/{len(func_dicts)}] {func['qualified_name'][:40]}...")
            print(f"       ETA: {remaining/60:.1f} minutes")
    
    # Save results
    output = {
        'codebase': codebase,
        'extraction_version': 'v2',
        'total': len(func_dicts),
        'with_summaries': sum(1 for f in func_dicts if f.get('summary')),
        'functions': func_dicts
    }
    
    output_path = ROOT / f"results/{codebase}_v2_summaries.json"
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    elapsed = time.time() - start_time
    print(f"\n✅ DONE in {elapsed/60:.1f} minutes!")
    print(f"📁 Saved to: {output_path}")
    print(f"📊 {output['with_summaries']}/{output['total']} functions have summaries")


if __name__ == "__main__":
    main()
