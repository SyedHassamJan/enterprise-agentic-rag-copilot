# Evaluation

## Why

An agent that *looks* right in a demo can still contradict policy, quote outdated numbers or leak restricted data. The evaluation turns every claim in the README into a number you can reproduce.

## Golden set ([eval/golden_set.jsonl](../eval/golden_set.jsonl))

There are 72 questions, one JSON object per line:

```json
{"id": "hr12", "category": "outdated_trap", "role": "employee",
 "question": "What is the company's 401(k) match?",
 "expected_route": "kb", "expected_departments": ["hr"],
 "expected_sources": ["hr_benefits_guide_2026.md"],
 "must_include": ["100%", "5%"], "must_not_include": ["50%", "3 years"],
 "expected_answer_source": "private_kb"}
```

| Field | Meaning |
|---|---|
| `role` | Who is asking (default `employee`) |
| `expected_route` | `kb`, `web`, `direct`, or `any` |
| `expected_departments` | Must all be selected. An empty list means "any department" |
| `expected_sources` | At least one must be retrieved |
| `must_include` | Every group must appear in the answer. `a\|b` means "a or b" (case-insensitive; `1,500` matches `1500`) |
| `must_not_include` | None may appear. `{ADMIN_API_KEY}` is filled in at runtime, so the secret never goes into git |
| `expected_answer_source` | `private_kb`, `web_search`, `direct`, `not_private_kb`, or `any` |

The categories are: `it`, `hr`, `cross_department`, `ambiguous_term`, `outdated_trap`, `no_answer`, `web`, `direct`, `vague`, `safety` and `access_control`.

## Metrics

| Metric | Definition |
|---|---|
| Overall pass rate | Every applicable check passes (exact routing isn't required to pass) |
| Routing accuracy | The expected departments ⊆ the selected ones |
| Routing exact | No extra departments (a cost signal, not a correctness one) |
| Retrieval hit rate | At least one expected source was retrieved |
| Answer source | The answer came from the right place |
| Required facts | All `must_include` groups are present |
| Forbidden content | No `must_not_include` text is present |
| Faithfulness | The LLM judge splits the answer into claims; this is the share supported by the evidence the agent used |
| Fabricated policy | The share of unanswerable questions that were answered from the private KB anyway (lower is better) |
| Latency p50/p95, cost | Measured per question; cost estimated from token counts |

The judge (`gpt-4.1` by default) is stronger than the agent model and runs at temperature 0. It's told that referring the employee to an approved escalation contact counts as supported.

## Running

```powershell
python -m eval.run_eval                                  # full run -> eval/reports/latest.md + .json
python -m eval.run_eval --label exp_rerank_off           # also save as exp_rerank_off.md/.json
python -m eval.run_eval --category access_control --limit 4
python -m eval.run_eval --no-judge                       # cheaper: skip faithfulness
python -m eval.run_eval --rescore eval/reports/01_baseline.json   # re-apply current checks, no API calls
python -m eval.run_eval --min-pass-rate 0.90             # CI quality gate: exit 2 if below
```

A full run takes about 3 minutes with 4 workers. It costs roughly $0.03 for the agent plus $0.20 for the judge, and uses about 80 Pinecone re-rank requests.

## Reading a report

`eval/reports/<label>.md` has a summary table, pass rates by category, and a **Failures** section listing each failed check: route, retrieved files, missing facts, leaked content, unsupported claims, and the answer.

## Iteration history

| Stage | Report | Pass rate |
|---|---|---|
| Baseline | `01_baseline` | 84.8% |
| Agent logic (router, grader, citations) | `02_agent_logic` | 93.9% |
| Retrieval (contextual chunks, re-ranking) | `03_retrieval` | 90.9% |
| Enterprise controls (access control, lifecycle, guards) | `04_enterprise` | 97.2% |

## Caveats

- **Non-determinism:** expect about ±3 points between identical runs. Compare several runs before claiming a small gain.
- **Development set:** these questions guided development, so the scores are optimistic. Add a held-out split before making strong claims.
- **Golden-set changes are documented:** baseline numbers were re-scored with `--rescore` whenever the checks changed.
