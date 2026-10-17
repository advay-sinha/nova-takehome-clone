"""Turn one batch folder into document occurrences: emails and attachments with page text and receipt metadata.

Page text comes from the vendored grader text layer, so quotes cut from it resolve the way the grader checks them.
Scans fall back to OCR. A file that cannot be read is still recorded, with `read_error`, rather than stopping ingest.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import timezone
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from pathlib import Path

from . import textlayer
from .ocr import ocr_pdf

READABLE = {"pdf", "xlsx"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_iso(date_header) -> str | None:
    """Email Date header -> 'YYYY-MM-DDTHH:MM:SSZ' in UTC. A header without a zone is taken as UTC."""
    if not date_header:
        return None
    try:
        dt = parsedate_to_datetime(str(date_header))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _addrs(value) -> str:
    return json.dumps([addr.lower() for _, addr in getaddresses([str(value)]) if addr]) if value else "[]"


def _attachment_pages(name: str, data: bytes) -> tuple[str, bool, list[dict], str | None]:
    """-> (kind, is_scan, pages, read_error)."""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in READABLE:
        return "other", False, [], f"unsupported attachment type .{ext}"
    try:
        if ext == "pdf" and textlayer.pdf_is_image_only(data):
            return "pdf", True, [{"page": i + 1, "text": p["text"], "method": "ocr", "ocr_json": p["ocr_json"]}
                                 for i, p in enumerate(ocr_pdf(data))], None
        texts = textlayer.pages_of(data, ext)
        return ext, False, [{"page": i + 1, "text": t, "method": "textlayer"} for i, t in enumerate(texts)], None
    except Exception as e:  # noqa: BLE001 - one bad file must not stop the batch
        return ext, False, [], f"{type(e).__name__}: {e}"


def read_batch(batch_dir: str | Path) -> list[dict]:
    """-> [{'row': documents row, 'pages': [...], 'data': bytes}] for every .eml in the folder and its attachments."""
    batch_dir = Path(batch_dir)
    batch = batch_dir.name
    out = []
    for eml in sorted(batch_dir.glob("*.eml")):
        data = eml.read_bytes()
        doc = f"{batch}/{eml.name}"
        try:
            msg = textlayer.parse_eml(data)
            name, addr = parseaddr(str(msg["From"] or ""))
            headers = {k: str(msg[k]) for k in ("Message-ID", "In-Reply-To", "References") if msg[k]}
            base = {"batch": batch, "email_doc": doc, "received_at": utc_iso(msg["Date"]),
                    "sender_name": name, "sender_addr": addr.lower(), "to_addrs": _addrs(msg["To"]),
                    "cc_addrs": _addrs(msg["Cc"]), "subject": str(msg["Subject"] or ""),
                    "headers_json": json.dumps(headers, sort_keys=True)}
            try:
                pages, err = [{"page": 1, "text": textlayer.pages_of(data, "eml")[0], "method": "textlayer"}], None
            except Exception as e:  # noqa: BLE001
                pages, err = [], f"{type(e).__name__}: {e}"
            out.append({"row": {**base, "doc": doc, "kind": "eml", "name": eml.name, "sha256": sha256(data),
                                "is_scan": 0, "page_count": len(pages), "read_error": err},
                        "pages": pages, "data": data})
            for att_name, att_data in textlayer.attachments(data):
                kind, scan, att_pages, att_err = _attachment_pages(att_name, att_data)
                out.append({"row": {**base, "doc": f"{doc}#{att_name}", "kind": kind, "name": att_name,
                                    "sha256": sha256(att_data), "is_scan": int(scan), "page_count": len(att_pages),
                                    "read_error": att_err},
                            "pages": att_pages, "data": att_data})
        except Exception as e:  # noqa: BLE001 - unparseable email: keep a trace of it, carry on
            print(f"ingest: cannot read {doc}: {type(e).__name__}: {e}", file=sys.stderr)
            out.append({"row": {"batch": batch, "email_doc": doc, "doc": doc, "kind": "eml", "name": eml.name,
                                "sha256": sha256(data), "received_at": None, "page_count": 0, "is_scan": 0,
                                "read_error": f"{type(e).__name__}: {e}"},
                        "pages": [], "data": data})
    return out
