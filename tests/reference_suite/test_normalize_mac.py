import pytest

from sut.provisioning import normalize_mac

CANONICAL = "AA:BB:CC:DD:EE:FF"


@pytest.mark.parametrize("text", ["aa:bb:cc:dd:ee:ff", "AA-BB-CC-DD-EE-FF", "aabb.ccdd.eeff", "AABBCCDDEEFF", "aa-bb-cc-dd-ee-ff", "aa.bb.cc.dd.ee.ff"])
def test_every_form_gives_the_canonical_form(text):
    assert normalize_mac(text) == CANONICAL


def test_digits_are_unchanged_and_letters_upper_case():
    assert normalize_mac("00:11:22:33:44:55") == "00:11:22:33:44:55"


@pytest.mark.parametrize("text", ["aa:bb:cc:dd:ee", "aa:bb:cc:dd:ee:ff:00", "aabbccddeeff0", "gg:bb:cc:dd:ee:ff", "aa:bb:cc:dd:ee:fg", ""])
def test_wrong_length_or_non_hex_is_a_value_error(text):
    with pytest.raises(ValueError):
        normalize_mac(text)


@pytest.mark.parametrize("value", [None, 5])
def test_non_strings_are_a_value_error(value):
    with pytest.raises(ValueError):
        normalize_mac(value)
