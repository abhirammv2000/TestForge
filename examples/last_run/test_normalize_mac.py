import pytest
from sut.provisioning import normalize_mac

@pytest.mark.parametrize(
    "mac, expected",
    [
        ('aa:bb:cc:dd:ee:ff', 'AA:BB:CC:DD:EE:FF'),
        ('AA-BB-CC-DD-EE-FF', 'AA:BB:CC:DD:EE:FF'),
        ('aabb.ccdd.eeff', 'AA:BB:CC:DD:EE:FF'),
        ('1a:2b:3c:4d:5e:6f', '1A:2B:3C:4D:5E:6F')
    ]
)
def test_normalize_mac_returns(mac, expected):
    assert normalize_mac(mac) == expected


@pytest.mark.parametrize(
    "invalid_mac",
    ['gg:bb:cc:dd:ee:ff', 'aa:bb:cc']
)
def test_normalize_mac_raises(invalid_mac):
    with pytest.raises(ValueError):
        normalize_mac(invalid_mac)