"""One tiny live call through the selected LLM back end (user-run; see .claude/handoffs/H-002).

    python harness/live_check.py              # the normal environment (what `make sheet` / `make run` see)
    python harness/live_check.py --stripped   # re-run with only PATH, a fresh HOME/TMP and ANTHROPIC_* (what `make grade` sees)

Prints the back end, model, time, token usage and the parsed answer. Prints no credentials. Exit 0 when the answer
matches the expected value, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from nova.llm import LLMError, LLMRequest, load_config, select_provider  # noqa: E402

SCHEMA = {"type": "object", "properties": {"invoice_id": {"type": "string"}, "total": {"type": "string"}},
          "required": ["invoice_id", "total"], "additionalProperties": False}
DOC = "Synthetic Freight Ltd\nInvoice SF-0042\nAir freight 10 kg x 3.10 = 31.00\nTotal USD 31.00\n"
WANT = {"invoice_id": "SF-0042", "total": "31.00"}


def check() -> int:
    cfg = load_config()
    try:
        provider = select_provider(cfg)
        res = provider.complete(LLMRequest(
            purpose="live_check", system="Extract the invoice number and the total amount (digits only, 2 decimals).",
            user=DOC, schema=SCHEMA, max_tokens=1000))
    except LLMError as e:
        print(f"FAIL {type(e).__name__}: {e}")
        return 1
    print(json.dumps({"backend": res.backend, "model": res.model, "elapsed_s": res.elapsed_s, "usage": res.usage,
                      "answer": res.data}, indent=1))
    ok = res.data == WANT
    print("PASS" if ok else f"FAIL expected {WANT}")
    return 0 if ok else 1


def stripped() -> int:
    with tempfile.TemporaryDirectory(prefix="nova-stripped-") as tmp:
        home, tmpdir = Path(tmp, "home"), Path(tmp, "tmp")
        home.mkdir()
        tmpdir.mkdir()
        env = {k: os.environ[k] for k in ("PATH", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL") if k in os.environ}
        env.update(HOME=str(home), TMPDIR=str(tmpdir), TMP=str(tmpdir), TEMP=str(tmpdir))   # as grader/run_grader.py
        return subprocess.run([sys.executable, __file__], env=env, cwd=home).returncode


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stripped", action="store_true", help="simulate the grader's filtered environment")
    raise SystemExit(stripped() if ap.parse_args().stripped else check())
