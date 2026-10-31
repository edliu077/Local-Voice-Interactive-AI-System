"""Legacy reply API: natural text cleanup with neutral UI compatibility only."""
from __future__ import annotations

from dataclasses import dataclass
import re
from reply_text import clean_reply_text

ALLOWED_EMOTIONS = frozenset({"neutral", "love", "sad", "excited"})
DEFAULT_EMOTION = "neutral"
MAX_CLEAN_TEXT_CHARS = 300
EMPTY_REPLY_FALLBACK = "我刚刚走神了一下，你再说一次好吗？"
_EMOJI_PRESENTATION = re.compile(
    "[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\U000E0020-\U000E007F"
    "\u2600-\u26FF\u2700-\u27BF\u200D\u20E3\uFE0E-\uFE0F]"
)


@dataclass(frozen=True)
class ParsedAssistantReply:
    text: str
    emotion: str = DEFAULT_EMOTION


def parse_assistant_reply(raw_completion: str) -> ParsedAssistantReply:
    """No header is required or interpreted; old metadata is merely discarded."""
    text = clean_reply_text(raw_completion)
    if not text:
        # An internal parse failure must not be committed as a chat message.
        raise ValueError("Assistant reply is empty after control cleanup")
    return ParsedAssistantReply(text=text[:MAX_CLEAN_TEXT_CHARS].rstrip())


def refine_emotion(parsed_emotion: str, clean_text: str) -> str:
    """Compatibility shim; no generated tag or inferred sentiment drives the UI."""
    return DEFAULT_EMOTION


def sanitize_tts_text(text: str) -> str:
    """Keep spoken output clean; retain the existing decorative emoji filter."""
    speech_text = _EMOJI_PRESENTATION.sub("", clean_reply_text(text))
    return re.sub(r"[ \t]{2,}", " ", speech_text).strip()
