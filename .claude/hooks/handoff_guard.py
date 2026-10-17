"""Block known human-owned actions in Claude tool calls; not a security sandbox."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTECTED_FILES = {'README.md', 'GLOSSARY.md', 'BRIEF.pdf', 'SUBMISSION.md'}
PROTECTED_TREES = ('grader/', 'data/')
SHELL_TOOLS = {'Bash', 'PowerShell'}

def block_reason(payload: dict) -> str | None:
    name = payload.get('tool_name', '')
    tool = payload.get('tool_input') or {}
    if name in {'Write', 'Edit'}:
        raw = str(tool.get('file_path', '')).replace('\\', '/')
        p = Path(raw)
        if p.is_absolute():
            try:
                raw = p.resolve().relative_to(ROOT).as_posix()
            except ValueError:
                return None
        else:
            raw = p.as_posix().removeprefix('./')
        if raw in PROTECTED_FILES or raw.startswith(PROTECTED_TREES):
            return 'Supplied brief, grader and data are protected. Fix the implementation or create original eval fixtures instead.'
        return None
    if name not in SHELL_TOOLS:
        return None
    command = str(tool.get('command', ''))
    flags = re.IGNORECASE
    # Inspecting an entry point is allowed; --help is not a real corpus run.
    # Reject compounds here so a second command cannot hide after the inspection.
    if not re.search(r'[;&|\n`]', command):
        if re.fullmatch(r'\s*(?:cat|sed|head|tail|rg)\s+[^\n]+', command, flags):
            return None
        if re.fullmatch(r'\s*[\w./\\:-]*python[\d.]*(?:\.exe)?\s+[\w./\\-]+\.py\s+--help\s*', command, flags):
            return None
    # Named user exception (2026-10-17, .claude/rules/human-execution.md): the project runs the submission needs:
    # eval runs, practice run/grade, the exam answer sheet, harness steps on evals/, data/scenarios and data/exam.
    # One command at a time (no chaining), python entry points only (no make), and every path argument inside the
    # project's run areas. Secrets, model downloads, training and publishing stay gated below.
    if not re.search(r'[;&|\n`]', command) and not re.search(r'\bmake\b', command, flags):
        py = r'\s*(?:time\s+)?(?:PYTHONIOENCODING=utf-?8\s+)?[\w./\\:-]*python[\d.]*(?:\.exe)?\s+'
        entry = (r'(?:evals[/\\]run_evals\.py|grader[/\\]run_grader\.py|tools[/\\]run_mailbox\.py|'
                 r'harness[/\\]harness\.py\s+(?:ingest|report|feedback))(?:\s|$)')
        m = re.match(py + entry + r'(.*)$', command, flags)
        if m:
            area = r'"?(?:evals[/\\]|data[/\\](?:scenarios|exam)\b|out[/\\]|report_card\.(?:json|txt)|answer_sheet\.json|harness[/\\]harness\.py|python\b)'
            words = [w for w in re.split(r'\s+', m.group(1)) if w]
            values = [w.lstrip('2>').lstrip('>') for w in words if not w.startswith('-')]
            values = [v.strip('"') for v in values if v and not re.fullmatch(
                r'\d{4}-\d{2}-\d{2}|supervised|autonomous|both|[\d.]+|[\w-]+', v.strip('"'))]
            if all(re.match(area, v, flags) for v in values):
                return None
    # Not gated: offline checks/tests, make setup/validate/clean and dependency installs.
    # Human-owned: API/service setup, API-backed runs, ML/AI preprocessing, model preparation,
    # training and publishing.
    gates = [
        (r'\bmake\b[^\n;&|]*\b(?:run|grade|sheet|eval)\b', 'API-backed mailbox or eval run'),
        (r'\bclaude\s+(?:login|logout|setup-token)\b', 'account/API setup'),
        (r'\b(?:ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN|ANTHROPIC_BASE_URL|CLAUDE_CODE_OAUTH_TOKEN)\s*=', 'API credential/service setup'),
        (r'\bsetx\s+(?:ANTHROPIC_\w+|CLAUDE_CODE_OAUTH_TOKEN)\b', 'API credential/service setup'),
        (r'\b(?:curl|wget|Invoke-WebRequest|Invoke-RestMethod|iwr|irm)\b[^\n;]*(?:anthropic|huggingface|hf\.co)', 'API call or model download'),
        (r'\b(?:hf|huggingface-cli)\s+download\b', 'model download'),
        (r'\b(?:python[\d.]*|bash|sh|pwsh|powershell)\b[^\n;&|]*(?:harness\.py\s+(?:ingest|report|feedback)|run_mailbox\.py|run_grader\.py|run_evals\.py|smoke_api\.py|live_check\.py|live_eval\.py)', 'real-mailbox AI processing or API-backed replay'),
        (r'(?:^|[\s;&|])(?:[./\\\w-]+[/\\])?(?:preprocess|prepare_embeddings|prepare_model|prepare_reranker|export_model|export_reranker|quantize_model|quantize_reranker|build_index|train|finetune|fine_tune|fit_confidence|calibrate_confidence)[\w.-]*\.(?:py|sh|ps1)\b', 'ML/AI preprocessing, model preparation or training'),
        (r'\bpython[\d.]*\b[^\n;]*(?:snapshot_download|hf_hub_download|from_pretrained|SentenceTransformer\s*\(|anthropic\.Anthropic|client\.messages\.create|\.fit\s*\()', 'inline API/model preparation or training'),
        (r'\bgit\s+push\b|\bgh\s+(?:repo\s+create|api\b)', 'external publication/account operation'),
    ]
    for pattern, category in gates:
        if re.search(pattern, command, flags):
            return ('Human execution required for ' + category + '. Prepare /nova-handoff with exact steps, expected artifacts and safe output to return; the user runs it in their terminal. Do not bypass via another command/tool.')
    return None

def deny(reason: str) -> dict:
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionReason': reason}}

def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError('invalid payload')
        reason = block_reason(payload)
    except (ValueError, TypeError):
        reason = 'Invalid hook input: stop and diagnose the workflow guard; do not execute the proposed tool call.'
    if reason:
        print(json.dumps(deny(reason)))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
