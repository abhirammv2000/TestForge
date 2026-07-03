"""
Backing data store for the mock Atlassian MCP server.

Everything here talks to local files so the whole workflow runs offline:
  * Jira issues       -> data/jira/*.json          (read-only)
  * Bitbucket source  -> real files in the repo    (read-only)
  * Confluence pages  -> data/confluence/pages.json (read + write)

Swapping this module for real Atlassian REST calls is the only change needed
to point the workflow at a live instance - the MCP tool surface stays the same.
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JIRA_DIR = PROJECT_ROOT / "data" / "jira"
CONFLUENCE_FILE = PROJECT_ROOT / "data" / "confluence" / "pages.json"


# ----------------------------------------------------------------------------- Jira
def get_jira_issue(key: str) -> dict:
    """Return the full Jira issue for ``key`` (e.g. 'MXL-101')."""
    path = JIRA_DIR / f"{key}.json"
    if not path.exists():
        raise KeyError(f"Jira issue not found: {key}")
    return json.loads(path.read_text(encoding="utf-8"))


def search_jira(status: str | None = None) -> list[dict]:
    """Return lightweight summaries of all issues, optionally filtered by status."""
    results = []
    for path in sorted(JIRA_DIR.glob("*.json")):
        issue = json.loads(path.read_text(encoding="utf-8"))
        if status and issue.get("status") != status:
            continue
        results.append(
            {
                "key": issue["key"],
                "summary": issue["summary"],
                "status": issue["status"],
                "target_function": issue.get("target_function"),
            }
        )
    return results


# ------------------------------------------------------------------------ Bitbucket
def get_bitbucket_file(repo_path: str) -> str:
    """Return the text of a source file, addressed by its repo-relative path.

    e.g. get_bitbucket_file("sut/provisioning.py")
    """
    # Prevent path escapes; only serve files inside the repo.
    target = (PROJECT_ROOT / repo_path).resolve()
    if PROJECT_ROOT not in target.parents and target != PROJECT_ROOT:
        raise ValueError(f"path escapes repository: {repo_path}")
    if not target.exists():
        raise FileNotFoundError(f"file not found in repo: {repo_path}")
    return target.read_text(encoding="utf-8")


# ------------------------------------------------------------------------ Confluence
def _load_pages() -> dict:
    return json.loads(CONFLUENCE_FILE.read_text(encoding="utf-8"))


def _save_pages(pages: dict) -> None:
    CONFLUENCE_FILE.write_text(
        json.dumps(pages, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get_confluence_page(page_id: str) -> dict:
    pages = _load_pages()
    if page_id not in pages:
        raise KeyError(f"Confluence page not found: {page_id}")
    return pages[page_id]


def publish_confluence_page(title: str, body: str, parent_id: str = "TEST-HOME") -> dict:
    """Create or update a Confluence page. Returns the stored page record.

    Pages are keyed by a slug derived from the title so re-publishing the same
    report updates in place instead of creating duplicates.
    """
    pages = _load_pages()
    page_id = title.lower().replace(" ", "-").replace(":", "").replace("/", "-")

    record = {
        "id": page_id,
        "space": "QA",
        "title": title,
        "body": body,
        "parent": parent_id,
    }
    pages[page_id] = record

    # maintain the parent's children list
    if parent_id in pages:
        children = pages[parent_id].setdefault("children", [])
        if page_id not in children:
            children.append(page_id)

    _save_pages(pages)
    return record
