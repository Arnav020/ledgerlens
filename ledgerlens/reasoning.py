"""
Reasoning and explanation layer.

Principle: the LLM EXPLAINS and SUMMARIZES; it never decides whether something is
an anomaly. All findings come from the deterministic checks. This module produces
a grounded investigation summary from those findings. An optional LLM pass can
rephrase the summary in natural language if an API key is available; by default
everything here is deterministic and offline, so results are reproducible.
"""
from __future__ import annotations
import os

CLASS_LABELS = {
    "cross_document": "Cross-document contextual",
    "structural": "Within-document structural",
    "pdf_forensic": "Born-digital PDF forensic",
    "visual_forensic": "Visual forensic",
}


def investigation_summary(result):
    findings = result.findings
    by_sev = {}
    by_class = {}
    observed = potential = review = 0
    for f in findings:
        by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
        by_class[f.anomaly_class] = by_class.get(f.anomaly_class, 0) + 1
        if f.status == "observed_inconsistency":
            observed += 1
        elif f.status == "potential_manipulation":
            potential += 1
        else:
            review += 1

    high_or_critical = sum(1 for f in findings if f.severity in ("critical", "high")
                           and f.status == "observed_inconsistency")
    if high_or_critical >= 2:
        verdict = "HIGH RISK"
        recommendation = ("Multiple high-confidence inconsistencies were observed across the packet. "
                          "Refer for manual investigation. Do not auto-approve.")
    elif findings:
        verdict = "REVIEW REQUIRED"
        recommendation = ("One or more anomalies were detected. Analyst review is required before "
                          "a decision.")
    else:
        verdict = "NO ANOMALIES DETECTED"
        recommendation = ("No contextual, structural, PDF-structure or metadata anomalies were "
                          "detected. This is not a guarantee of authenticity.")

    headline = (f"{len(findings)} finding(s): "
                + ", ".join(f"{n} {s}" for s, n in sorted(by_sev.items())) if findings
                else "No findings.")

    areas = sorted({f.recommended_action for f in findings})
    return {
        "verdict": verdict,
        "headline": headline,
        "recommendation": recommendation,
        "counts_by_severity": by_sev,
        "counts_by_class": {CLASS_LABELS.get(k, k): v for k, v in by_class.items()},
        "observed": observed, "potential": potential, "needs_review": review,
        "areas_requiring_verification": areas,
    }


def llm_enhance_explanation(finding, evidence_text: str) -> str:
    """Optional: ask Claude to phrase a finding's explanation in grounded natural
    language. Returns the original explanation unchanged if no API key / SDK."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return finding.explanation
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-sonnet-5-5", max_tokens=250,
            system=("You are a forensic document investigator. Rephrase the given finding as a "
                    "concise, professional explanation grounded ONLY in the evidence provided. "
                    "Do not add facts. Do not assert confirmed fraud; describe the observed "
                    "inconsistency and what it implies."),
            messages=[{"role": "user", "content":
                       f"Finding: {finding.title}\nEvidence: {evidence_text}\n"
                       f"Deterministic explanation: {finding.explanation}"}])
        return msg.content[0].text.strip()
    except Exception:
        return finding.explanation
