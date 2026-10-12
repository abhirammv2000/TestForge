"""Tests for the pytest/Robot result parsers in workflow/run_tests.py.

These use fixture XML matching the pytest --junitxml and robot --outputdir
output formats, so no subprocess or LLM call is needed to run them.
"""

from pathlib import Path

from workflow import run_tests

JUNIT_ALL_PASS = """<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" errors="0" failures="0" skipped="0" tests="2" time="0.02"><testcase classname="generated_tests.test_x" name="test_x[1-True]" time="0.001" /><testcase classname="generated_tests.test_x" name="test_x[2-True]" time="0.001" /></testsuite></testsuites>"""

JUNIT_ONE_FAIL = """<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" errors="0" failures="1" skipped="0" tests="2" time="0.02"><testcase classname="generated_tests.test_x" name="test_x[1-True]" time="0.001" /><testcase classname="generated_tests.test_x" name="test_x[2-True]" time="0.001"><failure message="assert False == True">AssertionError</failure></testcase></testsuite></testsuites>"""

ROBOT_ALL_PASS = """<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0">
<suite name="Example">
<test id="s1-t1" name="First case" line="5">
<status status="PASS" start="2026-01-01T00:00:00.000000" elapsed="0.001"/>
</test>
</suite>
</robot>"""

ROBOT_ONE_FAIL = """<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0">
<suite name="Example">
<test id="s1-t1" name="Broken case" line="5">
<status status="FAIL" start="2026-01-01T00:00:00.000000" elapsed="0.001">Expected 'True' but got 'False'.</status>
</test>
</suite>
</robot>"""


def test_parse_junit_all_pass(tmp_path):
    junit = tmp_path / "junit.xml"
    junit.write_text(JUNIT_ALL_PASS, encoding="utf-8")
    log = tmp_path / "log.txt"
    log.write_text("ok", encoding="utf-8")

    result = run_tests._parse_junit(junit, "pytest", 0, log)

    assert result["framework"] == "pytest"
    assert result["total"] == 2
    assert result["passed"] == 2
    assert result["failed"] == 0
    assert result["return_code"] == 0


def test_parse_junit_one_failure_carries_message(tmp_path):
    junit = tmp_path / "junit.xml"
    junit.write_text(JUNIT_ONE_FAIL, encoding="utf-8")
    log = tmp_path / "log.txt"
    log.write_text("ok", encoding="utf-8")

    result = run_tests._parse_junit(junit, "pytest", 1, log)

    assert result["total"] == 2
    assert result["passed"] == 1
    assert result["failed"] == 1
    failing = [c for c in result["cases"] if c["status"] == "FAIL"]
    assert len(failing) == 1
    assert failing[0]["message"] == "assert False == True"


def test_parse_junit_missing_file_is_zero_cases(tmp_path):
    # No junit.xml was written at all (e.g. pytest crashed before producing one).
    junit = tmp_path / "does_not_exist.xml"
    log = tmp_path / "log.txt"
    log.write_text("crash", encoding="utf-8")

    result = run_tests._parse_junit(junit, "pytest", 2, log)

    assert result["total"] == 0
    assert result["passed"] == 0
    assert result["failed"] == 0


def test_parse_robot_output_all_pass(tmp_path):
    output_xml = tmp_path / "output.xml"
    output_xml.write_text(ROBOT_ALL_PASS, encoding="utf-8")
    log = tmp_path / "console.txt"
    log.write_text("ok", encoding="utf-8")

    result = run_tests._parse_robot_output(output_xml, 0, log)

    assert result["framework"] == "robot"
    assert result["total"] == 1
    assert result["passed"] == 1
    assert result["failed"] == 0


def test_parse_robot_output_failure_carries_message(tmp_path):
    output_xml = tmp_path / "output.xml"
    output_xml.write_text(ROBOT_ONE_FAIL, encoding="utf-8")
    log = tmp_path / "console.txt"
    log.write_text("ok", encoding="utf-8")

    result = run_tests._parse_robot_output(output_xml, 1, log)

    assert result["total"] == 1
    assert result["passed"] == 0
    assert result["failed"] == 1
    assert result["cases"][0]["message"] == "Expected 'True' but got 'False'."


def test_failed_to_execute_pytest_collection_error():
    # rc=2 is pytest's "usage error / collection error" code, no tests ran.
    result = {"framework": "pytest", "return_code": 2, "total": 0}
    assert run_tests.failed_to_execute(result) is True


def test_failed_to_execute_pytest_normal_test_failure():
    # rc=1 with cases collected means tests ran and some failed legitimately.
    result = {"framework": "pytest", "return_code": 1, "total": 3}
    assert run_tests.failed_to_execute(result) is False


def test_failed_to_execute_robot_infrastructure_error():
    # rc >= 251 is a Robot data/usage error (e.g. a bad keyword call), not test failures.
    result = {"framework": "robot", "return_code": 252, "total": 0}
    assert run_tests.failed_to_execute(result) is True


def test_failed_to_execute_robot_normal_failure_count():
    # Robot returns the number of failed tests (0-250) as its exit code.
    result = {"framework": "robot", "return_code": 2, "total": 5}
    assert run_tests.failed_to_execute(result) is False


def test_failed_to_execute_zero_cases_collected():
    result = {"framework": "pytest", "return_code": 0, "total": 0}
    assert run_tests.failed_to_execute(result) is True


def test_rel_path_inside_project_root():
    inside = run_tests.PROJECT_ROOT / "results" / "X" / "log.txt"
    assert run_tests._rel(inside) == str(Path("results") / "X" / "log.txt")


def test_rel_path_outside_project_root_returns_absolute(tmp_path):
    # tmp_path is outside the repo, so relative_to() must fail and fall back
    # to the absolute path instead of raising.
    outside = tmp_path / "log.txt"
    assert run_tests._rel(outside) == str(outside.resolve())
