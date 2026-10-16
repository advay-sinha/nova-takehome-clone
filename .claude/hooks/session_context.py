"""Emit a short reminder only; never start installations or corpus work."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
try:
    state = json.loads((root / '.claude/progress.json').read_text())
    phase = state.get('current_phase', 'unknown')
except (OSError, ValueError):
    phase = 'unknown'
print('Nova: read CLAUDE.md and phase ' + str(phase) + '. Claude may run offline checks/tests and install dependencies into .venv. Human executes API/service setup, API-backed runs (grade/sheet/run/eval, real-mailbox harness), ML/AI preprocessing and model preparation, training and publishing. Prepare concrete steps; do not bypass. See .claude/references/HUMAN-HANDOFF.md.')
