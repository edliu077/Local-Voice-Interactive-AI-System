"""Session-local, topic-independent, bounded message-source evidence.

This is source evidence, not a fact extractor or a claim of summary fidelity.
The caller keeps the bounded raw-history-to-evidence-ID alignment separately.
"""
from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass, replace
import time
from typing import Callable, Iterable, Sequence


DEFAULT_MAX_RECORDS = 32
DEFAULT_MAX_TEXT_BYTES = 2048
DEFAULT_MAX_TOTAL_TEXT_BYTES = 32768
DEFAULT_MAX_LOSS_NOTES = 16


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    session_id: str
    turn_id: int
    message_role: str
    message_sequence: int
    text: str | None
    source_type: str
    normalization: str
    recorded_at: float
    turn_state: str = "partial"
    turn_phase: str = "accepted_user"
    source_removed_reason: str | None = None
    summary_revision: int | None = None

    @property
    def lifecycle_state(self) -> str:
        if self.source_removed_reason is not None:
            return f"source_removed_{self.source_removed_reason}"
        return f"raw_{self.turn_state}"


@dataclass(frozen=True)
class LossNote:
    evidence_id: str
    reason: str


class EvidenceStore:
    """Bound exact copies and metadata independently of Rolling Summary.

    If metadata ages out, an ID not still mapped to raw history becomes
    UNAVAILABLE; no indefinite tombstone registry is retained.
    """

    def __init__(
        self, session_id: str, *, max_records: int = DEFAULT_MAX_RECORDS,
        max_text_bytes: int = DEFAULT_MAX_TEXT_BYTES,
        max_total_text_bytes: int = DEFAULT_MAX_TOTAL_TEXT_BYTES,
        max_loss_notes: int = DEFAULT_MAX_LOSS_NOTES,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not session_id or min(max_records, max_text_bytes, max_total_text_bytes, max_loss_notes) <= 0:
            raise ValueError("evidence limits and session_id must be positive/nonempty")
        self.session_id = session_id
        self.max_records = max_records
        self.max_text_bytes = max_text_bytes
        self.max_total_text_bytes = max_total_text_bytes
        self.max_loss_notes = max_loss_notes
        self._clock = clock
        self._sequence = 0
        self._records: OrderedDict[str, EvidenceRecord] = OrderedDict()
        self.loss_notes: deque[LossNote] = deque(maxlen=max_loss_notes)
        self.summary_rejections = 0
        self.retained_text_bytes = 0

    @property
    def record_count(self) -> int:
        return len(self._records)

    def get(self, evidence_id: str) -> EvidenceRecord | None:
        return self._records.get(evidence_id)

    def _note(self, evidence_id: str, reason: str) -> None:
        self.loss_notes.append(LossNote(evidence_id, reason))

    def _release_text(self, evidence_id: str) -> None:
        record = self._records[evidence_id]
        if record.text is None:
            return
        self.retained_text_bytes -= len(record.text.encode("utf-8"))
        self._records[evidence_id] = replace(record, text=None)
        self._note(evidence_id, "exact_copy_evicted")

    def record_message(
        self, turn_id: int, message_role: str, text: str,
        source_type: str, normalization: str,
    ) -> EvidenceRecord:
        """Record exactly the message text placed in history, or no copy at all."""
        if message_role not in {"user", "assistant"}:
            raise ValueError("only user/assistant history messages are evidence")
        if not isinstance(text, str):
            raise TypeError("evidence text must be a string")
        self._sequence += 1
        evidence_id = f"{self.session_id}:{self._sequence}"
        text_bytes = len(text.encode("utf-8"))
        retained = text if text_bytes <= self.max_text_bytes else None
        if retained is None:
            self._note(evidence_id, "text_exceeds_per_record_limit")
        while retained is not None and self.retained_text_bytes + text_bytes > self.max_total_text_bytes:
            oldest_copy = next((key for key, item in self._records.items() if item.text is not None), None)
            if oldest_copy is None:
                retained = None
                self._note(evidence_id, "text_exceeds_total_limit")
                break
            self._release_text(oldest_copy)
        while len(self._records) >= self.max_records:
            old_id, old_record = self._records.popitem(last=False)
            if old_record.text is not None:
                self.retained_text_bytes -= len(old_record.text.encode("utf-8"))
            self._note(old_id, "record_metadata_expired")
        record = EvidenceRecord(
            evidence_id, self.session_id, turn_id, message_role, self._sequence,
            retained, source_type, normalization, self._clock(),
            turn_phase="accepted_user" if message_role == "user" else "assistant_selected",
        )
        self._records[evidence_id] = record
        if retained is not None:
            self.retained_text_bytes += text_bytes
        return record

    def mark_turn_completed(self, turn_id: int) -> None:
        for evidence_id, record in tuple(self._records.items()):
            if record.turn_id == turn_id and record.turn_state == "partial":
                self._records[evidence_id] = replace(
                    record, turn_state="completed", turn_phase="completed",
                )

    def mark_turn_phase(self, turn_id: int, phase: str) -> None:
        if phase not in {"assistant_text_sent", "playback_started", "playback_finished"}:
            raise ValueError("unknown turn phase")
        for evidence_id, record in tuple(self._records.items()):
            if record.turn_id == turn_id and record.turn_state == "partial":
                self._records[evidence_id] = replace(record, turn_phase=phase)

    def mark_raw_removed(
        self, evidence_ids: Iterable[str], reason: str, summary_revision: int | None,
    ) -> None:
        if reason not in {"summary", "hard_cap", "interrupted_cap"}:
            raise ValueError("unknown raw-source removal reason")
        for evidence_id in dict.fromkeys(evidence_ids):
            record = self._records.get(evidence_id)
            if record is None:
                self._note(evidence_id, f"source_removed_{reason}_metadata_expired")
            elif record.source_removed_reason is None:
                self._records[evidence_id] = replace(
                    record, source_removed_reason=reason,
                    summary_revision=summary_revision if reason == "summary" else None,
                )

    def note_summary_rejected(self) -> None:
        # A bounded diagnostic counter; rejection never changes source state.
        self.summary_rejections = min(255, self.summary_rejections + 1)

    def availability(self, evidence_id: str, raw_history_ids: Sequence[str]) -> str:
        if evidence_id in raw_history_ids:
            return "RAW_HISTORY"
        record = self._records.get(evidence_id)
        if record is not None:
            if record.text is not None:
                return "EXACT_STORE"
            if record.source_removed_reason == "summary" and record.summary_revision is not None:
                return "SUMMARY_ONLY"
            return "UNAVAILABLE"
        if any(note.evidence_id == evidence_id for note in self.loss_notes):
            return "EXPIRED"
        return "UNAVAILABLE"
