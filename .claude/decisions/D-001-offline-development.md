# Decision: develop offline, no personal Anthropic key

Status: SUPERSEDED on 2026-10-16 by D-002 (auto-select SDK or local Claude Code CLI back end).

Date: 2026-10-13. Decided by: user.

Context and observed failure: The harness extracts document meaning with Claude through the Anthropic SDK. `make grade` (practice report card) and `make sheet` (exam answer sheet, the pass/fail gate) run the harness over a full mailbox, so they need a working API route. Claude Pro/Claude Code cannot serve the harness's SDK calls.
Options: (a) personal API key used only in the user's terminal; (b) ask the employer for a testing route; (c) stay offline and disclose the gap.
Chosen option and why: (c), the user's choice. The evaluator supplies its own key at grading time; development continues with real local components (reader, OCR, SQL retrieval, embeddings, Decimal rules, policy) and an explicit mock extraction provider for tests.
Evidence / test: none yet; this records the choice.
Time and runtime impact: none at evaluator runtime. Live extraction quality, prompt behaviour, latency and cost stay unmeasured.
Human execution needed: none for the API. Any `make grade`/`make sheet` run stays human-owned and needs an API route the user does not have.
Unverified assumptions:
- The evaluator key and `ANTHROPIC_BASE_URL` reach the harness as the README states.
- The model ID in the checked-in config is available to the evaluator.
Consequences to disclose:
- Without a key, `answer_sheet.json` and `report_card.*` cannot come from the real harness, and `make validate` will fail those checks.
- SOLUTION.md and DESIGN.md must state this plainly. Never substitute mock-produced or hand-assembled artifacts.
Open option, not decided: a provider that works without a key (local reader, OCR and generic layout-independent parsing plus embeddings) could let the real harness produce the sheet offline. The README warns that rules tuned to practice layouts fail the hidden set, so this needs its own decision record and evidence before any work.
Revisit condition: the user obtains an API route, the employer offers one, or the offline-provider option is chosen.
