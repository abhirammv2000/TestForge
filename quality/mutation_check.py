"""How good are the generated tests? Seed bugs into the code under test and count how many the tests catch.

    python -m quality.mutation_check                    # tests in generated_tests/ if present, else examples/last_run/
    python -m quality.mutation_check some/dir

"All tests pass" says little, because a test file with no useful assertions passes too. A mutation check asks the
opposite question: if the code were wrong in a small, realistic way, would these tests fail? The bugs are listed in
quality/mutants.py. A bug only counts if it changes the function's behaviour on at least one probe input, so
edits that do nothing are not held against the tests.

Each function's own test file is run against its own mutants, which is the fair question for a per-function
generator. The overall suite, all test files together, is reported too, because a bug in validate_ipv4 can also be
caught by the provision_device tests.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from .mutants import MUTANTS, PROBES, Mutant

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "sut" / "provisioning.py"
PYTEST_TIMEOUT_SECONDS = 60


def apply(source: str, mutant: Mutant) -> str:
    count = source.count(mutant.old)
    if count != 1:
        raise ValueError(f"{mutant.function}/{mutant.name}: the text to change appears {count} times, expected once")
    return source.replace(mutant.old, mutant.new, 1)


def load_functions(source: str) -> dict:
    namespace: dict = {"__name__": "sut_under_test"}
    exec(compile(source, "provisioning.py", "exec"), namespace)
    return namespace


def answer(function, args: tuple):
    """What a function does with an input: its result, or the type of exception it raised."""
    try:
        return ("value", function(*args))
    except Exception as error:  # a different exception type is a different behaviour
        return ("raises", type(error).__name__)


def changes_behaviour(mutant: Mutant, original: dict, mutated: dict) -> bool:
    return any(
        answer(original[mutant.function], args) != answer(mutated[mutant.function], args)
        for args in PROBES[mutant.function]
    )


@dataclass
class Outcome:
    mutant: Mutant
    live: bool            # changes behaviour on a probe, so it is a real bug
    killed_by_own: bool   # the function's own test file fails on it
    killed_by_any: bool   # at least one generated test file fails on it


def run_tests(mutated_source: str, test_files: list[Path]) -> bool:
    """True if the tests FAIL against the mutated module, meaning the bug was caught."""
    with tempfile.TemporaryDirectory(prefix="mutation_") as tmp:
        work = Path(tmp)
        (work / "sut").mkdir()
        (work / "sut" / "__init__.py").write_text("", encoding="utf-8")
        (work / "sut" / "provisioning.py").write_text(mutated_source, encoding="utf-8")
        copied = []
        for f in test_files:
            target = work / f.name
            shutil.copy(f, target)
            copied.append(str(target))
        argv = [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *copied]
        try:
            proc = subprocess.run(argv, cwd=work, capture_output=True, text=True, timeout=PYTEST_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            return True
        return proc.returncode != 0


def tests_pass_on_original(test_files: list[Path]) -> bool:
    return not run_tests(SOURCE.read_text(encoding="utf-8"), test_files)


def check(test_dir: Path) -> list[Outcome]:
    original_source = SOURCE.read_text(encoding="utf-8")
    original = load_functions(original_source)
    files = {p.stem.removeprefix("test_"): p for p in sorted(test_dir.glob("test_*.py"))}
    if not files:
        raise SystemExit(f"no test_*.py files in {test_dir}")
    for name, path in files.items():
        if not tests_pass_on_original([path]):
            raise SystemExit(f"{path.name} fails on the original code, so a kill rate would mean nothing")

    def judge(mutant: Mutant) -> Outcome:
        mutated_source = apply(original_source, mutant)
        live = changes_behaviour(mutant, original, load_functions(mutated_source))
        own_file = files.get(mutant.function)
        own = bool(live and own_file and run_tests(mutated_source, [own_file]))
        # if the function's own tests caught it, the whole suite did too, so the second run is only for the misses
        anyone = own or bool(live and run_tests(mutated_source, list(files.values())))
        return Outcome(mutant, live, killed_by_own=own, killed_by_any=anyone)

    with ThreadPoolExecutor(max_workers=4) as pool:  # each check is a separate pytest process
        return list(pool.map(judge, MUTANTS))


def report(outcomes: list[Outcome]) -> str:
    lines = ["| function | real bugs | caught by its own tests | caught by any test | missed by its own tests |",
             "|---|---|---|---|---|"]
    functions = sorted({o.mutant.function for o in outcomes}, key=[m.function for m in MUTANTS].index)
    total = own_total = any_total = 0
    for fn in functions:
        live = [o for o in outcomes if o.mutant.function == fn and o.live]
        own = [o for o in live if o.killed_by_own]
        anyk = [o for o in live if o.killed_by_any]
        missed = ", ".join(o.mutant.name for o in live if not o.killed_by_own) or "none"
        lines.append(f"| {fn} | {len(live)} | {len(own)} ({len(own) / len(live):.0%}) | {len(anyk)} ({len(anyk) / len(live):.0%}) | {missed} |"
                     if live else f"| {fn} | 0 | - | - | - |")
        total, own_total, any_total = total + len(live), own_total + len(own), any_total + len(anyk)
    lines.append(f"| **all** | {total} | {own_total} ({own_total / total:.0%}) | {any_total} ({any_total / total:.0%}) | |")
    dropped = [o.mutant.name for o in outcomes if not o.live]
    if dropped:
        lines += ["", "Edits that did not change behaviour on any probe, so they were not counted: " + ", ".join(dropped) + "."]
    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) > 2:
        sys.exit("usage: python -m quality.mutation_check [directory with test_*.py files]")
    if len(sys.argv) == 2:
        test_dir = Path(sys.argv[1])
    else:
        test_dir = ROOT / "generated_tests" if any((ROOT / "generated_tests").glob("test_*.py")) else ROOT / "examples" / "last_run"
    print(f"Tests from {test_dir}\n")
    print(report(check(test_dir)))


if __name__ == "__main__":
    main()
