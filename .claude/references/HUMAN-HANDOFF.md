# Manual operation procedure

1. Classify the operation using `rules/human-execution.md`.
2. Prepare/review the relevant files and verify scripts on isolated mocks where possible. Do not start the actual human-owned run.
3. Create `.claude/handoffs/H-NNN-<slug>.md` from `templates/HANDOFF.md`. Add its ID to progress. Use the actual repository path, shell and existing script arguments.
4. Give the user a short explanation and numbered steps. Ask them to execute, not merely approve.
5. Mark WAITING_HUMAN and keep dependent phase work blocked. Work on independent code if useful.
6. On returned output, verify artifacts read-only and check reproducibility/provenance. Record failures accurately. Repeated commands need a new request only when their inputs or scope materially changed.

## Environment installation

Claude creates/updates `.venv` and installs pinned `harness/requirements.txt` itself. Hand off only system-level installs that need admin rights (Python, make, system libraries); do not guess an OS install command. WSL has the original Makefile path conventions; on native Windows use `.venv/Scripts/python.exe`.

## API setup

Default: evaluator owns the API key. Implement providers reading the supplied ANTHROPIC_API_KEY and ANTHROPIC_BASE_URL, and locally test adapters with mocks. Do not ask the user to buy API credits or paste credentials. If the user explicitly chooses live testing, explain a presence-only configuration check and a small script using credentials in their terminal; they run it and share sanitized status. Their Claude Pro login is separate from the harness API configuration.

## Preprocessing and embeddings

Author a deterministic preprocessing entry point first, document input batch/mailbox paths and a fresh `--state-dir`, preserve raw source/citations and make re-ingest idempotent. Then give the exact `--help`-verified command and expected page/fact/chunk/vector counts. Do not overwrite existing state blindly.

For encoder or optional reranker preparation, specify model/revision, CPU runtime, output directory, tokenizer consistency, pooling, hashes/license and offline inference check. The user downloads/exports/quantizes the model. Reranking additionally requires a phase 07 experiment gate, paired tokenizer/classification checks and a CPU benchmark. Corpus vectors are produced by the real ingestion path and belong under state, not in a code patch keyed to exam answers.

Do not provide invented executable names. `tools/preprocess.py`, `tools/prepare_embeddings.py` or `tools/train.py` are suggestions until implemented and verified; show a command only when its target exists and arguments are known.

## Training if it ever becomes necessary

There is no training or learned-confidence phase in the current scope. A new scope decision is required before adding one. First write a decision explaining a real failure, representative labeled data, train/validation/test separation, leakage controls, baseline and target metrics, CPU/GPU/memory/time needs, artifacts and evaluator compatibility. Ask the user to choose whether to add training. If chosen, finish a runnable training/config/evaluation script, then issue a human-execution request. An instruction to train a model is not permission for Claude to execute the training itself under this project policy.

## Official runs and final artifacts

Once code is ready, prepare the original `make grade`, `make sheet`, `make eval`, `make validate` commands for the user. Explain that live-provider credentials may be needed. Read actual returned report cards, exam report, answer sheet and eval results before marking verified. Local mocks are never substituted for official outputs. Final submission or invitation stays user-directed.
