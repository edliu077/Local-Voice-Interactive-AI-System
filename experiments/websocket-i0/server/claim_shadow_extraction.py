"""Offline-only, provider-neutral shadow extraction of *unconfirmed* proposals.

No model/provider implementation, runtime hook, semantic validator, or network I/O.
Providers must enforce their own hard timeout; an elapsed-time check here only
discards late output and cannot interrupt a blocking provider.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time
from typing import Callable, Protocol, Sequence

from claim_proposals import (ClaimProposal, ClaimProposalStore, CurrentSourceRead,
                             EvidenceRef, verify_sources)
from evidence_store import EvidenceStore


@dataclass(frozen=True)
class EvidenceInput:
    evidence_id: str
    session_id: str
    message_role: str
    turn_id: int
    text: str


@dataclass(frozen=True)
class SourceContext:
    evidence: EvidenceStore
    raw_history: Sequence[dict[str, str]]
    raw_ids: Sequence[str]
    raw_turn_ids: Sequence[int]


class ClaimExtractorProvider(Protocol):
    def extract(self, source: EvidenceInput, *, timeout_seconds: float) -> str:
        """Return JSON {"candidates": [...]}; [] means abstain.

        A provider must implement its own bounded/hard timeout and may raise
        TimeoutError. Nothing here assumes a particular LLM or transport.
        """


@dataclass(frozen=True)
class ShadowEvent:
    kind: str
    reason: str = ""
    candidate_index: int | None = None
    claim_id: str | None = None
    availability: str | None = None
    amount: int = 1


@dataclass(frozen=True)
class ShadowCaseResult:
    source_id: str
    candidate_count: int
    elapsed_seconds: float
    events: tuple[ShadowEvent, ...]


def _source_probe(source: EvidenceInput) -> ClaimProposal:
    """Verify the *whole input* against G1 before passing it to a provider."""
    return ClaimProposal("input-probe", source.session_id, "unknown", "source_probe",
                         "source_probe", "none", "unknown", "proposed",
                         (EvidenceRef(source.evidence_id, source.message_role, source.turn_id,
                                      0, len(source.text), source.text),), source.turn_id)


def _parse_candidate(item: object, source: EvidenceInput) -> ClaimProposal:
    if not isinstance(item, dict):
        raise ValueError("candidate_not_object")
    required = {"evidence_id", "message_role", "turn_id", "start", "end", "quote",
                "subject_ref", "predicate", "value", "scope", "modality"}
    if not required.issubset(item) or set(item) - (required | {"valid_time", "conflict_refs"}):
        raise ValueError("candidate_schema")
    if (item["evidence_id"] != source.evidence_id or item["message_role"] != source.message_role or
            item["turn_id"] != source.turn_id):
        raise ValueError("source_identity_mismatch")
    if (not isinstance(item["start"], int) or isinstance(item["start"], bool) or
            not isinstance(item["end"], int) or isinstance(item["end"], bool) or
            not isinstance(item["quote"], str) or not item["quote"]):
        raise ValueError("invalid_span")
    for name in ("subject_ref", "predicate", "value", "scope", "modality"):
        if not isinstance(item[name], str) or not item[name]:
            raise ValueError("invalid_field_" + name)
    valid_time = item.get("valid_time")
    conflicts = item.get("conflict_refs", [])
    if ((valid_time is not None and not isinstance(valid_time, str)) or
            not isinstance(conflicts, list) or not all(isinstance(x, str) for x in conflicts)):
        raise ValueError("invalid_optional_fields")
    # Canonical, order-independent identity over the same stable fields used
    # for G2-A.1 structural deduplication. Full SHA-256 avoids process-random
    # hash(); ClaimProposalStore.put checks a same-ID/different-content collision.
    identity = (source.session_id, item["subject_ref"], item["predicate"], item["value"],
                item["scope"], item["modality"],
                (source.evidence_id, source.message_role, source.turn_id,
                 item["start"], item["end"], item["quote"]),
                source.turn_id, valid_time, tuple(conflicts))
    canonical = json.dumps(identity, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return ClaimProposal(
        claim_id=f"{source.evidence_id}:shadow:sha256:{digest}", session_id=source.session_id,
        subject_ref=item["subject_ref"], predicate=item["predicate"], value=item["value"],
        scope=item["scope"], modality=item["modality"], status="proposed",
        evidence_refs=(EvidenceRef(source.evidence_id, source.message_role, source.turn_id,
                                   item["start"], item["end"], item["quote"]),),
        observed_turn=source.turn_id, valid_time=valid_time,
        conflict_refs=tuple(conflicts),
    )


class ShadowEvaluator:
    """Bounded, deterministic accounting; no claim is promoted to a fact."""

    def __init__(self, store: ClaimProposalStore, *, max_cases: int = 128,
                 max_candidates: int = 16, max_output_bytes: int = 16384,
                 timeout_seconds: float = 5.0,
                 clock: Callable[[], float] = time.perf_counter) -> None:
        if min(max_cases, max_candidates, max_output_bytes) <= 0 or timeout_seconds <= 0:
            raise ValueError("invalid shadow limits")
        self.store = store
        self.max_cases = max_cases
        self.max_candidates = max_candidates
        self.max_output_bytes = max_output_bytes
        self.timeout_seconds = timeout_seconds
        self.clock = clock
        self.results: list[ShadowCaseResult] = []

    def inspect_existing(self, claim_id: str, context: SourceContext) -> CurrentSourceRead:
        """Always recheck current provenance; never trust the cached get()."""
        return self.store.get_with_current_source(
            claim_id, context.evidence, context.raw_history, context.raw_ids,
            context.raw_turn_ids)

    def run_case(self, provider: ClaimExtractorProvider, source: EvidenceInput,
                 context: SourceContext) -> ShadowCaseResult:
        start = self.clock()
        events: list[ShadowEvent] = []
        count = 0
        if len(self.results) >= self.max_cases:
            source_id = source.evidence_id if isinstance(source, EvidenceInput) and isinstance(source.evidence_id, str) else ""
            return ShadowCaseResult(source_id, 0, 0.0,
                                    (ShadowEvent("capacity_rejected", "max_cases"),))
        try:
            if (not isinstance(source, EvidenceInput) or source.session_id != self.store.session_id or
                    not isinstance(source.text, str) or not source.text or
                    len(source.text.encode("utf-8")) > self.max_output_bytes):
                events.append(ShadowEvent("source_rejected", "invalid_input"))
            else:
                probe = verify_sources(_source_probe(source), context.evidence,
                                       context.raw_history, context.raw_ids, context.raw_turn_ids)
                if probe.state != "source_verified":
                    availability = probe.sources[0].availability if probe.sources else "UNAVAILABLE"
                    events.append(ShadowEvent("source_rejected", "input_source_unverifiable",
                                              availability=availability))
                else:
                    raw = provider.extract(source, timeout_seconds=self.timeout_seconds)
                    if self.clock() - start > self.timeout_seconds:
                        events.append(ShadowEvent("timeout", "provider_returned_late"))
                    elif not isinstance(raw, str) or len(raw.encode("utf-8")) > self.max_output_bytes:
                        events.append(ShadowEvent("invalid_format", "output_type_or_size"))
                    else:
                        try:
                            decoded = json.loads(raw)
                            if (not isinstance(decoded, dict) or set(decoded) != {"candidates"} or
                                    not isinstance(decoded["candidates"], list) or
                                    len(decoded["candidates"]) > self.max_candidates):
                                raise ValueError("output_schema_or_candidate_limit")
                        except (ValueError, TypeError, RecursionError):
                            events.append(ShadowEvent("invalid_format", "output_json_or_schema"))
                        else:
                            count = len(decoded["candidates"])
                            if not count:
                                events.append(ShadowEvent("abstained", "no_candidates"))
                            for index, payload in enumerate(decoded["candidates"]):
                                try:
                                    proposal = _parse_candidate(payload, source)
                                except (ValueError, TypeError):
                                    events.append(ShadowEvent("invalid_format", "candidate_schema", index))
                                    continue
                                check = verify_sources(proposal, context.evidence,
                                                       context.raw_history, context.raw_ids,
                                                       context.raw_turn_ids)
                                if check.state != "source_verified":
                                    availability = check.sources[0].availability if check.sources else "UNAVAILABLE"
                                    reason = check.sources[0].reason if check.sources else "source_unverifiable"
                                    events.append(ShadowEvent("source_rejected", reason, index,
                                                              availability=availability))
                                    continue
                                events.append(ShadowEvent("source_verified", "exact_span_match", index,
                                                          proposal.claim_id, check.sources[0].availability))
                                # A repeated quote is acceptable only with an exact,
                                # matching code-point offset; no fuzzy first match.
                                saved = self.store.put(proposal)
                                if saved.reason in {"duplicate", "duplicate_content"}:
                                    events.append(ShadowEvent("duplicate", saved.reason, index))
                                elif saved.reason == "claim_id_conflict":
                                    events.append(ShadowEvent("conflict_rejected", "fingerprint_collision_or_id_conflict", index))
                                elif not saved.accepted:
                                    events.append(ShadowEvent("capacity_rejected", saved.reason, index))
                                else:
                                    refreshed = self.store.refresh_sources(
                                        proposal.claim_id, context.evidence, context.raw_history,
                                        context.raw_ids, context.raw_turn_ids)
                                    current = self.inspect_existing(proposal.claim_id, context)
                                    if current.proposal is None:
                                        events.append(ShadowEvent("capacity_rejected", "validation_update_over_budget",
                                                                  index, proposal.claim_id))
                                    elif refreshed.state != "source_verified" or current.check.state != "source_verified":
                                        events.append(ShadowEvent("source_rejected", "source_changed_during_refresh",
                                                                  index, proposal.claim_id))
                                    else:
                                        events.append(ShadowEvent("proposal_retained", "semantic_not_evaluated",
                                                                  index, proposal.claim_id,
                                                                  current.check.sources[0].availability))
                                    if saved.evicted_ids:
                                        events.append(ShadowEvent("capacity_evicted", "proposal_store_limit",
                                                                  amount=len(saved.evicted_ids)))
        except TimeoutError:
            events.append(ShadowEvent("timeout", "provider_timeout"))
        except Exception as exc:  # provider failures must not escape to a caller
            events.append(ShadowEvent("extractor_exception", type(exc).__name__))
        result = ShadowCaseResult(source.evidence_id if isinstance(source, EvidenceInput) else "",
                                  count, max(0.0, self.clock() - start), tuple(events[:self.max_candidates * 3 + 2]))
        self.results.append(result)
        return result

    def summary(self) -> dict[str, object]:
        """Source pass rate is NOT semantic/factual accuracy."""
        counts: dict[str, int] = {}
        for result in self.results:
            for event in result.events:
                counts[event.kind] = counts.get(event.kind, 0) + event.amount
        candidates = sum(result.candidate_count for result in self.results)
        # An input rejected before provider invocation is not a candidate in
        # the source-pass denominator.
        candidate_rejections = sum(1 for result in self.results for event in result.events
                                   if event.kind == "source_rejected" and event.candidate_index is not None
                                   and event.claim_id is None)
        assessed = counts.get("source_verified", 0) + candidate_rejections
        unavailable_sources = sum(1 for result in self.results for event in result.events
                                  if event.kind == "source_rejected" and
                                  event.availability in {"SUMMARY_ONLY", "EXPIRED", "UNAVAILABLE"})
        return {"cases": len(self.results), "candidates": candidates,
                "counts": counts, "rejection_reasons": self._reasons(),
                "unavailable_source_rejections": unavailable_sources,
                "abstention_rate": counts.get("abstained", 0) / len(self.results) if self.results else 0.0,
                "source_pass_rate": counts.get("source_verified", 0) / assessed if assessed else 0.0,
                "proposal_retention_rate_at_case_end": counts.get("proposal_retained", 0) /
                counts.get("source_verified", 0) if counts.get("source_verified", 0) else 0.0,
                "historical_proposal_retained_events": counts.get("proposal_retained", 0),
                # Historical retention events may later be evicted; this is
                # the current store size, not a currently verified fact count.
                "current_store_count": self.store.count,
                "confirmed_fact_count": 0,
                "total_processing_seconds": sum(result.elapsed_seconds for result in self.results),
                "source_pass_rate_is_fact_accuracy": False}

    def _reasons(self) -> dict[str, int]:
        reasons: dict[str, int] = {}
        for result in self.results:
            for event in result.events:
                if event.kind in {"source_rejected", "invalid_format", "capacity_rejected",
                                  "conflict_rejected", "timeout", "extractor_exception"}:
                    reasons[event.reason] = reasons.get(event.reason, 0) + 1
        return reasons
