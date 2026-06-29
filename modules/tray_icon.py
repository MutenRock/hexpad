"""
modules/tray_icon.py — Contrôleur System Tray pour HexPad
  - Icône hexagone générée via Pillow (déjà dep)
  - Menu contextuel : Ouvrir / Start / Stop / Quitter
  - Fallback silencieux si pystray absent
"""
import threading

try:
    import pystray
    from PIL import Image, ImageDraw
    PYSTRAY_OK = True
except ImportError:
    pystray = None
    PYSTRAY_OK = False


class TrayController:
    def __init__(self, gui):
        self.gui   = gui
        self.icon  = None
        self._thread = None

    @property
    def available(self):
        return PYSTRAY_OK

    # ── Icône hexagone ────────────────────────────────────────────────────────
    def _make_image(self):
        size = 64
        img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d    = ImageDraw.Draw(img)
        cx, cy, r = size // 2, size // 2, size // 2 - 2
        import math
        hex_pts = [
            (cx + r * math.cos(math.radians(60 * i - 90)),
             cy + r * math.sin(math.radians(60 * i - 90)))
            for i in range(6)
        ]
        inner_pts = [
            (cx + (r - 14) * math.cos(math.radians(60 * i - 90)),
             cy + (r - 14) * math.sin(math.radians(60 * i - 90)))
            for i in range(6)
        ]
        d.polygon(hex_pts,   fill="#62d6ff")
        d.polygon(inner_pts, fill="#0d1117")
        return img

    # ── Cycle de vie ──────────────────────────────────────────────────────────
    def _ensure_started(self):
        if not self.available:
            return False
        if self.icon is not None:
            return True

        menu = pystray.Menu(
            pystray.MenuItem(
                "⬡ Ouvrir HexPad",
                lambda icon, item: self.gui.root.after(0, self.restore)
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "▶ Start",
                lambda icon, item: self.gui.root.after(0, self.gui._start),
                enabled=lambda item: not self.gui.running
            ),
            pystray.MenuItem(
                "■ Stop",
                lambda icon, item: self.gui.root.after(0, self.gui._stop),
                enabled=lambda item: self.gui.running
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "✕ Quitter",
                lambda icon, item: self.gui.root.after(0, self.gui._quit_app)
            ),
        )

        self.icon = pystray.Icon(
            "hexpad",
            self._make_image(),
            "HexPad",
            menu
        )
        self._thread = threading.Thread(target=self.icon.run, daemon=True)
        self._thread.start()
        return True

    def minimize(self):
        """Envoie la fenêtre dans le tray. Retourne True si succès."""
        if not self._ensure_started():
            return False
        self.gui.root.withdraw()
        return True

    def restore(self):
        """Restaure la fenêtre depuis le tray."""
        self.gui.root.deiconify()
        self.gui.root.lift()
        self.gui.root.focus_force()
        try:
            self.gui.root.attributes("-topmost", True)
            self.gui.root.after(150,
                lambda: self.gui.root.attributes("-topmost", False))
        except Exception:
            pass

    def stop(self):
        """Arrête proprement l'icône tray."""
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon   = None
            self._thread = None
