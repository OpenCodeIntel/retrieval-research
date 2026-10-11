# Working notes

Documents written during the week of December 18 to 21, 2025, kept as written. They record what was believed at the time, and several of their conclusions were overtaken by later days. The current summary, with the final numbers and their caveats, is the [repo README](../README.md).

Read them with these corrections:

- **`FINAL_RESULTS.md`** (Dec 18 to 19) reports 87.5% Hit@1 for JavaScript and 75.8% overall on 8 codebases. That was before the fused pipeline and the Voyage reranker. The 87.5% covers JavaScript codebases only, and the per-codebase numbers differ from the final scoreboard.
- **`RESEARCH_SUMMARY.md`** and **`DEEP_RESEARCH_FINDINGS.md`** say 81% Hit@1 is "competitive with state-of-the-art". That was one 21-query run on Zustand, compared against published numbers that use a different metric (MRR on CodeSearchNet). It is not a valid comparison.
- **`RESEARCH_PLAN.md`** is the plan written on Day 1, before any results.
- **`PYTHON_OPTIMIZATION_PLAN.md`** is the plan for closing the Python gap on Day 3.
- **`ARCHITECTURE.md`** describes how the research harness was meant to connect to the product (Pinecone, Redis, hosting). This repo does not use that stack.
