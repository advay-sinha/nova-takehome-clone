"""Offline checks for ai_log/export_claude_sessions.py. Synthetic strings only; no transcript or network access."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('export_claude_sessions', ROOT / 'ai_log' / 'export_claude_sessions.py')
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


def load_fake_key():
    env_file = ROOT / '.env'
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8').splitlines():
            name, separator, value = line.partition('=')
            if separator and name.strip() == 'FAKE_KEY':
                return value.strip().removeprefix("'").removesuffix("'")

    # Keep offline CI runs self-contained when the ignored local .env is absent.
    


class RedactTests(unittest.TestCase):
    def test_secrets_redacted(self):
        fake = load_fake_key()
        out, hits = export.redact(fake)
        self.assertEqual(hits, 5)
        for secret in ['ABCDEFGHIJKLMNOP', 'abcd1234efgh', 'zzzz9999yyyy', 'abcdefghijklmnopqrstuvwxyz012345',
                       'ghp_abcdefghijklmnopqrstuvwxyz']:
            self.assertNotIn(secret, out)
        self.assertIn('ANTHROPIC_API_KEY=[REDACTED]', out)

    def test_json_escaped_quote_redacted(self):
        for escaped in ['\\"', '\\\\\\"']:
            out, hits = export.redact('{"command": "$env:ANTHROPIC_API_KEY = ' + escaped + 'zzzz9999yyyy' + escaped + '"}')
            self.assertEqual(hits, 1)
            self.assertNotIn('zzzz9999yyyy', out)

    def test_ordinary_text_kept(self):
        text = 'The harness reads ANTHROPIC_API_KEY and ANTHROPIC_BASE_URL from the environment; make grade later.'
        out, hits = export.redact(text)
        self.assertEqual((out, hits), (text, 0))

    def test_readable_log(self):
        records = [
            {'type': 'user', 'timestamp': 't1', 'message': {'content': 'read the brief'}},
            {'type': 'assistant', 'timestamp': 't2', 'message': {'content': [
                {'type': 'text', 'text': 'Reading it.'},
                {'type': 'tool_use', 'name': 'Read', 'input': {'file_path': 'README.md'}}]}},
            {'type': 'user', 'isMeta': True, 'message': {'content': 'hidden meta'}},
        ]
        md = export.readable(records, 's1')
        self.assertIn('read the brief', md)
        self.assertIn('Reading it.', md)
        self.assertIn("tool `Read` file_path='README.md'", md)
        self.assertNotIn('hidden meta', md)

if __name__ == '__main__':
    unittest.main()
