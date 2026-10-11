# CodeIntel Semantic Search Research Plan
## Cofounder Discussion - December 18, 2025

---

## 🎯 HONEST ASSESSMENT OF CURRENT RESULTS

### What We Found:
| Approach | Top-1 Accuracy | Avg Score |
|----------|----------------|-----------|
| RAW_CODE | 41.7% | 0.277 |
| NL_DESCRIPTION | 50.0% | 0.301 |

### Is This Good?
**NO. This is bad.**

- 50% accuracy = wrong half the time = frustrated users
- Scores of 0.27-0.30 are LOW (good = 0.5+, great = 0.7+)
- 8% improvement is marginal, not transformative

### Why Are Results Bad?

1. **Embedding Model Issue**
   - `text-embedding-3-small` is GENERAL PURPOSE
   - Not optimized for code understanding
   - Trained on natural language, struggles with code semantics

2. **Query-Document Mismatch**
   - Users query in English: "how to authenticate"
   - Functions are named: `verify_repo_access`, `get_current_user`
   - Even with NL descriptions, the gap is huge

3. **Semantic Search Alone Isn't Enough**
   - Greptile uses: semantic + graph + keyword hybrid
   - Sourcegraph uses: trigram index + regex + semantic
   - We're using: just semantic (single vector similarity)

---

## 🔬 STRUCTURED RESEARCH PLAN

### Research Question:
**How can we achieve >80% Top-3 accuracy with >0.5 confidence scores for natural language code search?**

### Success Criteria:
| Metric | Current | Target | Stretch |
|--------|---------|--------|---------|
| Top-1 Accuracy | 50% | 70% | 85% |
| Top-3 Accuracy | 58% | 85% | 95% |
| Avg Score | 0.30 | 0.50 | 0.65 |
| Latency | N/A | <500ms | <200ms |

### Variables to Test (One at a Time):

#### 1. EMBEDDING MODELS (Highest Impact)
| Model | Type | Cost | Expected Benefit |
|-------|------|------|------------------|
| text-embedding-3-small | General | $0.02/1M | Baseline |
| text-embedding-3-large | General | $0.13/1M | +5-10% |
| voyage-code-2 | CODE-SPECIFIC | $0.12/1M | +20-30%? |
| voyage-code-3 | CODE-SPECIFIC | $0.18/1M | +25-35%? |
| Cohere embed-v3 | General | $0.10/1M | +10-15% |
| jina-embeddings-v3 | Code-aware | $0.02/1M | +15-20%? |

**Hypothesis:** Code-specific embeddings (Voyage) will significantly outperform general purpose.

#### 2. DESCRIPTION PROMPTS
| Variant | Focus | Expected Impact |
|---------|-------|-----------------|
| Current | What + Why | Baseline |
| Technical | Implementation details | Lower (more code-like) |
| User Intent | Use cases + scenarios | Higher? |
| Keywords | Searchable terms | Higher for keyword queries |
| Multi-aspect | All above combined | Highest? |

#### 3. HYBRID SEARCH STRATEGIES
| Strategy | How It Works | Complexity |
|----------|--------------|------------|
| Pure Semantic | Vector similarity only | Low |
| Keyword + Semantic | BM25 + vectors | Medium |
| Reranking | Semantic → LLM rerank top-20 | High |
| Graph-enhanced | Include dependency context | High |

#### 4. CHUNKING STRATEGIES
| Strategy | What We Embed | Trade-off |
|----------|---------------|-----------|
| Full function | Entire code | Context vs noise |
| Signature + docstring | Declaration only | Precise vs incomplete |
| Multi-chunk | Multiple representations | Cost vs coverage |

---

## 📋 EXPERIMENT ROADMAP

### Phase 1: Embedding Model Comparison (2-3 days)
**Goal:** Find best embedding model for code

```
Test Setup:
- Same 100 functions from Zustand repo
- Same 30 queries
- Compare: text-embedding-3-small vs voyage-code-2 vs jina-v3

Expected Output:
- Clear winner for code embeddings
- Cost/accuracy trade-off data
```

### Phase 2: Description Optimization (1-2 days)
**Goal:** Find optimal prompt for generating descriptions

```
Test Setup:
- Use winning embedding model
- Test 5 different prompt variants
- Measure accuracy improvement

Expected Output:
- Best prompt template
- Understanding of what makes good descriptions
```

### Phase 3: Hybrid Search (2-3 days)
**Goal:** Combine semantic with keyword search

```
Test Setup:
- Implement BM25 keyword search
- Test different fusion strategies
- Alpha tuning (semantic weight vs keyword weight)

Expected Output:
- Optimal hybrid configuration
- Fallback strategy for low-confidence results
```

### Phase 4: Reranking (2-3 days)
**Goal:** Use LLM to rerank top candidates

```
Test Setup:
- Get top-20 from semantic search
- Use GPT-4o-mini to rerank
- Compare with/without reranking

Expected Output:
- Reranking effectiveness data
- Cost/latency trade-offs
```

---

## 💰 RESEARCH BUDGET

| Phase | Estimated Cost | Time |
|-------|---------------|------|
| Phase 1: Embeddings | $5-10 | 2-3 days |
| Phase 2: Prompts | $2-5 | 1-2 days |
| Phase 3: Hybrid | $3-5 | 2-3 days |
| Phase 4: Reranking | $10-15 | 2-3 days |
| **Total** | **$20-35** | **7-11 days** |

---

## 🎯 DECISION POINT

After Phase 1 (embedding comparison), we'll know:
1. Is this approach viable? (Can we hit >70% accuracy?)
2. What's the cost structure?
3. Should we continue or pivot?

**If results are still bad after trying code-specific embeddings:**
- Consider: Is pure semantic search the wrong approach?
- Alternative: Build a keyword-first system with semantic augmentation
- Alternative: Focus on code graph/AST instead of embeddings

---

## 📁 TEST REPO SELECTION

### Why Zustand?
- Popular (40K+ stars)
- Well-documented
- Medium size (~50 files)
- Mix of simple + complex functions
- Good representation of real-world code

### Alternative Test Repos:
1. **Zustand** - State management (chosen)
2. **date-fns** - Utility library (many small functions)
3. **express** - Web framework (well-known patterns)

---

## ✅ IMMEDIATE NEXT STEPS

1. **Set up proper test harness**
   - Clone Zustand
   - Parse all functions
   - Create ground-truth query→function mappings

2. **Get Voyage AI API key**
   - Sign up at voyageai.com
   - Get code-specific embedding access

3. **Run Phase 1: Embedding Comparison**
   - Baseline: text-embedding-3-small
   - Test: voyage-code-2
   - Document results

4. **Decision checkpoint**
   - Review Phase 1 results
   - Decide: continue research or pivot strategy

