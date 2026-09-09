"""Tests for the report builder in workflow/analyze.py.

build_report() calls llm.pick_model() to stamp the report, so that's
monkeypatched to a fixed value - no real Ollama call happens here.
"""

from workflow import analyze, llm


def _issue():
    return {
        "key": "MXL-101",
        "summary": "IPv4 address validation",
        "target_function": "validate_ipv4",
        "target_module": "sut/provisioning.py",
    }


def test_status_badge_passed_when_no_failures():
    results = [{"failed": 0}, {"failed": 0}]
    assert analyze._status_badge(results) == "PASSED"


def test_status_badge_failed_with_count():
    results = [{"failed": 1}, {"failed": 2}]
    assert analyze._status_badge(results) == "FAILED (3)"


def test_build_report_includes_key_fields(monkeypatch):
    monkeypatch.setattr(llm, "pick_model", lambda: "qwen2.5-coder:7b")
    results = [
        {
            "framework": "pytest",
            "passed": 2,
            "failed": 0,
            "total": 2,
            "repairs": 0,
            "cases": [{"name": "test_a", "status": "PASS", "message": ""}],
        }
    ]

    title, body = analyze.build_report(_issue(), results, "all good")

    assert title == "Test Report: MXL-101 IPv4 address validation"
    assert "validate_ipv4" in body
    assert "PASSED" in body
    assert "qwen2.5-coder:7b" in body
    assert "all good" in body
    assert "[PASS] test_a" in body


def test_build_report_shows_failure_detail(monkeypatch):
    monkeypatch.setattr(llm, "pick_model", lambda: "qwen2.5-coder:7b")
    results = [
        {
            "framework": "pytest",
            "passed": 0,
            "failed": 1,
            "total": 1,
            "repairs": 0,
            "cases": [{"name": "test_b", "status": "FAIL", "message": "boom"}],
        }
    ]

    _, body = analyze.build_report(_issue(), results, "one failure")

    assert "FAILED (1)" in body
    assert "[FAIL] test_b: boom" in body


def test_build_report_handles_no_cases_collected(monkeypatch):
    monkeypatch.setattr(llm, "pick_model", lambda: "qwen2.5-coder:7b")
    results = [
        {"framework": "robot", "passed": 0, "failed": 0, "total": 0, "repairs": 3, "cases": []}
    ]

    _, body = analyze.build_report(_issue(), results, "nothing ran")

    assert "no test cases were collected" in body
