"""Lightweight guardrails: prompt-injection screening and PII redaction.

These are deterministic first-line checks. They complement, not replace, the structural defences:
RBAC filtering at retrieval, prompts that treat documents as data, and answers restricted to
cited sources.
"""
import re

_INJECTION_PATTERNS = [
    r"\bignore (all |any |the )?(previous|prior|above|earlier) (instructions|prompts|rules)",
    r"\bdisregard (all |any |the )?(previous|prior|above|system) (instructions|prompts|rules)",
    r"\b(reveal|print|show|output|leak) (the |your )?(system prompt|(admin |api |secret )+key|password|secret)",
    r"\byou are now (a|an|in) ",
    r"\bnew (system )?instructions:",
    r"<\s*/?\s*(system|assistant)\s*>",
    r"\bact as (the )?(system|developer|admin)",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def detect_injection(text: str) -> list[str]:
    """Return the suspicious phrases found (empty list = clean)."""
    return [m.group(0) for m in _INJECTION_RE.finditer(text or "")]


_PII_RULES = [
    ("[EMAIL]", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("[CARD]", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("[SSN]", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("[PHONE]", re.compile(r"(?<!\w)(?:\+?\d{1,3}[ .-]?)?(?:\(\d{2,4}\)|\d{2,4})[ .-]?\d{3}[ .-]?\d{3,4}(?!\w)")),
]


def redact_pii(text: str) -> str:
    """Mask emails, card numbers, SSNs and phone numbers before text is stored in logs."""
    for token, pattern in _PII_RULES:
        text = pattern.sub(token, text)
    return text
