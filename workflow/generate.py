"""
Generate Robot Framework + pytest test files from a Jira issue and its source.

Before a generated file is used it's checked for the usual junk (empty files,
`pass`-only stubs, repetition loops) and regenerated if it fails the check, so a
broken file never gets treated as a valid test.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from workflow import llm, prompts

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "generated_tests"

# Where each framework's file is written, given the target function name.
_FILENAME = {
    "pytest": lambda fn: f"test_{fn}.py",
    "robot": lambda fn: f"{fn}.robot",
}
_PROMPT = {"pytest": prompts.pytest_prompt, "robot": prompts.robot_prompt}
_LANG = {"pytest": "python", "robot": "robotframework"}

MAX_GEN_ATTEMPTS = 3


def _path_for(framework: str, issue: dict) -> Path:
    return OUTPUT_DIR / _FILENAME[framework](issue["target_function"])


def function_spec(source_code: str, function_name: str) -> str:
    """Pull the target function's signature and docstring out of the source.

    We test black-box: give the model the contract (signature + docstring) and
    the ticket's examples, not the full body. Handing it the whole file tends to
    make it copy the implementation back instead of writing tests, and the
    examples already carry the expected values.

    Falls back to the full source if the function can't be found or parsed.
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return source_code
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            signature = f"def {node.name}({ast.unparse(node.args)})"
            if node.returns is not None:
                signature += f" -> {ast.unparse(node.returns)}"
            spec = signature + ":"
            docstring = ast.get_docstring(node)
            if docstring:
                spec += f'\n    """{docstring}"""'
            return spec
    return source_code


def looks_degenerate(framework: str, code: str) -> str | None:
    """Return a reason string if the test file is obviously bad, else None.

    Catches the common ways a small model goes wrong: empty output, a stub with
    no assertions, a leftover ``` fence from truncated output, and repetition
    loops (very long lines or far too many tests).
    """
    if not code.strip():
        return "empty file"
    if "```" in code:
        return "stray code fence (truncated output)"
    if any(len(line) > 200 for line in code.splitlines()):
        return "over-long line (repetition loop)"

    if framework == "pytest":
        assertions = len(re.findall(r"\bassert\b|pytest\.raises", code))
        tests = len(re.findall(r"^\s*def\s+test_", code, re.MULTILINE))
        if "import pytest" not in code:
            return "missing 'import pytest'"
        if assertions == 0:
            return "no assertions (stub)"
        if re.search(r"#\s*your test cases here", code, re.IGNORECASE):
            return "placeholder stub"
        if tests > 30:
            return f"runaway test count ({tests})"
    else:  # robot
        checks = len(re.findall(r"Should |Run Keyword And Expect Error", code))
        if "*** Test Cases ***" not in code:
            return "no *** Test Cases *** section"
        if re.search(r"\*\*\*\s*Keywords\s*\*\*\*", code):
            return "defines its own keywords instead of using the library"
        if checks == 0:
            return "no assertions (stub)"
        if checks > 60:
            return f"runaway keyword count ({checks})"
    return None


def generate_one(framework: str, issue: dict, source_code: str) -> Path:
    """Generate one framework's test file, retrying past degenerate output."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = _path_for(framework, issue)
    spec = function_spec(source_code, issue["target_function"])
    prompt = _PROMPT[framework](issue, spec)

    last_code = ""
    for attempt in range(1, MAX_GEN_ATTEMPTS + 1):
        # Deterministic first; escalate temperature on retries so a rejected
        # output can be escaped with a different generation.
        temperature = 0.0 if attempt == 1 else 0.3 * attempt
        raw = llm.generate(prompt, system=prompts.SYSTEM, temperature=temperature)
        code = llm.extract_code_block(raw, _LANG[framework])
        reason = looks_degenerate(framework, code)
        if reason is None:
            path.write_text(code, encoding="utf-8")
            return path
        print(f"    [quality gate] attempt {attempt}/{MAX_GEN_ATTEMPTS} "
              f"rejected: {reason}")
        last_code = code

    # All attempts were degenerate: write the last one so the failure is visible
    # downstream, rather than silently swallowed.
    path.write_text(last_code, encoding="utf-8")
    return path


def repair_one(framework: str, path: Path, issue: dict, source_code: str,
               error_log: str) -> Path:
    """Ask the LLM to fix a failing test file in place, given its execution error.

    A repair that comes back degenerate (e.g. a stub that trivially passes) is
    refused - we keep the previous file rather than replace a working test with
    garbage.
    """
    broken = path.read_text(encoding="utf-8")
    spec = function_spec(source_code, issue["target_function"])
    raw = llm.generate(
        prompts.repair_prompt(framework, issue, spec, broken, error_log),
        system=prompts.SYSTEM,
    )
    fixed = llm.extract_code_block(raw, _LANG[framework])
    reason = looks_degenerate(framework, fixed)
    if reason is not None:
        print(f"    [quality gate] repair rejected ({reason}); keeping prior file")
        return path
    path.write_text(fixed, encoding="utf-8")
    return path
