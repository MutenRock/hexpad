#!/usr/bin/env python3
"""
HexPad — DisplayPanel
Widget tkinter qui affiche texte / image / GIF animé.
Peut être embarqué dans la GUI principale ou ouvert dans une Toplevel.
"""
import tkinter as tk
from tkinter import filedialog, font as tkfont
import os

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False


class DisplayPanel:
    """
    Panneau d'affichage multimédia.
    Paramètres :
      parent  — widget parent tkinter
      width   — largeur du canvas (px)
      height  — hauteur du canvas (px)
      bg      — couleur de fond par défaut
      fg      — couleur de texte par défaut
      root    — référence à la Tk root (pour .after)
    """

    def __init__(self, parent, width=320, height=200,
                 bg="#111111", fg="#ffffff", root=None):
        self.root   = root or parent.winfo_toplevel()
        self.bg     = bg
        self.fg     = fg
        self.width  = width
        self.height = height
        self._gif_frames   = []
        self._gif_idx      = 0
        self._gif_job      = None
        self._current_img  = None   # keep reference (GC protection)

        self.canvas = tk.Canvas(
            parent,
            width=width, height=height,
            bg=bg, highlightthickness=1, highlightbackground="#333333"
        )
        self.canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self._item = None
        self._draw_placeholder()

    # ── Public API ───────────────────────────────────────────────────────────

    def show(self, cfg: dict):
        """Affiche le contenu décrit par cfg (type: text/image/gif/clear)."""
        self._stop_gif()
        t = cfg.get("type", "text")
        if t == "clear":
            self.clear()
        elif t == "text":
            self._show_text(cfg)
        elif t == "image":
            self._show_image(cfg)
        elif t == "gif":
            self._show_gif(cfg)

    def clear(self):
        """Vide le panneau."""
        self._stop_gif()
        self.canvas.config(bg=self.bg)
        self.canvas.delete("all")
        self._draw_placeholder()

    def set_size(self, width: int, height: int):
        self.width  = width
        self.height = height
        self.canvas.config(width=width, height=height)

    def set_bg(self, color: str):
        self.bg = color
        self.canvas.config(bg=color)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _draw_placeholder(self):
        cx, cy = self.width // 2, self.height // 2
        self.canvas.create_text(
            cx, cy,
            text="\u2b21  DISPLAY",
            fill="#333333",
            font=("Courier", 14, "bold")
        )

    def _show_text(self, cfg: dict):
        text  = cfg.get("content", "")
        color = cfg.get("color", self.fg)
        size  = int(cfg.get("size", 28))
        bold  = cfg.get("bold", True)
        bg    = cfg.get("bg", self.bg)
        weight = "bold" if bold else "normal"
        self.canvas.config(bg=bg)
        self.canvas.delete("all")
        cx, cy = self.width // 2, self.height // 2
        self.canvas.create_text(
            cx, cy,
            text=text,
            fill=color,
            font=("Courier", size, weight),
            width=self.width - 16,
            justify="center"
        )

    def _show_image(self, cfg: dict):
        path = cfg.get("content", "")
        bg   = cfg.get("bg", self.bg)
        self.canvas.config(bg=bg)
        self.canvas.delete("all")
        if not path or not os.path.isfile(path):
            self._show_error(f"Image introuvable :\n{path}")
            return
        if not PIL_OK:
            self._show_error("pip install Pillow\npour les images")
            return
        try:
            img = Image.open(path)
            img = img.convert("RGBA")
            img.thumbnail((self.width - 8, self.height - 8), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._current_img = photo
            cx, cy = self.width // 2, self.height // 2
            self.canvas.create_image(cx, cy, image=photo, anchor="center")
        except Exception as e:
            self._show_error(str(e))

    def _show_gif(self, cfg: dict):
        path  = cfg.get("content", "")
        bg    = cfg.get("bg", self.bg)
        speed = int(cfg.get("speed", 50))   # ms entre frames
        self.canvas.config(bg=bg)
        self.canvas.delete("all")
        if not path or not os.path.isfile(path):
            self._show_error(f"GIF introuvable :\n{path}")
            return
        if not PIL_OK:
            self._show_error("pip install Pillow\npour les GIFs")
            return
        try:
            gif = Image.open(path)
            self._gif_frames = []
            self._gif_delays = []
            try:
                while True:
                    frame = gif.copy().convert("RGBA")
                    frame.thumbnail((self.width - 8, self.height - 8), Image.LANCZOS)
                    self._gif_frames.append(ImageTk.PhotoImage(frame))
                    delay = gif.info.get("duration", speed)
                    self._gif_delays.append(max(20, delay))
                    gif.seek(gif.tell() + 1)
            except EOFError:
                pass
            if not self._gif_frames:
                self._show_error("GIF vide")
                return
            self._gif_idx = 0
            self._gif_image_item = self.canvas.create_image(
                self.width // 2, self.height // 2,
                image=self._gif_frames[0], anchor="center"
            )
            self._animate_gif()
        except Exception as e:
            self._show_error(str(e))

    def _animate_gif(self):
        if not self._gif_frames:
            return
        idx = self._gif_idx % len(self._gif_frames)
        self.canvas.itemconfig(self._gif_image_item, image=self._gif_frames[idx])
        delay = self._gif_delays[idx] if self._gif_delays else 50
        self._gif_idx += 1
        self._gif_job = self.root.after(delay, self._animate_gif)

    def _stop_gif(self):
        if self._gif_job:
            self.root.after_cancel(self._gif_job)
            self._gif_job = None
        self._gif_frames = []
        self._gif_delays = []

    def _show_error(self, msg: str):
        self.canvas.delete("all")
        cx, cy = self.width // 2, self.height // 2
        self.canvas.create_text(
            cx, cy,
            text=f"\u26a0\ufe0f\n{msg}",
            fill="#ff4444",
            font=("Courier", 11),
            width=self.width - 16,
            justify="center"
        )
