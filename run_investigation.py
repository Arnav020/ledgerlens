"""
LedgerLens command-line investigation.

Usage:
    python run_investigation.py --packet dataset/manipulated --out samples/sample_dossier.pdf

Runs the full pipeline on a packet directory, prints the ranked findings, and
writes an investigation dossier (PDF) plus a machine-readable result (JSON).
Deterministic and offline.
"""
import argparse
import json
from pathlib import Path

from ledgerlens.pipeline import run
from ledgerlens.reasoning import investigation_summary
from ledgerlens.dossier import generate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--packet", default="dataset/manipulated")
    ap.add_argument("--out", default="samples/sample_dossier.pdf")
    args = ap.parse_args()

    result = run(args.packet)
    summary = investigation_summary(result)

    print(f"\nPacket: {args.packet}")
    print(f"Verdict: {summary['verdict']}  ({summary['headline']})")
    print("-" * 72)
    for f in result.findings:
        print(f" [{f.severity:8s} | {f.confidence_tier:6s} | {f.status:22s}] {f.title}")
    print("-" * 72)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    generate(result, str(out))
    json_out = out.with_suffix(".json")
    json_out.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    print(f"Dossier : {out}")
    print(f"Result  : {json_out}")


if __name__ == "__main__":
    main()
