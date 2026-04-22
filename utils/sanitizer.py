"""
utils/sanitizer.py

LogSanitizer: A logging.Filter that redacts sensitive credential patterns
from log messages before they are written to any handler (file or console).

Architecture rule: filter() must always return True — sanitizer mutates
content only, never drops records.
"""
import re
import logging
from typing import Pattern

# Compile once at module level for thread-safety and performance.
# Covers the most common credential leak vectors in this project.
_SENSITIVE_PATTERNS: list[tuple[Pattern, str]] = [
    # Key=value style: sessionid=abc123, access_token=xyz, client_secret=XYZ
    (
        re.compile(
            r'((?:sessionid|access_token|refresh_token|client_secret|client_id|'
            r'api_key|bearer|authorization|cookie|a_bogus)[=:\s]+)([^\s&"\'<>,;]+)',
            re.IGNORECASE,
        ),
        r'\1***REDACTED***',
    ),
    # Raw Bearer token headers: "Bearer ey..."
    (
        re.compile(r'(Bearer\s+)([A-Za-z0-9\-._~+/]+=*)', re.IGNORECASE),
        r'\1***REDACTED***',
    ),
    # Long alphanumeric strings that look like raw tokens (>= 32 chars)
    (
        re.compile(r'(?<![a-zA-Z0-9])([A-Za-z0-9_\-]{32,})(?![a-zA-Z0-9])'),
        lambda m: '***REDACTED***' if _looks_like_token(m.group(1)) else m.group(0),
    ),
]


def _looks_like_token(s: str) -> bool:
    """Heuristic: only redact long strings with high character entropy (mixed case + digits)."""
    has_upper = any(c.isupper() for c in s)
    has_lower = any(c.islower() for c in s)
    has_digit = any(c.isdigit() for c in s)
    return has_upper and has_lower and has_digit


def sanitize_message(message: str) -> str:
    """Apply all sensitive patterns to a plain string and return sanitized version."""
    for pattern, replacement in _SENSITIVE_PATTERNS:
        if callable(replacement):
            message = pattern.sub(replacement, message)
        else:
            message = pattern.sub(replacement, message)
    return message


class LogSanitizer(logging.Filter):
    """
    Logging filter that redacts sensitive credential strings from log records.

    Attach this filter to any logging.Handler to ensure tokens/cookies are
    never written to disk or stdout in plaintext.

    Usage:
        handler.addFilter(LogSanitizer())
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Interpolate args into message first (safe even if args is empty/None)
        try:
            message = record.getMessage()
        except Exception:
            # If interpolation itself fails, leave the record untouched
            return True

        sanitized = sanitize_message(message)

        # Mutate in-place: set pre-formatted message and clear args so handlers
        # don't re-interpolate and accidentally expose the raw values again.
        record.msg = sanitized
        record.args = None

        return True
