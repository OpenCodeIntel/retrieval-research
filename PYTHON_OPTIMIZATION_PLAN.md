# Python Code Search Optimization - Research & Action Plan
## Date: December 19, 2025

---

## 📊 Current Problem

**JavaScript vs Python Gap:**
| Language | Average Hit@1 | Codebases |
|----------|---------------|-----------|
| JavaScript | 87.5% | Zustand, Express, Axios, Zod, Lodash |
| Python | 64.0% | Flask, Requests, Click |
| **Gap** | **23.5%** | |

**Root Causes Identified:**
1. Class-based patterns (methods inside classes)
2. Duplicate function names across files (e.g., "get", "name" appear 10+ times)
3. Dunder methods (__init__, __call__) pollution
4. Decorator patterns (@app.route, @click.command)
5. Property patterns (request.form, session['key'])

---

## 🔬 Research Findings

### Key Insight 1: Class-Aware Extraction (CRITICAL)

**Problem:** We extract `get()` but should extract `Session.get()` or `Request.get()`

**Solution from Research:**
- Use Python AST or Tree-sitter to extract **fully qualified names**
- Store as `ClassName.method_name` not just `method_name`
- Include class docstring + method docstring in index

**Implementation:**
```python
# Current: name = "get"
# New: name = "Session.get"
#      qualified_name = "requests.sessions.Session.get"
#      class_context = "Session manages HTTP connections..."
```

**Reference:** Sourcegraph's scip-python uses fully qualified names for precise navigation

---

### Key Insight 2: Hierarchical Chunking (from Qodo/LanceDB)

**Problem:** Large classes get chunked without context

**Solution:**
1. Create TWO indices:
   - **Class-level index**: Embed class docstring + method signatures
   - **Method-level index**: Embed individual methods WITH class context included

2. For each method chunk, INCLUDE:
   - Import statements
   - Class definition + __init__
   - The specific method

**Example:**
```python
# BAD (current approach):
"def get(self, url): ..."

# GOOD (with context):
"""
from urllib3 import HTTPConnectionPool
class Session:
    '''A Requests session manages persistent connections.'''
    def __init__(self): self.headers = {}
    def get(self, url): ...
"""
```

---

### Key Insight 3: Natural Language Descriptions (CRITICAL)

**Problem:** Code embeddings don't capture semantic meaning for natural language queries

**Solution from Qodo:**
- Generate natural language description for each chunk
- Embed description ALONGSIDE code
- Hybrid retrieval: semantic similarity on descriptions + BM25 on code

**Example:**
```python
# Code: def map_finish_reason(finish_reason): ...
# Generated description: "Python function that standardizes finish reasons 
#                         from various AI platforms to common terms"
```

This bridges the gap between "how do I make an HTTP request" and `requests.get()`

---

### Key Insight 4: Docstring + Inheritance Awareness

**Problem:** Python methods inherit from base classes, docstrings may be in parent

**Solution:**
- Walk class hierarchy to collect inherited docstrings
- Combine parent + child docstrings for complete context
- Index both the method AND what it inherits from

---

### Key Insight 5: Decorator-Aware Extraction

**Problem:** `@app.route`, `@click.command` decorators provide critical context

**Solution:**
- Extract decorator information as metadata
- Boost decorated functions in ranking
- Include decorator in the indexed content

**Example:**
```python
# Extract:
{
    "name": "index",
    "decorators": ["@app.route('/')"],
    "type": "route_handler",
    "code": "def index(): return render_template('index.html')"
}
```

---

### Key Insight 6: Two-Stage Retrieval + Re-ranking

**Problem:** Initial retrieval returns noisy results

**Solution from Qodo:**
1. **Stage 1:** Vector search + BM25 hybrid (retrieve top 50)
2. **Stage 2:** LLM re-ranking based on query relevance

---

## 🎯 Action Plan

### Phase 1: Enhanced Python Extraction Pipeline

**Goal:** Extract richer context from Python codebases

**Tasks:**
1. **Class-aware extraction**
   - Extract `ClassName.method_name` as the indexed name
   - Include class docstring with each method
   - Track inheritance hierarchy

2. **Decorator extraction**
   - Parse @decorators and include in metadata
   - Flag route handlers, CLI commands, etc.

3. **Docstring inheritance**
   - Walk MRO (Method Resolution Order) to find docstrings
   - Combine parent + child documentation

**Files to create:**
```
experiments/
├── python_extractor_v2.py      # Enhanced AST-based extractor
├── test_python_extractor.py    # Test on Flask/Requests/Click
```

---

### Phase 2: Context-Rich Chunking

**Goal:** Each chunk has full context needed to understand it

**Tasks:**
1. **Hierarchical indexing**
   - Create class-level embeddings (overview)
   - Create method-level embeddings (detail + class context)

2. **Context injection**
   - Add imports to each method chunk
   - Add class definition to each method chunk
   - Add __init__ to each method chunk

3. **Natural language descriptions**
   - Generate LLM summaries that describe WHAT the code does
   - Index descriptions alongside code

**Files to create:**
```
experiments/
├── context_rich_chunker.py     # Chunking with full context
├── description_generator.py    # LLM descriptions for code
```

---

### Phase 3: Improved Search Engine

**Goal:** Better retrieval for Python patterns

**Tasks:**
1. **Qualified name matching**
   - If query mentions "Session", boost Session.* methods
   - If query mentions "request", boost Request.* methods

2. **Decorator-aware ranking**
   - Boost @app.route for web framework queries
   - Boost @click.command for CLI queries

3. **Hybrid retrieval**
   - BM25 on code (exact matches)
   - Embeddings on descriptions (semantic matches)
   - Combine scores with tuned weights

**Files to create:**
```
experiments/
├── python_search_v4.py         # Python-optimized search
├── run_python_v4_eval.py       # Evaluation script
```

---

### Phase 4: Re-ranking Layer

**Goal:** Use LLM to filter and re-rank initial results

**Tasks:**
1. Retrieve top-50 candidates
2. Use LLM to score relevance (0-10) for each
3. Re-rank based on LLM scores

---

## 📋 Concrete Implementation Checklist

### Extraction Changes
- [ ] Extract qualified names: `ClassName.method_name`
- [ ] Include class docstring with methods
- [ ] Track decorator information
- [ ] Walk inheritance hierarchy for docstrings
- [ ] Mark public vs private functions

### Indexing Changes  
- [ ] Create dual index (class-level + method-level)
- [ ] Include imports in method chunks
- [ ] Include class context in method chunks
- [ ] Generate natural language descriptions
- [ ] Create separate embedding for description

### Search Changes
- [ ] Qualified name matching
- [ ] Decorator-aware boosting
- [ ] Hybrid retrieval (BM25 + semantic)
- [ ] Two-stage retrieval with re-ranking

---

## 📊 Expected Improvements

Based on research findings:

| Change | Expected Impact |
|--------|----------------|
| Qualified names (Session.get) | +5-10% |
| Class context in chunks | +5-8% |
| Natural language descriptions | +8-12% |
| Decorator-aware ranking | +3-5% |
| Two-stage re-ranking | +5-8% |

**Target:** Improve Python from 64% → 80%+ Hit@1

---

## 🔗 Key References

1. **Qodo RAG Blog** - Intelligent chunking, LLM descriptions
   https://www.qodo.ai/blog/rag-for-large-scale-code-repos/

2. **LanceDB Codebase RAG Part 2** - Hybrid search, re-ranking
   https://lancedb.com/blog/building-rag-on-codebases-part-2/

3. **Sourcegraph scip-python** - Precise Python indexing
   https://sourcegraph.com/blog/scip-python

4. **Tree-sitter Python** - AST parsing for extraction
   https://github.com/tree-sitter/tree-sitter-python

5. **PEP 3155** - Qualified names for classes/functions
   https://peps.python.org/pep-3155/

---

## 🚀 Next Steps (Priority Order)

1. **TODAY:** Create enhanced Python extractor with qualified names
2. **NEXT:** Test on Flask - compare old vs new extraction
3. **THEN:** Add context-rich chunking (class context in method chunks)
4. **AFTER:** Generate natural language descriptions
5. **FINALLY:** Implement hybrid retrieval + re-ranking

---

*"The biggest insight: We're indexing Python like JavaScript, but Python is fundamentally different. Class.method, not just method."*

*Logged: December 19, 2025*
