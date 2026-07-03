"""
Execute generated test suites and parse their results.

Runs pytest and Robot Framework as subprocesses (cwd = project root so the
`sut` package imports cleanly), then parses their machine-readable output into
a uniform result dict the reporter can consume.
"""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_framework(framework: str, test_file: Path, results_dir: Path) -> dict:
    """Dispatch to the right runner by framework name ('pytest' or 'robot')."""
    if framework == "pytest":
        return run_pytest(test_file, results_dir)
    if framework == "robot":
        return run_robot(test_file, results_dir)
    raise ValueError(f"unknown framework: {framework}")


def failed_to_execute(result: dict) -> bool:
    """True if the suite didn't actually run (parse/collection/import error).

    Distinguishes "the test file is broken" (worth repairing) from "the tests
    ran and some legitimately failed". Non-executable if no cases were collected,
    or the runner returned an infrastructure error: pytest usage/collection codes
    (2/3/4), or Robot codes >=251 (data/usage errors; 0-250 == failed-test count).
    """
    if result["framework"] == "pytest" and result["return_code"] in (2, 3, 4):
        return True
    if result["framework"] == "robot" and result["return_code"] >= 251:
        return True
    return result["total"] == 0


def read_log(result: dict) -> str:
    if result.get("log_path"):
        return (PROJECT_ROOT / result["log_path"]).read_text(encoding="utf-8")
    return ""


def run_pytest(test_file: Path, results_dir: Path) -> dict:
    """Run a pytest file, returning a parsed result dict."""
    results_dir.mkdir(parents=True, exist_ok=True)
    junit = results_dir / "pytest-junit.xml"
    log = results_dir / "pytest-output.txt"
    junit.unlink(missing_ok=True)  # never parse a previous run's results

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_file), f"--junitxml={junit}", "-v"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    log.write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
    return _parse_junit(junit, "pytest", proc.returncode, log)


def run_robot(test_file: Path, results_dir: Path) -> dict:
    """Run a Robot Framework suite, returning a parsed result dict."""
    results_dir.mkdir(parents=True, exist_ok=True)
    log = results_dir / "robot-console.txt"
    output_xml = results_dir / "output.xml"
    output_xml.unlink(missing_ok=True)  # never parse a previous run's results

    proc = subprocess.run(
        [sys.executable, "-m", "robot", "--outputdir", str(results_dir), str(test_file)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    log.write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
    return _parse_robot_output(output_xml, proc.returncode, log)


# --------------------------------------------------------------------------- parsers
def _parse_junit(junit: Path, framework: str, return_code: int, log: Path) -> dict:
    cases: list[dict] = []
    if junit.exists():
        root = ET.parse(junit).getroot()
        # junit root may be <testsuites> or a single <testsuite>
        suites = root.findall("testsuite") or [root]
        for suite in suites:
            for case in suite.findall("testcase"):
                failure = case.find("failure")
                error = case.find("error")
                bad = failure if failure is not None else error
                cases.append(
                    {
                        "name": case.get("name", "<unknown>"),
                        "status": "FAIL" if bad is not None else "PASS",
                        "message": (bad.get("message", "") if bad is not None else ""),
                    }
                )
    return _summarize(framework, cases, return_code, log)


def _parse_robot_output(output_xml: Path, return_code: int, log: Path) -> dict:
    cases: list[dict] = []
    if output_xml.exists():
        root = ET.parse(output_xml).getroot()
        for test in root.iter("test"):
            status_el = test.find("status")
            status = status_el.get("status", "FAIL") if status_el is not None else "FAIL"
            message = (status_el.text or "").strip() if status_el is not None else ""
            cases.append(
                {
                    "name": test.get("name", "<unknown>"),
                    "status": "PASS" if status == "PASS" else "FAIL",
                    "message": message,
                }
            )
    return _summarize("robot", cases, return_code, log)


def _summarize(framework: str, cases: list[dict], return_code: int, log: Path) -> dict:
    passed = sum(1 for c in cases if c["status"] == "PASS")
    failed = len(cases) - passed
    return {
        "framework": framework,
        "total": len(cases),
        "passed": passed,
        "failed": failed,
        "cases": cases,
        "return_code": return_code,
        "log_path": _rel(log) if log.exists() else None,
    }


def _rel(path: Path) -> str:
    """Path relative to the project root for display, or absolute if outside it."""
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())
