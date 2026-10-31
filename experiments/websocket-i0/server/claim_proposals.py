"""Bounded, source-bound claim *proposals*. Not a semantic fact extractor.

Offsets are Python Unicode code-point offsets into the exact evidence message.
This module is deliberately not imported by the live conversation path.
EvidenceRef.quote is retained within the proposal's byte budget even after G1
exact evidence expires; that quote alone never establishes current provenance.
"""
from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass, replace
import json
from typing import Sequence

from evidence_store import EvidenceStore


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    message_role: str
    turn_id: int
    start: int
    end: int
    quote: str


@dataclass(frozen=True)
class ClaimProposal:
    claim_id: str
    session_id: str
    subject_ref: str
    predicate: str
    value: str
    scope: str
    modality: str
    status: str
    evidence_refs: tuple[EvidenceRef, ...]
    observed_turn: int
    valid_time: str | None = None
    validation_state: str = "not_checked"
    semantic_validation: str = "not_evaluated"
    fact_confirmation: str = "not_confirmed"
    revision: int = 0
    conflict_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceCheck:
    evidence_id: str
    availability: str
    state: str
    reason: str
    message_role: str | None = None
    turn_id: int | None = None
    turn_state: str | None = None
    turn_phase: str | None = None


@dataclass(frozen=True)
class ClaimCheck:
    state: str
    sources: tuple[SourceCheck, ...]


@dataclass(frozen=True)
class StoreResult:
    accepted: bool
    reason: str
    evicted_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CurrentSourceRead:
    """A current check and a non-persisted proposal view, not fact approval."""
    proposal: ClaimProposal | None
    check: ClaimCheck


def _proposal_identity(item: ClaimProposal) -> tuple[object, ...]:
    """Stable structural identity; excludes ID and mutable validation lifecycle."""
    return (item.session_id, item.subject_ref, item.predicate, item.value,
            item.scope, item.modality, item.evidence_refs, item.observed_turn,
            item.valid_time, item.conflict_refs)


def verify_sources(
    proposal: ClaimProposal,
    evidence: EvidenceStore,
    raw_history: Sequence[dict[str, str]],
    raw_ids: Sequence[str],
    raw_turn_ids: Sequence[int],
) -> ClaimCheck:
    """Read-only structural/exact-text check; never validates claim semantics.

    raw_history includes the system message; both sidecars exclude it.
    Missing/invalid inputs yield an unverified result rather than an exception.
    """
    if not isinstance(proposal, ClaimProposal) or not isinstance(evidence, EvidenceStore):
        return ClaimCheck("source_unverifiable", ())
    if proposal.session_id != evidence.session_id or not isinstance(proposal.evidence_refs, tuple) or not proposal.evidence_refs:
        return ClaimCheck("source_unverifiable", ())
    try:
        aligned = (len(raw_history) == len(raw_ids) + 1 == len(raw_turn_ids) + 1
                   and isinstance(raw_history[0], dict)
                   and raw_history[0].get("role") == "system")
    except (TypeError, IndexError):
        aligned = False
    if not aligned:
        return ClaimCheck("source_unverifiable", ())
    checks: list[SourceCheck] = []
    for ref in proposal.evidence_refs:
        if not isinstance(ref, EvidenceRef) or not isinstance(ref.evidence_id, str):
            checks.append(SourceCheck("", "UNAVAILABLE", "source_unverifiable", "invalid_reference"))
            continue
        record = evidence.get(ref.evidence_id)
        availability = evidence.availability(ref.evidence_id, raw_ids)
        base = dict(evidence_id=ref.evidence_id, availability=availability,
                    message_role=record.message_role if record else None,
                    turn_id=record.turn_id if record else None,
                    turn_state=record.turn_state if record else None,
                    turn_phase=record.turn_phase if record else None)
        def fail(reason: str) -> SourceCheck:
            return SourceCheck(state="source_unverifiable", reason=reason, **base)
        if not ref.evidence_id.startswith(proposal.session_id + ":") or (record and record.session_id != proposal.session_id):
            checks.append(fail("cross_session_or_unknown_id"))
            continue
        if ref.message_role not in {"user", "assistant"} or not isinstance(ref.turn_id, int) or isinstance(ref.turn_id, bool):
            checks.append(fail("invalid_role_or_turn"))
            continue
        if (not isinstance(ref.start, int) or isinstance(ref.start, bool) or
            not isinstance(ref.end, int) or isinstance(ref.end, bool) or
            not isinstance(ref.quote, str) or ref.start < 0 or ref.end <= ref.start):
            checks.append(fail("invalid_span"))
            continue
        positions = [i for i, item in enumerate(raw_ids) if item == ref.evidence_id]
        if len(positions) > 1:
            checks.append(fail("duplicate_raw_id"))
            continue
        if positions:
            i = positions[0]
            message = raw_history[i + 1]
            if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                checks.append(fail("invalid_raw_message"))
                continue
            if message.get("role") != ref.message_role or raw_turn_ids[i] != ref.turn_id:
                checks.append(fail("raw_role_or_turn_mismatch"))
                continue
            if record and (record.message_role != ref.message_role or record.turn_id != ref.turn_id or
                           record.source_removed_reason is not None or
                           (record.text is not None and record.text != message["content"])):
                checks.append(fail("raw_record_mismatch"))
                continue
            # An ID without its G1 metadata cannot establish its provenance,
            # even if a raw sidecar still names it.
            if record is None:
                checks.append(fail("record_metadata_expired"))
                continue
            source_text = message["content"]
        elif record is not None and availability == "EXACT_STORE":
            if record.message_role != ref.message_role or record.turn_id != ref.turn_id:
                checks.append(fail("record_role_or_turn_mismatch"))
                continue
            source_text = record.text
        else:
            checks.append(fail("exact_source_unavailable"))
            continue
        if source_text is None or ref.end > len(source_text) or source_text[ref.start:ref.end] != ref.quote:
            checks.append(fail("span_text_mismatch"))
            continue
        checks.append(SourceCheck(state="source_verified", reason="exact_span_match", **base))
    return ClaimCheck("source_verified" if checks and all(c.state == "source_verified" for c in checks)
                      else "source_unverifiable", tuple(checks))


class ClaimProposalStore:
    """Per-session bounded proposals; never promotes semantics or facts."""

    def __init__(self, session_id: str, *, max_records: int = 32,
                 max_metadata_bytes: int = 32768, max_quote_bytes: int = 8192,
                 max_loss_notes: int = 16) -> None:
        if not session_id or min(max_records, max_metadata_bytes, max_quote_bytes, max_loss_notes) <= 0:
            raise ValueError("invalid store limits or session")
        self.session_id = session_id
        self.max_records = max_records
        self.max_metadata_bytes = max_metadata_bytes
        self.max_quote_bytes = max_quote_bytes
        self.loss_notes: deque[tuple[str, str]] = deque(maxlen=max_loss_notes)
        self._items: OrderedDict[str, ClaimProposal] = OrderedDict()

    def get(self, claim_id: str) -> ClaimProposal | None:
        """Return stored snapshot only; validation_state may now be stale.

        Use get_with_current_source when deciding whether evidence is currently
        verifiable. Retained EvidenceRef.quote is not independent proof.
        """
        return self._items.get(claim_id)

    def get_with_current_source(self, claim_id: str, evidence: EvidenceStore,
                                raw_history: Sequence[dict[str, str]], raw_ids: Sequence[str],
                                raw_turn_ids: Sequence[int]) -> CurrentSourceRead:
        """Read and recheck G1 sources without mutating the stored proposal."""
        item = self.get(claim_id)
        if item is None:
            return CurrentSourceRead(None, ClaimCheck("source_unverifiable", ()))
        check = verify_sources(item, evidence, raw_history, raw_ids, raw_turn_ids)
        status = "proposed" if check.state == "source_verified" else "source_unverifiable"
        view = replace(item, status=status, validation_state=check.state)
        return CurrentSourceRead(view, check)

    @property
    def count(self) -> int:
        return len(self._items)

    @staticmethod
    def _sizes(item: ClaimProposal) -> tuple[int, int]:
        quotes = sum(len(ref.quote.encode("utf-8")) for ref in item.evidence_refs)
        payload = (item.claim_id, item.session_id, item.subject_ref, item.predicate,
                   item.value, item.scope, item.modality, item.status, item.observed_turn,
                   item.valid_time, item.validation_state, item.semantic_validation,
                   item.fact_confirmation, item.revision, item.conflict_refs,
                   tuple((r.evidence_id, r.message_role, r.turn_id, r.start, r.end)
                         for r in item.evidence_refs))
        return len(json.dumps(payload, ensure_ascii=False).encode("utf-8")), quotes

    @property
    def retained_bytes(self) -> tuple[int, int]:
        sizes = [self._sizes(item) for item in self._items.values()]
        return sum(s[0] for s in sizes), sum(s[1] for s in sizes)

    def put(self, item: ClaimProposal) -> StoreResult:
        try:
            valid = (isinstance(item, ClaimProposal) and item.session_id == self.session_id and
                     isinstance(item.claim_id, str) and bool(item.claim_id) and
                     all(isinstance(x, str) and bool(x) for x in
                         (item.subject_ref, item.predicate, item.value, item.scope, item.modality)) and
                     item.status == "proposed" and item.validation_state == "not_checked" and
                     item.semantic_validation == "not_evaluated" and
                     item.fact_confirmation == "not_confirmed" and item.revision == 0 and
                     isinstance(item.observed_turn, int) and not isinstance(item.observed_turn, bool) and
                     item.observed_turn >= 0 and isinstance(item.evidence_refs, tuple) and
                     bool(item.evidence_refs) and all(isinstance(r, EvidenceRef) for r in item.evidence_refs) and
                     isinstance(item.conflict_refs, tuple) and
                     all(isinstance(x, str) for x in item.conflict_refs) and
                     (item.valid_time is None or isinstance(item.valid_time, str)))
            if not valid:
                return StoreResult(False, "invalid_proposal")
            metadata, quotes = self._sizes(item)
        except (TypeError, ValueError, AttributeError, UnicodeError, RecursionError):
            return StoreResult(False, "invalid_proposal")
        if metadata > self.max_metadata_bytes or quotes > self.max_quote_bytes:
            return StoreResult(False, "single_proposal_over_budget")
        old = self._items.get(item.claim_id)
        if old is not None:
            return StoreResult(_proposal_identity(old) == _proposal_identity(item),
                               "duplicate" if _proposal_identity(old) == _proposal_identity(item)
                               else "claim_id_conflict")
        # Distinct caller-generated IDs must not repeatedly retain the same
        # proposal. This is structural deduplication, not semantic inference.
        if any(_proposal_identity(existing) == _proposal_identity(item)
               for existing in self._items.values()):
            return StoreResult(False, "duplicate_content")
        evicted: list[str] = []
        total_meta, total_quotes = self.retained_bytes
        while self._items and (len(self._items) >= self.max_records or
                               total_meta + metadata > self.max_metadata_bytes or
                               total_quotes + quotes > self.max_quote_bytes):
            old_id, removed = self._items.popitem(last=False)
            m, q = self._sizes(removed)
            total_meta -= m
            total_quotes -= q
            evicted.append(old_id)
            self.loss_notes.append((old_id[:128], "proposal_capacity_eviction"))
        self._items[item.claim_id] = item
        return StoreResult(True, "added", tuple(evicted))

    def refresh_sources(self, claim_id: str, evidence: EvidenceStore,
                        raw_history: Sequence[dict[str, str]], raw_ids: Sequence[str],
                        raw_turn_ids: Sequence[int]) -> ClaimCheck:
        item = self.get(claim_id)
        if item is None:
            return ClaimCheck("source_unverifiable", ())
        result = verify_sources(item, evidence, raw_history, raw_ids, raw_turn_ids)
        status = "proposed" if result.state == "source_verified" else "source_unverifiable"
        updated = replace(item, status=status, validation_state=result.state, revision=item.revision + 1)
        if (status, result.state) == (item.status, item.validation_state):
            return result
        # The extra status metadata must also respect the configured byte cap.
        new_meta, new_quotes = self._sizes(updated)
        old_meta, old_quotes = self._sizes(item)
        total_meta, total_quotes = self.retained_bytes
        if total_meta - old_meta + new_meta > self.max_metadata_bytes or total_quotes - old_quotes + new_quotes > self.max_quote_bytes:
            self._items.pop(claim_id)
            self.loss_notes.append((claim_id[:128], "validation_update_over_budget"))
            return result
        self._items[claim_id] = updated
        return result
