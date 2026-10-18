# Evaluation report: 02_agent_logic · 2026-10-18 09:28 UTC

Agent model `gpt-4o-mini` · embeddings `text-embedding-3-small` · judge `gpt-4.1` · top_k 4 · 66 questions

| Metric | Result |
|---|---|
| **Overall pass rate** (all checks pass) | **93.9%** |
| Routing accuracy (expected departments selected) | 96.9% (n=65) |
| Routing exact match (no extra departments) | 90.8% (n=65) |
| Retrieval hit rate (expected doc retrieved) | 100.0% (n=45) |
| Answer source correct (KB / web / direct / declined) | 100.0% (n=62) |
| Required facts present | 95.6% (n=45) |
| No forbidden/outdated content | 80.0% (n=5) |
| Faithfulness, mean claim support (LLM judge) | 100.0% |
| Fully faithful answers (every claim supported) | 100.0% (n=54) |
| Fabricated company policy on unanswerable questions (lower is better) | 0.0% |
| Latency p50 / p95 | 4.1s / 9.5s |
| Agent cost per question (est.) | $0.0004 |
| Errors | 0 |

## By category

| Category | Questions | Pass rate |
|---|---|---|
| ambiguous_term | 2 | 50.0% |
| cross_department | 6 | 66.7% |
| direct | 4 | 100.0% |
| hr | 16 | 100.0% |
| it | 16 | 100.0% |
| no_answer | 8 | 100.0% |
| outdated_trap | 4 | 75.0% |
| safety | 3 | 100.0% |
| vague | 3 | 100.0% |
| web | 4 | 100.0% |

## Failures

### hr14 (outdated_trap): When is benefits open enrollment?
- Failed checks: `forbidden`
- Route: private_kb ['hr'] · retrieved: hr_benefits_guide_2024_archived.md, hr_benefits_guide_2026.md
- Forbidden content present: ['October']
- Answer: Benefits open enrollment runs from November 1 to November 15, with changes taking effect on January 1 [1]. The previous document stated that open enrollment ran from October 15 to October 31, but this has been superseded by the current information [2].

### x04 (cross_department): I'm a new hire starting Monday. What do I need to do on day one for IT and HR?
- Failed checks: `facts`
- Route: private_kb ['it', 'hr'] · retrieved: hr_operations_runbook.md, it_new_hire_device_setup.md
- Missing facts: ['authenticator|MFA']
- Answer: On your first day, you need to ensure the following for IT and HR:  **IT Requirements:** - Confirm that your IT access request was submitted at least 10 business days before your start date. If it was not, your access may not be ready on day one [1]. - You will receive a standard 14-inch NovaBook laptop with 16 GB of memory, unless you are in an engineering or data role, in which case you will rec

### x06 (cross_department): Can I get reimbursed for my personal phone plan since I use it for work email?
- Failed checks: `routing, routing_exact`
- Route: private_kb ['hr'] · retrieved: hr_expense_and_travel_policy.md
- Answer: No, you cannot get reimbursed for your personal phone plan, as personal mobile phone plans are listed as non-reimbursable items [1].

### a01 (ambiguous_term): What counts as a P1?
- Failed checks: `routing, routing_exact, facts`
- Route: private_kb ['it'] · retrieved: service_desk_runbook.md
- Missing facts: ['payroll|salary']
- Answer: A P1 ticket is defined as a company-wide outage or a critical security incident [1].
