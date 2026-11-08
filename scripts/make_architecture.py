"""Render the LedgerLens architecture diagram to docs/architecture.png."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

NAVY = "#16365e"; BLUE = "#2b6cb0"; TEAL = "#2c7a7b"
AMBER = "#b7791f"; RED = "#c0291f"; GREY = "#5b6670"; LIGHT = "#eef2f7"

OUT = Path(__file__).resolve().parent.parent / "docs" / "architecture.png"
OUT.parent.mkdir(parents=True, exist_ok=True)


def box(ax, x, y, w, h, text, fc, tc="white", fs=10, bold=True):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                       linewidth=0, facecolor=fc)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            color=tc, fontsize=fs, fontweight="bold" if bold else "normal", wrap=True)


def arrow(ax, x0, y0, x1, y1, color=NAVY):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>",
                                 mutation_scale=14, linewidth=1.6, color=color))


fig, ax = plt.subplots(figsize=(13, 7.2))
ax.set_xlim(0, 13); ax.set_ylim(0, 7.2); ax.axis("off")

ax.text(0.2, 6.9, "LedgerLens", fontsize=20, fontweight="bold", color=NAVY)
ax.text(0.2, 6.55, "Evidence-driven cross-document forensic investigation",
        fontsize=11, color=GREY)

# Row 1: ingestion -> extraction -> graph
box(ax, 0.2, 5.2, 2.2, 0.9, "Document\nIngestion\n(PDF / image packet)", BLUE)
box(ax, 2.8, 5.2, 2.4, 0.9, "OCR + Layout\nField Extraction\n(bbox + confidence)", BLUE)
box(ax, 5.6, 5.2, 2.4, 0.9, "Classification\n(document type)", BLUE, fs=9)
box(ax, 8.4, 5.2, 2.5, 0.9, "Evidence Graph\nprovenance-stamped\nentity nodes", NAVY)
arrow(ax, 2.4, 5.65, 2.8, 5.65); arrow(ax, 5.2, 5.65, 5.6, 5.65)
arrow(ax, 8.0, 5.65, 8.4, 5.65)

# Row 2: deterministic checks
ax.text(0.2, 4.55, "Deterministic checks (the LLM never decides here)",
        fontsize=10.5, fontweight="bold", color=NAVY)
checks = [
    ("Cross-document\ncontextual\n(name, DOB, PAN,\naddress, income)", TEAL),
    ("Within-document\nstructural\n(ledger arithmetic,\ndate logic)", TEAL),
    ("Born-digital PDF\nforensics\n(revisions, metadata,\nchanged-region)", AMBER),
    ("Visual signals\n(EXIF, ELA aid)\nlow confidence,\nneeds review", GREY),
]
for i, (t, c) in enumerate(checks):
    box(ax, 0.2 + i * 3.25, 3.1, 2.9, 1.25, t, c, fs=8.6)
    arrow(ax, 9.6, 5.2, 1.65 + i * 3.25, 4.35, color="#9aa6b2")

# Row 3: reasoning -> outputs
box(ax, 0.2, 1.5, 3.3, 1.0, "Reasoning layer\nLLM EXPLAINS findings,\ngrounded in evidence\n(optional, offline fallback)", BLUE, fs=9)
box(ax, 4.0, 1.5, 3.6, 1.0, "Investigation Dossier (PDF)\nsections 7.1 - 7.6\nembedded evidence crops", NAVY, fs=9)
box(ax, 8.1, 1.5, 2.8, 1.0, "Review Interface\nclick-to-source,\nevidence graph", NAVY, fs=9)
for i in range(4):
    arrow(ax, 1.65 + i * 3.25, 3.1, 1.85, 2.5, color="#9aa6b2")
arrow(ax, 3.5, 2.0, 4.0, 2.0); arrow(ax, 7.6, 2.0, 8.1, 2.0)

# audit trail band
box(ax, 0.2, 0.5, 10.7, 0.6, "Audit trail  -  every ingestion, extraction, finding and evidence link is logged and traceable", LIGHT, tc=NAVY, fs=9.5)

fig.tight_layout()
fig.savefig(OUT, dpi=150, bbox_inches="tight", facecolor="white")
print("wrote", OUT)
