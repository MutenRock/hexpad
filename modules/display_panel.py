#!/usr/bin/env python3
"""
HexPad — DisplayPanel v1.1
Widget tkinter qui affiche texte / image / GIF animé.
Les images et GIFs se redimensionnent automatiquement quand
le canvas change de taille (bind <Configure>).
"""
import tkinter as tk
import os

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False


def _fit(img: "Image.Image", w: int, h: int) -> "Image.Image":
    """
    Redimensionne img pour tenir dans (w, h) en conservant le ratio.
    Utilise LANCZOS si disponible, sinon ANTIALIAS (Pillow < 10).
    """
    pad = 8
    max_w, max_h = max(1, w - pad), max(1, h - pad)
    iw, ih = img.size
    if iw == 0 or ih == 0:
        return img
    scale = min(max_w / iw, max_h / ih)
    new_w, new_h = max(1, int(iw * scale)), max(1, int(ih * scale))
    resample = getattr(Image, "LANCZOS", getattr(Image, "ANTIALIAS", Image.BICUBIC))
    return img.resize((new_w, new_h), resample)


class DisplayPanel:
    """
    Panneau d'affichage multimédia avec auto-resize réactif.

    Paramètres :
      parent  — widget parent tkinter
      bg      — couleur de fond par défaut
      fg      — couleur de texte par défaut
      root    — référence à la Tk root (pour .after)
    """

    def __init__(self, parent, bg="#111111", fg="#ffffff", root=None):
        self.root  = root or parent.winfo_toplevel()
        self.bg    = bg
        self.fg    = fg

        # état courant (re-render à chaque resize)
        self._cfg          = None   # dernière config show()
        self._gif_src      = None   # Image PIL source du GIF (non redim)
        self._gif_raw      = []     # frames PIL brutes (non redim)
        self._gif_delays   = []
        self._gif_frames   = []     # frames ImageTk dimensionnées au canvas
        self._gif_idx      = 0
        self._gif_job      = None
        self._current_img  = None   # PhotoImage courante (GC guard)
        self._resize_job   = None   # debounce resize

        self.canvas = tk.Canvas(
            parent,
            bg=bg, highlightthickness=1, highlightbackground="#333333"
        )
        self.canvas.pack(fill="both", expand=True, padx=4, pady=4)

        self.canvas.bind("<Configure>", self._on_resize)
        self._draw_placeholder()

    # ── Taille courante ───────────────────────────────────────────────────────

    @property
    def width(self) -> int:
        w = self.canvas.winfo_width()
        return w if w > 1 else 320

    @property
    def height(self) -> int:
        h = self.canvas.winfo_height()
        return h if h > 1 else 200

    # ── Public API ────────────────────────────────────────────────────────────

    def show(self, cfg: dict):
        """Affiche le contenu décrit par cfg (type: text/image/gif/clear)."""
        self._stop_gif()
        self._cfg = cfg
        t = cfg.get("type", "text")
        if t == "clear":
            self.clear()
        elif t == "text":
            self._render_text(cfg)
        elif t == "image":
            self._load_image(cfg)
            self._render_image()
        elif t == "gif":
            self._load_gif(cfg)
            self._render_gif_frame(restart=True)

    def clear(self):
        """Vide le panneau et réinitialise l'état."""
        self._stop_gif()
        self._cfg         = None
        self._gif_src     = None
        self._gif_raw     = []
        self._gif_frames  = []
        self._current_img = None
        self.canvas.config(bg=self.bg)
        self.canvas.delete("all")
        self._draw_placeholder()

    def set_bg(self, color: str):
        self.bg = color
        self.canvas.config(bg=color)

    # ── Resize handler (debounced 80 ms) ──────────────────────────────────────

    def _on_resize(self, event=None):
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(80, self._do_resize)

    def _do_resize(self):
        self._resize_job = None
        if not self._cfg:
            return
        t = self._cfg.get("type", "text")
        if t == "text":
            self._render_text(self._cfg)
        elif t == "image":
            self._render_image()
        elif t == "gif":
            # re-scale toutes les frames et continuer l'anim
            self._scale_gif_frames()

    # ── Text ──────────────────────────────────────────────────────────────────

    def _render_text(self, cfg: dict):
        text   = cfg.get("content", "")
        color  = cfg.get("color", self.fg)
        size   = int(cfg.get("size", 28))
        bold   = cfg.get("bold", True)
        bg     = cfg.get("bg", self.bg)
        weight = "bold" if bold else "normal"
        self.canvas.config(bg=bg)
        self.canvas.delete("all")
        self.canvas.create_text(
            self.width // 2, self.height // 2,
            text=text,
            fill=color,
            font=("Courier", size, weight),
            width=self.width - 16,
            justify="center"
        )

    # ── Image ─────────────────────────────────────────────────────────────────

    def _load_image(self, cfg: dict):
        """Charge l'image source (non redimensionnée) en mémoire."""
        self._img_src = None
        if not PIL_OK:
            return
        path = cfg.get("content", "")
        if not path or not os.path.isfile(path):
            return
        try:
            img = Image.open(path)
            self._img_src = img.convert("RGBA")
        except Exception:
            pass

    def _render_image(self):
        """Redimensionne + affiche l'image source sur le canvas courant."""
        cfg = self._cfg or {}
        bg  = cfg.get("bg", self.bg)
        self.canvas.config(bg=bg)
        self.canvas.delete("all")

        if not PIL_OK:
            self._show_error("pip install Pillow\npour les images")
            return
        src = getattr(self, "_img_src", None)
        if src is None:
            path = cfg.get("content", "")
            self._show_error(
                f"Image introuvable :\n{path}" if path else "Chemin vide"
            )
            return
        try:
            fitted = _fit(src, self.width, self.height)
            photo  = ImageTk.PhotoImage(fitted)
            self._current_img = photo
            self.canvas.create_image(
                self.width // 2, self.height // 2,
                image=photo, anchor="center"
            )
        except Exception as e:
            self._show_error(str(e))

    # ── GIF ───────────────────────────────────────────────────────────────────

    def _load_gif(self, cfg: dict):
        """Charge toutes les frames PIL brutes (non redim) en mémoire."""
        self._gif_raw    = []
        self._gif_delays = []
        self._gif_frames = []
        if not PIL_OK:
            return
        path  = cfg.get("content", "")
        speed = int(cfg.get("speed", 50))
        if not path or not os.path.isfile(path):
            return
        try:
            gif = Image.open(path)
            while True:
                self._gif_raw.append(gif.copy().convert("RGBA"))
                delay = gif.info.get("duration", speed)
                self._gif_delays.append(max(20, delay))
                gif.seek(gif.tell() + 1)
        except EOFError:
            pass
        except Exception:
            pass
        self._scale_gif_frames()

    def _scale_gif_frames(self):
        """Re-scale toutes les frames brutes à la taille courante du canvas."""
        if not self._gif_raw:
            return
        w, h = self.width, self.height
        self._gif_frames = [
            ImageTk.PhotoImage(_fit(frame, w, h))
            for frame in self._gif_raw
        ]

    def _render_gif_frame(self, restart: bool = False):
        """Affiche (ou repart de) la première frame et lance l'animation."""
        cfg = self._cfg or {}
        bg  = cfg.get("bg", self.bg)
        self.canvas.config(bg=bg)
        self.canvas.delete("all")

        if not PIL_OK:
            self._show_error("pip install Pillow\npour les GIFs")
            return
        if not self._gif_frames:
            path = cfg.get("content", "")
            self._show_error(
                f"GIF introuvable :\n{path}" if path else "Chemin vide"
            )
            return

        if restart:
            self._gif_idx = 0

        self._gif_image_item = self.canvas.create_image(
            self.width // 2, self.height // 2,
            image=self._gif_frames[0],
            anchor="center"
        )
        self._stop_gif()
        self._animate_gif()

    def _animate_gif(self):
        if not self._gif_frames:
            return
        idx = self._gif_idx % len(self._gif_frames)
        try:
            self.canvas.itemconfig(self._gif_image_item, image=self._gif_frames[idx])
        except tk.TclError:
            return  # canvas détruit
        delay = self._gif_delays[idx] if self._gif_delays else 50
        self._gif_idx += 1
        self._gif_job = self.root.after(delay, self._animate_gif)

    def _stop_gif(self):
        if self._gif_job:
            self.root.after_cancel(self._gif_job)
            self._gif_job = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _draw_placeholder(self):
        self.canvas.create_text(
            self.width // 2, self.height // 2,
            text="\u2b21  DISPLAY",
            fill="#333333",
            font=("Courier", 14, "bold")
        )

    def _show_error(self, msg: str):
        self.canvas.delete("all")
        self.canvas.create_text(
            self.width // 2, self.height // 2,
            text=f"\u26a0\ufe0f\n{msg}",
            fill="#ff4444",
            font=("Courier", 11),
            width=self.width - 16,
            justify="center"
        )
