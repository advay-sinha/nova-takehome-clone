"""Original synthetic mailbox builder for offline tests. Every name, number and date here is invented for the tests."""
from __future__ import annotations

import io
from email.message import EmailMessage
from pathlib import Path

CARRIER = "Pellwick Air Cargo"
CUSTOMER = "Ostrava Bio"
INVOICE_LINE = "1 PW55120034 2041-03-02 Air freight KLX1-ORB2 118 kg 4.20 495.60"


def make_pdf(pages: list[list[str]]) -> bytes:
    import pymupdf
    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page()
        for i, line in enumerate(lines):
            page.insert_text((56, 72 + 16 * i), line, fontsize=10)
    return doc.tobytes()


def make_scan_pdf(lines: list[str]) -> bytes:
    """A PDF whose only content is an image of the text: no text layer, like a scanned invoice."""
    import pymupdf
    src = pymupdf.open(stream=make_pdf([lines]), filetype="pdf")
    png = src[0].get_pixmap(dpi=200).tobytes("png")
    out = pymupdf.open()
    page = out.new_page()
    page.insert_image(page.rect, stream=png)
    return out.tobytes()


def make_xlsx(rows: list[list]) -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Register"
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def write_eml(path: Path, sender: str, to: str, date: str, subject: str, body: str,
              attachments: list[tuple[str, bytes, str]] = ()) -> None:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Date"] = date
    msg["Subject"] = subject
    msg["Message-ID"] = f"<{path.stem}.{path.parent.name}@synthetic.example>"
    msg["X-GCA-Canary"] = "synthetic-canary"
    msg.set_content(body)
    for name, data, subtype in attachments:
        maintype = "application"
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(msg))


INVOICE_PDF = make_pdf([[f"{CARRIER} Invoice PW-OB-2041-0107", "Invoice date 2041-03-05", INVOICE_LINE,
                         "Total USD 495.60"]])


def build_mailbox(root: Path, extra: bool = False) -> Path:
    """root/batch_01, root/batch_02 with emails, PDFs, an XLSX, a resend of identical bytes and a scan. `extra` adds
    a 5-page agreement and a 70-row tracking export to batch_01."""
    b1, b2 = root / "batch_01", root / "batch_02"
    contract = make_pdf([["Master Services Agreement PW-OB-EXP-07", "2.2 Initial term ends on 2042-01-31."],
                         ["Schedule 1", "Mira Kostova, Billing Lead, PW: waivers <mira.kostova@pellwick.example>"]])
    write_eml(b1 / "0001.eml", "Lena Sorell <lena.sorell@ostravabio.example>", "ap@ostravabio.example",
              "Mon, 07 Jan 2041 09:15:00 +0000", "Executed agreement PW-OB-EXP-07", "Signed copy attached.",
              [("MSA-PW-OB-EXP-07.pdf", contract, "pdf")])
    # 03:10 on 6 March in India is 21:40 on 5 March UTC: receipt must use UTC.
    write_eml(b1 / "0002.eml", f"{CARRIER} Billing <billing@pellwick.example>", "ap@ostravabio.example",
              "Wed, 06 Mar 2041 03:10:00 +0530", "Invoice PW-OB-2041-0107", "Please find the invoice attached.",
              [("PW-OB-2041-0107.pdf", INVOICE_PDF, "pdf")])
    register = make_xlsx([["Invoice", "Due", "Amount", "Status"], ["PW-OB-2041-0107", "2041-04-04", 495.6, "open"]])
    write_eml(b1 / "0003.eml", "Tomas Reiner <tomas.reiner@ostravabio.example>", "ap@ostravabio.example",
              "Fri, 29 Mar 2041 17:00:00 +0000", "AP register 2041-03-29", "Register attached.",
              [("ap-register-2041-03-29.xlsx", register, "vnd.openxmlformats-officedocument.spreadsheetml.sheet")])
    # Same invoice bytes sent again: a second occurrence that must not be merged away.
    write_eml(b1 / "0004.eml", f"{CARRIER} Billing <billing@pellwick.example>", "ap@ostravabio.example",
              "Mon, 01 Apr 2041 08:00:00 +0000", "Invoice PW-OB-2041-0107", "Please process payment.",
              [("PW-OB-2041-0107.pdf", INVOICE_PDF, "pdf")])
    if extra:
        long_pdf = make_pdf([[f"Agreement PW-OB-EXP-08 page {i}", f"{i}.1 Clause text for page {i}."] for i in range(1, 6)])
        write_eml(b1 / "0005.eml", "Lena Sorell <lena.sorell@ostravabio.example>", "ap@ostravabio.example",
                  "Tue, 02 Apr 2041 09:00:00 +0000", "Executed agreement PW-OB-EXP-08", "Attached.",
                  [("MSA-PW-OB-EXP-08.pdf", long_pdf, "pdf")])
        rows = [["AWB", "Event", "Date", "Station", "Reason code"]]
        rows += [[f"PW{55120000 + i}", "PICKED_UP", f"2041-03-{1 + i % 28:02d}", "KLX1", "-"] for i in range(70)]
        write_eml(b1 / "0006.eml", "Tomas Reiner <tomas.reiner@ostravabio.example>", "ap@ostravabio.example",
                  "Wed, 03 Apr 2041 09:00:00 +0000", "Tracking export 2041-03", "Export attached.",
                  [("tracking-2041-03.xlsx", make_xlsx(rows), "vnd.openxmlformats-officedocument.spreadsheetml.sheet")])
    scan = make_scan_pdf([f"{CARRIER} Invoice PW-OB-2041-0219", "Invoice date 2041-06-10", "Total USD 812.40"])
    write_eml(b2 / "0001.eml", f"{CARRIER} Billing <billing@pellwick.example>", "ap@ostravabio.example",
              "Tue, 11 Jun 2041 10:00:00 +0000", "Invoice PW-OB-2041-0219", "Scanned copy attached.",
              [("PW-OB-2041-0219.pdf", scan, "pdf")])
    return root
