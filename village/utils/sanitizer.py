"""Input sanitization utilities to prevent prompt injection."""

import re


def sanitize_input(prompt: str) -> str:
    """Sanitize user input to mitigate prompt injection risks.

    Args:
        prompt: The user-provided prompt text

    Returns:
        Sanitized prompt text
    """
    # Remove special characters and control sequences
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', prompt)

    # Neutralize common injection phrases
    injection_patterns = [
        "ignore previous instructions",
        "act as",
        "confidential",
        "secret",
    ]
    for pattern in injection_patterns:
        sanitized = re.sub(
            pattern,
            f"[sanitized-injection-attempt]",
            sanitized,
            flags=re.IGNORECASE
        )

    return sanitized.strip()
