"""
midi_learn.py — Moteur MIDI Learn découplé de la GUI.

Usage typique depuis le Mapping Editor :

    from modules.midi_learn import MidiLearn

    def on_learned(kind, number):
        # kind = 'note' | 'cc'
        # number = int 0-127
        print(f"Appris : {kind} {number}")

    learn = MidiLearn(device_name, on_learned)
    learn.start()   # lance l'écoute dans un thread daemon
    # …l'utilisateur appuie sur un pad/knob…
    # le callback est appelé automatiquement puis l'écoute s'arrête
    learn.cancel()  # si on veut annuler manuellement
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Literal

try:
    import mido
    MIDO_OK = True
except ImportError:
    MIDO_OK = False

LearnKind = Literal["note", "cc"]
LearnCallback = Callable[[LearnKind, int], None]


class MidiLearn:
    """
    Ouvre le port MIDI en lecture et attend le premier message
    note_on (velocity > 0) ou control_change, puis appelle
    `callback(kind, number)` et ferme le port.

    Thread-safe — le callback est exécuté dans le thread d'écoute.
    Si vous mettez à jour un widget Tkinter depuis le callback,
    utilisez `root.after(0, ...)` côté appelant.
    """

    def __init__(self, device_name: str, callback: LearnCallback,
                 accept: tuple[LearnKind, ...] = ("note", "cc"),
                 timeout: float = 30.0) -> None:
        self.device_name = device_name
        self.callback = callback
        self.accept = accept
        self.timeout = timeout
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ──────────────────────────────────────────────────────────────
    def start(self) -> None:
        """Lance l'écoute dans un thread daemon."""
        if not MIDO_OK:
            raise RuntimeError("mido n'est pas installé — pip install mido")
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        """Annule l'écoute en cours (idempotent)."""
        self._stop_event.set()

    def is_active(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ──────────────────────────────────────────────────────────────
    def _run(self) -> None:
        deadline = time.monotonic() + self.timeout
        try:
            with mido.open_input(self.device_name) as port:
                while not self._stop_event.is_set():
                    if time.monotonic() > deadline:
                        break
                    msg = port.poll()
                    if msg is None:
                        time.sleep(0.005)
                        continue
                    kind, number = self._classify(msg)
                    if kind is None:
                        continue
                    if kind not in self.accept:
                        continue
                    self._stop_event.set()
                    self.callback(kind, number)
                    return
        except Exception:
            pass  # port indisponible ou device débranché

    @staticmethod
    def _classify(msg) -> tuple[LearnKind | None, int]:
        if msg.type == "note_on" and msg.velocity > 0:
            return "note", msg.note
        if msg.type == "control_change":
            return "cc", msg.control
        return None, 0
