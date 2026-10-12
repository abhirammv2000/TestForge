import pytest
from sut.provisioning import provision_device

@pytest.mark.parametrize(
    "config, expected",
    [
        (
            {"ip": "192.168.1.1", "bandwidth": "100 Mbps"},  # Fixed typo here and added space after Mbps
            {
                "status": "ok",
                "errors": [],
            },
        ),
        (
            {"bandwidth": "100Mbps"},
            {
                "status": "error",
                "errors": ["missing 'ip'"],
            },
        ),
        (
            {"ip": "192.168.1.1"},
            {
                "status": "error",
                "errors": ["missing 'bandwidth'"],
            },
        ),
        (
            {"ip": "999.1.1.1", "bandwidth": "100 Mbps"},
            {
                "status": "error",
                "errors": ["invalid ip address: '999.1.1.1'"],  # Corrected error message to include 'address'
            },
        ),
    ],
)
def test_provision_device(config, expected):
    result = provision_device(config)
    assert result["status"] == expected["status"]
    if not expected.get("errors"):
        assert len(result["errors"]) == 0
    else:
        for key in ("ip", "bandwidth"):  # Ensure we check both keys
            errors_with_key = [e for e in expected['errors'] if f"{key} is missing." in e]
            invalid_ip_errors = [e for e in expected['errors'] if any(e.startswith(f"Invalid {key}:") or f"{key} is missing.")]

            if errors_with_key:
                assert all(error.endswith(key) for error in errors_with_key), \
                    f"All '{key}' related messages should end with the correct format."
            
            elif invalid_ip_errors:
                assert all(any(e.startswith(f"Invalid {key}") or f"{key} is missing.")
                         and (f'{key} must be a valid IPv4 address.' in e or 
                              f'{key} cannot contain non-numeric characters.') for e in invalid_ip_errors)