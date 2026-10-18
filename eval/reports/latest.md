# Evaluation report: 04_enterprise · 2026-10-18 09:48 UTC

Agent model `gpt-4o-mini` · embeddings `text-embedding-3-small` · judge `gpt-4.1` · top_k 4 · 72 questions

| Metric | Result |
|---|---|
| **Overall pass rate** (all checks pass) | **97.2%** |
| Routing accuracy (expected departments selected) | 97.2% (n=71) |
| Routing exact match (no extra departments) | 91.5% (n=71) |
| Retrieval hit rate (expected doc retrieved) | 100.0% (n=48) |
| Answer source correct (KB / web / direct / declined) | 100.0% (n=67) |
| Required facts present | 97.9% (n=48) |
| No forbidden/outdated content | 100.0% (n=8) |
| Faithfulness, mean claim support (LLM judge) | 100.0% |
| Fully faithful answers (every claim supported) | 100.0% (n=57) |
| Fabricated company policy on unanswerable questions (lower is better) | 0.0% |
| Latency p50 / p95 | 4.3s / 10.8s |
| Agent cost per question (est.) | $0.0004 |
| Errors | 0 |

## By category

| Category | Questions | Pass rate |
|---|---|---|
| access_control | 6 | 100.0% |
| ambiguous_term | 2 | 50.0% |
| cross_department | 6 | 83.3% |
| direct | 4 | 100.0% |
| hr | 16 | 100.0% |
| it | 16 | 100.0% |
| no_answer | 8 | 100.0% |
| outdated_trap | 4 | 100.0% |
| safety | 3 | 100.0% |
| vague | 3 | 100.0% |
| web | 4 | 100.0% |

## Failures

### x06 (cross_department, as employee): Can I get reimbursed for my personal phone plan since I use it for work email?
- Failed checks: `routing, routing_exact`
- Route: private_kb ['hr'] · retrieved: hr_expense_and_travel_policy.md
- Answer: No, you cannot get reimbursed for your personal phone plan, as personal mobile phone plans are listed as non-reimbursable items according to the policy [1].

### a01 (ambiguous_term, as employee): What counts as a P1?
- Failed checks: `routing, routing_exact, facts`
- Route: private_kb ['it'] · retrieved: service_desk_runbook.md
- Missing facts: ['payroll|salary']
- Answer: A P1 is defined as a company-wide outage or a critical security incident [1].
