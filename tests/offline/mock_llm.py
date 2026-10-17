"""Explicit test-only LLM provider. The harness never selects it; tests pass it in by hand."""
from __future__ import annotations

import threading

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "harness"))

from nova.llm.base import LLMError, LLMRequest, LLMResult  # noqa: E402


class MockProvider:
    name = "mock"
    model = "mock-model"
    timeout_s = 5.0

    def __init__(self, responder):
        """responder(req) -> dict, or raises LLMError."""
        self.responder = responder
        self.calls: list[LLMRequest] = []
        self._lock = threading.Lock()

    def complete(self, req: LLMRequest) -> LLMResult:
        with self._lock:
            self.calls.append(req)
        data = self.responder(req)
        if not isinstance(data, dict):
            raise LLMError("mock responder returned a non-dict")
        return LLMResult(data=data, backend=self.name, model=self.model, usage={"input_tokens": 0, "output_tokens": 0})
