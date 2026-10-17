# Human execution request: H-001 / Reader check on the real mailboxes

Status: VERIFIED
Phase: 01
Reason you must run this: real-mailbox preprocessing, including OCR of the scanned invoices (human-owned under `.claude/rules/human-execution.md`).
Prepared files: `harness/harness.py`, `harness/nova/{app,reader,store,ocr,textlayer}.py`. No model or API calls exist yet in the harness.
Working directory: `D:\Code\sides\nova-takehome`
Terminal: PowerShell
Prerequisites: `.venv` with `harness/requirements.txt` (already installed).
Expected time/resources: unmeasured; local CPU only. OCR of the two scans loads RapidOCR once per process.
Reads: `data/scenarios/batch_01`, `batch_02`, `data/exam/batch_01`, `batch_02` (read-only).
Writes: `out/state_check_practice/`, `out/state_check_exam/` (gitignored by `out/state_*/`).
Network/API: none.

## Steps

1. Open PowerShell in the repository root.
2. Run the block below.
3. Send back the stderr lines it prints (the `ingest …` and `report …` summary lines and any `unreadable:` lines), plus the exit codes.

```powershell
$py = ".venv\Scripts\python.exe"
foreach ($b in "batch_01","batch_02") { & $py harness\harness.py ingest "data\scenarios\$b" --state-dir out\state_check_practice; "exit $LASTEXITCODE" }
& $py harness\harness.py report --as-of 2035-09-30 --state-dir out\state_check_practice > $null; "exit $LASTEXITCODE"
foreach ($b in "batch_01","batch_02") { & $py harness\harness.py ingest "data\exam\$b" --state-dir out\state_check_exam; "exit $LASTEXITCODE" }
& $py harness\harness.py report --as-of 2031-02-28 --state-dir out\state_check_exam > $null; "exit $LASTEXITCODE"
```

Expected result: every exit is 0. The planning inventory expects 78 emails + 71 PDFs + 14 XLSX = 163 practice documents and 41 + 41 + 4 = 86 exam documents across the two batches each, with 0 unreadable. The final `report` line says how many documents were received by the last report date.
If it fails: stop and send the full stderr. Do not delete or edit anything under `data/`.
Send back: the stderr summary lines and exit codes. Nothing secret is involved.
Claude will verify: read-only queries on the two state databases (document counts per kind, scan rows, OCR text of the scans compared with what the page shows, receipt-time range against batches.json).
Resume: phase 02 work continues meanwhile; this result confirms the reader on real layouts before extraction relies on it.

## Completion evidence

Executed by: user, 2026-10-16.
Result received: all exit codes 0 (reported by the user; stderr lines not sent).
Artifacts verified (read-only SQL on `out/state_check_practice` and `out/state_check_exam`):
- Practice: 163 documents (78 eml, 71 pdf, 14 xlsx), batch_01 82 / batch_02 81. Exam: 86 documents (41 eml, 41 pdf, 4 xlsx), batch_01 35 / batch_02 51. Both match the planning inventory.
- 0 unreadable; 0 missing receipt times; receipt ranges sit inside each batch's window; documents received by the report dates are 82/163 (practice) and 35/86 (exam).
- Scans: practice `batch_02/0016.eml#TXI-35-36-0024.pdf` and exam `batch_02/0016.eml#CDI-3031-0306.pdf`, 1 page each. OCR text has every line item, rate and amount. Exam spot check: 274 kg x 330.42 = 90,535.08 and 25.33% x 90,535.08 = 22,932.54 match the page.
- Findings for phase 02: OCR drops spaces ("Fuelsurcharge", "275kg") and emits full-width brackets (U+FF08/FF09), so apply NFKC normalisation and compare labels with spaces removed. The exam scan is a different layout ("Charges advice", DD/MM/YYYY dates, Route/Waybill/Charge/Basis/Rate/Amount/Collected, thousands separators). One OCR label is garbled ("Tax !!u"); its amount is intact.
