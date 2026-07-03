"""
MCP client wrapper.

Spawns the mock Atlassian MCP server over stdio and exposes its tools as plain
async methods, so the workflow reaches Jira / Bitbucket / Confluence through MCP
instead of importing the store directly.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["-m", "mcp_server.server"],
    cwd=str(PROJECT_ROOT),
)


class AtlassianTools:
    """Convenience facade over the raw MCP session."""

    def __init__(self, session: ClientSession):
        self._session = session

    async def _call(self, name: str, **args) -> str:
        result = await self._session.call_tool(name, args)
        # Concatenate any text content blocks the tool returned.
        parts = [c.text for c in result.content if getattr(c, "type", None) == "text"]
        return "\n".join(parts)

    async def list_tools(self) -> list[str]:
        resp = await self._session.list_tools()
        return [t.name for t in resp.tools]

    async def get_jira_issue(self, key: str) -> str:
        return await self._call("get_jira_issue", key=key)

    async def search_jira(self, status: str = "") -> str:
        return await self._call("search_jira", status=status)

    async def get_bitbucket_file(self, repo_path: str) -> str:
        return await self._call("get_bitbucket_file", repo_path=repo_path)

    async def get_confluence_page(self, page_id: str) -> str:
        return await self._call("get_confluence_page", page_id=page_id)

    async def publish_confluence_page(self, title: str, body: str) -> str:
        return await self._call("publish_confluence_page", title=title, body=body)


@asynccontextmanager
async def atlassian_session():
    """Async context manager yielding a connected AtlassianTools facade."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield AtlassianTools(session)
