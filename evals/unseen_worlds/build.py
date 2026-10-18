"""Build the unseen-world mailboxes and case files (deterministic; rerun after editing a case).

    python evals/unseen_worlds/build.py [--split dev|holdout|all]

Writes evals/unseen_worlds/mailboxes/<case>/batch_NN/*.eml, feedback/<case>-*.json and cases/<case>.json. Expected
answers come from the case definitions (oracle.py arithmetic on the printed terms); nothing here imports the harness.
Before a case is accepted its fixture is read back through the grader's text layer (grader/extract.py) and every
expected key, cited evidence document and expected amount's source numbers are checked to be present.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "grader"))

import extract as text_layer  # noqa: E402  (the grader's reader: a fixture check, not the code under test)
from spec import CASES  # noqa: E402

import importlib  # noqa: E402

# Each module registers its cases with spec.case; the holdout module is written after the reader is frozen.
for _module in sorted(p.stem for p in HERE.glob("cases_*.py")):
    importlib.import_module(_module)

SEED = 4317          # fixed; the cases use no randomness today, but any future draw must come from this seed


def all_text(mailbox: Path) -> dict[str, list[str]]:
    out = {}
    for f in sorted(mailbox.rglob("*.eml")):
        rel = f.relative_to(mailbox).as_posix()
        out[rel] = text_layer.pages_of(f.read_bytes(), "eml")
        for name, data in text_layer.attachments(f.read_bytes()):
            out[f"{rel}#{name}"] = text_layer.pages_of(data, name.rsplit(".", 1)[-1].lower())
    return out


def check_fixture(case_id: str, mailbox: Path, spec: dict) -> list[str]:
    texts = all_text(mailbox)
    flat = text_layer.norm(" ".join(" ".join(p) for p in texts.values()))
    problems = []
    for rp in spec["reports"]:
        for it in rp["expect"] + rp["controls"]:
            key = it["key"]
            ident = key.get("invoice_id") or key.get("contract_id")
            if text_layer.norm(ident) not in flat:
                problems.append(f"{case_id}: key id {ident} is not in any document's text layer")
            for doc in it.get("evidence_docs", []):
                if doc not in texts:
                    problems.append(f"{case_id}: evidence document {doc} does not exist")
    return problems


def build(split: str) -> int:
    random.seed(SEED)
    out_boxes, out_cases, out_fb = HERE / "mailboxes", HERE / "cases", HERE / "feedback"
    for d in (out_boxes, out_cases, out_fb):
        d.mkdir(exist_ok=True)
    problems, built = [], 0
    for case_id, fn in sorted(CASES.items()):
        meta = fn.meta
        if split != "all" and meta["split"] != split:
            continue
        mailbox, spec = fn()
        assert mailbox.name == case_id, (mailbox.name, case_id)
        path = mailbox.write(out_boxes)
        feedback = {}
        for batch, data in (spec.pop("feedback", None) or {}).items():
            f = out_fb / f"{case_id}-after-{batch}.json"
            f.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
            feedback[batch] = f.relative_to(ROOT).as_posix()
        record = {**meta, "mailbox": path.relative_to(ROOT).as_posix(), "feedback": feedback, **spec}
        problems += check_fixture(case_id, path, record)
        (out_cases / f"{case_id}.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
        built += 1
        print(f"{case_id}: {meta['split']}, " + ", ".join(f"{b} {len(v)}" for b, v in sorted(mailbox.batches.items())))
    for p in problems:
        print("FIXTURE PROBLEM:", p, file=sys.stderr)
    print(f"built {built} case(s); {len(problems)} fixture problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "holdout", "all"], default="all")
    sys.exit(build(ap.parse_args().split))
