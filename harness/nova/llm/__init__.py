"""LLM back-end selection (decision D-002).

ANTHROPIC_API_KEY set -> Anthropic SDK (the grader's machine). Otherwise -> the local Claude Code CLI. Otherwise ->
LLMUnavailable: the harness fails loudly instead of returning a clean audit. Test mocks live in tests/, never here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .base import (BudgetExhausted, CallBudget, LLMError, LLMLimited, LLMRequest, LLMResult, LLMUnavailable, iter_completed,
                   run_many)

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE.parent / "llm_config.json"
LOCAL_FILE = HERE.parents[1] / ".local-llm.json"     # harness/.local-llm.json, gitignored

__all__ = ["BudgetExhausted", "CallBudget", "LLMError", "LLMLimited", "LLMRequest", "LLMResult", "LLMUnavailable", "load_config",
           "load_local", "select_provider", "iter_completed", "run_many"]


def load_config() -> dict:
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def load_local(path: Path | None = None) -> dict:
    """The local CLI settings. NOVA_LOCAL_LLM may point at another file (offline tests use it to substitute a fake
    CLI); the grader's environment never carries it."""
    if path is None:
        path = Path(os.environ["NOVA_LOCAL_LLM"]) if os.environ.get("NOVA_LOCAL_LLM") else LOCAL_FILE
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))   # tolerate the BOM Windows PowerShell 5.1 writes
    if not isinstance(data, dict):
        raise LLMUnavailable(f"{path.name} must hold a JSON object")
    return data


def select_provider(cfg: dict | None = None, local: dict | None = None, environ=None):
    cfg = cfg or load_config()
    environ = os.environ if environ is None else environ
    if environ.get("ANTHROPIC_API_KEY"):
        from .sdk import SDKProvider
        return SDKProvider(cfg)
    from .cli import CLIProvider
    return CLIProvider(cfg, load_local() if local is None else local)


def workers_for(provider, cfg: dict) -> int:
    return int(cfg["concurrency"].get(provider.name, 2))
