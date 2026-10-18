"""Your harness. The grader calls exactly these three commands, in a fresh process each time:

    python harness.py ingest <batch_dir> --state-dir <dir>
    python harness.py report --as-of YYYY-MM-DD [--mode supervised|autonomous] [--state-dir <dir>] > report.json
    python harness.py feedback <feedback.json> --state-dir <dir>

- ingest: read every .eml in <batch_dir> (attachments inside) and store what you learn under --state-dir. The process
  is restarted between batches, so everything you need later must be on disk.
- report: print one report.json (grader/schema/report.schema.json) to stdout. Only documents received on or before
  --as-of count. --mode defaults to supervised.
- feedback: take in a person's decisions on what you escalated (feedback.json) and let them change later reports.

The environment gives ANTHROPIC_API_KEY and ANTHROPIC_BASE_URL. Keep the argument names as they are: grader/validate.py
checks them. Replace the NotImplementedError bodies with your code.

Optional, before the command: --local-reader-only sets NOVA_LOCAL_READER_ONLY=1 and drops ANTHROPIC_API_KEY,
ANTHROPIC_BASE_URL and NOVA_LOCAL_LLM inside this process, so extraction uses only the local document reader (no SDK,
no Claude CLI, no response cache). The grader passes only PATH and ANTHROPIC_* to the harness, so the flag travels in
its --harness command string instead of the environment.
"""
from __future__ import annotations

import argparse
import os
import sys

from nova.app import feedback, ingest, report
from nova.llm import LLMError

DEFAULT_STATE = ".state"
MODEL_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "NOVA_LOCAL_LLM")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="harness.py", description="Freight invoice audit harness")
    ap.add_argument("--local-reader-only", action="store_true",
                    help="extract with the local document reader only (no model provider or response cache)")
    sub =ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest", help="read one batch folder into the state dir")
    p.add_argument("batch_dir")
    p.add_argument("--state-dir", default=DEFAULT_STATE)
    p = sub.add_parser("report", help="print report.json for a date")
    p.add_argument("--as-of", required=True, help="YYYY-MM-DD; only documents received by then count")
    p.add_argument("--mode", choices=["supervised", "autonomous"], default="supervised")
    p.add_argument("--state-dir", default=DEFAULT_STATE)
    p = sub.add_parser("feedback", help="take in a person's decisions (feedback.json)")
    p.add_argument("feedback_file")
    p.add_argument("--state-dir", default=DEFAULT_STATE)
    a = ap.parse_args(argv)
    if a.local_reader_only:
        for k in MODEL_ENV:
            os.environ.pop(k, None)
        os.environ["NOVA_LOCAL_READER_ONLY"] = "1"
    try:
        if a.cmd == "ingest":
            ingest(a.batch_dir, a.state_dir)
        elif a.cmd == "report":
            import json
            json.dump(report(a.as_of, a.mode, a.state_dir), sys.stdout, indent=1)
            sys.stdout.write("\n")
        else:
            feedback(a.feedback_file, a.state_dir)
    except NotImplementedError as e:
        print(f"harness.py {a.cmd}: {e}", file=sys.stderr)
        return 3
    except (ValueError, OSError, LLMError) as e:
        print(f"harness.py {a.cmd}: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
