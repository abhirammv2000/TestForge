from sut.provisioning import provision_device


def test_a_valid_config_is_ok_with_no_errors():
    assert provision_device({"ip": "10.0.0.1", "bandwidth": "100Mbps"}) == {"status": "ok", "errors": []}


def test_a_bad_ip_is_reported():
    result = provision_device({"ip": "999.0.0.1", "bandwidth": "100Mbps"})
    assert result["status"] == "error"
    assert result["errors"] == ["invalid ip: '999.0.0.1'"]


def test_a_leading_zero_ip_is_reported():
    assert provision_device({"ip": "01.0.0.1", "bandwidth": "1Gbps"})["status"] == "error"


def test_a_bad_bandwidth_is_reported():
    result = provision_device({"ip": "10.0.0.1", "bandwidth": "fast"})
    assert result["status"] == "error"
    assert len(result["errors"]) == 1 and result["errors"][0].startswith("invalid bandwidth")


def test_a_negative_bandwidth_is_reported():
    assert provision_device({"ip": "10.0.0.1", "bandwidth": "-5"})["status"] == "error"


def test_missing_keys_are_reported_by_name():
    assert provision_device({"bandwidth": "1Gbps"})["errors"] == ["missing 'ip'"]
    assert provision_device({"ip": "10.0.0.1"})["errors"] == ["missing 'bandwidth'"]


def test_everything_wrong_lists_every_problem():
    result = provision_device({"ip": "bad", "bandwidth": "bad"})
    assert result["status"] == "error"
    assert len(result["errors"]) == 2


def test_an_empty_config_reports_both_missing():
    assert provision_device({})["errors"] == ["missing 'ip'", "missing 'bandwidth'"]


def test_zero_bandwidth_is_allowed():
    assert provision_device({"ip": "10.0.0.1", "bandwidth": "0"}) == {"status": "ok", "errors": []}
