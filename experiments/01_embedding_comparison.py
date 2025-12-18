"""
Experiment 01: Embedding Model Comparison
==========================================
THE critical experiment - compare OpenAI vs Voyage AI for code search.

Models:
- OpenAI text-embedding-3-small (baseline)
- Voyage voyage-code-2 (code-specific)  
- Voyage voyage-code-3 (latest)

Success Criteria: >70% Top-3 accuracy, >0.5 avg score
"""

import asyncio
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

from openai import AsyncOpenAI
import voyageai

# Initialize clients
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
voyage_client = voyageai.AsyncClient(api_key=os.getenv("VOYAGE_API_KEY"))

print(f"OpenAI Key: {os.getenv('OPENAI_API_KEY')[:20]}...")
print(f"Voyage Key: {os.getenv('VOYAGE_API_KEY')[:20]}...")


# =============================================================================
# EMBEDDING PROVIDERS
# =============================================================================

class EmbeddingProvider:
    """Base class for embedding providers."""
    name: str
    dimensions: int
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class OpenAISmall(EmbeddingProvider):
    name = "openai-small"
    dimensions = 1536
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        response = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=texts
        )
        return [d.embedding for d in response.data]


class OpenAILarge(EmbeddingProvider):
    name = "openai-large"
    dimensions = 3072
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        response = await openai_client.embeddings.create(
            model="text-embedding-3-large",
            input=texts
        )
        return [d.embedding for d in response.data]


class VoyageCode2(EmbeddingProvider):
    name = "voyage-code-2"
    dimensions = 1536
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        # Rate limit: 3 RPM on free tier, so we wait between calls
        await asyncio.sleep(21)  # Wait 21 seconds between batches (3 per minute)
        response = await voyage_client.embed(
            texts=texts,
            model="voyage-code-2",
            input_type="document"
        )
        return response.embeddings


class VoyageCode3(EmbeddingProvider):
    name = "voyage-code-3"
    dimensions = 1024
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        await asyncio.sleep(21)  # Wait 21 seconds between batches
        response = await voyage_client.embed(
            texts=texts,
            model="voyage-code-3",
            input_type="document"
        )
        return response.embeddings


# All providers to test
PROVIDERS = [
    OpenAISmall(),
    VoyageCode2(),
    VoyageCode3(),
]


# =============================================================================
# GROUND TRUTH - Queries with expected function matches
# =============================================================================
# Format: (query, list of acceptable function names, category)
# These are HARD queries - natural language, not function name hints

GROUND_TRUTH = [
    # State Management Core
    ("update the store state", ["setState", "set"], "state"),
    ("get current state value", ["getState", "get"], "state"),
    ("listen for state changes", ["subscribe", "subscribeWithSelector"], "state"),
    ("create a new store", ["createStore", "create", "createStoreImpl"], "state"),
    
    # Persistence
    ("save state to localStorage", ["persist", "setItem", "persistImpl"], "persist"),
    ("load saved state from storage", ["hydrate", "rehydrate", "getItem"], "persist"),
    ("clear persisted data", ["clearStorage", "removeItem"], "persist"),
    ("migrate old stored state version", ["migrate", "migration"], "persist"),
    ("custom storage adapter", ["createJSONStorage", "StateStorage"], "persist"),
    
    # Middleware
    ("combine multiple stores", ["combine"], "middleware"),
    ("redux devtools integration", ["devtools"], "middleware"),
    ("use immer for immutable updates", ["immer"], "middleware"),
    ("subscribe to specific state slice", ["subscribeWithSelector"], "middleware"),
    
    # React Integration
    ("use store in react component", ["useStore", "create", "useStoreWithEqualityFn"], "react"),
    ("shallow comparison for selectors", ["shallow", "useShallow"], "react"),
    ("avoid unnecessary rerenders", ["shallow", "useShallow", "equalityFn"], "react"),
    
    # Advanced
    ("check if state objects are equal", ["shallow", "is", "Object.is"], "comparison"),
    ("merge new state with existing", ["merge", "assign", "Object.assign"], "state"),
    ("notify all listeners of change", ["listeners", "forEach", "notify"], "state"),
    
    # Error Handling & Edge Cases
    ("handle storage not available", ["storage", "catch", "undefined"], "error"),
    ("server side rendering safe", ["ssrSafe", "skipHydration"], "ssr"),
]


# =============================================================================
# CODE PARSER (Tree-sitter)
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
        # Function types to extract
        if node.type in ['function_declaration', 'arrow_function', 
                         'method_definition', 'variable_declarator']:
            name = get_name(node)
            if name and not name.startswith('_'):
                func_code = code[node.start_byte:node.end_byte]
                if len(func_code) > 20:  # Skip tiny snippets
                    functions.append({
                        'name': name,
                        'code': func_code[:2000],  # Limit size
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
        print("   Run: git clone https://github.com/pmndrs/zustand test_repos/zustand")
        return []
    
    all_functions = []
    
    for ts_file in repo_path.rglob("*.ts"):
        funcs = extract_functions_from_file(str(ts_file))
        all_functions.extend(funcs)
    
    # Limit to 50 functions for faster testing (rate limits)
    if len(all_functions) > 50:
        all_functions = all_functions[:50]
    
    print(f"📦 Loaded {len(all_functions)} functions from Zustand")
    return all_functions


# =============================================================================
# SEARCH ENGINE
# =============================================================================

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors."""
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


class SearchEngine:
    """Simple in-memory search engine for testing."""
    
    def __init__(self, provider: EmbeddingProvider):
        self.provider = provider
        self.functions = []
        self.embeddings = []
    
    async def index(self, functions: List[Dict]):
        """Index functions with embeddings."""
        self.functions = functions
        
        # Prepare texts for embedding
        texts = [f"Function: {f['name']}\n\n{f['code']}" for f in functions]
        
        # For Voyage, use larger batches (up to 128) to reduce API calls
        self.embeddings = []
        batch_size = 50 if 'voyage' in self.provider.name else 20
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            print(f"   Embedding batch {i//batch_size + 1}...")
            batch_embeddings = await self.provider.embed(batch)
            self.embeddings.extend(batch_embeddings)
        
        print(f"   Indexed {len(self.embeddings)} functions with {self.provider.name}")

    
    async def search(self, query: str, top_k: int = 10) -> List[Tuple[Dict, float]]:
        """Search for functions matching query."""
        # Embed query
        query_embedding = (await self.provider.embed([query]))[0]
        
        # Calculate similarities
        scores = []
        for func, emb in zip(self.functions, self.embeddings):
            score = cosine_similarity(query_embedding, emb)
            scores.append((func, score))
        
        # Sort by score
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
    
    async def batch_search(self, queries: List[str], top_k: int = 10) -> List[List[Tuple[Dict, float]]]:
        """Search multiple queries at once (more efficient for rate-limited APIs)."""
        # Embed all queries in one call
        query_embeddings = await self.provider.embed(queries)
        
        all_results = []
        for query_emb in query_embeddings:
            scores = []
            for func, emb in zip(self.functions, self.embeddings):
                score = cosine_similarity(query_emb, emb)
                scores.append((func, score))
            scores.sort(key=lambda x: x[1], reverse=True)
            all_results.append(scores[:top_k])
        
        return all_results



# =============================================================================
# EXPERIMENT RUNNER
# =============================================================================

def check_hit(results: List[Tuple[Dict, float]], expected_names: List[str], k: int) -> bool:
    """Check if any expected function is in top-k results."""
    top_k_names = [r[0]['name'].lower() for r in results[:k]]
    return any(exp.lower() in name or name in exp.lower() 
               for exp in expected_names 
               for name in top_k_names)


async def run_experiment():
    """Run the embedding comparison experiment."""
    print("=" * 70)
    print("EXPERIMENT 01: EMBEDDING MODEL COMPARISON")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load Zustand codebase
    functions = load_zustand_codebase()
    if not functions:
        return
    
    # Results storage
    results = {}
    
    # Extract all queries for batch processing
    all_queries = [q[0] for q in GROUND_TRUTH]
    
    # Test each provider
    for provider in PROVIDERS:
        print(f"\n{'─' * 60}")
        print(f"Testing: {provider.name}")
        print(f"{'─' * 60}")
        
        # Create search engine
        engine = SearchEngine(provider)
        await engine.index(functions)
        
        # Run ALL queries in one batch (more efficient for rate-limited APIs)
        print(f"   Running {len(all_queries)} queries...")
        all_search_results = await engine.batch_search(all_queries, top_k=10)
        
        # Process results
        provider_results = []
        
        for i, (query, expected, category) in enumerate(GROUND_TRUTH):
            search_results = all_search_results[i]
            
            hit_1 = check_hit(search_results, expected, 1)
            hit_3 = check_hit(search_results, expected, 3)
            hit_5 = check_hit(search_results, expected, 5)
            top_score = search_results[0][1] if search_results else 0
            
            provider_results.append({
                'query': query,
                'expected': expected,
                'category': category,
                'hit@1': hit_1,
                'hit@3': hit_3,
                'hit@5': hit_5,
                'top_score': top_score,
                'top_result': search_results[0][0]['name'] if search_results else None,
            })
            
            status = "✅" if hit_1 else ("⚠️" if hit_3 else "❌")
            print(f"   {status} \"{query[:40]}...\" → {search_results[0][0]['name'] if search_results else 'N/A'} ({top_score:.3f})")
        
        # Calculate metrics
        total = len(provider_results)
        metrics = {
            'hit@1': sum(r['hit@1'] for r in provider_results) / total,
            'hit@3': sum(r['hit@3'] for r in provider_results) / total,
            'hit@5': sum(r['hit@5'] for r in provider_results) / total,
            'avg_score': np.mean([r['top_score'] for r in provider_results]),
        }
        
        results[provider.name] = {
            'metrics': metrics,
            'details': provider_results,
        }
        
        print(f"\n   📊 {provider.name} Results:")
        print(f"      Hit@1: {metrics['hit@1']:.1%}")
        print(f"      Hit@3: {metrics['hit@3']:.1%}")
        print(f"      Hit@5: {metrics['hit@5']:.1%}")
        print(f"      Avg Score: {metrics['avg_score']:.4f}")
    
    # ==========================================================================
    # COMPARISON SUMMARY
    # ==========================================================================
    print("\n" + "=" * 70)
    print("COMPARISON SUMMARY")
    print("=" * 70)
    
    print(f"\n{'Model':<20} {'Hit@1':<10} {'Hit@3':<10} {'Hit@5':<10} {'Avg Score':<12}")
    print("-" * 62)
    
    for name, data in results.items():
        m = data['metrics']
        print(f"{name:<20} {m['hit@1']:<10.1%} {m['hit@3']:<10.1%} {m['hit@5']:<10.1%} {m['avg_score']:<12.4f}")
    
    # Find winner
    best_model = max(results.keys(), key=lambda x: (results[x]['metrics']['hit@1'], results[x]['metrics']['avg_score']))
    baseline = results.get('openai-small', {}).get('metrics', {})
    best = results[best_model]['metrics']
    
    print("\n" + "=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)
    
    print(f"\n🏆 Best Model: {best_model}")
    print(f"   Hit@1: {best['hit@1']:.1%}")
    print(f"   Hit@3: {best['hit@3']:.1%}")
    print(f"   Avg Score: {best['avg_score']:.4f}")
    
    if best_model != 'openai-small' and baseline:
        print(f"\n📈 vs OpenAI Small (baseline):")
        print(f"   Hit@1: {best['hit@1'] - baseline['hit@1']:+.1%}")
        print(f"   Avg Score: {best['avg_score'] - baseline['avg_score']:+.4f}")
    
    # Decision point
    print("\n" + "-" * 70)
    if best['hit@1'] >= 0.7:
        print("✅ DECISION: Proceed with implementation!")
        print(f"   {best_model} achieves target accuracy (>70%)")
    elif best['hit@1'] >= 0.5:
        print("⚠️  DECISION: Promising, but needs improvement")
        print("   Consider: hybrid search, reranking, better prompts")
    else:
        print("❌ DECISION: Rethink approach")
        print("   Semantic search alone may not be sufficient")
    
    # Save results
    output = {
        'timestamp': datetime.now().isoformat(),
        'experiment': '01_embedding_comparison',
        'models': list(results.keys()),
        'num_queries': len(GROUND_TRUTH),
        'results': results,
    }
    
    results_dir = Path(__file__).parent.parent / "results"
    results_dir.mkdir(exist_ok=True)
    
    filename = results_dir / f"exp01_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # Convert numpy types for JSON
    def convert(obj):
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert(i) for i in obj]
        return obj
    
    with open(filename, 'w') as f:
        json.dump(convert(output), f, indent=2)
    
    print(f"\n💾 Results saved: {filename}")
    print("\n✅ Experiment complete!")
    
    return results


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    asyncio.run(run_experiment())
