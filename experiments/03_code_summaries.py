"""
Experiment 03: LLM-Generated Code Summaries
============================================
Day 2 - Part 2 of CodeIntel Research

Hypothesis: Embedding natural language descriptions of code 
(instead of raw code) will dramatically improve search accuracy.

Why? User queries are natural language. Code is syntax.
LLM summaries bridge this gap.

This is what Greptile does - validated with $25M funding.

Target: >80% Hit@1 (up from 71.4% hybrid)
"""

import asyncio
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

from openai import OpenAI

# Initialize OpenAI client (using GPT-4 for summaries)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

print(f"OpenAI Key: {os.getenv('OPENAI_API_KEY')[:20]}...")


# =============================================================================
# SUMMARY GENERATION
# =============================================================================

SUMMARY_PROMPT = """You are a code documentation expert. Your job is to write natural language descriptions that help developers FIND this code when searching.

Given this TypeScript function from the Zustand state management library:

**File:** {file_path}
**Function Name:** {func_name}

```typescript
{code}
```

Write a 2-3 sentence description that:
1. Explains what this function DOES (not how it's implemented)
2. Describes WHEN a developer would use it
3. Uses natural, searchable language (think: what would someone type to find this?)

Focus on the PURPOSE and USE CASE, not implementation details.

Examples of good descriptions:
- "Persists store state to localStorage or sessionStorage. Used when you need state to survive page refreshes. Handles serialization and deserialization automatically."
- "Creates a new Zustand store with the given initial state and actions. This is the main entry point for setting up state management in your app."

Write ONLY the description, nothing else. No markdown, no quotes."""


async def generate_summary(func: Dict) -> str:
    """Generate a natural language summary for a function using GPT-4."""
    
    prompt = SUMMARY_PROMPT.format(
        file_path=Path(func['file']).name,
        func_name=func['name'],
        code=func['code'][:1500]  # Limit code length
    )
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cheap, good enough for summaries
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"   ⚠️ Error generating summary for {func['name']}: {e}")
        # Fallback: use function name as description
        return f"Function {func['name']} from Zustand library."


async def generate_all_summaries(functions: List[Dict]) -> List[Dict]:
    """Generate summaries for all functions."""
    print(f"\n📝 Generating summaries for {len(functions)} functions...")
    print("   (This will take ~2-3 minutes with rate limiting)\n")
    
    enriched = []
    
    for i, func in enumerate(functions):
        print(f"   [{i+1}/{len(functions)}] {func['name'][:30]}...", end=" ")
        
        summary = await generate_summary(func)
        
        enriched.append({
            **func,
            'summary': summary
        })
        
        print(f"✓")
        
        # Small delay to avoid rate limits
        if i < len(functions) - 1:
            await asyncio.sleep(0.5)
    
    print(f"\n✅ Generated {len(enriched)} summaries!")
    return enriched


# =============================================================================
# CODE PARSER (Same as before)
# =============================================================================

import tree_sitter_typescript as tstypescript
from tree_sitter import Language, Parser

TS_LANGUAGE = Language(tstypescript.language_typescript())
ts_parser = Parser(TS_LANGUAGE)


def extract_functions_from_file(file_path: str) -> List[Dict]:
    """Extract functions from TypeScript file."""
    try:
        code = Path(file_path).read_text()
    except:
        return []
    
    tree = ts_parser.parse(bytes(code, 'utf8'))
    functions = []
    
    def get_name(node):
        for child in node.children:
            if child.type in ['identifier', 'property_identifier']:
                return child.text.decode('utf8')
        return None
    
    def traverse(node):
        if node.type in ['function_declaration', 'arrow_function', 
                         'method_definition', 'variable_declarator']:
            name = get_name(node)
            if name and not name.startswith('_'):
                func_code = code[node.start_byte:node.end_byte]
                if len(func_code) > 20:
                    functions.append({
                        'name': name,
                        'code': func_code[:2000],
                        'file': str(file_path),
                        'type': node.type,
                    })
        
        for child in node.children:
            traverse(child)
    
    traverse(tree.root_node)
    return functions


def load_zustand_codebase() -> List[Dict]:
    """Load all functions from Zustand repo."""
    repo_path = Path(__file__).parent.parent / "test_repos" / "zustand" / "src"
    
    if not repo_path.exists():
        print(f"❌ Zustand repo not found at {repo_path}")
        return []
    
    all_functions = []
    
    for ts_file in repo_path.rglob("*.ts"):
        funcs = extract_functions_from_file(str(ts_file))
        all_functions.extend(funcs)
    
    print(f"📦 Loaded {len(all_functions)} functions from Zustand")
    return all_functions


# =============================================================================
# CHECKPOINT 1: Just generate summaries and save them
# =============================================================================

async def checkpoint_1_generate_summaries():
    """Generate and save summaries - CHECKPOINT 1"""
    print("=" * 70)
    print("EXPERIMENT 03 - CHECKPOINT 1: Generate Summaries")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load functions
    functions = load_zustand_codebase()
    if not functions:
        return None
    
    # Generate summaries
    enriched_functions = await generate_all_summaries(functions)
    
    # Save to file for reuse
    output_dir = Path(__file__).parent.parent / "results"
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / "exp03_summaries.json"
    
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'num_functions': len(enriched_functions),
            'functions': enriched_functions
        }, f, indent=2)
    
    print(f"\n💾 Summaries saved to: {output_file}")
    
    # Show a few examples
    print("\n" + "=" * 70)
    print("SAMPLE SUMMARIES (first 5)")
    print("=" * 70)
    
    for func in enriched_functions[:5]:
        print(f"\n📌 {func['name']} ({Path(func['file']).name})")
        print(f"   {func['summary']}")
    
    print("\n" + "=" * 70)
    print("✅ CHECKPOINT 1 COMPLETE!")
    print("=" * 70)
    print(f"\nGenerated {len(enriched_functions)} summaries.")
    print("Next: Run checkpoint_2 to test embedding strategies.")
    
    return enriched_functions


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    asyncio.run(checkpoint_1_generate_summaries())


# =============================================================================
# CHECKPOINT 2: Embedding Strategies & Evaluation
# =============================================================================

import voyageai
import numpy as np

# Initialize Voyage client
voyage_client = voyageai.AsyncClient(api_key=os.getenv("VOYAGE_API_KEY"))


# Ground truth (same as before)
GROUND_TRUTH = [
    ("update the store state", ["setState", "set"], "state"),
    ("get current state value", ["getState", "get"], "state"),
    ("listen for state changes", ["subscribe", "subscribeWithSelector"], "state"),
    ("create a new store", ["createStore", "create", "createStoreImpl"], "state"),
    ("save state to localStorage", ["persist", "setItem", "persistImpl"], "persist"),
    ("load saved state from storage", ["hydrate", "rehydrate", "getItem"], "persist"),
    ("clear persisted data", ["clearStorage", "removeItem"], "persist"),
    ("migrate old stored state version", ["migrate", "migration"], "persist"),
    ("custom storage adapter", ["createJSONStorage", "StateStorage"], "persist"),
    ("combine multiple stores", ["combine"], "middleware"),
    ("redux devtools integration", ["devtools"], "middleware"),
    ("use immer for immutable updates", ["immer"], "middleware"),
    ("subscribe to specific state slice", ["subscribeWithSelector"], "middleware"),
    ("use store in react component", ["useStore", "create", "useStoreWithEqualityFn"], "react"),
    ("shallow comparison for selectors", ["shallow", "useShallow"], "react"),
    ("avoid unnecessary rerenders", ["shallow", "useShallow", "equalityFn"], "react"),
    ("check if state objects are equal", ["shallow", "is", "Object.is"], "comparison"),
    ("merge new state with existing", ["merge", "assign", "Object.assign"], "state"),
    ("notify all listeners of change", ["listeners", "forEach", "notify"], "state"),
    ("handle storage not available", ["storage", "catch", "undefined"], "error"),
    ("server side rendering safe", ["ssrSafe", "skipHydration"], "ssr"),
]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors."""
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def check_hit(results: List[tuple], expected_names: List[str], k: int) -> bool:
    """Check if any expected function is in top-k results."""
    top_k_names = [r[0]['name'].lower() for r in results[:k]]
    return any(exp.lower() in name or name in exp.lower() 
               for exp in expected_names 
               for name in top_k_names)


class SummarySearchEngine:
    """Search engine using LLM-generated summaries."""
    
    def __init__(self, strategy: str = "summary_only"):
        """
        strategy options:
        - "summary_only": Embed just the summary
        - "summary_name": Embed "Function {name}: {summary}"
        - "summary_name_file": Embed "Function {name} ({file}): {summary}"
        """
        self.strategy = strategy
        self.functions = []
        self.embeddings = []
    
    def _get_text_for_embedding(self, func: Dict) -> str:
        """Get the text to embed based on strategy."""
        if self.strategy == "summary_only":
            return func['summary']
        elif self.strategy == "summary_name":
            return f"Function {func['name']}: {func['summary']}"
        elif self.strategy == "summary_name_file":
            file_name = Path(func['file']).name
            return f"Function {func['name']} ({file_name}): {func['summary']}"
        else:
            return func['summary']
    
    async def index(self, functions: List[Dict]):
        """Index functions with embeddings."""
        self.functions = functions
        
        # Prepare texts based on strategy
        texts = [self._get_text_for_embedding(f) for f in functions]
        
        # Embed in batches
        self.embeddings = []
        batch_size = 50
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            print(f"   Embedding batch {i//batch_size + 1}...")
            
            await asyncio.sleep(21)  # Voyage rate limit
            response = await voyage_client.embed(
                texts=batch,
                model="voyage-code-3",
                input_type="document"
            )
            self.embeddings.extend(response.embeddings)
        
        print(f"   Indexed {len(self.embeddings)} documents with strategy: {self.strategy}")
    
    async def search(self, query: str, top_k: int = 10) -> List[tuple]:
        """Search for functions matching query."""
        await asyncio.sleep(21)  # Rate limit
        response = await voyage_client.embed(
            texts=[query],
            model="voyage-code-3",
            input_type="query"
        )
        query_embedding = response.embeddings[0]
        
        # Calculate similarities
        scores = []
        for func, emb in zip(self.functions, self.embeddings):
            score = cosine_similarity(query_embedding, emb)
            scores.append((func, score))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
    
    async def batch_search(self, queries: List[str], top_k: int = 10) -> List[List[tuple]]:
        """Search multiple queries efficiently."""
        await asyncio.sleep(21)
        response = await voyage_client.embed(
            texts=queries,
            model="voyage-code-3",
            input_type="query"
        )
        query_embeddings = response.embeddings
        
        all_results = []
        for query_emb in query_embeddings:
            scores = []
            for func, emb in zip(self.functions, self.embeddings):
                score = cosine_similarity(query_emb, emb)
                scores.append((func, score))
            scores.sort(key=lambda x: x[1], reverse=True)
            all_results.append(scores[:top_k])
        
        return all_results


async def checkpoint_2_evaluate():
    """Evaluate different embedding strategies - CHECKPOINT 2"""
    print("=" * 70)
    print("EXPERIMENT 03 - CHECKPOINT 2: Evaluate Strategies")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load summaries from checkpoint 1
    summaries_file = Path(__file__).parent.parent / "results" / "exp03_summaries.json"
    
    if not summaries_file.exists():
        print("❌ Summaries file not found! Run checkpoint_1 first.")
        return
    
    with open(summaries_file) as f:
        data = json.load(f)
    
    functions = data['functions']
    print(f"📦 Loaded {len(functions)} functions with summaries")
    
    # Strategies to test
    strategies = ["summary_only", "summary_name", "summary_name_file"]
    
    results = {}
    
    for strategy in strategies:
        print(f"\n{'─' * 60}")
        print(f"Testing Strategy: {strategy.upper()}")
        print(f"{'─' * 60}")
        
        # Create engine and index
        engine = SummarySearchEngine(strategy=strategy)
        await engine.index(functions)
        
        # Batch search all queries
        all_queries = [q[0] for q in GROUND_TRUTH]
        search_results = await engine.batch_search(all_queries, top_k=10)
        
        # Evaluate
        strategy_results = []
        for i, (query, expected, category) in enumerate(GROUND_TRUTH):
            res = search_results[i]
            
            hit_1 = check_hit(res, expected, 1)
            hit_3 = check_hit(res, expected, 3)
            hit_5 = check_hit(res, expected, 5)
            top_score = res[0][1] if res else 0
            top_result = res[0][0]['name'] if res else 'N/A'
            
            strategy_results.append({
                'query': query,
                'expected': expected,
                'category': category,
                'hit@1': hit_1,
                'hit@3': hit_3,
                'hit@5': hit_5,
                'top_score': top_score,
                'top_result': top_result,
            })
            
            status = "✅" if hit_1 else ("⚠️" if hit_3 else "❌")
            print(f"   {status} \"{query[:35]}...\" → {top_result}")
        
        # Calculate metrics
        total = len(strategy_results)
        metrics = {
            'hit@1': sum(r['hit@1'] for r in strategy_results) / total,
            'hit@3': sum(r['hit@3'] for r in strategy_results) / total,
            'hit@5': sum(r['hit@5'] for r in strategy_results) / total,
        }
        
        results[strategy] = {'metrics': metrics, 'details': strategy_results}
        print(f"\n   📊 {strategy}: Hit@1={metrics['hit@1']:.1%}, Hit@3={metrics['hit@3']:.1%}")
    
    # ==========================================================================
    # COMPARISON
    # ==========================================================================
    print("\n" + "=" * 70)
    print("COMPARISON: Summary Strategies vs Previous Best (Hybrid)")
    print("=" * 70)
    
    # Previous best from exp02
    prev_best = {'hit@1': 0.714, 'hit@3': 0.952, 'hit@5': 0.952}
    
    print(f"\n{'Strategy':<25} {'Hit@1':<10} {'Hit@3':<10} {'Hit@5':<10} {'vs Hybrid':<12}")
    print("─" * 67)
    print(f"{'hybrid-α0.7 (prev best)':<25} {prev_best['hit@1']:<10.1%} {prev_best['hit@3']:<10.1%} {prev_best['hit@5']:<10.1%} {'baseline':<12}")
    
    for name, data in sorted(results.items(), key=lambda x: x[1]['metrics']['hit@1'], reverse=True):
        m = data['metrics']
        diff = m['hit@1'] - prev_best['hit@1']
        diff_str = f"{diff:+.1%}"
        print(f"{name:<25} {m['hit@1']:<10.1%} {m['hit@3']:<10.1%} {m['hit@5']:<10.1%} {diff_str:<12}")
    
    # Find best
    best_name = max(results.keys(), key=lambda x: results[x]['metrics']['hit@1'])
    best = results[best_name]['metrics']
    
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    
    print(f"\n🏆 Best Strategy: {best_name}")
    print(f"   Hit@1: {best['hit@1']:.1%}")
    print(f"   Hit@3: {best['hit@3']:.1%}")
    print(f"   Hit@5: {best['hit@5']:.1%}")
    
    improvement = best['hit@1'] - prev_best['hit@1']
    print(f"\n📈 vs Previous Best (Hybrid): {improvement:+.1%}")
    
    # Decision
    print("\n" + "─" * 70)
    if best['hit@1'] >= 0.80:
        print("✅ TARGET ACHIEVED! >80% Hit@1")
        print("   LLM summaries significantly improve search quality!")
    elif best['hit@1'] > prev_best['hit@1']:
        print("⚠️  IMPROVEMENT over hybrid, but below 80% target")
    else:
        print("❌ NO IMPROVEMENT over hybrid approach")
    
    # Save results
    output = {
        'timestamp': datetime.now().isoformat(),
        'experiment': '03_code_summaries',
        'target': '>80% Hit@1',
        'strategies': list(results.keys()),
        'num_queries': len(GROUND_TRUTH),
        'results': results,
        'winner': best_name,
        'improvement_vs_hybrid': improvement,
        'previous_best': prev_best,
    }
    
    results_dir = Path(__file__).parent.parent / "results"
    filename = results_dir / f"exp03_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    def convert(obj):
        if isinstance(obj, (np.floating, float)):
            return float(obj)
        if isinstance(obj, (np.integer, int)):
            return int(obj)
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert(i) for i in obj]
        return obj
    
    with open(filename, 'w') as f:
        json.dump(convert(output), f, indent=2)
    
    print(f"\n💾 Results saved: {filename}")
    print("\n✅ CHECKPOINT 2 COMPLETE!")
    
    return results


# =============================================================================
# MAIN - Run checkpoint based on argument
# =============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "checkpoint2":
        asyncio.run(checkpoint_2_evaluate())
    else:
        asyncio.run(checkpoint_1_generate_summaries())


# =============================================================================
# CHECKPOINT 3: Hybrid + Summary FUSION
# =============================================================================
# 
# The insight: Hybrid and Summary are COMPLEMENTARY
# - Hybrid wins on exact keyword matches (4 queries)
# - Summary wins on concept understanding (2 queries)
# - Both hit on 11 queries
# 
# If we combine them: 11 + 4 + 2 = 17/21 = 81% Hit@1 (theoretical max)
#
# Strategy: Score fusion between hybrid search and summary search
# =============================================================================

async def checkpoint_3_fusion():
    """Combine Hybrid + Summary approaches - CHECKPOINT 3"""
    print("=" * 70)
    print("EXPERIMENT 03 - CHECKPOINT 3: Hybrid + Summary FUSION")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n💡 Insight: Hybrid and Summary are complementary!")
    print("   - Hybrid wins on keyword matches")
    print("   - Summary wins on concept understanding")
    print("   - Combining them should give us the best of both!\n")
    
    # Load summaries
    summaries_file = Path(__file__).parent.parent / "results" / "exp03_summaries.json"
    with open(summaries_file) as f:
        data = json.load(f)
    functions = data['functions']
    print(f"📦 Loaded {len(functions)} functions with summaries")
    
    # ==========================================================================
    # BUILD BOTH INDEXES
    # ==========================================================================
    
    print("\n" + "─" * 60)
    print("Building indexes...")
    print("─" * 60)
    
    # 1. Summary index (embed summaries)
    print("\n📝 Building SUMMARY index...")
    summary_engine = SummarySearchEngine(strategy="summary_only")
    await summary_engine.index(functions)
    
    # 2. Code index (embed raw code - for hybrid)
    print("\n💻 Building CODE index (for hybrid)...")
    
    # We need to create embeddings for raw code
    code_texts = [f"Function: {f['name']}\n\n{f['code']}" for f in functions]
    code_embeddings = []
    batch_size = 50
    
    for i in range(0, len(code_texts), batch_size):
        batch = code_texts[i:i + batch_size]
        print(f"   Embedding batch {i//batch_size + 1}...")
        await asyncio.sleep(21)
        response = await voyage_client.embed(
            texts=batch,
            model="voyage-code-3",
            input_type="document"
        )
        code_embeddings.extend(response.embeddings)
    
    print(f"   Indexed {len(code_embeddings)} code documents")
    
    # 3. BM25 index (for hybrid keyword matching)
    print("\n🔤 Building BM25 index...")
    # Import BM25 from exp02
    sys.path.insert(0, str(Path(__file__).parent))
    
    # Inline BM25 to avoid import issues
    from collections import defaultdict
    import math
    import re
    
    class SimpleTokenizer:
        STOPWORDS = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                     'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                     'function', 'const', 'let', 'var', 'return', 'export', 'import'}
        
        @classmethod
        def tokenize(cls, text):
            words = re.findall(r'[a-zA-Z][a-zA-Z0-9]*', text)
            tokens = []
            for word in words:
                word_lower = word.lower()
                if word_lower in cls.STOPWORDS or len(word_lower) < 2:
                    continue
                tokens.append(word_lower)
                # Split camelCase
                if re.search(r'[a-z][A-Z]', word):
                    parts = re.sub('([A-Z])', r' \1', word).lower().split()
                    tokens.extend([p for p in parts if len(p) >= 2 and p not in cls.STOPWORDS])
            return tokens
    
    # Build BM25 index
    bm25_index = defaultdict(dict)
    doc_freqs = defaultdict(int)
    doc_lengths = []
    doc_tokens_list = []
    
    for doc_id, func in enumerate(functions):
        text = f"{func['name']} {func['code']}"
        tokens = SimpleTokenizer.tokenize(text)
        doc_tokens_list.append(tokens)
        doc_lengths.append(len(tokens))
        
        term_freqs = defaultdict(int)
        for token in tokens:
            term_freqs[token] += 1
        
        for term, freq in term_freqs.items():
            bm25_index[term][doc_id] = freq
            doc_freqs[term] += 1
    
    avg_doc_length = sum(doc_lengths) / len(doc_lengths)
    num_docs = len(functions)
    print(f"   BM25: Indexed {num_docs} docs, {len(bm25_index)} unique terms")
    
    def bm25_score(query, doc_id, k1=1.5, b=0.75):
        tokens = SimpleTokenizer.tokenize(query)
        score = 0.0
        doc_length = doc_lengths[doc_id]
        
        for token in tokens:
            if token not in bm25_index or doc_id not in bm25_index[token]:
                continue
            tf = bm25_index[token][doc_id]
            df = doc_freqs[token]
            idf = math.log((num_docs - df + 0.5) / (df + 0.5) + 1)
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * doc_length / avg_doc_length)
            score += idf * (numerator / denominator)
        return score
    
    # ==========================================================================
    # FUSION STRATEGIES
    # ==========================================================================
    
    async def search_with_fusion(query: str, alpha: float = 0.5, beta: float = 0.3):
        """
        Fusion search combining:
        - Summary semantic search
        - Code semantic search  
        - BM25 keyword search
        
        Final score = alpha * summary_score + beta * code_semantic + (1-alpha-beta) * bm25
        """
        # 1. Summary semantic search
        await asyncio.sleep(21)
        response = await voyage_client.embed(
            texts=[query],
            model="voyage-code-3", 
            input_type="query"
        )
        query_embedding = response.embeddings[0]
        
        # Score against summaries
        summary_scores = []
        for func, emb in zip(functions, summary_engine.embeddings):
            score = cosine_similarity(query_embedding, emb)
            summary_scores.append(score)
        
        # Score against code
        code_scores = []
        for emb in code_embeddings:
            score = cosine_similarity(query_embedding, emb)
            code_scores.append(score)
        
        # BM25 scores
        bm25_scores = [bm25_score(query, i) for i in range(len(functions))]
        
        # Normalize scores to [0, 1]
        def normalize(scores):
            min_s, max_s = min(scores), max(scores)
            if max_s == min_s:
                return [0.5] * len(scores)
            return [(s - min_s) / (max_s - min_s) for s in scores]
        
        summary_norm = normalize(summary_scores)
        code_norm = normalize(code_scores)
        bm25_norm = normalize(bm25_scores)
        
        # Fuse
        fused = []
        for i, func in enumerate(functions):
            final_score = (alpha * summary_norm[i] + 
                          beta * code_norm[i] + 
                          (1 - alpha - beta) * bm25_norm[i])
            fused.append((func, final_score))
        
        fused.sort(key=lambda x: x[1], reverse=True)
        return fused[:10]
    
    # ==========================================================================
    # TEST DIFFERENT FUSION WEIGHTS
    # ==========================================================================
    
    fusion_configs = [
        # (alpha, beta, name) - alpha=summary, beta=code_semantic, rest=bm25
        (0.5, 0.3, "summary50-code30-bm25_20"),
        (0.4, 0.4, "summary40-code40-bm25_20"),
        (0.6, 0.2, "summary60-code20-bm25_20"),
        (0.5, 0.2, "summary50-code20-bm25_30"),
        (0.4, 0.3, "summary40-code30-bm25_30"),
        (0.5, 0.0, "summary50-bm25_50"),  # No code semantic, just summary + BM25
    ]
    
    results = {}
    
    for alpha, beta, name in fusion_configs:
        print(f"\n{'─' * 60}")
        print(f"Testing: {name}")
        print(f"{'─' * 60}")
        
        strategy_results = []
        
        for query, expected, category in GROUND_TRUTH:
            res = await search_with_fusion(query, alpha=alpha, beta=beta)
            
            hit_1 = check_hit(res, expected, 1)
            hit_3 = check_hit(res, expected, 3)
            hit_5 = check_hit(res, expected, 5)
            top_result = res[0][0]['name'] if res else 'N/A'
            
            strategy_results.append({
                'query': query,
                'expected': expected,
                'hit@1': hit_1,
                'hit@3': hit_3,
                'hit@5': hit_5,
                'top_result': top_result,
            })
            
            status = "✅" if hit_1 else ("⚠️" if hit_3 else "❌")
            print(f"   {status} \"{query[:35]}...\" → {top_result}")
        
        total = len(strategy_results)
        metrics = {
            'hit@1': sum(r['hit@1'] for r in strategy_results) / total,
            'hit@3': sum(r['hit@3'] for r in strategy_results) / total,
            'hit@5': sum(r['hit@5'] for r in strategy_results) / total,
        }
        
        results[name] = {'metrics': metrics, 'details': strategy_results}
        print(f"\n   📊 {name}: Hit@1={metrics['hit@1']:.1%}, Hit@3={metrics['hit@3']:.1%}")
    
    # ==========================================================================
    # FINAL COMPARISON
    # ==========================================================================
    
    print("\n" + "=" * 70)
    print("FINAL COMPARISON: All Approaches")
    print("=" * 70)
    
    prev_hybrid = 0.714
    prev_summary = 0.619
    
    print(f"\n{'Strategy':<35} {'Hit@1':<10} {'Hit@3':<10} {'vs Best':<12}")
    print("─" * 67)
    print(f"{'hybrid-α0.7 (Exp02)':<35} {prev_hybrid:<10.1%} {'95.2%':<10} {'baseline':<12}")
    print(f"{'summary-only (Exp03)':<35} {prev_summary:<10.1%} {'100%':<10} {prev_summary-prev_hybrid:+.1%}")
    
    for name, data in sorted(results.items(), key=lambda x: x[1]['metrics']['hit@1'], reverse=True):
        m = data['metrics']
        diff = m['hit@1'] - prev_hybrid
        print(f"{name:<35} {m['hit@1']:<10.1%} {m['hit@3']:<10.1%} {diff:+.1%}")
    
    # Best fusion
    best_name = max(results.keys(), key=lambda x: results[x]['metrics']['hit@1'])
    best = results[best_name]['metrics']
    
    print("\n" + "=" * 70)
    print("🏆 RESULTS")
    print("=" * 70)
    
    print(f"\n🥇 Best Fusion: {best_name}")
    print(f"   Hit@1: {best['hit@1']:.1%}")
    print(f"   Hit@3: {best['hit@3']:.1%}")
    print(f"   Hit@5: {best['hit@5']:.1%}")
    
    improvement = best['hit@1'] - prev_hybrid
    print(f"\n📈 vs Hybrid (Exp02): {improvement:+.1%}")
    print(f"📈 vs Summary (Exp03): {best['hit@1'] - prev_summary:+.1%}")
    
    # Target check
    print("\n" + "─" * 70)
    if best['hit@1'] >= 0.80:
        print("🎉 TARGET ACHIEVED! >80% Hit@1")
        print("   Fusion of Hybrid + Summary = Best of both worlds!")
    elif best['hit@1'] > prev_hybrid:
        print(f"✅ IMPROVEMENT! {best['hit@1']:.1%} > {prev_hybrid:.1%}")
        print("   Fusion approach works!")
    else:
        print("❌ No improvement over hybrid")
    
    # Save results
    output = {
        'timestamp': datetime.now().isoformat(),
        'experiment': '03_fusion',
        'target': '>80% Hit@1',
        'previous_best_hybrid': prev_hybrid,
        'previous_best_summary': prev_summary,
        'results': results,
        'winner': best_name,
        'best_hit1': best['hit@1'],
    }
    
    results_dir = Path(__file__).parent.parent / "results"
    filename = results_dir / f"exp03_fusion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    def convert(obj):
        if isinstance(obj, (np.floating, float)):
            return float(obj)
        if isinstance(obj, (np.integer, int)):
            return int(obj)
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert(i) for i in obj]
        return obj
    
    with open(filename, 'w') as f:
        json.dump(convert(output), f, indent=2)
    
    print(f"\n💾 Results saved: {filename}")
    print("\n✅ CHECKPOINT 3 COMPLETE!")
    
    return results


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "checkpoint2":
            asyncio.run(checkpoint_2_evaluate())
        elif sys.argv[1] == "checkpoint3":
            asyncio.run(checkpoint_3_fusion())
    else:
        asyncio.run(checkpoint_1_generate_summaries())
