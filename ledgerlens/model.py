"""Core data structures shared across the pipeline."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class BBox:
    """Bounding box in pixels of the rendered page image (origin top-left)."""
    x: int
    y: int
    w: int
    h: int

    def as_list(self):
        return [self.x, self.y, self.w, self.h]


@dataclass
class Field:
    """One extracted field with full provenance."""
    doc_id: str
    doc_type: str
    name: str                 # canonical field name, e.g. "date_of_birth"
    label: str                # the label text found on the page
    value: str                # OCR-read value (normalized where noted)
    raw_value: str            # value exactly as OCR returned it
    confidence: float         # OCR confidence 0..1 (field-level, min of tokens)
    bbox: Optional[BBox]      # location on the page image
    page_image: str           # path to the rendered page image

    def to_dict(self):
        d = asdict(self)
        d["bbox"] = self.bbox.as_list() if self.bbox else None
        return d


@dataclass
class Evidence:
    """A pointer back to the exact place a finding came from."""
    doc_id: str
    page_image: str
    bbox: Optional[BBox]
    snippet: str              # the value/text that is the evidence
    field_name: Optional[str] = None

    def to_dict(self):
        d = asdict(self)
        d["bbox"] = self.bbox.as_list() if self.bbox else None
        return d


# Confidence tiers are set by the CLASS of check, not by a guessed probability.
TIER_HIGH = "high"       # deterministic contradiction (exact value conflict, arithmetic break, PDF revision)
TIER_MEDIUM = "medium"   # structural / metadata signal
TIER_LOW = "low"         # visual similarity / heatmap signal -> needs human review

# Observation status separates what was OBSERVED from what is only POTENTIAL.
STATUS_OBSERVED = "observed_inconsistency"      # the values genuinely disagree / math is wrong
STATUS_POTENTIAL = "potential_manipulation"     # a signal suggests manipulation, not proven
STATUS_NEEDS_REVIEW = "needs_human_review"


@dataclass
class Finding:
    id: str
    title: str
    anomaly_class: str              # cross_document | structural | pdf_forensic | visual_forensic
    severity: str                   # critical | high | medium | low
    confidence_tier: str            # TIER_*
    status: str                     # STATUS_*
    documents: list                 # list of doc_id
    explanation: str                # grounded, plain-language reasoning
    evidence: list = field(default_factory=list)   # list[Evidence]
    recommended_action: str = ""

    def to_dict(self):
        d = asdict(self)
        d["evidence"] = [e.to_dict() for e in self.evidence]
        return d
