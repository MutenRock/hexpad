import builtins
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import scrolledtext

import mido

from modules.config_defaults import DEFAULT_CONFIG, ensure_local_config
from modules.dispatcher import Dispatcher
from modules.gamepad import GamepadBridge
from modules.midi_listener import MidiListener
from modules.themes import get as get_theme

VERSION = "2.3.0"
DEVICE_HINTS = ("mpk", "mini", "akai", "pad")
PAD_NOTES = [36, 37, 38, 39, 40, 41, 42, 43]


def list_devices():
    try:
        return [d for d in mido.get_input_names() if d and d.lower() != "aucun"]
    except Exception:
        return []


def auto_device(devices):
    if not devices:
        return None
    for d in devices:
        dl = d.lower()
        if any(h in dl for h in DEVICE_HINTS):
            return d
    return devices[0]


def default_gamepad_mapping():
    return DEFAULT_CONFIG["programs"]["1"].copy()


class SimpleGamecontroller:
    def __init__(self, root):
        ensure_local_config(silent=True)
        self.root = root
        self.C = get_theme("dark")
        self.listener = None
        self.bridge = None
        self.dispatcher = None
        self.running = False
        self.device = None
        self._orig_print = builtins.print
        self._pad_labels = {}

        root.title(f"HexPad Simple Gamecontroller v{VERSION}")
        root.geometry("430x520")
        root.minsize(380, 460)
        root.configure(bg=self.C["bg"])
        root.protocol("WM_DELETE_WINDOW", self.close)

        self._build()
        self._patch_print()
        self._poll_devices()

    def _build(self):
        C = self.C
        header = tk.Frame(self.root, bg=C["panel"], pady=10)
        header.pack(fill="x")
        tk.Label(header, text="⬡", fg=C["accent"], bg=C["panel"], font=("Courier", 22, "bold")).pack(side="left", padx=(12, 4))
        tk.Label(header, text="Simple Manette", fg=C["text"], bg=C["panel"], font=("Courier", 14, "bold")).pack(side="left")
        tk.Button(header, text="HexPad complet", bg=C["accent2"], fg=C["bg"], relief="flat", cursor="hand2", command=self.open_full).pack(side="right", padx=8)

        status = tk.Frame(self.root, bg=C["bg"], pady=10)
        status.pack(fill="x", padx=12)
        self.dot = tk.Label(status, text="●", fg=C["red"], bg=C["bg"], font=("Courier", 16, "bold"))
        self.dot.pack(side="left")
        self.status_var = tk.StringVar(value="Recherche AKAI/MPK...")
        tk.Label(status, textvariable=self.status_var, fg=C["text"], bg=C["bg"], font=("Courier", 10, "bold")).pack(side="left", padx=8)

        hint = "Auto : AKAI/MPK détecté → vJoy gamecontroller.\nPads = boutons 1-8 · Joystick MPK = axes X/Y."
        tk.Label(self.root, text=hint, fg=C["dim"], bg=C["bg"], justify="left", font=("Courier", 8)).pack(anchor="w", padx=14)

        grid = tk.Frame(self.root, bg=C["bg"], pady=12)
        grid.pack()
        for i, note in enumerate(PAD_NOTES):
            lbl = tk.Label(grid, text=f"P{i+1}\nbtn_{i+1}", width=8, height=3, bg=C["pad_off"], fg=C["dim"], font=("Courier", 9, "bold"))
            lbl.grid(row=i // 4, column=i % 4, padx=4, pady=4)
            self._pad_labels[note] = lbl

        controls = tk.Frame(self.root, bg=C["bg"], pady=4)
        controls.pack(fill="x", padx=12)
        self.start_btn = tk.Button(controls, text="▶ START AUTO", bg=C["green"], fg=C["bg"], relief="flat", pady=10, font=("Courier", 11, "bold"), command=self.start)
        self.start_btn.pack(fill="x", pady=(0, 6))
        self.stop_btn = tk.Button(controls, text="■ STOP", bg=C["red"], fg="white", relief="flat", pady=8, font=("Courier", 10, "bold"), state="disabled", command=self.stop)
        self.stop_btn.pack(fill="x")

        self.console = scrolledtext.ScrolledText(self.root, height=8, bg=C["console_bg"], fg=C["console_fg"], insertbackground=C["accent"], relief="flat", font=("Courier", 8))
        self.console.pack(fill="both", expand=True, padx=12, pady=10)
        self.console.config(state="disabled")

    def _patch_print(self):
        def gui_print(*args, **kwargs):
            msg = " ".join(str(a) for a in args)
            self.root.after(0, self.log, msg)
        builtins.print = gui_print

    def log(self, msg):
        self.console.config(state="normal")
        self.console.insert("end", msg + "\n")
        self.console.see("end")
        self.console.config(state="disabled")

    def _poll_devices(self):
        devices = list_devices()
        chosen = auto_device(devices)
        if chosen and chosen != self.device:
            self.device = chosen
            self.status_var.set(f"PAD READY : {chosen}")
            self.dot.config(fg=self.C["accent2"])
            self.log(f"[MIDI] Pad detecte : {chosen}")
            if not self.running:
                self.start()
        elif not chosen:
            self.device = None
            if not self.running:
                self.status_var.set("NO PAD - branche ton AKAI/MPK")
                self.dot.config(fg=self.C["red"])
        self.root.after(1000, self._poll_devices)

    def _on_raw(self, msg):
        if msg.type == "note_on" and msg.velocity > 0 and msg.note in self._pad_labels:
            lbl = self._pad_labels[msg.note]
            self.root.after(0, lbl.config, {"bg": self.C["accent"], "fg": self.C["bg"]})
            self.root.after(160, lbl.config, {"bg": self.C["pad_off"], "fg": self.C["dim"]})

    def start(self):
        if self.running:
            return
        devices = list_devices()
        self.device = self.device or auto_device(devices)
        if not self.device:
            self.status_var.set("NO PAD - impossible de lancer")
            self.dot.config(fg=self.C["red"])
            self.log("[ERR] Aucun device MIDI trouve.")
            return

        mapping = default_gamepad_mapping()
        self.bridge = GamepadBridge(mapping)
        if not getattr(self.bridge, "ready", False):
            self.status_var.set("vJoy non prêt - installe/active vJoy")
            self.dot.config(fg=self.C["red"])
            self.log("[ERR] vJoy non initialise. Le mode manette ne peut pas fonctionner.")
            return

        config = {"device_name": self.device}
        self.dispatcher = Dispatcher(on_error=lambda msg: self.root.after(0, self.log, msg))
        self.dispatcher.set_bridge(self.bridge, "gamepad")
        self.listener = MidiListener(config, self.dispatcher, on_raw=self._on_raw)
        self.running = True
        self.status_var.set(f"MANETTE ACTIVE : {self.device}")
        self.dot.config(fg=self.C["green"])
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.log(f"[START] Gamecontroller sur {self.device}")
        threading.Thread(target=self._run_listener, daemon=True).start()

    def _run_listener(self):
        try:
            self.listener.start()
        except Exception as e:
            self.root.after(0, self.log, f"[ERR] {e}")
        finally:
            self.root.after(0, self._stopped)

    def stop(self):
        if self.listener:
            self.listener.stop()
        if self.dispatcher:
            self.dispatcher.stop_all()

    def _stopped(self):
        self.running = False
        self.listener = None
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        if self.device:
            self.status_var.set(f"PAD READY : {self.device}")
            self.dot.config(fg=self.C["accent2"])
        else:
            self.status_var.set("NO PAD")
            self.dot.config(fg=self.C["red"])
        self.log("[STOP] Manette arretee.")

    def open_full(self):
        subprocess.Popen([sys.executable, "gui.py"])

    def close(self):
        try:
            self.stop()
        except Exception:
            pass
        builtins.print = self._orig_print
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    SimpleGamecontroller(root)
    root.mainloop()
