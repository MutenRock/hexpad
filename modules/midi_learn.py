"""MidiLearn — capture MIDI note/CC sur demande et notifie via callback.

Usage (dans gui.py, monitor thread) :

    from modules.midi_learn import MidiLearn
    self._midi_learn = MidiLearn()

    # Armer la capture pour un pad (ex : pad_key = "36")
    self._midi_learn.arm("36", callback=self._on_learn_done)

    # Dans le monitor MIDI (thread) :
    result = self._midi_learn.process(msg)  # msg = mido.Message
    # result : None si rien, ou (target_key, note_or_cc, msg_type)

    # Annuler :
    self._midi_learn.cancel()

Le callback reçoit (target_key: str, value: int, msg_type: str)
    msg_type = "note" | "cc"
"""
from __future__ import annotations
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class LearnCapture:
    """Contexte d'une capture en cours."""
    target_key: str
    callback:   Callable[[str, int, str], None]
    msg_types:  tuple = field(default=("note", "cc"))  # quels types écouter


class MidiLearn:
    """State machine simple pour capturer un message MIDI et l'assigner.

    États :
      idle    → aucune capture en cours
      armed   → en attente du prochain message MIDI

    Transitions :
      idle  --arm()-->      armed
      armed --process()-->  idle  (via callback)
      armed --cancel()-->   idle
    """

    def __init__(self) -> None:
        self._lock    = threading.Lock()
        self._capture: Optional[LearnCapture] = None

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def is_armed(self) -> bool:
        """True si une capture est en attente."""
        return self._capture is not None

    @property
    def armed_target(self) -> Optional[str]:
        """Clé du pad/CC en cours de capture, ou None."""
        with self._lock:
            return self._capture.target_key if self._capture else None

    def arm(
        self,
        target_key: str,
        callback: Callable[[str, int, str], None],
        msg_types: tuple = ("note", "cc"),
    ) -> None:
        """Arme la capture pour *target_key*.

        Args:
            target_key : identifiant libre (ex : "36", "knob_0")
            callback   : appelé avec (target_key, value, msg_type) à la capture
            msg_types  : tuple parmi ("note", "cc") — filtre les types écoutés
        """
        with self._lock:
            self._capture = LearnCapture(
                target_key=target_key,
                callback=callback,
                msg_types=msg_types,
            )

    def cancel(self) -> None:
        """Annule la capture en cours sans appeler le callback."""
        with self._lock:
            self._capture = None

    def process(self, msg) -> Optional[tuple]:
        """Injecter chaque message MIDI entrant.

        Appelle le callback si la capture est armée ET que le type de message
        correspond au filtre ``msg_types``.

        Args:
            msg : mido.Message

        Returns:
            (target_key, value, msg_type) si capturé, sinon None.
        """
        with self._lock:
            if self._capture is None:
                return None

            capture = self._capture

            # Déterminer le type et la valeur utile
            msg_type: Optional[str] = None
            value:    Optional[int] = None

            if msg.type == "note_on" and msg.velocity > 0:
                if "note" in capture.msg_types:
                    msg_type = "note"
                    value    = msg.note

            elif msg.type == "note_off":
                # Ignorer les note_off — on attend un note_on
                return None

            elif msg.type == "control_change":
                if "cc" in capture.msg_types:
                    msg_type = "cc"
                    value    = msg.control

            if msg_type is None:
                return None  # type non ciblé

            # Capturer → désarmer
            self._capture = None

        # Appel du callback hors du lock pour éviter les deadlocks
        try:
            capture.callback(capture.target_key, value, msg_type)
        except Exception:
            pass  # Le callback ne doit pas crasher le thread MIDI

        return (capture.target_key, value, msg_type)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def arm_for_pad(
        self,
        pad_note: int | str,
        callback: Callable[[str, int, str], None],
    ) -> None:
        """Raccourci : arme uniquement pour les notes (pads physiques)."""
        self.arm(str(pad_note), callback, msg_types=("note",))

    def arm_for_knob(
        self,
        knob_cc: int | str,
        callback: Callable[[str, int, str], None],
    ) -> None:
        """Raccourci : arme uniquement pour les CC (encodeurs)."""
        self.arm(str(knob_cc), callback, msg_types=("cc",))

    def __repr__(self) -> str:
        state = f"armed={self._capture.target_key}" if self._capture else "idle"
        return f"<MidiLearn {state}>"
