"""
RRF (Reciprocal Rank Fusion) Search Engine
==========================================

This is the PRODUCTION-GRADE search engine that matches OLD system's approach.

RRF Benefits:
- Combines multiple ranking signals without needing to normalize scores
- More robust than linear combination
- Industry standard (used by Elasticsearch, etc.)

Formula: RRF_score = Σ 1/(k + rank_i) for each ranking method

Usage:
    python3 scripts/evaluate_rrf.py flask
"""

import json
import sys
import os
import time
import re
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi

# Setup paths
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.extractors.base import ExtractedFunction


@dataclass
class RRFResult:
    """Search result with RRF scoring details."""
    function: ExtractedFunction
    rrf_score: float
    bm25_rank: int
    semantic_rank: int
    summary_rank: int


class RRFSearchEngine:
    """
    Triple Fusion Search with Reciprocal Rank Fusion.
    
    Combines three signals:
    1. BM25 (lexical/keyword matching)
    2. Code embeddings (semantic code similarity)
    3. Summary embeddings (semantic summary similarity)
    
    This matches the OLD system's approach that achieved 64% on Flask.
    """
    
    def __init__(
        self,
        functions: List[ExtractedFunction],
        embedding_provider: str = "openai",  # "openai" or "voyage"
        k: int = 60,  # RRF constant (standard is 60)
    ):
        self.functions = functions
        self.embedding_provider = embedding_provider
        self.k = k
        
        # Setup embedding client
        if embedding_provider == "openai":
            from openai import OpenAI
            from dotenv import load_dotenv
            load_dotenv(ROOT / ".env")
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.model = "text-embedding-3-small"
        else:
            import voyageai
            self.client = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))
            self.model = "voyage-code-3"
        
        self._build_indices()
    
    def _build_indices(self):
        """Build all three indices."""
        print("📚 Building indices...")
        
        # 1. BM25 Index
        print("   [1/3] BM25 index...")
        self._build_bm25_index()
        
        # 2. Code Embeddings
        print("   [2/3] Code embeddings...")
        self._build_code_embeddings()
        
        # 3. Summary Embeddings
        print("   [3/3] Summary embeddings...")
        self._build_summary_embeddings()
        
        print("   ✅ All indices ready!")
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize for BM25."""
        text = text.lower()
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
        text = text.replace('_', ' ').replace('.', ' ')
        return re.findall(r'\b\w+\b', text)
    
    def _build_bm25_index(self):
        """Build BM25 index on code + metadata."""
        corpus = []
        for func in self.functions:
            text_parts = [
                func.qualified_name,
                func.name,
                func.signature,
                func.docstring or "",
                func.class_docstring or "",
                " ".join(func.decorators),
            ]
            corpus.append(self._tokenize(" ".join(text_parts)))
        
        self.bm25 = BM25Okapi(corpus)
    
    def _embed_batch(self, texts: List[str], input_type: str = "document") -> List[List[float]]:
        """Embed a batch of texts."""
        # Truncate long texts
        texts = [t[:8000] if len(t) > 8000 else t for t in texts]
        
        if self.embedding_provider == "openai":
            response = self.client.embeddings.create(
                model=self.model,
                input=texts
            )
            return [e.embedding for e in response.data]
        else:
            # Voyage with rate limit handling
            try:
                result = self.client.embed(
                    texts,
                    model=self.model,
                    input_type=input_type
                )
                return result.embeddings
            except Exception as e:
                print(f"      ⚠️ Rate limit hit, waiting 60s...")
                time.sleep(60)
                result = self.client.embed(
                    texts,
                    model=self.model,
                    input_type=input_type
                )
                return result.embeddings
    
    def _build_code_embeddings(self):
        """Build embeddings on code content."""
        # Use full_context (signature + class context + docstring)
        contexts = [func.full_context for func in self.functions]
        
        embeddings = []
        batch_size = 50 if self.embedding_provider == "voyage" else 100
        
        for i in range(0, len(contexts), batch_size):
            batch = contexts[i:i+batch_size]
            batch_emb = self._embed_batch(batch, "document")
            embeddings.extend(batch_emb)
            print(f"      Code: {min(i+batch_size, len(contexts))}/{len(contexts)}")
            
            # Rate limit delay for Voyage
            if self.embedding_provider == "voyage" and i + batch_size < len(contexts):
                print(f"      ⏳ Waiting 25s for rate limit...")
                time.sleep(25)
        
        self.code_embeddings = np.array(embeddings)
    
    def _build_summary_embeddings(self):
        """Build embeddings on summaries."""
        # Use summaries where available, else signature
        summaries = []
        for func in self.functions:
            if func.summary:
                summaries.append(func.summary)
            else:
                summaries.append(func.signature)
        
        embeddings = []
        batch_size = 50 if self.embedding_provider == "voyage" else 100
        
        for i in range(0, len(summaries), batch_size):
            batch = summaries[i:i+batch_size]
            batch_emb = self._embed_batch(batch, "document")
            embeddings.extend(batch_emb)
            print(f"      Summary: {min(i+batch_size, len(summaries))}/{len(summaries)}")
            
            # Rate limit delay for Voyage
            if self.embedding_provider == "voyage" and i + batch_size < len(summaries):
                print(f"      ⏳ Waiting 25s for rate limit...")
                time.sleep(25)
        
        self.summary_embeddings = np.array(embeddings)
    
    def _embed_query(self, query: str) -> List[float]:
        """Embed a single query."""
        if self.embedding_provider == "openai":
            response = self.client.embeddings.create(
                model=self.model,
                input=[query]
            )
            return response.data[0].embedding
        else:
            # Voyage with rate limit handling
            try:
                result = self.client.embed(
                    [query],
                    model=self.model,
                    input_type="query"
                )
                return result.embeddings[0]
            except Exception as e:
                print(f"      ⚠️ Rate limit, waiting 30s...")
                time.sleep(30)
                result = self.client.embed(
                    [query],
                    model=self.model,
                    input_type="query"
                )
                return result.embeddings[0]
    
    def _get_rankings(self, query: str) -> tuple:
        """Get rankings from all three methods."""
        n = len(self.functions)
        
        # 1. BM25 Rankings
        query_tokens = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(query_tokens)
        bm25_ranking = np.argsort(-bm25_scores)  # Descending
        bm25_ranks = np.empty(n, dtype=int)
        bm25_ranks[bm25_ranking] = np.arange(n)
        
        # 2. Code Embedding Rankings
        query_emb = self._embed_query(query)
        code_scores = np.dot(self.code_embeddings, query_emb)
        code_ranking = np.argsort(-code_scores)
        code_ranks = np.empty(n, dtype=int)
        code_ranks[code_ranking] = np.arange(n)
        
        # 3. Summary Embedding Rankings
        summary_scores = np.dot(self.summary_embeddings, query_emb)
        summary_ranking = np.argsort(-summary_scores)
        summary_ranks = np.empty(n, dtype=int)
        summary_ranks[summary_ranking] = np.arange(n)
        
        return bm25_ranks, code_ranks, summary_ranks
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        weights: Dict[str, float] = None
    ) -> List[RRFResult]:
        """
        Search using Reciprocal Rank Fusion.
        
        Args:
            query: Search query
            top_k: Number of results
            weights: Optional weights for each signal
                     Default: {'bm25': 1.0, 'code': 1.0, 'summary': 1.0}
        """
        if weights is None:
            weights = {'bm25': 1.0, 'code': 1.0, 'summary': 1.0}
        
        # Get rankings from all methods
        bm25_ranks, code_ranks, summary_ranks = self._get_rankings(query)
        
        # Calculate RRF scores
        rrf_scores = []
        for i in range(len(self.functions)):
            score = (
                weights['bm25'] * (1.0 / (self.k + bm25_ranks[i])) +
                weights['code'] * (1.0 / (self.k + code_ranks[i])) +
                weights['summary'] * (1.0 / (self.k + summary_ranks[i]))
            )
            rrf_scores.append(score)
        
        # Sort by RRF score
        rrf_scores = np.array(rrf_scores)
        top_indices = np.argsort(-rrf_scores)[:top_k]
        
        # Build results
        results = []
        for idx in top_indices:
            results.append(RRFResult(
                function=self.functions[idx],
                rrf_score=rrf_scores[idx],
                bm25_rank=bm25_ranks[idx],
                semantic_rank=code_ranks[idx],
                summary_rank=summary_ranks[idx],
            ))
        
        return results


def load_functions(codebase: str) -> List[ExtractedFunction]:
    """Load functions from v2 summaries."""
    path = ROOT / f"results/{codebase}_v2_summaries.json"
    
    with open(path) as f:
        data = json.load(f)
    
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
            is_dunder=fd.get('is_dunder', False),
            language='python',
            summary=fd.get('summary'),
        )
        functions.append(func)
    
    return functions


def run_evaluation(
    search_engine: RRFSearchEngine,
    queries: List[Dict],
    verbose: bool = True
) -> Dict[str, Any]:
    """Run evaluation with RRF search."""
    hits = 0
    is_voyage = search_engine.embedding_provider == "voyage"
    
    for idx, item in enumerate(queries):
        query = item['query']
        expected = item['expected']
        expected_list = expected if isinstance(expected, list) else [expected]
        
        results = search_engine.search(query, top_k=1)
        
        if results:
            top = results[0]
            is_hit = any(
                exp == top.function.name or
                exp == top.function.qualified_name or
                exp in top.function.qualified_name
                for exp in expected_list
            )
            
            if is_hit:
                hits += 1
                status = "✅"
            else:
                status = "❌"
            
            if verbose:
                print(f"{status} [{idx+1}/{len(queries)}] {query[:40]}")
                print(f"   Expected: {expected_list[0]} | Got: {top.function.qualified_name}")
                print(f"   Ranks: BM25={top.bm25_rank}, Code={top.semantic_rank}, Summary={top.summary_rank}")
        
        # Rate limit delay for Voyage queries
        if is_voyage and idx + 1 < len(queries):
            time.sleep(21)
    
    hit_rate = hits / len(queries)
    return {'hit_at_1': hit_rate, 'hits': hits, 'total': len(queries)}


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 evaluate_rrf.py <codebase> [openai|voyage]")
        print("Example: python3 evaluate_rrf.py flask openai")
        sys.exit(1)
    
    codebase = sys.argv[1].lower()
    provider = sys.argv[2] if len(sys.argv) > 2 else "openai"
    
    print("=" * 60)
    print(f"🚀 RRF EVALUATION - {codebase.upper()} ({provider})")
    print("=" * 60)
    
    # Load functions
    print(f"\n📦 Loading functions...")
    try:
        functions = load_functions(codebase)
    except FileNotFoundError:
        print(f"❌ Run generate_summaries.py first!")
        sys.exit(1)
    
    with_summary = sum(1 for f in functions if f.summary)
    print(f"   {len(functions)} functions, {with_summary} with summaries")
    
    # Build RRF search engine
    print(f"\n🔧 Building RRF search engine...")
    search = RRFSearchEngine(functions, embedding_provider=provider)
    
    # Load queries
    queries_path = ROOT / f"evals/{codebase}_queries.json"
    with open(queries_path) as f:
        queries = json.load(f)
    print(f"\n📋 {len(queries)} queries loaded")
    
    # Evaluate
    print(f"\n{'='*60}")
    print("📊 EVALUATION")
    print(f"{'='*60}\n")
    
    results = run_evaluation(search, queries, verbose=True)
    
    # Results
    print(f"\n{'='*60}")
    print(f"🎯 RRF Hit@1: {results['hit_at_1']*100:.1f}% ({results['hits']}/{results['total']})")
    print(f"{'='*60}")
    
    # Comparison
    try:
        with open(ROOT / f"results/{codebase}_evaluation.json") as f:
            old_data = json.load(f)
        old_hit = old_data.get('hit@1', 0) * 100
        
        print(f"\n📊 COMPARISON:")
        print(f"   OLD (Voyage+RRF):    {old_hit:.1f}%")
        print(f"   NEW Linear+OpenAI:   54-56%")
        print(f"   NEW Linear+Voyage:   58%")
        print(f"   NEW RRF+{provider.capitalize()}:       {results['hit_at_1']*100:.1f}%")
        
        diff = results['hit_at_1']*100 - old_hit
        emoji = "📈" if diff >= 0 else "📉"
        print(f"   {emoji} vs OLD: {diff:+.1f}%")
    except:
        pass


if __name__ == "__main__":
    main()
