"""NOVA_LOCAL_READER_ONLY / --local-reader-only: extraction uses the local document reader and nothing else.

Every way out to a model is made to fail loudly (provider construction, the Claude CLI process, the shared and
per-state response caches, sockets), so a passing test proves those paths were never entered; a log line would not.
"""
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack, closing
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "harness" / "harness.py"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "harness"))

from fixtures import build_mailbox  # noqa: E402
from nova import app  # noqa: E402
from nova.extract import run as extract_run  # noqa: E402
from nova.llm import LocalOnlyViolation, cli, sdk, select_provider, shared_cache  # noqa: E402
from nova.store import Store  # noqa: E402

FAKE_KEY = "not-a-real-key"


def _forbidden(what):
    def fail(*_a, **_k):
        raise AssertionError(f"{what} was used in local-reader-only mode")
    return fail


def _backends(state: Path) -> set[tuple]:
    """(backend, model) of every extracted unit; clone units copy facts without any backend."""
    with closing(sqlite3.connect(state / "nova.sqlite3")) as db:
        rows = db.execute("SELECT kind, backend, model, status FROM extraction_units").fetchall()
    assert all(s == "done" for _, _, _, s in rows), rows
    assert all(b is None for k, b, _, _ in rows if k == "clone"), rows
    return {(b, m) for k, b, m, _ in rows if k != "clone"}


def _cache_rows(state: Path) -> int:
    with closing(sqlite3.connect(state / "nova.sqlite3")) as db:
        return db.execute("SELECT count(*) FROM llm_cache").fetchone()[0]


class LocalOnlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        # batch_01 only: batch_02 holds a scan with no billed rows, which the local reader refuses by design.
        self.batch = build_mailbox(base / "mailbox") / "batch_01"
        self.state = base / "state"
        self.marker = base / "claude-was-run"
        fake_cli = base / "fake_cli.py"
        fake_cli.write_text(f"from pathlib import Path\nPath({str(self.marker)!r}).write_text('ran')\n")
        self.local_cfg = base / "local-llm.json"
        self.local_cfg.write_text(json.dumps({"claude_command": [sys.executable, str(fake_cli)],
                                              "shared_cache": str(base / "shared.sqlite3")}))
        self.saved = {k: os.environ.get(k) for k in
                      ("NOVA_LOCAL_READER_ONLY", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "NOVA_LOCAL_LLM")}

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def _model_env(self, local_only: bool):
        # A key, a base URL and a CLI config are all present: only the switch may keep them unused.
        os.environ.update(ANTHROPIC_API_KEY=FAKE_KEY, ANTHROPIC_BASE_URL="http://127.0.0.1:9",
                          NOVA_LOCAL_LLM=str(self.local_cfg))
        if local_only:
            os.environ["NOVA_LOCAL_READER_ONLY"] = "1"
        else:
            os.environ.pop("NOVA_LOCAL_READER_ONLY", None)

    def test_ingest_and_report_never_touch_a_provider_cache_process_or_socket(self):
        self._model_env(local_only=True)
        with ExitStack() as stack:
            for target, what in [(app, "select_provider"), (extract_run, "open_shared")]:
                stack.enter_context(mock.patch.object(target, what, _forbidden(what)))
            stack.enter_context(mock.patch.object(cli.CLIProvider, "__init__", _forbidden("CLIProvider")))
            stack.enter_context(mock.patch.object(sdk.SDKProvider, "__init__", _forbidden("SDKProvider")))
            stack.enter_context(mock.patch.object(Store, "cache_get", _forbidden("Store.cache_get")))
            stack.enter_context(mock.patch.object(Store, "cache_put", _forbidden("Store.cache_put")))
            stack.enter_context(mock.patch.object(subprocess, "Popen", _forbidden("subprocess.Popen")))
            stack.enter_context(mock.patch.object(socket.socket, "connect", _forbidden("socket.connect")))
            app.ingest(str(self.batch), str(self.state))
            report = app.report("2041-04-30", "supervised", str(self.state))
        self.assertEqual(_backends(self.state), {("local", "local-reader-1")})
        self.assertEqual(_cache_rows(self.state), 0)
        self.assertIn("findings", report)
        self.assertFalse(self.marker.exists())

    def test_guards_refuse_every_model_path_when_the_switch_is_on(self):
        self._model_env(local_only=True)
        with self.assertRaises(LocalOnlyViolation):
            select_provider()
        with self.assertRaises(LocalOnlyViolation):
            cli.CLIProvider({"model": "m", "request_timeout_s": 1, "max_cli_arg_chars": 1}, {})
        with self.assertRaises(LocalOnlyViolation):
            sdk.SDKProvider({"request_timeout_s": 1, "sdk_max_retries": 0}, client=object())
        with self.assertRaises(LocalOnlyViolation):
            shared_cache.open_shared()
        self.state.mkdir()
        store = Store(str(self.state))
        try:
            with self.assertRaises(LocalOnlyViolation):
                store.cache_get("k")
            with self.assertRaises(LocalOnlyViolation):
                store.cache_put("k", "p", {}, "cli", "m", {}, "now")
        finally:
            store.close()

    def test_without_the_switch_the_configured_provider_is_still_asked_first(self):
        self._model_env(local_only=False)
        asked = []

        class Stop(Exception):
            pass

        def provider(cfg):
            asked.append(True)
            raise Stop("a configured provider is constructed as before")

        # A non-LLMUnavailable failure must surface, not be turned into a local-reader result.
        with mock.patch.object(app, "select_provider", provider), \
                mock.patch.object(extract_run, "open_shared", lambda: None), self.assertRaises(Stop):
            app.ingest(str(self.batch), str(self.state))
        self.assertEqual(asked, [True])

    def test_harness_flag_reaches_the_process_through_a_stripped_grader_environment(self):
        # The grader passes only PATH, HOME, TMPDIR and ANTHROPIC_*; the flag travels in the command string.
        env = {"PATH": os.environ.get("PATH", ""), "HOME": self.tmp.name, "TMPDIR": self.tmp.name,
               "ANTHROPIC_API_KEY": FAKE_KEY, "ANTHROPIC_BASE_URL": "http://127.0.0.1:9",
               "NOVA_LOCAL_LLM": str(self.local_cfg)}
        if os.name == "nt":
            env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
        r = subprocess.run([sys.executable, str(HARNESS), "--local-reader-only", "ingest", str(self.batch),
                            "--state-dir", str(self.state)], env=env, capture_output=True, text=True, timeout=300,
                           cwd=self.tmp.name)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertIn("NOVA_LOCAL_READER_ONLY=1; using local document reader", r.stderr)
        self.assertFalse(self.marker.exists(), "the configured Claude CLI command was launched")
        self.assertFalse((Path(self.tmp.name) / "shared.sqlite3").exists(), "the shared cache was opened")
        self.assertEqual(_backends(self.state), {("local", "local-reader-1")})
        self.assertEqual(_cache_rows(self.state), 0)


if __name__ == "__main__":
    unittest.main()
