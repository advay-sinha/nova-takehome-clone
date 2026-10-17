"""Back-end-neutral LLM request/response types, the shared call budget and cache keys.

A request carries its own JSON schema; every back end must return a dict for that schema or raise LLMError. Python
validates the content of every answer afterwards; nothing here decides money, authority or actions.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

PROMPT_VERSION = "1"


class LLMError(Exception):
    """A model call failed or returned something unusable (technical failure, never a business answer)."""


class LLMUnavailable(LLMError):
    """No back end can be used in this environment."""


class BudgetExhausted(LLMError):
    """The step's time or call budget is spent; remaining work is left pending, not guessed."""


class LLMLimited(LLMError):
    """The account's usage or rate limit, or an overloaded service: not the document's fault. The unit stays
    pending without using up an attempt, and the step stops starting new calls."""


LIMIT_WORDS = ("usage limit", "rate limit", "rate_limit", "limit reached", "limit exceeded", "overloaded",
               "too many requests", "quota", "429", "529")


def is_limit_message(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in LIMIT_WORDS)


@dataclass(frozen=True)
class LLMRequest:
    purpose: str                 # e.g. 'classify', 'extract:invoice'
    system: str
    user: str
    schema: dict
    max_tokens: int | None = None

    def cache_key(self, model: str) -> str:
        blob = json.dumps({"v": PROMPT_VERSION, "model": model, "purpose": self.purpose, "system": self.system,
                           "user": self.user, "schema": self.schema}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class LLMResult:
    data: dict
    backend: str
    model: str
    usage: dict = field(default_factory=dict)
    elapsed_s: float = 0.0
    cached: bool = False


class CallBudget:
    """Shared, thread-safe limit on wall time and number of calls for one harness step."""

    def __init__(self, seconds: float, max_calls: int):
        self.deadline = time.monotonic() + seconds
        self.max_calls = max_calls
        self.calls = 0
        self.stopped: str | None = None
        self._lock = threading.Lock()

    def remaining_s(self) -> float:
        return self.deadline - time.monotonic()

    def take(self, reserve_s: float = 0.0) -> None:
        with self._lock:
            if self.calls >= self.max_calls:
                raise BudgetExhausted(f"call budget of {self.max_calls} spent")
            if self.remaining_s() <= reserve_s:
                raise BudgetExhausted("step time budget spent")
            self.calls += 1

    def stop(self, reason: str) -> None:
        """No further calls in this step (e.g. the usage limit was reached)."""
        with self._lock:
            self.stopped = reason
            self.max_calls = self.calls


def parse_json_text(text: str) -> dict:
    """JSON object from model text, tolerating a ```json fence around it."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        t = t.rsplit("```", 1)[0]
    try:
        data = json.loads(t)
    except json.JSONDecodeError as e:
        raise LLMError(f"model output is not JSON: {e}") from e
    if not isinstance(data, dict):
        raise LLMError("model output is not a JSON object")
    return data


def iter_completed(provider, requests: list[LLMRequest], budget: CallBudget, workers: int):
    """Run requests concurrently and yield (index, result-or-error) as each finishes, so the caller can save every
    answer immediately: a step killed by its time limit then keeps all the work that completed."""
    def one(req: LLMRequest):
        try:
            budget.take(reserve_s=provider.timeout_s / 4)
            return provider.complete(req)
        except LLMLimited as e:
            budget.stop(str(e))
            return e
        except LLMError as e:
            return e

    if not requests:
        return
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(requests)))) as pool:
        futures = {pool.submit(one, req): i for i, req in enumerate(requests)}
        for fut in as_completed(futures):
            yield futures[fut], fut.result()


def run_many(provider, requests: list[LLMRequest], budget: CallBudget, workers: int) -> list[LLMResult | LLMError]:
    """Run requests concurrently; each slot gets its result or the error it raised, in input order."""
    out: list = [None] * len(requests)
    for i, res in iter_completed(provider, requests, budget, workers):
        out[i] = res
    return out
