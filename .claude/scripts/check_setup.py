"""Read-only validation of the Claude setup package; standard library only."""
import json
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
errors=[]
required=['CLAUDE.md','.claude/SETUP.md','.claude/progress.json','.claude/WORKLOG.md',
          '.claude/rules/human-execution.md','.claude/references/HUMAN-HANDOFF.md',
          '.claude/hooks/handoff_guard.py','.claude/hooks/session_context.py',
          '.claude/templates/HANDOFF.md','.claude/templates/EXPERIMENT.md',
          '.claude/templates/FINDING-TRACE.md','.claude/references/DIFFERENTIATORS.md',
          'docs/NOVA-SOLUTION-PLAN.md']
for name in required:
    if not (ROOT/name).is_file():errors.append('Missing '+name)
try:
    settings=json.loads((ROOT/'.claude/settings.json').read_text())
    for event in ['SessionStart','PreToolUse']:
        if event not in settings.get('hooks',{}):errors.append('Missing hook '+event)
    for event in settings.get('hooks',{}).values():
        for group in event:
            for hook in group.get('hooks',[]):
                refs=re.findall(r'\$CLAUDE_PROJECT_DIR/([^"\s]+)',hook.get('command',''))
                if not refs or not all((ROOT/ref).is_file() for ref in refs):errors.append('Invalid hook script reference')
except (OSError,ValueError) as exc:errors.append('settings.json: '+str(exc))
try:
    json.loads((ROOT/'.claude/progress.json').read_text())
except (OSError,ValueError) as exc:errors.append('progress.json: '+str(exc))
skills=sorted((ROOT/'.claude/skills').glob('*/SKILL.md'))
for skill in skills:
    text=skill.read_text()
    if not text.startswith('---\n'):errors.append('No frontmatter: '+str(skill))
    parts=text.split('---',2)
    front=parts[1] if len(parts)>2 else ''
    if not re.search(r'^name: '+re.escape(skill.parent.name)+r'$',front,re.M):errors.append('Skill name mismatch: '+str(skill))
    if not re.search(r'^description: .+',front,re.M):errors.append('Missing skill description: '+str(skill))
    if not re.fullmatch(r'[a-z0-9-]+',skill.parent.name):errors.append('Invalid skill name: '+str(skill))
if len(skills)!=8:errors.append('Expected 8 project skills')
phases=sorted((ROOT/'.claude/phases').glob('[0-9][0-9]-*.md'))
if len(phases)!=10:errors.append('Expected 10 phase guides')
index=(ROOT/'.claude/phases/INDEX.md').read_text()
for phase in phases:
    if phase.name not in index:errors.append('Phase missing from index: '+phase.name)
if errors:
    print('\n'.join('FAIL '+e for e in errors))
    sys.exit(1)
print(f'PASS: {len(skills)} skills, {len(phases)} phases, settings/progress/hooks and reference files.')
print('Scope: setup only; harness, live extraction, model assets and exam answers are unverified.')
