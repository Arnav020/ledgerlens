"""
LedgerLens review interface (Streamlit).

The mandatory PS-2 "interface for reviewing extracted information and findings".
Runs the real pipeline live, shows extracted fields, ranks findings, and lets a
reviewer click any finding to trace it to the exact highlighted region on the
source document. Generates the investigation dossier on demand.

Run:  streamlit run app.py
"""
import io
import tempfile
from pathlib import Path

import streamlit as st
from PIL import Image

from ledgerlens.pipeline import run
from ledgerlens.reasoning import investigation_summary
from ledgerlens.viz import highlight_full, highlight_crop, render_evidence_graph, ela_heatmap
from ledgerlens.dossier import generate as generate_dossier

st.set_page_config(page_title="LedgerLens", layout="wide", page_icon="::")

st.markdown("""
<style>
.block-container {padding-top: 1.4rem;}
h1, h2, h3 {color: #16365e;}
.ll-badge {display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;color:white;}
.ll-crit {background:#c0291f;} .ll-high {background:#d14836;} .ll-med {background:#b7791f;} .ll-low {background:#5b6670;}
.ll-verdict {padding:12px 16px;border-radius:8px;background:#f3f5f8;border-left:6px solid #c0291f;margin-bottom:8px;}
.ll-card {border:1px solid #e1e5ea;border-radius:8px;padding:10px 12px;margin-bottom:8px;background:white;}
</style>
""", unsafe_allow_html=True)

SEV_CLASS = {"critical": "ll-crit", "high": "ll-high", "medium": "ll-med", "low": "ll-low"}

st.title("LedgerLens")
st.caption("Evidence-driven cross-document forensic investigation for financial document packets. "
           "All demonstration data is synthetic.")

with st.sidebar:
    st.header("Investigation")
    choice = st.radio("Select a document packet", ["manipulated", "genuine", "upload"], index=0)
    packet_dir = None
    if choice in ("manipulated", "genuine"):
        packet_dir = f"dataset/{choice}"
    else:
        up = st.file_uploader("Upload documents (PDF / image)", accept_multiple_files=True)
        if up:
            tmp = Path(tempfile.mkdtemp())
            for f in up:
                (tmp / f.name).write_bytes(f.getbuffer())
            packet_dir = str(tmp)
            st.caption("Note: uploaded files should follow the 01_..05_ naming used in the dataset.")
    go = st.button("Run investigation", type="primary")

if "result" not in st.session_state:
    st.session_state.result = None

if go and packet_dir:
    with st.spinner("Extracting, correlating and investigating..."):
        st.session_state.result = run(packet_dir)

result = st.session_state.result
if result is None:
    st.info("Pick a packet in the sidebar and click **Run investigation**.")
    st.stop()

summary = investigation_summary(result)

# verdict
vcls = "ll-crit" if summary["verdict"] == "HIGH RISK" else ("ll-med" if "REVIEW" in summary["verdict"] else "ll-low")
st.markdown(f"<div class='ll-verdict'><b>Overall assessment: {summary['verdict']}</b><br>"
            f"{summary['recommendation']}</div>", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Documents", len(result.documents))
c2.metric("Findings", len(result.findings))
c3.metric("Observed inconsistencies", summary["observed"])
c4.metric("Needs review", summary["potential"] + summary["needs_review"])

tab_find, tab_fields, tab_graph, tab_audit = st.tabs(
    ["Findings & evidence", "Extracted information", "Evidence graph", "Audit trail"])

with tab_find:
    if not result.findings:
        st.success("No contextual, structural, PDF-structure or metadata anomalies detected.")
    else:
        labels = [f"[{f.severity.upper()}] {f.title}" for f in result.findings]
        idx = st.radio("Findings (ranked by severity)", range(len(labels)),
                       format_func=lambda i: labels[i])
        f = result.findings[idx]
        left, right = st.columns([5, 6])
        with left:
            st.markdown(f"<span class='ll-badge {SEV_CLASS[f.severity]}'>{f.severity.upper()}</span> "
                        f"&nbsp; **{f.id}**", unsafe_allow_html=True)
            st.markdown(f"### {f.title}")
            st.write(f.explanation)
            st.markdown(f"**Class:** {f.anomaly_class}  \n"
                        f"**Confidence:** {f.confidence_tier}  \n"
                        f"**Status:** {f.status.replace('_',' ')}  \n"
                        f"**Recommended action:** {f.recommended_action}")
        with right:
            st.caption("Click-to-source: each piece of evidence is highlighted on its document.")
            for ev in f.evidence:
                dn = result.documents[ev.doc_id]["display_name"]
                st.markdown(f"**{dn}** &mdash; {ev.snippet}")
                if ev.bbox:
                    img = highlight_crop(ev.page_image, ev.bbox.as_list())
                    st.image(img, use_container_width=True)
                else:
                    st.caption("(Document-level signal, no single region)")

with tab_fields:
    for did, fields in result.fields_by_doc.items():
        meta = result.documents[did]
        with st.expander(f"{meta['display_name']}  ({meta['doc_type']})", expanded=False):
            cols = st.columns([5, 4])
            with cols[0]:
                st.image(meta["page_image"], use_container_width=True)
            with cols[1]:
                if fields:
                    st.table([{"field": n, "value": fd.value, "conf": f"{fd.confidence:.0%}"}
                              for n, fd in fields.items()])
                else:
                    st.caption("No labelled fields extracted.")

with tab_graph:
    st.caption("Each extracted entity is a provenance-stamped node. Red dashed edges are "
               "cross-document conflicts.")
    out = Path(tempfile.gettempdir()) / "ll_graph.png"
    p = render_evidence_graph(result.graph, str(out), result.documents)
    if p:
        st.image(str(p), use_container_width=True)
    else:
        st.caption("No correlated entities to graph.")

with tab_audit:
    st.table(result.audit)

st.divider()
colA, colB = st.columns([1, 3])
with colA:
    if st.button("Generate dossier (PDF)"):
        out = Path(tempfile.gettempdir()) / "ledgerlens_dossier.pdf"
        generate_dossier(result, str(out))
        st.session_state.dossier = out.read_bytes()
with colB:
    if st.session_state.get("dossier"):
        st.download_button("Download investigation dossier", st.session_state.dossier,
                           file_name="investigation_dossier.pdf", mime="application/pdf")
