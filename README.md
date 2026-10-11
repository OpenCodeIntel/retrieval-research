# OpenCodeIntel retrieval research

The experiments behind [OpenCodeIntel](https://github.com/OpenCodeIntel/opencodeintel)'s code search, run December 18 to 21, 2025. Everything needed to check the numbers is here: the query sets, the raw results, the scripts and the day-by-day log, including the parts that went wrong.

Written by [Devanshu Chicholikar](https://www.devanshuchicholikar.com).

## Results, with their conditions

**94% average Hit@1 across 14 open-source codebases** (Python, JavaScript/TypeScript, Java, Go; 9,941 functions; 665 queries). The full system fuses BM25, code embeddings and summary embeddings with reciprocal rank fusion, then reranks the top 10 with Voyage `rerank-2`. Without the reranker the same pipeline averages 78%. The 94% is an unweighted average of the per-codebase scores (93.9%). Source: the Day 6 scoreboard in [`RESEARCH_LOG.md`](RESEARCH_LOG.md).

| Codebase | Language | Functions | Fusion only | + Rerank |
|---|---|---|---|---|
| Rich | Python | 910 | 100% | 100% |
| Zustand | TypeScript | 33 | 78% | 100% |
| FastAPI | Python | 1,341 | 96% | 100% |
| Retrofit | Java | 2,224 | 78% | 100% |
| Gson | Java | 3,082 | 80% | 100% |
| GORM | Go | 104 | 82% | 100% |
| OkHttp | Java | 253 | 86% | 98% |
| Lodash | JavaScript | 745 | 64% | 96% |
| Fiber | Go | 374 | 74% | 92% |
| Echo | Go | 133 | 72% | 92% |
| Express | JavaScript | 115 | 70% | 88% |
| Axios | JavaScript | 41 | 73% | 88% |
| Requests | Python | 230 | 84% | 88% |
| Flask | Python | 356 | 60% | 72% |

**The reranker's contribution, isolated.** A 98-run ablation (14 configurations across 7 codebases, using the human-written query sets where they exist) puts the full system at 92.1% and the same system without reranking at 83.7%: **+8.4 points**. Summary embeddings alone scored 84.1%, code embeddings alone 78.1% and BM25 alone 68.7%. Source: the Day 7 ablation in `RESEARCH_LOG.md` and [`scripts/ablation_study.py`](scripts/ablation_study.py).

**Human-written queries.** On 20 hand-written queries for Fiber, fusion found the right function first 80% of the time, and 85% with reranking (strict scoring).

## Read this before quoting the 94%

- **Most queries are generated from function names.** `CreateBatchInBatches` becomes "create batch in batches", so the query shares words with the answer. That is easier than real searches. The log's own estimate for real-world queries is 70 to 80%. The human-written sets in `evals/*_human_queries.json` exist to check this: Fiber scored 85% on its hand-written queries against 92% on its generated ones.
- **The same reranker hurt before it helped.** On Day 2, with a weaker first stage and uncorrected labels on 21 Zustand queries, rerankers trained on web text made results worse (BGE `bge-reranker-v2-m3`: 61.9% to 47.6% against its own baseline), and so did Voyage `rerank-2` itself (76.2% to 66.7%, 2 queries better and 4 worse; `results/exp04_20251218_173747.json`). From Day 5, with a proper fused first stage, a top-10 candidate set and corrected labels, the same Voyage reranker helped on every codebase reported. A reranker amplifies whatever it is handed.
- **Lodash's jump from 62% to 74% had three causes at once:** better summaries, relabeled ground truth and filtering out vendored code. It is not evidence for any one of them.
- **Two counting errors in the log, left as written:** the ablation is described as "224 queries" but its query files add up to 212, and the language table says "Python: 5 codebases, 3,837 functions" when the scoreboard has 4 Python codebases with 2,837 functions.
- **This is a research harness, not OpenCodeIntel's production search.** Production uses a different reranker (Cohere `rerank-v3.5`, never tested here). On production's own 10-query regression set, reranking raises Recall@10 from 0.80 to 0.85 but lowers MRR from 0.80 to 0.66 (see [`backend/evals`](https://github.com/OpenCodeIntel/opencodeintel/tree/main/backend/evals) in the main repo). So these results say how far the approach can go, not what production scores today.

## Reproduce it

You need Python 3.13, a Voyage API key and an OpenAI API key (for summaries).

```bash
pip install -r requirements.txt
export VOYAGE_API_KEY=...        # or put it in .env, see .env.example
export OPENAI_API_KEY=...

# Clone the codebases into test_repos/ at the commits that were indexed
# (table below), then run one codebase:
python3 scripts/evaluate_codebase.py fastapi

# Ablation across configurations
python3 scripts/ablation_study.py
```

Results are written to `results/`. The committed files in `results/` are the original runs.

| Codebase | Repository | Commit |
|---|---|---|
| axios | github.com/axios/axios | 21df8edc8a90 |
| echo | github.com/labstack/echo | 321530d2c2d1 |
| express | github.com/expressjs/express | 9eb700151b68 |
| fastapi | github.com/tiangolo/fastapi | c2c1cc8aec83 |
| fiber | github.com/gofiber/fiber | 6808448110e8 |
| flask | github.com/pallets/flask | 2579ce9f18e6 |
| gorm | github.com/go-gorm/gorm | e98dccce2fbb |
| gson | github.com/google/gson | d43795417185 |
| lodash | github.com/lodash/lodash | 19c9251b3631 |
| okhttp | github.com/square/okhttp | ace792f443b2 |
| requests | github.com/psf/requests | 70298332899f |
| retrofit | github.com/square/retrofit | 92ce2cb09b99 |
| rich | github.com/Textualize/rich | f82a399d5840 |
| zustand | github.com/pmndrs/zustand | 234a948a05ba |

Click and Zod also have query sets in `evals/` from earlier experiments; they are not part of the 14-codebase scoreboard.

## What is where

- `RESEARCH_LOG.md`: the day-by-day log, failures included. Start here.
- `FINAL_RESULTS.md`, `RESEARCH_SUMMARY.md`: summaries written at the end of the week.
- `evals/`: query sets per codebase. `*_queries.json` are generated from function names, `*_human_queries.json` are hand-written.
- `results/`: raw outputs of every run, timestamped.
- `scripts/`: evaluation, ablation, reranking and fusion scripts.
- `experiments/`: the earlier day-by-day experiments (embeddings, hybrid search, summaries, reranking).
- `src/`: tree-sitter function extraction.

## History

The commits are the original ones, December 18 to 21, 2025, with their original dates. Before publishing, an API key (since revoked) and local file paths were removed from every commit with `git filter-repo`; nothing else in the history was changed. The last commit (October 2026) adds this README, the license, pinned requirements and two hand-written query sets that were written on December 21 but never committed.

What came next is in the main repo: the hybrid retrieval and reranking work went into OpenCodeIntel's search (search v2 and v3, January 2026).

## License

MIT for the code and docs in this repo (see `LICENSE`). `results/` contains function code extracted from the open-source projects above. That code stays under each project's own license.
