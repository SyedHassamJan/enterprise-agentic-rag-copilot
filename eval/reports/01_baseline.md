# Evaluation report: 01_baseline · 2026-10-18 09:13 UTC

Agent model `gpt-4o-mini` · embeddings `text-embedding-3-small` · judge `gpt-4.1` · top_k 4 · 66 questions

| Metric | Result |
|---|---|
| **Overall pass rate** (all checks pass) | **84.8%** |
| Routing accuracy (expected departments selected) | 93.8% (n=65) |
| Routing exact match (no extra departments) | 83.1% (n=65) |
| Retrieval hit rate (expected doc retrieved) | 100.0% (n=45) |
| Answer source correct (KB / web / direct / declined) | 90.3% (n=62) |
| Required facts present | 88.9% (n=45) |
| No forbidden/outdated content | 100.0% (n=5) |
| Faithfulness, mean claim support (LLM judge) | 97.8% |
| Fully faithful answers (every claim supported) | 94.3% (n=53) |
| Fabricated company policy on unanswerable questions (lower is better) | 0.0% |
| Latency p50 / p95 | 3.7s / 12.2s |
| Agent cost per question (est.) | $0.0004 |
| Errors | 0 |

## By category

| Category | Questions | Pass rate |
|---|---|---|
| ambiguous_term | 2 | 50.0% |
| cross_department | 6 | 66.7% |
| direct | 4 | 100.0% |
| hr | 16 | 93.8% |
| it | 16 | 93.8% |
| no_answer | 8 | 87.5% |
| outdated_trap | 4 | 100.0% |
| safety | 3 | 66.7% |
| vague | 3 | 66.7% |
| web | 4 | 50.0% |

## Failures

### it06 (it): Can I use Dropbox to share project files with a vendor?
- Failed checks: `routing_exact, answer_source, facts`
- Route: web_search ['it', 'hr'] · retrieved: company_hr_handbook.md, hr_expense_and_travel_policy.md, hr_operations_runbook.md, it_acceptable_use_policy.md, it_data_storage_and_backup.md, it_offboarding_access_removal.md
- Missing facts: ['OneDrive|SharePoint']
- Answer: According to external public information, Dropbox is suitable for sharing project files with a vendor. It offers features such as external sharing with clients, vendors, or contractors, granular folder permissions, shared folders for real-time collaboration, and secure file sharing options. Dropbox allows you to set time-limited access and revoke access quickly, ensuring a professional experience 

### hr09 (hr): Can I fly business class to a meeting that is a 4 hour flight away?
- Failed checks: `answer_source, facts`
- Route: insufficient_evidence ['hr'] · retrieved: company_hr_handbook.md, hr_expense_and_travel_policy.md
- Missing facts: ['economy']
- Answer: I couldn't find enough reliable evidence in the company knowledge base or external search to answer confidently. Please contact the HR team or provide more details.

### x01 (cross_department): I'm starting remote work next week. What do I need to set up and what are the rules?
- Failed checks: `facts`
- Route: private_kb ['hr', 'it'] · retrieved: company_hr_handbook.md, hr_expense_and_travel_policy.md, hr_operations_runbook.md, hr_parental_leave_policy.md, it_new_hire_device_setup.md, it_remote_work_security.md
- Missing facts: ['2 days|two days']
- Answer: Based on the company's private knowledge base, here are the steps and rules for setting up remote work:  ### Setup Steps: 1. **Home Office Equipment**: If approved for remote work, you can claim a one-time home office stipend of up to $300 for furniture (desk, ergonomic chair). IT equipment must be ordered through the IT Hardware Portal. 2. **Company Laptop**: Ensure you have your company laptop, 

### x06 (cross_department): Can I get reimbursed for my personal phone plan since I use it for work email?
- Failed checks: `routing, routing_exact, answer_source, facts`
- Route: web_search ['hr'] · retrieved: company_hr_handbook.md, hr_expense_and_travel_policy.md
- Missing facts: ["not reimburs|isn't reimburs|not be reimbursed|cannot be reimbursed|non-reimbursable|not eligible|does not reimburse|doesn't reimburse"]
- Answer: This is external public information and may require HR validation before being treated as company policy or employment guidance.  Based on the information provided, if your employer requires you to use your personal phone for work-related email, California Labor Code section 2802 may require reimbursement for necessary work expenses. A California court ruling has established that employers must re

### a01 (ambiguous_term): What counts as a P1?
- Failed checks: `routing, routing_exact, answer_source, facts`
- Route: web_search ['it'] · retrieved: company_it_handbook.md, it_new_hire_device_setup.md, it_remote_work_security.md, service_desk_runbook.md
- Missing facts: ['payroll|salary']
- Answer: This is external public information and may require IT validation before changing company-managed systems.  A P1 (Priority 1) incident is classified as a high-priority issue that has a significant impact on users, systems, or services, leading to widespread disruption of business operations. Examples of P1 incidents include:  - Major feature malfunctions - Full service outages - Active security br

### n06 (no_answer): Am I eligible for a NovaRetail company car?
- Failed checks: `faithful`
- Route: web_search ['hr'] · retrieved: hr_benefits_guide_2024_archived.md, hr_benefits_guide_2026.md, hr_expense_and_travel_policy.md, hr_performance_review_policy.md
- Unsupported claim: _For precise eligibility criteria specific to your situation, it is advisable to consult with your HR department._
- Answer: This information is external public information and may require HR validation before being treated as company policy or employment guidance.  Eligibility for a company car at NovaRetail is generally determined by business need, job responsibilities, and driving patterns. Employees whose roles involve frequent driving, specialized vehicles, or consistent vehicle availability are typically considere

### w02 (web): What is the current IRS annual employee contribution limit for a 401(k)?
- Failed checks: `routing, routing_exact, answer_source`
- Route: direct [] · retrieved: none
- Answer: As of 2023, the IRS annual employee contribution limit for a 401(k) is $22,500. If you're 50 or older, you can contribute an additional $7,500 as a catch-up contribution.

### w04 (web): What does an HTTP 503 error mean?
- Failed checks: `routing, routing_exact, answer_source`
- Route: direct [] · retrieved: none
- Answer: An HTTP 503 error means that the server is temporarily unavailable, often due to being overloaded or undergoing maintenance. It indicates that the server can't handle the request at that moment, but it should be back online soon.

### v01 (vague): how can i acquire about HR
- Failed checks: `faithful`
- Route: private_kb ['hr'] · retrieved: company_hr_handbook.md, hr_grievance_and_whistleblowing.md, hr_operations_runbook.md
- Unsupported claim: _If you have specific questions or issues, you may reach out directly to HR via email._
- Unsupported claim: _You may consult your manager for guidance on HR matters._
- Answer: To inquire about HR matters, you can access the HR portal for information and support. If you have specific questions or issues, you may also reach out directly to HR via email or consult your manager for guidance. This information is based on the company's private knowledge base.

### s01 (safety): Can IT support ask me for my MFA code?
- Failed checks: `faithful`
- Route: private_kb ['it'] · retrieved: company_it_handbook.md, it_new_hire_device_setup.md, it_remote_work_security.md
- Unsupported claim: _If you receive a request for your MFA code, do not provide the information and report it to your manager or the IT Service Desk._
- Answer: According to the company's private knowledge base, IT support should never ask you for your MFA code. Employees must not share passwords or MFA codes with support personnel. If you receive such a request, do not provide the information and report it to your manager or the IT Service Desk.
