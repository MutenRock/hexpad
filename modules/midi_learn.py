"""
MidiLearn — one-shot MIDI input capture for the Mapping Editor.

Usage:
    ml = MidiLearn()
    ml.start_learn("36", lambda key, val, kind: print(key, val, kind))
    # user presses a pad on the AKAI -> callback fires with ("36", 38, "note")
    ml.cancel()  # abort if needed
"""
from __future__ import annotations
from typing import Callable, Optional


class MidiLearn:
    """
    One-shot MIDI capture engine.

    Integrate into any MIDI monitor loop by calling .feed(msg).
    When learn is active, the first matching note_on or control_change
    triggers the callback and disarms the engine.
    """

    def __init__(self) -> None:
        self._target: Optional[str] = None
        self._callback: Optional[Callable[[str, int, str], None]] = None
        self.active = False

    # ── Public ──────────────────────────────────────────────────────────────

    def start_learn(self, target_key: str,
                    callback: Callable[[str, int, str], None]) -> None:
        """
        Arm learn mode.

        Parameters
        ----------
        target_key : str
            Identifier of the element being mapped (e.g. pad note string "36",
            or knob CC string "70").
        callback : callable(target_key, midi_value, kind)
            Called once when a MIDI event is captured.
            ``kind`` is ``"note"`` or ``"cc"``.
        """
        self._target = target_key
        self._callback = callback
        self.active = True

    def cancel(self) -> None:
        """Abort without firing callback."""
        self._target = None
        self._callback = None
        self.active = False

    def feed(self, msg) -> bool:
        """
        Feed a mido Message. Returns True if consumed by learn engine.
        Fires callback and disarms on first note_on or control_change.
        """
        if not self.active:
            return False

        kind: Optional[str] = None
        value: Optional[int] = None

        if msg.type == "note_on" and msg.velocity > 0:
            kind = "note"
            value = msg.note
        elif msg.type == "control_change":
            kind = "cc"
            value = msg.control

        if kind is None:
            return False

        target = self._target
        cb = self._callback
        self.cancel()       # disarm *before* callback to avoid re-entry
        if cb is not None:
            try:
                cb(target, value, kind)
            except Exception as exc:
                print(f"[MIDI LEARN] Erreur callback: {exc}")
        return True
