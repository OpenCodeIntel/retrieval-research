# OpenCodeIntel retrieval research

The experiments behind [OpenCodeIntel](https://github.com/OpenCodeIntel/opencodeintel)'s code search, run December 18 to 21, 2025. Everything needed to re-run the numbers is here: the query sets, the LLM summaries the search runs on, the scripts and the day-by-day log, including the parts that went wrong.

Written by [Devanshu Chicholikar](https://www.devanshuchicholikar.com).

## Results, with their conditions

**94% average Hit@1 across 14 open-source codebases** (Python, JavaScript/TypeScript, Java, Go; 9,941 functions; 665 queries). The full system fuses BM25, code embeddings and summary embeddings with reciprocal rank fusion, then reranks the top 10 with Voyage `rerank-2`. Without the reranker the same pipeline averages 78%. The 94% is an unweighted average of the per-codebase scores (93.9%). Source: the Day 6 scoreboard in [`RESEARCH_LOG.md`](RESEARCH_LOG.md). The evaluation script printed these scores to the console and they were recorded in the log; the console output itself was not saved, so there is no separate results file for this table. The inputs are committed, so it can be re-run (see below).

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
- **Reranking did the work; fusion added almost nothing on top.** In the ablation, with reranking on, the full fused system beat the best single component on only 1 of 7 codebases (Rich, +5 points), an average of +0.7. Without reranking, summary embeddings alone (84.1%) matched the full fusion (83.7%).
- **Example code inside a repo costs a lot.** FastAPI's 1,341 functions include 921 from its `docs_src` examples. On 20 hand-written FastAPI queries, strict Hit@1 was 30% on the full repo, 75% after accepting equally valid answers, and 95% on the core library alone (299 functions). The 100% in the table is on generated queries over the full repo.
- **Lodash's jump from 62% to 74% had three causes at once:** better summaries, relabeled ground truth and filtering out vendored code. It is not evidence for any one of them.
- **Two counting errors in the log, left as written:** the ablation is described as "224 queries" but its query files add up to 212, and the language table says "Python: 5 codebases, 3,837 functions" when the scoreboard has 4 Python codebases with 2,837 functions.
- **This is a research harness, not OpenCodeIntel's production search.** Production uses a different reranker (Cohere `rerank-v3.5`, never tested here). On production's own 10-query regression set, reranking raises Recall@10 from 0.80 to 0.85 but lowers MRR from 0.80 to 0.66 (see [`backend/evals`](https://github.com/OpenCodeIntel/opencodeintel/tree/main/backend/evals) in the main repo). So these results say how far the approach can go, not what production scores today.

## Reproduce it

You need Python 3.13 and a Voyage API key. An OpenAI API key is only needed for a codebase that has no committed summaries; the 14 scoreboard codebases already have theirs in `results/*_v2_summaries.json`, and the script loads them.

```bash
pip install -r requirements.txt
export VOYAGE_API_KEY=...        # the main scripts read keys from the environment
export OPENAI_API_KEY=...        # optional, see above

# Clone the codebases into test_repos/<name> at the commits that were indexed
# (table below), then score one codebase:
python3 scripts/evaluate_codebase.py fastapi

# Ablation: one codebase per run. The 98-run table used
# gorm, fiber, lodash, express, flask, rich and zustand.
python3 scripts/ablation_study.py gorm
```

Both scripts print their scores to the console. Embedding and reranking APIs change over time, so a re-run today may not match the December 2025 numbers exactly.

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
- `notes/`: plans and interim summaries written during the week. Several of their conclusions were overtaken; [`notes/README.md`](notes/README.md) lists which.
- `evals/`: query sets per codebase. `*_queries.json` are generated from function names, `*_human_queries.json` are hand-written.
- `results/`: the LLM summaries for each codebase, plus raw outputs from the Day 1 to 3 experiments (timestamped). The Day 6 scoreboard and the ablation were printed to the console, not saved here.
- `scripts/`: evaluation, ablation, reranking and fusion scripts.
- `experiments/`: the earlier day-by-day experiments (embeddings, hybrid search, summaries, reranking). The local BGE reranker experiment also needs `sentence-transformers`, which is not in `requirements.txt`.
- `src/`: tree-sitter function extraction.
- `run.sh`, `test_search_quality.py`, `test_real_codebase.py`: the Day 1 prototype, kept for the record.

## History

The commits are the original ones, December 18 to 21, 2025, with their original dates. Before publishing, an API key (since revoked) and local file paths were removed from every commit with `git filter-repo`; nothing else in the history was changed. The last commit (October 2026) adds this README, the license, pinned requirements and two hand-written query sets that were written on December 21 but never committed.

Work continued after December 21 but is not published here as results. A HyDE trial (December 31) saved no output, so its effect is unmeasured. A 170-query evaluation of a local search API over pandas (January 3 to 4) had its index rebuilt and 10 expected answers edited between runs, so its scores track development, not a fixed benchmark.

What came next is in the main repo: the hybrid retrieval and reranking work went into OpenCodeIntel's search (search v2 and v3, January 2026).

## License

MIT for the code and docs in this repo (see `LICENSE`). `results/` contains function code extracted from the open-source projects above. That code stays under each project's own license.
