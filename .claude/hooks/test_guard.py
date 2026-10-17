"""Offline hook contract tests. No corpus, model, API or installation is touched."""
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOK = Path(__file__).with_name('handoff_guard.py')
spec = importlib.util.spec_from_file_location('handoff_guard', HOOK)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

def shell(command, tool='Bash'):
    return guard.block_reason({'tool_name':tool,'tool_input':{'command':command}})

class GuardTests(unittest.TestCase):
    def test_named_exception_project_runs(self):
        allowed = [
            '.venv/Scripts/python.exe evals/run_evals.py',
            '.venv/Scripts/python.exe evals/run_evals.py -k e01',
            '.venv/Scripts/python.exe harness/harness.py ingest evals/mailboxes/m01_wrong_bracket/batch_01 --state-dir out/state_eval/m01 2> out/state_eval/m01.log',
            '.venv/Scripts/python.exe harness/harness.py feedback evals/feedback/m13_close_a_one_off.json --state-dir out/state_eval/m13',
            '.venv/Scripts/python.exe harness/harness.py report --as-of 2041-04-30 --mode autonomous --state-dir out/state_eval/m01',
            'python grader/run_grader.py --harness "python harness/harness.py" --data data/scenarios --key data/scenarios/answers --mode both --out report_card.json',
            'PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe grader/run_grader.py --harness "python harness/harness.py" --data data/scenarios --key data/scenarios/answers --mode both --out report_card.json > report_card.txt',
            '.venv/Scripts/python.exe tools/run_mailbox.py --data data/exam --harness harness/harness.py --out out/exam_report.json --sheet answer_sheet.json',
            '.venv/Scripts/python.exe harness/harness.py ingest data/exam/batch_01 --state-dir out/state_exam',
        ]
        for command in allowed:
            self.assertIsNone(shell(command), command)
        still_blocked = [
            'python harness/harness.py ingest evals/mailboxes/m01/batch_01 --state-dir out/state_eval/m && git push origin main',
            'python harness/harness.py ingest C:/elsewhere/batch_01 --state-dir out/s',
            'python harness/harness.py ingest data/exam/batch_01 --state-dir /tmp/s',
            'python evals/run_evals.py; git push origin main',
            'make eval', 'make grade', 'make sheet',
            'python tools/preprocess.py --input data/scenarios', 'hf download x/y', 'git push origin main',
            'export ANTHROPIC_API_KEY=example', 'claude login',
        ]
        for command in still_blocked:
            self.assertIsNotNone(shell(command), command)

    def test_human_commands_blocked(self):
        commands = [
            'make grade MODE=both', 'make sheet', 'make eval', 'make run',
            'cd repo && make grade',
            'claude login', 'export ANTHROPIC_API_KEY=example', 'setx ANTHROPIC_API_KEY example',
            'python3 tools/preprocess.py --input data/scenarios',
            './tools/train.py --config train.yaml',
            'python3 tools/prepare_embeddings.py',
            'python3 tools/prepare_reranker.py --output harness/assets/reranker',
            'python3 tools/export_reranker.py',
            './tools/quantize_reranker.sh',
            'python3 tools/fit_confidence.py --input labeled.jsonl',
            'python3 tools/calibrate_confidence.py',
            'hf download sentence-transformers/all-MiniLM-L6-v2',
            'python3 -c "model = SentenceTransformer(\"local\")"',
            'curl https://api.anthropic.com/v1/messages', 'git push origin main',
            'python3 tools/smoke_api.py',
            'python3 tools/preprocess.py --help && make grade',
        ]
        for command in commands:
            with self.subTest(command=command):
                self.assertIsNotNone(shell(command))

    def test_read_checks_and_installs_not_blocked(self):
        for command in ['git status --short','git diff','rg -n rate harness',
                        'python3 .claude/hooks/test_guard.py',
                        'python3 .claude/scripts/check_setup.py',
                        '.venv/Scripts/python.exe .claude/scripts/check_setup.py',
                        '.venv/Scripts/python.exe .claude/hooks/test_guard.py',
                        'python3 -m unittest discover -s tests/offline -v',
                        'make setup', 'make validate', 'make clean',
                        'uv pip install -r harness/requirements.txt',
                        'python3 -m pip install numpy', 'python -m venv .venv',
                        '.venv/Scripts/python.exe -m pip install -r harness/requirements.txt',
                        'python3 tools/check_submission.py --harness harness/harness.py',
                        'cat GLOSSARY.md', 'cat tools/train.py',
                        'python3 tools/preprocess.py --help',
                        '.venv/Scripts/python.exe tools/preprocess.py --help',
                        'python3 tools/prepare_reranker.py --help',
                        'cat tools/fit_confidence.py']:
            with self.subTest(command=command):
                self.assertIsNone(shell(command))

    def test_powershell_tool(self):
        for command in ['make sheet', '$env:ANTHROPIC_API_KEY = "example"',
                        'Invoke-WebRequest https://huggingface.co/x -OutFile m.onnx']:
            with self.subTest(command=command):
                self.assertIsNotNone(shell(command, 'PowerShell'))
        for command in ['git status', '.venv\\Scripts\\python.exe -m pip install -r harness\\requirements.txt',
                        '.venv\\Scripts\\python.exe -m unittest discover -s tests\\offline']:
            with self.subTest(command=command):
                self.assertIsNone(shell(command, 'PowerShell'))

    def test_protected_write(self):
        for path in ['README.md','grader/score.py','data/exam/batch_01/x.eml',str(guard.ROOT/'GLOSSARY.md')]:
            self.assertIsNotNone(guard.block_reason({'tool_name':'Write','tool_input':{'file_path':path}}))
        self.assertIsNone(guard.block_reason({'tool_name':'Edit','tool_input':{'file_path':'harness/rules.py'}}))
        self.assertIsNone(guard.block_reason({'tool_name':'Write','tool_input':{'file_path':'evals/cases/original.yaml'}}))

    def test_cli_json_deny(self):
        p=subprocess.run([sys.executable,str(HOOK)],input=json.dumps({'tool_name':'Bash','tool_input':{'command':'make sheet'}}),text=True,capture_output=True)
        self.assertEqual(p.returncode,0)
        self.assertEqual(json.loads(p.stdout)['hookSpecificOutput']['permissionDecision'],'deny')
        self.assertNotIn('make sheet',json.loads(p.stdout)['hookSpecificOutput']['permissionDecisionReason'])

    def test_cli_allowed_silent(self):
        p=subprocess.run([sys.executable,str(HOOK)],input=json.dumps({'tool_name':'Bash','tool_input':{'command':'git status'}}),text=True,capture_output=True)
        self.assertEqual(p.returncode,0)
        self.assertEqual(p.stdout,'')

    def test_malformed_input_denied(self):
        p=subprocess.run([sys.executable,str(HOOK)],input='{bad',text=True,capture_output=True)
        self.assertEqual(json.loads(p.stdout)['hookSpecificOutput']['permissionDecision'],'deny')

if __name__=='__main__':
    unittest.main(verbosity=2)
