"""Prompt templates for test-case generation and self-repair."""

from __future__ import annotations

SYSTEM = (
    "You are a senior QA automation engineer. You write correct, runnable test "
    "cases from requirements. You output ONLY the requested test file inside a "
    "single fenced code block, with no prose before or after."
)


def _format_issue(issue: dict) -> str:
    lines = [
        f"Issue: {issue['key']} - {issue['summary']}",
        f"Target module: {issue['target_module']}",
        f"Target function: {issue['target_function']}",
        "",
        "Description:",
        issue["description"],
        "",
        "Acceptance criteria:",
    ]
    for i, ac in enumerate(issue.get("acceptance_criteria", []), 1):
        lines.append(f"  {i}. {ac}")
    if issue.get("flowchart_mermaid"):
        lines += ["", "Flowchart (Mermaid):", issue["flowchart_mermaid"]]
    return "\n".join(lines)


def _module_import(issue: dict) -> str:
    return issue["target_module"].replace("/", ".").removesuffix(".py")


def _format_examples(issue: dict, framework: str = "pytest") -> str:
    """Render the ticket's verified input->expected examples as a plain table.

    These are the concrete test oracles; the model transcribes them into test
    syntax rather than deriving expected values itself (which a small model does
    unreliably). Returns "" when a ticket has no examples.

    Empty-string inputs are omitted for Robot: a bare blank argument is silently
    dropped by Robot (the "got 0 arguments" gotcha) and models handle the
    workarounds unreliably, so that edge case is left to pytest, which covers it
    cleanly.
    """
    examples = issue.get("examples")
    if not examples:
        return ""
    lines = ["Test these EXACT examples (input -> expected), and only these:"]
    for ex in examples:
        inp = ex["input"]
        if framework == "robot" and inp == "":
            continue  # Robot can't pass an empty argument cleanly; pytest covers it
        if "raises" in ex:
            lines.append(f"  - {inp!r} raises {ex['raises']}")
        else:
            lines.append(f"  - {inp!r} returns {ex['returns']!r}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- pytest
PYTEST_EXAMPLE = '''\
# Follow this structure EXACTLY - two parametrized tests, nothing else.
# No fixtures, no loops, no module-level code, no xfail.
import pytest
from sut.example import my_func

@pytest.mark.parametrize("value, expected", [("a", 1), ("b", 2)])
def test_my_func_returns_expected(value, expected):
    assert my_func(value) == expected

@pytest.mark.parametrize("bad", ["oops", "nope"])
def test_my_func_raises(bad):
    with pytest.raises(ValueError):
        my_func(bad)'''


def pytest_prompt(issue: dict, source_code: str) -> str:
    n = len(issue.get("acceptance_criteria", [])) or 6
    return f"""Write a pytest test module for the function below.

{_format_issue(issue)}

Function under test (signature + docstring - treat as the contract):
```python
{source_code}
```

{_format_examples(issue, "pytest")}

Rules:
- Import with: from {_module_import(issue)} import {issue['target_function']}
- Use ONE @pytest.mark.parametrize with a list of (input, expected) tuples for
  the "returns" examples above - pair each input with its own expected value on
  the same tuple (do NOT create a second parametrize or a cross-product).
- Put all "raises" examples in ONE parametrized test that calls the function
  inside `with pytest.raises(ValueError):` (see the example structure).
- Write a raises-test ONLY for inputs explicitly listed as "raises" above. If NO
  example says "raises", do NOT use pytest.raises at all - every example is a
  returns-assertion, including invalid inputs that simply return False.
- Output ONLY plain test functions. No fixtures, no loops, no module-level code,
  no @pytest.mark.xfail, no helper functions.
- Assert against LITERAL expected values copied straight from the acceptance
  criteria, e.g. assert {issue['target_function']}(<input>) == <expected>. NEVER
  compute the expected value in the test, reimplement the function's logic, or
  add if/else/match logic inside a test. Each test is a plain call + assert.
- Read the source and acceptance criteria carefully. Only expect an exception
  (pytest.raises) when the criteria explicitly say the function RAISES. If the
  criteria say it "returns True/False", assert the returned value instead.
- Every @pytest.mark.parametrize argument list must match the test function's
  parameters exactly (no unused parameters).
- One focused test per acceptance criterion; descriptive names; no main guard.
- Write EXACTLY one test per criterion (about {n} tests total). Do NOT invent
  extra tests, do NOT duplicate a test, and never pad names with repeated words.
  The whole file should be short (well under 40 lines).

{PYTEST_EXAMPLE}

Return ONLY the Python file in one ```python code block."""


# ------------------------------------------------------------------------ Robot
ROBOT_EXAMPLE = '''\
*** Settings ***
Library    sut.example

*** Test Cases ***
Valid Input Returns True
    ${result}=    My Func    good
    Should Be True    ${result}

Invalid Input Returns False
    ${result}=    My Func    bad
    Should Not Be True    ${result}

Unknown Value Raises Error
    Run Keyword And Expect Error    ValueError*    My Func    impossible'''


def robot_prompt(issue: dict, source_code: str) -> str:
    keyword = issue["target_function"].replace("_", " ").title()
    n = len(issue.get("acceptance_criteria", [])) or 6
    return f"""Write a Robot Framework test suite (.robot) for the function below.

{_format_issue(issue)}

Function under test (signature + docstring - treat as the contract):
```python
{source_code}
```

{_format_examples(issue, "robot")}

Rules (Robot Framework syntax is strict - follow the example exactly):
- In *** Settings *** use: Library    {_module_import(issue)}
- The Python function becomes the keyword: `{keyword}`. To CALL it and capture
  the return value, write:  ${{result}}=    {keyword}    <arg>
  then assert with `Should Be True` / `Should Not Be True` / `Should Be Equal As Integers`.
- NEVER put the argument on its own as a keyword. Arguments go after the keyword
  on the SAME line, separated by 4+ spaces.
- Read the acceptance criteria carefully. If a criterion says the function
  RETURNS True/False/a value (including for empty or invalid input), CALL the
  keyword and assert the returned value. Only use Run Keyword And Expect Error
  when the criterion literally says the function RAISES or errors.
- For a case that must raise: Run Keyword And Expect Error    ValueError*    {keyword}    <arg>
  (the error pattern is the FIRST argument, then the keyword, then its args).
- Use Run Keyword And Expect Error ONLY for inputs explicitly listed as "raises"
  above. If no example says "raises", never use it - assert the returned value
  for every example, including invalid inputs that simply return False.
- To pass an EMPTY string as an argument use ${{EMPTY}} (a bare blank is dropped
  by Robot and causes a "got 0 arguments" error). For a literal space use ${{SPACE}}.
- Create one test case per example above: call the keyword with the input and
  assert the expected result. Cover every example.
- Output ONLY *** Settings *** and *** Test Cases ***. Do NOT add a *** Variables ***
  section, do NOT define keywords (the Library already provides `{keyword}`), and
  do NOT pad test names with repeated words.

Here is the exact structure to mirror:
```robotframework
{ROBOT_EXAMPLE}
```

Return ONLY the .robot file in one ```robotframework code block."""


# --------------------------------------------------------------------------- repair
def repair_prompt(framework: str, issue: dict, source_code: str,
                  broken_code: str, error_log: str) -> str:
    lang = "python" if framework == "pytest" else "robotframework"
    return f"""The {framework} test file below did NOT pass. Either it failed to run
(a syntax / keyword / parametrize error) or a test's EXPECTATION is wrong.

The code under test is a KNOWN-CORRECT reference implementation. Never blame it and
never weaken a test to make it pass - instead re-derive the correct expected value
from the acceptance criteria AND the reference source, and fix the test so it both
runs and asserts the right thing. Keep the same intent and coverage.

{_format_issue(issue)}

Function under test (signature + docstring - the correct contract):
```python
{source_code}
```

Failing test file:
```{lang}
{broken_code}
```

Execution error / log:
{error_log[:2500]}

Return ONLY the corrected file in one ```{lang} code block, nothing else."""
