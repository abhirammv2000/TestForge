import pytest

from sut.provisioning import validate_ipv4


@pytest.mark.parametrize("address", ["192.168.1.10", "0.0.0.0", "255.255.255.255", "1.2.3.0", "255.0.0.1", "1.2.3.255"])
def test_valid_addresses(address):
    assert validate_ipv4(address) is True


@pytest.mark.parametrize(
    "address",
    ["256.1.1.1", "1.2.3.256", "1.2.3", "1.2.3.4.5", "1.2.3.4.", "01.2.3.4", "1.2.3.00", "1.2.3.a", "", "abc", "1..3.4",
     " 1.2.3.4", "1.2.3.4 ", "1.2.3.-4"],
)
def test_invalid_addresses(address):
    assert validate_ipv4(address) is False


@pytest.mark.parametrize("value", [None, 5, ["1.2.3.4"]])
def test_non_strings_are_invalid_not_errors(value):
    assert validate_ipv4(value) is False
