# CodeIntel Search Research: The Journey 🚀

> Building the best semantic code search - one experiment at a time.
> 
> "Hum isko best shape mein laayenge. Apne liye bana rahe hain, that's it."

---

## 📅 December 18, 2025 - Day 1: The Reality Check

### The Beginning

Aaj humne serious research shuru ki. CodeIntel ka search quality improve karna hai - not just incrementally, but significantly.

**Starting point:** Humara current search 41% accuracy de raha tha. Matlab half the time galat answer. Users ke liye ye frustrating hai.

**The question we asked:** Kya semantic search alone code search ke liye enough hai?

---

### What We Built Today

1. **Research Infrastructure**
   - Proper experiment framework with tree-sitter parsing
   - Ground truth queries for Zustand codebase
   - Multi-model comparison setup

2. **Test Environment**
   - Cloned Zustand repo (40K+ stars, real-world codebase)
   - Extracted 50+ functions using tree-sitter
   - Created 21 hard queries (natural language, no function name hints)

---

### Experiment 01: Embedding Model Showdown

**The Hypothesis:** Code-specific embeddings (Voyage) will crush general-purpose embeddings (OpenAI).

**Models Tested:**
| Model | Type | Dimensions |
|-------|------|------------|
| OpenAI text-embedding-3-small | General purpose | 1536 |
| Voyage voyage-code-2 | Code-specific | 1536 |
| Voyage voyage-code-3 | Code-specific (latest) | 1024 |

**The Results:**

```
Model                Hit@1      Hit@3      Avg Score   
──────────────────────────────────────────────────────
openai-small         19.0%      33.3%      0.4444      
voyage-code-2        14.3%      23.8%      0.8495   ← WTF moment
voyage-code-3        33.3%      38.1%      0.6265   ← Winner
```

---

### The WTF Moment 🤯

Voyage-code-2 gave **highest confidence scores (0.85)** but **lowest accuracy (14%)**!

Matlab: Bahut confidence se galat jawab de raha tha. 

**Lesson learned:** High similarity score ≠ correct answer. Different embedding models have different score distributions. You can't compare scores across models.

---

### The Honest Truth

**Voyage-code-3 won** with 33% accuracy - that's +14% over OpenAI.

But 33% is still **garbage**. 

Agar 3 mein se 2 baar galat answer de rahe ho, users kaise trust karenge?

---

### What This Means

**Pure semantic search alone is NOT enough for code search.**

Ye humari hypothesis thi, aur results ne confirm kar diya.

Greptile, Sourcegraph - ye sab hybrid approaches use karte hain for a reason. They've learned this lesson already.

---

### Key Insights

1. **Embedding model matters, but not enough**
   - Code-specific > general purpose (confirmed)
   - But even best model = 33% accuracy

2. **Score confidence is misleading**
   - voyage-code-2: High scores, wrong answers
   - Don't trust absolute scores, only relative ranking

3. **The problem is fundamental**
   - User queries: Natural language ("how to save state")
   - Code: Syntax + identifiers (`setState`, `persist`)
   - Even code-specific embeddings struggle with this gap

---

### What's Next?

Tomorrow we try **hybrid approaches**:

| Experiment | Approach | Why |
|------------|----------|-----|
| 02 | BM25 + Semantic | Keyword matching catches exact terms |
| 03 | Reranking with LLM | Let GPT-4 judge relevance |
| 04 | Query expansion | Expand "save state" → "persist, storage, localStorage" |
| 05 | Better chunking | Maybe we're embedding wrong things |

---

### Code Artifacts

- `experiments/01_embedding_comparison.py` - Full experiment code
- `results/exp01_20251218_121807.json` - Detailed results
- `test_repos/zustand/` - Test codebase

---

### Vibe Check

Thoda disappointing hai ki semantic search alone kaam nahi kar raha. But this is exactly why we're doing research - to find what actually works, not what we hope works.

The $180M funded competitors (Greptile, etc.) are using hybrid approaches. Ab samajh aa raha hai kyun.

**Mood:** Determined. We know what doesn't work. Now let's find what does.

---

### Tomorrow's Goals

1. Implement BM25 keyword search
2. Test hybrid (semantic + keyword) approach
3. Target: >60% Hit@1 accuracy

---

*"Failure is not the opposite of success, it's part of success."*


---

## 📊 Quick Stats (Updated: Dec 18, 2025)

| Metric | Baseline | Current Best | Target |
|--------|----------|--------------|--------|
| Hit@1 Accuracy | 19% (OpenAI) | 33% (Voyage-code-3) | 70%+ |
| Hit@3 Accuracy | 33% | 38% | 85%+ |
| Avg Score | 0.44 | 0.63 | 0.50+ |
| Experiments Run | 1 | 1 | 5-7 |

**Status:** 🔴 Not production ready. Need hybrid approach.

---

## 🗓️ Research Timeline

| Day | Date | Focus | Key Finding |
|-----|------|-------|-------------|
| 1 | Dec 18 | Embedding comparison | Voyage-code-3 best (+14%), but 33% not enough |
| 2 | Dec 19 | TBD | - |
| 3 | Dec 20 | TBD | - |

---

## 💡 Key Learnings (Running List)

1. **Semantic search alone ≠ code search solution** (Dec 18)
2. **High confidence scores can mean wrong answers** (Dec 18)
3. **Code-specific embeddings help, but not enough** (Dec 18)

---

## 🎯 The Goal

Build a code search that developers actually trust. Not 50% accuracy. Not 70%. We want **>85% relevance** on natural language queries.

If Greptile raised $25M at $180M valuation with this problem, there's clearly value here. But we need to solve it right.

---

## 📁 File Structure

```
codeintel-research/
├── RESEARCH_LOG.md          ← You are here (the story)
├── experiments/
│   └── 01_embedding_comparison.py
├── results/
│   └── exp01_20251218_*.json
├── test_repos/
│   └── zustand/             ← Test codebase
└── .env                     ← API keys (gitignored)
```

---

*Last updated: December 18, 2025 12:30 PM CST*

