"""Dependency-free detection and temporary prompting for memory recall turns."""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Sequence


MEMORY_RECALL_CONTEXT_INSTRUCTION = (
    "这是一次对已有对话信息的回忆查询。回答前请检查滚动摘要和最近对话，"
    "优先采用最新的明确用户陈述或纠正。若新信息与旧摘要冲突，以最近用户消息为准。"
    "不要在上下文已有答案时声称用户没有告诉过你。用户消息中的‘我’指用户本人；"
    "回忆用户的偏好、姓名、计划或经历时，不要改写成助手自己的第一人称事实，"
    "应使用‘你……’、‘你之前说……’或其他明确指向用户的表达。"
)
MEMORY_RECALL_RETRY_INSTRUCTION = (
    "请重新检查提供给你的滚动摘要和最近对话。若其中已有相关事实或最新纠正，请直接使用；"
    "只有确实没有信息时才说不知道。"
)
MEMORY_RECALL_REPETITION_RETRY_INSTRUCTION = (
    "重新回答用户最新的回忆问题。不要重复或轻微改写最近几轮助手已经使用过的回复，"
    "不要复用最近的模板句。"
    "先从最近对话和滚动摘要中找到用户最新明确提供或纠正的信息。"
    "用户所说的‘我’指用户本人，不要把用户事实说成助手自己的事实。"
    "直接回答问题，使用‘你……’或‘你之前说……’等明确用户主体的表述。"
    "用简短自然的中文回答。"
)

_RECALL_QUERY_PATTERNS = (
    re.compile(r"(?:你)?(?:还)?记得我.{0,24}(?:什么|啥|吗|么|来着)"),
    re.compile(r"你还记不记得.{0,24}(?:什么|啥|吗|么|来着)"),
    re.compile(
        r"(?:我)?(?:之前|刚才|前面).{0,24}"
        r"(?:告诉过你|说过|我说|我说的|说|提过).{0,24}"
        r"(?:是什么|什么|啥|吗|么|来着)"
    ),
    re.compile(
        r"我(?:现在|目前|当前|之前)(?:的)?.{0,16}"
        r"(?:最喜欢|偏好|名字|计划|要做).{0,16}"
        r"(?:是什么|什么|啥|来着|吗|么)"
    ),
)
_FALSE_UNKNOWN_SIGNALS = (
    "还没告诉我",
    "没告诉我",
    "没有告诉我",
    "没说过",
    "没有说过",
    "没跟我说过",
    "没有跟我说过",
    "我不知道",
    "我不记得",
)
_IGNORABLE = re.compile(r"[\s，。！？、；：,.!?;:\-—~～]+")


def _compact(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text)).lower()
    return _IGNORABLE.sub("", normalized)


def is_memory_recall_query(user_text: str) -> bool:
    """Return True only for explicit references to prior conversation memory."""
    compact = _compact(user_text)
    return any(pattern.search(compact) is not None for pattern in _RECALL_QUERY_PATTERNS)


def contains_false_unknown_claim(candidate_text: str) -> bool:
    """Detect strong claims that prior information was unavailable or forgotten."""
    compact = _compact(candidate_text)
    return any(_compact(signal) in compact for signal in _FALSE_UNKNOWN_SIGNALS)


def is_question_reflection(candidate_text: str, latest_user_text: str) -> bool:
    """Catch a recall answer that asks for the unknown information again."""
    candidate = str(candidate_text).strip()
    if not candidate.endswith(("?", "？")):
        return False
    answer = _compact(candidate)
    question = _compact(latest_user_text)
    if re.search(r"(?:什么|啥|哪.{0,3})(?:吗|么)?$", answer) is None:
        return False
    if min(len(answer), len(question)) < 6:
        return False
    shared = SequenceMatcher(None, answer, question, autojunk=False).find_longest_match(
        0, len(answer), 0, len(question)
    ).size
    return shared >= 5 and shared / min(len(answer), len(question)) >= 0.4


def with_memory_recall_instruction(
    base_history: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Copy context and place a temporary recall instruction before the latest user turn."""
    history = [dict(message) for message in base_history]
    if not history or history[-1].get("role") != "user":
        raise ValueError("recall_context_requires_latest_user_message")
    history.insert(len(history) - 1, {"role": "system", "content": MEMORY_RECALL_CONTEXT_INSTRUCTION})
    return history
