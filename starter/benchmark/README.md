# Benchmark — Astronomy 2e, Chapters 3–4

File: [`questions.json`](questions.json) — 20 questions, fixed **before** any retrieval run on the real corpus.

## Composition

| | Dev | Test | Total |
|---|---:|---:|---:|
| Questions | 15 | 5 | 20 |
| Chapter 3 (`astronomy2e-ch03`) | 9 | 2 | 11 |
| Chapter 4 (`astronomy2e-ch04`) | 6 | 3 | 9 |
| With metadata filter (`chapter`) | 2 (q14, q15) | 2 (q16, q17) | 4 |

Types (label `type`): `direct` 5, `paraphrase` 6, `condition_exception` 5, `metadata_filter` 4 (q04 has two accepted gold pages: p95 and p88).

## How the split was made

- Split **by page/topic** to limit leakage: test questions use pages 101, 103 (section 3.4), 121 (4.2), 142, 144 (4.7); no dev question uses these pages, and section 3.4 is test-only.
- Remaining leakage risk: dev and test share the same two chapters and vocabulary (e.g., Kepler's second law appears in dev q04 and test q18); with only 5 test questions, results are illustrative only.
- Filter values are given **in the question context** ("In the chapter on …"), i.e., assumed user input before retrieval. They never contain the answer or the gold page.

## Evidence verification

- Every `evidence_quote` was copied from the normalized text in `results/pages.jsonl` and verified automatically with `python -m src.run check` (quote must appear verbatim, after whitespace/case normalization, on the gold page; filter values must exist in corpus metadata). Result: `Evidence check OK`.
- Each answer was also checked manually against the page text, including conditions (e.g., q12 "only century years divisible by 400").

## Strategy selection rule (fixed before running)

1. Highest **dev Evidence Hit@3**.
2. Tie → higher **dev Hit@1**.
3. Tie → higher **dev filter compliance** on filter questions.
4. Tie → fewer chunks / lower ingest time.

The test split is evaluated only once, after the strategy is chosen on dev. It is not used to tune chunk size, overlap or filters.

## Authorship note

Questions were drafted with AI assistance (Claude) from the normalized source text and must be reviewed by the student before the first experiment run; this is disclosed in the report as required by RULES.md.
