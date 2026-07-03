"""
Device provisioning helpers (the "code under test").

This is a small, self-contained module that stands in for real product code.
The AI workflow reads the Jira ticket describing these requirements, fetches
this source via the (mock) Bitbucket MCP tool, and generates Robot Framework
and pytest test cases against the functions below.

Keeping the module pure (no I/O, no globals) makes the generated tests
deterministic and runnable in CI.
"""

from __future__ import annotations


def validate_ipv4(address: str) -> bool:
    """Return True if ``address`` is a well-formed IPv4 dotted-quad.

    Rules (see JIRA MXL-101):
      * Exactly four octets separated by single dots.
      * Each octet is an integer in the range 0-255.
      * No leading zeros (e.g. "01" is invalid), except the value "0" itself.
      * Leading/trailing whitespace is not allowed.
    """
    if not isinstance(address, str):
        return False
    parts = address.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit():
            return False
        if len(part) > 1 and part[0] == "0":
            return False  # reject leading zeros
        if int(part) > 255:
            return False
    return True


def parse_bandwidth(value: str) -> int:
    """Parse a human bandwidth string into an integer number of **Mbps**.

    Supported units (case-insensitive, see JIRA MXL-102):
      * ``Kbps`` -> value / 1000 (rounded down)
      * ``Mbps`` -> value as-is
      * ``Gbps`` -> value * 1000

    A bare number with no unit is treated as Mbps. Raises ``ValueError`` for
    unknown units, negative numbers, or unparseable input.
    """
    if not isinstance(value, str):
        raise ValueError("bandwidth must be a string")
    text = value.strip().lower().replace(" ", "")
    if not text:
        raise ValueError("empty bandwidth string")

    units = {"kbps": 0.001, "mbps": 1.0, "gbps": 1000.0}
    factor = 1.0
    number_text = text
    for unit, unit_factor in units.items():
        if text.endswith(unit):
            factor = unit_factor
            number_text = text[: -len(unit)]
            break

    try:
        number = float(number_text)
    except ValueError as exc:
        raise ValueError(f"cannot parse bandwidth: {value!r}") from exc

    if number < 0:
        raise ValueError("bandwidth cannot be negative")

    return int(number * factor)


def normalize_mac(mac: str) -> str:
    """Normalize a MAC address to canonical upper-case colon form ``AA:BB:CC:DD:EE:FF``.

    Accepts the three common separators (see JIRA MXL-103):
      * colon-separated  "aa:bb:cc:dd:ee:ff"
      * hyphen-separated "AA-BB-CC-DD-EE-FF"
      * Cisco dotted      "aabb.ccdd.eeff"

    Raises ``ValueError`` if the input does not contain exactly 12 hexadecimal
    digits once separators are removed.
    """
    if not isinstance(mac, str):
        raise ValueError("mac must be a string")
    hex_digits = mac.replace(":", "").replace("-", "").replace(".", "").strip()
    if len(hex_digits) != 12:
        raise ValueError(f"expected 12 hex digits, got {len(hex_digits)}: {mac!r}")
    try:
        int(hex_digits, 16)
    except ValueError as exc:
        raise ValueError(f"non-hex characters in MAC: {mac!r}") from exc
    pairs = [hex_digits[i:i + 2].upper() for i in range(0, 12, 2)]
    return ":".join(pairs)


def provision_device(config: dict) -> dict:
    """Validate a device provisioning ``config`` and return a status report.

    Expects keys ``ip`` (str) and ``bandwidth`` (str). Returns a dict with
    ``status`` ("ok" or "error") and an ``errors`` list describing any
    validation failures (see JIRA MXL-103).
    """
    errors: list[str] = []

    ip = config.get("ip")
    if ip is None:
        errors.append("missing 'ip'")
    elif not validate_ipv4(ip):
        errors.append(f"invalid ip: {ip!r}")

    bandwidth = config.get("bandwidth")
    if bandwidth is None:
        errors.append("missing 'bandwidth'")
    else:
        try:
            parse_bandwidth(bandwidth)
        except ValueError as exc:
            errors.append(f"invalid bandwidth: {exc}")

    return {"status": "ok" if not errors else "error", "errors": errors}
