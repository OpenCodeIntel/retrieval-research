"""
Python-Optimized Search Engine

Supports both OpenAI and Voyage embeddings.
Use OpenAI for fast iteration, Voyage for best quality.
"""

import re
import os
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi
from openai import OpenAI
from dotenv import load_dotenv

# Load env
load_dotenv(Path(__file__).parent.parent.parent / ".env")

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.extractors.base import ExtractedFunction


@dataclass
class SearchResult:
    """A single search result with scoring details."""
    function: ExtractedFunction
    score: float
    bm25_score: float = 0.0
    semantic_score: float = 0.0
    qualified_name_boost: float = 0.0
    class_context_boost: float = 0.0
    decorator_boost: float = 0.0
    match_reason: str = ""


class PythonOptimizedSearch:
    """
    Search engine optimized for Python codebases.
    
    Uses Triple Fusion (BM25 + Embeddings) with Python-specific boosts.
    """
    
    def __init__(
        self,
        functions: List[ExtractedFunction],
        embedding_provider: str = "openai",  # "openai" or "voyage"
        voyage_api_key: Optional[str] = None,
    ):
        self.functions = functions
        self.embedding_provider = embedding_provider
        
        # Setup embedding client
        if embedding_provider == "openai":
            self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.embedding_model = "text-embedding-3-small"
        else:
            import voyageai
            self.voyage_client = voyageai.Client(api_key=voyage_api_key or os.getenv("VOYAGE_API_KEY"))
            self.embedding_model = "voyage-code-3"
        
        # Build indices
        self._build_bm25_index()
        self._build_embedding_index()
    
    def _build_bm25_index(self):
        """Build BM25 index on code + qualified names + docstrings."""
        print("📚 Building BM25 index...")
        
        self.corpus = []
        for func in self.functions:
            text_parts = [
                func.qualified_name,
                func.name,
                func.signature,
                func.docstring or "",
                func.class_docstring or "",
                " ".join(func.decorators),
            ]
            text = " ".join(text_parts)
            tokens = self._tokenize(text)
            self.corpus.append(tokens)
        
        self.bm25 = BM25Okapi(self.corpus)
        print(f"   ✅ BM25 index built with {len(self.corpus)} documents")
    
    def _build_embedding_index(self):
        """Build embedding index using full_context + summary."""
        print(f"🧠 Building embedding index ({self.embedding_provider})...")
        
        # Use summary if available, otherwise full_context
        contexts = []
        for func in self.functions:
            if func.summary:
                # Combine summary with signature for best results
                ctx = f"{func.signature}\n{func.summary}"
            else:
                ctx = func.full_context
            contexts.append(ctx)
        
        if self.embedding_provider == "openai":
            embeddings = self._embed_openai(contexts)
        else:
            embeddings = self._embed_voyage(contexts)
        
        self.embeddings = np.array(embeddings)
        
        # Count how many have summaries
        with_summary = sum(1 for f in self.functions if f.summary)
        print(f"   ✅ Embedded {len(self.embeddings)} functions ({with_summary} with summaries)")
    
    def _embed_openai(self, texts: List[str]) -> List[List[float]]:
        """Embed using OpenAI - fast, no rate limit issues."""
        embeddings = []
        batch_size = 100
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            # Truncate long texts
            batch = [t[:8000] for t in batch]
            
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=batch
            )
            batch_embeddings = [e.embedding for e in response.data]
            embeddings.extend(batch_embeddings)
            print(f"      Embedded {min(i+batch_size, len(texts))}/{len(texts)}")
        
        return embeddings
    
    def _embed_voyage(self, texts: List[str], batch_size: int = 50) -> List[List[float]]:
        """Embed using Voyage - best quality, but rate limited."""
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            
            result = self.voyage_client.embed(
                batch,
                model=self.embedding_model,
                input_type="document"
            )
            embeddings.extend(result.embeddings)
            print(f"      Embedded {min(i+batch_size, len(texts))}/{len(texts)}")
            
            # Rate limit: 3 RPM on free tier, so wait 20 seconds between batches
            if i + batch_size < len(texts):
                print(f"      ⏳ Waiting 20s for rate limit...")
                time.sleep(20)
        
        return embeddings
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for BM25."""
        text = text.lower()
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
        text = text.replace('_', ' ').replace('.', ' ')
        tokens = re.findall(r'\b\w+\b', text)
        return tokens
    
    def _embed_query(self, query: str) -> List[float]:
        """Embed a single query."""
        if self.embedding_provider == "openai":
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=[query]
            )
            return response.data[0].embedding
        else:
            result = self.voyage_client.embed(
                [query],
                model=self.embedding_model,
                input_type="query"
            )
            return result.embeddings[0]
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        bm25_weight: float = 0.3,
        semantic_weight: float = 0.7,
        apply_python_boosts: bool = True
    ) -> List[SearchResult]:
        """Search for functions matching the query."""
        
        # BM25 scores
        query_tokens = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(query_tokens)
        if bm25_scores.max() > 0:
            bm25_scores = bm25_scores / bm25_scores.max()
        
        # Semantic scores
        query_embedding = self._embed_query(query)
        semantic_scores = np.dot(self.embeddings, query_embedding)
        semantic_scores = (semantic_scores - semantic_scores.min()) / (semantic_scores.max() - semantic_scores.min() + 1e-8)
        
        # Combine
        results = []
        for i, func in enumerate(self.functions):
            bm25 = bm25_scores[i]
            semantic = semantic_scores[i]
            score = (bm25_weight * bm25) + (semantic_weight * semantic)
            
            qname_boost = 0.0
            class_boost = 0.0
            decorator_boost = 0.0
            
            if apply_python_boosts:
                qname_boost = self._qualified_name_boost(query, func)
                class_boost = self._class_context_boost(query, func)
                decorator_boost = self._decorator_boost(query, func)
                
                if func.is_dunder and not self._query_wants_dunder(query):
                    score *= 0.5
                
                score += qname_boost + class_boost + decorator_boost
            
            reasons = []
            if qname_boost > 0: reasons.append(f"name:{qname_boost:.2f}")
            if class_boost > 0: reasons.append(f"class:{class_boost:.2f}")
            if decorator_boost > 0: reasons.append(f"deco:{decorator_boost:.2f}")
            
            results.append(SearchResult(
                function=func,
                score=score,
                bm25_score=bm25,
                semantic_score=semantic,
                qualified_name_boost=qname_boost,
                class_context_boost=class_boost,
                decorator_boost=decorator_boost,
                match_reason=", ".join(reasons) if reasons else "semantic"
            ))
        
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
    
    def _qualified_name_boost(self, query: str, func: ExtractedFunction) -> float:
        query_lower = query.lower()
        boost = 0.0
        if func.qualified_name.lower() in query_lower:
            boost += 0.3
        if func.class_name and func.class_name.lower() in query_lower:
            boost += 0.2
        if func.class_name:
            class_words = self._tokenize(func.class_name)
            query_words = set(self._tokenize(query))
            if any(cw in query_words for cw in class_words):
                boost += 0.1
        return boost
    
    def _class_context_boost(self, query: str, func: ExtractedFunction) -> float:
        if not func.class_docstring:
            return 0.0
        query_words = set(self._tokenize(query))
        class_doc_words = set(self._tokenize(func.class_docstring))
        overlap = len(query_words & class_doc_words)
        if overlap >= 2:
            return 0.15
        elif overlap >= 1:
            return 0.05
        return 0.0
    
    def _decorator_boost(self, query: str, func: ExtractedFunction) -> float:
        if not func.decorators:
            return 0.0
        query_lower = query.lower()
        decorators_str = " ".join(func.decorators).lower()
        
        route_keywords = ['route', 'endpoint', 'url', 'path', 'api', 'http']
        if any(kw in query_lower for kw in route_keywords):
            if '@app.route' in decorators_str or '@route' in decorators_str:
                return 0.2
        
        cli_keywords = ['command', 'cli', 'click']
        if any(kw in query_lower for kw in cli_keywords):
            if '@click' in decorators_str:
                return 0.2
        
        return 0.0
    
    def _query_wants_dunder(self, query: str) -> bool:
        dunder_keywords = ['__init__', '__str__', 'constructor', 'initialize', 'dunder']
        return any(kw in query.lower() for kw in dunder_keywords)


def run_evaluation(
    search_engine: PythonOptimizedSearch,
    ground_truth: List[Dict],
    verbose: bool = True
) -> Dict[str, Any]:
    """Run evaluation against ground truth."""
    hits = 0
    results_detail = []
    
    for item in ground_truth:
        query = item['query']
        expected = item['expected']
        
        results = search_engine.search(query, top_k=10)
        
        if results:
            top_result = results[0]
            is_hit = (
                top_result.function.qualified_name == expected or
                top_result.function.name == expected or
                expected in top_result.function.qualified_name
            )
            
            if is_hit:
                hits += 1
                status = "✅"
            else:
                status = "❌"
            
            if verbose:
                print(f"{status} {query[:50]}")
                print(f"   Expected: {expected} | Got: {top_result.function.qualified_name}")
    
    hit_rate = hits / len(ground_truth) if ground_truth else 0
    
    print(f"\n{'='*60}")
    print(f"🎯 Hit@1: {hit_rate*100:.1f}% ({hits}/{len(ground_truth)})")
    print(f"{'='*60}")
    
    return {'hit_at_1': hit_rate, 'hits': hits, 'total': len(ground_truth)}
