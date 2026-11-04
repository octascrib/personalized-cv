"""Build a private adaptation report, kept outside version control."""

from datetime import datetime

from .models import GeneratedCV


def adaptation_report(cv: GeneratedCV, metadata: dict[str, str], model: str,
                      generated_at: datetime, verification: str, provider: str = "openai") -> str:
    lines = ["# CV adaptation report", "",
             f"- Template: {metadata['id']} ({metadata['version']})",
             f"- Provider: {provider}", f"- Model: {model}", f"- Generated at: {generated_at.isoformat(timespec='seconds')}",
             f"- Document language: {cv.language}", f"- Verification: {verification}",
             "- Visual inspection: pending human review; not automatically verified.",
             "", "## Requirements", ""]
    for item in cv.requirements:
        lines.extend((f"### {item.requirement}", "",
                      f"Priority: {item.priority}; evidence status: {item.status}", "", item.note, ""))
        lines.extend(f"> {quote.replace(chr(10), chr(10) + '> ')}" for quote in item.profile_quotes)
        lines.append("")
    lines.extend(("## Claim provenance", ""))
    for claim in cv.claims():
        lines.extend((f"### {claim.text}", ""))
        lines.extend(f"> {quote.replace(chr(10), chr(10) + '> ')}" for quote in claim.profile_quotes)
        lines.append("")
    for heading, items in (("Wording changes", cv.wording_changes),
                           ("Warnings", cv.warnings),
                           ("Clarification questions", cv.clarification_questions)):
        lines.extend((f"## {heading}", ""))
        lines.extend(f"- {item}" for item in items)
        lines.append("")
    lines.extend(("## Review limits", "",
                  "Exact source quotations are checked locally. This does not establish that every",
                  "paraphrase is semantically supported or that all job requirements were identified.",
                  "Review the CV and evidence before submitting. No ATS acceptance is guaranteed.", ""))
    return "\n".join(lines)
