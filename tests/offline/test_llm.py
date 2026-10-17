"""LLM back-end selection, the CLI and SDK adapters, budgets and cache keys. No network and no real model:
the CLI is a fake script, the SDK client is a stub, and the mock provider is passed in explicitly."""
import json
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mock_llm import MockProvider  # noqa: E402
from nova.llm import (BudgetExhausted, CallBudget, LLMError, LLMRequest, LLMUnavailable, load_config,  # noqa: E402
                      run_many, select_provider)
from nova.llm.cli import CLIProvider  # noqa: E402
from nova.llm.sdk import SDKProvider  # noqa: E402

SCHEMA = {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"], "additionalProperties": False}
REQ = LLMRequest(purpose="test", system="Return n.", user="document text", schema=SCHEMA)

FAKE_CLAUDE = textwrap.dedent('''
    import json, os, signal, sys
    args = sys.argv[1:]
    doc = sys.stdin.read()
    mode = os.environ.get("FAKE_MODE", "structured")
    counter = os.environ.get("FAKE_COUNTER")
    if counter:
        n = int(open(counter).read() or 0) + 1 if os.path.exists(counter) else 1
        open(counter, "w").write(str(n))
        if mode == "crash" or (mode == "crash_once" and n == 1):
            if os.name == "nt":
                sys.exit(3221226505)      # Windows fail-fast, no output
            os.kill(os.getpid(), signal.SIGTERM)  # POSIX reports a negative signal return code
        if mode == "crash_once":
            mode = "structured"
    need = ["-p", "--output-format", "json", "--json-schema", "--tools", "--restricted", "--strict-mcp-config",
            "--no-session-persistence", "--system-prompt", "--model"]
    missing = [a for a in need if a not in args]
    info = {"missing": missing, "tools_arg": args[args.index("--tools") + 1] if "--tools" in args else None,
            "has_key": "ANTHROPIC_API_KEY" in os.environ, "marker": os.environ.get("LOGIN_HOME"),
            "stdin": doc, "cwd_empty": os.listdir(".") == [], "sysroot": os.environ.get("SYSTEMROOT")}
    if mode == "structured":
        print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "",
                          "structured_output": info, "usage": {"input_tokens": 3, "output_tokens": 4}}))
    elif mode == "text":
        print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                          "result": "```json\\n" + json.dumps(info) + "\\n```"}))
    elif mode == "error":
        print(json.dumps({"type": "result", "subtype": "success", "is_error": True, "result": "usage limit"}))
    else:
        sys.stderr.write("boom"); sys.exit(1)
''')


class SelectionTests(unittest.TestCase):
    def test_api_key_selects_sdk(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-placeholder"}), \
                mock.patch("anthropic.Anthropic") as client:
            self.assertIsInstance(select_provider(load_config(), local={}), SDKProvider)
        client.assert_called_once()

    def test_no_key_selects_cli(self):
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with mock.patch.dict(os.environ, env, clear=True):
            p = select_provider(load_config(), local={"claude_command": [sys.executable, "-c", "pass"]})
        self.assertIsInstance(p, CLIProvider)

    def test_nothing_available_fails_loudly(self):
        with mock.patch.dict(os.environ, {"PATH": ""}, clear=True):
            with self.assertRaises(LLMUnavailable):
                select_provider(load_config(), local={})


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        script = Path(self.tmp.name) / "fake_claude.py"
        script.write_text(FAKE_CLAUDE)
        self.local = {"claude_command": [sys.executable, str(script)], "env": {"LOGIN_HOME": "C:/fake-home"}}

    def tearDown(self):
        self.tmp.cleanup()

    def provider(self, mode):
        with mock.patch.dict(os.environ, {"FAKE_MODE": mode, "ANTHROPIC_API_KEY": "stray"}):
            return CLIProvider(load_config(), self.local)

    def counted(self, mode):
        counter = Path(self.tmp.name) / f"calls-{mode}.txt"
        with mock.patch.dict(os.environ, {"FAKE_MODE": mode, "FAKE_COUNTER": str(counter)}):
            prov = CLIProvider(load_config(), self.local)
            with mock.patch("nova.llm.cli.time.sleep"):
                try:
                    return prov.complete(REQ), int(counter.read_text())
                except LLMError as e:
                    return e, int(counter.read_text())

    def test_crashed_process_is_relaunched_once(self):
        res, calls = self.counted("crash_once")
        self.assertEqual((res.backend, calls), ("cli", 2))
        res, calls = self.counted("crash")
        self.assertIsInstance(res, LLMError)
        self.assertEqual(calls, 2)                       # bounded: one relaunch only
        res, calls = self.counted("fail")
        self.assertIsInstance(res, LLMError)
        self.assertEqual(calls, 1)                       # an ordinary failure is not relaunched

    def test_isolated_structured_call(self):
        res = self.provider("structured").complete(REQ)
        d = res.data
        self.assertEqual(d["missing"], [])
        self.assertEqual(d["tools_arg"], "")             # every tool disabled
        self.assertFalse(d["has_key"])                   # a stray API key never reaches the CLI
        self.assertEqual(d["marker"], "C:/fake-home")    # .local-llm.json env overrides applied
        self.assertEqual(d["stdin"], "document text")    # the document goes on stdin
        self.assertTrue(d["cwd_empty"])                  # runs from an empty temp folder
        self.assertEqual((res.backend, res.usage["output_tokens"]), ("cli", 4))

    @unittest.skipUnless(os.name == "nt", "Windows-only environment repair")
    def test_stripped_environment_gets_systemroot(self):
        stripped = {"PATH": os.environ.get("PATH", ""), "FAKE_MODE": "structured"}   # like grader/run_grader.py
        with mock.patch.dict(os.environ, stripped, clear=True):
            p = CLIProvider(load_config(), self.local)
        sysroot = p.complete(REQ).data["sysroot"]
        self.assertTrue(sysroot and Path(sysroot, "System32").is_dir())

    def test_local_file_with_bom(self):
        f = Path(self.tmp.name) / "local.json"
        f.write_bytes(b"\xef\xbb\xbf" + json.dumps({"model": "m"}).encode())
        from nova.llm import load_local
        self.assertEqual(load_local(f), {"model": "m"})

    def test_result_text_fallback(self):
        self.assertEqual(self.provider("text").complete(REQ).data["stdin"], "document text")

    def test_errors_are_technical_failures(self):
        for mode in ("error", "crash"):
            with self.subTest(mode=mode), self.assertRaises(LLMError):
                self.provider(mode).complete(REQ)
        from nova.llm import LLMLimited
        with self.assertRaises(LLMLimited):                  # "usage limit" is the account's limit, not the document's
            self.provider("error").complete(REQ)
        with mock.patch("nova.llm.cli.time.sleep"):
            try:
                self.provider("fail").complete(REQ)
            except LLMError as e:
                self.assertNotIsInstance(e, LLMLimited)

    def test_overlong_command_rejected(self):
        p = self.provider("structured")
        big = LLMRequest(purpose="big", system="x" * 40000, user="", schema=SCHEMA)
        with self.assertRaises(LLMError):
            p.complete(big)


class BadRequestError(Exception):
    pass


class FakeClient:
    def __init__(self, beta_error=None, stop="end_turn", text='{"n": 7}'):
        self.beta_error, self.stop, self.text, self.calls = beta_error, stop, text, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._beta))
        self.messages = SimpleNamespace(create=self._plain)

    def _resp(self):
        return SimpleNamespace(stop_reason=self.stop, model="m", content=[SimpleNamespace(type="text", text=self.text)],
                               usage=SimpleNamespace(input_tokens=10, output_tokens=2, cache_read_input_tokens=0,
                                                     cache_creation_input_tokens=0), stop_details=None)

    def _beta(self, **kw):
        self.calls.append(("beta", kw))
        if self.beta_error:
            raise self.beta_error
        return self._resp()

    def _plain(self, **kw):
        self.calls.append(("plain", kw))
        return self._resp()


class SDKTests(unittest.TestCase):
    def test_structured_output_request(self):
        client = FakeClient()
        res = SDKProvider(load_config(), client=client).complete(REQ)
        kind, kw = client.calls[0]
        self.assertEqual(kind, "beta")
        self.assertEqual(kw["output_config"]["format"], {"type": "json_schema", "schema": SCHEMA})
        self.assertEqual(kw["fallbacks"], "default")
        self.assertNotIn("tool_choice", kw)
        self.assertEqual((res.data, res.usage["input_tokens"]), ({"n": 7}, 10))

    def test_rejected_fallback_beta_retries_plain(self):
        client = FakeClient(beta_error=BadRequestError("unknown anthropic-beta header"))
        p = SDKProvider(load_config(), client=client)
        self.assertEqual(p.complete(REQ).data, {"n": 7})
        self.assertEqual([c[0] for c in client.calls], ["beta", "plain"])
        p.complete(REQ)
        self.assertEqual(client.calls[-1][0], "plain")      # fallbacks stay off afterwards

    def test_refusal_and_truncation_fail(self):
        for stop in ("refusal", "max_tokens"):
            with self.subTest(stop=stop), self.assertRaises(LLMError):
                SDKProvider(load_config(), client=FakeClient(stop=stop)).complete(REQ)

    def test_non_json_fails(self):
        with self.assertRaises(LLMError):
            SDKProvider(load_config(), client=FakeClient(text="not json")).complete(REQ)


class BudgetAndCacheTests(unittest.TestCase):
    def test_run_many_keeps_order_and_errors(self):
        def responder(req):
            if req.user == "bad":
                raise LLMError("nope")
            return {"n": int(req.user)}
        reqs = [LLMRequest("t", "s", u, SCHEMA) for u in ("1", "bad", "3")]
        out = run_many(MockProvider(responder), reqs, CallBudget(60, 10), workers=3)
        self.assertEqual(out[0].data, {"n": 1})
        self.assertIsInstance(out[1], LLMError)
        self.assertEqual(out[2].data, {"n": 3})

    def test_budget_exhaustion_leaves_work_pending(self):
        reqs = [LLMRequest("t", "s", str(i), SCHEMA) for i in range(5)]
        out = run_many(MockProvider(lambda r: {"n": 1}), reqs, CallBudget(60, 2), workers=1)
        self.assertEqual(sum(isinstance(x, BudgetExhausted) for x in out), 3)
        out = run_many(MockProvider(lambda r: {"n": 1}), reqs[:1], CallBudget(0, 10), workers=1)
        self.assertIsInstance(out[0], BudgetExhausted)

    def test_cache_key(self):
        a = REQ.cache_key("m1")
        self.assertEqual(a, LLMRequest("test", "Return n.", "document text", SCHEMA).cache_key("m1"))
        self.assertNotEqual(a, REQ.cache_key("m2"))
        self.assertNotEqual(a, LLMRequest("test", "Return n.", "other", SCHEMA).cache_key("m1"))


if __name__ == "__main__":
    unittest.main()
