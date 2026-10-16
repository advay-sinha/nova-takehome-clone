"""Export this project's real Claude Code session transcripts into ai_log/, secrets redacted.

Standard library only. Re-run after each working session; output files are overwritten.

    .venv/Scripts/python.exe ai_log/export_claude_sessions.py           # Windows venv
    python ai_log/export_claude_sessions.py --source <transcript dir>   # explicit source

For every <session>.jsonl it writes:
  ai_log/claude-code/<session>.jsonl  the raw transcript, secrets redacted, nothing else removed
  ai_log/claude-code/<session>.md     a readable log: user prompts and assistant text verbatim,
                                      tool calls as one line each, tool output omitted
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / 'claude-code'
SECRET_PATTERNS = [
    re.compile(r'sk-ant-[A-Za-z0-9_-]{10,}'),
    re.compile(r'\bsk-[A-Za-z0-9]{20,}'),
    re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}'),
    re.compile(r'\bxox[abposr]-[A-Za-z0-9-]{10,}'),
    re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
    re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._~+/-]{20,}=*'),
    # Backslashes before the quote cover quotes escaped (possibly several times) inside JSON transcript lines.
    re.compile(r'(?i)\b(ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN|CLAUDE_CODE_OAUTH_TOKEN)(\s*[=:]\s*)(?:\\*["\'])?[^\s"\'\\]{8,}'),
]
TOOL_FIELDS = ('command', 'file_path', 'pattern', 'path', 'skill', 'query', 'url', 'description')

def default_source() -> Path:
    # Claude Code stores transcripts under ~/.claude/projects/<project path with separators replaced by '-'>.
    return Path.home() / '.claude' / 'projects' / re.sub(r'[:\\/]', '-', str(REPO))

def redact(text: str) -> tuple[str, int]:
    count = 0
    for pattern in SECRET_PATTERNS:
        if pattern.groups:
            text, n = pattern.subn(lambda m: m.group(1) + m.group(2) + '[REDACTED]', text)
        else:
            text, n = pattern.subn('[REDACTED]', text)
        count += n
    return text, count

def blocks(message: dict) -> list:
    content = message.get('content')
    if isinstance(content, str):
        return [{'type': 'text', 'text': content}]
    return content if isinstance(content, list) else []

def tool_line(block: dict) -> str:
    args = block.get('input') or {}
    shown = [f'{k}={str(args[k])[:200]!r}' for k in TOOL_FIELDS if k in args]
    return f"- tool `{block.get('name')}` " + ', '.join(shown)

def readable(records: list[dict], name: str) -> str:
    lines = [f'# Claude Code session {name}', '',
             'Exported by ai_log/export_claude_sessions.py: prompts and replies verbatim, tool calls summarized, '
             'tool output omitted, secrets redacted. The redacted .jsonl beside this file is the complete record.', '']
    for rec in records:
        kind, msg = rec.get('type'), rec.get('message') or {}
        if kind not in ('user', 'assistant') or rec.get('isMeta'):
            continue
        stamp = rec.get('timestamp', '')
        for block in blocks(msg):
            btype = block.get('type')
            if kind == 'user' and btype == 'text' and block.get('text', '').strip():
                lines += [f'## User ({stamp})', '', block['text'].strip(), '']
            elif kind == 'assistant' and btype == 'text' and block.get('text', '').strip():
                lines += [f'### Assistant ({stamp})', '', block['text'].strip(), '']
            elif kind == 'assistant' and btype == 'tool_use':
                lines.append(tool_line(block))
        if kind == 'assistant' and any(b.get('type') == 'tool_use' for b in blocks(msg)):
            lines.append('')
    return '\n'.join(lines) + '\n'

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--source', type=Path, default=None, help='directory holding <session>.jsonl transcripts')
    args = parser.parse_args()
    source = args.source or default_source()
    sessions = sorted(source.glob('*.jsonl'))
    if not sessions:
        print(f'No transcripts found in {source}', file=sys.stderr)
        return 1
    OUT.mkdir(exist_ok=True)
    for path in sessions:
        raw, hits = redact(path.read_text(encoding='utf-8'))
        records = [json.loads(line) for line in raw.splitlines() if line.strip()]
        (OUT / path.name).write_text(raw, encoding='utf-8', newline='\n')
        (OUT / (path.stem + '.md')).write_text(readable(records, path.stem), encoding='utf-8', newline='\n')
        print(f'{path.name}: {len(records)} records, {hits} redactions')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
