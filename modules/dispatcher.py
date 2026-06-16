#!/usr/bin/env python3
"""
HexPad — Dispatcher v2.1
- Support multi-bridge (liste de bridges actifs simultanément)
- Callback on_error unifié → remonte à la GUI
- Routage note_on / note_off / control_change / pitchwheel
"""
from __future__ import annotations
from typing import Callable, List, Optional


class Dispatcher:
    def __init__(self, on_error: Optional[Callable[[str], None]] = None):
        """
        on_error : callback(msg: str) appelé quand un bridge lève une exception.
                   Si None, les erreurs sont printées.
        """
        self._bridges: List[object] = []
        self._modes:   List[str]   = []
        self.on_error = on_error or (lambda msg: print(f"[ERR] {msg}"))

    # ── Configuration ─────────────────────────────────────────────────────────

    def set_bridge(self, bridge, mode: str):
        """Remplace tous les bridges actifs par un seul (mode simple)."""
        self.clear_bridges()
        self.add_bridge(bridge, mode)

    def add_bridge(self, bridge, mode: str):
        """Ajoute un bridge sans effacer les autres (mode multi)."""
        self._bridges.append(bridge)
        self._modes.append(mode)
        print(f"[DISPATCHER] Bridge ajouté : {mode}")

    def clear_bridges(self):
        self._bridges.clear()
        self._modes.clear()

    @property
    def mode(self) -> str:
        """Mode du premier bridge (compat ascendante)."""
        return self._modes[0] if self._modes else "debug"

    # ── Routage MIDI ──────────────────────────────────────────────────────────

    def handle(self, msg):
        if not self._bridges:
            print(f"[DEBUG MIDI] {msg}")
            return

        for bridge, mode in zip(self._bridges, self._modes):
            try:
                if mode == "debug":
                    print(f"[DEBUG MIDI] {msg}")
                    continue
                t = msg.type
                if t == "note_on":
                    bridge.on_note(msg.note, msg.velocity)
                elif t == "note_off":
                    bridge.on_note(msg.note, 0)
                elif t == "control_change":
                    bridge.on_cc(msg.control, msg.value)
                elif t == "pitchwheel":
                    bridge.on_pitchwheel(msg.pitch)
            except Exception as e:
                self.on_error(f"[{mode}] {type(e).__name__}: {e}")

    def stop_all(self):
        """Appelle stop() sur tous les bridges."""
        for bridge, mode in zip(self._bridges, self._modes):
            try:
                bridge.stop()
            except Exception as e:
                self.on_error(f"[{mode}] stop() : {e}")
        self.clear_bridges()
