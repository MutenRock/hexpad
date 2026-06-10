#!/usr/bin/env python3
"""
HexPad GUI
==========
Interface graphique Tkinter pour lancer HexPad
sans passer par le terminal.

Usage:
    python gui.py
    ou double-cliquer launch_gui.bat
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading, json, mido, sys, os
from modules.dispatcher       import Dispatcher
from modules.midi_listener    import MidiListener
from modules.gamepad          import GamepadBridge
from modules.websocket_bridge import WebSocketBridge
from modules.macros           import MacroBridge

COLORS = {
    "bg":       "#0d0d0d",
    "panel":    "#1a1a2e",
    "accent":   "#00ffe7",
    "accent2":  "#7f00ff",
    "text":     "#e0e0e0",
    "btn":      "#16213e",
    "btn_hover":"#0f3460",
    "green":    "#00ff99",
    "red":      "#ff4444",
    "yellow":   "#ffd700",
}

class HexPadGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("HexPad v1.0.0")
        self.root.configure(bg=COLORS["bg"])
        self.root.resizable(False, False)
        self.listener_thread = None
        self.running = False
        self.config = self._load_config()
        self._build_ui()

    def _load_config(self):
        try:
            with open("config.json") as f:
                return json.load(f)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de lire config.json\n{e}")
            sys.exit(1)

    def _build_ui(self):
        # ── Header ──
        hdr = tk.Frame(self.root, bg=COLORS["bg"])
        hdr.pack(fill="x", padx=20, pady=(15, 5))
        tk.Label(hdr, text="⬡ HexPad", font=("Courier", 22, "bold"),
                 fg=COLORS["accent"], bg=COLORS["bg"]).pack(side="left")
        tk.Label(hdr, text="v1.0.0", font=("Courier", 10),
                 fg=COLORS["accent2"], bg=COLORS["bg"]).pack(side="left", padx=8, pady=6)

        # ── Device ──
        dev_frame = tk.Frame(self.root, bg=COLORS["panel"], pady=8)
        dev_frame.pack(fill="x", padx=20, pady=4)
        tk.Label(dev_frame, text="DEVICE", font=("Courier", 8),
                 fg=COLORS["accent2"], bg=COLORS["panel"]).pack(side="left", padx=10)
        self.device_var = tk.StringVar(value=self.config.get("device_name", "—"))
        devices = mido.get_input_names() or ["Aucun appareil"]
        cb = ttk.Combobox(dev_frame, textvariable=self.device_var,
                          values=devices, width=28, state="readonly")
        cb.pack(side="left", padx=6)
        # Auto-select MPK
        for d in devices:
            if "mpk" in d.lower() or "mini" in d.lower():
                self.device_var.set(d)
                break
        self.status_dot = tk.Label(dev_frame, text="●", font=("Courier", 14),
                                   fg=COLORS["red"], bg=COLORS["panel"])
        self.status_dot.pack(side="right", padx=10)

        # ── Programme selector ──
        prog_frame = tk.Frame(self.root, bg=COLORS["bg"])
        prog_frame.pack(fill="x", padx=20, pady=8)
        tk.Label(prog_frame, text="PROGRAMME", font=("Courier", 8),
                 fg=COLORS["accent2"], bg=COLORS["bg"]).pack(anchor="w")
        self.prog_btns = {}
        btn_row = tk.Frame(prog_frame, bg=COLORS["bg"])
        btn_row.pack(fill="x")
        programs = self.config.get("programs", {})
        for key, prog in programs.items():
            mode = prog.get("mode", "debug")
            b = tk.Button(btn_row, text=f" {key}\n{mode.upper()} ",
                          font=("Courier", 9, "bold"),
                          bg=COLORS["btn"], fg=COLORS["text"],
                          activebackground=COLORS["accent2"],
                          relief="flat", bd=0, padx=10, pady=6,
                          command=lambda k=key: self._select_program(k))
            b.pack(side="left", padx=4)
            self.prog_btns[key] = b
        self.selected_program = tk.StringVar(value="1")
        self._select_program("1")

        # ── Boutons start/stop ──
        ctrl = tk.Frame(self.root, bg=COLORS["bg"])
        ctrl.pack(fill="x", padx=20, pady=6)
        self.start_btn = tk.Button(ctrl, text="▶  START",
                                   font=("Courier", 11, "bold"),
                                   bg=COLORS["accent"], fg=COLORS["bg"],
                                   relief="flat", padx=20, pady=8,
                                   command=self._start)
        self.start_btn.pack(side="left", padx=(0, 8))
        self.stop_btn  = tk.Button(ctrl, text="■  STOP",
                                   font=("Courier", 11, "bold"),
                                   bg=COLORS["red"], fg="white",
                                   relief="flat", padx=20, pady=8,
                                   state="disabled",
                                   command=self._stop)
        self.stop_btn.pack(side="left")
        tk.Button(ctrl, text="⚙ Wizard",
                  font=("Courier", 9),
                  bg=COLORS["btn"], fg=COLORS["accent2"],
                  relief="flat", padx=12, pady=8,
                  command=self._open_wizard).pack(side="right")

        # ── Log console ──
        tk.Label(self.root, text="CONSOLE", font=("Courier", 8),
                 fg=COLORS["accent2"], bg=COLORS["bg"]).pack(anchor="w", padx=20)
        self.console = scrolledtext.ScrolledText(
            self.root, width=58, height=14,
            bg="#0a0a0a", fg=COLORS["accent"],
            font=("Courier", 9), relief="flat",
            insertbackground=COLORS["accent"])
        self.console.pack(padx=20, pady=(2, 15))
        self.console.config(state="disabled")
        self._log("⬡ HexPad prêt. Sélectionne un programme et clique START.")

    def _select_program(self, key):
        self.selected_program.set(key)
        for k, b in self.prog_btns.items():
            b.config(bg=COLORS["accent"] if k == key else COLORS["btn"],
                     fg=COLORS["bg"]      if k == key else COLORS["text"])

    def _log(self, msg):
        self.console.config(state="normal")
        self.console.insert("end", msg + "\n")
        self.console.see("end")
        self.console.config(state="disabled")

    def _build_bridge(self, prog):
        mode = prog.get("mode", "debug")
        if mode == "gamepad":   return GamepadBridge(prog), mode
        if mode == "websocket": return WebSocketBridge(prog.get("ws_url", "ws://localhost:8765")), mode
        if mode == "macro":     return MacroBridge(prog), mode
        return None, "debug"

    def _start(self):
        prog_key = self.selected_program.get()
        prog = self.config["programs"].get(prog_key, {})
        device = self.device_var.get()
        self.config["device_name"] = device
        bridge, mode = self._build_bridge(prog)
        d = Dispatcher()
        # Redirect print to console
        import builtins
        orig_print = builtins.print
        def gui_print(*args, **kwargs):
            self._log(" ".join(str(a) for a in args))
        builtins.print = gui_print
        d.set_bridge(bridge, mode)
        self.running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_dot.config(fg=COLORS["green"])
        self._log(f"▶ Démarrage — mode: {mode} | device: {device}")
        listener = MidiListener(self.config, d)
        self._stop_event = threading.Event()
        def run():
            try:
                listener.start()
            except Exception as e:
                self._log(f"[ERREUR] {e}")
            finally:
                builtins.print = orig_print
                self.root.after(0, self._on_stopped)
        self.listener_thread = threading.Thread(target=run, daemon=True)
        self.listener_thread.start()

    def _stop(self):
        self.running = False
        self._log("■ Arrêt demandé...")
        self._on_stopped()

    def _on_stopped(self):
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_dot.config(fg=COLORS["red"])
        self.running = False

    def _open_wizard(self):
        self._log("⚙ Lance wizard.py dans le terminal pour reconfigurer.")
        os.system("start cmd /k python wizard.py")

def main():
    root = tk.Tk()
    app  = HexPadGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
