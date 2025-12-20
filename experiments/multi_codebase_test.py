"""
Universal Code Search Testing Framework
========================================
Tests code search on multiple codebases:
- Zustand (state management)
- Express (web framework)
- Lodash (utility library)
"""

import json
import os
import re
from pathlib import Path
from collections import defaultdict

# =============================================================================
# Function Extractor (Simple regex-based for speed)
# =============================================================================

def extract_js_functions(file_path: str) -> list:
    """Extract function definitions from JS/TS files."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        return []
    
    functions = []
    
    # Pattern 1: function name() {}
    pattern1 = r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*\{'
    
    # Pattern 2: const/let/var name = function() {}
    pattern2 = r'(?:const|let|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(?:async\s+)?function'
    
    # Pattern 3: const/let/var name = () => {}
    pattern3 = r'(?:const|let|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>'
    
    # Pattern 4: name: function() {} (object methods)
    pattern4 = r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(?:async\s+)?function\s*\('
    
    # Pattern 5: exports.name = function
    pattern5 = r'exports\.([a-zA-Z_][a-zA-Z0-9_]*)\s*='
    
    # Pattern 6: module.exports.name = function
    pattern6 = r'module\.exports\.([a-zA-Z_][a-zA-Z0-9_]*)\s*='
    
    for pattern in [pattern1, pattern2, pattern3, pattern4, pattern5, pattern6]:
        matches = re.findall(pattern, content)
        for name in matches:
            if len(name) > 1 and name not in ['if', 'for', 'while', 'switch', 'catch']:
                # Get surrounding context
                idx = content.find(name)
                start = max(0, idx - 50)
                end = min(len(content), idx + 200)
                context = content[start:end]
                
                functions.append({
                    'name': name,
                    'file': file_path,
                    'code': context,
                })
    
    return functions


def scan_codebase(repo_path: str, extensions: list = ['.js', '.ts', '.mjs']) -> list:
    """Scan a codebase and extract all functions."""
    all_functions = []
    seen_names = set()
    
    for root, dirs, files in os.walk(repo_path):
        # Skip node_modules, test files, etc.
        dirs[:] = [d for d in dirs if d not in ['node_modules', '.git', 'test', 'tests', '__tests__', 'dist', 'build']]
        
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                file_path = os.path.join(root, file)
                funcs = extract_js_functions(file_path)
                
                for func in funcs:
                    if func['name'] not in seen_names:
                        seen_names.add(func['name'])
                        all_functions.append(func)
    
    return all_functions


# =============================================================================
# Test Cases for Different Codebases
# =============================================================================

EXPRESS_QUERIES = [
    # Routing
    ("create a new route", ["Router", "route", "get", "post"]),
    ("handle GET request", ["get", "route"]),
    ("handle POST request", ["post", "route"]),
    ("add middleware to app", ["use", "middleware"]),
    ("parse JSON body", ["json", "bodyParser"]),
    ("parse URL encoded data", ["urlencoded"]),
    ("serve static files", ["static", "serveStatic"]),
    ("set response header", ["set", "header", "setHeader"]),
    ("send JSON response", ["json", "send"]),
    ("redirect to another URL", ["redirect", "location"]),
    ("render a view template", ["render", "view"]),
    ("handle errors", ["error", "errorHandler"]),
    ("get request parameters", ["param", "params"]),
    ("get query string", ["query"]),
    ("set cookie", ["cookie"]),
    ("create express application", ["express", "createApplication"]),
    ("listen on port", ["listen"]),
    ("configure app settings", ["set", "settings"]),
    ("enable trust proxy", ["trust", "proxy"]),
    ("handle all HTTP methods", ["all", "route"]),
]

LODASH_QUERIES = [
    # Array operations
    ("get first element of array", ["first", "head"]),
    ("get last element of array", ["last"]),
    ("flatten nested array", ["flatten", "flattenDeep"]),
    ("remove duplicates from array", ["uniq", "unique"]),
    ("sort array of objects", ["sortBy", "orderBy"]),
    ("filter array elements", ["filter"]),
    ("map over array", ["map"]),
    ("reduce array to value", ["reduce"]),
    ("find element in array", ["find", "findIndex"]),
    ("chunk array into groups", ["chunk"]),
    
    # Object operations
    ("merge objects together", ["merge", "assign"]),
    ("pick specific properties", ["pick"]),
    ("omit specific properties", ["omit"]),
    ("get nested property value", ["get"]),
    ("set nested property value", ["set"]),
    ("clone object deeply", ["cloneDeep", "clone"]),
    ("check if object is empty", ["isEmpty"]),
    ("get all object keys", ["keys"]),
    ("get all object values", ["values"]),
    
    # String operations  
    ("convert to camel case", ["camelCase"]),
    ("convert to snake case", ["snakeCase"]),
    ("capitalize first letter", ["capitalize", "upperFirst"]),
    ("truncate long string", ["truncate"]),
    ("escape HTML characters", ["escape"]),
    
    # Utility
    ("debounce function calls", ["debounce"]),
    ("throttle function calls", ["throttle"]),
    ("create unique ID", ["uniqueId"]),
    ("check if value is null", ["isNull", "isNil"]),
    ("check if value is array", ["isArray"]),
]

# =============================================================================
# Save for future use
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("📦 MULTI-CODEBASE TEST FRAMEWORK")
    print("=" * 70)
    
    repos = {
        'express': 'test_repos/express',
        'lodash': 'test_repos/lodash',
    }
    
    for name, path in repos.items():
        print(f"\n🔍 Scanning {name}...")
        if os.path.exists(path):
            funcs = scan_codebase(path)
            print(f"   Found {len(funcs)} functions")
            
            # Save extracted functions
            output_file = f'results/{name}_functions.json'
            with open(output_file, 'w') as f:
                json.dump({'repo': name, 'functions': funcs}, f, indent=2)
            print(f"   Saved to {output_file}")
        else:
            print(f"   ❌ Path not found: {path}")
    
    print("\n✅ Done! Ready for testing.")
