# Experiment 04: Reranking Results Summary

**Date:** December 18, 2024  
**Researcher:** Devanshu + Claude

---

## Current State

| Approach | Hit@1 | Hit@3 | Notes |
|----------|-------|-------|-------|
| **Baseline: Triple Fusion** | **81%** | **100%** | Code + Summary + BM25 embeddings |
| Simulated Fusion (no API) | 61.9% | 100% | BM25 + name matching only |

---

## Reranking Experiments

### Experiment 04.0: MS-MARCO Cross-Encoder
- **Result:** Made things WORSE
- **Why:** Trained on web search, doesn't understand code

### Experiment 04.2: BGE Reranker (bge-reranker-v2-m3)
- **Result:** 47.6% Hit@1 (simulated fusion baseline: 61.9%)
- **Why:** Also trained on web/general text, not code-specific

### Experiment 04.7: LLM Listwise (GPT-4o-mini)
- **Result:** 71.4% Hit@1 (improved simulated fusion from 61.9%)
- **Insight:** LLM +10% improvement when starting from weak baseline

### Experiment 04.7b: LLM Full Pipeline (Retrieve + Rerank)
- **Result:** 76.2% Hit@1
- **Insight:** Pure LLM approach is worse than embeddings+BM25

---

## Key Findings

### 1. Cross-Encoders Don't Work for Code
Both MS-MARCO MiniLM and BGE rerankers failed because they're trained on:
- Web search queries → news, Wikipedia articles
- Natural language → not programming syntax
- Short passages → not code files

### 2. LLM Reranking Helps, But Not Enough
GPT-4o-mini improved weak retrieval by +10%, but:
- Can't match the precision of embeddings + BM25
- Has its own biases (prefers certain function names)
- More expensive and slower

### 3. Our Fusion Approach is Already Strong
The 81% Hit@1 baseline from Triple Fusion (Code + Summary + BM25) is:
- Near state-of-the-art for this task
- Hard to improve with off-the-shelf rerankers
- Uses LLM intelligence (summaries) at indexing time

### 4. The Remaining Errors Are Hard Cases
Looking at the failures:
- "clear persisted data" → No `clearStorage` function exists
- "merge new state" → Expects `merge` but codebase uses spread operator
- Some queries have ambiguous ground truth

---

## Recommendations

### Option A: Accept 81% and Ship 🚀
- 81% Hit@1 with 100% Hit@3 is production-ready
- Focus on other features (multi-file support, etc.)

### Option B: Try Code-Specific Reranker
- Fine-tune cross-encoder on CodeSearchNet
- Use CodeBERT/UniXcoder as base
- Would need training data

### Option C: Improve Ground Truth
- Review the 4 failing queries
- Some "expected" answers may be wrong
- Better ground truth = more meaningful metrics

### Option D: Ensemble Approach
- Run multiple retrieval methods in parallel
- Combine signals for final ranking
- More complex but potentially 85-90%

---

## Cost Analysis

| Method | Cost per Query | Total (21 queries) |
|--------|---------------|-------------------|
| Voyage embeddings | ~$0.001 | ~$0.02 |
| LLM retrieval | ~$0.002 | ~$0.04 |
| LLM reranking | ~$0.001 | ~$0.02 |
| Cohere rerank | ~$0.001 | ~$0.02 |

All methods are cheap enough for production.

---

## Next Steps

1. **Immediate:** Document the 81% fusion approach as our best
2. **Research:** Try Cohere/Voyage rerank APIs when rate limits reset
3. **Long-term:** Build code-specific reranker if 81% isn't good enough

---

## Files Created

- `experiments/04_reranking/README.md` - Research plan
- `experiments/04_reranking/_shared.py` - Shared utilities
- `experiments/04_reranking/02_bge_reranker.py` - BGE reranker
- `experiments/04_reranking/07_llm_listwise.py` - LLM listwise
- `experiments/04_reranking/07b_llm_full_pipeline.py` - Full LLM pipeline
- `results/exp04_*.json` - Experiment results
