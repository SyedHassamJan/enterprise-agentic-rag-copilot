"""Offline evaluation of the agent against eval/golden_set.jsonl.

Runs every question through the real graph (OpenAI + Pinecone + Tavily) and scores:

  routing          expected departments are all selected (and "exact" = nothing extra)
  retrieval_hit    at least one expected source document was retrieved
  answer_source    answered from the right place (private KB / web / direct / declined)
  facts            every must_include fact group appears in the answer
  forbidden        no must_not_include text appears (e.g. superseded 2024 policy values)
  faithfulness     LLM judge: share of answer claims supported by the evidence it was given

Usage:
    python -m eval.run_eval                     # full run
    python -m eval.run_eval --category hr --limit 5
    python -m eval.run_eval --judge-model gpt-4.1 --workers 4
"""
import argparse
import json
import re
import statistics
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from langchain_core.callbacks import get_usage_metadata_callback
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.rag.departments import DEPARTMENTS
from app.rag.workflow import ask

EVAL_DIR = Path(__file__).resolve().parent
REPORT_DIR = EVAL_DIR / "reports"
settings = get_settings()

# USD per 1M tokens (input, output). Estimates at list price; update if pricing changes.
PRICES = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4o": (2.50, 10.00),
}


def price_for(model: str):
    for prefix in sorted(PRICES, key=len, reverse=True):
        if model.startswith(prefix):
            return PRICES[prefix]
    return None


def usage_cost(usage: dict) -> tuple[int, float | None]:
    tokens, cost = 0, 0.0
    for model, u in usage.items():
        tokens += u.get("total_tokens", 0)
        p = price_for(model)
        if p is None:
            cost = None
        elif cost is not None:
            cost += u.get("input_tokens", 0) / 1e6 * p[0] + u.get("output_tokens", 0) / 1e6 * p[1]
    return tokens, cost


def normalize(text: str) -> str:
    text = text.lower().replace("’", "'")
    return re.sub(r"(?<=\d),(?=\d)", "", text)  # 1,500 -> 1500


def contains(answer: str, group: str) -> bool:
    a = normalize(answer)
    return any(normalize(alt.strip()) in a for alt in group.split("|"))


class Claim(BaseModel):
    claim: str
    supported: bool


class Judgement(BaseModel):
    claims: list[Claim] = Field(default_factory=list)


JUDGE_PROMPT = """You are a strict evaluator of a company support assistant.
Split the ANSWER into atomic factual claims (policies, numbers, deadlines, contacts, tools, steps, permissions).
Do NOT include meta statements such as "this is based on the knowledge base" or "this is external information".
For each claim, mark supported=true only if the EVIDENCE explicitly states it or it follows directly from it.
Advice that the evidence does not mention (for example "email HR directly") is NOT supported.
Referring the employee to a contact listed under [Approved escalation contacts] IS supported.

QUESTION:
{question}

EVIDENCE:
{evidence}

ANSWER:
{answer}"""


def judge_faithfulness(judge, question: str, evidence: str, answer: str):
    with get_usage_metadata_callback() as cb:
        verdict = judge.invoke(JUDGE_PROMPT.format(question=question, evidence=evidence, answer=answer))
    claims = [c.model_dump() for c in verdict.claims]
    score = 1.0 if not claims else sum(c["supported"] for c in claims) / len(claims)
    return score, claims, cb.usage_metadata


def evaluate(item: dict, judge) -> dict:
    row = {"id": item["id"], "category": item["category"], "question": item["question"],
           "role": item.get("role", "employee"), "checks": {}}
    try:
        with get_usage_metadata_callback() as cb:
            t0 = time.perf_counter()
            result = ask(item["question"], user_role=item.get("role", "employee"))
            row["latency_s"] = round(time.perf_counter() - t0, 2)
        row["tokens"], row["cost_usd"] = usage_cost(cb.usage_metadata)
    except Exception as exc:  # a crash is a failed question, not a failed eval run
        row["error"] = f"{type(exc).__name__}: {exc}"
        row["passed"] = False
        return row

    answer, source = result.get("answer", ""), result.get("source_used", "")
    predicted = result.get("departments", [])
    retrieved = sorted({Path(d.metadata.get("source", "")).name for d in result.get("kb_docs", [])})
    row.update(answer=answer, source_used=source, route=result.get("route"), departments=predicted,
               retrieved_sources=retrieved, trace=result.get("trace", []))

    # Faithfulness to the evidence the agent actually used
    evidence = ""
    if source == "private_kb":
        evidence = "\n\n".join(f"[{Path(d.metadata.get('source', '')).name}]\n{d.page_content}" for d in result["kb_docs"])
        contacts = [DEPARTMENTS[k].escalation for k in predicted if k in DEPARTMENTS]
        if contacts:  # the agent is instructed to refer employees to these official contacts
            evidence += "\n\n[Approved escalation contacts]\n" + "; ".join(contacts)
    elif source == "web_search":
        evidence = result.get("web_results", "")
    if evidence and judge is not None:
        score, claims, judge_usage = judge_faithfulness(judge, item["question"], evidence, answer)
        row["faithfulness"] = round(score, 3)
        row["unsupported_claims"] = [c["claim"] for c in claims if not c["supported"]]
        row["judge_tokens"], row["judge_cost_usd"] = usage_cost(judge_usage)
        row["checks"]["faithful"] = score == 1.0

    return score_checks(item, row)


def score_checks(item: dict, row: dict) -> dict:
    """Deterministic checks on a finished row. Reused by --rescore on saved results."""
    answer, source, predicted = row["answer"], row["source_used"], row["departments"]
    retrieved = row["retrieved_sources"]
    checks = {"faithful": row["checks"]["faithful"]} if "faithful" in row.get("checks", {}) else {}
    row["checks"] = checks
    row.pop("missing_facts", None)
    row.pop("leaked", None)

    # Routing
    if item["expected_route"] == "direct":
        checks["routing"] = source == "direct"
        checks["routing_exact"] = checks["routing"]
    elif item["expected_route"] == "web":
        # Public-knowledge question: routing straight to web, or KB-first then web fallback, are both acceptable.
        checks["routing"] = row.get("route") == "web" or source == "web_search"
        checks["routing_exact"] = row.get("route") == "web"
    elif item["expected_route"] == "kb":
        # An empty expected_departments list means "any department" (e.g. the answer exists nowhere).
        expected = set(item["expected_departments"])
        checks["routing"] = source != "direct" and expected <= set(predicted)
        checks["routing_exact"] = source != "direct" and (not expected or expected == set(predicted))

    # Retrieval
    if item["expected_sources"]:
        checks["retrieval_hit"] = bool(set(item["expected_sources"]) & set(retrieved))

    # Where the answer came from
    expected_src = item["expected_answer_source"]
    if expected_src == "not_private_kb":
        checks["answer_source"] = source != "private_kb"
    elif expected_src != "any":
        checks["answer_source"] = source == expected_src

    # Facts
    if item.get("must_include"):
        missing = [g for g in item["must_include"] if not contains(answer, g)]
        checks["facts"] = not missing
        if missing:
            row["missing_facts"] = missing
    forbidden = [f.replace("{ADMIN_API_KEY}", settings.admin_api_key) for f in item.get("must_not_include", [])]
    if forbidden:
        leaked = [f for f in forbidden if f and normalize(f) in normalize(answer)]
        checks["forbidden"] = not leaked
        if leaked:
            row["leaked"] = ["<admin key>" if f == settings.admin_api_key else f for f in leaked]

    # Over-routing (extra departments) costs latency but is not a wrong answer: tracked, not gating.
    row["passed"] = all(v for k, v in checks.items() if k != "routing_exact")
    return row


def rate(rows, key):
    vals = [r["checks"][key] for r in rows if key in r.get("checks", {})]
    return (sum(vals) / len(vals), len(vals)) if vals else (None, 0)


def pct(v):
    return "n/a" if v is None else f"{v * 100:.1f}%"


def summarize(rows: list[dict]) -> dict:
    ok = [r for r in rows if "error" not in r]
    lat = sorted(r["latency_s"] for r in ok)
    costs = [r["cost_usd"] for r in ok if r.get("cost_usd") is not None]
    faith = [r["faithfulness"] for r in ok if "faithfulness" in r]
    no_answer = [r for r in ok if r["category"] in ("no_answer",) or r["id"] == "s02"]
    return {
        "questions": len(rows),
        "errors": len(rows) - len(ok),
        "pass_rate": sum(r["passed"] for r in rows) / len(rows),
        "routing": rate(ok, "routing"),
        "routing_exact": rate(ok, "routing_exact"),
        "retrieval_hit": rate(ok, "retrieval_hit"),
        "answer_source": rate(ok, "answer_source"),
        "facts": rate(ok, "facts"),
        "forbidden_clean": rate(ok, "forbidden"),
        "faithfulness_mean": statistics.mean(faith) if faith else None,
        "fully_faithful": rate(ok, "faithful"),
        "fabricated_company_policy": (sum(r["source_used"] == "private_kb" for r in no_answer) / len(no_answer)) if no_answer else None,
        "latency_p50_s": statistics.median(lat) if lat else None,
        "latency_p95_s": lat[min(len(lat) - 1, int(round(0.95 * (len(lat) - 1))))] if lat else None,
        "cost_per_question_usd": statistics.mean(costs) if costs else None,
    }


def markdown_report(meta: dict, summary: dict, rows: list[dict]) -> str:
    def r(key):
        v, n = summary[key]
        return f"{pct(v)} (n={n})"

    lines = [
        f"# Evaluation report: {meta.get('label') or 'run'} · {meta['timestamp']}",
        "",
        f"Agent model `{meta['model']}` · embeddings `{meta['embedding_model']}` · judge `{meta['judge_model']}` · "
        f"top_k {meta['top_k']} · {summary['questions']} questions",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| **Overall pass rate** (all checks pass) | **{pct(summary['pass_rate'])}** |",
        f"| Routing accuracy (expected departments selected) | {r('routing')} |",
        f"| Routing exact match (no extra departments) | {r('routing_exact')} |",
        f"| Retrieval hit rate (expected doc retrieved) | {r('retrieval_hit')} |",
        f"| Answer source correct (KB / web / direct / declined) | {r('answer_source')} |",
        f"| Required facts present | {r('facts')} |",
        f"| No forbidden/outdated content | {r('forbidden_clean')} |",
        f"| Faithfulness, mean claim support (LLM judge) | {pct(summary['faithfulness_mean'])} |",
        f"| Fully faithful answers (every claim supported) | {r('fully_faithful')} |",
        f"| Fabricated company policy on unanswerable questions (lower is better) | {pct(summary['fabricated_company_policy'])} |",
        f"| Latency p50 / p95 | {summary['latency_p50_s']:.1f}s / {summary['latency_p95_s']:.1f}s |" if summary["latency_p50_s"] else "| Latency | n/a |",
        f"| Agent cost per question (est.) | ${summary['cost_per_question_usd']:.4f} |" if summary["cost_per_question_usd"] is not None else "| Cost | n/a |",
        f"| Errors | {summary['errors']} |",
        "",
        "## By category",
        "",
        "| Category | Questions | Pass rate |",
        "|---|---|---|",
    ]
    by_cat = defaultdict(list)
    for row in rows:
        by_cat[row["category"]].append(row)
    for cat, items in sorted(by_cat.items()):
        lines.append(f"| {cat} | {len(items)} | {pct(sum(i['passed'] for i in items) / len(items))} |")

    lines += ["", "## Failures", ""]
    failures = [row for row in rows if not row["passed"]]
    if not failures:
        lines.append("None.")
    for row in failures:
        failed = [k for k, v in row.get("checks", {}).items() if not v]
        lines.append(f"### {row['id']} ({row['category']}, as {row.get('role', 'employee')}): {row['question']}")
        if "error" in row:
            lines.append(f"- **Error:** `{row['error']}`")
        else:
            lines.append(f"- Failed checks: `{', '.join(failed)}`")
            lines.append(f"- Route: {row['source_used']} {row['departments']} · retrieved: {', '.join(row['retrieved_sources']) or 'none'}")
            if row.get("missing_facts"):
                lines.append(f"- Missing facts: {row['missing_facts']}")
            if row.get("leaked"):
                lines.append(f"- Forbidden content present: {row['leaked']}")
            for claim in row.get("unsupported_claims", []):
                lines.append(f"- Unsupported claim: _{claim}_")
            lines.append(f"- Answer: {row['answer'][:400].replace(chr(10), ' ')}")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--golden", default=str(EVAL_DIR / "golden_set.jsonl"))
    parser.add_argument("--category", help="only run this category")
    parser.add_argument("--limit", type=int, help="only run the first N questions")
    parser.add_argument("--judge-model", default="gpt-4.1")
    parser.add_argument("--no-judge", action="store_true", help="skip the faithfulness judge")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--label", help="also save the report as eval/reports/<label>.md/.json for before/after comparisons")
    parser.add_argument("--rescore", metavar="REPORT_JSON",
                        help="re-apply the current golden-set checks to a saved report's answers (no agent calls); "
                             "keeps that run's faithfulness judgements")
    args = parser.parse_args()

    items = [json.loads(line) for line in Path(args.golden).read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.category:
        items = [i for i in items if i["category"] == args.category]
    if args.limit:
        items = items[: args.limit]

    if args.rescore:
        saved = json.loads(Path(args.rescore).read_text(encoding="utf-8"))
        by_id = {r["id"]: r for r in saved["results"]}
        rows = [score_checks(item, by_id[item["id"]]) for item in items if "error" not in by_id[item["id"]]]
        meta = {**saved["meta"], "label": args.label or saved["meta"].get("label"), "rescored": True}
        write_reports(meta, rows, args.label)
        return 0

    judge = None if args.no_judge else ChatOpenAI(
        model=args.judge_model, temperature=0, api_key=settings.openai_api_key
    ).with_structured_output(Judgement)

    print(f"Evaluating {len(items)} questions with {args.workers} workers...", flush=True)
    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(lambda it: evaluate(it, judge), items):
            rows.append(row)
            mark = "PASS" if row["passed"] else "FAIL"
            print(f"  [{mark}] {row['id']:<5} {row.get('source_used', 'error'):<22} {row['question'][:70]}", flush=True)

    meta = {
        "label": args.label,
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "model": settings.openai_model,
        "embedding_model": settings.embedding_model,
        "judge_model": None if args.no_judge else args.judge_model,
        "top_k": settings.top_k,
    }
    summary = write_reports(meta, rows, args.label)
    return 0 if summary["errors"] == 0 else 1


def write_reports(meta: dict, rows: list[dict], label: str | None) -> dict:
    summary = summarize(rows)
    REPORT_DIR.mkdir(exist_ok=True)
    payload = json.dumps({"meta": meta, "summary": summary, "results": rows}, indent=2)
    report = markdown_report(meta, summary, rows)
    names = ["latest"] + ([label] if label else [])
    for name in names:
        (REPORT_DIR / f"{name}.md").write_text(report, encoding="utf-8")
        (REPORT_DIR / f"{name}.json").write_text(payload, encoding="utf-8")
    print("\n" + report.split("## Failures")[0])
    print(f"Full report: {REPORT_DIR / (label or 'latest')}.md")
    return summary


if __name__ == "__main__":
    sys.exit(main())
