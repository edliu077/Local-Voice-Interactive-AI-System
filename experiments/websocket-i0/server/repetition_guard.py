"""Dependency-free conservative repetition detection for assistant replies."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Mapping, Sequence
import unicodedata


MIN_NORMALIZED_LENGTH = 15
SIMILARITY_THRESHOLD = 0.84
RECENT_ASSISTANT_REPETITION_WINDOW = 4
_EXPLICIT_REPEAT_REQUESTS = (
    "再说一遍",
    "重复一下",
    "你刚才说什么",
    "再讲一次",
    "请重复刚才的话",
)


@dataclass(frozen=True)
class RepetitionAssessment:
    suspicious: bool
    similarity: float
    explicit_repeat_request: bool
    matched_index: int | None = None


def _normalize_for_comparison(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text)).casefold()
    return "".join(character for character in normalized if character.isalnum())


def is_explicit_repeat_request(latest_user_text: str) -> bool:
    normalized_user = _normalize_for_comparison(latest_user_text)
    return any(
        _normalize_for_comparison(request) in normalized_user
        for request in _EXPLICIT_REPEAT_REQUESTS
    )


def assess_repetition(
    candidate_text: str,
    previous_assistant_text: str | None,
    latest_user_text: str,
) -> RepetitionAssessment:
    previous = [] if previous_assistant_text is None else [previous_assistant_text]
    return assess_recent_repetition(candidate_text, previous, latest_user_text)


def assess_recent_repetition(
    candidate_text: str,
    previous_assistant_texts: Sequence[str],
    latest_user_text: str,
) -> RepetitionAssessment:
    """Compare a candidate with a bounded newest-first assistant reply window."""
    explicit_repeat = is_explicit_repeat_request(latest_user_text)
    if explicit_repeat or not previous_assistant_texts:
        return RepetitionAssessment(False, 0.0, explicit_repeat)

    candidate = _normalize_for_comparison(candidate_text)
    maximum_similarity = 0.0
    matched_index: int | None = None
    for index, previous_text in enumerate(previous_assistant_texts):
        previous = _normalize_for_comparison(previous_text)
        if min(len(candidate), len(previous)) < MIN_NORMALIZED_LENGTH:
            continue
        similarity = SequenceMatcher(None, candidate, previous, autojunk=False).ratio()
        if similarity > maximum_similarity:
            maximum_similarity = similarity
            matched_index = index

    return RepetitionAssessment(
        maximum_similarity >= SIMILARITY_THRESHOLD,
        maximum_similarity,
        False,
        matched_index,
    )


def is_suspicious_repetition(
    candidate_text: str,
    previous_assistant_text: str | None,
    latest_user_text: str,
) -> bool:
    return assess_repetition(candidate_text, previous_assistant_text, latest_user_text).suspicious


def latest_assistant_text(history: Sequence[Mapping[str, str]]) -> str | None:
    recent = recent_assistant_texts(history, limit=1)
    return recent[0] if recent else None


def recent_assistant_texts(
    history: Sequence[Mapping[str, str]],
    limit: int = RECENT_ASSISTANT_REPETITION_WINDOW,
) -> list[str]:
    """Return up to ``limit`` non-empty assistant replies, newest first."""
    if limit <= 0:
        return []
    recent: list[str] = []
    for message in reversed(history):
        if message.get("role") == "assistant":
            text = str(message.get("content", "")).strip()
            if text:
                recent.append(text)
                if len(recent) >= limit:
                    break
    return recent
