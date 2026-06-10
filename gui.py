#!/usr/bin/env python3
"""
HexPad GUI v2 — interface cyber avec editeur de presets integre
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import threading, json, mido, sys, os, builtins
from modules.dispatcher       import Dispatcher
from modules.midi_listener    import MidiListener
from modules.gamepad          import GamepadBridge
from modules.websocket_bridge import WebSocketBridge
from modules.macros           import MacroBridge

VERSION = "1.2.0"

C = {
    "bg":      "#0a0a12",
    "panel":   "#11111f",
    "panel2":  "#16162a",
    "border":  "#1e1e3a",
    "accent":  "#00ffe7",
    "accent2": "#7f00ff",
    "accent3": "#ff006e",
    "text":    "#c8c8e8",
    "dim":     "#555577",
    "green":   "#00ff99",
    "red":     "#ff4455",
    "yellow":  "#ffd700",
    "btn":     "#1a1a30",
}

MODE_COLORS = {
    "gamepad":   "#00ffe7",
    "websocket": "#7f00ff",
    "macro":     "#ffd700",
    "debug":     "#ff006e",
}

AXIS_OPTIONS  = ["axis_x","axis_y","axis_z","axis_rx","axis_ry","axis_rz","axis_sl0","axis_sl1"]
BTN_OPTIONS   = [f"btn_{i}" for i in range(1, 17)]
MACRO_OPTIONS = ["ctrl+z","ctrl+s","ctrl+c","ctrl+v","ctrl+shift+z","f5","f11","esc","space","enter"]

PAD_NOTES_A = [36,37,38,39,40,41,42,43]
PAD_NOTES_B = [44,45,46,47,48,49,50,51]
KNOB_CC     = [70,71,72,73,74,75,76,77]
KNOB_LABELS = ["K1","K2","K3","K4","K5","K6","K7","K8"]


def make_sep(parent, color=None):
    c = color or C["border"]
    tk.Frame(parent, bg=c, height=1).pack(fill="x", padx=16, pady=6)


class HexPadGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"HexPad v{VERSION}")
        self.root.configure(bg=C["bg"])
        self.root.resizable(True, True)
        self.root.minsize(700, 640)
        self.running = False
        self._orig_print = builtins.print
        self.config = self._load_config()
        self._build_ui()

    # ── Config I/O ────────────────────────────────────────────────────────────
    def _load_config(self):
        try:
            with open("config.json") as f:
                return json.load(f)
        except Exception as e:
            messagebox.showerror("Erreur config", str(e))
            sys.exit(1)

    def _save_config(self):
        with open("config.json", "w") as f:
            json.dump(self.config, f, indent=2)
        self._log("[CONFIG] Sauvegarde OK")

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Split: left = controls, right = preset editor
        self.main = tk.Frame(self.root, bg=C["bg"])
        self.main.pack(fill="both", expand=True)
        self.left  = tk.Frame(self.main, bg=C["bg"], width=320)
        self.right = tk.Frame(self.main, bg=C["panel"], width=380)
        self.left.pack(side="left", fill="both", expand=False, padx=(12,4), pady=12)
        self.right.pack(side="right", fill="both", expand=True, padx=(4,12), pady=12)
        self.left.pack_propagate(False)
        self._build_left()
        self._build_right()

    def _build_left(self):
        p = self.left
        # Header
        hdr = tk.Frame(p, bg=C["bg"])
        hdr.pack(fill="x", pady=(6,2))
        tk.Label(hdr, text="⬡", font=("Courier",28,"bold"), fg=C["accent"],  bg=C["bg"]).pack(side="left")
        tk.Label(hdr, text=" HexPad", font=("Courier",20,"bold"), fg=C["text"], bg=C["bg"]).pack(side="left")
        tk.Label(hdr, text=f"v{VERSION}", font=("Courier",9), fg=C["dim"], bg=C["bg"]).pack(side="left", pady=8)

        make_sep(p, C["accent2"])

        # Device
        df = tk.Frame(p, bg=C["panel2"], pady=8)
        df.pack(fill="x", pady=4)
        tk.Label(df, text="  ■ DEVICE", font=("Courier",8,"bold"), fg=C["accent2"], bg=C["panel2"]).pack(anchor="w")
        row = tk.Frame(df, bg=C["panel2"])
        row.pack(fill="x", padx=8)
        self.device_var = tk.StringVar(value=self.config.get("device_name",""))
        devices = mido.get_input_names() or ["Aucun appareil"]
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.TCombobox",
            fieldbackground=C["btn"], background=C["btn"],
            foreground=C["accent"], selectbackground=C["accent2"],
            arrowcolor=C["accent"])
        cb = ttk.Combobox(row, textvariable=self.device_var,
                          values=devices, width=24, state="readonly",
                          style="Dark.TCombobox")
        cb.pack(side="left")
        for d in devices:
            if any(x in d.lower() for x in ("mpk","mini","akai")):
                self.device_var.set(d); break
        self.status_dot = tk.Label(row, text="● OFFLINE", font=("Courier",9,"bold"),
                                   fg=C["red"], bg=C["panel2"])
        self.status_dot.pack(side="right", padx=6)

        make_sep(p)

        # Programme selector
        tk.Label(p, text="  ■ PROGRAMME", font=("Courier",8,"bold"), fg=C["accent2"], bg=C["bg"]).pack(anchor="w")
        self.prog_frame = tk.Frame(p, bg=C["bg"])
        self.prog_frame.pack(fill="x", pady=6)
        self.prog_btns = {}
        self._build_prog_btns()

        make_sep(p)

        # Controls
        ctrl = tk.Frame(p, bg=C["bg"])
        ctrl.pack(fill="x", pady=4)
        self.start_btn = tk.Button(ctrl, text="▶  START",
            font=("Courier",12,"bold"), bg=C["green"], fg=C["bg"],
            relief="flat", padx=16, pady=10, cursor="hand2",
            command=self._start)
        self.start_btn.pack(side="left", padx=(0,6))
        self.stop_btn = tk.Button(ctrl, text="■  STOP",
            font=("Courier",12,"bold"), bg=C["red"], fg="white",
            relief="flat", padx=16, pady=10, state="disabled", cursor="hand2",
            command=self._stop)
        self.stop_btn.pack(side="left")
        tk.Button(ctrl, text="⚙",
            font=("Courier",14), bg=C["btn"], fg=C["accent2"],
            relief="flat", padx=10, pady=8, cursor="hand2",
            command=self._open_wizard).pack(side="right")

        make_sep(p)

        # Console
        tk.Label(p, text="  ■ CONSOLE", font=("Courier",8,"bold"), fg=C["accent2"], bg=C["bg"]).pack(anchor="w")
        self.console = scrolledtext.ScrolledText(p,
            bg="#06060e", fg=C["accent"], font=("Courier",8),
            relief="flat", height=12, insertbackground=C["accent"],
            selectbackground=C["accent2"])
        self.console.pack(fill="both", expand=True, pady=(2,8))
        self.console.config(state="disabled")
        self._log(f"⬡ HexPad v{VERSION} ready")

    def _build_prog_btns(self):
        for w in self.prog_frame.winfo_children():
            w.destroy()
        self.prog_btns = {}
        for key, prog in self.config.get("programs", {}).items():
            mode = prog.get("mode", "debug")
            col  = MODE_COLORS.get(mode, C["dim"])
            f = tk.Frame(self.prog_frame, bg=C["btn"], padx=2, pady=2)
            f.pack(side="left", padx=3)
            b = tk.Button(f,
                text=f"  {key}  \n{mode[:6].upper()}",
                font=("Courier",8,"bold"),
                bg=C["btn"], fg=col,
                activebackground=col, activeforeground=C["bg"],
                relief="flat", bd=0, padx=8, pady=5, cursor="hand2",
                command=lambda k=key: self._select_program(k))
            b.pack()
            self.prog_btns[key] = (b, col)
        if self.config.get("programs"):
            self._select_program(list(self.config["programs"].keys())[0])

    def _build_right(self):
        p = self.right
        tk.Label(p, text="■ PRESET EDITOR", font=("Courier",9,"bold"),
                 fg=C["accent"], bg=C["panel"]).pack(anchor="w", padx=12, pady=(10,4))
        make_sep(p, C["accent"])

        # Preset name + mode
        top = tk.Frame(p, bg=C["panel"])
        top.pack(fill="x", padx=12, pady=4)
        tk.Label(top, text="Nom", font=("Courier",8), fg=C["dim"], bg=C["panel"]).grid(row=0,col=0, sticky="w")
        self.preset_name_var = tk.StringVar(value="Programme 1")
        tk.Entry(top, textvariable=self.preset_name_var,
                 bg=C["btn"], fg=C["accent"], font=("Courier",10),
                 relief="flat", insertbackground=C["accent"], width=20
                 ).grid(row=0, column=1, padx=8, sticky="w")
        tk.Label(top, text="Mode", font=("Courier",8), fg=C["dim"], bg=C["panel"]).grid(row=1,column=0, sticky="w", pady=4)
        self.preset_mode_var = tk.StringVar(value="gamepad")
        mode_cb = ttk.Combobox(top, textvariable=self.preset_mode_var,
                               values=["gamepad","websocket","macro","debug"],
                               width=12, state="readonly")
        mode_cb.grid(row=1, column=1, padx=8, sticky="w")
        mode_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_editor())
        tk.Label(top, text="WS URL", font=("Courier",8), fg=C["dim"], bg=C["panel"]).grid(row=2,column=0, sticky="w")
        self.ws_url_var = tk.StringVar(value="ws://localhost:8765")
        self.ws_entry = tk.Entry(top, textvariable=self.ws_url_var,
                  bg=C["btn"], fg=C["accent"], font=("Courier",9),
                  relief="flat", insertbackground=C["accent"], width=22)
        self.ws_entry.grid(row=2, column=1, padx=8, sticky="w", pady=2)

        make_sep(p)

        # Pad grid
        tk.Label(p, text="PADS  (Bank A: notes 36-43)", font=("Courier",8,"bold"),
                 fg=C["accent2"], bg=C["panel"]).pack(anchor="w", padx=12)
        self.pad_frame = tk.Frame(p, bg=C["panel"])
        self.pad_frame.pack(fill="x", padx=12, pady=4)
        self.pad_vars = {}
        self._build_pad_grid()

        make_sep(p)

        # Knob grid
        tk.Label(p, text="ENCODEURS  (CC 70-77)", font=("Courier",8,"bold"),
                 fg=C["accent2"], bg=C["panel"]).pack(anchor="w", padx=12)
        self.knob_frame = tk.Frame(p, bg=C["panel"])
        self.knob_frame.pack(fill="x", padx=12, pady=4)
        self.knob_vars = {}
        self._build_knob_grid()

        make_sep(p)

        # Joystick
        tk.Label(p, text="JOYSTICK", font=("Courier",8,"bold"),
                 fg=C["accent2"], bg=C["panel"]).pack(anchor="w", padx=12)
        joy = tk.Frame(p, bg=C["panel"])
        joy.pack(fill="x", padx=12, pady=4)
        tk.Label(joy, text="Pitch (X)", font=("Courier",8), fg=C["dim"], bg=C["panel"]).grid(row=0,column=0,sticky="w",pady=2)
        self.pitch_var = tk.StringVar(value="axis_x")
        ttk.Combobox(joy, textvariable=self.pitch_var, values=[""]+AXIS_OPTIONS, width=12, state="readonly").grid(row=0,column=1,padx=8)
        tk.Label(joy, text="Mod  (Y)", font=("Courier",8), fg=C["dim"], bg=C["panel"]).grid(row=1,column=0,sticky="w",pady=2)
        self.mod_var = tk.StringVar(value="axis_y")
        ttk.Combobox(joy, textvariable=self.mod_var, values=[""]+AXIS_OPTIONS, width=12, state="readonly").grid(row=1,column=1,padx=8)

        make_sep(p)

        # Buttons
        btns = tk.Frame(p, bg=C["panel"])
        btns.pack(fill="x", padx=12, pady=8)
        tk.Button(btns, text="💾  SAUVEGARDER",
            font=("Courier",9,"bold"), bg=C["accent"], fg=C["bg"],
            relief="flat", padx=12, pady=7, cursor="hand2",
            command=self._save_preset).pack(side="left", padx=(0,6))
        tk.Button(btns, text="+ NOUVEAU",
            font=("Courier",9), bg=C["btn"], fg=C["accent2"],
            relief="flat", padx=10, pady=7, cursor="hand2",
            command=self._new_preset).pack(side="left", padx=(0,6))
        tk.Button(btns, text="✕ SUPPR",
            font=("Courier",9), bg=C["btn"], fg=C["red"],
            relief="flat", padx=10, pady=7, cursor="hand2",
            command=self._delete_preset).pack(side="left")

    def _build_pad_grid(self):
        for w in self.pad_frame.winfo_children(): w.destroy()
        self.pad_vars = {}
        mode = self.preset_mode_var.get()
        opts = BTN_OPTIONS if mode == "gamepad" else MACRO_OPTIONS if mode == "macro" else []
        prog = self._get_current_preset()
        pads = prog.get("pads", {}) if prog else {}
        for i, note in enumerate(PAD_NOTES_A):
            col = i % 4
            row = i // 4
            cell = tk.Frame(self.pad_frame, bg=C["panel2"], padx=4, pady=4)
            cell.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")
            tk.Label(cell, text=f"PAD {i+1}\nnote {note}",
                     font=("Courier",7), fg=C["dim"], bg=C["panel2"]).pack()
            var = tk.StringVar(value=pads.get(str(note), ""))
            self.pad_vars[str(note)] = var
            if opts:
                cb = ttk.Combobox(cell, textvariable=var, values=[""] + opts,
                                  width=9, state="normal")
                cb.pack()
            else:
                tk.Entry(cell, textvariable=var, bg=C["btn"], fg=C["accent"],
                         font=("Courier",8), relief="flat", width=10).pack()

    def _build_knob_grid(self):
        for w in self.knob_frame.winfo_children(): w.destroy()
        self.knob_vars = {}
        mode = self.preset_mode_var.get()
        opts = AXIS_OPTIONS if mode == "gamepad" else []
        prog = self._get_current_preset()
        knobs = prog.get("knobs", {}) if prog else {}
        for i, cc in enumerate(KNOB_CC):
            cell = tk.Frame(self.knob_frame, bg=C["panel2"], padx=4, pady=4)
            cell.grid(row=0, column=i, padx=2, pady=2, sticky="nsew")
            tk.Label(cell, text=f"{KNOB_LABELS[i]}\nCC{cc}",
                     font=("Courier",7), fg=C["dim"], bg=C["panel2"]).pack()
            var = tk.StringVar(value=knobs.get(str(cc), ""))
            self.knob_vars[str(cc)] = var
            cb = ttk.Combobox(cell, textvariable=var, values=[""] + AXIS_OPTIONS,
                              width=7, state="normal")
            cb.pack()

    # ── Preset logic ──────────────────────────────────────────────────────────
    def _get_current_preset(self):
        key = getattr(self, "_current_prog", None)
        if key:
            return self.config["programs"].get(key)
        return None

    def _select_program(self, key):
        self._current_prog = key
        for k, (b, col) in self.prog_btns.items():
            is_sel = (k == key)
            b.config(bg=col if is_sel else C["btn"],
                     fg=C["bg"] if is_sel else col)
        prog = self.config["programs"].get(key, {})
        mode = prog.get("mode", "debug")
        self.preset_name_var.set(prog.get("name", f"Programme {key}"))
        self.preset_mode_var.set(mode)
        self.ws_url_var.set(prog.get("ws_url", "ws://localhost:8765"))
        self.pitch_var.set(prog.get("pitchwheel", ""))
        self.mod_var.set(prog.get("modwheel", ""))
        self._refresh_editor()

    def _refresh_editor(self):
        self._build_pad_grid()
        self._build_knob_grid()

    def _collect_preset(self):
        mode = self.preset_mode_var.get()
        prog = {"mode": mode, "name": self.preset_name_var.get()}
        if mode == "websocket":
            prog["ws_url"] = self.ws_url_var.get()
        pads = {n: v.get() for n, v in self.pad_vars.items() if v.get()}
        if pads:  prog["pads"]  = pads
        knobs = {c: v.get() for c, v in self.knob_vars.items() if v.get()}
        if knobs: prog["knobs"] = knobs
        if self.pitch_var.get(): prog["pitchwheel"] = self.pitch_var.get()
        if self.mod_var.get():   prog["modwheel"]   = self.mod_var.get()
        return prog

    def _save_preset(self):
        key = getattr(self, "_current_prog", None)
        if not key:
            return
        self.config["programs"][key] = self._collect_preset()
        self._save_config()
        self._build_prog_btns()
        self._select_program(key)
        self._log(f"[PRESET] Programme {key} sauvegarde")

    def _new_preset(self):
        existing = list(self.config["programs"].keys())
        new_key  = str(max(int(k) for k in existing) + 1) if existing else "1"
        self.config["programs"][new_key] = {"mode": "debug", "name": f"Programme {new_key}"}
        self._save_config()
        self._build_prog_btns()
        self._select_program(new_key)
        self._log(f"[PRESET] Nouveau programme {new_key} cree")

    def _delete_preset(self):
        key = getattr(self, "_current_prog", None)
        if not key or len(self.config["programs"]) <= 1:
            messagebox.showwarning("Suppression", "Impossible de supprimer le dernier preset.")
            return
        if messagebox.askyesno("Supprimer", f"Supprimer le programme {key} ?"):
            del self.config["programs"][key]
            self._save_config()
            self._build_prog_btns()
            first = list(self.config["programs"].keys())[0]
            self._select_program(first)
            self._log(f"[PRESET] Programme {key} supprime")

    # ── Log & run ─────────────────────────────────────────────────────────────
    def _log(self, msg):
        self.console.config(state="normal")
        self.console.insert("end", msg + "\n")
        self.console.see("end")
        self.console.config(state="disabled")

    def _build_bridge(self, prog):
        mode = prog.get("mode", "debug")
        if mode == "gamepad":   return GamepadBridge(prog), mode
        if mode == "websocket": return WebSocketBridge(prog.get("ws_url","ws://localhost:8765")), mode
        if mode == "macro":     return MacroBridge(prog), mode
        return None, "debug"

    def _start(self):
        key  = getattr(self, "_current_prog", "1")
        prog = self.config["programs"].get(key, {})
        self.config["device_name"] = self.device_var.get()
        bridge, mode = self._build_bridge(prog)
        d = Dispatcher()
        def gui_print(*args, **kwargs):
            self.root.after(0, self._log, " ".join(str(a) for a in args))
        builtins.print = gui_print
        d.set_bridge(bridge, mode)
        self.running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_dot.config(text="● ONLINE", fg=C["green"])
        self._log(f"\u25b6 mode={mode} | prog={key} | device={self.device_var.get()}")
        listener = MidiListener(self.config, d)
        def run():
            try:    listener.start()
            except Exception as e: self.root.after(0, self._log, f"[ERR] {e}")
            finally:
                builtins.print = self._orig_print
                self.root.after(0, self._on_stopped)
        threading.Thread(target=run, daemon=True).start()

    def _stop(self):
        self._log("■ Arret...")
        self._on_stopped()

    def _on_stopped(self):
        builtins.print = self._orig_print
        self.running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_dot.config(text="● OFFLINE", fg=C["red"])

    def _open_wizard(self):
        os.system("start cmd /k python wizard.py")


def main():
    root = tk.Tk()
    HexPadGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
