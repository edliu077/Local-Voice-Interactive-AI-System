"""Dependency-free cleanup shared by WS replies and the legacy LLM client."""
from __future__ import annotations
import re

_THINK_TOKEN = re.compile(r"</?think\s*>", re.IGNORECASE)
_EMOTION_TAG = re.compile(r"</?emotion\s*:[^<>\r\n]*>", re.IGNORECASE)
_BARE_CONTROL_LINE = re.compile(
    r"(?im)^[ \t]*<?/?emotion:(?:neutral|love|sad|excited)>?[ \t]*$"
)
_BARE_INLINE_HEADER = re.compile(
    r"\A\s*emotion:(?:neutral|love|sad|excited)>[ \t]*", re.IGNORECASE
)


def clean_reply_text(raw: str) -> str:
    """Remove complete think blocks and metadata, preserving surrounding prose.

    Nested complete think blocks are removed as a unit. For unmatched tokens
    only the token is removed: guessing where an unclosed block's final answer
    begins would silently delete usable text. This ambiguity remains a risk.
    """
    text = str(raw)
    spans: list[tuple[int, int]] = []
    depth = 0
    start = 0
    for token in _THINK_TOKEN.finditer(text):
        if not token.group().startswith("</"):
            if depth == 0:
                start = token.start()
            depth += 1
        elif depth:
            depth -= 1
            if depth == 0:
                spans.append((start, token.end()))
    for start, end in reversed(spans):
        text = text[:start] + text[end:]
    text = _THINK_TOKEN.sub("", text)
    text = _EMOTION_TAG.sub("", text)
    text = _BARE_CONTROL_LINE.sub("", text)
    text = _BARE_INLINE_HEADER.sub("", text)
    text = re.sub(r"```[A-Za-z0-9_+-]*\s*(.*?)```", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", text)
    text = re.sub(r"(?m)^\s*[-*+]\s+", "", text)
    return text.strip()
