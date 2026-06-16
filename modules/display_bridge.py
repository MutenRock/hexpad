#!/usr/bin/env python3
"""
HexPad — Display Bridge v1.1
Contrôle le panneau d'affichage de la GUI HexPad via les pads MIDI.
Chaque pad peut afficher : texte, image (PNG/JPG/BMP) ou GIF animé.

Config exemple dans config.json :
  {
    "mode": "display",
    "name": "Display",
    "display_bg": "#000000",
    "display_fg": "#ffffff",
    "pads": {
      "36": {"type": "text",  "content": "Hello!",   "color": "#00ff88", "size": 36},
      "37": {"type": "image", "content": "assets/logo.png"},
      "38": {"type": "gif",   "content": "assets/anim.gif", "speed": 60},
      "39": {"type": "text",  "content": "REC",       "color": "#ff0000", "size": 64},
      "43": {"type": "clear"}
    }
  }
"""
from __future__ import annotations
from typing import Optional


class DisplayBridge:
    """
    Bridge Display — met à jour le DisplayPanel de la GUI sur note_on.
    Le panel est injecté via set_panel() après construction par la GUI.
    """

    def __init__(self, prog: dict):
        self.prog  = prog
        self.panel = None

    def set_panel(self, panel):
        """Injecter le DisplayPanel tkinter."""
        self.panel = panel
        # Appliquer bg/fg du preset
        bg = self.prog.get("display_bg")
        fg = self.prog.get("display_fg")
        if bg and self.panel:
            self.panel.bg = bg
            self.panel.set_bg(bg)
        if fg and self.panel:
            self.panel.fg = fg

    # ── Interface Dispatcher ──────────────────────────────────────────────────

    def on_note(self, note: int, velocity: int):
        if velocity == 0:
            return
        if not self.panel:
            return
        cfg = self.prog.get("pads", {}).get(str(note))
        if not cfg:
            return
        self.panel.root.after(0, self.panel.show, cfg)

    def on_cc(self, cc: int, value: int):
        pass

    def on_pitchwheel(self, pitch: int):
        pass

    def stop(self):
        if self.panel:
            self.panel.root.after(0, self.panel.clear)
