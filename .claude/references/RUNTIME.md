# Runtime boundaries

The grader launches commands in fresh processes, from unrelated working directories, with mailbox/state isolation and filtered environment variables. Persist mutable state under the supplied state path. Read code/config/assets relative to the script.

Honor evaluator ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL. Do not assume arbitrary custom env variables reach the harness. No external database/embedding service, GPU or model-weight download can be assumed. Bundle the encoder/tokenizer/license/manifest with actual bytes, not an LFS pointer.

Public replay defaults to 600 seconds per step; hidden limits are not guaranteed identical. Keep extraction/interpretation calls bounded and cache completed work. Official full replays are human-owned during development; evaluator execution is unattended product operation.

Preserve README.md, GLOSSARY.md and BRIEF.pdf. Never patch the supplied grader/data/answers for scoring. Keep runtime independent from public practice answers and evaluation fixture expectations. Consult actual schema and scripts, not only this summary.
