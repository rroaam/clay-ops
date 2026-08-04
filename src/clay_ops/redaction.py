from __future__ import annotations
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# Pattern-based redactions
_PATTERNS=[
 re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+"),
 re.compile(r"(?i)\b(api[_-]?key|token|password|secret)\s*[=:]\s*[^\s,;]+"),
 re.compile(r"\b(?:sk|pk)-[A-Za-z0-9_-]{12,}\b"),
 # Slack-specific token patterns
 re.compile(r"\bxo[xbasp]-[A-Za-z0-9_-]+-[A-Za-z0-9_-]+(?:-[A-Za-z0-9_-]+)?\b"),
]

# Query parameters that commonly contain secrets
SENSITIVE_QUERY_PARAMS = {
    "token", "access_token", "api_key", "apikey", "secret",
    "Signature", "Expires", "X-Amz-Algorithm", "X-Amz-Credential",
    "X-Amz-Signature", "X-Amz-SignedHeaders",
}

def redact(value: str) -> str:
    """Redact secrets from a string value."""
    text = str(value)
    # Apply pattern-based redactions
    text = _PATTERNS[0].sub(r"\1[REDACTED]", text)
    text = _PATTERNS[1].sub(lambda m: f"{m.group(1)}=[REDACTED]", text)
    text = _PATTERNS[2].sub("[REDACTED]", text)
    # Redact Slack-like URLs with sensitive query params
    text = _redact_url_secrets(text)
    return text

def _redact_url_secrets(text: str) -> str:
    """Find URLs in text and redact sensitive query parameters."""
    # Simple URL detection — find http(s) URLs
    url_pattern = re.compile(r'https?://[^\s<>"\']+')
    def redact_url(match):
        url = match.group(0)
        try:
            parsed = urlparse(url)
            if parsed.query:
                params = parse_qs(parsed.query, keep_blank_values=True)
                redacted_params = {
                    k: ["[REDACTED]"] if k in SENSITIVE_QUERY_PARAMS else v
                    for k, v in params.items()
                }
                new_query = urlencode(redacted_params, doseq=True)
                new_url = urlunparse((
                    parsed.scheme, parsed.netloc, parsed.path,
                    parsed.params, new_query, parsed.fragment
                ))
                return new_url
        except Exception:
            pass
        return url
    return url_pattern.sub(redact_url, text)
