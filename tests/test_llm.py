"""Tests for workflow/llm.py's pure logic: code-block extraction and model
selection. No real Ollama call is made.

Note: this repo's .env sets OLLAMA_MODEL, and llm.py loads it at import
time, so tests that check the "no override" path must explicitly clear
the env var rather than assume a clean environment.
"""

from workflow import llm


def test_extract_code_block_with_closed_fence():
    text = "Here is the file:\n```python\nprint('hi')\n```\nDone."
    assert llm.extract_code_block(text) == "print('hi')"


def test_extract_code_block_prefers_matching_language():
    text = (
        "```python\nimport json\n```\n"
        "```robotframework\n*** Settings ***\n```"
    )
    assert llm.extract_code_block(text, "robotframework") == "*** Settings ***"
    assert llm.extract_code_block(text, "python") == "import json"


def test_extract_code_block_with_unclosed_fence():
    # model ran out of tokens mid-file, no closing ```
    text = "```python\nimport pytest\ndef test_x():\n    assert True"
    result = llm.extract_code_block(text)
    assert result == "import pytest\ndef test_x():\n    assert True"
    assert "```" not in result


def test_extract_code_block_with_no_fence_at_all():
    text = "  just plain text, no fence  "
    assert llm.extract_code_block(text) == "just plain text, no fence"


def test_pick_model_honors_env_override(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "some-custom-model:latest")
    assert llm.pick_model() == "some-custom-model:latest"


def test_pick_model_picks_best_installed_when_no_override(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setattr(
        llm, "_installed_models", lambda: ["llama3.2:3b", "qwen2.5-coder:3b"]
    )
    # qwen2.5-coder:3b ranks above llama3.2:3b in PREFERRED_MODELS
    assert llm.pick_model() == "qwen2.5-coder:3b"


def test_pick_model_falls_back_to_first_installed_if_none_preferred(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setattr(llm, "_installed_models", lambda: ["some-other-model:latest"])
    assert llm.pick_model() == "some-other-model:latest"


def test_pick_model_falls_back_to_top_preference_when_nothing_installed(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setattr(llm, "_installed_models", lambda: [])
    assert llm.pick_model() == llm.PREFERRED_MODELS[0]
