"""
Analyze execution results and build a Confluence-ready report.

Two layers:
  * Deterministic stats (counts, per-case table) parsed from the run.
  * An optional LLM-written narrative that reads the raw logs and explains what
    passed or failed in plain English.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from workflow import llm

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def summarize_with_llm(issue: dict, results: list[dict], logs: str) -> str:
    """Ask the local LLM for a short plain-English health summary of the run."""
    totals = ", ".join(
        f"{r['framework']}: {r['passed']}/{r['total']} passed" for r in results
    )
    prompt = f"""You are a QA lead. Summarize this automated test run in 3-4 sentences
for a Confluence report. Be concrete: mention the feature, the pass/fail counts,
and call out any failing tests and their likely cause. Do not invent results.

Feature under test: {issue['key']} - {issue['summary']}
Totals: {totals}

Raw execution logs:
{logs[:4000]}
"""
    try:
        return llm.generate(prompt).strip()
    except Exception as exc:  # never let summary failure break the pipeline
        return f"_(LLM summary unavailable: {exc})_"


def _status_badge(results: list[dict]) -> str:
    total_failed = sum(r["failed"] for r in results)
    return "PASSED" if total_failed == 0 else f"FAILED ({total_failed})"


def build_report(issue: dict, results: list[dict], narrative: str) -> tuple[str, str]:
    """Return (title, markdown_body) for the Confluence page."""
    title = f"Test Report: {issue['key']} {issue['summary']}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"# Test Execution Summary - {issue['key']}",
        "",
        f"- **Feature:** {issue['summary']}",
        f"- **Function under test:** `{issue['target_function']}` in `{issue['target_module']}`",
        f"- **Overall result:** {_status_badge(results)}",
        f"- **Generated:** {now} (model: {llm.pick_model()})",
        "",
        "## Results by framework",
        "",
        "| Framework | Passed | Failed | Total | Self-repairs |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in results:
        lines.append(
            f"| {r['framework']} | {r['passed']} | {r['failed']} | {r['total']} "
            f"| {r.get('repairs', 0)} |"
        )

    lines += ["", "## Analysis", "", narrative, ""]

    for r in results:
        lines += [f"## {r['framework']} test cases", ""]
        for c in r["cases"]:
            mark = "PASS" if c["status"] == "PASS" else "FAIL"
            detail = f": {c['message']}" if c["status"] == "FAIL" and c["message"] else ""
            lines.append(f"- [{mark}] {c['name']}{detail}")
        if not r["cases"]:
            lines.append("- _(no test cases were collected - see logs)_")
        lines.append("")

    return title, "\n".join(lines)
