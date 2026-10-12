import pytest
from sut.provisioning import validate_ipv4


@pytest.mark.parametrize(
    "address, expected",
    [
        ('192.168.1.10', True),
        ('0.0.0.0', True),
        ('255.255.255.255', True),
        ('256.1.1.1', False),
        ('1.2.3', False),
        ('192.168.01.1', False),
        ('', False),
        ('abc', False)
    ]
)
def test_validate_ipv4(address: str, expected: bool):
    assert validate_ipv4(address) == expected