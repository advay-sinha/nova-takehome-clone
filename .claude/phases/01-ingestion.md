# Phase 01: Readers and persistent state

Complete required correctness and verification before optional experiments. Read progress and the previous phase's evidence before starting. Preserve the user execution policy.

## Implement

Implement CLI plumbing, canonical EML/PDF/XLSX reader, source occurrence metadata, UTC receipt dates, SQLite transactions, pages and scan/OCR adapter. Keep same-content email resends as separate occurrences. Test arbitrary cwd, restart and idempotence using small synthetic fixtures.

Preserve field/source versions needed by later traces. Keep raw OCR observations separate from normalized values; provenance lists are enough, with no graph database.

## Human execution gate

Human executes any real-mailbox OCR/preprocessing; Claude may install dependencies. Prepare reviewed entry point, fresh state path and counts. Synthetic in-memory reader tests may run autonomously.

Prepare exact reviewed commands using `/nova-handoff`, then wait for the user's output. Do not treat user approval as an execution result. Continue independent code only if useful.

## Exit evidence

Three CLI commands wired; source provenance and receipt timestamps stored; scan extraction path implemented; offline restart/idempotence cases pass.

Source/fact identities can support reproducible traces without depending on file order.

Record actual files/checks, limitations, open handoff IDs and the next task in progress/WORKLOG. Separate IMPLEMENTED, VERIFIED_OFFLINE and VERIFIED_LIVE. Commit a coherent slice when appropriate; publishing remains user-directed.
