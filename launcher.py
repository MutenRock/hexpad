import runpy
import tkinter as tk

from modules.config_defaults import ensure_local_config
from modules.themes import get as get_theme

VERSION = "2.4.0"


class HexPadLauncher:
    def __init__(self, root):
        ensure_local_config(silent=True)
        self.root = root
        self.C = get_theme("dark")
        root.title(f"HexPad Launcher v{VERSION}")
        root.geometry("440x430")
        root.resizable(False, False)
        root.configure(bg=self.C["bg"])
        self._next_script = None
        self._build()

    def _launch(self, script):
        self._next_script = script
        self.root.destroy()

    def _build(self):
        C = self.C
        header = tk.Frame(self.root, bg=C["panel"], pady=16)
        header.pack(fill="x")
        tk.Label(header, text="HexPad", fg=C["text"], bg=C["panel"], font=("Courier", 20, "bold")).pack(anchor="w", padx=20)
        tk.Label(header, text="choisis ton mode", fg=C["dim"], bg=C["panel"], font=("Courier", 9)).pack(anchor="w", padx=20)

        body = tk.Frame(self.root, bg=C["bg"], pady=18)
        body.pack(fill="both", expand=True, padx=18)

        self._big_button(body, "PLAY SOUND / STUDIO", "Akai -> son direct, preset, volume, sortie audio", C["green"], lambda: self._launch("studio_play.py"))
        self._big_button(body, "SIMPLE MANETTE AKAI", "Auto-detect MPK/Akai vers vJoy gamecontroller", C["accent2"], lambda: self._launch("simple_gamecontroller.py"))
        self._big_button(body, "HEXPAD COMPLET", "Tous les presets : macros, OBS, HTTP, sampler, RGB", C["accent"], lambda: self._launch("gui.py"))
        self._big_button(body, "DEBUG / TEST", "MIDI raw monitor, AKAI/SysEx, HTTP, WebSocket", C["btn"], lambda: self._launch("debug_test.py"))

        foot = tk.Frame(self.root, bg=C["bg"], pady=8)
        foot.pack(fill="x")
        tk.Button(foot, text="Quitter", bg=C["btn"], fg=C["dim"], relief="flat", padx=12, command=self.root.destroy).pack(side="right", padx=16)

    def _big_button(self, parent, title, subtitle, color, cmd):
        C = self.C
        wrap = tk.Frame(parent, bg=C["bg"])
        wrap.pack(fill="x", pady=6)
        tk.Button(wrap, text=title, bg=color, fg=C["bg"] if color != C["btn"] else C["accent"], relief="flat", font=("Courier", 11, "bold"), pady=9, cursor="hand2", command=cmd).pack(fill="x")
        tk.Label(wrap, text=subtitle, fg=C["dim"], bg=C["bg"], font=("Courier", 8), anchor="w").pack(fill="x", pady=(2, 0))


if __name__ == "__main__":
    root = tk.Tk()
    app = HexPadLauncher(root)
    root.mainloop()
    if app._next_script:
        runpy.run_path(app._next_script, run_name="__main__")
