"""Small, deterministic gate for choosing between two already-generated replies."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from emotion_parser import EMPTY_REPLY_FALLBACK, ParsedAssistantReply
from memory_recall_guard import contains_false_unknown_claim, is_question_reflection
from repetition_guard import assess_recent_repetition


@dataclass(frozen=True)
class CandidateCheck:
    critical_defects: int
    repetitive: bool
    false_unknown: bool
    question_reflection: bool

    @property
    def rank(self) -> tuple[int, int]:
        return self.critical_defects, int(self.repetitive)


def check_candidate(reply: ParsedAssistantReply, latest_user_text: str,
                    previous_assistant_texts: Sequence[str],
                    memory_recall: bool) -> CandidateCheck:
    text = reply.text.strip()
    false_unknown = memory_recall and contains_false_unknown_claim(text)
    reflection = memory_recall and is_question_reflection(text, latest_user_text)
    empty_or_fallback = not text or text == EMPTY_REPLY_FALLBACK
    repetitive = assess_recent_repetition(
        text, previous_assistant_texts, latest_user_text
    ).suspicious
    return CandidateCheck(
        int(false_unknown) + int(reflection) + int(empty_or_fallback),
        repetitive, false_unknown, reflection,
    )


def choose_retry_candidate(first: ParsedAssistantReply, second: ParsedAssistantReply,
                           latest_user_text: str, previous_assistant_texts: Sequence[str],
                           memory_recall: bool) -> tuple[ParsedAssistantReply, str]:
    """Prefer a strictly cleaner retry; ties preserve the first candidate."""
    first_check = check_candidate(first, latest_user_text, previous_assistant_texts, memory_recall)
    second_check = check_candidate(second, latest_user_text, previous_assistant_texts, memory_recall)
    if second_check.rank < first_check.rank:
        return second, "retry_reduced_observable_defects"
    return first, "first_preserved_retry_not_better"
