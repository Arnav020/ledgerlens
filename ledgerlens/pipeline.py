"""
End-to-end investigation pipeline.

run(packet_dir) -> InvestigationResult with documents, extracted fields, the
evidence graph, ranked findings, and an audit trail.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field as dc_field
from pathlib import Path

from .extract import extract_document
from .graph import detect_contradictions
from .checks import ALL_CHECKS

# filename prefix -> (doc_id, display_name, doc_type hint)
DOC_SPECS = {
    "01": ("application", "Loan Application Form", "loan_application"),
    "02": ("id", "PAN Identity Card", "pan_id"),
    "03": ("address_proof", "Electricity Bill (Address Proof)", "address_proof"),
    "04": ("salary_slip", "Salary Slip", "salary_slip"),
    "05": ("bank_statement", "Bank Statement", "bank_statement"),
}

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


@dataclass
class InvestigationResult:
    packet_dir: str
    documents: dict
    fields_by_doc: dict
    graph: dict
    findings: list
    audit: list = dc_field(default_factory=list)

    def to_dict(self):
        return {
            "packet_dir": self.packet_dir,
            "documents": {k: {kk: str(vv) for kk, vv in v.items()}
                          for k, v in self.documents.items()},
            "fields": {d: {n: f.to_dict() for n, f in fs.items()}
                       for d, fs in self.fields_by_doc.items()},
            "findings": [f.to_dict() for f in self.findings],
            "audit": self.audit,
        }


def _discover(packet_dir: Path):
    documents = {}
    for p in sorted(packet_dir.iterdir()):
        if p.suffix.lower() == ".pdf":
            prefix = p.stem[:2]
            if prefix in DOC_SPECS:
                doc_id, display, dtype = DOC_SPECS[prefix]
                png = p.with_suffix(".png")
                documents[doc_id] = {
                    "doc_type": dtype, "display_name": display,
                    "original_path": str(p),
                    "page_image": str(png if png.exists() else p)}
        elif p.suffix.lower() in (".jpg", ".jpeg", ".png"):
            prefix = p.stem[:2]
            # skip the rasterized renders of PDFs (their stem matches a pdf)
            if (packet_dir / (p.stem + ".pdf")).exists():
                continue
            if prefix in DOC_SPECS:
                doc_id, display, dtype = DOC_SPECS[prefix]
                documents[doc_id] = {
                    "doc_type": dtype, "display_name": display,
                    "original_path": str(p), "page_image": str(p)}
    return documents


def run(packet_dir: str) -> InvestigationResult:
    packet_dir = Path(packet_dir)
    audit = []
    def log(stage, msg):
        audit.append({"ts": _dt.datetime.now().isoformat(timespec="seconds"),
                      "stage": stage, "message": msg})

    documents = _discover(packet_dir)
    log("ingest", f"Discovered {len(documents)} documents in {packet_dir.name}")

    fields_by_doc = {}
    for doc_id, meta in documents.items():
        dtype, fields, _ = extract_document(doc_id, meta["page_image"], meta["doc_type"])
        fields_by_doc[doc_id] = fields
        log("extract", f"{meta['display_name']}: classified as {dtype}, "
                       f"extracted {len(fields)} fields")

    graph, findings = detect_contradictions(fields_by_doc, documents)
    log("correlate", f"Evidence graph: {len(graph['nodes'])} entity nodes, "
                     f"{len(graph['edges'])} correlation edges, "
                     f"{len(findings)} cross-document contradiction(s)")

    for check in ALL_CHECKS:
        new = check(fields_by_doc, documents)
        if new:
            log("check", f"{check.__name__}: {len(new)} finding(s)")
        findings.extend(new)

    findings.sort(key=lambda f: (SEVERITY_RANK.get(f.severity, 9), f.id))
    log("rank", f"Total findings: {len(findings)}")

    return InvestigationResult(str(packet_dir), documents, fields_by_doc,
                               graph, findings, audit)
