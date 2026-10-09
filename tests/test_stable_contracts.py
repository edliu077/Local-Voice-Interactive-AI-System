"""Dependency-free static contracts for the Demo Stable default path."""
from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "backend" / "orchestrator" / "voice_ws_server.py").read_text(encoding="utf-8")
CLIENT = (ROOT / "backend" / "orchestrator" / "backend_client.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "frontend" / "src" / "components" / "VoiceConsole.tsx").read_text(encoding="utf-8")


class StableContracts(unittest.TestCase):
    def test_experimental_default_paths_are_absent(self) -> None:
        combined = SERVER + CLIENT + FRONTEND
        for forbidden in (
            "bounded_context",
            "conversation_summary",
            "emotion_parser",
            "pendingEmotionRef",
            "EMOTION_TO_EXPRESSION",
            "resetExpressionLifecycle",
            "Qwen3-4B",
            "8081",
        ):
            self.assertNotIn(forbidden, combined)

    def test_state_order_is_preserved(self) -> None:
        positions = [
            SERVER.index(f'"{state}"')
            for state in (
                "LISTENING",
                "TRANSCRIBING",
                "THINKING",
                "SYNTHESIZING",
                "SPEAKING",
            )
        ]
        self.assertEqual(positions, sorted(positions))

    def test_ack_wait_precedes_next_turn(self) -> None:
        started = SERVER.index('"started",\n                            BROWSER_STARTED_TIMEOUT_SECONDS')
        speaking = SERVER.index('"SPEAKING", turn_id=turn_id')
        finished = SERVER.index('playback_wait, "finished", finished_timeout')
        turn_complete = SERVER.index('"turn_complete"')
        self.assertLess(started, speaking)
        self.assertLess(speaking, finished)
        self.assertLess(finished, turn_complete)

    def test_loopback_and_origin_guards_exist(self) -> None:
        config = (ROOT / "backend" / "common" / "lviai_config.py").read_text(encoding="utf-8")
        self.assertIn('LOOPBACK_HOST = "127.0.0.1"', config)
        self.assertIn('parsed.hostname not in {"127.0.0.1", "localhost"}', config)
        self.assertIn("origins=ALLOWED_ORIGINS", SERVER)


if __name__ == "__main__":
    unittest.main()
