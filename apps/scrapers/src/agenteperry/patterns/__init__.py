"""Detection patterns module."""

from agenteperry.patterns.queries import (
    PATTERNS,
    DetectionPattern,
    get_pattern,
    list_patterns,
    patterns_by_severity,
)

__all__ = [
    "DetectionPattern",
    "PATTERNS",
    "get_pattern",
    "list_patterns",
    "patterns_by_severity",
]
