"""
The evidence graph.

Every extracted field becomes a provenance-stamped node. Fields that describe
the SAME real-world entity (the applicant's date of birth, PAN, address, ...)
are linked across documents. When linked values disagree, that edge is a
contradiction, which is the core of cross-document contextual intelligence.

This module builds the graph (for visualization) and detects cross-document
contradictions generically, so one mechanism covers name, DOB, PAN, address,
employer and account-number conflicts.
"""
from __future__ import annotations

import re
from .model import Finding, Evidence, TIER_HIGH, STATUS_OBSERVED

# canonical entities we correlate across documents, with how to compare them
CORRELATED_ENTITIES = {
    "full_name": {"label": "Name", "mode": "name", "severity": "high"},
    "date_of_birth": {"label": "Date of Birth", "mode": "exact", "severity": "critical"},
    "pan": {"label": "PAN", "mode": "alnum", "severity": "critical"},
    "address": {"label": "Address", "mode": "address", "severity": "high"},
    "employer": {"label": "Employer", "mode": "name", "severity": "medium"},
    "account_number": {"label": "Account Number", "mode": "digits", "severity": "high"},
}


def _norm(value: str, mode: str) -> str:
    v = (value or "").strip().lower()
    if mode == "alnum":
        return re.sub(r"[^a-z0-9]", "", v)
    if mode == "digits":
        return re.sub(r"[^0-9]", "", v)
    if mode == "name":
        return re.sub(r"[^a-z ]", "", v).strip()
    if mode == "address":
        # compare the informative tokens (street number + pin) rather than
        # punctuation/case, so trivial formatting differences do not flag.
        return re.sub(r"[^a-z0-9 ]", "", v)
    return v


def build_graph(fields_by_doc):
    """Return a graph dict: nodes (entity instances) and correlation edges."""
    nodes, edges = [], []
    by_entity = {}
    for doc_id, fields in fields_by_doc.items():
        for name, f in fields.items():
            if name in CORRELATED_ENTITIES:
                node_id = f"{doc_id}:{name}"
                nodes.append({"id": node_id, "entity": name, "doc_id": doc_id,
                              "value": f.value, "confidence": f.confidence})
                by_entity.setdefault(name, []).append((doc_id, f))
    for name, instances in by_entity.items():
        for i in range(len(instances)):
            for j in range(i + 1, len(instances)):
                d1, f1 = instances[i]; d2, f2 = instances[j]
                mode = CORRELATED_ENTITIES[name]["mode"]
                agree = _norm(f1.value, mode) == _norm(f2.value, mode)
                edges.append({"entity": name, "a": f"{d1}:{name}",
                              "b": f"{d2}:{name}", "agree": agree})
    return {"nodes": nodes, "edges": edges, "by_entity": by_entity}


def detect_contradictions(fields_by_doc, documents):
    graph = build_graph(fields_by_doc)
    findings = []
    seq = 0
    for name, cfg in CORRELATED_ENTITIES.items():
        instances = graph["by_entity"].get(name, [])
        if len(instances) < 2:
            continue
        mode = cfg["mode"]
        # bucket documents by normalized value
        buckets = {}
        for doc_id, f in instances:
            buckets.setdefault(_norm(f.value, mode), []).append((doc_id, f))
        if len(buckets) <= 1:
            continue  # all agree
        seq += 1
        # build a finding describing the disagreement
        values_desc = []
        evidence = []
        docs_involved = []
        for _, group in buckets.items():
            for doc_id, f in group:
                dn = documents[doc_id]["display_name"]
                values_desc.append(f'"{f.value}" on {dn}')
                docs_involved.append(doc_id)
                evidence.append(Evidence(
                    doc_id=doc_id, page_image=f.page_image, bbox=f.bbox,
                    snippet=f.value, field_name=name))
        findings.append(Finding(
            id=f"XDOC-{name.upper()}-{seq}",
            title=f"{cfg['label']} conflicts across documents",
            anomaly_class="cross_document",
            severity=cfg["severity"],
            confidence_tier=TIER_HIGH,
            status=STATUS_OBSERVED,
            documents=sorted(set(docs_involved)),
            explanation=(f"The {cfg['label'].lower()} does not match across the packet: "
                         + "; ".join(values_desc) +
                         ". Values for the same applicant entity should be identical "
                         "across all submitted documents."),
            evidence=evidence,
            recommended_action="Verify the applicant's "
                               f"{cfg['label'].lower()} against an authoritative source."))
    return graph, findings
