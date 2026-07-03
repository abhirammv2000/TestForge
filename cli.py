"""
AI test-case generation workflow - orchestrator / CLI.

Ties the whole loop together, reaching the toolchain through the MCP server:

    Jira (MCP)  ->  Bitbucket (MCP)  ->  local LLM  ->  Robot + pytest files
                                                             |
                                     run  ->  analyze logs  ->  Confluence (MCP)

Usage:
    python cli.py list                 # list Jira issues that are ready for test
    python cli.py run MXL-101          # full pipeline for one issue
    python cli.py run MXL-101 --no-llm-summary
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from workflow import analyze, generate, run_tests
from workflow.mcp_client import atlassian_session

PROJECT_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = PROJECT_ROOT / "results"


MAX_REPAIRS = 3
# Repairing a test that RAN but FAILED is off by default: a test-generation tool
# must report genuine failures, not silently rewrite tests until they pass (which
# would hide real product bugs). Syntax/"failed to execute" repair is always on.
# Set REPAIR_ON_FAILURE=1 to also repair failing tests against the bundled
# known-correct reference module (handy when iterating on prompts).
REPAIR_ON_FAILURE = os.getenv("REPAIR_ON_FAILURE", "0") not in ("0", "false", "False")


def _hr(title: str) -> None:
    print(f"\n{'=' * 68}\n  {title}\n{'=' * 68}")


def _needs_repair(result: dict) -> bool:
    if run_tests.failed_to_execute(result):
        return True
    return REPAIR_ON_FAILURE and result["failed"] > 0


def _run_with_repair(framework: str, path, issue: dict, source: str, run_dir) -> dict:
    """Run a framework; repair on syntax errors and (optionally) on failing tests."""
    result = run_tests.run_framework(framework, path, run_dir)
    attempt = 0
    while _needs_repair(result) and attempt < MAX_REPAIRS:
        attempt += 1
        reason = ("did not execute" if run_tests.failed_to_execute(result)
                  else f"{result['failed']} test(s) failed")
        print(f"  {reason} (rc={result['return_code']}) - "
              f"repair attempt {attempt}/{MAX_REPAIRS}")
        generate.repair_one(framework, path, issue, source, run_tests.read_log(result))
        result = run_tests.run_framework(framework, path, run_dir)
    result["repairs"] = attempt
    print(f"  {result['passed']}/{result['total']} passed"
          f"  (rc={result['return_code']}, repairs={attempt})")
    return result


async def cmd_list() -> None:
    async with atlassian_session() as tools:
        _hr("MCP tools available")
        print(", ".join(await tools.list_tools()))
        _hr("Jira issues: Ready for Test")
        issues = json.loads(await tools.search_jira("Ready for Test"))
        for it in issues:
            print(f"  {it['key']:<8} {it['summary']}  -> {it['target_function']}()")


async def cmd_run(key: str, llm_summary: bool) -> None:
    async with atlassian_session() as tools:
        # 1. Fetch requirements from Jira (via MCP)
        _hr(f"[1/5] Fetch Jira issue {key} (MCP: get_jira_issue)")
        issue = json.loads(await tools.get_jira_issue(key))
        print(f"  {issue['summary']}")
        print(f"  {len(issue.get('acceptance_criteria', []))} acceptance criteria, "
              f"flowchart: {'yes' if issue.get('flowchart_mermaid') else 'no'}")

        # 2. Fetch the source under test from Bitbucket (via MCP)
        _hr("[2/5] Fetch source from Bitbucket (MCP: get_bitbucket_file)")
        source = await tools.get_bitbucket_file(issue["target_module"])
        print(f"  {issue['target_module']} ({len(source.splitlines())} lines)")

        # 3+4. Generate, run, and self-repair each framework's tests
        run_dir = RESULTS_DIR / key
        results = []
        for framework in ("pytest", "robot"):
            _hr(f"[3/5] Generate + run {framework} (local LLM, self-repair)")
            path = generate.generate_one(framework, issue, source)
            print(f"  generated -> {path.relative_to(PROJECT_ROOT)}")
            result = _run_with_repair(framework, path, issue, source, run_dir)
            results.append(result)

        logs = ""
        for r in results:
            logs += f"\n===== {r['framework']} log =====\n" + run_tests.read_log(r)

        _hr("[4/5] Analyze logs with local LLM")
        narrative = (
            analyze.summarize_with_llm(issue, results, logs)
            if llm_summary
            else "LLM narrative skipped (--no-llm-summary)."
        )
        print("  " + narrative.replace("\n", "\n  "))

        # 5. Publish the report to Confluence (via MCP)
        _hr("[5/5] Publish report to Confluence (MCP: publish_confluence_page)")
        title, body = analyze.build_report(issue, results, narrative)
        record = json.loads(await tools.publish_confluence_page(title, body))
        report_path = RESULTS_DIR / key / "report.md"
        report_path.write_text(body, encoding="utf-8")
        print(f"  Published page id: {record['id']}")
        print(f"  Local copy: {report_path.relative_to(PROJECT_ROOT)}")
        print(f"\n  Done. Overall: "
              f"{'PASS' if all(r['failed'] == 0 for r in results) else 'FAIL'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI test-case generation workflow")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list Jira issues ready for test")
    run_p = sub.add_parser("run", help="run the full pipeline for an issue")
    run_p.add_argument("key", help="Jira issue key, e.g. MXL-101")
    run_p.add_argument("--no-llm-summary", action="store_true",
                       help="skip the LLM narrative (faster)")

    args = parser.parse_args()
    if args.command == "list":
        asyncio.run(cmd_list())
    elif args.command == "run":
        asyncio.run(cmd_run(args.key, llm_summary=not args.no_llm_summary))


if __name__ == "__main__":
    main()
