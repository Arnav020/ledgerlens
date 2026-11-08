"""
OCR and layout-aware field extraction.

Design notes:
- We run REAL OCR (Tesseract via pytesseract) over the rendered page image and
  keep every word's bounding box and confidence. Nothing is read from the
  generator's ground truth.
- Columnar label/value layouts (common in forms) break naive line grouping, so
  we regroup words into rows by their vertical position, then read the value as
  the tokens to the right of a field's label on the same row. This genuinely
  interprets layout (Document Understanding) rather than using fixed templates.
- Document type is classified from OCR keywords.
- For born-digital PDFs we additionally parse the text layer (PyMuPDF) where a
  precise numeric ledger is needed; scanned images fall back to OCR only.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

from .model import BBox, Field


def _to_int(token: str):
    s = re.sub(r"[^0-9\-]", "", token.replace("+", ""))
    if s in ("", "-"):
        return None
    try:
        return int(s)
    except ValueError:
        return None


def parse_bank_ledger(pdf_path: str):
    """
    Parse a born-digital bank-statement PDF text layer into a ledger.
    Returns dict: opening, transactions [(date, amount, balance)],
    closing_printed, computed_closing. None values if not parseable.
    """
    doc = fitz.open(pdf_path)
    words = doc[0].get_text("words")  # (x0,y0,x1,y1,word,block,line,wordno)
    doc.close()
    # group by VISUAL row (y position), since columns land in different blocks
    rows = []
    for x0, y0, x1, y1, word, *_ in sorted(words, key=lambda w: (w[1], w[0])):
        cy = (y0 + y1) / 2
        placed = False
        for row in rows:
            if abs(cy - row["cy"]) <= 4:
                row["words"].append((x0, word)); placed = True; break
        if not placed:
            rows.append({"cy": cy, "words": [(x0, word)]})
    text_lines = [[w for _, w in sorted(r["words"])] for r in rows]

    opening = closing_printed = None
    txns = []
    date_re = re.compile(r"^\d{2}-\d{2}-\d{4}$")
    for toks in text_lines:
        joined = " ".join(toks).lower()
        nums = [t for t in toks if _to_int(t) is not None and re.search(r"\d", t)]
        if "opening balance" in joined and nums:
            opening = _to_int(nums[-1])
        elif "closing balance" in joined and nums:
            closing_printed = _to_int(nums[-1])
        elif toks and date_re.match(toks[0]) and len(nums) >= 2:
            amount = _to_int(nums[-2])
            balance = _to_int(nums[-1])
            txns.append((toks[0], amount, balance))
    computed = None
    if opening is not None and txns:
        computed = opening + sum(a for _, a, _ in txns if a is not None)
    return {"opening": opening, "transactions": txns,
            "closing_printed": closing_printed, "computed_closing": computed}

# ---------------------------------------------------------------------------
# OCR primitives
# ---------------------------------------------------------------------------

def ocr_words(image_path: str):
    """Return list of word dicts: {text,l,t,w,h,conf} with conf in 0..1."""
    img = Image.open(image_path)
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    words = []
    for i in range(len(data["text"])):
        txt = data["text"][i].strip()
        conf = data["conf"][i]
        try:
            conf = float(conf)
        except Exception:
            conf = -1.0
        if not txt or conf < 0:
            continue
        words.append({
            "text": txt, "l": int(data["left"][i]), "t": int(data["top"][i]),
            "w": int(data["width"][i]), "h": int(data["height"][i]),
            "conf": conf / 100.0,
        })
    return words


def group_rows(words, y_tol_ratio=0.6):
    """Group words into visual rows by vertical overlap, robust to column gaps."""
    rows = []
    for wd in sorted(words, key=lambda w: (w["t"], w["l"])):
        placed = False
        cy = wd["t"] + wd["h"] / 2
        for row in rows:
            ry = row["cy"]
            # base tolerance on the SMALLER height (so one oversized OCR artifact
            # cannot merge distant lines), with a sane absolute cap.
            tol = max(6.0, min(min(wd["h"], row["h"]) * y_tol_ratio, 20.0))
            if abs(cy - ry) <= tol:
                row["words"].append(wd)
                n = len(row["words"])
                row["cy"] = (ry * (n - 1) + cy) / n
                row["h"] = max(row["h"], wd["h"])
                placed = True
                break
        if not placed:
            rows.append({"cy": cy, "h": wd["h"], "words": [wd]})
    for row in rows:
        row["words"].sort(key=lambda w: w["l"])
    rows.sort(key=lambda r: r["cy"])
    return rows


def _union_bbox(words) -> Optional[BBox]:
    if not words:
        return None
    x0 = min(w["l"] for w in words)
    y0 = min(w["t"] for w in words)
    x1 = max(w["l"] + w["w"] for w in words)
    y1 = max(w["t"] + w["h"] for w in words)
    return BBox(x0, y0, x1 - x0, y1 - y0)


PAN_RE = re.compile(r"[A-Z]{5}\d{4}[A-Z]", re.I)
DATE_RE = re.compile(r"\d{2}[-/]\d{2}[-/]\d{4}")


def _row_has_label(row, label_tokens):
    low = [w["text"].lower().strip(":") for w in row["words"]]
    n = len(label_tokens)
    for i in range(0, len(low) - n + 1):
        if low[i:i + n] == label_tokens:
            return i
    return -1


def find_field(rows, label: str, want_regex=None, skip_row_tokens=("income", "department")):
    """
    Locate a label phrase and return (value_text, bbox, conf).

    Tries, for each occurrence of the label:
      1. value = tokens to the RIGHT of the label on the same row;
      2. else value = the next row below (stacked label/value layout).
    If want_regex is given, only a candidate whose text matches is accepted, and
    occurrences inside a title row (containing skip_row_tokens) are ignored.
    Returns None if nothing suitable is found.
    """
    label_tokens = [t.lower().strip(":") for t in label.split()]
    n = len(label_tokens)
    for ri, row in enumerate(rows):
        i = _row_has_label(row, label_tokens)
        if i < 0:
            continue
        row_text = " ".join(w["text"].lower() for w in row["words"])
        if want_regex is not None and any(s in row_text for s in skip_row_tokens):
            continue
        # 1) same-row, to the right of the label
        right = row["words"][i + n:]
        candidates = []
        if right:
            candidates.append(right)
        # 2) the row below (stacked layout)
        if ri + 1 < len(rows):
            candidates.append(rows[ri + 1]["words"])
        for value_words in candidates:
            if not value_words:
                continue
            value = " ".join(w["text"] for w in value_words).strip()
            if want_regex is not None:
                m = want_regex.search(value)
                if not m:
                    continue
            bbox = _union_bbox(value_words)
            conf = min(w["conf"] for w in value_words)
            return value, bbox, conf
    return None


# ---------------------------------------------------------------------------
# Document classification
# ---------------------------------------------------------------------------

DOC_SIGNATURES = [
    ("loan_application", ["personal loan application", "applicant details", "loan amount requested"]),
    ("bank_statement", ["account statement", "closing balance", "statement period"]),
    ("salary_slip", ["payslip", "net pay", "gross earnings", "salary"]),
    ("address_proof", ["electricity bill", "consumer name", "supply address"]),
    ("pan_id", ["income tax department", "permanent account", "pan"]),
]


def classify(full_text: str) -> str:
    t = full_text.lower()
    best, score = "unknown", 0
    for dtype, keys in DOC_SIGNATURES:
        s = sum(1 for k in keys if k in t)
        if s > score:
            best, score = dtype, s
    return best


# ---------------------------------------------------------------------------
# Per-document-type field anchors (canonical_name -> on-page label)
# ---------------------------------------------------------------------------

FIELD_ANCHORS = {
    "loan_application": {
        "full_name": "Full Name",
        "date_of_birth": "Date of Birth",
        "pan": "PAN Number",
        "address": "Residential Address",
        "employer": "Employer Name",
        "declared_monthly_income": "Declared Monthly Income",
        "account_number": "Bank Account Number",
        "loan_amount": "Loan Amount Requested",
        "application_date": "Application Date",
    },
    "bank_statement": {
        "full_name": "Account Holder",
        "account_number": "Account Number",
        "statement_period": "Statement Period",
        "closing_balance": "Closing Balance",
    },
    "salary_slip": {
        "full_name": "Employee Name",
        "pan": "PAN",
        "net_pay": "Net Pay",
        "gross_earnings": "Gross Earnings",
        "pay_date": "Pay Date",
    },
    "address_proof": {
        "full_name": "Consumer Name",
        "address": "Supply Address",
        "bill_date": "Bill Date",
    },
    "pan_id": {
        "full_name": "Name",
        "date_of_birth": "Date of Birth",
        "pan": "PAN",
        "id_issue_date": "Date of Issue",
    },
}

# document-type specific "title line" fields (not label:value)
TITLE_FIELDS = {
    "salary_slip": "employer",   # employer name is the top title line
}


def normalize_value(name: str, value: str) -> str:
    v = value.strip()
    if name in ("declared_monthly_income", "net_pay", "gross_earnings",
                "closing_balance", "loan_amount"):
        digits = re.sub(r"[^0-9]", "", v)
        return digits
    if name in ("date_of_birth", "application_date", "id_issue_date",
                "bill_date", "pay_date"):
        m = re.search(r"\d{2}[-/]\d{2}[-/]\d{4}", v)
        return m.group(0).replace("/", "-") if m else v
    if name == "pan":
        m = re.search(r"[A-Z]{5}\d{4}[A-Z]", v.upper().replace(" ", ""))
        return m.group(0) if m else v.upper()
    if name == "account_number":
        return re.sub(r"\s+", " ", v).strip()
    return v


# ---------------------------------------------------------------------------
# Main extraction entry point
# ---------------------------------------------------------------------------

def extract_document(doc_id: str, page_image: str, doc_type_hint: Optional[str] = None):
    words = ocr_words(page_image)
    rows = group_rows(words)
    full_text = " ".join(w["text"] for w in words)
    doc_type = doc_type_hint or classify(full_text)

    fields = {}
    anchors = FIELD_ANCHORS.get(doc_type, {})
    for name, label in anchors.items():
        want = None
        if name == "pan":
            want = PAN_RE
        elif name in ("date_of_birth", "id_issue_date", "application_date",
                       "bill_date", "pay_date"):
            want = DATE_RE
        hit = find_field(rows, label, want_regex=want)
        if hit is None:
            continue
        raw_value, bbox, conf = hit
        value = normalize_value(name, raw_value)
        fields[name] = Field(
            doc_id=doc_id, doc_type=doc_type, name=name, label=label,
            value=value, raw_value=raw_value, confidence=round(conf, 3),
            bbox=bbox, page_image=page_image,
        )

    # regex fallback for PAN (unambiguous) if the labelled extraction missed it
    if "pan" in anchors and "pan" not in fields:
        for wd in words:
            m = PAN_RE.search(wd["text"].upper().replace(" ", ""))
            if m:
                fields["pan"] = Field(
                    doc_id=doc_id, doc_type=doc_type, name="pan", label="(pattern match)",
                    value=m.group(0), raw_value=wd["text"], confidence=round(wd["conf"], 3),
                    bbox=BBox(wd["l"], wd["t"], wd["w"], wd["h"]), page_image=page_image)
                break

    # title-line field (e.g. employer on a salary slip = top-most large row)
    if doc_type in TITLE_FIELDS and rows:
        name = TITLE_FIELDS[doc_type]
        top_row = rows[0]
        value = " ".join(w["text"] for w in top_row["words"]).strip()
        fields[name] = Field(
            doc_id=doc_id, doc_type=doc_type, name=name, label="(title)",
            value=value, raw_value=value,
            confidence=round(min(w["conf"] for w in top_row["words"]), 3),
            bbox=_union_bbox(top_row["words"]), page_image=page_image,
        )

    return doc_type, fields, full_text
