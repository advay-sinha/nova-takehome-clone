"""Local back end: the user's logged-in Claude Code CLI in headless mode (decision D-002), used only when no
ANTHROPIC_API_KEY is set. Never present on the grader's machine.

Each call runs `claude -p` from an empty temp directory with no tools, no settings files, no MCP servers and no slash
commands, so nothing from this repository or the user's setup enters the extraction. The schema goes in
`--json-schema`; the document goes on stdin. `harness/.local-llm.json` (gitignored) can add environment overrides so
the CLI finds its login when a grader strips the environment, and can pin the command path.
"""
from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import tempfile
import time

from .base import LLMError, LLMLimited, LLMRequest, LLMResult, LLMUnavailable, is_limit_message, parse_json_text


def windows_system_env(environ) -> dict:
    """SYSTEMROOT/WINDIR/COMSPEC when the caller stripped them (grader/run_grader.py passes only PATH and
    ANTHROPIC_*). The Claude Code CLI cannot make network requests on Windows without SYSTEMROOT. The Windows
    directory comes from the OS API, which needs no environment variables."""
    if os.name != "nt":
        return {}
    present = {k.upper() for k in environ}
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        root = buf.value if ctypes.windll.kernel32.GetWindowsDirectoryW(buf, 260) else "C:\\Windows"
    except (OSError, AttributeError):
        root = "C:\\Windows"
    wanted = {"SYSTEMROOT": root, "WINDIR": root, "COMSPEC": os.path.join(root, "System32", "cmd.exe")}
    return {k: v for k, v in wanted.items() if k not in present}


def find_cli(local: dict) -> list[str] | None:
    cmd = local.get("claude_command")
    if cmd:
        return list(cmd) if isinstance(cmd, list) else [str(cmd)]
    exe = shutil.which("claude")
    return [exe] if exe else None


class CLIProvider:
    name = "cli"

    def __init__(self, cfg: dict, local: dict):
        cmd = find_cli(local)
        if not cmd:
            raise LLMUnavailable("no ANTHROPIC_API_KEY and no `claude` CLI on PATH")
        self.cmd = cmd
        self.model = local.get("model") or cfg["model"]
        self.effort = local.get("effort") or cfg.get("effort")
        self.timeout_s = float(cfg["request_timeout_s"])
        self.max_arg_chars = int(cfg["max_cli_arg_chars"])
        self.env = {**windows_system_env(os.environ), **os.environ,
                    **{str(k): str(v) for k, v in (local.get("env") or {}).items()}}
        self.env.pop("ANTHROPIC_API_KEY", None)   # the CLI must use the user's login, never a stray key

    def command(self, req: LLMRequest) -> list[str]:
        schema = json.dumps(req.schema, separators=(",", ":"))
        cmd = self.cmd + ["-p", "--output-format", "json", "--json-schema", schema, "--model", self.model,
                          "--tools", "", "--restricted", "--strict-mcp-config", "--disable-slash-commands",
                          "--no-session-persistence", "--system-prompt", req.system]
        if self.effort:
            cmd += ["--effort", self.effort]
        if sum(len(a) for a in cmd) > self.max_arg_chars:
            raise LLMError(f"{req.purpose}: schema and system prompt too long for one CLI command line")
        return cmd

    @staticmethod
    def parse_output(stdout: str) -> tuple[dict, dict]:
        """-> (structured data, usage) from `claude -p --output-format json` output."""
        try:
            out = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise LLMError(f"CLI output is not JSON: {stdout[:200]!r}") from e
        if not isinstance(out, dict):
            raise LLMError("CLI output is not a JSON object")
        if out.get("is_error") or out.get("subtype", "success") != "success":
            msg = str(out.get("result") or out.get("subtype"))
            if is_limit_message(msg):
                raise LLMLimited(f"CLI usage/rate limit: {msg[:300]}")
            raise LLMError(f"CLI reported an error: {str(out.get('result') or out.get('subtype'))[:300]}")
        usage = out.get("usage") if isinstance(out.get("usage"), dict) else {}
        for key in ("structured_output", "structuredOutput"):
            if isinstance(out.get(key), dict):
                return out[key], usage
        return parse_json_text(out.get("result") or ""), usage

    def complete(self, req: LLMRequest) -> LLMResult:
        start = time.monotonic()
        cmd = self.command(req)
        for attempt in range(2):
            with tempfile.TemporaryDirectory(prefix="nova-llm-") as cwd:
                try:
                    r = subprocess.run(cmd, input=req.user, capture_output=True, text=True, encoding="utf-8",
                                       timeout=self.timeout_s, cwd=cwd, env=self.env)
                except subprocess.TimeoutExpired as e:
                    raise LLMError(f"CLI timed out after {self.timeout_s:.0f} s") from e
                except OSError as e:
                    raise LLMUnavailable(f"cannot start the claude CLI: {e}") from e
            # A process that crashed with no output (Windows fail-fast 0xC0000409 seen when several start at once,
            # or killed by a signal) is relaunched once after a short, staggered pause; any other failure is not.
            crashed = not r.stdout.strip() and (r.returncode < 0 or r.returncode >= 0xC0000000)
            if not crashed or attempt:
                break
            time.sleep(2.0 + random.random() * 3.0)
        if r.returncode != 0 and not r.stdout.strip():
            if is_limit_message(r.stderr):
                raise LLMLimited(f"CLI usage/rate limit: {r.stderr.strip()[:300]}")
            raise LLMError(f"CLI exit {r.returncode}: {r.stderr.strip()[:300]}")
        data, usage = self.parse_output(r.stdout)
        return LLMResult(data=data, backend=self.name, model=self.model, usage=usage,
                         elapsed_s=round(time.monotonic() - start, 3))
