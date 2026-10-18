"""Anthropic SDK back end, used whenever ANTHROPIC_API_KEY is set (the grader's environment).

Structured output via `output_config.format` (forced tool_choice is rejected by current models). The client reads
ANTHROPIC_API_KEY and ANTHROPIC_BASE_URL from the environment itself. Server-side refusal fallbacks are requested
when configured; if the endpoint rejects that beta, the call is retried once without it and fallbacks stay off.
"""
from __future__ import annotations

import time

from .base import LLMError, LLMLimited, LLMRequest, LLMResult, parse_json_text

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class SDKProvider:
    name = "sdk"

    def __init__(self, cfg: dict, client=None):
        from . import forbid_in_local_only
        forbid_in_local_only("Anthropic SDK provider")
        if client is None:
            import anthropic
            client = anthropic.Anthropic(timeout=float(cfg["request_timeout_s"]), max_retries=int(cfg["sdk_max_retries"]))
        self.client = client
        self.model = cfg["model"]
        self.effort = cfg.get("effort")
        self.max_tokens = int(cfg["max_tokens"])
        self.timeout_s = float(cfg["request_timeout_s"])
        self.fallbacks = cfg.get("server_fallbacks")

    def _create(self, req: LLMRequest):
        output_config = {"format": {"type": "json_schema", "schema": req.schema}}
        if self.effort:
            output_config["effort"] = self.effort
        kwargs = {"model": self.model, "max_tokens": req.max_tokens or self.max_tokens, "system": req.system,
                  "messages": [{"role": "user", "content": req.user}], "output_config": output_config}
        if self.fallbacks:
            try:
                return self.client.beta.messages.create(**kwargs, betas=[FALLBACK_BETA], fallbacks=self.fallbacks)
            except Exception as e:  # noqa: BLE001 - only a rejected beta/fallback request is retried below
                if type(e).__name__ != "BadRequestError" or not any(
                        w in str(e).lower() for w in ("fallback", "beta", "anthropic-beta")):
                    raise
                self.fallbacks = None
        return self.client.messages.create(**kwargs)

    def complete(self, req: LLMRequest) -> LLMResult:
        start = time.monotonic()
        try:
            resp = self._create(req)
        except LLMError:
            raise
        except Exception as e:  # noqa: BLE001 - SDK errors become technical failures for this document
            if type(e).__name__ in ("RateLimitError", "OverloadedError") or getattr(e, "status_code", None) in (429, 529):
                raise LLMLimited(f"{type(e).__name__}: {e}") from e
            raise LLMError(f"{type(e).__name__}: {e}") from e
        stop = getattr(resp, "stop_reason", None)
        if stop == "refusal":
            raise LLMError(f"model refused ({getattr(getattr(resp, 'stop_details', None), 'category', None)})")
        if stop == "max_tokens":
            raise LLMError("model output hit max_tokens; answer truncated")
        text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), None)
        if text is None:
            raise LLMError("model returned no text block")
        u = getattr(resp, "usage", None)
        usage = {k: getattr(u, k, None) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                                  "cache_creation_input_tokens")} if u else {}
        return LLMResult(data=parse_json_text(text), backend=self.name, model=getattr(resp, "model", self.model),
                         usage=usage, elapsed_s=round(time.monotonic() - start, 3))
