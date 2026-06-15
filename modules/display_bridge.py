#!/usr/bin/env python3
"""
HexPad — Display Bridge v1.0
Contrôle le panneau d'affichage de la GUI HexPad via les pads MIDI.
Chaque pad peut afficher : texte, image (PNG/JPG/BMP) ou GIF animé.

Config exemple dans config.json :
  {
    "mode": "display",
    "name": "Display",
    "display_bg": "#000000",
    "display_fg": "#ffffff",
    "display_font_size": 28,
    "pads": {
      "36": {"type": "text",  "content": "Hello!", "color": "#00ff88", "size": 36},
      "37": {"type": "image", "content": "assets/logo.png"},
      "38": {"type": "gif",   "content": "assets/anim.gif"},
      "39": {"type": "text",  "content": "Scene 1", "color": "#ff4455"},
      "40": {"type": "text",  "content": "REC", "color": "#ff0000", "size": 64},
      "41": {"type": "image", "content": "assets/obs.png"},
      "42": {"type": "text",  "content": "\u23f8 PAUSE", "color": "#ffaa00"},
      "43": {"type": "clear"}
    }
  }
"""
import threading
import os


class DisplayBridge:
    """
    Bridge Display — met à jour le panneau DisplayPanel de la GUI
    sur chaque note_on.
    Le panel est injecté via set_panel() après construction.
    """

    def __init__(self, prog: dict):
        self.prog  = prog
        self.panel = None   # référence à DisplayPanel (injectée par la GUI)

    def set_panel(self, panel):
        """Injecter le DisplayPanel tkinter après construction."""
        self.panel = panel

    # ── Interface attendue par Dispatcher ────────────────────────────────────

    def on_note(self, note: int, velocity: int):
        if velocity == 0:
            return
        if not self.panel:
            return
        ns  = str(note)
        cfg = self.prog.get("pads", {}).get(ns)
        if not cfg:
            return
        # dispatch dans le thread principal via after()
        self.panel.root.after(0, self.panel.show, cfg)

    def on_cc(self, cc: int, value: int):
        pass

    def on_pitchwheel(self, pitch: int):
        pass

    def stop(self):
        if self.panel:
            self.panel.root.after(0, self.panel.clear)
