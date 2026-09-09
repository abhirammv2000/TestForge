"""Tests for the quality gate and spec extraction in workflow/generate.py.

No LLM calls here: looks_degenerate() and function_spec() are pure functions,
so we can feed them known-good and known-bad strings directly.
"""

from workflow.generate import function_spec, looks_degenerate

GOOD_PYTEST = '''\
import pytest
from sut.example import my_func

@pytest.mark.parametrize("value, expected", [("a", 1), ("b", 2)])
def test_my_func_returns_expected(value, expected):
    assert my_func(value) == expected

@pytest.mark.parametrize("bad", ["oops"])
def test_my_func_raises(bad):
    with pytest.raises(ValueError):
        my_func(bad)
'''

GOOD_ROBOT = """\
*** Settings ***
Library    sut.example

*** Test Cases ***
Valid Input Returns True
    ${result}=    My Func    good
    Should Be True    ${result}
"""


def test_good_pytest_file_passes_the_gate():
    assert looks_degenerate("pytest", GOOD_PYTEST) is None


def test_good_robot_file_passes_the_gate():
    assert looks_degenerate("robot", GOOD_ROBOT) is None


def test_empty_file_is_rejected():
    assert looks_degenerate("pytest", "") == "empty file"
    assert looks_degenerate("pytest", "   \n  ") == "empty file"


def test_pytest_stub_with_no_assertions_is_rejected():
    stub = "import pytest\n\ndef test_thing():\n    pass\n"
    reason = looks_degenerate("pytest", stub)
    assert reason == "no assertions (stub)"


def test_pytest_missing_import_is_rejected():
    no_import = 'def test_thing():\n    assert 1 == 1\n'
    reason = looks_degenerate("pytest", no_import)
    assert reason == "missing 'import pytest'"


def test_placeholder_comment_stub_is_rejected():
    stub = "import pytest\n\ndef test_thing():\n    assert True\n    # Your test cases here\n"
    # has an assert, but the placeholder comment should still flag it
    reason = looks_degenerate("pytest", stub)
    assert reason == "placeholder stub"


def test_truncated_code_fence_is_rejected():
    broken = GOOD_PYTEST + "\n```\n"
    reason = looks_degenerate("pytest", broken)
    assert reason == "stray code fence (truncated output)"


def test_repetition_loop_long_line_is_rejected():
    junk = "import pytest\n" + "x" * 500 + "\nassert 1\n"
    reason = looks_degenerate("pytest", junk)
    assert reason == "over-long line (repetition loop)"


def test_runaway_test_count_is_rejected():
    lines = ["import pytest"]
    for i in range(35):
        lines.append(f"def test_case_{i}():\n    assert True")
    reason = looks_degenerate("pytest", "\n".join(lines))
    assert reason is not None
    assert "runaway test count" in reason


def test_robot_file_without_test_cases_section_is_rejected():
    broken = "*** Settings ***\nLibrary    sut.example\n"
    reason = looks_degenerate("robot", broken)
    assert reason == "no *** Test Cases *** section"


def test_robot_file_defining_its_own_keywords_is_rejected():
    broken = GOOD_ROBOT + "\n*** Keywords ***\nMy Func\n    No Operation\n"
    reason = looks_degenerate("robot", broken)
    assert reason == "defines its own keywords instead of using the library"


def test_robot_stub_with_no_checks_is_rejected():
    stub = "*** Settings ***\nLibrary    sut.example\n\n*** Test Cases ***\nEmpty\n    No Operation\n"
    reason = looks_degenerate("robot", stub)
    assert reason == "no assertions (stub)"


def test_function_spec_extracts_signature_and_docstring():
    source = '''
def helper(x):
    """internal, not the target"""
    return x

def validate_ipv4(address: str) -> bool:
    """Return True if address is a valid IPv4 dotted-quad."""
    return True
'''
    spec = function_spec(source, "validate_ipv4")
    assert "def validate_ipv4(address: str) -> bool:" in spec
    assert "Return True if address is a valid IPv4 dotted-quad." in spec
    # the other function's body must not leak into the spec
    assert "helper" not in spec
    assert "return True" not in spec


def test_function_spec_falls_back_to_full_source_on_syntax_error():
    broken_source = "def broken(:\n    this is not valid python"
    spec = function_spec(broken_source, "broken")
    assert spec == broken_source


def test_function_spec_falls_back_when_function_not_found():
    source = "def other_func():\n    return 1\n"
    spec = function_spec(source, "missing_func")
    assert spec == source
