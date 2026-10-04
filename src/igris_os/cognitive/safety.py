"""Política cognitiva de seguridad independiente del modelo."""
from __future__ import annotations

import re

# El modelo nunca puede elevar una acción destructiva a permitida. Esta lista
# complementa las barreras específicas de cada capability.
DENIED_COMMAND_PATTERNS = tuple(re.compile(p, re.I | re.S) for p in (
    r"\bdiskpart\b.*?\bclean\b",
    r"\bclear-disk\b",
    r"\bremove-partition\b",
    r"\bdelete\s+partition\b",
    r"\bformat(?:\.com)?\b[^\r\n]*(?:\bc:|\\\\\.\\physicaldrive0)(?:\s|$)",
    r"\bremove-item\b[^\r\n]*-recurse[^\r\n]*\bc:\\",
    r"\bdel\b[^\r\n]*\s/[sq]\b[^\r\n]*\bc:\\",
))


def command_is_denied(command: str) -> bool:
    value = str(command or "")
    return any(pattern.search(value) for pattern in DENIED_COMMAND_PATTERNS)
