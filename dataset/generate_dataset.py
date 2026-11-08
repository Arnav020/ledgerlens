"""
LedgerLens synthetic dataset generator.

Creates two loan / KYC application packets of related financial documents:

  - genuine/      : an internally consistent packet (no planted anomalies)
  - manipulated/  : the same packet with a documented set of planted anomalies
                    spanning cross-document, structural, born-digital-PDF and
                    visual-forensic classes.

Everything here is fully SYNTHETIC. No real person, account, PAN or photograph
is used. Names, numbers and values are invented for demonstration only.

The generator also writes dataset/ground_truth.json and dataset/GROUND_TRUTH.md
listing every planted anomaly, so evaluation is honest and reproducible.

Run:  python dataset/generate_dataset.py
Deterministic: fixed seed, no network, no external services.
"""

from __future__ import annotations

import io
import json
import os
import random
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

SEED = 20261109
random.seed(SEED)

HERE = Path(__file__).resolve().parent
GENUINE = HERE / "genuine"
MANIP = HERE / "manipulated"
RENDER_DPI = 150

# ---------------------------------------------------------------------------
# Font handling (fall back to a bundled PIL default if a TTF is unavailable)
# ---------------------------------------------------------------------------

def _find_font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# The two applicants.  The manipulated applicant is a deliberately altered copy.
# ---------------------------------------------------------------------------

def base_profile():
    return {
        "name": "Rohan Mehta",
        "dob": "14-03-1992",
        "address": "48 Camac Street, Kolkata, West Bengal 700017",
        "pan": "AKMPM4821Q",
        "id_issue_date": "22-07-2015",
        "employer": "Nimbus Analytics Pvt Ltd",
        "monthly_net_income": 86000,          # true monthly net salary
        "account_number": "50100 2234 7781",
        "statement_period": "01-08-2026 to 31-08-2026",
        "opening_balance": 142300,
        "salary_credit": 86000,
        "application_date": "05-09-2026",
        "loan_amount": 1500000,
    }


# ---------------------------------------------------------------------------
# PDF documents (born-digital), drawn with a simple label/value layout so that
# label-anchored OCR extraction is reliable.
# ---------------------------------------------------------------------------

def _pdf_canvas(path: Path, title: str, producer="LedgerLens DemoForms 1.0"):
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(title)
    c.setAuthor("LedgerLens Synthetic Data")
    c.setProducer(producer)
    c.setCreator(producer)
    return c


def _field(c, x_mm, y_mm, label, value, size=12, bold_value=True):
    c.setFont("Helvetica", size)
    c.drawString(x_mm * mm, y_mm * mm, label)
    c.setFont("Helvetica-Bold" if bold_value else "Helvetica", size)
    c.drawString((x_mm + 55) * mm, y_mm * mm, str(value))


def make_application_form(path: Path, p: dict):
    c = _pdf_canvas(path, "Personal Loan Application Form")
    W, H = A4
    c.setFont("Helvetica-Bold", 17)
    c.drawString(20 * mm, 280 * mm, "MERIDIAN BANK  -  Personal Loan Application")
    c.setLineWidth(0.6)
    c.line(20 * mm, 276 * mm, 190 * mm, 276 * mm)
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, 271 * mm, "Section A: Applicant Details")
    y = 262
    rows = [
        ("Full Name:", p["name"]),
        ("Date of Birth:", p["dob"]),
        ("PAN Number:", p["pan"]),
        ("Residential Address:", p["address"]),
        ("Employer Name:", p["employer"]),
        ("Declared Monthly Income:", "INR " + f"{p['monthly_net_income']:,}"),
        ("Bank Account Number:", p["account_number"]),
        ("Loan Amount Requested:", "INR " + f"{p['loan_amount']:,}"),
        ("Application Date:", p["application_date"]),
    ]
    for label, value in rows:
        _field(c, 20, y, label, value, size=12)
        y -= 11
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, (y - 6) * mm, "Declaration: I confirm the information above is true and complete.")
    c.setFont("Helvetica-Oblique", 13)
    c.drawString(20 * mm, (y - 22) * mm, "Signature:  R. Mehta")
    c.showPage()
    c.save()


def make_address_proof(path: Path, p: dict):
    c = _pdf_canvas(path, "Electricity Bill - Address Proof")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, 280 * mm, "CESC Limited  -  Electricity Bill")
    c.line(20 * mm, 276 * mm, 190 * mm, 276 * mm)
    rows = [
        ("Consumer Name:", p["name"]),
        ("Supply Address:", p["address"]),
        ("Bill Number:", "CESC-2026-884213"),
        ("Billing Month:", "August 2026"),
        ("Bill Date:", "02-09-2026"),
        ("Amount Payable:", "INR 2,140"),
    ]
    y = 262
    for label, value in rows:
        _field(c, 20, y, label, value, size=12)
        y -= 12
    c.showPage()
    c.save()


def make_salary_slip(path: Path, p: dict):
    c = _pdf_canvas(path, "Salary Slip")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, 280 * mm, p["employer"])
    c.setFont("Helvetica", 11)
    c.drawString(20 * mm, 274 * mm, "Payslip for the month of August 2026")
    c.line(20 * mm, 270 * mm, 190 * mm, 270 * mm)
    gross = p["monthly_net_income"] + 18000
    rows = [
        ("Employee Name:", p["name"]),
        ("Employee ID:", "NIM-2041"),
        ("Designation:", "Senior Data Analyst"),
        ("PAN:", p["pan"]),
        ("Gross Earnings:", "INR " + f"{gross:,}"),
        ("Total Deductions:", "INR 18,000"),
        ("Net Pay:", "INR " + f"{p['monthly_net_income']:,}"),
        ("Pay Date:", "31-08-2026"),
    ]
    y = 258
    for label, value in rows:
        _field(c, 20, y, label, value, size=12)
        y -= 12
    c.showPage()
    c.save()


def make_bank_statement(path: Path, p: dict, break_balance: bool = False):
    """
    Bank statement with a running-balance ledger.
    If break_balance is True, the printed CLOSING balance is altered so the
    arithmetic no longer reconciles (within-document structural anomaly).
    """
    c = _pdf_canvas(path, "Bank Statement")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, 285 * mm, "MERIDIAN BANK  -  Account Statement")
    c.line(20 * mm, 281 * mm, 190 * mm, 281 * mm)
    _field(c, 20, 274, "Account Holder:", p["name"], size=11)
    _field(c, 20, 268, "Account Number:", p["account_number"], size=11)
    _field(c, 20, 262, "Statement Period:", p["statement_period"], size=11)

    # ledger
    txns = [
        ("03-08-2026", "UPI/Grocery/Spencer", -4200),
        ("09-08-2026", "ATM Withdrawal", -10000),
        ("17-08-2026", "UPI/Electricity/CESC", -2140),
        ("24-08-2026", "Rent Transfer", -32000),
        ("31-08-2026", "Salary Credit " + p["employer"], p["salary_credit"]),
    ]
    bal = p["opening_balance"]
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, 252 * mm, "Date")
    c.drawString(55 * mm, 252 * mm, "Description")
    c.drawString(140 * mm, 252 * mm, "Amount")
    c.drawString(170 * mm, 252 * mm, "Balance")
    c.setFont("Helvetica", 11)
    y = 245
    c.drawString(20 * mm, y * mm, "01-08-2026")
    c.drawString(55 * mm, y * mm, "Opening Balance")
    c.drawString(170 * mm, y * mm, f"{bal:,}")
    y -= 8
    for date, desc, amt in txns:
        bal += amt
        c.drawString(20 * mm, y * mm, date)
        c.drawString(55 * mm, y * mm, desc)
        c.drawString(140 * mm, y * mm, ("+" if amt >= 0 else "-") + f"{abs(amt):,}")
        c.drawString(170 * mm, y * mm, f"{bal:,}")
        y -= 8
    true_closing = bal
    printed_closing = true_closing + 95000 if break_balance else true_closing
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, (y - 4) * mm, "Closing Balance:")
    c.drawString(170 * mm, (y - 4) * mm, f"{printed_closing:,}")
    c.showPage()
    c.save()
    return true_closing, printed_closing


def tamper_pdf_incremental(path: Path):
    """
    Simulate a born-digital tamper: open the finished PDF and append an
    incremental update that overlays text. This leaves a second xref section
    and a second %%EOF in the file, which the PDF-forensics check detects.
    Also rewrites the producer so creator and producer disagree.
    """
    doc = fitz.open(str(path))
    page = doc[0]
    # overlay a faint 'verified' mark via incremental save -> adds a revision
    page.insert_text((400, 60), "e-verified", fontsize=8, color=(0.6, 0.6, 0.6))
    doc.set_metadata({"producer": "iText 7.2.5", "creator": "LedgerLens DemoForms 1.0"})
    doc.save(str(path), incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    doc.close()


# ---------------------------------------------------------------------------
# ID card (raster image) with a synthetic avatar (no real face).
# ---------------------------------------------------------------------------

def _avatar(size=(130, 160), seed=1):
    """A synthetic ID photo with UNIQUE fine texture (random noise), so the image
    has no accidental self-similarity. A real copy-move splice then stands out."""
    import numpy as np
    rng = np.random.default_rng(seed)
    noise = rng.integers(90, 190, size=(size[1], size[0], 3), dtype="uint8")
    img = Image.fromarray(noise, "RGB")
    d = ImageDraw.Draw(img)
    # head + shoulders silhouette over the textured background
    d.ellipse([size[0] // 2 - 30, 25, size[0] // 2 + 30, 85], fill=(150, 120, 100))
    d.rectangle([size[0] // 2 - 42, 95, size[0] // 2 + 42, size[1]], fill=(90, 110, 150))
    return img


def make_id_card(path: Path, p: dict, copy_move: bool = False, mark_edited: bool = False):
    W, Hh = 640, 400
    img = Image.new("RGB", (W, Hh), (247, 245, 238))
    d = ImageDraw.Draw(img)
    f_title = _find_font(28, bold=True)
    f_label = _find_font(20)
    f_val = _find_font(22, bold=True)
    d.rectangle([0, 0, W, 60], fill=(16, 54, 94))
    d.text((20, 15), "INCOME TAX DEPARTMENT  -  PAN", font=f_title, fill=(255, 255, 255))
    # photo
    av = _avatar(seed=7)
    img.paste(av, (30, 90))
    d.rectangle([30, 90, 160, 250], outline=(80, 80, 80), width=2)
    # fields
    rows = [
        ("Name", p["name"]),
        ("Date of Birth", p["dob"]),
        ("PAN", p["pan"]),
        ("Date of Issue", p["id_issue_date"]),
    ]
    y = 95
    for label, value in rows:
        d.text((200, y), label, font=f_label, fill=(70, 70, 70))
        d.text((200, y + 24), str(value), font=f_val, fill=(10, 10, 10))
        y += 62
    d.text((200, y + 6), "Signature:  R. Mehta", font=_find_font(20), fill=(20, 20, 60))

    if copy_move:
        # Splice a region with a DIFFERENT compression history (double JPEG),
        # the textbook manipulation that Error Level Analysis localizes. The
        # genuine image has a single uniform compression history, so ELA stays
        # flat there and lights up only on this spliced region.
        box = (40, 100, 120, 180)
        patch = img.crop(box)
        buf = io.BytesIO()
        patch.save(buf, format="JPEG", quality=25)
        buf.seek(0)
        patch_recompressed = Image.open(buf).convert("RGB")
        img.paste(patch_recompressed, (box[0], box[1]))

    exif_bytes = None
    if mark_edited:
        import piexif
        zeroth = {piexif.ImageIFD.Software: b"Adobe Photoshop 25.1 (Windows)"}
        exif_bytes = piexif.dump({"0th": zeroth, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None})

    if exif_bytes:
        img.save(str(path), format="JPEG", quality=92, exif=exif_bytes)
    else:
        img.save(str(path), format="JPEG", quality=92)


# ---------------------------------------------------------------------------
# Render helper: rasterize a PDF first page to PNG for OCR / UI.
# ---------------------------------------------------------------------------

def render_pdf_to_png(pdf_path: Path, png_path: Path, dpi=RENDER_DPI):
    doc = fitz.open(str(pdf_path))
    page = doc[0]
    pix = page.get_pixmap(dpi=dpi)
    pix.save(str(png_path))
    doc.close()


# ---------------------------------------------------------------------------
# Build a full packet.
# ---------------------------------------------------------------------------

def build_packet(outdir: Path, p: dict, manipulated: bool, anomalies: list):
    outdir.mkdir(parents=True, exist_ok=True)
    files = {}

    # application form
    app_pdf = outdir / "01_loan_application.pdf"
    make_application_form(app_pdf, p)
    files["application"] = app_pdf

    # government ID (image)
    id_img = outdir / "02_pan_id.jpg"
    make_id_card(id_img, p,
                 copy_move=manipulated and "A6_photo_splice" in anomalies,
                 mark_edited=manipulated and "A6_photo_splice" in anomalies)
    files["id"] = id_img

    # address proof
    addr_pdf = outdir / "03_address_proof.pdf"
    make_address_proof(addr_pdf, p)
    files["address_proof"] = addr_pdf

    # salary slip
    sal_pdf = outdir / "04_salary_slip.pdf"
    make_salary_slip(sal_pdf, p)
    files["salary_slip"] = sal_pdf

    # bank statement (optionally with broken arithmetic + born-digital tamper)
    stmt_pdf = outdir / "05_bank_statement.pdf"
    true_close, printed_close = make_bank_statement(
        stmt_pdf, p, break_balance=manipulated and "A3_balance_arithmetic" in anomalies)
    if manipulated and "A5_pdf_incremental" in anomalies:
        tamper_pdf_incremental(stmt_pdf)
    files["bank_statement"] = stmt_pdf

    # rasterize PDFs for OCR / UI
    renders = {}
    for key, fp in files.items():
        if fp.suffix.lower() == ".pdf":
            png = outdir / (fp.stem + ".png")
            render_pdf_to_png(fp, png)
            renders[key] = png
        else:
            renders[key] = fp
    return files, renders, (true_close, printed_close)


def main():
    for d in (GENUINE, MANIP):
        d.mkdir(parents=True, exist_ok=True)

    # genuine packet
    g = base_profile()
    build_packet(GENUINE, g, manipulated=False, anomalies=[])

    # manipulated packet: start from the genuine profile, then plant anomalies
    m = base_profile()
    planted = []

    # A1 cross-document: DOB on the ID differs from the application form
    m_id = dict(m); m_id["dob"] = "14-03-1990"
    planted.append({
        "id": "A1_dob_mismatch", "class": "cross_document",
        "detail": "DOB on PAN ID (14-03-1990) conflicts with application form (14-03-1992).",
        "documents": ["id", "application"], "confidence_expectation": "high"})

    # A2 cross-document / financial: declared income inflated vs salary slip & bank credit
    m["monthly_net_income_declared"] = 140000  # application overrides
    planted.append({
        "id": "A2_income_inflation", "class": "cross_document",
        "detail": "Declared monthly income on application (INR 140,000) exceeds salary-slip net pay and bank salary credit (INR 86,000).",
        "documents": ["application", "salary_slip", "bank_statement"], "confidence_expectation": "high"})

    # A3 structural: bank statement closing balance does not reconcile
    planted.append({
        "id": "A3_balance_arithmetic", "class": "structural",
        "detail": "Printed closing balance does not equal opening balance plus the sum of ledger transactions.",
        "documents": ["bank_statement"], "confidence_expectation": "high"})

    # A4 cross-document: address proof address differs from application
    m_addr = dict(m); m_addr["address"] = "12 Park Street, Kolkata, West Bengal 700016"
    planted.append({
        "id": "A4_address_mismatch", "class": "cross_document",
        "detail": "Address on utility bill (12 Park Street) conflicts with application address (48 Camac Street).",
        "documents": ["address_proof", "application"], "confidence_expectation": "high"})

    # A5 born-digital pdf: incremental-update tamper on the bank statement
    planted.append({
        "id": "A5_pdf_incremental", "class": "pdf_forensic",
        "detail": "Bank statement PDF contains an incremental-update revision after signing, and creator/producer disagree.",
        "documents": ["bank_statement"], "confidence_expectation": "high"})

    # A6 visual: ID photo shows copy-move duplication and photo-editor EXIF
    planted.append({
        "id": "A6_photo_splice", "class": "visual_forensic",
        "detail": "ID photo region shows duplicated (copy-move) texture and EXIF Software tag indicates photo-editing software.",
        "documents": ["id"], "confidence_expectation": "medium"})

    # A7 cross-document: employer name mismatch salary slip vs application
    m_sal = dict(m); m_sal["employer"] = "Nimbus Data Labs LLP"
    planted.append({
        "id": "A7_employer_mismatch", "class": "cross_document",
        "detail": "Employer on salary slip (Nimbus Data Labs LLP) differs from application (Nimbus Analytics Pvt Ltd).",
        "documents": ["salary_slip", "application"], "confidence_expectation": "medium"})

    # A8 cross-document date logic: application date precedes ID issue date
    m_id["id_issue_date"] = "22-07-2027"
    planted.append({
        "id": "A8_date_logic", "class": "cross_document",
        "detail": "PAN issue date (22-07-2027) is after the application date (05-09-2026), which is impossible.",
        "documents": ["id", "application"], "confidence_expectation": "high"})

    # assemble manipulated packet with field-level overrides baked into each doc
    MANIP.mkdir(parents=True, exist_ok=True)
    # application uses inflated declared income + genuine identity
    app_profile = dict(m); app_profile["monthly_net_income"] = m["monthly_net_income_declared"]
    make_application_form(MANIP / "01_loan_application.pdf", app_profile)
    # ID uses mismatched DOB + future issue date + splice
    make_id_card(MANIP / "02_pan_id.jpg", m_id, copy_move=True, mark_edited=True)
    # address proof uses mismatched address
    make_address_proof(MANIP / "03_address_proof.pdf", m_addr)
    # salary slip uses mismatched employer, true net income
    make_salary_slip(MANIP / "04_salary_slip.pdf", m_sal)
    # bank statement: broken arithmetic + incremental tamper
    make_bank_statement(MANIP / "05_bank_statement.pdf", m, break_balance=True)
    tamper_pdf_incremental(MANIP / "05_bank_statement.pdf")

    # rasterize manipulated PDFs
    for pdf in MANIP.glob("*.pdf"):
        render_pdf_to_png(pdf, MANIP / (pdf.stem + ".png"))

    # ground truth
    gt = {
        "seed": SEED,
        "note": "All documents are fully synthetic. No real PII is used.",
        "genuine_packet": {"expected_findings": 0,
                           "profile": {k: v for k, v in g.items()}},
        "manipulated_packet": {"planted_anomalies": planted},
    }
    (HERE / "ground_truth.json").write_text(json.dumps(gt, indent=2), encoding="utf-8")

    md = ["# Demonstration Dataset - Ground Truth", "",
          "All documents are fully synthetic. No real person, PAN, account or photograph is used.",
          "", f"Deterministic seed: {SEED}", "",
          "## Genuine packet (`dataset/genuine/`)", "",
          "An internally consistent loan / KYC packet. Expected findings: 0 high-confidence anomalies.",
          "", "## Manipulated packet (`dataset/manipulated/`)", "",
          "The same packet with the following planted anomalies:", "",
          "| ID | Class | Documents | Detail | Expected confidence |",
          "|----|-------|-----------|--------|---------------------|"]
    for a in planted:
        md.append(f"| {a['id']} | {a['class']} | {', '.join(a['documents'])} | {a['detail']} | {a['confidence_expectation']} |")
    md += ["", "Classes: cross_document (contextual correlation), structural (within-document arithmetic/logic),",
           "pdf_forensic (born-digital PDF tamper), visual_forensic (image-level, reported at low/medium confidence)."]
    (HERE / "GROUND_TRUTH.md").write_text("\n".join(md), encoding="utf-8")

    print("Dataset generated.")
    print("  genuine packet     :", len(list(GENUINE.glob('*'))), "files")
    print("  manipulated packet :", len(list(MANIP.glob('*'))), "files")
    print("  planted anomalies  :", len(planted))


if __name__ == "__main__":
    main()
