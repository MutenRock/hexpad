"""
midi_learn_widget.py — Widget Tkinter « bouton Learn » réutilisable.

Encapsule un tk.Button qui :
  1. Lance un MidiLearn sur clic
  2. Clignote en orange pendant l'écoute
  3. Appelle on_learned(kind, number) quand un pad/knob est détecté
  4. S'annule proprement si cancel() est appelé ou si un autre
     LearnButton est activé sur la même session partagée.

Usage :
    lbtn = LearnButton(
        parent        = frame,
        device_fn     = lambda: gui.device_var.get(),
        on_learned    = lambda kind, num: print(kind, num),
        theme         = C,          # dict couleurs HexPad
        accept        = ("note",),  # ou ("cc",) ou ("note", "cc")
        session       = learn_sess, # LearnSession partagée (optionnel)
    )
    lbtn.pack(side="left", padx=2)
"""
from __future__ import annotations

import tkinter as tk
import threading
from typing import Callable, Tuple, Optional

from modules.midi_learn import MidiLearn, LearnKind


class LearnSession:
    """
    Objet partagé entre tous les LearnButton d'un même éditeur.
    Garantit qu'un seul Learn est actif à la fois.
    """
    def __init__(self) -> None:
        self._active: Optional["LearnButton"] = None
        self._lock = threading.Lock()

    def register(self, btn: "LearnButton") -> None:
        """Annule le Learn précédent et enregistre btn comme actif."""
        with self._lock:
            if self._active is not None and self._active is not btn:
                self._active._do_cancel()
            self._active = btn

    def release(self, btn: "LearnButton") -> None:
        with self._lock:
            if self._active is btn:
                self._active = None


class LearnButton(tk.Button):
    """
    Bouton ⚡ Learn qui lance un MidiLearn et clignote pendant l'écoute.
    """
    _BLINK_MS = 400

    def __init__(
        self,
        parent,
        device_fn:  Callable[[], str],
        on_learned: Callable[[LearnKind, int], None],
        theme:      dict,
        accept:     Tuple[str, ...] = ("note",),
        session:    Optional[LearnSession] = None,
        **kwargs,
    ) -> None:
        self._device_fn  = device_fn
        self._on_learned = on_learned
        self._C          = theme
        self._accept     = accept
        self._session    = session
        self._learner: Optional[MidiLearn] = None
        self._blinking   = False
        self._blink_state = False

        super().__init__(
            parent,
            text="⚡",
            font=("Courier", 8, "bold"),
            bg=theme["btn"],
            fg=theme["accent2"],
            activebackground=theme["accent2"],
            activeforeground=theme["bg"],
            relief="flat",
            padx=4,
            cursor="hand2",
            command=self._on_click,
            **kwargs,
        )

    # ─────────────────────────────────────────────────────────────
    def _on_click(self) -> None:
        if self._learner and self._learner.is_active():
            self._do_cancel()
            return
        device = self._device_fn()
        if not device or device == "Aucun":
            self._flash_error()
            return
        if self._session:
            self._session.register(self)
        self._learner = MidiLearn(
            device_name=device,
            callback=self._on_result,
            accept=self._accept,
            timeout=30.0,
        )
        self._learner.start()
        self._start_blink()

    def _on_result(self, kind: LearnKind, number: int) -> None:
        # Appelé dans le thread daemon MidiLearn → on schedule sur Tkinter
        try:
            root = self.winfo_toplevel()
            root.after(0, self._apply_result, kind, number)
        except Exception:
            pass

    def _apply_result(self, kind: LearnKind, number: int) -> None:
        self._stop_blink()
        if self._session:
            self._session.release(self)
        self._on_learned(kind, number)

    def _do_cancel(self) -> None:
        if self._learner:
            self._learner.cancel()
            self._learner = None
        self._stop_blink()
        if self._session:
            self._session.release(self)

    # ── Blink ─────────────────────────────────────────────────────
    def _start_blink(self) -> None:
        self._blinking = True
        self._blink_state = True
        self.config(fg=self._C["bg"])
        self._blink_step()

    def _stop_blink(self) -> None:
        self._blinking = False
        try:
            self.config(
                bg=self._C["btn"],
                fg=self._C["accent2"],
                text="⚡",
            )
        except tk.TclError:
            pass  # widget détruit

    def _blink_step(self) -> None:
        if not self._blinking:
            return
        try:
            if self._blink_state:
                self.config(bg="#e07000", fg=self._C["bg"], text="● LEARN")
            else:
                self.config(bg=self._C["btn"], fg="#e07000", text="⚡ LEARN")
            self._blink_state = not self._blink_state
            self.after(self._BLINK_MS, self._blink_step)
        except tk.TclError:
            pass  # widget détruit

    def _flash_error(self) -> None:
        orig_bg = self["bg"]
        try:
            self.config(bg=self._C["red"])
            self.after(500, lambda: self.config(bg=orig_bg))
        except tk.TclError:
            pass
