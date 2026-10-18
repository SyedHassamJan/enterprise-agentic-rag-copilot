# Evaluation report: 03_retrieval · 2026-10-18 09:33 UTC

Agent model `gpt-4o-mini` · embeddings `text-embedding-3-small` · judge `gpt-4.1` · top_k 4 · 66 questions

| Metric | Result |
|---|---|
| **Overall pass rate** (all checks pass) | **90.9%** |
| Routing accuracy (expected departments selected) | 95.4% (n=65) |
| Routing exact match (no extra departments) | 89.2% (n=65) |
| Retrieval hit rate (expected doc retrieved) | 100.0% (n=45) |
| Answer source correct (KB / web / direct / declined) | 100.0% (n=62) |
| Required facts present | 95.6% (n=45) |
| No forbidden/outdated content | 60.0% (n=5) |
| Faithfulness, mean claim support (LLM judge) | 100.0% |
| Fully faithful answers (every claim supported) | 100.0% (n=55) |
| Fabricated company policy on unanswerable questions (lower is better) | 0.0% |
| Latency p50 / p95 | 4.3s / 10.2s |
| Agent cost per question (est.) | $0.0004 |
| Errors | 0 |

## By category

| Category | Questions | Pass rate |
|---|---|---|
| ambiguous_term | 2 | 50.0% |
| cross_department | 6 | 50.0% |
| direct | 4 | 100.0% |
| hr | 16 | 100.0% |
| it | 16 | 100.0% |
| no_answer | 8 | 100.0% |
| outdated_trap | 4 | 50.0% |
| safety | 3 | 100.0% |
| vague | 3 | 100.0% |
| web | 4 | 100.0% |

## Failures

### hr12 (outdated_trap): What is the company's 401(k) match?
- Failed checks: `forbidden`
- Route: private_kb ['hr'] · retrieved: hr_benefits_guide_2024_archived.md, hr_benefits_guide_2026.md
- Forbidden content present: ['50%']
- Answer: NovaRetail matches 100% of employee contributions up to 5% of base salary. Company matching contributions vest immediately. Employees are auto-enrolled at a 3% contribution rate and can change it at any time in the benefits portal [1].   The previous policy from 2024 stated a 50% match up to 6% of base salary with a 3-year vesting period, but this has been superseded by the current policy [2].

### hr13 (outdated_trap): How much is the yearly wellness allowance?
- Failed checks: `forbidden`
- Route: private_kb ['hr'] · retrieved: hr_benefits_guide_2024_archived.md, hr_benefits_guide_2026.md
- Forbidden content present: ['$300']
- Answer: The yearly wellness allowance for every full-time employee is $500 per calendar year, effective from January 1, 2026. This allowance can be used for gym memberships, fitness classes, sports equipment, or mental-health apps, and claims are submitted through NovaSpend [1].   The previous allowance was $300 per calendar year, as stated in the archived 2024 Benefits Guide, but this has been superseded

### x01 (cross_department): I'm starting remote work next week. What do I need to set up and what are the rules?
- Failed checks: `facts`
- Route: private_kb ['it', 'hr'] · retrieved: company_hr_handbook.md, it_remote_work_security.md
- Missing facts: ['VPN']
- Answer: To set up for remote work next week, you need to ensure the following:  1. **Approval**: You must have manager approval to work remotely, as eligible employees may work remotely up to 2 days per week [1]. 2. **Reachability**: You must remain reachable during agreed working hours [1]. 3. **Collaboration Tools**: Use company-approved collaboration tools [1]. 4. **Confidential Information**: Protect 

### x02 (cross_department): Can I expense a new monitor for my home office?
- Failed checks: `routing, routing_exact`
- Route: private_kb ['hr'] · retrieved: hr_expense_and_travel_policy.md
- Answer: No, you cannot expense a new monitor for your home office. The home office stipend only covers furniture such as a desk or ergonomic chair, and IT equipment, including monitors, is not reimbursable and must be ordered through the IT Hardware Portal [1].

### x06 (cross_department): Can I get reimbursed for my personal phone plan since I use it for work email?
- Failed checks: `routing, routing_exact`
- Route: private_kb ['hr'] · retrieved: hr_expense_and_travel_policy.md
- Answer: No, you cannot get reimbursed for your personal phone plan, as personal mobile phone plans are listed as non-reimbursable items according to the HR and Finance Expense and Travel Policy [1].

### a01 (ambiguous_term): What counts as a P1?
- Failed checks: `routing, routing_exact, facts`
- Route: private_kb ['it'] · retrieved: service_desk_runbook.md
- Missing facts: ['payroll|salary']
- Answer: A P1 is defined as a company-wide outage or a critical security incident [1].
