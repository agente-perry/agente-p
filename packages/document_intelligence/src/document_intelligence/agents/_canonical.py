"""Shared utilities: canonical cluster catalog loader, accent-fold matcher."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import yaml

_CATALOG_PATH = Path(__file__).resolve().parent.parent / "flags" / "cluster_catalog.yaml"
_CLUSTER_FLAG_MAP_PATH = Path(__file__).resolve().parent.parent / "flags" / "cluster_flag_map.yaml"
_PLANNER_QUERIES_PATH = Path(__file__).resolve().parent.parent / "flags" / "planner_queries.yaml"
_INTENT_MAP_PATH = Path(__file__).resolve().parent.parent / "flags" / "intent_map.yaml"

OTHERS_LABEL = "Otros"


@dataclass(frozen=True)
class ClusterDefinition:
    label: str
    keywords: tuple[str, ...]


def normalize(text: str) -> str:
    """Upper-case + strip accents for keyword matching.

    Performs NFKD decomposition and strips combining characters BEFORE
    upper-casing.  This ordering is critical for 'ñ': if upper-cased first,
    ñ→Ñ which then NFKD-decomposes to 'N'+tilde, producing a second 'N'
    alongside the original base 'n' in the same word.
    By decomposing first (ñ→'n'+tilde, Ñ→'N'+tilde), stripping the tilde,
    and only then upper-casing, 'ñ' contributes a single 'N' to the
    result regardless of its original case.
    """
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.upper()


@lru_cache(maxsize=1)
def load_cluster_catalog() -> tuple[ClusterDefinition, ...]:
    raw_any: Any = yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8")) or []
    raw = cast(list[dict[str, Any]], raw_any if isinstance(raw_any, list) else [])
    return tuple(
        ClusterDefinition(
            label=str(entry["label"]),
            keywords=tuple(normalize(k) for k in cast(list[str], entry["keywords"])),
        )
        for entry in raw
    )


@lru_cache(maxsize=1)
def load_cluster_flag_map() -> dict[str, tuple[str, ...]]:
    raw_any: Any = yaml.safe_load(_CLUSTER_FLAG_MAP_PATH.read_text(encoding="utf-8")) or {}
    raw = cast(dict[str, list[str]], raw_any if isinstance(raw_any, dict) else {})
    return {flag: tuple(clusters) for flag, clusters in raw.items()}


@lru_cache(maxsize=1)
def load_planner_queries() -> dict[str, tuple[str, ...]]:
    raw_any: Any = yaml.safe_load(_PLANNER_QUERIES_PATH.read_text(encoding="utf-8")) or {}
    raw = cast(dict[str, list[str]], raw_any if isinstance(raw_any, dict) else {})
    return {flag: tuple(queries) for flag, queries in raw.items()}


def match_cluster(text: str | None) -> str:
    """Return the canonical cluster label that best matches ``text`` or ``"Otros"``."""
    if not text:
        return OTHERS_LABEL
    haystack = normalize(text)
    for definition in load_cluster_catalog():
        for keyword in definition.keywords:
            if keyword in haystack:
                return definition.label
    return OTHERS_LABEL


def canonical_labels() -> tuple[str, ...]:
    return tuple(d.label for d in load_cluster_catalog()) + (OTHERS_LABEL,)


@dataclass(frozen=True)
class IntentDefinition:
    name: str
    trigger_phrases: tuple[str, ...]  # already normalized
    expands_to: tuple[str, ...]


@lru_cache(maxsize=1)
def load_intent_map() -> tuple[IntentDefinition, ...]:
    """Load intent → flag-expansion mapping from ``flags/intent_map.yaml``.

    Trigger phrases are normalized (accent-folded, uppercased) at load time so
    matching against a normalized question is a cheap substring check.
    """
    if not _INTENT_MAP_PATH.exists():
        return ()
    raw_any: Any = yaml.safe_load(_INTENT_MAP_PATH.read_text(encoding="utf-8")) or {}
    raw = cast(dict[str, dict[str, Any]], raw_any if isinstance(raw_any, dict) else {})
    definitions: list[IntentDefinition] = []
    for name, payload in raw.items():
        triggers = cast(list[str], payload.get("trigger_phrases", []) or [])
        flags = cast(list[str], payload.get("expands_to", []) or [])
        definitions.append(
            IntentDefinition(
                name=str(name),
                trigger_phrases=tuple(normalize(t) for t in triggers if t),
                expands_to=tuple(flags),
            )
        )
    return tuple(definitions)


def match_intents(question: str) -> tuple[IntentDefinition, ...]:
    """Return the intents whose trigger phrases appear in ``question``.

    Matching is substring on the normalized form of the question, so accents
    and casing in the user input are irrelevant.
    """
    if not question:
        return ()
    haystack = normalize(question)
    matched: list[IntentDefinition] = []
    for intent in load_intent_map():
        if any(trigger and trigger in haystack for trigger in intent.trigger_phrases):
            matched.append(intent)
    return tuple(matched)


def expand_intents_to_flags(question: str) -> tuple[str, ...]:
    """Return the union of flag codes triggered by the question's intents."""
    seen: list[str] = []
    for intent in match_intents(question):
        for code in intent.expands_to:
            if code and code not in seen:
                seen.append(code)
    return tuple(seen)
