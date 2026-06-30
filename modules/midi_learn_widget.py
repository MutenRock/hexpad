#!/usr/bin/env python3
"""
midi_learn_widget.py — Widget Tkinter LearnButton.

Bouton autonome qui :
  1. Au clic, lance MidiLearn sur le device courant
  2. Clignote en rouge pendant l'écoute
  3. Affiche le résultat (note N / CC N) quand appris
  4. Appelle on_learned(kind, number) pour persister le mapping

Corrections vs version précédente :
  - idle_label est passé en paramètre (dynamique)
  - accept tuple transmis correctement au MidiLearn
  - _stop_blink utilise after_cancel() — plus d'AttributeError si
    le widget est détruit avant la fin du blink
  - le callback MidiLearn est wrappé dans root.after(0, ...) pour
    garantir le thread-safety Tkinter
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Literal, Tuple

from modules.midi_learn import MidiLearn, LearnKind

LearnCallback = Callable[[LearnKind, int], None]


class LearnButton(tk.Button):
    """
    Bouton MIDI Learn autonome.

    Paramètres
    ----------
    parent      : widget parent Tkinter
    root        : fenêtre racine (pour root.after)
    device_var  : tk.StringVar contenant le nom du port MIDI ouvert
    on_learned  : callable(kind: str, number: int) — appelé quand
                  un message MIDI est détecté
    accept      : tuple de kinds autorisés ("note", "cc")
    idle_label  : texte affiché à l'état repos (ex: "⚡ Learn")
    colors      : dict de couleurs du thème HexPad
    timeout     : durée max d'attente MIDI en secondes
    **kwargs    : transmis à tk.Button
    """

    BLINK_MS  = 420   # intervalle clignotement

    def __init__(
        self,
        parent: tk.Widget,
        root: tk.Tk,
        device_var: tk.StringVar,
        on_learned: LearnCallback,
        accept: Tuple[LearnKind, ...] = ("note", "cc"),
        idle_label: str = "⚡ Learn",
        colors: dict | None = None,
        timeout: float = 30.0,
        **kwargs,
    ) -> None:
        self._root       = root
        self._device_var = device_var
        self._on_learned = on_learned
        self._accept     = accept
        self._idle_label = idle_label
        self._timeout    = timeout
        self._C          = colors or {}
        self._learner: MidiLearn | None = None
        self._blink_job: str | None = None
        self._blink_state = False
        self._countdown_job: str | None = None
        self._remaining: float = 0.0

        # couleurs
        self._bg_idle   = self._C.get("btn",   "#1e1b4b")
        self._fg_idle   = self._C.get("learn", "#f43f5e")
        self._bg_active = self._C.get("learn", "#f43f5e")
        self._fg_active = self._C.get("bg",    "#0a0a12")

        defaults = dict(
            text=idle_label,
            font=("Courier", 8, "bold"),
            bg=self._bg_idle,
            fg=self._fg_idle,
            activebackground=self._bg_active,
            activeforeground=self._fg_active,
            relief="flat",
            padx=6,
            cursor="hand2",
            command=self._toggle,
        )
        defaults.update(kwargs)
        super().__init__(parent, **defaults)

    # ─────────────────────────────────────────────────────────────────────────
    # API publique
    # ─────────────────────────────────────────────────────────────────────────

    def cancel(self) -> None:
        """Annule l'écoute en cours et remet le bouton à l'état repos."""
        if self._learner:
            self._learner.cancel()
            self._learner = None
        self._stop_blink()
        self._stop_countdown()
        self._set_idle()

    # ─────────────────────────────────────────────────────────────────────────
    # Internes
    # ─────────────────────────────────────────────────────────────────────────

    def _toggle(self) -> None:
        if self._learner and self._learner.is_active():
            self.cancel()
        else:
            self._start_learn()

    def _start_learn(self) -> None:
        device = self._device_var.get().strip()
        if not device or device == "Aucun":
            self.config(text="No device", fg=self._C.get("red", "#ef4444"))
            self._root.after(1500, self._set_idle)
            return

        self._learner = MidiLearn(
            device_name=device,
            callback=self._on_midi_received,
            accept=self._accept,
            timeout=self._timeout,
        )
        self._learner.start()
        self._start_blink()
        self._start_countdown(self._timeout)

    def _on_midi_received(self, kind: LearnKind, number: int) -> None:
        """Appelé depuis le thread MidiLearn — on délègue à Tkinter."""
        self._root.after(0, self._apply_learned, kind, number)

    def _apply_learned(self, kind: LearnKind, number: int) -> None:
        self._learner = None
        self._stop_blink()
        self._stop_countdown()
        label = f"✓ {'N' if kind == 'note' else 'CC'}{number}"
        try:
            self.config(
                text=label,
                bg=self._C.get("green", "#22c55e"),
                fg=self._C.get("bg",    "#0a0a12"),
            )
        except tk.TclError:
            return
        try:
            self._on_learned(kind, number)
        except Exception:
            pass
        self._root.after(2000, self._set_idle)

    def _set_idle(self) -> None:
        """Remet le bouton à l'état repos."""
        try:
            self.config(
                text=self._idle_label,
                bg=self._bg_idle,
                fg=self._fg_idle,
            )
        except tk.TclError:
            pass  # widget détruit

    # ── Blink ─────────────────────────────────────────────────────────────────

    def _start_blink(self) -> None:
        self._blink_state = False
        self._blink_tick()

    def _blink_tick(self) -> None:
        try:
            if self._blink_state:
                self.config(
                    bg=self._bg_active,
                    fg=self._fg_active,
                    text="● LISTEN",
                )
            else:
                self.config(
                    bg=self._bg_idle,
                    fg=self._fg_idle,
                    text="○ LISTEN",
                )
            self._blink_state = not self._blink_state
            self._blink_job = self._root.after(self.BLINK_MS, self._blink_tick)
        except tk.TclError:
            pass  # widget détruit entre deux ticks

    def _stop_blink(self) -> None:
        """Annule le job blink en cours — corrige le bug d'AttributeError."""
        if self._blink_job is not None:
            try:
                self._root.after_cancel(self._blink_job)
            except Exception:
                pass
            self._blink_job = None

    # ── Countdown ─────────────────────────────────────────────────────────────

    def _start_countdown(self, remaining: float) -> None:
        self._remaining = remaining
        self._countdown_tick()

    def _countdown_tick(self) -> None:
        self._remaining -= 1
        if self._remaining <= 0:
            self.cancel()
            return
        self._countdown_job = self._root.after(1000, self._countdown_tick)

    def _stop_countdown(self) -> None:
        if self._countdown_job is not None:
            try:
                self._root.after_cancel(self._countdown_job)
            except Exception:
                pass
            self._countdown_job = None
