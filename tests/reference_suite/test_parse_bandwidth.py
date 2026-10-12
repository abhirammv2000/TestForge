import pytest

from sut.provisioning import parse_bandwidth


@pytest.mark.parametrize(
    "text, expected",
    [
        ("10", 10), ("10Mbps", 10), ("10 mbps", 10), ("10MBPS", 10), ("1500kbps", 1), ("999kbps", 0), ("1000Kbps", 1),
        ("2Gbps", 2000), ("2gbps", 2000), ("1.5gbps", 1500), ("1.9mbps", 1), ("0", 0), ("0mbps", 0),
    ],
)
def test_parses_to_whole_mbps_rounded_down(text, expected):
    assert parse_bandwidth(text) == expected


@pytest.mark.parametrize("text", ["-5", "-0.5", "-1", "-5mbps", "abc", "", "   ", "5xbps", "mbps"])
def test_bad_input_is_a_value_error(text):
    with pytest.raises(ValueError):
        parse_bandwidth(text)


@pytest.mark.parametrize("value", [None, 7])
def test_non_strings_are_a_value_error(value):
    with pytest.raises(ValueError):
        parse_bandwidth(value)
