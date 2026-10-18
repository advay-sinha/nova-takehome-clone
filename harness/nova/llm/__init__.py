"""LLM back-end selection (decision D-002).

ANTHROPIC_API_KEY set -> Anthropic SDK (the grader's machine). Otherwise -> the local Claude Code CLI. Otherwise ->
LLMUnavailable: the extraction runner selects its validated local document reader. An unsupported local billing
layout still fails loudly instead of returning a clean audit. Test mocks live in tests/, never here.

NOVA_LOCAL_READER_ONLY=1 skips all of that: the runner goes straight to the local document reader, and constructing
a provider or opening the shared response cache raises instead of silently calling a model.
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

LOCAL_ONLY_ENV = "NOVA_LOCAL_READER_ONLY"

__all__ = ["BudgetExhausted", "CallBudget", "LLMError", "LLMLimited", "LLMRequest", "LLMResult", "LLMUnavailable", "load_config",
           "load_local", "select_provider", "iter_completed", "run_many", "local_reader_only", "LocalOnlyViolation"]


class LocalOnlyViolation(RuntimeError):
    """A model provider or response cache was requested while NOVA_LOCAL_READER_ONLY=1."""


def local_reader_only(environ=None) -> bool:
    return (os.environ if environ is None else environ).get(LOCAL_ONLY_ENV) == "1"


def forbid_in_local_only(what: str) -> None:
    if local_reader_only():
        raise LocalOnlyViolation(f"{what} requested while {LOCAL_ONLY_ENV}=1")


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
    forbid_in_local_only("model provider")
    cfg = cfg or load_config()
    environ = os.environ if environ is None else environ
    if environ.get("ANTHROPIC_API_KEY"):
        from .sdk import SDKProvider
        return SDKProvider(cfg)
    from .cli import CLIProvider
    return CLIProvider(cfg, load_local() if local is None else local)


def workers_for(provider, cfg: dict) -> int:
    return int(cfg["concurrency"].get(provider.name, 2))
