"""OCR for scanned PDFs (no text layer) with the local RapidOCR models shipped in its wheel.

RapidOCR returns text boxes with positions and drops most spaces inside a box. `group_lines` rebuilds reading-order
lines from box positions; the raw boxes and scores are kept separately so later stages can judge field confidence.
"""
from __future__ import annotations

import json
import statistics

from .config import OCR_DPI

_ENGINE = None


def _box_geometry(box) -> tuple[float, float, float, float]:
    xs = [float(p[0]) for p in box]
    ys = [float(p[1]) for p in box]
    return min(xs), (min(ys) + max(ys)) / 2, max(ys) - min(ys), max(xs)


def group_lines(results) -> list[dict]:
    """[(box, text, score), ...] -> [{'text', 'score', 'boxes'}] top to bottom, each line left to right.

    Two boxes share a line when their vertical centres differ by less than half the median box height.
    """
    items = []
    for box, text, score in results or []:
        text = str(text).strip()
        if not text:
            continue
        x0, cy, h, x1 = _box_geometry(box)
        items.append({"x0": x0, "x1": x1, "cy": cy, "h": max(h, 1.0), "text": text, "score": float(score)})
    if not items:
        return []
    tol = statistics.median(i["h"] for i in items) / 2
    items.sort(key=lambda i: (i["cy"], i["x0"]))
    lines: list[list[dict]] = []
    for it in items:
        if lines and abs(statistics.fmean(i["cy"] for i in lines[-1]) - it["cy"]) < tol:
            lines[-1].append(it)
        else:
            lines.append([it])
    out = []
    for ln in lines:
        ln.sort(key=lambda i: i["x0"])
        out.append({"text": " ".join(i["text"] for i in ln),
                    "score": round(min(i["score"] for i in ln), 4),
                    "boxes": [[round(i["x0"], 1), round(i["cy"], 1), round(i["x1"], 1), i["text"], round(i["score"], 4)]
                              for i in ln]})
    return out


def _engine():
    global _ENGINE
    if _ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        _ENGINE = RapidOCR()
    return _ENGINE


def ocr_pdf(data: bytes) -> list[dict]:
    """-> one {'text', 'ocr_json'} per page of a scanned PDF."""
    import pymupdf
    pages = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            png = page.get_pixmap(dpi=OCR_DPI).tobytes("png")
            result, _ = _engine()(png)
            lines = group_lines(result)
            pages.append({"text": "\n".join(ln["text"] for ln in lines),
                          "ocr_json": json.dumps({"dpi": OCR_DPI, "lines": lines})})
    return pages
