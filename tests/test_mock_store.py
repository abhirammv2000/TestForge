"""Tests for mcp_server/mock_store.py.

Reads use the real committed fixtures in data/jira/ (read-only, so this also
guards against those files becoming malformed). Writes are redirected to a
temp file via monkeypatch so tests never touch the real Confluence store.
"""

import json

import pytest

from mcp_server import mock_store


def test_get_jira_issue_reads_real_fixture():
    issue = mock_store.get_jira_issue("MXL-101")
    assert issue["key"] == "MXL-101"
    assert issue["target_function"] == "validate_ipv4"
    assert issue["status"] == "Ready for Test"


def test_get_jira_issue_unknown_key_raises_keyerror():
    with pytest.raises(KeyError):
        mock_store.get_jira_issue("MXL-999")


def test_search_jira_returns_all_three_tickets():
    results = mock_store.search_jira()
    keys = {r["key"] for r in results}
    assert keys == {"MXL-101", "MXL-102", "MXL-103"}


def test_search_jira_filters_by_status():
    results = mock_store.search_jira("Ready for Test")
    assert len(results) == 3
    no_match = mock_store.search_jira("Nonexistent Status")
    assert no_match == []


def test_get_bitbucket_file_reads_real_source():
    content = mock_store.get_bitbucket_file("sut/provisioning.py")
    assert "def validate_ipv4" in content


def test_get_bitbucket_file_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        mock_store.get_bitbucket_file("sut/does_not_exist.py")


def test_get_bitbucket_file_rejects_path_escape():
    with pytest.raises(ValueError):
        mock_store.get_bitbucket_file("../../../../etc/passwd")


@pytest.fixture
def isolated_confluence(tmp_path, monkeypatch):
    """Point CONFLUENCE_FILE at a throwaway file so tests never touch the real store."""
    fake_store = tmp_path / "pages.json"
    fake_store.write_text(
        json.dumps({"TEST-HOME": {"id": "TEST-HOME", "children": []}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(mock_store, "CONFLUENCE_FILE", fake_store)
    return fake_store


def test_publish_confluence_page_creates_a_page(isolated_confluence):
    record = mock_store.publish_confluence_page("My Report", "body text")
    assert record["title"] == "My Report"
    assert record["id"] == "my-report"

    fetched = mock_store.get_confluence_page("my-report")
    assert fetched["body"] == "body text"


def test_publish_confluence_page_registers_as_child_of_parent(isolated_confluence):
    mock_store.publish_confluence_page("My Report", "body")
    home = mock_store.get_confluence_page("TEST-HOME")
    assert "my-report" in home["children"]


def test_publish_confluence_page_updates_in_place_on_republish(isolated_confluence):
    mock_store.publish_confluence_page("My Report", "first version")
    mock_store.publish_confluence_page("My Report", "second version")

    home = mock_store.get_confluence_page("TEST-HOME")
    # republishing the same title must update, not duplicate, the child entry
    assert home["children"].count("my-report") == 1

    page = mock_store.get_confluence_page("my-report")
    assert page["body"] == "second version"


def test_get_confluence_page_unknown_id_raises(isolated_confluence):
    with pytest.raises(KeyError):
        mock_store.get_confluence_page("does-not-exist")
