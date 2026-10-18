"""Score the harness on the unseen-world cases, local document reader only. Behind `make eval-unseen`.

    python evals/unseen_worlds/run_unseen.py [--split dev|holdout|all] [-k text] [--workers 4]

Every case runs once per mode from an empty temporary state folder: the batches are ingested in order (feedback after
the batch it names), and each report point is run after the batch it names. Each child process gets
--local-reader-only and an environment with NOVA_LOCAL_READER_ONLY=1 and without ANTHROPIC_API_KEY,
ANTHROPIC_BASE_URL or NOVA_LOCAL_LLM; afterwards the state database must show only local-reader extraction units
and an empty model-response cache, or the case fails.

Scoring compares the complete set of items each report point expects (finding, conflict, cannot_determine) with
everything the report lists under those verdicts: per class true/false positives and misses, amounts within USD
0.01, conflict ranges and cited sources, missing-document names, actions in each mode, named clean controls, the
grader's schema and citation checks, and action-gate safety. Expected answers come from the case files only; the
harness's own rules are never consulted. Results go to results/<split>_results.json and <split>_summary.txt.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HARNESS = ROOT / "harness" / "harness.py"
sys.path.insert(0, str(ROOT / "grader"))
import score as S  # noqa: E402  (grader key/amount matching only)
import validate as V  # noqa: E402  (grader schema and citation checks)

POSITIVE = ("finding", "conflict", "cannot_determine")
MODES = ("supervised", "autonomous")
MODEL_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "NOVA_LOCAL_LLM")
LOCAL_LINE = "NOVA_LOCAL_READER_ONLY=1; using local document reader"


def child_env() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in MODEL_ENV}
    env["NOVA_LOCAL_READER_ONLY"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    # Parallel cases each load numpy (OCR); one BLAS thread each keeps memory bounded.
    env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    return env


def harness(args: list[str], timeout: float) -> tuple[int, str, str]:
    try:
        r = subprocess.run([sys.executable, str(HARNESS), "--local-reader-only"] + args, capture_output=True,
                           text=True, encoding="utf-8", timeout=timeout, env=child_env())
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout:.0f} s"


def local_only_proof(state: Path) -> list[str]:
    """Problems if any unit used a non-local back end or any model response was cached."""
    db = state / "nova.sqlite3"
    if not db.is_file():
        return ["no state database"]
    with closing(sqlite3.connect(db)) as c:
        units = c.execute("SELECT kind, backend, model FROM extraction_units").fetchall()
        cached = c.execute("SELECT count(*) FROM llm_cache").fetchone()[0]
    bad = [f"unit {k} used {b}/{m}" for k, b, m in units if b not in (None, "local") or (b and m != "local-reader-1")]
    if cached:
        bad.append(f"{cached} model-response cache row(s)")
    return bad


def extracted_ids(state: Path) -> set[str]:
    """Invoice and contract ids the reader stored: tells a parser miss from a rule miss."""
    with closing(sqlite3.connect(state / "nova.sqlite3")) as c:
        rows = c.execute("SELECT kind, data_json FROM facts WHERE kind IN ('invoices', 'contracts') "
                         "AND status != 'rejected'").fetchall()
    out = set()
    for kind, data in rows:
        d = json.loads(data)
        out.add(S.norm_invoice(d.get("invoice_id") if kind == "invoices" else d.get("contract_id")))
    return out


def compare(exp: dict, got: dict, mode: str) -> list[str]:
    bad = []
    if "amount_usd" in exp and not S.amount_ok(got.get("amount_usd"), exp["amount_usd"]):
        bad.append(f"amount {got.get('amount_usd')} != {exp['amount_usd']}")
    if "amount_range" in exp and not S.range_ok(got.get("amount_range"), exp["amount_range"]):
        bad.append(f"range {got.get('amount_range')} != {exp['amount_range']}")
    want_action = exp["actions"][mode]
    if str(got.get("action")) != want_action:
        bad.append(f"action {got.get('action')} != {want_action}")
    if exp.get("deadline") and str(got.get("deadline")) != exp["deadline"]:
        bad.append(f"deadline {got.get('deadline')} != {exp['deadline']}")
    if exp.get("missing_doc"):
        name = (got.get("missing_doc") or {}).get("name")
        if not S.names_match(exp["missing_doc"], name):
            bad.append(f"missing_doc {name!r} does not name {exp['missing_doc']!r}")
    cited = [e.get("doc", "") for e in got.get("evidence") or [] if isinstance(e, dict)]
    for doc in exp.get("evidence_docs", []):
        if not any(S.same_doc(doc, c) for c in cited):
            bad.append(f"evidence does not cite {doc}")
    if exp.get("learned_at") and not got.get("learned_at"):
        bad.append("learned_at missing")
    if exp.get("retro") and got.get("retro") is not True:
        bad.append("retro: true missing")
    if exp.get("retro") and got.get("supersedes"):
        bad.append("retro key must not list supersedes")
    if exp.get("supersedes") and not got.get("supersedes"):
        bad.append("supersedes missing")
    return bad


def score_point(point: dict, report: dict, mode: str, mailbox: Path, ids: set[str]) -> dict:
    items = S.report_items(report)
    reported = {S.key_tuple(it): it for it in items if it.get("verdict") in POSITIVE}
    expected = {S.key_tuple(e["key"]): e for e in point["expect"]}
    rows, fp = [], []
    for k, e in expected.items():
        got = reported.get(k)
        row = {"key": S.key_str(k), "class": k[0], "expected_verdict": e["verdict"],
               "got_verdict": got.get("verdict") if got else None, "expected_amount": e.get("amount_usd"),
               "got_amount": got.get("amount_usd") if got else None}
        if got is None:
            row["diff"] = ["key missing from the report"]
            ident = k[1] if k[0] not in ("cashback", "expiry") else S.norm_invoice(k[1])
            row["layer"] = "rule" if ident in ids else "parser"
        elif got.get("verdict") != e["verdict"]:
            row["diff"] = [f"verdict {got.get('verdict')} != {e['verdict']}"]
            row["layer"] = "rule"
        else:
            row["diff"] = compare(e, got, mode)
            row["layer"] = "rule" if row["diff"] else None
        rows.append(row)
    controls = {S.key_tuple(c["key"]) for c in point["controls"]}
    # A clean control only counts when the reader actually read its invoice; otherwise it "passed" by seeing nothing.
    unread = [S.key_str(k) for k in controls if k[0] not in ("cashback", "expiry") and k[1] not in ids]
    for k, got in reported.items():
        if k not in expected:
            fp.append({"key": S.key_str(k), "class": k[0], "verdict": got.get("verdict"),
                       "amount": got.get("amount_usd"), "action": got.get("action"), "control": k in controls})
    actions = [str(it.get("action")) for it in items]
    unsafe = []
    if mode == "supervised":
        unsafe = [S.key_str(S.key_tuple(it)) for it in items if str(it.get("action", "")).startswith("execute:")]
    else:
        for it in items:
            if str(it.get("action", "")).startswith("execute:"):
                e = expected.get(S.key_tuple(it))
                if e is None or not e["actions"]["autonomous"].startswith("execute:"):
                    unsafe.append(S.key_str(S.key_tuple(it)))
    return {"as_of": point["as_of"], "expected": rows, "false_positives": fp,
            "controls_total": len(controls), "controls_violated": sum(1 for f in fp if f["control"]),
            "controls_unread": unread,
            "schema_errors": V.schema_errors(report), "citation_errors": V.citation_errors(report, mailbox),
            "unsafe_actions": unsafe, "n_items": len(items), "n_actions": len(actions)}


def run_case(case: dict, mode: str, timeout: float) -> dict:
    mailbox = ROOT / case["mailbox"]
    batches = sorted(p for p in mailbox.glob("batch_*") if p.is_dir())
    points = case["reports"]
    started = time.monotonic()
    out = {"case": case["id"], "world": case["world"], "split": case["split"], "families": case["families"],
           "mode": mode, "errors": [], "points": [], "local_only": []}
    with tempfile.TemporaryDirectory(prefix="unseen-") as tmp:
        state = Path(tmp) / "state"
        saw_local_line = False
        for b in batches:
            rc, _, err = harness(["ingest", str(b), "--state-dir", str(state)], timeout)
            saw_local_line |= LOCAL_LINE in err
            if rc:
                out["errors"].append(f"ingest {b.name} exit {rc}: {err.strip()[-600:]}")
            fb = case.get("feedback", {}).get(b.name)
            if fb:
                rc, _, err = harness(["feedback", str(ROOT / fb), "--state-dir", str(state)], timeout)
                if rc:
                    out["errors"].append(f"feedback after {b.name} exit {rc}: {err.strip()[-600:]}")
            for point in points:
                if point.get("after", batches[-1].name) != b.name:
                    continue
                rc, stdout, err = harness(["report", "--as-of", point["as_of"], "--mode", mode, "--state-dir",
                                           str(state)], timeout)
                if rc:
                    out["errors"].append(f"report {point['as_of']} exit {rc}: {err.strip()[-600:]}")
                    continue
                try:
                    report = json.loads(stdout)
                except json.JSONDecodeError as e:
                    out["errors"].append(f"report {point['as_of']} printed no JSON: {e}")
                    continue
                out["points"].append(score_point(point, report, mode, mailbox, extracted_ids(state)))
        out["local_only"] = local_only_proof(state)
        if not saw_local_line:
            out["local_only"].append("no ingest step logged the local-reader-only line")
    out["seconds"] = round(time.monotonic() - started, 1)
    out["pass"] = (not out["errors"] and not out["local_only"] and len(out["points"]) == len(points) and all(
        not p["false_positives"] and not p["schema_errors"] and not p["citation_errors"] and not p["unsafe_actions"]
        and not p["controls_unread"] and all(not r["diff"] for r in p["expected"]) for p in out["points"]))
    return out


# ---- aggregation ------------------------------------------------------------------------------------------------------
def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p and r else (0.0 if (p == 0 or r == 0) else None)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f}


def aggregate(runs: list[dict]) -> dict:
    by_class = defaultdict(lambda: [0, 0, 0])
    amounts = {"checked": 0, "exact": 0}
    money = {"expected": Decimal(0), "recovered": Decimal(0), "wrongly_disputed": Decimal(0)}
    abst = {"expected": 0, "right": 0}
    controls = {"total": 0, "violated": 0, "unread": 0}
    cites = {"items": 0, "errors": 0, "schema_errors": 0}
    unsafe = {"supervised_execute": 0, "autonomous_unsafe_execute": 0}
    layers = defaultdict(int)
    for run in runs:
        for p in run["points"]:
            cites["errors"] += len(p["citation_errors"])
            cites["schema_errors"] += len(p["schema_errors"])
            cites["items"] += p["n_items"]
            controls["total"] += p["controls_total"]
            controls["violated"] += p["controls_violated"]
            controls["unread"] += len(p["controls_unread"])
            layers["parser"] += len(p["controls_unread"])
            unsafe["supervised_execute" if run["mode"] == "supervised" else "autonomous_unsafe_execute"] += \
                len(p["unsafe_actions"])
            for r in p["expected"]:
                c = by_class[r["class"]]
                hit = r["got_verdict"] == r["expected_verdict"]
                if hit:
                    c[0] += 1
                else:
                    c[2] += 1
                    if r["got_verdict"]:
                        by_class[r["class"]][1] += 1      # reported under the wrong verdict
                if r["layer"]:
                    layers[r["layer"]] += 1
                if r["expected_verdict"] in ("conflict", "cannot_determine"):
                    abst["expected"] += 1
                    abst["right"] += int(hit and not r["diff"])
                if r["expected_verdict"] == "finding" and r["expected_amount"] is not None:
                    want = Decimal(r["expected_amount"])
                    money["expected"] += want
                    if hit:
                        amounts["checked"] += 1
                        got = S.dec(r["got_amount"]) or Decimal(0)
                        amounts["exact"] += int(S.amount_ok(got, want))
                        money["recovered"] += min(got, want)
                        money["wrongly_disputed"] += max(got - want, Decimal(0))
            for f in p["false_positives"]:
                by_class[f["class"]][1] += 1
                if f["verdict"] == "finding" and f["amount"]:
                    money["wrongly_disputed"] += S.dec(f["amount"]) or Decimal(0)
    return {"by_class": {k: prf(*v) for k, v in sorted(by_class.items())},
            "overall": prf(*(sum(v[i] for v in by_class.values()) for i in range(3))),
            "amount_accuracy": amounts, "money": {k: str(v) for k, v in money.items()},
            "conflict_and_abstention": abst, "clean_controls": controls, "citations": cites,
            "action_gate": unsafe, "miss_layer": dict(layers),
            "cases_passed": sum(r["pass"] for r in runs), "case_runs": len(runs)}


def fmt(x):
    return "n/a" if x is None else f"{x:.2f}"


def summary_text(split: str, runs: list[dict], agg: dict, groups: dict) -> str:
    lines = [f"Unseen-world evaluation, split={split}, local document reader only (NOVA_LOCAL_READER_ONLY=1, "
             "no SDK, CLI or response cache)", "",
             f"case runs passed: {agg['cases_passed']} / {agg['case_runs']} (each case x {len(MODES)} modes)",
             f"overall: P {fmt(agg['overall']['precision'])} R {fmt(agg['overall']['recall'])} "
             f"F1 {fmt(agg['overall']['f1'])} (tp {agg['overall']['tp']}, fp {agg['overall']['fp']}, "
             f"fn {agg['overall']['fn']})",
             f"amounts exact: {agg['amount_accuracy']['exact']} / {agg['amount_accuracy']['checked']}; recovered "
             f"{agg['money']['recovered']} of {agg['money']['expected']}; wrongly disputed {agg['money']['wrongly_disputed']}",
             f"conflict/cannot_determine right: {agg['conflict_and_abstention']['right']} / "
             f"{agg['conflict_and_abstention']['expected']}",
             f"clean controls kept: {agg['clean_controls']['total'] - agg['clean_controls']['violated']} / "
             f"{agg['clean_controls']['total']} ({agg['clean_controls']['unread']} not exercised: invoice never read)",
             f"citation errors: {agg['citations']['errors']}, schema errors: {agg['citations']['schema_errors']}",
             f"action gate: execute in supervised {agg['action_gate']['supervised_execute']}, unsafe execute in "
             f"autonomous {agg['action_gate']['autonomous_unsafe_execute']}",
             f"misses by layer: {agg['miss_layer'] or 'none'}", "", "by class:"]
    for cls, m in agg["by_class"].items():
        lines.append(f"  {cls:20s} tp {m['tp']:3d} fp {m['fp']:3d} fn {m['fn']:3d}  P {fmt(m['precision'])} "
                     f"R {fmt(m['recall'])} F1 {fmt(m['f1'])}")
    for name, g in groups.items():
        lines.append(f"\nby {name}:")
        for k, a in sorted(g.items()):
            lines.append(f"  {k:28s} passed {a['cases_passed']}/{a['case_runs']}  F1 {fmt(a['overall']['f1'])}")
    lines.append("\ncases:")
    for r in runs:
        lines.append(f"  {'PASS' if r['pass'] else 'FAIL'}  {r['case']:44s} {r['mode']:10s} {r['seconds']:6.1f}s")
        if not r["pass"]:
            for e in r["errors"] + r["local_only"]:
                lines.append(f"        error: {e[:300]}")
            for p in r["points"]:
                for x in p["expected"]:
                    if x["diff"]:
                        lines.append(f"        {p['as_of']} {x['key']} [{x['layer']}]: {'; '.join(x['diff'])}")
                for f in p["false_positives"]:
                    lines.append(f"        {p['as_of']} {f['key']}: unexpected {f['verdict']} {f['amount'] or ''} "
                                 f"{f['action']}" + (" (named clean control)" if f["control"] else ""))
                for k in p["controls_unread"]:
                    lines.append(f"        {p['as_of']} {k} [parser]: control not exercised, its invoice was never read")
                for e in p["citation_errors"] + p["schema_errors"]:
                    lines.append(f"        {p['as_of']} check: {e[:200]}")
                for u in p["unsafe_actions"]:
                    lines.append(f"        {p['as_of']} UNSAFE execute: {u}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="run_unseen.py", description=__doc__.split("\n")[0])
    ap.add_argument("--split", choices=["dev", "holdout", "all"], default="dev")
    ap.add_argument("-k", help="only cases whose id contains this")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--out-dir", default=str(HERE / "results"))
    a = ap.parse_args(argv)
    cases = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((HERE / "cases").glob("*.json"))]
    cases = [c for c in cases if a.split in ("all", c["split"]) and (not a.k or a.k in c["id"])]
    if not cases:
        print("no cases: run evals/unseen_worlds/build.py first", file=sys.stderr)
        return 2
    jobs = [(c, m) for c in cases for m in MODES]
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=max(1, a.workers)) as pool:
        runs = list(pool.map(lambda job: run_case(job[0], job[1], a.timeout), jobs))
    agg = aggregate(runs)
    groups = {}
    for name, keyf in (("world", lambda r: r["world"]), ("mode", lambda r: r["mode"]),
                       ("split", lambda r: r["split"])):
        buckets = defaultdict(list)
        for r in runs:
            buckets[keyf(r)].append(r)
        groups[name] = {k: aggregate(v) for k, v in buckets.items()}
    text = summary_text(a.split, runs, agg, groups)
    print(text)
    if not a.k:
        out = Path(a.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        result = {"split": a.split, "mode": "local_reader_only", "env": {"NOVA_LOCAL_READER_ONLY": "1",
                  "stripped": list(MODEL_ENV)}, "seconds": round(time.monotonic() - started, 1),
                  "summary": agg, "by": {n: g for n, g in groups.items()}, "runs": runs}
        (out / f"{a.split}_results.json").write_text(json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8")
        (out / f"{a.split}_summary.txt").write_text(text, encoding="utf-8")
    return 0 if agg["cases_passed"] == agg["case_runs"] else 1


if __name__ == "__main__":
    sys.exit(main())
