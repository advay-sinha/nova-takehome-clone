# Human execution ownership

This is the user's explicit workflow preference, not a permission that the assistant can waive.

Revised 2026-10-13 at the user's request: Claude runs offline checks and dependency installs itself. Human gates are limited to API/service setup, API-backed runs, ML/AI preprocessing and model preparation, training, and publishing.

| Operation | Claude may do | Human must do |
|---|---|---|
| Design, source edits, fixtures | Implement and review | Clarify business ambiguity when necessary |
| Offline checks and tests | Run setup checks, hook tests, offline unit tests and `make validate` with the `.venv` interpreter | Nothing |
| Dependency/environment installation | Create/update `.venv`, install pinned requirements (`make setup`, pip/uv into `.venv`) | Only system-level installs that need admin rights |
| API/account/secret/service setup | Implement adapter/config docs and presence-only diagnostics | Login/configure secrets and services; never disclose them in chat |
| API-backed runs (live smoke test, `make grade/sheet/run/eval`, real-mailbox harness ingest/report/feedback) | Prepare entry points, budget and expected outputs | Run them and share redacted output |
| ML/AI preprocessing (real-mailbox OCR, embedding, indexing) | Write and review entry points; test on small synthetic fixtures | Execute corpus processing and verify outputs |
| Encoder/reranker download/export/quantization | Prepare exact model revision, scripts and asset manifest | Run preparation and verify packaged assets |
| Training/fine-tuning | First explain need, data split, metrics, cost and deployment impact | Choose whether to proceed, then execute |
| Publishing/submission/invitation | Prepare final files, commit and draft instructions | Explicitly direct/perform the external action |

At a human gate: finish authorized preparation, create a concrete request from the template, explain why the user owns this action, provide shell-specific numbered steps, then wait for the user's execution result. Mark dependent work BLOCKED_HUMAN, not done. Continue independent coding only when safe and useful. Do not repeatedly request a gate already completed; rerun only if relevant inputs changed or the first attempt failed.

An approval to proceed is not an execution result. Do not fabricate status, run the command anyway or bypass the guard through a different shell, Python snippet, SDK, tool or subagent. If the user later explicitly changes this policy for a named action, record that changed instruction and its scope; do not silently broaden it.

Development is Claude Pro-only by default. Evaluator API credentials are supplied externally. Do not insist on a personal API purchase. If local live testing is unavailable, label it unverified and describe the resulting delivery gap without replacing genuine artifacts with mocks.
