"""
Experiment 02: Hybrid BM25 + Semantic Search
=============================================
Day 2 of CodeIntel Research

Hypothesis: BM25 catches exact keyword matches that semantic search misses.
Combined intelligently, they should cover each other's weaknesses.

Target: >60% Hit@1 accuracy (up from 33% semantic-only)

Fusion Strategies:
- Linear combination (various α weights)
- Reciprocal Rank Fusion (RRF)
"""

import asyncio
import os
import sys
import json
import re
import math
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass
import numpy as np
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

from openai import AsyncOpenAI
import voyageai

# Initialize clients
voyage_client = voyageai.AsyncClient(api_key=os.getenv("VOYAGE_API_KEY"))

print(f"Voyage Key: {os.getenv('VOYAGE_API_KEY')[:20]}...")


# =============================================================================
# CODE-AWARE TOKENIZER
# =============================================================================

class CodeTokenizer:
    """
    Tokenizer that understands code patterns.
    
    Handles:
    - camelCase → ["camel", "case", "camelcase"]
    - snake_case → ["snake", "case", "snakecase"]  
    - PascalCase → ["pascal", "case", "pascalcase"]
    - Preserves important code terms
    """
    
    # Common code stopwords to filter
    STOPWORDS = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'could', 'should', 'may', 'might', 'must', 'shall',
        'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
        'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
        'through', 'during', 'before', 'after', 'above', 'below',
        'between', 'under', 'again', 'further', 'then', 'once',
        'here', 'there', 'when', 'where', 'why', 'how', 'all',
        'each', 'few', 'more', 'most', 'other', 'some', 'such',
        'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
        'too', 'very', 'just', 'and', 'but', 'if', 'or', 'because',
        'until', 'while', 'this', 'that', 'these', 'those', 'it',
        # Code-specific stopwords
        'function', 'const', 'let', 'var', 'return', 'export',
        'import', 'default', 'type', 'interface', 'class',
    }
    
    @staticmethod
    def split_camel_case(text: str) -> List[str]:
        """Split camelCase and PascalCase into components."""
        # Insert space before uppercase letters
        result = re.sub('([A-Z])', r' \1', text)
        return result.lower().split()
    
    @staticmethod
    def split_snake_case(text: str) -> List[str]:
        """Split snake_case into components."""
        return text.lower().split('_')
    
    @classmethod
    def tokenize(cls, text: str, include_original: bool = True) -> List[str]:
        """
        Tokenize text with code awareness.
        
        Args:
            text: Input text (code or query)
            include_original: Whether to include original compound terms
            
        Returns:
            List of tokens
        """
        tokens = []
        
        # First, extract words (alphanumeric sequences)
        words = re.findall(r'[a-zA-Z][a-zA-Z0-9]*', text)
        
        for word in words:
            word_lower = word.lower()
            
            # Skip stopwords
            if word_lower in cls.STOPWORDS:
                continue
            
            # Skip very short tokens
            if len(word_lower) < 2:
                continue
                
            # Always include the full word (lowercase)
            if include_original:
                tokens.append(word_lower)
            
            # Split camelCase/PascalCase
            if re.search(r'[a-z][A-Z]', word):
                parts = cls.split_camel_case(word)
                tokens.extend([p for p in parts if len(p) >= 2 and p not in cls.STOPWORDS])
            
            # Split snake_case (already handled by regex, but check for underscores in original)
            if '_' in word:
                parts = cls.split_snake_case(word)
                tokens.extend([p for p in parts if len(p) >= 2 and p not in cls.STOPWORDS])
        
        return tokens


# =============================================================================
# BM25 IMPLEMENTATION
# =============================================================================

@dataclass
class BM25Config:
    """BM25 hyperparameters."""
    k1: float = 1.5  # Term frequency saturation
    b: float = 0.75   # Length normalization


class BM25Index:
    """
    BM25 index for code search.
    
    Standard BM25 formula:
    score(D, Q) = Σ IDF(qi) * (f(qi, D) * (k1 + 1)) / (f(qi, D) + k1 * (1 - b + b * |D|/avgdl))
    """
    
    def __init__(self, config: BM25Config = None):
        self.config = config or BM25Config()
        self.tokenizer = CodeTokenizer()
        
        # Index structures
        self.documents: List[Dict] = []
        self.doc_tokens: List[List[str]] = []
        self.doc_lengths: List[int] = []
        self.avg_doc_length: float = 0
        
        # Inverted index: term → {doc_id: term_freq}
        self.inverted_index: Dict[str, Dict[int, int]] = defaultdict(dict)
        
        # Document frequencies: term → num_docs_containing_term
        self.doc_freqs: Dict[str, int] = defaultdict(int)
        
        self.num_docs: int = 0
    
    def index(self, documents: List[Dict]):
        """Build BM25 index from documents."""
        self.documents = documents
        self.num_docs = len(documents)
        
        total_length = 0
        
        for doc_id, doc in enumerate(documents):
            # Tokenize: function name + code
            text = f"{doc['name']} {doc['code']}"
            tokens = self.tokenizer.tokenize(text)
            
            self.doc_tokens.append(tokens)
            self.doc_lengths.append(len(tokens))
            total_length += len(tokens)
            
            # Build inverted index
            term_freqs = defaultdict(int)
            for token in tokens:
                term_freqs[token] += 1
            
            for term, freq in term_freqs.items():
                self.inverted_index[term][doc_id] = freq
                self.doc_freqs[term] += 1
        
        self.avg_doc_length = total_length / self.num_docs if self.num_docs > 0 else 0
        
        print(f"   BM25: Indexed {self.num_docs} docs, {len(self.inverted_index)} unique terms")
    
    def _idf(self, term: str) -> float:
        """Calculate IDF for a term."""
        doc_freq = self.doc_freqs.get(term, 0)
        if doc_freq == 0:
            return 0
        # Standard IDF with smoothing
        return math.log((self.num_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1)
    
    def _score_document(self, doc_id: int, query_tokens: List[str]) -> float:
        """Calculate BM25 score for a single document."""
        score = 0.0
        doc_length = self.doc_lengths[doc_id]
        
        for token in query_tokens:
            if token not in self.inverted_index:
                continue
            
            if doc_id not in self.inverted_index[token]:
                continue
            
            tf = self.inverted_index[token][doc_id]
            idf = self._idf(token)
            
            # BM25 formula
            numerator = tf * (self.config.k1 + 1)
            denominator = tf + self.config.k1 * (
                1 - self.config.b + self.config.b * doc_length / self.avg_doc_length
            )
            
            score += idf * (numerator / denominator)
        
        return score
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[Dict, float]]:
        """Search for documents matching query."""
        query_tokens = self.tokenizer.tokenize(query)
        
        # Score all documents
        scores = []
        for doc_id in range(self.num_docs):
            score = self._score_document(doc_id, query_tokens)
            if score > 0:
                scores.append((self.documents[doc_id], score))
        
        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return scores[:top_k]


# =============================================================================
# SEMANTIC SEARCH (Voyage-code-3 - Our Day 1 Winner)
# =============================================================================

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors."""
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


class SemanticIndex:
    """Semantic search using Voyage-code-3 embeddings."""
    
    def __init__(self):
        self.documents: List[Dict] = []
        self.embeddings: List[List[float]] = []
    
    async def index(self, documents: List[Dict]):
        """Index documents with embeddings."""
        self.documents = documents
        
        # Prepare texts
        texts = [f"Function: {f['name']}\n\n{f['code']}" for f in documents]
        
        # Embed in batches (rate limited)
        self.embeddings = []
        batch_size = 50
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            print(f"   Semantic: Embedding batch {i//batch_size + 1}...")
            
            await asyncio.sleep(21)  # Voyage rate limit
            response = await voyage_client.embed(
                texts=batch,
                model="voyage-code-3",
                input_type="document"
            )
            self.embeddings.extend(response.embeddings)
        
        print(f"   Semantic: Indexed {len(self.embeddings)} documents")
    
    async def search(self, query: str, top_k: int = 10) -> List[Tuple[Dict, float]]:
        """Search for documents matching query."""
        # Embed query
        await asyncio.sleep(21)  # Rate limit
        response = await voyage_client.embed(
            texts=[query],
            model="voyage-code-3",
            input_type="query"
        )
        query_embedding = response.embeddings[0]
        
        # Calculate similarities
        scores = []
        for doc, emb in zip(self.documents, self.embeddings):
            score = cosine_similarity(query_embedding, emb)
            scores.append((doc, score))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
    
    async def batch_search(self, queries: List[str], top_k: int = 10) -> List[List[Tuple[Dict, float]]]:
        """Search multiple queries efficiently."""
        await asyncio.sleep(21)  # Rate limit
        response = await voyage_client.embed(
            texts=queries,
            model="voyage-code-3",
            input_type="query"
        )
        query_embeddings = response.embeddings
        
        all_results = []
        for query_emb in query_embeddings:
            scores = []
            for doc, emb in zip(self.documents, self.embeddings):
                score = cosine_similarity(query_emb, emb)
                scores.append((doc, score))
            scores.sort(key=lambda x: x[1], reverse=True)
            all_results.append(scores[:top_k])
        
        return all_results


# =============================================================================
# FUSION STRATEGIES
# =============================================================================

class FusionStrategy:
    """Base class for score fusion strategies."""
    name: str
    
    def fuse(self, 
             bm25_results: List[Tuple[Dict, float]], 
             semantic_results: List[Tuple[Dict, float]],
             all_docs: List[Dict]) -> List[Tuple[Dict, float]]:
        raise NotImplementedError


class LinearFusion(FusionStrategy):
    """
    Linear combination: final = α * semantic + (1-α) * bm25
    
    Requires score normalization since BM25 and semantic have different scales.
    """
    
    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha
        self.name = f"linear-α{alpha}"
    
    def _normalize_scores(self, results: List[Tuple[Dict, float]]) -> Dict[str, float]:
        """Min-max normalize scores to [0, 1]."""
        if not results:
            return {}
        
        scores = [r[1] for r in results]
        min_score, max_score = min(scores), max(scores)
        range_score = max_score - min_score
        
        normalized = {}
        for doc, score in results:
            if range_score > 0:
                normalized[doc['name']] = (score - min_score) / range_score
            else:
                normalized[doc['name']] = 1.0
        
        return normalized
    
    def fuse(self, 
             bm25_results: List[Tuple[Dict, float]], 
             semantic_results: List[Tuple[Dict, float]],
             all_docs: List[Dict]) -> List[Tuple[Dict, float]]:
        
        # Normalize scores
        bm25_norm = self._normalize_scores(bm25_results)
        semantic_norm = self._normalize_scores(semantic_results)
        
        # Create doc lookup
        doc_lookup = {d['name']: d for d in all_docs}
        
        # Combine scores for all docs that appear in either result set
        all_doc_names = set(bm25_norm.keys()) | set(semantic_norm.keys())
        
        fused = []
        for name in all_doc_names:
            bm25_score = bm25_norm.get(name, 0)
            semantic_score = semantic_norm.get(name, 0)
            
            combined = self.alpha * semantic_score + (1 - self.alpha) * bm25_score
            fused.append((doc_lookup[name], combined))
        
        fused.sort(key=lambda x: x[1], reverse=True)
        return fused


class RRFFusion(FusionStrategy):
    """
    Reciprocal Rank Fusion (RRF)
    
    RRF_score = Σ 1 / (k + rank_i)
    
    Benefits:
    - No score normalization needed
    - Robust to outliers
    - Works well with different retrieval methods
    """
    
    def __init__(self, k: int = 60):
        self.k = k  # Standard RRF constant
        self.name = f"rrf-k{k}"
    
    def fuse(self, 
             bm25_results: List[Tuple[Dict, float]], 
             semantic_results: List[Tuple[Dict, float]],
             all_docs: List[Dict]) -> List[Tuple[Dict, float]]:
        
        # Build rank lookup
        bm25_ranks = {doc['name']: rank for rank, (doc, _) in enumerate(bm25_results)}
        semantic_ranks = {doc['name']: rank for rank, (doc, _) in enumerate(semantic_results)}
        
        # Create doc lookup
        doc_lookup = {d['name']: d for d in all_docs}
        
        # Calculate RRF scores
        all_doc_names = set(bm25_ranks.keys()) | set(semantic_ranks.keys())
        
        fused = []
        for name in all_doc_names:
            rrf_score = 0
            
            if name in bm25_ranks:
                rrf_score += 1 / (self.k + bm25_ranks[name])
            
            if name in semantic_ranks:
                rrf_score += 1 / (self.k + semantic_ranks[name])
            
            fused.append((doc_lookup[name], rrf_score))
        
        fused.sort(key=lambda x: x[1], reverse=True)
        return fused


class WeightedRRFFusion(FusionStrategy):
    """
    Weighted RRF - give different weights to each retriever.
    
    RRF_score = w1 / (k + rank_bm25) + w2 / (k + rank_semantic)
    """
    
    def __init__(self, bm25_weight: float = 1.0, semantic_weight: float = 1.0, k: int = 60):
        self.bm25_weight = bm25_weight
        self.semantic_weight = semantic_weight
        self.k = k
        self.name = f"wrrf-bm25_{bm25_weight}-sem_{semantic_weight}"
    
    def fuse(self, 
             bm25_results: List[Tuple[Dict, float]], 
             semantic_results: List[Tuple[Dict, float]],
             all_docs: List[Dict]) -> List[Tuple[Dict, float]]:
        
        bm25_ranks = {doc['name']: rank for rank, (doc, _) in enumerate(bm25_results)}
        semantic_ranks = {doc['name']: rank for rank, (doc, _) in enumerate(semantic_results)}
        doc_lookup = {d['name']: d for d in all_docs}
        
        all_doc_names = set(bm25_ranks.keys()) | set(semantic_ranks.keys())
        
        fused = []
        for name in all_doc_names:
            rrf_score = 0
            
            if name in bm25_ranks:
                rrf_score += self.bm25_weight / (self.k + bm25_ranks[name])
            
            if name in semantic_ranks:
                rrf_score += self.semantic_weight / (self.k + semantic_ranks[name])
            
            fused.append((doc_lookup[name], rrf_score))
        
        fused.sort(key=lambda x: x[1], reverse=True)
        return fused


# =============================================================================
# HYBRID SEARCH ENGINE
# =============================================================================

class HybridSearchEngine:
    """
    Combines BM25 and Semantic search with configurable fusion.
    """
    
    def __init__(self, fusion_strategy: FusionStrategy):
        self.bm25_index = BM25Index()
        self.semantic_index = SemanticIndex()
        self.fusion = fusion_strategy
        self.documents: List[Dict] = []
    
    async def index(self, documents: List[Dict]):
        """Index documents in both systems."""
        self.documents = documents
        
        # BM25 indexing (instant, no API)
        print(f"\n   Building BM25 index...")
        self.bm25_index.index(documents)
        
        # Semantic indexing (requires API calls)
        print(f"   Building Semantic index...")
        await self.semantic_index.index(documents)
    
    def search_bm25_only(self, query: str, top_k: int = 50) -> List[Tuple[Dict, float]]:
        """BM25 search only."""
        return self.bm25_index.search(query, top_k)
    
    async def search_semantic_only(self, query: str, top_k: int = 50) -> List[Tuple[Dict, float]]:
        """Semantic search only."""
        return await self.semantic_index.search(query, top_k)
    
    async def search(self, query: str, top_k: int = 10) -> List[Tuple[Dict, float]]:
        """Hybrid search with fusion."""
        # Get results from both systems
        bm25_results = self.bm25_index.search(query, top_k=50)
        semantic_results = await self.semantic_index.search(query, top_k=50)
        
        # Fuse results
        fused = self.fusion.fuse(bm25_results, semantic_results, self.documents)
        
        return fused[:top_k]


# =============================================================================
# GROUND TRUTH (Same as Experiment 01)
# =============================================================================

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
    
    # NO LIMIT! Index all functions
    # Day 1 we limited to 50 for rate limits, but that excluded
    # all the middleware functions (persist, devtools, immer, etc.)
    
    print(f"📦 Loaded {len(all_functions)} functions from Zustand")
    return all_functions


# =============================================================================
# EVALUATION
# =============================================================================

def check_hit(results: List[Tuple[Dict, float]], expected_names: List[str], k: int) -> bool:
    """Check if any expected function is in top-k results."""
    top_k_names = [r[0]['name'].lower() for r in results[:k]]
    return any(exp.lower() in name or name in exp.lower() 
               for exp in expected_names 
               for name in top_k_names)


# =============================================================================
# EXPERIMENT RUNNER
# =============================================================================

async def run_experiment():
    """Run the hybrid search experiment."""
    print("=" * 70)
    print("EXPERIMENT 02: HYBRID BM25 + SEMANTIC SEARCH")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target: >60% Hit@1 (up from 33% semantic-only)")
    
    # Load codebase
    functions = load_zustand_codebase()
    if not functions:
        return
    
    # Define all strategies to test
    strategies = [
        # Linear combinations
        LinearFusion(alpha=0.3),   # BM25-heavy
        LinearFusion(alpha=0.5),   # Balanced
        LinearFusion(alpha=0.7),   # Semantic-heavy
        
        # RRF variants
        RRFFusion(k=60),           # Standard RRF
        
        # Weighted RRF
        WeightedRRFFusion(bm25_weight=2.0, semantic_weight=1.0),  # BM25 2x
        WeightedRRFFusion(bm25_weight=1.0, semantic_weight=2.0),  # Semantic 2x
    ]
    
    results = {}
    
    # First, build indexes once (expensive due to API calls)
    print("\n" + "─" * 60)
    print("BUILDING INDEXES (one-time cost)")
    print("─" * 60)
    
    # We'll use a dummy strategy just to build indexes
    engine = HybridSearchEngine(LinearFusion(alpha=0.5))
    await engine.index(functions)
    
    # ==========================================================================
    # TEST 1: BM25 Only (No API calls needed!)
    # ==========================================================================
    print("\n" + "─" * 60)
    print("Testing: BM25 ONLY (baseline)")
    print("─" * 60)
    
    bm25_results_list = []
    for query, expected, category in GROUND_TRUTH:
        search_results = engine.search_bm25_only(query, top_k=10)
        
        hit_1 = check_hit(search_results, expected, 1)
        hit_3 = check_hit(search_results, expected, 3)
        hit_5 = check_hit(search_results, expected, 5)
        top_score = search_results[0][1] if search_results else 0
        top_result = search_results[0][0]['name'] if search_results else 'N/A'
        
        bm25_results_list.append({
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
    
    total = len(bm25_results_list)
    bm25_metrics = {
        'hit@1': sum(r['hit@1'] for r in bm25_results_list) / total,
        'hit@3': sum(r['hit@3'] for r in bm25_results_list) / total,
        'hit@5': sum(r['hit@5'] for r in bm25_results_list) / total,
    }
    
    results['bm25-only'] = {'metrics': bm25_metrics, 'details': bm25_results_list}
    print(f"\n   📊 BM25 Only: Hit@1={bm25_metrics['hit@1']:.1%}, Hit@3={bm25_metrics['hit@3']:.1%}")
    
    # ==========================================================================
    # TEST 2: Semantic Only (reusing Day 1's best - voyage-code-3)
    # ==========================================================================
    print("\n" + "─" * 60)
    print("Testing: SEMANTIC ONLY (voyage-code-3 baseline)")
    print("─" * 60)
    
    # Batch search for efficiency
    all_queries = [q[0] for q in GROUND_TRUTH]
    semantic_all_results = await engine.semantic_index.batch_search(all_queries, top_k=10)
    
    semantic_results_list = []
    for i, (query, expected, category) in enumerate(GROUND_TRUTH):
        search_results = semantic_all_results[i]
        
        hit_1 = check_hit(search_results, expected, 1)
        hit_3 = check_hit(search_results, expected, 3)
        hit_5 = check_hit(search_results, expected, 5)
        top_score = search_results[0][1] if search_results else 0
        top_result = search_results[0][0]['name'] if search_results else 'N/A'
        
        semantic_results_list.append({
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
    
    semantic_metrics = {
        'hit@1': sum(r['hit@1'] for r in semantic_results_list) / total,
        'hit@3': sum(r['hit@3'] for r in semantic_results_list) / total,
        'hit@5': sum(r['hit@5'] for r in semantic_results_list) / total,
    }
    
    results['semantic-only'] = {'metrics': semantic_metrics, 'details': semantic_results_list}
    print(f"\n   📊 Semantic Only: Hit@1={semantic_metrics['hit@1']:.1%}, Hit@3={semantic_metrics['hit@3']:.1%}")
    
    # ==========================================================================
    # TEST 3: Hybrid Strategies
    # ==========================================================================
    
    # Pre-compute BM25 and Semantic results for all queries (for fusion)
    bm25_all = [engine.search_bm25_only(q, top_k=50) for q in all_queries]
    # semantic_all already computed above, but need full 50 results
    semantic_all_full = await engine.semantic_index.batch_search(all_queries, top_k=50)
    
    for strategy in strategies:
        print("\n" + "─" * 60)
        print(f"Testing: {strategy.name.upper()}")
        print("─" * 60)
        
        strategy_results_list = []
        
        for i, (query, expected, category) in enumerate(GROUND_TRUTH):
            # Fuse pre-computed results
            fused = strategy.fuse(bm25_all[i], semantic_all_full[i], functions)[:10]
            
            hit_1 = check_hit(fused, expected, 1)
            hit_3 = check_hit(fused, expected, 3)
            hit_5 = check_hit(fused, expected, 5)
            top_score = fused[0][1] if fused else 0
            top_result = fused[0][0]['name'] if fused else 'N/A'
            
            strategy_results_list.append({
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
        
        strategy_metrics = {
            'hit@1': sum(r['hit@1'] for r in strategy_results_list) / total,
            'hit@3': sum(r['hit@3'] for r in strategy_results_list) / total,
            'hit@5': sum(r['hit@5'] for r in strategy_results_list) / total,
        }
        
        results[strategy.name] = {'metrics': strategy_metrics, 'details': strategy_results_list}
        print(f"\n   📊 {strategy.name}: Hit@1={strategy_metrics['hit@1']:.1%}, Hit@3={strategy_metrics['hit@3']:.1%}")
    
    # ==========================================================================
    # FINAL COMPARISON
    # ==========================================================================
    print("\n" + "=" * 70)
    print("COMPARISON SUMMARY")
    print("=" * 70)
    
    print(f"\n{'Strategy':<35} {'Hit@1':<10} {'Hit@3':<10} {'Hit@5':<10} {'vs Semantic':<12}")
    print("─" * 77)
    
    semantic_baseline = results['semantic-only']['metrics']['hit@1']
    
    for name, data in sorted(results.items(), key=lambda x: x[1]['metrics']['hit@1'], reverse=True):
        m = data['metrics']
        improvement = m['hit@1'] - semantic_baseline
        imp_str = f"{improvement:+.1%}" if name != 'semantic-only' else "baseline"
        print(f"{name:<35} {m['hit@1']:<10.1%} {m['hit@3']:<10.1%} {m['hit@5']:<10.1%} {imp_str:<12}")
    
    # Find winner
    best_name = max(results.keys(), key=lambda x: results[x]['metrics']['hit@1'])
    best = results[best_name]['metrics']
    
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    
    print(f"\n🏆 Best Strategy: {best_name}")
    print(f"   Hit@1: {best['hit@1']:.1%}")
    print(f"   Hit@3: {best['hit@3']:.1%}")
    print(f"   Hit@5: {best['hit@5']:.1%}")
    
    improvement = best['hit@1'] - semantic_baseline
    print(f"\n📈 Improvement over semantic-only: {improvement:+.1%}")
    
    # Decision
    print("\n" + "─" * 70)
    if best['hit@1'] >= 0.6:
        print("✅ TARGET ACHIEVED! >60% Hit@1")
        print(f"   Hybrid search is {improvement/semantic_baseline:.0%} better than semantic alone")
    elif best['hit@1'] >= 0.5:
        print("⚠️  PROGRESS: 50-60% range")
        print("   Hybrid helps, but need more improvements")
    else:
        print("❌ BELOW TARGET: <50%")
        print("   Need to explore other approaches")
    
    # ==========================================================================
    # DETAILED ANALYSIS: What did hybrid fix?
    # ==========================================================================
    print("\n" + "=" * 70)
    print("ANALYSIS: What did hybrid fix?")
    print("=" * 70)
    
    best_details = results[best_name]['details']
    semantic_details = results['semantic-only']['details']
    
    fixed = []
    broke = []
    
    for i in range(len(GROUND_TRUTH)):
        sem_hit = semantic_details[i]['hit@1']
        hyb_hit = best_details[i]['hit@1']
        query = GROUND_TRUTH[i][0]
        
        if not sem_hit and hyb_hit:
            fixed.append((query, semantic_details[i]['top_result'], best_details[i]['top_result']))
        elif sem_hit and not hyb_hit:
            broke.append((query, semantic_details[i]['top_result'], best_details[i]['top_result']))
    
    if fixed:
        print(f"\n✅ FIXED by hybrid ({len(fixed)} queries):")
        for query, sem_result, hyb_result in fixed:
            print(f"   \"{query[:40]}\"")
            print(f"      Semantic: {sem_result} ❌ → Hybrid: {hyb_result} ✅")
    
    if broke:
        print(f"\n❌ BROKEN by hybrid ({len(broke)} queries):")
        for query, sem_result, hyb_result in broke:
            print(f"   \"{query[:40]}\"")
            print(f"      Semantic: {sem_result} ✅ → Hybrid: {hyb_result} ❌")
    
    # Save results
    output = {
        'timestamp': datetime.now().isoformat(),
        'experiment': '02_hybrid_search',
        'target': '>60% Hit@1',
        'strategies': list(results.keys()),
        'num_queries': len(GROUND_TRUTH),
        'results': results,
        'winner': best_name,
        'improvement_vs_semantic': improvement,
    }
    
    results_dir = Path(__file__).parent.parent / "results"
    results_dir.mkdir(exist_ok=True)
    
    filename = results_dir / f"exp02_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
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
    print("\n✅ Experiment 02 complete!")
    
    return results


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    asyncio.run(run_experiment())
