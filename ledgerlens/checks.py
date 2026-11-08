"""
Deterministic checks that run over the extracted fields, the evidence graph and
the original files. Each returns a list of Finding objects with grounded
explanations and provenance. The LLM never decides here; these are explainable,
reproducible signals.
"""
from __future__ import annotations

import re
from pathlib import Path

import fitz
import numpy as np

from .model import (BBox, Finding, Evidence,
                    TIER_HIGH, TIER_MEDIUM, TIER_LOW,
                    STATUS_OBSERVED, STATUS_POTENTIAL, STATUS_NEEDS_REVIEW)
from .extract import parse_bank_ledger


def _f(fields_by_doc, doc_id, name):
    return fields_by_doc.get(doc_id, {}).get(name)


def _ev(field, snippet=None):
    return Evidence(doc_id=field.doc_id, page_image=field.page_image,
                    bbox=field.bbox, snippet=snippet or field.value,
                    field_name=field.name)


# ---------------------------------------------------------------------------
# Cross-document financial reconciliation (income)
# ---------------------------------------------------------------------------

def check_income_reconciliation(fields_by_doc, documents):
    findings = []
    app = None; sal = None
    for doc_id, fields in fields_by_doc.items():
        if fields.get("declared_monthly_income"):
            app = fields["declared_monthly_income"]
        if documents[doc_id]["doc_type"] == "salary_slip" and fields.get("net_pay"):
            sal = fields["net_pay"]
    # bank salary credit (largest positive transaction)
    bank_credit = None; bank_doc = None
    for doc_id, meta in documents.items():
        if meta["doc_type"] == "bank_statement":
            ledger = parse_bank_ledger(meta["original_path"])
            pos = [a for _, a, _ in ledger["transactions"] if a and a > 0]
            if pos:
                bank_credit = max(pos); bank_doc = doc_id
    if app is None:
        return findings
    declared = int(app.value) if app.value.isdigit() else None
    if declared is None:
        return findings
    comparisons = []
    evidence = [_ev(app, snippet=f"Declared INR {declared:,}")]
    if sal is not None and sal.value.isdigit():
        net = int(sal.value)
        comparisons.append((net, "salary slip net pay"))
        evidence.append(_ev(sal, snippet=f"Net pay INR {net:,}"))
    if bank_credit is not None:
        comparisons.append((bank_credit, "bank statement salary credit"))
    worst = [c for c in comparisons if abs(c[0] - declared) / max(declared, 1) > 0.15]
    if worst:
        detail = "; ".join(f"INR {amt:,} ({src})" for amt, src in comparisons)
        findings.append(Finding(
            id="FIN-INCOME-1",
            title="Declared income is not supported by payroll or bank records",
            anomaly_class="cross_document",
            severity="high", confidence_tier=TIER_HIGH, status=STATUS_OBSERVED,
            documents=sorted({app.doc_id} | ({sal.doc_id} if sal else set())
                             | ({bank_doc} if bank_doc else set())),
            explanation=(f"The application declares a monthly income of INR {declared:,}, "
                         f"but corroborating documents show {detail}. Declared income "
                         "materially exceeds the income evidenced by payroll and bank records."),
            evidence=evidence,
            recommended_action="Confirm actual monthly income from payroll and bank credits "
                               "before using the declared figure for loan eligibility."))
    return findings


# ---------------------------------------------------------------------------
# Cross-document date logic
# ---------------------------------------------------------------------------

def _parse_date(s):
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})", s or "")
    if not m:
        return None
    d, mo, y = map(int, m.groups())
    return y * 10000 + mo * 100 + d


def check_date_logic(fields_by_doc, documents):
    findings = []
    app_date = id_issue = None
    for doc_id, fields in fields_by_doc.items():
        if fields.get("application_date"):
            app_date = fields["application_date"]
        if fields.get("id_issue_date"):
            id_issue = fields["id_issue_date"]
    if app_date and id_issue:
        a = _parse_date(app_date.value); b = _parse_date(id_issue.value)
        if a and b and b > a:
            findings.append(Finding(
                id="DATE-LOGIC-1",
                title="Identity document issued after the application date",
                anomaly_class="cross_document",
                severity="high", confidence_tier=TIER_HIGH, status=STATUS_OBSERVED,
                documents=sorted({app_date.doc_id, id_issue.doc_id}),
                explanation=(f"The PAN identity document shows an issue date of {id_issue.value}, "
                             f"which is after the application date {app_date.value}. An identity "
                             "proof cannot be issued after the application that relies on it."),
                evidence=[_ev(id_issue), _ev(app_date)],
                recommended_action="Re-verify the identity document and its issue date."))
    return findings


# ---------------------------------------------------------------------------
# Within-document structural arithmetic (bank statement)
# ---------------------------------------------------------------------------

def check_statement_arithmetic(fields_by_doc, documents):
    findings = []
    for doc_id, meta in documents.items():
        if meta["doc_type"] != "bank_statement":
            continue
        ledger = parse_bank_ledger(meta["original_path"])
        comp = ledger["computed_closing"]; printed = ledger["closing_printed"]
        if comp is None or printed is None:
            continue
        if comp != printed:
            cb = _f(fields_by_doc, doc_id, "closing_balance")
            ev = [_ev(cb, snippet=f"Printed closing INR {printed:,}")] if cb else []
            findings.append(Finding(
                id="STRUCT-BALANCE-1",
                title="Bank statement closing balance does not reconcile",
                anomaly_class="structural",
                severity="high", confidence_tier=TIER_HIGH, status=STATUS_OBSERVED,
                documents=[doc_id],
                explanation=(f"The statement prints a closing balance of INR {printed:,}, but the "
                             f"opening balance plus the sum of the listed transactions comes to "
                             f"INR {comp:,}. The ledger does not add up, a strong indicator that the "
                             f"closing figure was altered (difference INR {printed - comp:,})."),
                evidence=ev,
                recommended_action="Recompute the ledger from the transaction list and obtain a "
                                   "bank-certified statement."))
    return findings


# ---------------------------------------------------------------------------
# Born-digital PDF forensics
# ---------------------------------------------------------------------------

def revision_diff_bbox(pdf_path, page_image, dpi=150):
    """
    An incremental-update PDF keeps its PRIOR revision inside the file. We render
    the prior revision (bytes up to the first %%EOF) and the current revision,
    diff them, and return the BBox (in page-image pixels) of what changed after
    signing. Deterministic and precise. Returns None if there is no prior revision.
    """
    try:
        raw = Path(pdf_path).read_bytes()
        idx = raw.find(b"%%EOF")
        if idx < 0 or raw.count(b"%%EOF") < 2:
            return None
        prior_bytes = raw[:idx + 5]
        d0 = fitz.open(stream=prior_bytes, filetype="pdf")
        d1 = fitz.open(pdf_path)
        p0 = d0[0].get_pixmap(dpi=dpi); p1 = d1[0].get_pixmap(dpi=dpi)
        import numpy as _np
        a0 = _np.frombuffer(p0.samples, dtype=_np.uint8).reshape(p0.h, p0.w, p0.n)
        a1 = _np.frombuffer(p1.samples, dtype=_np.uint8).reshape(p1.h, p1.w, p1.n)
        d0.close(); d1.close()
        if a0.shape != a1.shape:
            return None
        diff = _np.abs(a0.astype("int16") - a1.astype("int16")).sum(axis=2)
        ys, xs = _np.where(diff > 40)
        if len(xs) < 5:
            return None
        # scale from render dpi to the stored page_image resolution if different
        from PIL import Image as _Image
        pw, ph = _Image.open(page_image).size
        sx = pw / p1.w; sy = ph / p1.h
        x0 = int(xs.min() * sx); y0 = int(ys.min() * sy)
        x1 = int(xs.max() * sx); y1 = int(ys.max() * sy)
        return BBox(x0, y0, max(4, x1 - x0), max(4, y1 - y0))
    except Exception:
        return None


def check_pdf_forensics(fields_by_doc, documents):
    findings = []
    for doc_id, meta in documents.items():
        path = meta["original_path"]
        if not str(path).lower().endswith(".pdf"):
            continue
        raw = Path(path).read_bytes()
        eof = raw.count(b"%%EOF")
        doc = fitz.open(path)
        md = doc.metadata or {}
        doc.close()
        signals = []
        if eof > 1:
            signals.append(f"the file contains {eof - 1} incremental-update revision(s) "
                           "appended after the original was written")
        creator = (md.get("creator") or "").strip()
        producer = (md.get("producer") or "").strip()
        if creator and producer and creator.split()[0].lower() != producer.split()[0].lower():
            signals.append(f"the creator ('{creator}') and producer ('{producer}') disagree, "
                           "which happens when a file is re-saved by a different tool")
        if signals:
            region = revision_diff_bbox(path, meta["page_image"]) if eof > 1 else None
            ev = [Evidence(doc_id=doc_id, page_image=meta["page_image"], bbox=region,
                           snippet="Content added after the original revision"
                                   if region else "PDF revision / metadata signal")]
            loc = (" The content that changed between revisions has been localized on the page."
                   if region else "")
            findings.append(Finding(
                id=f"PDF-FORENSIC-{doc_id}",
                title="Born-digital PDF shows post-authoring modification",
                anomaly_class="pdf_forensic",
                severity="high", confidence_tier=TIER_HIGH, status=STATUS_POTENTIAL,
                documents=[doc_id],
                explanation=("Structural analysis of the PDF indicates it was modified after it "
                             "was first produced: " + "; and ".join(signals) +
                             ". This is deterministic file-structure evidence, not a visual guess." + loc +
                             " A revision can be benign, so this is flagged for human review."),
                evidence=ev,
                recommended_action="Obtain the original unmodified PDF directly from the issuer."))
    return findings


# ---------------------------------------------------------------------------
# Visual-forensic signals (honest, low/medium confidence, needs human review)
# ---------------------------------------------------------------------------

def _exif_software(path):
    try:
        import piexif
        ex = piexif.load(str(path))
        soft = ex["0th"].get(piexif.ImageIFD.Software)
        return soft.decode("utf-8", "ignore") if isinstance(soft, bytes) else soft
    except Exception:
        return None


def ela_map(path, quality=90):
    """Error Level Analysis: re-save at a fixed JPEG quality and measure the
    per-pixel error. A region with a different compression history (e.g. a
    spliced patch) shows markedly higher error. Returns (error_grid, cols, rows,
    cell_w, cell_h) over a coarse block grid, or None."""
    import io
    from PIL import Image, ImageChops
    try:
        orig = Image.open(path).convert("RGB")
        buf = io.BytesIO()
        orig.save(buf, format="JPEG", quality=quality)
        buf.seek(0)
        resaved = Image.open(buf).convert("RGB")
        diff = np.asarray(ImageChops.difference(orig, resaved)).astype("float32").sum(axis=2)
        H, W = diff.shape
        gx, gy = 24, 24
        cw, ch = max(1, W // gx), max(1, H // gy)
        grid = np.zeros((gy, gx), dtype="float32")
        for j in range(gy):
            for i in range(gx):
                block = diff[j * ch:(j + 1) * ch, i * cw:(i + 1) * cw]
                grid[j, i] = block.mean() if block.size else 0.0
        return grid, gx, gy, cw, ch
    except Exception:
        return None


def _ela_region(path):
    """Return a BBox of the strongest localized ELA anomaly if it stands out
    well above the rest of the image, else None. LOW confidence by nature."""
    res = ela_map(path)
    if res is None:
        return None
    grid, gx, gy, cw, ch = res
    med = float(np.median(grid))
    mad = float(np.median(np.abs(grid - med))) + 1e-6
    z = (grid - med) / (1.4826 * mad)
    hot = z > 6.0            # blocks far above the image's typical error
    # require a compact cluster of hot blocks (a real region, not scattered noise)
    ys, xs = np.where(hot)
    if len(xs) < 6:
        return None
    # cluster compactness: the hot blocks should be spatially concentrated
    if xs.std() > gx * 0.22 or ys.std() > gy * 0.22:
        return None
    x0 = int(xs.min() * cw); y0 = int(ys.min() * ch)
    x1 = int((xs.max() + 1) * cw); y1 = int((ys.max() + 1) * ch)
    return BBox(x0, y0, x1 - x0, y1 - y0)


def check_visual_forensics(fields_by_doc, documents):
    findings = []
    for doc_id, meta in documents.items():
        path = meta["original_path"]
        is_image = str(path).lower().endswith((".jpg", ".jpeg", ".png"))
        if not is_image:
            continue
        soft = _exif_software(path)
        if soft and any(k in soft.lower() for k in ("photoshop", "gimp", "editor", "lightroom")):
            findings.append(Finding(
                id=f"VIS-EXIF-{doc_id}",
                title="Image metadata indicates photo-editing software",
                anomaly_class="visual_forensic",
                severity="medium", confidence_tier=TIER_MEDIUM, status=STATUS_POTENTIAL,
                documents=[doc_id],
                explanation=(f"The image's EXIF metadata records editing software ('{soft}'). "
                             "Identity photos captured by a scanner or camera would not normally "
                             "carry a photo-editor signature. This is a supporting signal, not proof."),
                evidence=[Evidence(doc_id=doc_id, page_image=meta["page_image"], bbox=None,
                                   snippet=f"EXIF Software: {soft}")],
                recommended_action="Request the original unedited photograph or a fresh capture."))
        # Note: pixel-level splice localization (ELA) is intentionally NOT turned
        # into an automatic finding. On clean document graphics it is dominated by
        # text edges and does not discriminate reliably (consistent with published
        # benchmarks). The ELA heatmap is still offered in the UI as an exploratory
        # visual aid, clearly labelled low-confidence, for a human to interpret.
    return findings


ALL_CHECKS = [
    check_income_reconciliation,
    check_date_logic,
    check_statement_arithmetic,
    check_pdf_forensics,
    check_visual_forensics,
]
