# Acceptance matrix

| Area | Required evidence |
|---|---|
| CLI/state | Three commands, JSON-only stdout, arbitrary cwd, restart persistence, idempotence |
| Reader/extraction | EML/PDF/XLSX/scan, exact citations, typed fields, distinct email occurrences |
| Structured retrieval | Complete applicable records/ledger; receipt/effective dates; no entity leakage |
| Embeddings | Actual local asset bytes, matching tokenizer/revision, 384 dimensions, no download at runtime |
| Hybrid search/RAG | Relevant original chunks; parent expansion; mandatory coverage; grounded validated proposal |
| Money | Decimal and exact per-line/finding/FX behavior; all finding classes and clean controls |
| Feedback/history | All listed decisions/types; every scope filter; supersedes/retro/learned_at; no stale findings |
| Actions | Both modes; aggregated $5,000 boundary; Schedule 1 recipient; no unsafe execution |
| Evaluations | At least 10 original cases beyond samples; retrieval tests; genuine runner output and actual caught bug |
| Submission | Completed templates, actual official artifacts, prompt log, honest limits and final commit |

Status vocabulary: NOT_STARTED, IN_PROGRESS, BLOCKED_HUMAN, IMPLEMENTED, VERIFIED_OFFLINE, VERIFIED_LIVE. Offline success alone does not mean every phase has been validated end-to-end. Keep user execution records separate from code status.

## Additional acceptance evidence for this revision

| Area | Required evidence |
|---|---|
| Field verification | Distinguish extraction error, legitimate tax/discount and real overcharge; bounded source-backed recheck; live quality labeled honestly |
| Decision traces | Fact/source versions, typed operands, governing rule, rounding/FX and action gates; replay catches mismatches; unchanged report schema |
| Generalization | Six transformation families with independently expected relations; no parent/variant split leakage |
| Optional reranker | Off by default; diagnosed failure and measured quality/CPU/assets gates, or recorded defer/reject decision |
