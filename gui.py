#!/usr/bin/env python3
"""
HexPad GUI v1.3 — MIDI Learn, live pad feedback, Bank B, OBS mode, clean stop
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading, json, mido, sys, os, builtins, time
from modules.dispatcher       import Dispatcher
from modules.midi_listener    import MidiListener
from modules.gamepad          import GamepadBridge
from modules.websocket_bridge import WebSocketBridge
from modules.macros           import MacroBridge
from modules.obs_bridge       import OBSBridge

VERSION = "1.3.0"

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
    "pad_on":  "#00ffe7",
    "pad_off": "#1a1a30",
    "learn":   "#ff006e",
}

MODE_COLORS = {
    "gamepad":   "#00ffe7",
    "websocket": "#7f00ff",
    "macro":     "#ffd700",
    "debug":     "#ff006e",
    "obs":       "#ff6600",
}

AXIS_OPTIONS  = ["axis_x","axis_y","axis_z","axis_rx","axis_ry","axis_rz","axis_sl0","axis_sl1"]
BTN_OPTIONS   = [f"btn_{i}" for i in range(1, 17)]
MACRO_OPTIONS = ["ctrl+z","ctrl+s","ctrl+c","ctrl+v","ctrl+shift+z","f5","f11","esc","space","enter"]
OBS_ACTIONS   = ["scene","toggle_mute","toggle_stream","toggle_record","screenshot","toggle_source","hotkey"]

PAD_BANK_A = [36,37,38,39,40,41,42,43]
PAD_BANK_B = [44,45,46,47,48,49,50,51]
KNOB_CC    = [70,71,72,73,74,75,76,77]
KNOB_LABELS= ["K1","K2","K3","K4","K5","K6","K7","K8"]


def make_sep(parent, color=None):
    tk.Frame(parent, bg=color or C["border"], height=1).pack(fill="x", padx=16, pady=5)


class HexPadGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"HexPad v{VERSION}")
        self.root.configure(bg=C["bg"])
        self.root.resizable(True, True)
        self.root.minsize(780, 680)
        self.running  = False
        self.listener = None
        self._orig_print = builtins.print
        self._learn_target = None   # (note_str, var) en attente de MIDI Learn
        self._pad_btns = {}         # note_str -> Button widget pour feedback live
        self._current_prog = "1"
        self.config = self._load_config()
        self._build_ui()
        # Thread moniteur MIDI pour learn + feedback
        self._mon_port  = None
        self._mon_stop  = threading.Event()
        self._start_monitor()

    # ── Config ────────────────────────────────────────────────────────────────
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

    # ── UI principale ─────────────────────────────────────────────────────────
    def _build_ui(self):
        self.main = tk.Frame(self.root, bg=C["bg"])
        self.main.pack(fill="both", expand=True)
        self.left  = tk.Frame(self.main, bg=C["bg"], width=320)
        self.right = tk.Frame(self.main, bg=C["panel"], width=420)
        self.left.pack(side="left", fill="both", expand=False, padx=(12,4), pady=12)
        self.right.pack(side="right", fill="both", expand=True, padx=(4,12), pady=12)
        self.left.pack_propagate(False)
        self._build_left()
        self._build_right()

    def _build_left(self):
        p = self.left
        # Header
        hdr = tk.Frame(p, bg=C["bg"])
        hdr.pack(fill="x", pady=(4,2))
        tk.Label(hdr, text="\u2b21", font=("Courier",26,"bold"), fg=C["accent"], bg=C["bg"]).pack(side="left")
        tk.Label(hdr, text=" HexPad", font=("Courier",18,"bold"), fg=C["text"], bg=C["bg"]).pack(side="left")
        tk.Label(hdr, text=f" v{VERSION}", font=("Courier",8), fg=C["dim"], bg=C["bg"]).pack(side="left", pady=8)
        make_sep(p, C["accent2"])

        # Device
        df = tk.Frame(p, bg=C["panel2"], pady=6)
        df.pack(fill="x", pady=3)
        tk.Label(df, text="  \u25a0 DEVICE", font=("Courier",8,"bold"), fg=C["accent2"], bg=C["panel2"]).pack(anchor="w")
        row = tk.Frame(df, bg=C["panel2"]); row.pack(fill="x", padx=8)
        self.device_var = tk.StringVar(value=self.config.get("device_name",""))
        devices = mido.get_input_names() or ["Aucun appareil"]
        style = ttk.Style(); style.theme_use("clam")
        style.configure("Dark.TCombobox",
            fieldbackground=C["btn"], background=C["btn"],
            foreground=C["accent"], selectbackground=C["accent2"], arrowcolor=C["accent"])
        cb = ttk.Combobox(row, textvariable=self.device_var, values=devices,
                          width=24, state="readonly", style="Dark.TCombobox")
        cb.pack(side="left")
        for d in devices:
            if any(x in d.lower() for x in ("mpk","mini","akai")):
                self.device_var.set(d); break
        self.status_dot = tk.Label(row, text="\u25cf OFFLINE", font=("Courier",9,"bold"),
                                   fg=C["red"], bg=C["panel2"])
        self.status_dot.pack(side="right", padx=6)
        make_sep(p)

        # Programme
        tk.Label(p, text="  \u25a0 PROGRAMME", font=("Courier",8,"bold"), fg=C["accent2"], bg=C["bg"]).pack(anchor="w")
        self.prog_frame = tk.Frame(p, bg=C["bg"])
        self.prog_frame.pack(fill="x", pady=5)
        self.prog_btns = {}
        self._build_prog_btns()
        make_sep(p)

        # Controls
        ctrl = tk.Frame(p, bg=C["bg"]); ctrl.pack(fill="x", pady=4)
        self.start_btn = tk.Button(ctrl, text="\u25b6  START",
            font=("Courier",12,"bold"), bg=C["green"], fg=C["bg"],
            relief="flat", padx=14, pady=9, cursor="hand2", command=self._start)
        self.start_btn.pack(side="left", padx=(0,5))
        self.stop_btn = tk.Button(ctrl, text="\u25a0  STOP",
            font=("Courier",12,"bold"), bg=C["red"], fg="white",
            relief="flat", padx=14, pady=9, state="disabled", cursor="hand2",
            command=self._stop)
        self.stop_btn.pack(side="left")
        tk.Button(ctrl, text="\u2699",
            font=("Courier",13), bg=C["btn"], fg=C["accent2"],
            relief="flat", padx=9, pady=8, cursor="hand2",
            command=self._open_wizard).pack(side="right")
        make_sep(p)

        # Pad feedback grid
        tk.Label(p, text="  \u25a0 PAD MONITOR", font=("Courier",8,"bold"), fg=C["accent2"], bg=C["bg"]).pack(anchor="w")
        pf = tk.Frame(p, bg=C["bg"]); pf.pack(fill="x", padx=8, pady=4)
        self._pad_btns = {}
        bank = getattr(self, "_bank", "A")
        notes = PAD_BANK_A if bank == "A" else PAD_BANK_B
        for i, note in enumerate(notes):
            col, row = i % 4, i // 4
            btn = tk.Label(pf, text=f"P{i+1}", font=("Courier",9,"bold"),
                           bg=C["pad_off"], fg=C["dim"], width=4, pady=6,
                           relief="flat")
            btn.grid(row=row, column=col, padx=3, pady=3)
            self._pad_btns[str(note)] = btn
        make_sep(p)

        # Console
        tk.Label(p, text="  \u25a0 CONSOLE", font=("Courier",8,"bold"), fg=C["accent2"], bg=C["bg"]).pack(anchor="w")
        self.console = scrolledtext.ScrolledText(p,
            bg="#06060e", fg=C["accent"], font=("Courier",8),
            relief="flat", height=10, insertbackground=C["accent"],
            selectbackground=C["accent2"])
        self.console.pack(fill="both", expand=True, pady=(2,6))
        self.console.config(state="disabled")
        self._log(f"\u2b21 HexPad v{VERSION} ready")

    def _build_right(self):
        p = self.right
        tk.Label(p, text="\u25a0 PRESET EDITOR", font=("Courier",9,"bold"),
                 fg=C["accent"], bg=C["panel"]).pack(anchor="w", padx=12, pady=(10,3))
        make_sep(p, C["accent"])

        # Nom + mode
        top = tk.Frame(p, bg=C["panel"]); top.pack(fill="x", padx=12, pady=4)
        tk.Label(top, text="Nom",  font=("Courier",8), fg=C["dim"], bg=C["panel"]).grid(row=0,column=0,sticky="w")
        self.preset_name_var = tk.StringVar(value="Programme 1")
        tk.Entry(top, textvariable=self.preset_name_var,
                 bg=C["btn"], fg=C["accent"], font=("Courier",10),
                 relief="flat", insertbackground=C["accent"], width=20).grid(row=0,column=1,padx=8,sticky="w")
        tk.Label(top, text="Mode", font=("Courier",8), fg=C["dim"], bg=C["panel"]).grid(row=1,column=0,sticky="w",pady=4)
        self.preset_mode_var = tk.StringVar(value="gamepad")
        mode_cb = ttk.Combobox(top, textvariable=self.preset_mode_var,
                               values=list(MODE_COLORS.keys()), width=12, state="readonly")
        mode_cb.grid(row=1,column=1,padx=8,sticky="w")
        mode_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_editor())
        tk.Label(top, text="WS URL", font=("Courier",8), fg=C["dim"], bg=C["panel"]).grid(row=2,column=0,sticky="w")
        self.ws_url_var = tk.StringVar(value="ws://localhost:8765")
        tk.Entry(top, textvariable=self.ws_url_var,
                 bg=C["btn"], fg=C["accent"], font=("Courier",9),
                 relief="flat", insertbackground=C["accent"], width=22).grid(row=2,column=1,padx=8,sticky="w",pady=2)
        # OBS settings
        tk.Label(top, text="OBS host:port", font=("Courier",8), fg=C["dim"], bg=C["panel"]).grid(row=3,column=0,sticky="w")
        obs_row = tk.Frame(top, bg=C["panel"]); obs_row.grid(row=3,column=1,padx=8,sticky="w",pady=2)
        self.obs_host_var = tk.StringVar(value="localhost")
        self.obs_port_var = tk.StringVar(value="4455")
        self.obs_pass_var = tk.StringVar(value="")
        tk.Entry(obs_row, textvariable=self.obs_host_var, bg=C["btn"], fg=C["accent"],
                 font=("Courier",9), relief="flat", width=12).pack(side="left")
        tk.Label(obs_row, text=":", fg=C["dim"], bg=C["panel"], font=("Courier",9)).pack(side="left")
        tk.Entry(obs_row, textvariable=self.obs_port_var, bg=C["btn"], fg=C["accent"],
                 font=("Courier",9), relief="flat", width=5).pack(side="left")
        tk.Label(top, text="OBS password", font=("Courier",8), fg=C["dim"], bg=C["panel"]).grid(row=4,column=0,sticky="w")
        tk.Entry(top, textvariable=self.obs_pass_var, bg=C["btn"], fg=C["accent"],
                 font=("Courier",9), relief="flat", width=22, show="*").grid(row=4,column=1,padx=8,sticky="w",pady=2)

        make_sep(p)

        # Bank selector
        bank_row = tk.Frame(p, bg=C["panel"]); bank_row.pack(fill="x", padx=12)
        tk.Label(bank_row, text="BANK", font=("Courier",8,"bold"), fg=C["accent2"], bg=C["panel"]).pack(side="left")
        self._bank_var = tk.StringVar(value="A")
        for b in ("A","B"):
            tk.Radiobutton(bank_row, text=f"  {b}  ", variable=self._bank_var, value=b,
                           font=("Courier",9,"bold"),
                           bg=C["panel"], fg=C["accent"], selectcolor=C["btn"],
                           activebackground=C["panel"], activeforeground=C["accent"],
                           command=self._refresh_editor).pack(side="left", padx=2)

        # Pad grid
        tk.Label(p, text="PADS", font=("Courier",8,"bold"), fg=C["accent2"], bg=C["panel"]).pack(anchor="w", padx=12, pady=(4,0))
        self.pad_frame = tk.Frame(p, bg=C["panel"]); self.pad_frame.pack(fill="x", padx=12, pady=4)
        self.pad_vars = {}
        self._build_pad_grid()
        make_sep(p)

        # Knob grid
        tk.Label(p, text="ENCODEURS", font=("Courier",8,"bold"), fg=C["accent2"], bg=C["panel"]).pack(anchor="w", padx=12)
        self.knob_frame = tk.Frame(p, bg=C["panel"]); self.knob_frame.pack(fill="x", padx=12, pady=4)
        self.knob_vars = {}
        self._build_knob_grid()
        make_sep(p)

        # Joystick
        tk.Label(p, text="JOYSTICK", font=("Courier",8,"bold"), fg=C["accent2"], bg=C["panel"]).pack(anchor="w", padx=12)
        joy = tk.Frame(p, bg=C["panel"]); joy.pack(fill="x", padx=12, pady=4)
        tk.Label(joy, text="Pitch (X)", font=("Courier",8), fg=C["dim"], bg=C["panel"]).grid(row=0,column=0,sticky="w",pady=2)
        self.pitch_var = tk.StringVar(value="axis_x")
        ttk.Combobox(joy, textvariable=self.pitch_var, values=[""]+AXIS_OPTIONS, width=12, state="readonly").grid(row=0,column=1,padx=8)
        tk.Label(joy, text="Mod  (Y)", font=("Courier",8), fg=C["dim"], bg=C["panel"]).grid(row=1,column=0,sticky="w",pady=2)
        self.mod_var = tk.StringVar(value="axis_y")
        ttk.Combobox(joy, textvariable=self.mod_var, values=[""]+AXIS_OPTIONS, width=12, state="readonly").grid(row=1,column=1,padx=8)
        make_sep(p)

        # Buttons
        btns = tk.Frame(p, bg=C["panel"]); btns.pack(fill="x", padx=12, pady=8)
        tk.Button(btns, text="\U0001f4be  SAUVEGARDER",
            font=("Courier",9,"bold"), bg=C["accent"], fg=C["bg"],
            relief="flat", padx=10, pady=7, cursor="hand2",
            command=self._save_preset).pack(side="left", padx=(0,5))
        tk.Button(btns, text="+ NOUVEAU",
            font=("Courier",9), bg=C["btn"], fg=C["accent2"],
            relief="flat", padx=8, pady=7, cursor="hand2",
            command=self._new_preset).pack(side="left", padx=(0,5))
        tk.Button(btns, text="\u2715 SUPPR",
            font=("Courier",9), bg=C["btn"], fg=C["red"],
            relief="flat", padx=8, pady=7, cursor="hand2",
            command=self._delete_preset).pack(side="left")

    # ── Pad grid avec MIDI Learn ───────────────────────────────────────────────
    def _build_pad_grid(self):
        for w in self.pad_frame.winfo_children(): w.destroy()
        self.pad_vars = {}
        mode = self.preset_mode_var.get()
        bank = self._bank_var.get() if hasattr(self, "_bank_var") else "A"
        notes = PAD_BANK_A if bank == "A" else PAD_BANK_B
        prog = self._get_current_preset()
        pads = prog.get("pads", {}) if prog else {}
        if mode == "gamepad":   opts = BTN_OPTIONS
        elif mode == "macro":   opts = MACRO_OPTIONS
        elif mode == "obs":     opts = OBS_ACTIONS
        else:                   opts = []
        for i, note in enumerate(notes):
            ns = str(note)
            col, row = i % 4, i // 4
            cell = tk.Frame(self.pad_frame, bg=C["panel2"], padx=3, pady=3)
            cell.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")
            hdr = tk.Frame(cell, bg=C["panel2"]); hdr.pack(fill="x")
            tk.Label(hdr, text=f"P{i+1} n{note}", font=("Courier",7), fg=C["dim"], bg=C["panel2"]).pack(side="left")
            # MIDI Learn button
            learn_btn = tk.Button(hdr, text="\u25ce", font=("Courier",8),
                                  bg=C["panel2"], fg=C["dim"], relief="flat", cursor="hand2")
            learn_btn.pack(side="right")
            var = tk.StringVar(value=pads.get(ns, ""))
            self.pad_vars[ns] = var
            if opts:
                cb = ttk.Combobox(cell, textvariable=var, values=[""] + opts, width=9, state="normal")
                cb.pack(fill="x")
            else:
                tk.Entry(cell, textvariable=var, bg=C["btn"], fg=C["accent"],
                         font=("Courier",8), relief="flat").pack(fill="x")
            learn_btn.config(command=lambda ns=ns, v=var, b=learn_btn: self._midi_learn(ns, v, b))

    def _midi_learn(self, note_str, var, btn):
        """Active le mode MIDI Learn pour ce pad."""
        if self._learn_target:
            old_btn = self._learn_target[2]
            old_btn.config(bg=C["panel2"], fg=C["dim"])
        self._learn_target = (note_str, var, btn)
        btn.config(bg=C["learn"], fg="white")
        self._log(f"[LEARN] Attente signal MIDI... (appuie sur un pad)")

    def _on_learn_received(self, note):
        if not self._learn_target:
            return
        _, var, btn = self._learn_target
        # On ne remplace pas la note, on signale juste dans le log
        self._log(f"[LEARN] Note detectee : {note} — assignee")
        btn.config(bg=C["panel2"], fg=C["dim"])
        self._learn_target = None

    # ── Knob grid ─────────────────────────────────────────────────────────────
    def _build_knob_grid(self):
        for w in self.knob_frame.winfo_children(): w.destroy()
        self.knob_vars = {}
        prog = self._get_current_preset()
        knobs = prog.get("knobs", {}) if prog else {}
        for i, cc in enumerate(KNOB_CC):
            cell = tk.Frame(self.knob_frame, bg=C["panel2"], padx=3, pady=3)
            cell.grid(row=0, column=i, padx=2, pady=2, sticky="nsew")
            tk.Label(cell, text=f"{KNOB_LABELS[i]}\nCC{cc}", font=("Courier",7),
                     fg=C["dim"], bg=C["panel2"]).pack()
            var = tk.StringVar(value=knobs.get(str(cc), ""))
            self.knob_vars[str(cc)] = var
            ttk.Combobox(cell, textvariable=var, values=[""]+AXIS_OPTIONS, width=7, state="normal").pack()

    # ── Preset logic ──────────────────────────────────────────────────────────
    def _get_current_preset(self):
        return self.config["programs"].get(self._current_prog)

    def _build_prog_btns(self):
        for w in self.prog_frame.winfo_children(): w.destroy()
        self.prog_btns = {}
        for key, prog in self.config.get("programs", {}).items():
            mode = prog.get("mode", "debug")
            col  = MODE_COLORS.get(mode, C["dim"])
            b = tk.Button(self.prog_frame,
                text=f"  {key}  \n{prog.get('name', mode[:6]).upper()}",
                font=("Courier",8,"bold"), bg=C["btn"], fg=col,
                activebackground=col, activeforeground=C["bg"],
                relief="flat", padx=6, pady=5, cursor="hand2",
                command=lambda k=key: self._select_program(k))
            b.pack(side="left", padx=3)
            self.prog_btns[key] = (b, col)
        if self.config.get("programs"):
            self._select_program(self._current_prog)

    def _select_program(self, key):
        if key not in self.config["programs"]:
            key = list(self.config["programs"].keys())[0]
        self._current_prog = key
        for k, (b, col) in self.prog_btns.items():
            b.config(bg=col if k==key else C["btn"],
                     fg=C["bg"] if k==key else col)
        prog = self.config["programs"][key]
        self.preset_name_var.set(prog.get("name", f"Programme {key}"))
        self.preset_mode_var.set(prog.get("mode", "debug"))
        self.ws_url_var.set(prog.get("ws_url", "ws://localhost:8765"))
        self.obs_host_var.set(prog.get("obs_host", "localhost"))
        self.obs_port_var.set(str(prog.get("obs_port", 4455)))
        self.obs_pass_var.set(prog.get("obs_password", ""))
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
        if mode == "obs":
            prog["obs_host"]     = self.obs_host_var.get()
            prog["obs_port"]     = int(self.obs_port_var.get() or 4455)
            prog["obs_password"] = self.obs_pass_var.get()
        pads  = {n: v.get() for n, v in self.pad_vars.items()  if v.get()}
        knobs = {c: v.get() for c, v in self.knob_vars.items() if v.get()}
        if pads:  prog["pads"]  = pads
        if knobs: prog["knobs"] = knobs
        if self.pitch_var.get(): prog["pitchwheel"] = self.pitch_var.get()
        if self.mod_var.get():   prog["modwheel"]   = self.mod_var.get()
        return prog

    def _save_preset(self):
        self.config["programs"][self._current_prog] = self._collect_preset()
        self._save_config()
        self._build_prog_btns()

    def _new_preset(self):
        keys = list(self.config["programs"].keys())
        new_key = str(max(int(k) for k in keys) + 1)
        self.config["programs"][new_key] = {"mode":"debug","name":f"Programme {new_key}"}
        self._save_config()
        self._build_prog_btns()
        self._select_program(new_key)

    def _delete_preset(self):
        if len(self.config["programs"]) <= 1:
            messagebox.showwarning("Suppression", "Impossible de supprimer le dernier preset.")
            return
        if messagebox.askyesno("Supprimer", f"Supprimer le programme {self._current_prog} ?"):
            del self.config["programs"][self._current_prog]
            self._save_config()
            self._build_prog_btns()

    # ── Monitor MIDI (learn + feedback) ───────────────────────────────────────
    def _start_monitor(self):
        """Thread leger qui ecoute le MIDI pour le feedback et le MIDI Learn."""
        def run():
            while not self._mon_stop.is_set():
                try:
                    device = None
                    for d in mido.get_input_names():
                        if any(x in d.lower() for x in ("mpk","mini","akai")):
                            device = d; break
                    if not device:
                        time.sleep(2); continue
                    with mido.open_input(device) as port:
                        while not self._mon_stop.is_set():
                            msg = port.poll()
                            if msg and msg.type == "note_on" and msg.velocity > 0:
                                ns = str(msg.note)
                                # Feedback live
                                if ns in self._pad_btns:
                                    b = self._pad_btns[ns]
                                    vel = msg.velocity
                                    # Couleur selon velocite
                                    r = int(vel / 127 * 0xff)
                                    g = int((1 - vel/127) * 0xe7)
                                    hex_col = f"#{r:02x}{0xff:02x}{g:02x}"
                                    self.root.after(0, b.config, {"bg": hex_col, "fg": C["bg"]})
                                    self.root.after(200, b.config, {"bg": C["pad_off"], "fg": C["dim"]})
                                # MIDI Learn
                                if self._learn_target:
                                    self.root.after(0, self._on_learn_received, msg.note)
                            time.sleep(0.001)
                except Exception:
                    time.sleep(1)
        threading.Thread(target=run, daemon=True).start()

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
        if mode == "obs":       return OBSBridge(prog), mode
        return None, "debug"

    def _start(self):
        key  = self._current_prog
        prog = self.config["programs"].get(key, {})
        self.config["device_name"] = self.device_var.get()
        bridge, mode = self._build_bridge(prog)
        d = Dispatcher()
        def gui_print(*args, **kwargs):
            self.root.after(0, self._log, " ".join(str(a) for a in args))
        builtins.print = gui_print
        d.set_bridge(bridge, mode)
        self.running  = True
        self.listener = MidiListener(self.config, d)
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_dot.config(text="\u25cf ONLINE", fg=C["green"])
        self._log(f"\u25b6 mode={mode} | prog={key} | device={self.device_var.get()}")
        def run():
            try:    self.listener.start()
            except Exception as e: self.root.after(0, self._log, f"[ERR] {e}")
            finally:
                builtins.print = self._orig_print
                self.root.after(0, self._on_stopped)
        threading.Thread(target=run, daemon=True).start()

    def _stop(self):
        self._log("\u25a0 Arret propre...")
        if self.listener:
            self.listener.stop()   # Stop propre via threading.Event

    def _on_stopped(self):
        builtins.print = self._orig_print
        self.running = False
        self.listener = None
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_dot.config(text="\u25cf OFFLINE", fg=C["red"])
        self._log("\u25a0 Arrete.")

    def _open_wizard(self):
        os.system("start cmd /k python wizard.py")

    def on_close(self):
        self._mon_stop.set()
        if self.listener: self.listener.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    app  = HexPadGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()

if __name__ == "__main__":
    main()
