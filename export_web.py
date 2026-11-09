"""
Export the real investigation output (both packets) as static JSON + images for
the LedgerLens web console (ledgerlens/web/). No server needed: the frontend
renders this precomputed, genuine pipeline output.

Run from the repo root:  python export_web.py
"""
import json
import shutil
from pathlib import Path

from PIL import Image

from ledgerlens.pipeline import run
from ledgerlens.reasoning import investigation_summary
from ledgerlens.viz import render_evidence_graph
from ledgerlens.dossier import generate as generate_dossier

HERE = Path(__file__).resolve().parent
WEB = HERE / "web"
DATA = WEB / "data"


def export_packet(name, packet_dir):
    out = DATA / name
    img_dir = out / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    result = run(packet_dir)
    summary = investigation_summary(result)

    documents = {}
    for doc_id, meta in result.documents.items():
        src = Path(meta["page_image"])
        dst = img_dir / (doc_id + src.suffix.lower())
        shutil.copy(src, dst)
        w, h = Image.open(src).size
        documents[doc_id] = {"id": doc_id, "display_name": meta["display_name"],
                             "doc_type": meta["doc_type"], "img": f"img/{dst.name}", "w": w, "h": h}

    fields = {}
    for doc_id, fs in result.fields_by_doc.items():
        fields[doc_id] = {n: {"value": f.value, "confidence": f.confidence,
                              "bbox": f.bbox.as_list() if f.bbox else None} for n, f in fs.items()}

    findings = []
    for f in result.findings:
        findings.append({
            "id": f.id, "title": f.title, "anomaly_class": f.anomaly_class,
            "severity": f.severity, "confidence_tier": f.confidence_tier, "status": f.status,
            "documents": f.documents, "explanation": f.explanation,
            "recommended_action": f.recommended_action,
            "evidence": [{"doc_id": e.doc_id, "snippet": e.snippet, "field_name": e.field_name,
                          "bbox": e.bbox.as_list() if e.bbox else None} for e in f.evidence]})

    # aggregate the entity-level graph into clean document-to-document correlations
    pairs = {}
    for e in result.graph["edges"]:
        a = e["a"].split(":")[0]; b = e["b"].split(":")[0]
        if a == b:
            continue
        key = tuple(sorted([a, b]))
        p = pairs.setdefault(key, {"a": key[0], "b": key[1], "entities": [], "conflicts": []})
        if e["entity"] not in p["entities"]:
            p["entities"].append(e["entity"])
        if not e["agree"] and e["entity"] not in p["conflicts"]:
            p["conflicts"].append(e["entity"])
    correlations = list(pairs.values())

    payload = {"packet": name, "summary": summary, "documents": documents,
               "fields": fields, "findings": findings, "audit": result.audit,
               "correlations": correlations,
               "node_order": ["application", "id", "bank_statement", "salary_slip", "address_proof"]}
    (DATA / f"{name}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"  {name}: {len(documents)} docs, {len(findings)} findings -> {out}")
    return result


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    rm = export_packet("manipulated", "dataset/manipulated")
    export_packet("genuine", "dataset/genuine")
    # dossier for download
    generate_dossier(rm, str(DATA / "investigation_dossier.pdf"))
    print("done.")


if __name__ == "__main__":
    main()
