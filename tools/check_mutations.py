"""Offline fault injection: each synthetic regression must pass normally and fail under its paired mutation.

Only temporary copies of harness/nova and tests/offline are modified. A crash, import error, missing test or skipped
test is an invalid check, never a detected regression. No model calls or submission artifacts are involved.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# name, module, exact edit, replacement, independent regression asserting the required behavior
MUTATIONS = [
    ("inclusive monetary threshold", "report.py", 'THRESHOLD = Decimal("5000.00")',
     'THRESHOLD = Decimal("5000.01")',
     "test_report_feedback.ActionTests.test_exactly_5000_goes_to_human_review_in_both_modes"),
    ("aggregate outbound findings", "report.py", 'sums.get(group, Decimal("0")) + c.amount_usd',
     'c.amount_usd', "test_report_feedback.ActionTests.test_findings_on_one_invoice_are_summed"),
    ("supervised action boundary", "report.py", 'elif mode == "supervised":', 'elif False:',
     "test_report_feedback.ActionTests.test_exactly_5000_goes_to_human_review_in_both_modes"),
    ("trusted pickup source", "report.py", 'TRUSTED_PICKUP = {"tracking", "carrier_email"}',
     'TRUSTED_PICKUP = {"tracking", "carrier_email", "invoice"}',
     "test_report_feedback.ActionTests.test_autonomous_needs_a_tracked_pickup_date"),
    ("conflict rate period", "report.py", 'a["period"] == b["period"]', 'True',
     "test_report_guards.ConflictScopeTests.test_conflict_in_another_rate_period_does_not_block"),
    ("all invoice lanes", "report.py", 'for a in scopes for b in disputed', 'for a in scopes[:1] for b in disputed',
     "test_report_guards.ConflictScopeTests.test_conflict_on_second_lane_blocks_a_related_freight_dispute"),
    ("complete numeric values", "extract/validate.py", 'Decimal(token.replace(",", "")) == number',
     'str(number) in token.replace(",", "")',
     "test_extract_validate.ValidateTests.test_number_must_be_a_whole_value"),
    ("rejected evidence blocks execution", "report.py", 'c.signals["unverified"] = True',
     'c.signals["unverified"] = False',
     "test_report_guards.EvidenceGuardTests.test_rejected_citation_prevents_unattended_action"),
    # Added with the unseen-world suite; each guard passes on the real code and names the defect it pins.
    ("retro after an empty report", "report.py",
     'store.db.execute("INSERT OR IGNORE INTO report_runs VALUES (?, ?)", (mode, as_of))',
     'store.db.execute("SELECT ?, ?", (mode, as_of))',
     "test_report_feedback.ActionTests.test_key_created_by_a_backdated_amendment_after_an_empty_report_is_retro"),
    ("inclusive weight-break upper bound", "world.py", "(self.hi is None or weight <= self.hi)",
     "(self.hi is None or weight < self.hi)",
     "test_overcharge.OverchargeTests.test_weight_on_a_band_upper_bound_is_priced_in_that_band"),
    ("INR converted once", "report.py", 'or c.signals.get("usd_done") or c.cls == "overcharge":',
     'or c.signals.get("usd_done"):',
     "test_report_guards.CurrencyTests.test_inr_overcharge_is_converted_once_in_the_report"),
    ("duplicate self-collision", "rules/duplicate.py", "if k in first_seen and first_seen[k][0] != inv:",
     "if k in first_seen:",
     "test_detectors.DuplicateTests.test_two_lines_of_one_shipment_on_one_invoice_do_not_collide"),
    ("waiver scope by shipment", "rules/waiver.py",
     'return norm_id(line.get("house_awb") or line.get("awb")) in awbs or norm_id(line.get("awb")) in awbs',
     "return True",
     "test_unseen_metamorphic.PageAndScopeTests.test_one_off_waiver_follows_the_named_shipment_only"),
    ("ledger paid wording", "rules/common.py", r'PAID = re.compile(r"\b(?:paid|settled|cleared|remitted)\b", re.I)',
     r'PAID = re.compile(r"\b(?:paid)\b", re.I)',
     "test_reader_generalisation.LedgerWordsTests.test_status_words"),
    ("grace period wording", "extract/local_contracts.py", r'number(r"\bwithin\s+("',
     r'number(r"\bwithin_never\s+("',
     "test_reader_generalisation.AgreementGrammarTests.test_grace_written_as_payment_within_n_days"),
    ("clause across a page break", "extract/local_common.py",
     'if current and p != src_page and re.search(r"[.;:!?)]\\s*$", last):', "if current and p != src_page:",
     "test_unseen_metamorphic.PageAndScopeTests.test_grace_clause_split_across_a_page"),
    # Found by the frozen-reader holdout run (w2_h05, w4_h12) and fixed afterwards.
    ("dotted dates are day-first", "extract/validate.py",
     'if not dmy and not mdy and found and all(sep == "." for _, sep, _, _ in found):', "if False:",
     "test_reader_generalisation.HoldoutFoundTests.test_dotted_numeric_dates_are_day_first_when_no_day_exceeds_twelve"),
    ("amendment moves the term end", "extract/local_contracts.py",
     'c["term"].update(initial_term_end=iso(m[1], doc.order), source=src)', 'c["term"].update(source=src)',
     "test_reader_generalisation.HoldoutFoundTests.test_amendment_sentence_that_moves_the_term_end"),
    ("extension keeps renewal terms", "rules/expiry.py",
     'term = {**{k: v for k, v in term.items() if k != "non_renewal_notice_deadline"},', "term = {**{},",
     "test_reader_generalisation.HoldoutFoundTests.test_extension_keeps_the_agreement_renewal_terms"),
    ("OCR-glued waybill cell", "extract/local_billing.py", "or capture(GLUED_AWB, line, flags=0)", "",
     "test_reader_generalisation.InvoiceLayoutTests.test_ocr_glued_waybill_and_lane_cells"),
]
# The metamorphic guards build their mailboxes with the unseen-world document writers and oracle.
COPY = [("harness/nova", ()), ("tests/offline", ()),
        ("evals/unseen_worlds", ("mailboxes", "results", "cases", "feedback"))]

CHILD = """
import io, json, sys, unittest
sys.path.insert(0, sys.argv[1])
suite = unittest.defaultTestLoader.loadTestsFromName(sys.argv[2])
output = io.StringIO()
result = unittest.TextTestRunner(stream=output).run(suite)
print(json.dumps({"run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                  "skipped": len(result.skipped), "output": output.getvalue()}))
"""


def run_guard(root: Path, guard: str) -> dict:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("ANTHROPIC_API_KEY", None)
    process = subprocess.run([sys.executable, "-B", "-c", CHILD, str(root / "tests/offline"), guard],
                             cwd=root, env=env, text=True, encoding="utf-8", capture_output=True, timeout=60)
    if process.returncode:
        raise RuntimeError(f"guard process failed: {guard}\n{process.stderr[-2000:]}")
    result = json.loads(process.stdout)
    if result["run"] != 1 or result["errors"] or result["skipped"]:
        raise RuntimeError(f"guard did not complete normally: {guard}\n{result['output']}")
    return result


def main() -> int:
    caught = 0
    for name, module, original, replacement, guard in MUTATIONS:
        with tempfile.TemporaryDirectory(prefix="nova-mutation-") as tmp:
            root = Path(tmp)
            for rel, skip in COPY:
                shutil.copytree(ROOT / rel, root / rel, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", *skip))
            control = run_guard(root, guard)
            if control["failures"]:
                raise RuntimeError(f"unmodified control failed: {guard}\n{control['output']}")
            target = root / "harness/nova" / module
            text = target.read_text(encoding="utf-8")
            if text.count(original) != 1:
                raise RuntimeError(f"mutation must match exactly once: {name}")
            changed = text.replace(original, replacement, 1)
            compile(changed, str(target), "exec")
            target.write_text(changed, encoding="utf-8")
            detected = run_guard(root, guard)["failures"] > 0
            caught += int(detected)
            print(f"{'CAUGHT' if detected else 'MISSED'}: {name}", flush=True)
    print(f"{caught}/{len(MUTATIONS)} mutations detected; all unmodified controls passed")
    return 0 if caught == len(MUTATIONS) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"mutation check invalid: {exc}", file=sys.stderr)
        raise SystemExit(2)
