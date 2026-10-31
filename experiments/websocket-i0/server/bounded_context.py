"""Dependency-free bounded conversation context and rolling-summary helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
import re


RECENT_RAW_TURNS = 4
HARD_RAW_TURN_CAP = 8
SUMMARY_MAX_CHARS = 600
MAX_PROTECTED_WEEKEND_PLANS = 3
MAX_PROTECTED_PLAN_CHARS = 80
SUMMARY_CONTEXT_PREFIX = (
    "以下是此前对话的压缩摘要，仅作为背景事实使用。"
    "若与用户最新消息或较新的对话冲突，以较新的信息为准：\n"
)

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_THINK_TAG = re.compile(r"</?think>", re.IGNORECASE)
_CODE_FENCE = re.compile(r"```[A-Za-z0-9_+-]*\s*(.*?)```", re.DOTALL)
_EMOTION_TAG = re.compile(r"</?emotion:[^>\r\n]*>", re.IGNORECASE)
_FRUIT_STATEMENT = re.compile(
    r"我(?:现在|目前)?(?:最)?喜欢(?:吃)?的?水果\s*(?:是|为|变成|改成)\s*([^\s，。！？,;；]+)"
)
_FRUIT_CHANGE = re.compile(
    r"我(?:现在|目前)?(?:最)?喜欢(?:吃)?的?水果\s*(?:从|由)[^\s，。！？,;；]{1,16}"
    r"(?:改成|换成|变成)\s*([^\s，。！？,;；]+)"
)
_FRUIT_CORRECTION = re.compile(r"我(?:现在|目前)?(?:最)?喜欢(?:吃)?\s*([^\s，。！？,;；]+)")
# A bare "I like X" is not a fruit fact. Allow it only beside a rejection of
# the current fruit, and only for an unambiguous fruit name in this small set.
_KNOWN_FRUITS = frozenset((
    "草莓", "芒果", "苹果", "香蕉", "葡萄", "西瓜", "橙子", "橘子", "桃子", "樱桃",
    "梨", "菠萝", "蓝莓", "猕猴桃", "柠檬", "荔枝", "哈密瓜", "火龙果", "柚子",
))
_WEEKEND_STATEMENT = re.compile(
    r"(?:我(?:这|本)?周末|(?:这|本)?周末我?|我(?:准备|打算|计划)(?:这|本)?周末)"
    r"(?:准备|打算|计划)?\s*([^。！？?\n]+)"
)


class MemoryBudgetConflict(ValueError):
    """Protected facts cannot be represented within the fixed memory budget."""


@dataclass(frozen=True)
class ProtectedMemory:
    """Bounded, user-only provenance for two deliberately narrow fact categories."""

    favorite_fruit: str | None = None
    superseded_fruits: tuple[str, ...] = ()
    weekend_plans: tuple[str, ...] = ()

    def lines(self) -> list[str]:
        lines = []
        if self.favorite_fruit:
            lines.append(f"用户当前最喜欢的水果是{self.favorite_fruit}。")
        lines.extend(f"用户这周末计划{plan}。" for plan in self.weekend_plans)
        return lines


def _short_fact_value(value: str, limit: int) -> str:
    value = value.strip(" ：:，,。！？!?.～~ ")
    value = re.split(r"(?:不喜欢|不是|而不是|但|不过)", value, maxsplit=1)[0].strip()
    if not value or any(word in value for word in ("什么", "吗", "记得", "？", "?")):
        return ""
    if len(value) > limit:
        raise MemoryBudgetConflict("explicit user fact exceeds protected value budget")
    return value


def capture_user_facts(memory: ProtectedMemory, message: dict[str, str]) -> ProtectedMemory:
    """Only an explicitly user-role message may update protected provenance."""
    if message.get("role") != "user":
        return memory
    user_text = message.get("content", "")
    fruit = memory.favorite_fruit
    superseded = memory.superseded_fruits
    plans = memory.weekend_plans
    match = _FRUIT_STATEMENT.search(user_text) or _FRUIT_CHANGE.search(user_text)
    rejected = re.search(rf"不喜欢\s*{re.escape(fruit)}(?:了)?", user_text) if fruit else None
    if match is None and rejected is not None:
        # Only inspect a nearby, subsequent replacement; never a separate
        # unrelated "改成" or an earlier preference about another object.
        nearby = user_text[rejected.end():rejected.end() + 40]
        nearby = re.split(r"[。！？?\n]", nearby, maxsplit=1)[0]
        possible = _FRUIT_CORRECTION.search(nearby)
        if possible and _short_fact_value(possible.group(1), 16) in _KNOWN_FRUITS:
            match = possible
    if match is not None:
        candidate = _short_fact_value(match.group(1), 16)
        if candidate in _KNOWN_FRUITS and candidate != fruit:
            if fruit:
                updated_superseded = tuple(dict.fromkeys((*superseded, fruit)))
                if len(updated_superseded) > 8:
                    raise MemoryBudgetConflict("too many fruit corrections for protected budget")
                superseded = updated_superseded
            fruit = candidate
    if rejected is not None and fruit == memory.favorite_fruit:
        updated_superseded = tuple(dict.fromkeys((*superseded, fruit)))
        if len(updated_superseded) > 8:
            raise MemoryBudgetConflict("too many fruit corrections for protected budget")
        superseded = updated_superseded
        fruit = None

    match = _WEEKEND_STATEMENT.search(user_text)
    if match is not None:
        plan = _short_fact_value(match.group(1), MAX_PROTECTED_PLAN_CHARS)
        if plan and plan not in plans:
            if any(marker in user_text for marker in ("改为", "改成", "取消之前", "不再")):
                plans = ()
            if len(plans) >= MAX_PROTECTED_WEEKEND_PLANS:
                raise MemoryBudgetConflict("too many distinct weekend plans for protected budget")
            plans = (*plans, plan)
    return ProtectedMemory(fruit, superseded, plans)


def _copy_messages(messages: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    return [dict(message) for message in messages]


def _raw_start(history: Sequence[dict[str, str]]) -> int:
    return 1 if history and history[0].get("role") == "system" else 0


def _completed_pair_starts(
    history: Sequence[dict[str, str]],
    completed_starts: Sequence[int] | None = None,
) -> list[int]:
    """Locate pairs without treating an unpaired message as an end marker.

    Callers with lifecycle state MUST pass completed_starts: adjacent roles alone
    cannot establish that playback and the turn actually completed.
    """
    if completed_starts is not None:
        starts = list(completed_starts)
        if starts != sorted(set(starts)) or any(
            start < _raw_start(history) or start + 1 >= len(history)
            or history[start].get("role") != "user"
            or history[start + 1].get("role") != "assistant"
            or (offset and start <= starts[offset - 1] + 1)
            for offset, start in enumerate(starts)
        ):
            raise ValueError("invalid completed pair positions")
        return starts
    starts: list[int] = []
    index = _raw_start(history)
    while index + 1 < len(history):
        if history[index].get("role") == "user" and history[index + 1].get("role") == "assistant":
            starts.append(index)
            index += 2
        else:
            index += 1
    return starts


def count_completed_turns(
    history: Sequence[dict[str, str]], completed_starts: Sequence[int] | None = None,
) -> int:
    return len(_completed_pair_starts(history, completed_starts))


def build_llm_history(
    raw_history: Sequence[dict[str, str]],
    conversation_summary: str,
) -> list[dict[str, str]]:
    """Return system, optional summary system message, then recent raw messages."""
    history = _copy_messages(raw_history)
    if not history:
        return []
    summary = conversation_summary.strip()
    if not summary:
        return history
    insert_at = 1 if history[0].get("role") == "system" else 0
    history.insert(insert_at, {"role": "system", "content": SUMMARY_CONTEXT_PREFIX + summary})
    return history


def select_turns_to_compact(
    history: Sequence[dict[str, str]],
    recent_raw_turns: int = RECENT_RAW_TURNS,
    *, completed_starts: Sequence[int] | None = None,
) -> tuple[list[dict[str, str]], int]:
    """Select only oldest complete pairs beyond the recent raw-turn budget."""
    starts = _completed_pair_starts(history, completed_starts)
    compact_count = max(0, len(starts) - recent_raw_turns)
    selected: list[dict[str, str]] = []
    for start in starts[:compact_count]:
        selected.extend((dict(history[start]), dict(history[start + 1])))
    return selected, compact_count


def _drop_oldest_completed_turns(
    history: Sequence[dict[str, str]],
    turn_count: int,
    completed_starts: Sequence[int] | None = None,
) -> list[dict[str, str]]:
    copied = _copy_messages(history)
    starts = _completed_pair_starts(copied, completed_starts)
    if turn_count < 0 or turn_count > len(starts):
        raise ValueError("turn_count exceeds available completed turns")
    if turn_count == 0:
        return copied
    for start in reversed(starts[:turn_count]):
        del copied[start:start + 2]
    return copied


def _clean_summary_unbounded(raw_summary: str) -> str:
    summary = _THINK_BLOCK.sub("", str(raw_summary))
    summary = _THINK_TAG.sub("", summary)
    summary = _CODE_FENCE.sub(r"\1", summary)
    summary = _EMOTION_TAG.sub("", summary)
    summary = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", summary)
    summary = re.sub(r"(?m)^\s*[-*+]\s+", "", summary)
    return summary.strip()


def clean_summary_text(raw_summary: str) -> str:
    """Remove presentation/control artifacts and enforce the compact size limit."""
    summary = _clean_summary_unbounded(raw_summary)
    if len(summary) > SUMMARY_MAX_CHARS:
        summary = summary[:SUMMARY_MAX_CHARS].rstrip()
    return summary


def _structurally_broken(summary: str) -> bool:
    return not summary or bool(re.search(
        r"(?:^|\n|[:：])\s*(?:用户|助手|摘要|更新后摘要)\s*[:：]?\s*$", summary,
    ))


def _protected_clause_kind(clause: str, memory: ProtectedMemory) -> bool:
    """True only for a whole, attributable protected-fact clause.

    Ambiguous mixed clauses are rejected instead of losing unrelated facts.
    """
    text = clause.strip().rstrip("，,；;。！？ ")
    user_prefix = r"(?:摘要\s*[:：]\s*)?用户\s*[:：]?\s*"
    if re.match(user_prefix, text):
        body = re.sub(r"^" + user_prefix, "", text, count=1)
        fruits = {value for value in (memory.favorite_fruit, *memory.superseded_fruits) if value}
        fruit_like = (
            ("水果" in body and "喜欢" in body)
            or ("喜欢" in body and any(value in body for value in fruits))
        )
        weekend_like = bool(memory.weekend_plans) and "周末" in body and any(
            word in body for word in ("准备", "打算", "计划")
        )
        if fruit_like:
            fruit_statement = re.fullmatch(
                r"(?:当前|现在|目前)?(?:最)?喜欢(?:吃)?(?:的)?(?:水果)?"
                r"(?:是|为|变成|改成)?\s*([^\s，,；;。！？]{1,16}?)(?:了)?", body,
            )
            if fruit_statement and fruit_statement.group(1) in _KNOWN_FRUITS:
                return True
            raise MemoryBudgetConflict("ambiguous mixed fruit clause in summary")
        if weekend_like:
            weekend_statement = re.fullmatch(
                r"(?:这|本)?周末(?:准备|打算|计划)\s*([^，,；;。！？]{1,80})", body,
            )
            if weekend_statement and weekend_statement.group(1) in memory.weekend_plans:
                return True
            raise MemoryBudgetConflict("ambiguous mixed weekend clause in summary")
    if text.startswith("助手") and any(value in text for value in memory.superseded_fruits):
        raise MemoryBudgetConflict("assistant clause mentions superseded fruit")
    return False


def _compose_protected_summary(candidate: str, memory: ProtectedMemory) -> str:
    """Keep canonical user facts once; cut only complete unprotected sentences."""
    canonical = memory.lines()
    if len("\n".join(canonical)) > SUMMARY_MAX_CHARS:
        raise MemoryBudgetConflict("protected facts exceed summary budget")
    remaining: list[str] = []
    seen: set[str] = set()
    for line in candidate.splitlines():
        line = line.strip()
        if not line or line in seen:
            continue
        seen.add(line)
        user_line = bool(re.match(r"^(?:摘要\s*[:：]\s*)?用户", line))
        retained: list[str] = []
        for clause in re.findall(r"[^，,；;。！？]+[，,；;。！？]?", line):
            if _protected_clause_kind(clause, memory):
                continue
            retained.append(clause)
        kept = "".join(retained).strip(" ，,；; ")
        if kept and user_line and not re.match(r"^(?:摘要\s*[:：]\s*)?用户", kept):
            kept = "用户：" + kept
        if kept:
            remaining.append(kept)
    protected = "\n".join(canonical)
    rest = "\n".join(remaining)
    if not rest:
        return protected
    available = SUMMARY_MAX_CHARS - len(protected) - (1 if protected else 0)
    if available < 0:
        raise MemoryBudgetConflict("protected facts leave no summary budget")
    if len(rest) > available:
        boundary = max(rest.rfind(char, 0, available + 1) for char in "。！？\n")
        if boundary < 0:
            raise MemoryBudgetConflict("no complete unprotected sentence fits beside protected facts")
        rest = rest[:boundary + 1].strip()
    return "\n".join(part for part in (protected, rest) if part)


def preserve_protected_summary(summary: str, memory: ProtectedMemory) -> str:
    """Deterministic safety net before a hard-cap drop; never truncate facts."""
    if not memory.lines() and not memory.superseded_fruits:
        return summary
    cleaned = _clean_summary_unbounded(summary)
    if _structurally_broken(cleaned):
        cleaned = ""
    return _compose_protected_summary(cleaned, memory)


def summary_rejection_reason(
    raw_summary: str, compressed_turns: int, memory: ProtectedMemory,
) -> str:
    """Stable diagnostic reason; called only after a summary was rejected."""
    if compressed_turns <= 0:
        return "no_completed_turns"
    cleaned = _clean_summary_unbounded(raw_summary)
    if _structurally_broken(cleaned):
        return "empty_or_structurally_broken"
    if memory.lines() or memory.superseded_fruits:
        try:
            _compose_protected_summary(cleaned, memory)
        except MemoryBudgetConflict:
            return "protected_summary_budget_conflict"
    return "summary_rejected"


def apply_summary_result(
    history: Sequence[dict[str, str]],
    current_summary: str,
    raw_summary_result: str,
    compressed_turns: int,
    *,
    protected_memory: ProtectedMemory | None = None,
    completed_starts: Sequence[int] | None = None,
) -> tuple[list[dict[str, str]], str, bool]:
    """Commit deletion only when a non-empty valid replacement summary exists."""
    unbounded = _clean_summary_unbounded(raw_summary_result)
    if compressed_turns <= 0 or _structurally_broken(unbounded):
        return _copy_messages(history), current_summary, False
    if protected_memory is not None and (protected_memory.lines() or protected_memory.superseded_fruits):
        try:
            updated_summary = _compose_protected_summary(unbounded, protected_memory)
        except MemoryBudgetConflict:
            return _copy_messages(history), current_summary, False
    else:
        updated_summary = clean_summary_text(raw_summary_result)
    if not updated_summary:
        return _copy_messages(history), current_summary, False
    updated_history = _drop_oldest_completed_turns(history, compressed_turns, completed_starts)
    return updated_history, updated_summary, True


def enforce_hard_raw_turn_cap(
    history: Sequence[dict[str, str]],
    hard_cap: int = HARD_RAW_TURN_CAP,
    *, completed_starts: Sequence[int] | None = None,
) -> tuple[list[dict[str, str]], int]:
    """Last-resort bound: discard only the oldest complete pairs above the cap."""
    completed_turns = count_completed_turns(history, completed_starts)
    drop_count = max(0, completed_turns - hard_cap)
    return _drop_oldest_completed_turns(history, drop_count, completed_starts), drop_count


def build_summary_request(
    current_summary: str,
    selected_messages: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Build a temporary summarizer-only context without mutating conversation state."""
    transcript_lines = []
    role_labels = {"user": "用户", "assistant": "助手"}
    for message in selected_messages:
        role = role_labels.get(message.get("role", ""), "消息")
        transcript_lines.append(f"{role}: {message.get('content', '').strip()}")
    prior = current_summary.strip() or "（无）"
    transcript = "\n".join(transcript_lines)
    return [
        {
            "role": "system",
            "content": (
                "你负责维护简短的对话背景摘要。只输出更新后的摘要正文，不输出思考过程、"
                "emotion tag、Markdown、JSON 或控制信息。保留用户明确提供的姓名、关系事实、"
                "偏好、重要计划、持续话题、未解决问题和明确纠正；删除寒暄、填充语和重复情绪措辞。"
                "关于用户本人的事实、偏好、姓名、计划、经历和纠正，只能依据标记为‘用户’的消息；"
                "‘助手’消息只能用于对话衔接、未解决问题或助手承诺，不能作为用户事实的来源。"
                "若助手内容与用户消息冲突，以用户消息为准。"
                "较新的用户陈述或纠正必须替代旧版本，不要把相互矛盾的新旧值并列为同等事实；"
                "必要时将新值表述为当前状态。"
                f"不超过 {SUMMARY_MAX_CHARS} 个中文字符。"
            ),
        },
        {
            "role": "user",
            "content": f"现有摘要：\n{prior}\n\n需要合并的较早对话：\n{transcript}\n\n请给出更新后的紧凑摘要。",
        },
    ]
