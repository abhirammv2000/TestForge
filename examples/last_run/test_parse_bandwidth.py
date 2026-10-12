import pytest
from sut.provisioning import parse_bandwidth


@pytest.mark.parametrize(
    "input_value, expected",
    [
        ('100Mbps', 100),
        ('1Gbps', 1000),
        ('2000Kbps', 2),
        ('50', 50),
        ('1 gbps', 1000)
    ]
)
def test_parse_bandwidth_returns_correct_values(input_value, expected):
    assert parse_bandwidth(input_value) == expected


@pytest.mark.parametrize(
    "invalid_input",
    ['5Tbps', '-1Mbps']
)
def test_parse_bandwidth_raises_for_invalid_inputs(invalid_input):
    with pytest.raises(ValueError):
        parse_bandwidth(invalid_input)