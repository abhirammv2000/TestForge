"""
Mock Atlassian MCP server (stdio transport).

Exposes Jira / Bitbucket / Confluence as MCP tools so any MCP-capable client
(our workflow, Claude Desktop, etc.) can drive the toolchain. Data is served
from local files via mock_store - see that module to point at real Atlassian.

Run directly for a quick smoke test:
    python -m mcp_server.server        # speaks MCP over stdio, waits for a client
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from mcp_server import mock_store

mcp = FastMCP("atlassian-mock")


# --------------------------------------------------------------------------- Jira
@mcp.tool()
def get_jira_issue(key: str) -> str:
    """Fetch a full Jira issue (description, acceptance criteria, flowchart) by key.

    Args:
        key: Issue key such as "MXL-101".
    Returns:
        JSON string of the issue.
    """
    return json.dumps(mock_store.get_jira_issue(key), indent=2)


@mcp.tool()
def search_jira(status: str = "") -> str:
    """List Jira issues, optionally filtered by status (e.g. "Ready for Test")."""
    return json.dumps(mock_store.search_jira(status or None), indent=2)


# ---------------------------------------------------------------------- Bitbucket
@mcp.tool()
def get_bitbucket_file(repo_path: str) -> str:
    """Fetch the source of a file under test from Bitbucket by repo-relative path.

    Args:
        repo_path: e.g. "sut/provisioning.py".
    """
    return mock_store.get_bitbucket_file(repo_path)


# --------------------------------------------------------------------- Confluence
@mcp.tool()
def get_confluence_page(page_id: str) -> str:
    """Read a Confluence page by id."""
    return json.dumps(mock_store.get_confluence_page(page_id), indent=2)


@mcp.tool()
def publish_confluence_page(title: str, body: str, parent_id: str = "TEST-HOME") -> str:
    """Create or update a Confluence page under ``parent_id`` and return its record."""
    record = mock_store.publish_confluence_page(title, body, parent_id)
    return json.dumps(record, indent=2)


if __name__ == "__main__":
    mcp.run()
