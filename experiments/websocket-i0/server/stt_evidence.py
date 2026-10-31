"""Opt-in, bounded local STT evidence. Never calls models or authorizes processes."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import threading
from typing import Any, Callable
from uuid import uuid4
import wave

LIMIT = 3
MAX_WAV_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_BYTES = 512 * 1024


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            h.update(block)
    return h.hexdigest()


@dataclass
class Ticket:
    session_id: str
    turn_id: int
    sequence: int
    directory: Path | None = None
    input_sha256: str | None = None
    response_saved: bool = False
    failed: bool = False
    terminal: bool = False


class SttEvidence:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.input = self.root / 'runtime/input/i0-vad-utterance.wav'
        self.run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ-') + uuid4().hex
        self.directory = self.root / 'runtime/stt-evidence' / self.run_id
        self.attempts = 0
        self.lock = threading.Lock()
        self.limit_reported = False
        self.created = False

    @classmethod
    def from_environment(cls, root: Path) -> SttEvidence | None:
        # Disabled: no evidence-directory access or file IO, no counter allocation.
        return cls(root) if os.environ.get('CYBER_STT_EVIDENCE') == '1' else None

    def _event(self, event: str, ticket: Ticket | None = None, **fields: Any) -> None:
        # Never put a transcript, WAV bytes or exception text in ordinary logs.
        row = dict(event=event, diagnostic_run_id=self.run_id, utc=utc(), **fields)
        if ticket:
            row.update(session_id=ticket.session_id, turn_id=ticket.turn_id, sequence=ticket.sequence)
        try:
            print(json.dumps(row, ensure_ascii=False), file=sys.stderr, flush=True)
        except Exception:
            pass

    def _owned(self, path: Path) -> Path:
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root / 'runtime'):
            raise ValueError('Evidence path escapes local runtime')
        return resolved

    def _json(self, path: Path, value: Any) -> None:
        path = self._owned(path)
        data = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode('utf-8')
        if len(data) > MAX_RESPONSE_BYTES:
            raise ValueError('Evidence JSON limit exceeded')
        stage = self._owned(path.with_name('.pending-' + uuid4().hex[:16]))
        with stage.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # NTFS hard-link publication is atomic and refuses an existing target.
        # A failed/partial write remains .pending, never a valid completion marker.
        os.link(stage, path)
        try:
            stage.unlink()
        except OSError:
            pass  # A committed record is valid even if its own staging name remains.

    def _stack(self) -> dict[str, Any]:
        # Correlation only: never claim unvalidated environment data as ownership.
        # StackRunId is optional; existing managers remain the sole authority.
        candidate = os.environ.get('REBUILD_STACK_RUN_ID', '')
        if not re.fullmatch(r'[0-9a-f]{32}', candidate):
            return dict(stack_run_id=None, stack_link='unavailable')
        try:
            owner = json.loads((self.root / 'runtime/ws-service/owner.json').read_text(encoding='utf-8-sig'))
            if (owner.get('StackRunId') == candidate and owner.get('root') == str(self.root)
                    and owner.get('entry') == str(self.root / 'scripts/ws-run.py')
                    and any(p.get('pid') == os.getpid() for p in owner.get('processes', []))):
                # This is a record correlation, not a native FILETIME identity check.
                return dict(stack_run_id=None, stack_run_id_hint=candidate,
                            stack_link='environment_and_current_pid_owner_record_only_not_native_attested')
        except (OSError, ValueError, TypeError):
            pass
        return dict(stack_run_id=None, stack_link='not_reliably_attested')

    def fail(self, ticket: Ticket | None, code: str, error: Exception | None = None) -> None:
        if ticket is None or ticket.terminal:
            return
        ticket.failed = True
        ticket.terminal = True
        fields = dict(status='INCOMPLETE', code=code, error_type=type(error).__name__ if error else None)
        if ticket.directory:
            try:
                self._json(ticket.directory / 'incomplete.json', self._identity(ticket) | fields)
            except Exception:
                fields['incomplete_marker_written'] = False
        self._event('stt_evidence_incomplete', ticket, **fields)

    def _identity(self, ticket: Ticket) -> dict[str, Any]:
        return dict(diagnostic_run_id=self.run_id, ws_session_id=ticket.session_id,
                    turn_id=ticket.turn_id, sequence=ticket.sequence, utc=utc())

    def begin(self, session_id: str, turn_id: int, source: Path,
              cancelled: Callable[[], bool]) -> Ticket | None:
        if cancelled():
            return None
        with self.lock:
            if self.attempts >= LIMIT:
                if not self.limit_reported:
                    self.limit_reported = True
                    self._event('stt_evidence_limit_reached', limit=LIMIT)
                return None
            self.attempts += 1  # Failed attempts also consume budget; never reset per session.
            ticket = Ticket(session_id, turn_id, self.attempts)
        try:
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,96}', session_id) or type(turn_id) is not int or turn_id < 1:
                raise ValueError('Invalid correlation identifiers')
            if source != self.input or self._owned(source) != self.input:
                raise ValueError('Unexpected STT input path')
            if source.stat().st_size > MAX_WAV_BYTES:
                raise ValueError('Input WAV exceeds evidence size limit')
            self._owned(self.directory)
            self.directory.parent.mkdir(parents=True, exist_ok=True)
            with self.lock:
                if not self.created:
                    self.directory.mkdir(exist_ok=False)
                    self.created = True
            # Keep paths short on native Windows; the full session ID is in JSON.
            folder = self.directory / f'{ticket.sequence:02d}-turn-{turn_id}'
            folder.mkdir(exist_ok=False)
            ticket.directory = folder
            before = source.stat()
            h = hashlib.sha256()
            with source.open('rb') as incoming, (folder / 'input.wav').open('xb') as outgoing:
                for block in iter(lambda: incoming.read(65536), b''):
                    if cancelled():
                        raise InterruptedError('Capture cancelled')
                    h.update(block)
                    outgoing.write(block)
                outgoing.flush()
                os.fsync(outgoing.fileno())
            after = source.stat()
            ticket.input_sha256 = h.hexdigest()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError('Source changed during evidence copy')
            if ticket.input_sha256 != digest(source) or ticket.input_sha256 != digest(folder / 'input.wav'):
                raise ValueError('WAV hash mismatch')
            with wave.open(str(folder / 'input.wav'), 'rb') as audio:
                frames, rate = audio.getnframes(), audio.getframerate()
                if (audio.getnchannels(), audio.getsampwidth(), rate, audio.getcomptype()) != (1, 2, 16000, 'NONE') or frames <= 0:
                    raise ValueError('Unexpected input WAV format')
                if len(audio.readframes(frames)) != frames * 2:
                    raise ValueError('Truncated WAV data')
                fmt = dict(channels=1, sample_width_bytes=2, sample_rate=rate,
                           sample_frames=frames, duration_seconds=frames / rate, compression='NONE')
            if cancelled():
                raise InterruptedError('Capture cancelled')
            self._json(folder / 'input.json', self._identity(ticket) | self._stack() | dict(
                status='INPUT_SAVED_NOT_COMPLETE', source_path=str(source), source_bytes=after.st_size,
                source_mtime_ns=after.st_mtime_ns, source_sha256=ticket.input_sha256,
                copy_sha256=ticket.input_sha256, wav=fmt))
            self._event('stt_evidence_input_saved', ticket)
        except Exception as error:
            self.fail(ticket, 'input_save_failed', error)
        return ticket

    def response(self, ticket: Ticket | None, response: Any, cancelled: Callable[[], bool]) -> None:
        if ticket is None or ticket.terminal:
            return
        try:
            if type(response) is not dict:
                raise TypeError('STT response is not a dict')
            if digest(self.input) != ticket.input_sha256:
                raise ValueError('STT input changed during request')
            # Preserve exactly existing response fields, not an invented schema/defaults.
            self._json(ticket.directory / 'stt-response.json', self._identity(ticket) | dict(
                input_sha256=ticket.input_sha256, response=response,
                cancelled_after_response=cancelled()))
            ticket.response_saved = True
            if cancelled():
                self.fail(ticket, 'cancelled_after_stt_response')
        except Exception as error:
            self.fail(ticket, 'response_save_failed', error)

    def finish(self, ticket: Ticket | None, normalized: str, cancelled: Callable[[], bool]) -> None:
        if ticket is None or ticket.terminal:
            return
        try:
            if cancelled():
                self.fail(ticket, 'cancelled_before_normalized_text')
                return
            if not ticket.response_saved or not isinstance(normalized, str) or not normalized:
                raise ValueError('No complete response/normalization pair')
            self._json(ticket.directory / 'normalized.json', self._identity(ticket) | dict(
                input_sha256=ticket.input_sha256, opencc_text=normalized))
            if cancelled():
                self.fail(ticket, 'cancelled_before_completion')
                return
            required = ['input.wav', 'input.json', 'stt-response.json', 'normalized.json']
            hashes = {name: digest(ticket.directory / name) for name in required}
            if hashes['input.wav'] != ticket.input_sha256:
                raise ValueError('Evidence WAV changed before completion')
            if cancelled():
                self.fail(ticket, 'cancelled_before_completion')
                return
            self._json(ticket.directory / 'complete.json', self._identity(ticket) | dict(
                status='STT_EVIDENCE_COMPLETE', scope='input_response_normalization_only_not_conversation_success',
                sha256=hashes))
            ticket.terminal = True
            self._event('stt_evidence_complete', ticket)
        except Exception as error:
            self.fail(ticket, 'completion_save_failed', error)
