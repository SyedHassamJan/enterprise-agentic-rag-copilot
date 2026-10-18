from dataclasses import dataclass


@dataclass(frozen=True)
class Department:
    key: str
    label: str
    namespace: str
    topics: str
    escalation: str
    validation: str


# Single source of truth for every knowledge domain the copilot serves.
# Adding a department = add an entry here + drop its documents in data/sample_kb/<key>/.
DEPARTMENTS: dict[str, Department] = {
    "it": Department(
        key="it",
        label="IT Support",
        namespace="it-kb",
        topics="VPN, passwords, MFA, laptops and devices, software installation, email, "
               "security incidents, troubleshooting, IT ticket priorities (P1-P4), BYOD/mobile, data storage",
        escalation="the IT Service Desk",
        validation="IT validation before changing company-managed systems",
    ),
    "hr": Department(
        key="hr",
        label="HR Policy",
        namespace="hr-kb",
        topics="leave and holidays, sick leave, remote work, working hours, payroll, benefits, "
               "onboarding, offboarding, employee records, expenses and travel, code of conduct, "
               "performance reviews, grievances, learning budget, company holidays, payroll issue priorities (P1-P4)",
        escalation="the HR team",
        validation="HR validation before being treated as company policy or employment guidance",
    ),
}


def get_department(key: str) -> Department:
    if key not in DEPARTMENTS:
        raise ValueError(f"Unknown department '{key}'. Valid: {', '.join(DEPARTMENTS)}")
    return DEPARTMENTS[key]
