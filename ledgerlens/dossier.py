"""
Investigation Dossier generator (PDF), following PS-2 section 7:
  7.1 Document Overview        7.2 Extracted Information
  7.3 Contextual Analysis      7.4 Visual Forensic Findings
  7.5 Evidence and Traceability 7.6 Investigation Summary

Every finding is grounded in the pipeline's evidence and, where a region exists,
an embedded highlighted crop traces it to the exact spot on the source document.
"""
from __future__ import annotations
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image as RLImage, PageBreak, HRFlowable)

from .reasoning import investigation_summary, CLASS_LABELS
from .viz import highlight_crop

NAVY = colors.HexColor("#16365e")
RED = colors.HexColor("#c0291f")
AMBER = colors.HexColor("#b7791f")
GREEN = colors.HexColor("#2f7d46")
GREY = colors.HexColor("#5b6670")

SEV_COLOR = {"critical": RED, "high": RED, "medium": AMBER, "low": GREY}
TIER_LABEL = {"high": "High confidence", "medium": "Medium confidence", "low": "Low confidence"}
STATUS_LABEL = {
    "observed_inconsistency": "Observed inconsistency",
    "potential_manipulation": "Potential manipulation (needs review)",
    "needs_human_review": "Needs human review",
}


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("H", parent=ss["Heading1"], textColor=NAVY, fontSize=15, spaceBefore=12, spaceAfter=6))
    ss.add(ParagraphStyle("H2", parent=ss["Heading2"], textColor=NAVY, fontSize=12, spaceBefore=8, spaceAfter=4))
    ss.add(ParagraphStyle("Body", parent=ss["BodyText"], fontSize=9.5, leading=13))
    ss.add(ParagraphStyle("Small", parent=ss["BodyText"], fontSize=8, textColor=GREY, leading=10))
    ss.add(ParagraphStyle("Finding", parent=ss["BodyText"], fontSize=9.5, leading=13, spaceAfter=2))
    return ss


def _finding_block(f, ss, documents, evidence_dir, idx):
    els = []
    sev = f.severity.upper()
    sc = SEV_COLOR.get(f.severity, GREY)
    header = (f'<font color="{sc.hexval()}"><b>[{sev}] {f.id}</b></font> &nbsp; '
              f'<b>{f.title}</b>')
    els.append(Paragraph(header, ss["Finding"]))
    meta = (f'Class: {CLASS_LABELS.get(f.anomaly_class, f.anomaly_class)} &nbsp;|&nbsp; '
            f'{TIER_LABEL.get(f.confidence_tier, f.confidence_tier)} &nbsp;|&nbsp; '
            f'{STATUS_LABEL.get(f.status, f.status)} &nbsp;|&nbsp; '
            f'Documents: {", ".join(documents[d]["display_name"] for d in f.documents)}')
    els.append(Paragraph(meta, ss["Small"]))
    els.append(Paragraph(f.explanation, ss["Body"]))
    if f.recommended_action:
        els.append(Paragraph(f'<b>Recommended action:</b> {f.recommended_action}', ss["Small"]))
    # embed highlighted evidence crops
    crops = []
    for k, ev in enumerate(f.evidence):
        if ev.bbox:
            out = Path(evidence_dir) / f"{f.id}_{k}.png"
            try:
                highlight_crop(ev.page_image, ev.bbox.as_list() if hasattr(ev.bbox, "as_list") else ev.bbox,
                               out_path=str(out), max_w=360)
                crops.append((documents[ev.doc_id]["display_name"], str(out)))
            except Exception:
                pass
    for dn, img in crops[:2]:
        try:
            im = RLImage(img); im._restrictSize(170, 120)
            els.append(Paragraph(f'Evidence on <b>{dn}</b> (highlighted region traces to source):', ss["Small"]))
            els.append(im)
        except Exception:
            pass
    els.append(Spacer(1, 6))
    els.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#d8dce1")))
    els.append(Spacer(1, 4))
    return els


def generate(result, out_pdf: str, evidence_dir: str = None):
    ss = _styles()
    out_pdf = Path(out_pdf)
    evidence_dir = Path(evidence_dir or (out_pdf.parent / "_evidence"))
    evidence_dir.mkdir(parents=True, exist_ok=True)
    summary = investigation_summary(result)

    doc = SimpleDocTemplate(str(out_pdf), pagesize=A4,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            title="LedgerLens Investigation Dossier")
    E = []
    # Title
    E.append(Paragraph('<font color="#16365e"><b>LedgerLens</b></font> &nbsp; Investigation Dossier', ss["Title"]))
    E.append(Paragraph(f'Packet: <b>{Path(result.packet_dir).name}</b> &nbsp;|&nbsp; '
                       f'Documents analysed: {len(result.documents)} &nbsp;|&nbsp; '
                       f'Findings: {len(result.findings)}', ss["Small"]))
    E.append(Paragraph("All documents are synthetic demonstration data. No real PII is used.", ss["Small"]))
    E.append(Spacer(1, 6))
    # Verdict banner
    vcolor = RED if summary["verdict"] == "HIGH RISK" else (AMBER if "REVIEW" in summary["verdict"] else GREEN)
    banner = Table([[Paragraph(f'<b>Overall assessment: {summary["verdict"]}</b><br/>'
                               f'{summary["recommendation"]}', ss["Body"])]],
                   colWidths=[doc.width])
    banner.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f3f5f8")),
                                ("BOX", (0, 0), (-1, -1), 1, vcolor),
                                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                                ("TOPPADDING", (0, 0), (-1, -1), 6),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    E.append(banner)
    E.append(Spacer(1, 8))

    # 7.1 Document Overview
    E.append(Paragraph("7.1 Document Overview", ss["H"]))
    rows = [["Document", "Type", "Source file", "Status"]]
    for did, meta in result.documents.items():
        rows.append([meta["display_name"], meta["doc_type"],
                     Path(meta["original_path"]).name, "Processed"])
    t = Table(rows, colWidths=[55 * mm, 35 * mm, 50 * mm, 25 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9ced6")),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")])]))
    E.append(t)

    # 7.2 Extracted Information
    E.append(Paragraph("7.2 Extracted Information", ss["H"]))
    for did, fields in result.fields_by_doc.items():
        if not fields:
            continue
        E.append(Paragraph(result.documents[did]["display_name"], ss["H2"]))
        rows = [["Field", "Value", "Confidence"]]
        for name, f in fields.items():
            rows.append([name, f.value, f"{f.confidence:.0%}"])
        t = Table(rows, colWidths=[45 * mm, 90 * mm, 25 * mm])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dfe5ec")),
                               ("FONTSIZE", (0, 0), (-1, -1), 8),
                               ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d2d7de")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        E.append(t)
        E.append(Spacer(1, 4))

    # 7.3 Contextual Analysis
    E.append(PageBreak())
    E.append(Paragraph("7.3 Contextual Analysis (within and across documents)", ss["H"]))
    ctx = [f for f in result.findings if f.anomaly_class in ("cross_document", "structural")]
    if not ctx:
        E.append(Paragraph("No contextual or structural inconsistencies detected.", ss["Body"]))
    for i, f in enumerate(ctx):
        E += _finding_block(f, ss, result.documents, evidence_dir, i)

    # 7.4 Visual Forensic Findings
    E.append(Paragraph("7.4 Visual Forensic Findings", ss["H"]))
    vis = [f for f in result.findings if f.anomaly_class in ("pdf_forensic", "visual_forensic")]
    if not vis:
        E.append(Paragraph("No PDF-structure or visual anomalies detected.", ss["Body"]))
    for i, f in enumerate(vis):
        E += _finding_block(f, ss, result.documents, evidence_dir, 100 + i)

    # 7.5 Evidence and Traceability
    E.append(Paragraph("7.5 Evidence and Traceability", ss["H"]))
    rows = [["Finding", "Document", "Evidence", "Confidence", "Status"]]
    for f in result.findings:
        for ev in f.evidence:
            rows.append([f.id, result.documents[ev.doc_id]["display_name"],
                         (ev.snippet or "")[:40],
                         TIER_LABEL.get(f.confidence_tier, f.confidence_tier),
                         STATUS_LABEL.get(f.status, f.status)])
    t = Table(rows, colWidths=[30 * mm, 38 * mm, 48 * mm, 28 * mm, 34 * mm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("FONTSIZE", (0, 0), (-1, -1), 7.3),
                           ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c9ced6")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    E.append(t)

    # 7.6 Investigation Summary
    E.append(Paragraph("7.6 Investigation Summary", ss["H"]))
    E.append(Paragraph(f'<b>Verdict:</b> {summary["verdict"]}. {summary["recommendation"]}', ss["Body"]))
    by_class = ", ".join(f"{k}: {v}" for k, v in summary["counts_by_class"].items()) or "none"
    E.append(Paragraph(f'<b>Findings by category:</b> {by_class}.', ss["Body"]))
    E.append(Paragraph(f'<b>Observation status:</b> {summary["observed"]} observed inconsistencies, '
                       f'{summary["potential"]} potential manipulations, {summary["needs_review"]} '
                       f'needs-human-review.', ss["Body"]))
    if summary["areas_requiring_verification"]:
        E.append(Paragraph("<b>Areas requiring additional verification:</b>", ss["H2"]))
        for a in summary["areas_requiring_verification"]:
            E.append(Paragraph(f"&bull; {a}", ss["Body"]))
    E.append(Paragraph("<b>Limitations:</b> Findings are investigative signals, not legal "
                       "determinations of fraud. Visual forensics on documents is unreliable and is "
                       "reported at low confidence for human review. OCR output is not treated as "
                       "ground truth. All data here is synthetic.", ss["Small"]))

    doc.build(E)
    return str(out_pdf)
