"""The mutation check has to be trustworthy before its number means anything.

A reference suite written by hand must catch every bug that really changes behaviour. An empty suite must catch
none. Both directions are tested, because a check that always says "caught" or never does would be useless.
"""

from pathlib import Path

import pytest

from quality import mutation_check as mc
from quality.mutants import MUTANTS, Mutant

REFERENCE = Path(__file__).parent / "reference_suite"
SOURCE = mc.SOURCE.read_text(encoding="utf-8")


def test_every_mutant_text_matches_the_source_exactly_once():
    for mutant in MUTANTS:
        assert SOURCE.count(mutant.old) == 1, f"{mutant.function}/{mutant.name}"


def test_every_mutant_changes_the_source():
    for mutant in MUTANTS:
        assert mc.apply(SOURCE, mutant) != SOURCE


def test_a_mutant_that_does_not_match_is_an_error():
    with pytest.raises(ValueError, match="expected once"):
        mc.apply(SOURCE, Mutant("validate_ipv4", "bad", "this text is not in the module", "x"))


def test_an_edit_that_does_nothing_is_not_counted_as_a_bug():
    """Removing the empty-string check changes nothing a caller can see: the next line raises the same exception."""
    mutant = next(m for m in MUTANTS if m.name == "empty_string_check_removed")
    original = mc.load_functions(SOURCE)
    mutated = mc.load_functions(mc.apply(SOURCE, mutant))
    assert mc.changes_behaviour(mutant, original, mutated) is False


def test_a_real_bug_is_seen_by_the_probes():
    mutant = next(m for m in MUTANTS if m.name == "lowercase_output")
    original = mc.load_functions(SOURCE)
    mutated = mc.load_functions(mc.apply(SOURCE, mutant))
    assert mc.changes_behaviour(mutant, original, mutated) is True


def test_the_reference_suite_passes_on_the_original_code():
    files = sorted(REFERENCE.glob("test_*.py"))
    assert len(files) == 4
    assert mc.tests_pass_on_original(files)


def test_the_reference_suite_catches_every_real_bug():
    outcomes = mc.check(REFERENCE)
    live = [o for o in outcomes if o.live]
    missed = [o.mutant.name for o in live if not o.killed_by_own]
    assert len(live) >= 25
    assert missed == []


def test_an_empty_suite_catches_nothing(tmp_path):
    for fn in ("validate_ipv4", "parse_bandwidth", "normalize_mac", "provision_device"):
        (tmp_path / f"test_{fn}.py").write_text("def test_nothing():\n    assert True\n", encoding="utf-8")

    outcomes = mc.check(tmp_path)

    assert any(o.live for o in outcomes)
    assert not any(o.killed_by_own or o.killed_by_any for o in outcomes)


def test_tests_that_fail_on_the_original_code_are_refused(tmp_path):
    (tmp_path / "test_validate_ipv4.py").write_text(
        "from sut.provisioning import validate_ipv4\n\n\ndef test_wrong():\n    assert validate_ipv4('1.2.3.4') is False\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="fails on the original"):
        mc.check(tmp_path)
