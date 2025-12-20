"""
CodeIntel - Unified Code Search System
======================================

A multi-language semantic code search system that understands
developer intent beyond simple keyword matching.

Supported Languages:
- Python (with class-aware extraction)
- JavaScript/TypeScript
- More coming: C, C++, Rust, Go, Java

Architecture:
    src/
    ├── extractors/          # Language-specific code extraction
    │   ├── base.py          # Abstract base extractor
    │   ├── python.py        # Python extractor (AST-based)
    │   ├── javascript.py    # JS/TS extractor
    │   └── registry.py      # Language detection & routing
    │
    ├── search/              # Search engines
    │   ├── base.py          # Abstract base search
    │   ├── bm25.py          # BM25 lexical search
    │   ├── semantic.py      # Embedding-based search
    │   ├── hybrid.py        # Combined search
    │   └── reranker.py      # LLM-based reranking
    │
    ├── indexer/             # Indexing pipeline
    │   ├── chunker.py       # Context-aware chunking
    │   ├── summarizer.py    # LLM summary generation
    │   └── embedder.py      # Vector embeddings
    │
    └── models/              # Data models
        └── function.py      # Function/method representation

Usage:
    from src import CodeIntel
    
    # Index a codebase
    ci = CodeIntel()
    ci.index("/path/to/repo")
    
    # Search
    results = ci.search("handle HTTP authentication")
"""

__version__ = "0.2.0"
__author__ = "Devanshu"
