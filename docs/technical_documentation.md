# LedgerLens - Technical Documentation

## 1. Pipeline overview

`ledgerlens/pipeline.py:run(packet_dir)` executes:

1. **Ingestion** (`_discover`): finds the documents in a packet, assigns a stable `doc_id`
   and display name, and keeps both the original file (PDF or image) and a rasterized page
   image (for OCR, display and highlighting).
2. **Extraction** (`extract.py:extract_document`): OCR + layout-aware field reading.
3. **Evidence graph** (`graph.py:detect_contradictions`): builds provenance-stamped entity
   nodes and detects cross-document contradictions generically.
4. **Checks** (`checks.py:ALL_CHECKS`): income reconciliation, date logic, statement
   arithmetic, born-digital PDF forensics, visual signals.
5. **Ranking + audit**: findings are sorted by severity; every stage is logged.

The result (`InvestigationResult`) carries documents, extracted fields, the graph, ranked
findings and the audit trail, and serializes to JSON.

## 2. Extraction (`extract.py`)

- **OCR**: Tesseract via `pytesseract.image_to_data`, keeping each word's bounding box and
  confidence.
- **Row grouping** (`group_rows`): words are regrouped into visual rows by vertical overlap.
  The merge tolerance is based on the *smaller* of the two heights with an absolute cap, so a
  single oversized OCR artifact cannot merge distant lines. This makes columnar label/value
  form layouts parse correctly.
- **Field reading** (`find_field`): for each field's label, the value is taken from the
  tokens to the right on the same row, or, for stacked layouts (ID cards), from the row
  below. Optional regex (`PAN`, dates) disambiguates and skips title-row false matches.
- **Classification** (`classify`): document type from OCR keyword signatures.
- **Normalization**: amounts to digits, dates to `DD-MM-YYYY`, PAN to the canonical pattern.
- **Ledger parsing** (`parse_bank_ledger`): born-digital statements are parsed from the PDF
  text layer (PyMuPDF `get_text("words")`), grouped into visual rows by y-position, to get
  the opening balance, the transaction amounts and the printed closing balance.

Extraction never reads values from the dataset ground truth; it runs real OCR / real PDF
text extraction.

## 3. Evidence graph (`graph.py`)

Each extracted field for a correlated entity (name, DOB, PAN, address, employer, account
number) becomes a node carrying `{value, doc_id, confidence}`. For each entity appearing in
more than one document, values are compared with an entity-appropriate normalizer
(exact, alphanumeric, digits, name, address). Documents are bucketed by normalized value;
more than one bucket means a cross-document contradiction, emitted as a `Finding` with an
`Evidence` pointer (doc, bounding box, snippet) for every conflicting value.

## 4. Checks (`checks.py`)

- **Income reconciliation**: compares the application's declared monthly income against the
  salary-slip net pay and the largest positive bank credit; flags a gap above 15 percent.
- **Date logic**: flags an identity issue date later than the application date.
- **Statement arithmetic**: compares the printed closing balance with opening plus the sum
  of transactions; any mismatch is flagged and the printed balance region is the evidence.
- **PDF forensics**: counts `%%EOF` markers (incremental-update revisions), compares PDF
  creator vs producer, and, when there is a prior revision, **reconstructs and renders the
  prior revision, diffs it against the current render, and localizes the changed region**.
  This is deterministic file-structure evidence, not a visual guess.
- **Visual forensics**: EXIF editing-software tag (medium confidence). ELA is computed as a
  heatmap aid only; it is **not** turned into an automatic finding because on clean document
  graphics it is dominated by text edges and does not discriminate reliably.

## 5. Confidence and status (`model.py`)

Confidence tiers are set by the *class* of check, never by a guessed probability:
High (deterministic contradiction / arithmetic / PDF revision), Medium (metadata),
Low (visual). Status separates `observed_inconsistency`, `potential_manipulation` and
`needs_human_review`.

## 6. Reasoning (`reasoning.py`)

`investigation_summary` produces a deterministic verdict (HIGH RISK / REVIEW REQUIRED /
NO ANOMALIES) with counts and recommended actions. `llm_enhance_explanation` optionally
rephrases a finding with Claude, grounded only in the provided evidence, and falls back to
the deterministic explanation when no API key is present.

## 7. Dossier (`dossier.py`)

A reportlab PDF with PS-2 sections 7.1 - 7.6: document overview, extracted information with
confidence, contextual analysis, visual forensic findings, an evidence-and-traceability
table, and the investigation summary. Each finding embeds highlighted evidence crops cut
from the source page image.

## 8. Reproducibility

Fixed random seed in the dataset generator; pinned dependencies in `requirements.txt`;
deterministic, offline pipeline; one-command regeneration (`run_investigation.py`). The only
non-deterministic element, the optional LLM phrasing, is off by default.
