# Experiment 04: Reranking Research Plan

> **Note (October 2026):** this is the plan as written. Only `02_bge_reranker.py`, `07_llm_listwise.py` and `07b_llm_full_pipeline.py` exist; the other scripts listed below were never written, and Cohere was never tested. Results are in `RESULTS.md`. The Voyage reranker runs are in `scripts/` (see the repo README).

## CodeIntel Semantic Search Optimization

**Date:** December 18, 2025  
**Current Best:** 81% Hit@1 (Triple Fusion: Code + Summary + BM25)  
**Target:** 90%+ Hit@1  

---

## Research Summary

### Key Findings from Literature Review

#### 1. **Reranker Landscape (2024-2025)**

| Model | Type | Strengths | Weaknesses |
|-------|------|-----------|------------|
| **Voyage rerank-2.5** | API | Best overall (ELO 1547), 32K context | Rate limits, cost |
| **Cohere Rerank 4** | API | Fast (447ms), good accuracy | Slightly lower than Voyage |
| **BAAI/bge-reranker-v2-m3** | Local | Multilingual, free, fast | Not code-specific |
| **Jina Reranker v2** | Local/API | Good multilingual | Lower accuracy than top |
| **MS-MARCO MiniLM** | Local | Tiny, fast | Web-trained, not for code |

#### 2. **LLM Reranking Approaches**

| Approach | How it Works | Effectiveness |
|----------|--------------|---------------|
| **Pointwise** | Score each doc independently | Simple but suboptimal |
| **Pairwise (PRP)** | Compare pairs, aggregate | SOTA on TREC-DL |
| **Listwise (RankGPT)** | Rank entire list at once | Best but expensive |
| **FIRST** | Single token decoding | 50% faster, maintains quality |

#### 3. **Code-Specific Insights**

- **CodeXEmbed (Salesforce)**: 7B model, 20% better than Voyage-code on CoIR
- **CORNSTACK (Nomic AI)**: High-quality contrastive data for code retrieval
- **CodeBERT/UniXcoder**: Good for code understanding, can be used for reranking
- **Key insight**: Cross-encoders trained on web data (MS-MARCO) fail on code

#### 4. **What Works for Code Search**

1. **LLM summaries** (our Exp 03) - Bridges semantic gap ✅
2. **Code-specific embeddings** (Voyage-code-3) ✅
3. **Hybrid retrieval** (BM25 + semantic) ✅
4. **Code-aware rerankers** - NOT MS-MARCO models ⚠️

---

## Experiment Plan: Reranking Shootout

### Directory Structure

```
experiments/04_reranking/
├── README.md                  # This plan
├── _shared.py                 # Shared utilities, ground truth, fusion engine
├── 01_baseline.py             # No reranking (81% baseline)
├── 02_bge_reranker.py         # BAAI/bge-reranker-v2-m3 (local)
├── 03_cohere_rerank.py        # Cohere Rerank API
├── 04_voyage_rerank.py        # Voyage rerank-2 API
├── 05_llm_pointwise.py        # GPT-4o-mini pointwise scoring
├── 06_llm_pairwise.py         # GPT-4o-mini pairwise ranking (PRP)
├── 07_llm_listwise.py         # GPT-4o-mini listwise ranking
├── 08_hybrid_rerank.py        # Ensemble of best rerankers
└── compare_results.py         # Compare all approaches
```

---

## Sub-Experiments

### Experiment 04.1: Baseline (No Reranking)
**Status:** ✅ Done  
**Result:** 81% Hit@1, 100% Hit@3

### Experiment 04.2: BGE Reranker (Local)
**Model:** `BAAI/bge-reranker-v2-m3`  
**Why:** Free, fast, multilingual, widely used  
**Hypothesis:** Should improve over MS-MARCO model  
**Risk:** Not code-specific  

### Experiment 04.3: Cohere Rerank
**Model:** `rerank-english-v3.0` or `rerank-multilingual-v3.0`  
**Why:** Top-tier API, production-ready  
**Hypothesis:** Strong general reranking, may help  
**Risk:** API cost, rate limits  

### Experiment 04.4: Voyage Rerank
**Model:** `rerank-2` or `rerank-2-lite`  
**Why:** Best benchmark scores, same vendor as our embeddings  
**Hypothesis:** Best synergy with voyage-code-3 embeddings  
**Risk:** Rate limits (we already hit these)  

### Experiment 04.5: LLM Pointwise
**Model:** GPT-4o-mini  
**Approach:** Score each candidate 0-10 for relevance  
**Why:** Simple, interpretable  
**Risk:** May not rank well (absolute scores don't compare)  

### Experiment 04.6: LLM Pairwise (PRP)
**Model:** GPT-4o-mini  
**Approach:** Compare pairs, aggregate rankings  
**Why:** Research shows PRP outperforms pointwise  
**Risk:** O(n²) comparisons = expensive  

### Experiment 04.7: LLM Listwise
**Model:** GPT-4o-mini  
**Approach:** Rank entire list at once  
**Why:** Most powerful, single API call  
**Risk:** Position bias, may not follow format  

### Experiment 04.8: Hybrid Rerank
**Approach:** Ensemble of best performing rerankers  
**Why:** Combine strengths of multiple approaches  

---

## Evaluation Metrics

For each experiment, measure:
- **Hit@1** (primary) - Target: >81%
- **Hit@3** - Target: maintain 100%
- **Hit@5**
- **MRR** (Mean Reciprocal Rank)
- **Latency** (ms per query)
- **Cost** (API calls, tokens)

---

## Implementation Priority

### Phase 1: Quick Wins (Today)
1. ✅ 04.1 Baseline
2. 🔄 04.2 BGE Reranker (local, no API)
3. 🔄 04.5 LLM Pointwise (simple, OpenAI)
4. 🔄 04.7 LLM Listwise (most promising)

### Phase 2: API-Based (If needed)
5. 04.3 Cohere Rerank
6. 04.4 Voyage Rerank
7. 04.6 LLM Pairwise

### Phase 3: Optimization
8. 04.8 Hybrid ensemble

---

## Success Criteria

| Outcome | Next Step |
|---------|-----------|
| 90%+ Hit@1 | 🎉 Ship it! Document & integrate |
| 85-90% Hit@1 | Analyze failures, targeted fixes |
| <85% Hit@1 | Try ensemble of rerankers |

---

## Key Insights from Research

### Why MS-MARCO Failed (Exp 04.0)
- Trained on web search queries → news, Wikipedia
- Code has different vocabulary, structure
- Function names, syntax confuse the model

### What Should Work
1. **LLM reranking** - Understands code semantics natively
2. **Code-aware rerankers** - Voyage, potentially Cohere
3. **Instruction-following rerankers** - Can be guided with prompts

### The Big Bet: LLM Listwise
Research shows listwise LLM reranking is SOTA. With our summaries + code context, 
an LLM should be able to perfectly rank top 5 candidates.

**Expected cost:** ~21 queries × $0.001 = $0.02 per eval run

---

## Let's Go! 🚀
