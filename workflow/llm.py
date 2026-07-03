"""
Small wrapper around a local LLM served by Ollama.

Prefers a Qwen coder model and falls back to whatever is installed, so it still
runs on a modest machine. Set OLLAMA_MODEL to force a specific one.
"""

from __future__ import annotations

import os
import re

import ollama
from dotenv import load_dotenv

load_dotenv()  # honor OLLAMA_MODEL from a local .env file

# Best model first, then smaller fallbacks for weaker machines.
PREFERRED_MODELS = [
    "qwen2.5-coder:7b",
    "qwen2.5-coder:3b",
    "deepseek-coder:6.7b",
    "llama3.2:3b",
    "llama3.2:1b",
]


def _installed_models() -> list[str]:
    """Return the names of models Ollama currently has pulled, e.g. 'llama3.2:3b'.

    Empty list if Ollama isn't running. We read defensively because the ollama
    client has returned both a typed object (resp.models, each item.model) and a
    plain dict across versions - so we handle either shape.
    """
    try:
        resp = ollama.list()
    except Exception:  # Ollama daemon not reachable
        return []

    items = resp.models if hasattr(resp, "models") else resp.get("models", [])
    names = []
    for item in items:
        name = getattr(item, "model", None) or (
            item.get("model") if isinstance(item, dict) else None
        )
        if name:
            names.append(name)
    return names


def pick_model() -> str:
    """Choose which local model to use: env override, else best available preferred."""
    override = os.getenv("OLLAMA_MODEL")
    if override:
        return override

    installed = _installed_models()
    for candidate in PREFERRED_MODELS:
        if candidate in installed:
            return candidate
    if installed:
        return installed[0]
    # Nothing installed; return the top preference so the error message is useful.
    return PREFERRED_MODELS[0]


def generate(prompt: str, system: str | None = None, model: str | None = None,
             temperature: float = 0.0) -> str:
    """Run a single-turn completion against the local model and return the text.

    Temperature defaults to 0 (deterministic). Callers raise it on retries so a
    rejected, degenerate output can be escaped with a different generation.
    """
    model = model or pick_model()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = ollama.chat(
        model=model,
        messages=messages,
        options={
            "temperature": temperature,
            # Penalize repeating recent tokens over a wide window - this, not a
            # higher temperature, is what stops the degeneration loop where the
            # model re-emitted the same test hundreds of times.
            "repeat_penalty": 1.3,
            "repeat_last_n": 320,
            # Hard cap on output length so a runaway generation can't balloon;
            # our test files are ~40 lines, so this is generous.
            "num_predict": 2048,
        },
    )
    return resp["message"]["content"]


def extract_code_block(text: str, language: str | None = None) -> str:
    """Pull the first fenced code block out of an LLM response.

    LLMs wrap generated files in ```python ... ``` or ```robotframework ...```.
    Handles three cases:
      1. A well-formed closed block -> return its contents.
      2. A block whose closing fence was truncated (the model ran out of tokens)
         -> drop the opening fence line and return the rest, so we never write a
         stray ``` into the test file.
      3. No fence at all -> return the text unchanged.
    """
    closed = r"```(?:[a-zA-Z]+)?\n(.*?)```"
    matches = re.findall(closed, text, re.DOTALL)
    if matches:
        # Prefer a block whose fence matches the requested language, if given.
        if language:
            lang_pattern = rf"```{language}[^\n]*\n(.*?)```"
            lang_matches = re.findall(lang_pattern, text, re.DOTALL | re.IGNORECASE)
            if lang_matches:
                return lang_matches[0].strip()
        return matches[0].strip()

    # No closing fence: if there is an opening fence, keep everything after it.
    open_fence = re.search(r"```[a-zA-Z]*\n", text)
    if open_fence:
        return text[open_fence.end():].replace("```", "").strip()
    return text.strip()
