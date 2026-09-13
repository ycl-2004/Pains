"""Best-effort removal of obvious sensitive strings before storage/model submission."""

import re


def redact(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email removed]", text)
    text = re.sub(r"\b(?:sk-[\w-]{12,}|gh[pousr]_[\w]{20,}|github_pat_[\w]{20,})\b", "[token removed]", text)
    text = re.sub(r"(?i)(authorization\s*[:=]\s*bearer\s+)\S+", r"\1[token removed]", text)
    return text
