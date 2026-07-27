from __future__ import annotations
import re
_PATTERNS=[
 re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+"),
 re.compile(r"(?i)\b(api[_-]?key|token|password|secret)\s*[=:]\s*[^\s,;]+"),
 re.compile(r"\b(?:sk|pk)-[A-Za-z0-9_-]{12,}\b"),
]
def redact(value: str) -> str:
    text=str(value)
    text=_PATTERNS[0].sub(r"\1[REDACTED]",text)
    text=_PATTERNS[1].sub(lambda m:f"{m.group(1)}=[REDACTED]",text)
    return _PATTERNS[2].sub("[REDACTED]",text)
