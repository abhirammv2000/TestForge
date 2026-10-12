"""Deliberate bugs for the code under test (sut/provisioning.py), and inputs to prove each one is a real bug.

A mutant is a small edit that breaks one rule from a ticket: an off-by-one comparison, a dropped check, a wrong
constant. Good tests fail on it. Each edit must match the source exactly once, so a change to the module that
moves the target text is caught by a test and not silently skipped.

Not every edit changes behaviour. `if not text: raise ValueError(...)` can be removed and the function still
raises ValueError, from the next line. So every mutant is also run against PROBES, a list of inputs for each
function, and is only counted if some probe gives a different answer than the original. The probes are written
from the tickets' rules and are not the model's tests.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Mutant:
    function: str
    name: str
    old: str
    new: str


MUTANTS: list[Mutant] = [
    # validate_ipv4
    Mutant("validate_ipv4", "five_parts_accepted", "if len(parts) != 4:", "if len(parts) < 4:"),
    Mutant("validate_ipv4", "limit_is_256", "if int(part) > 255:", "if int(part) > 256:"),
    Mutant("validate_ipv4", "255_rejected", "if int(part) > 255:", "if int(part) >= 255:"),
    Mutant("validate_ipv4", "leading_zeros_accepted", 'if len(part) > 1 and part[0] == "0":', "if False:"),
    Mutant("validate_ipv4", "two_digit_leading_zero_accepted", 'if len(part) > 1 and part[0] == "0":', 'if len(part) > 2 and part[0] == "0":'),
    Mutant("validate_ipv4", "non_digits_accepted", "if not part.isdigit():", "if not part:"),
    Mutant("validate_ipv4", "non_string_crashes", "    if not isinstance(address, str):\n        return False\n    parts", "    parts"),
    # parse_bandwidth
    Mutant("parse_bandwidth", "kbps_factor_wrong", '"kbps": 0.001', '"kbps": 0.01'),
    Mutant("parse_bandwidth", "gbps_factor_wrong", '"gbps": 1000.0', '"gbps": 100.0'),
    Mutant("parse_bandwidth", "zero_rejected", "if number < 0:", "if number <= 0:"),
    Mutant("parse_bandwidth", "small_negatives_accepted", "if number < 0:", "if number < -1:"),
    Mutant("parse_bandwidth", "rounds_up", "return int(number * factor)", "return round(number * factor)"),
    Mutant("parse_bandwidth", "case_sensitive_units", 'text = value.strip().lower().replace(" ", "")', 'text = value.strip().replace(" ", "")'),
    Mutant("parse_bandwidth", "bare_number_is_kbps", "factor = 1.0\n    number_text = text", "factor = 0.001\n    number_text = text"),
    Mutant("parse_bandwidth", "non_string_crashes", '    if not isinstance(value, str):\n        raise ValueError("bandwidth must be a string")\n', ""),
    Mutant("parse_bandwidth", "empty_string_check_removed", '    if not text:\n        raise ValueError("empty bandwidth string")\n', ""),
    # normalize_mac
    Mutant("normalize_mac", "thirteen_digits_accepted", "if len(hex_digits) != 12:", "if len(hex_digits) < 12:"),
    Mutant("normalize_mac", "lowercase_output", ".upper()", ".lower()"),
    Mutant("normalize_mac", "dotted_form_rejected", '.replace(".", "")', ""),
    Mutant("normalize_mac", "hyphen_form_rejected", '.replace("-", "")', ""),
    Mutant("normalize_mac", "colon_form_rejected", 'mac.replace(":", "")', "mac"),
    Mutant("normalize_mac", "hyphen_output", 'return ":".join(pairs)', 'return "-".join(pairs)'),
    Mutant("normalize_mac", "non_hex_accepted", '    try:\n        int(hex_digits, 16)\n    except ValueError as exc:\n        raise ValueError(f"non-hex characters in MAC: {mac!r}") from exc\n', ""),
    # provision_device
    Mutant("provision_device", "status_always_ok", '"status": "ok" if not errors else "error"', '"status": "ok"'),
    Mutant("provision_device", "ip_not_validated", "elif not validate_ipv4(ip):", "elif False:"),
    Mutant("provision_device", "missing_ip_not_reported", "errors.append(\"missing 'ip'\")", "pass"),
    Mutant("provision_device", "bandwidth_not_validated", "            parse_bandwidth(bandwidth)", "            pass"),
    Mutant("provision_device", "missing_bandwidth_not_reported", "errors.append(\"missing 'bandwidth'\")", "pass"),
    Mutant("provision_device", "errors_not_listed", '"errors": errors}', '"errors": []}'),
]

PROBES: dict[str, list[tuple]] = {
    "validate_ipv4": [(a,) for a in [
        "192.168.1.10", "0.0.0.0", "255.255.255.255", "255.0.0.1", "256.1.1.1", "1.2.3", "1.2.3.4.5", "1.2.3.4.",
        "01.2.3.4", "1.2.3.00", "1.2.3.0", "192.168.01.1", "", "abc", "1.2.3.a", "1..3.4", " 1.2.3.4", "1.2.3.4 ",
        "1.2.3.-4", "1.2.3.256", "1.2.3.999", "١.٢.٣.٤", None, 5, ["1.2.3.4"],
    ]],
    "parse_bandwidth": [(a,) for a in [
        "10", "10Mbps", "10 mbps", "10MBPS", "1500kbps", "999kbps", "1000Kbps", "2Gbps", "2gbps", "1.5gbps", "1.9mbps",
        "0", "0mbps", "-0.5", "-1", "-5mbps", "abc", "", "   ", "5xbps", "mbps", "1e3", "1e3kbps", None, 7,
    ]],
    "normalize_mac": [(a,) for a in [
        "aa:bb:cc:dd:ee:ff", "AA-BB-CC-DD-EE-FF", "aabb.ccdd.eeff", "AABBCCDDEEFF", "00:11:22:33:44:55", "aa:bb:cc:dd:ee",
        "aa:bb:cc:dd:ee:ff:00", "aabbccddeeff0", "gg:bb:cc:dd:ee:ff", "aa:bb:cc:dd:ee:fg", "", " aa:bb:cc:dd:ee:ff ",
        "aa-bb-cc-dd-ee-ff", "aa.bb.cc.dd.ee.ff", None, 5,
    ]],
    "provision_device": [(a,) for a in [
        {"ip": "10.0.0.1", "bandwidth": "100Mbps"}, {"ip": "999.0.0.1", "bandwidth": "100Mbps"},
        {"ip": "10.0.0.1", "bandwidth": "fast"}, {"ip": "10.0.0.1"}, {"bandwidth": "1Gbps"}, {},
        {"ip": "bad", "bandwidth": "bad"}, {"ip": "10.0.0.1", "bandwidth": "-5"}, {"ip": "01.0.0.1", "bandwidth": "1Gbps"},
        {"ip": "10.0.0.1", "bandwidth": "0"},
    ]],
}
