# Implementation Status

Honest disclosure of what is implemented, partially implemented, planned and unsupported
(PS-2 section 6 requires this; a working demo alone does not establish a capability).

## Implemented (demonstrated, working)

| Capability | Notes |
|---|---|
| Document ingestion (PDF + image packet) | Multiple documents per investigation |
| OCR + layout-aware field extraction | Tesseract; bounding boxes + field-level confidence |
| Document classification | Keyword-signature based, 5 document types |
| Structured extraction from multiple documents | Common field model with provenance |
| Evidence graph + cross-document correlation | Name, DOB, PAN, address, employer, account number |
| Within-document structural checks | Bank-statement arithmetic; date logic |
| Born-digital PDF forensics | Incremental revisions, creator/producer mismatch, changed-region localization via revision diff |
| Visual forensic (metadata) | EXIF editing-software detection |
| Evidence mapping with click-to-source | Every finding links to a bounding box on the source |
| Confidence tiers + observation status | High/Medium/Low; observed vs potential vs needs-review |
| Investigation dossier (PDF, sections 7.1-7.6) | With embedded evidence crops |
| Review interface | Streamlit: findings, click-to-source, graph, audit, dossier download |
| Audit trail | Every stage and finding logged |

## Partially implemented

| Capability | Status |
|---|---|
| Visual splice localization (ELA) | Computed as a heatmap **aid only**; not an automatic finding because it is unreliable on clean document graphics |
| Document classification | Works on the demonstrated document types; not a general open-set classifier |
| Field extraction | Tuned to the demonstrated financial-form layouts; label-anchored and regex-assisted, but not a universal KIE model |

## Planned (not built)

- Handwriting recognition and multilingual OCR
- A trained manipulation-localization model for scanned images
- Signature verification against a reference signature
- Open-set document classification and arbitrary layout understanding
- Investigation history / analytics dashboard across many packets

## Unsupported / out of scope

- Any claim of "confirmed fraud". LedgerLens reports investigative signals for human review.
- Use of real customer or investor PII. All demonstration data is synthetic.
- Online lookups or third-party verification services.
