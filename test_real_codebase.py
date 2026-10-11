"""
CodeIntel REAL Search Quality Test
===================================
This is the REAL test - exactly how CodeIntel works:

1. Clone a real repo (or use local)
2. Parse with tree-sitter (extract functions)
3. Generate embeddings (raw vs NL description)
4. Test with HARD queries (ambiguous, no name hints)
5. Compare approaches

This simulates PRODUCTION behavior.
"""

import asyncio
import os
import json
import hashlib
import subprocess
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Tree-sitter imports
try:
    import tree_sitter_python as tspython
    import tree_sitter_javascript as tsjavascript
    import tree_sitter_typescript as tstypescript
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    print("⚠️  Tree-sitter not installed. Run:")
    print("   pip install tree-sitter tree-sitter-python tree-sitter-javascript tree-sitter-typescript")

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =============================================================================
# TREE-SITTER PARSER (Exactly like CodeIntel)
# =============================================================================

class CodeParser:
    """Parse code using tree-sitter - same as CodeIntel production."""
    
    def __init__(self):
        if not TREE_SITTER_AVAILABLE:
            raise RuntimeError("Tree-sitter not available")
        
        # Initialize parsers for each language
        self.parsers = {}
        self.languages = {}
        
        # Python
        self.languages['python'] = Language(tspython.language())
        self.parsers['python'] = Parser(self.languages['python'])
        
        # JavaScript  
        self.languages['javascript'] = Language(tsjavascript.language())
        self.parsers['javascript'] = Parser(self.languages['javascript'])
        
        # TypeScript
        self.languages['typescript'] = Language(tstypescript.language_typescript())
        self.parsers['typescript'] = Parser(self.languages['typescript'])
        
        # File extension mapping
        self.ext_to_lang = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
        }
    
    def get_language(self, file_path: str) -> Optional[str]:
        """Get language from file extension."""
        ext = Path(file_path).suffix.lower()
        return self.ext_to_lang.get(ext)
    
    def extract_functions(self, code: str, language: str, file_path: str = "") -> List[Dict]:
        """Extract functions/methods from code using tree-sitter."""
        if language not in self.parsers:
            return []
        
        parser = self.parsers[language]
        tree = parser.parse(bytes(code, 'utf8'))
        
        functions = []
        
        # Define node types to extract based on language
        if language == 'python':
            function_types = ['function_definition', 'class_definition']
        else:  # JavaScript/TypeScript
            function_types = [
                'function_declaration',
                'arrow_function', 
                'method_definition',
                'class_declaration',
                'function_expression'
            ]
        
        def traverse(node, parent_class=None):
            """Recursively traverse AST and extract functions."""
            
            if node.type in function_types:
                # Extract function name
                name = self._get_function_name(node, language)
                if name and not name.startswith('_'):  # Skip private/dunder
                    
                    # Get the code
                    func_code = code[node.start_byte:node.end_byte]
                    
                    # Get docstring/comments
                    docstring = self._extract_docstring(node, code, language)
                    
                    # Get parameters
                    params = self._extract_parameters(node, language)
                    
                    functions.append({
                        'name': name,
                        'full_name': f"{parent_class}.{name}" if parent_class else name,
                        'type': node.type,
                        'code': func_code,
                        'docstring': docstring,
                        'parameters': params,
                        'file_path': file_path,
                        'language': language,
                        'start_line': node.start_point[0] + 1,
                        'end_line': node.end_point[0] + 1,
                    })
                    
                    # If it's a class, traverse children with class context
                    if node.type in ['class_definition', 'class_declaration']:
                        for child in node.children:
                            traverse(child, parent_class=name)
                        return
            
            # Traverse children
            for child in node.children:
                traverse(child, parent_class)
        
        traverse(tree.root_node)
        return functions
    
    def _get_function_name(self, node, language: str) -> Optional[str]:
        """Extract function/class name from AST node."""
        for child in node.children:
            if child.type == 'identifier' or child.type == 'name':
                return child.text.decode('utf8')
            if child.type == 'property_identifier':
                return child.text.decode('utf8')
        return None
    
    def _extract_docstring(self, node, code: str, language: str) -> str:
        """Extract docstring or leading comment."""
        if language == 'python':
            # Look for expression_statement -> string as first child of body
            for child in node.children:
                if child.type == 'block':
                    for block_child in child.children:
                        if block_child.type == 'expression_statement':
                            for expr_child in block_child.children:
                                if expr_child.type == 'string':
                                    doc = code[expr_child.start_byte:expr_child.end_byte]
                                    # Clean up the docstring
                                    return doc.strip('"""').strip("'''").strip()
                        break  # Only check first statement
        else:
            # JS/TS - look for leading comment
            start_line = node.start_point[0]
            lines = code.split('\n')
            if start_line > 0:
                prev_line = lines[start_line - 1].strip()
                if prev_line.startswith('//') or prev_line.startswith('/*'):
                    return prev_line.lstrip('/*/ ').rstrip('*/ ')
        return ""
    
    def _extract_parameters(self, node, language: str) -> List[str]:
        """Extract parameter names from function."""
        params = []
        for child in node.children:
            if child.type in ['parameters', 'formal_parameters']:
                for param in child.children:
                    if param.type in ['identifier', 'name', 'typed_parameter', 'required_parameter']:
                        # Get the actual identifier
                        if param.type == 'identifier' or param.type == 'name':
                            params.append(param.text.decode('utf8'))
                        else:
                            # Look for identifier child
                            for p in param.children:
                                if p.type in ['identifier', 'name']:
                                    params.append(p.text.decode('utf8'))
                                    break
        return params


# =============================================================================
# CODEBASE SCANNER
# =============================================================================

class CodebaseScanner:
    """Scan a codebase and extract all functions."""
    
    IGNORE_DIRS = {
        'node_modules', 'venv', '.venv', '__pycache__', '.git',
        'dist', 'build', '.next', 'coverage', '.pytest_cache',
        'env', '.env', 'vendor', 'target'
    }
    
    IGNORE_FILES = {
        'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
        '.DS_Store', 'Thumbs.db'
    }
    
    def __init__(self, parser: CodeParser):
        self.parser = parser
    
    def scan_directory(self, root_path: str, max_files: int = 100) -> List[Dict]:
        """Scan directory and extract all functions."""
        all_functions = []
        files_processed = 0
        
        root = Path(root_path)
        
        for file_path in root.rglob('*'):
            if files_processed >= max_files:
                break
                
            # Skip ignored directories
            if any(ignored in file_path.parts for ignored in self.IGNORE_DIRS):
                continue
            
            # Skip non-files and ignored files
            if not file_path.is_file():
                continue
            if file_path.name in self.IGNORE_FILES:
                continue
            
            # Check if we can parse this file
            language = self.parser.get_language(str(file_path))
            if not language:
                continue
            
            try:
                code = file_path.read_text(encoding='utf-8', errors='ignore')
                
                # Skip very large files
                if len(code) > 100000:  # 100KB
                    continue
                
                functions = self.parser.extract_functions(
                    code, 
                    language,
                    str(file_path.relative_to(root))
                )
                all_functions.extend(functions)
                files_processed += 1
                
            except Exception as e:
                print(f"  ⚠️ Error parsing {file_path}: {e}")
                continue
        
        return all_functions


# =============================================================================
# EMBEDDING & SEARCH ENGINE
# =============================================================================

class SearchEngine:
    """Simulates CodeIntel's search engine for testing."""
    
    def __init__(self):
        self.functions = []
        self.embeddings = {}  # approach -> func_id -> embedding
        self.descriptions = {}  # func_id -> NL description
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding from OpenAI."""
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:8000]
        )
        return response.data[0].embedding
    
    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity."""
        a, b = np.array(a), np.array(b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    
    async def generate_description(self, func: Dict) -> str:
        """Generate NL description using LLM."""
        # Truncate code if too long
        code = func['code'][:1500]
        
        prompt = f"""Describe what this {func['language']} code does in 2-3 sentences.
Focus on:
1. WHAT it does (functionality/purpose)
2. WHY someone would use it (use case)
3. Key operations it performs

Be specific about the domain (auth, data processing, API, etc.)

```{func['language']}
{code}
```

Description:"""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0
        )
        return response.choices[0].message.content.strip()
    
    def get_func_id(self, func: Dict) -> str:
        """Generate unique ID for a function."""
        unique_str = f"{func['file_path']}:{func['name']}:{func['start_line']}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:12]
    
    async def index_functions(self, functions: List[Dict], approaches: List[str]):
        """Index functions using different approaches."""
        self.functions = functions
        
        print(f"\n📚 Indexing {len(functions)} functions...")
        
        # Generate descriptions for all functions first (needed for NL approaches)
        if any(a != 'RAW_CODE' for a in approaches):
            print("\n🤖 Generating NL descriptions...")
            for i, func in enumerate(functions):
                func_id = self.get_func_id(func)
                desc = await self.generate_description(func)
                self.descriptions[func_id] = desc
                if (i + 1) % 10 == 0:
                    print(f"   Generated {i + 1}/{len(functions)} descriptions")
            print(f"   ✅ All {len(functions)} descriptions generated")
        
        # Generate embeddings for each approach
        for approach in approaches:
            print(f"\n📊 Generating {approach} embeddings...")
            self.embeddings[approach] = {}
            
            for i, func in enumerate(functions):
                func_id = self.get_func_id(func)
                text = self._get_embedding_text(func, approach)
                embedding = await self.get_embedding(text)
                self.embeddings[approach][func_id] = embedding
                
                if (i + 1) % 20 == 0:
                    print(f"   Embedded {i + 1}/{len(functions)}")
            
            print(f"   ✅ {approach}: {len(functions)} embeddings")
    
    def _get_embedding_text(self, func: Dict, approach: str) -> str:
        """Get text to embed based on approach."""
        func_id = self.get_func_id(func)
        
        if approach == 'RAW_CODE':
            # Current CodeIntel approach
            return f"Function: {func['name']}\nType: {func['type']}\n\n{func['code'][:1000]}"
        
        elif approach == 'NL_DESCRIPTION':
            # Pure NL description
            return self.descriptions.get(func_id, "")
        
        elif approach == 'HYBRID_V1':
            # Description + function signature
            desc = self.descriptions.get(func_id, "")
            params = ", ".join(func['parameters']) if func['parameters'] else "none"
            return f"{desc}\n\nFunction: {func['name']}\nParameters: {params}"
        
        elif approach == 'HYBRID_V2':
            # Description + code keywords + docstring
            desc = self.descriptions.get(func_id, "")
            docstring = func.get('docstring', '')
            
            return f"""{desc}

Original docstring: {docstring if docstring else 'None'}
Function name: {func['name']}
File: {func['file_path']}
Language: {func['language']}"""
        
        elif approach == 'CHUNKED':
            # What Greptile does - chunk code + add context
            desc = self.descriptions.get(func_id, "")
            code_preview = func['code'][:500]
            
            return f"""Summary: {desc}

Code preview:
```{func['language']}
{code_preview}
```

Search keywords: {func['name'].replace('_', ' ')}, {func['language']}"""
        
        return func['code'][:1000]
    
    async def search(self, query: str, approach: str, top_k: int = 5) -> List[Tuple[Dict, float]]:
        """Search for functions matching query."""
        query_embedding = await self.get_embedding(query)
        
        scores = []
        for func in self.functions:
            func_id = self.get_func_id(func)
            if func_id in self.embeddings[approach]:
                score = self.cosine_similarity(query_embedding, self.embeddings[approach][func_id])
                scores.append((func, score))
        
        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# =============================================================================
# HARD TEST QUERIES
# =============================================================================

# These are HARD queries - no obvious function name hints
# Format: (query, keywords_that_should_match, description)
HARD_TEST_QUERIES = [
    # Authentication & Security
    ("how do users log in to the system", ["auth", "login", "user", "password", "credential"], "Auth flow"),
    ("verify if someone has permission to access this", ["permission", "access", "authorize", "role", "check"], "Authorization"),
    ("encrypt sensitive data before storing", ["encrypt", "hash", "password", "secure", "crypto"], "Encryption"),
    ("check if the session is still valid", ["session", "token", "expire", "valid", "jwt"], "Session validation"),
    
    # Data Processing
    ("read data from external source and transform it", ["fetch", "load", "parse", "transform", "import"], "Data ingestion"),
    ("filter and sort the results before returning", ["filter", "sort", "query", "results", "list"], "Data filtering"),
    ("combine multiple data sources together", ["merge", "join", "combine", "aggregate", "concat"], "Data merging"),
    ("save changes to persistent storage", ["save", "store", "write", "persist", "database", "update"], "Data persistence"),
    
    # API & HTTP
    ("handle incoming web requests", ["request", "handler", "route", "endpoint", "api", "http"], "Request handling"),
    ("send data to external service", ["send", "post", "request", "api", "client", "http"], "API calls"),
    ("validate input from user before processing", ["validate", "input", "check", "sanitize", "schema"], "Input validation"),
    ("return appropriate error response", ["error", "exception", "response", "handle", "catch"], "Error handling"),
    
    # Async & Performance
    ("run multiple operations at the same time", ["async", "parallel", "concurrent", "await", "promise"], "Concurrency"),
    ("cache results to avoid repeated computation", ["cache", "memo", "store", "redis", "memory"], "Caching"),
    ("retry failed operation with delay", ["retry", "backoff", "attempt", "fail", "recover"], "Retry logic"),
    ("limit how fast requests can be made", ["rate", "limit", "throttle", "quota", "restrict"], "Rate limiting"),
    
    # File & Storage  
    ("upload file to cloud storage", ["upload", "file", "s3", "storage", "blob", "cloud"], "File upload"),
    ("read configuration from file", ["config", "settings", "load", "read", "env", "yaml"], "Config loading"),
    ("generate unique identifier for record", ["uuid", "id", "generate", "unique", "random"], "ID generation"),
    ("compress data to reduce size", ["compress", "zip", "gzip", "reduce", "encode"], "Compression"),
    
    # Business Logic
    ("calculate final price with discounts", ["price", "discount", "calculate", "total", "cost"], "Pricing"),
    ("send notification to user", ["notify", "email", "sms", "push", "alert", "message"], "Notifications"),
    ("schedule task to run later", ["schedule", "job", "cron", "queue", "task", "delay"], "Task scheduling"),
    ("track user activity for analytics", ["track", "analytics", "event", "log", "metric"], "Analytics"),
]


# =============================================================================
# TEST RUNNER
# =============================================================================

@dataclass
class SearchResult:
    query: str
    approach: str
    expected_keywords: List[str]
    top_results: List[Tuple[str, str, float]]  # (name, file, score)
    relevance_score: float  # How relevant were the results
    hit_in_top1: bool
    hit_in_top3: bool
    hit_in_top5: bool


def check_relevance(func: Dict, keywords: List[str]) -> bool:
    """Check if function is relevant based on keywords."""
    # Check function name
    name_lower = func['name'].lower()
    for kw in keywords:
        if kw in name_lower:
            return True
    
    # Check code content
    code_lower = func['code'].lower()
    matches = sum(1 for kw in keywords if kw in code_lower)
    return matches >= 2  # At least 2 keyword matches in code


async def run_real_test(repo_path: str, max_functions: int = 50):
    """Run the real codebase test."""
    
    print("=" * 70)
    print("CODEINTEL REAL CODEBASE SEARCH QUALITY TEST")
    print("=" * 70)
    print(f"\nRepo: {repo_path}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize parser
    if not TREE_SITTER_AVAILABLE:
        print("\n❌ Tree-sitter not available. Installing...")
        subprocess.run([
            "pip", "install", "tree-sitter", 
            "tree-sitter-python", "tree-sitter-javascript", "tree-sitter-typescript"
        ], check=True)
        print("Please restart the script.")
        return
    
    parser = CodeParser()
    scanner = CodebaseScanner(parser)
    
    # Scan codebase
    print(f"\n📂 Scanning codebase...")
    functions = scanner.scan_directory(repo_path, max_files=100)
    print(f"   Found {len(functions)} functions")
    
    if len(functions) == 0:
        print("❌ No functions found. Check the repo path.")
        return
    
    # Limit functions for testing
    if len(functions) > max_functions:
        # Take a diverse sample
        functions = functions[:max_functions]
        print(f"   Using {len(functions)} functions for test")
    
    # Show some extracted functions
    print(f"\n📋 Sample functions extracted:")
    for func in functions[:5]:
        print(f"   • {func['name']} ({func['file_path']}) - {len(func['code'])} chars")
    
    # Initialize search engine
    engine = SearchEngine()
    
    # Approaches to test
    approaches = ['RAW_CODE', 'NL_DESCRIPTION', 'HYBRID_V1', 'HYBRID_V2', 'CHUNKED']
    
    # Index all functions
    await engine.index_functions(functions, approaches)
    
    # Run test queries
    print("\n" + "=" * 70)
    print("RUNNING SEARCH TESTS")
    print("=" * 70)
    
    results = {approach: [] for approach in approaches}
    
    # Select subset of queries for testing
    test_queries = HARD_TEST_QUERIES[:12]  # Use 12 queries
    
    for query, keywords, description in test_queries:
        print(f"\n🔍 Query: \"{query}\"")
        print(f"   Keywords: {keywords}")
        
        for approach in approaches:
            search_results = await engine.search(query, approach, top_k=5)
            
            # Check relevance of results
            hits = [check_relevance(func, keywords) for func, score in search_results]
            
            result = SearchResult(
                query=query,
                approach=approach,
                expected_keywords=keywords,
                top_results=[(f['name'], f['file_path'], s) for f, s in search_results],
                relevance_score=sum(hits) / len(hits) if hits else 0,
                hit_in_top1=hits[0] if hits else False,
                hit_in_top3=any(hits[:3]) if hits else False,
                hit_in_top5=any(hits[:5]) if hits else False,
            )
            results[approach].append(result)
        
        # Show results for this query
        print(f"\n   Results comparison:")
        for approach in approaches:
            r = results[approach][-1]
            top_name = r.top_results[0][0] if r.top_results else "N/A"
            top_score = r.top_results[0][2] if r.top_results else 0
            hit = "✅" if r.hit_in_top1 else "❌"
            print(f"   {approach:<15} → {top_name:<25} (score: {top_score:.4f}) {hit}")
    
    # Analyze results
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    
    print(f"\n{'Approach':<18} {'Top-1':<10} {'Top-3':<10} {'Top-5':<10} {'Avg Score':<12} {'Relevance':<10}")
    print("-" * 70)
    
    summary = {}
    for approach in approaches:
        approach_results = results[approach]
        
        top1_hits = sum(1 for r in approach_results if r.hit_in_top1)
        top3_hits = sum(1 for r in approach_results if r.hit_in_top3)
        top5_hits = sum(1 for r in approach_results if r.hit_in_top5)
        
        avg_score = np.mean([r.top_results[0][2] for r in approach_results if r.top_results])
        avg_relevance = np.mean([r.relevance_score for r in approach_results])
        
        total = len(approach_results)
        
        summary[approach] = {
            'top1': top1_hits / total,
            'top3': top3_hits / total,
            'top5': top5_hits / total,
            'avg_score': avg_score,
            'avg_relevance': avg_relevance,
        }
        
        print(f"{approach:<18} {top1_hits}/{total:<7} {top3_hits}/{total:<7} {top5_hits}/{total:<7} {avg_score:<12.4f} {avg_relevance:.2%}")
    
    # Find winner
    best_approach = max(summary.keys(), key=lambda a: (summary[a]['top1'], summary[a]['avg_score']))
    baseline = summary['RAW_CODE']
    best = summary[best_approach]
    
    print("\n" + "=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)
    
    print(f"\n🏆 Best approach: {best_approach}")
    print(f"   Top-1 accuracy: {best['top1']:.1%}")
    print(f"   Average score: {best['avg_score']:.4f}")
    
    if best_approach != 'RAW_CODE':
        improvement = best['top1'] - baseline['top1']
        score_improvement = best['avg_score'] - baseline['avg_score']
        print(f"\n📈 Improvement over RAW_CODE:")
        print(f"   Top-1 accuracy: {improvement:+.1%}")
        print(f"   Average score: {score_improvement:+.4f}")
    
    # Save detailed results
    output = {
        'timestamp': datetime.now().isoformat(),
        'repo_path': repo_path,
        'num_functions': len(functions),
        'num_queries': len(test_queries),
        'approaches': approaches,
        'summary': summary,
        'descriptions': engine.descriptions,
        'detailed_results': {
            approach: [
                {
                    'query': r.query,
                    'keywords': r.expected_keywords,
                    'top_results': r.top_results,
                    'hit_in_top1': r.hit_in_top1,
                    'relevance_score': r.relevance_score,
                }
                for r in results[approach]
            ]
            for approach in approaches
        }
    }
    
    os.makedirs('results', exist_ok=True)
    filename = f"results/real_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\n💾 Detailed results saved to: {filename}")
    print("\n✅ Test complete!")
    
    return summary


# =============================================================================
# MAIN
# =============================================================================

async def main():
    """Main entry point."""
    import sys
    
    # Default to CodeIntel repo or accept argument
    if len(sys.argv) > 1:
        repo_path = sys.argv[1]
    else:
        # Try to find CodeIntel repo
        possible_paths = [
            "../opencodeintel/backend",
            "../opencodeintel",
            os.getcwd(),
        ]
        
        repo_path = None
        for path in possible_paths:
            if os.path.exists(path):
                repo_path = path
                break
        
        if not repo_path:
            print("Usage: python test_real_codebase.py <repo_path>")
            print("Example: python test_real_codebase.py /path/to/your/repo")
            return
    
    await run_real_test(repo_path, max_functions=40)


if __name__ == "__main__":
    print("\n🧪 CodeIntel Real Codebase Test")
    print("================================\n")
    asyncio.run(main())
