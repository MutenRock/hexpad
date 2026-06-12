#!/usr/bin/env python3
"""
HexPad GUI v1.6.0 — Compact widget style + dark/light theme toggle
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import threading, json, mido, sys, os, builtins, time
from modules.dispatcher       import Dispatcher
from modules.midi_listener    import MidiListener
from modules.gamepad          import GamepadBridge
from modules.websocket_bridge import WebSocketBridge
from modules.macros           import MacroBridge
from modules.obs_bridge       import OBSBridge
from modules.game_profiles    import GameProfiles
from modules.combo_engine     import ComboEngine
from modules.themes           import DARK, LIGHT, MODE_COLORS, get as get_theme

VERSION = "1.6.0"
WIN_W, WIN_H = 420, 580

PAD_BANK_A  = [36,37,38,39,40,41,42,43]
PAD_BANK_B  = [44,45,46,47,48,49,50,51]
KNOB_CC     = [70,71,72,73,74,75,76,77]
KNOB_LABELS = ["K1","K2","K3","K4","K5","K6","K7","K8"]
AXIS_OPTIONS  = ["axis_x","axis_y","axis_z","axis_rx","axis_ry","axis_rz","axis_sl0","axis_sl1"]
BTN_OPTIONS   = [f"btn_{i}" for i in range(1,17)]
MACRO_OPTIONS = ["ctrl+z","ctrl+s","ctrl+c","ctrl+v","ctrl+shift+z","f5","f11","esc","space","enter"]
OBS_ACTIONS   = ["scene","toggle_mute","toggle_stream","toggle_record","screenshot","toggle_source","hotkey"]


# ─────────────────────────────────────────────────────────────────────────────
class HexPadGUI:
    def __init__(self, root):
        self.root         = root
        self._orig_print  = builtins.print
        self.running      = False
        self.listener     = None
        self._learn_target= None
        self._pad_btns    = {}
        self._current_prog= "1"
        self._editor_win  = None
        self.config       = self._load_config()
        self.profiles     = GameProfiles()
        self.combo_engine = ComboEngine()
        # Theme
        theme_name = self.config.get("theme", "dark")
        self.C = get_theme(theme_name)
        self._apply_window()
        self._build_ui()
        if self.config.get("programs"):
            self._select_program(self._current_prog)
        self._sync_profile()
        self._mon_stop = threading.Event()
        self._start_monitor()

    # ── Window setup ─────────────────────────────────────────────────────────
    def _apply_window(self):
        C = self.C
        self.root.title(f"HexPad v{VERSION}")
        self.root.configure(bg=C["bg"])
        self.root.resizable(False, True)
        self.root.minsize(WIN_W, WIN_H)
        self.root.geometry(f"{WIN_W}x{WIN_H}")

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

    # ── Theme toggle ─────────────────────────────────────────────────────────
    def _toggle_theme(self):
        new_name = "light" if self.C["name"] == "dark" else "dark"
        self.C = get_theme(new_name)
        self.config["theme"] = new_name
        self._save_config()
        # Full rebuild
        for w in self.root.winfo_children():
            w.destroy()
        self._apply_window()
        self._build_ui()
        if self.config.get("programs"):
            self._select_program(self._current_prog)
        self._sync_profile()

    # ── Style helpers ─────────────────────────────────────────────────────────
    def _style(self):
        C = self.C
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("H.TCombobox",
            fieldbackground=C["btn"], background=C["btn"],
            foreground=C["accent"], selectbackground=C["accent2"],
            arrowcolor=C["accent"])
        s.configure("H.TNotebook", background=C["bg"], borderwidth=0)
        s.configure("H.TNotebook.Tab",
            background=C["panel2"], foreground=C["dim"],
            font=("Courier",8,"bold"), padding=[10,4])
        s.map("H.TNotebook.Tab",
            background=[("selected", C["panel"])],
            foreground=[("selected", C["accent"])])

    def _sep(self, parent):
        tk.Frame(parent, bg=self.C["border"], height=1).pack(fill="x", padx=12, pady=4)

    def _label(self, parent, text, size=8, bold=False, color_key="dim", **kw):
        weight = "bold" if bold else "normal"
        return tk.Label(parent, text=text, font=("Courier",size,weight),
                        fg=self.C[color_key], bg=self.C["bg"], **kw)

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        C = self.C
        self._style()
        self.root.configure(bg=C["bg"])

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=C["panel"], pady=6)
        hdr.pack(fill="x")
        tk.Label(hdr, text="\u2b21", font=("Courier",18,"bold"),
                 fg=C["accent"], bg=C["panel"]).pack(side="left", padx=(10,2))
        tk.Label(hdr, text=f"HexPad", font=("Courier",13,"bold"),
                 fg=C["text"], bg=C["panel"]).pack(side="left")
        tk.Label(hdr, text=f" v{VERSION}", font=("Courier",7),
                 fg=C["dim"], bg=C["panel"]).pack(side="left")
        # Right side controls
        tk.Button(hdr, text="\u2715", font=("Courier",10,"bold"),
                  bg=C["panel"], fg=C["dim"], relief="flat", padx=8,
                  cursor="hand2", command=self.on_close).pack(side="right", padx=2)
        tk.Button(hdr, text="\u2013", font=("Courier",10,"bold"),
                  bg=C["panel"], fg=C["dim"], relief="flat", padx=8,
                  cursor="hand2", command=self.root.iconify).pack(side="right", padx=2)
        self._theme_btn = tk.Button(hdr, text=C["toggle_icon"],
                  font=("Courier",10), bg=C["panel"], fg=C["accent"],
                  relief="flat", padx=8, cursor="hand2",
                  command=self._toggle_theme)
        self._theme_btn.pack(side="right", padx=2)

        # ── Device + Profile row ───────────────────────────────────────────────
        dp = tk.Frame(self.root, bg=C["bg"], pady=4)
        dp.pack(fill="x", padx=10)
        self.status_dot = tk.Label(dp, text="\u25cf", font=("Courier",12,"bold"),
                                   fg=C["red"], bg=C["bg"])
        self.status_dot.pack(side="left", padx=(0,2))
        devices = mido.get_input_names() or ["Aucun"]
        self.device_var = tk.StringVar(value=self.config.get("device_name",""))
        dev_cb = ttk.Combobox(dp, textvariable=self.device_var, values=devices,
                              width=14, state="readonly", style="H.TCombobox")
        dev_cb.pack(side="left", padx=2)
        for d in devices:
            if any(x in d.lower() for x in ("mpk","mini","akai")):
                self.device_var.set(d); break
        tk.Label(dp, text="|", fg=C["border"], bg=C["bg"],
                 font=("Courier",10)).pack(side="left", padx=4)
        self.profile_var = tk.StringVar(value=self.profiles.active)
        self.profile_cb  = ttk.Combobox(dp, textvariable=self.profile_var,
                                        values=self.profiles.names,
                                        width=10, state="readonly",
                                        style="H.TCombobox")
        self.profile_cb.pack(side="left", padx=2)
        self.profile_cb.bind("<<ComboboxSelected>>", self._on_profile_changed)
        tk.Button(dp, text="\u2699", font=("Courier",10), bg=C["bg"],
                  fg=C["accent2"], relief="flat", padx=4, cursor="hand2",
                  command=self._open_editor).pack(side="right")

        self._sep(self.root)

        # ── Programme pills ───────────────────────────────────────────────────
        tk.Label(self.root, text="  PROGRAMME", font=("Courier",7,"bold"),
                 fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=12)
        prog_scroll = tk.Frame(self.root, bg=C["bg"])
        prog_scroll.pack(fill="x", padx=10, pady=4)
        self.prog_frame = prog_scroll
        self.prog_btns  = {}
        self._build_prog_btns()

        self._sep(self.root)

        # ── Pad Monitor ───────────────────────────────────────────────────────
        tk.Label(self.root, text="  PAD MONITOR", font=("Courier",7,"bold"),
                 fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=12)
        pf = tk.Frame(self.root, bg=C["bg"])
        pf.pack(padx=10, pady=4)
        self._pad_btns = {}
        for i, note in enumerate(PAD_BANK_A):
            col, row_idx = i % 4, i // 4
            btn = tk.Label(pf, text=f"P{i+1}",
                           font=("Courier",9,"bold"),
                           bg=C["pad_off"], fg=C["dim"],
                           width=5, pady=7, relief="flat")
            btn.grid(row=row_idx, column=col, padx=3, pady=3)
            self._pad_btns[str(note)] = btn

        self._sep(self.root)

        # ── Combos ────────────────────────────────────────────────────────────
        combo_hdr = tk.Frame(self.root, bg=C["bg"])
        combo_hdr.pack(fill="x", padx=10)
        tk.Label(combo_hdr, text="  COMBOS", font=("Courier",7,"bold"),
                 fg=C["combo"], bg=C["bg"]).pack(side="left")
        tk.Label(combo_hdr, text=self.profiles.active,
                 font=("Courier",7), fg=C["dim"], bg=C["bg"]).pack(side="left", padx=6)
        self.combo_frame = tk.Frame(self.root, bg=C["bg"])
        self.combo_frame.pack(fill="x", padx=10, pady=4)
        self._build_combo_buttons()

        self._sep(self.root)

        # ── Start/Stop ────────────────────────────────────────────────────────
        ctrl = tk.Frame(self.root, bg=C["bg"])
        ctrl.pack(fill="x", padx=10, pady=4)
        self.start_btn = tk.Button(ctrl, text="\u25b6\u25b6  START",
            font=("Courier",11,"bold"), bg=C["green"], fg=C["bg"],
            relief="flat", pady=10, cursor="hand2", command=self._start)
        self.start_btn.pack(fill="x", pady=(0,4))
        self.stop_btn = tk.Button(ctrl, text="\u25a0  STOP",
            font=("Courier",11,"bold"), bg=C["red"], fg="white",
            relief="flat", pady=8, state="disabled", cursor="hand2",
            command=self._stop)
        self.stop_btn.pack(fill="x")

        self._sep(self.root)

        # ── Console (3 lignes) ────────────────────────────────────────────────
        self.console = scrolledtext.ScrolledText(
            self.root, bg=C["console_bg"], fg=C["console_fg"],
            font=("Courier",7), relief="flat", height=4,
            insertbackground=C["accent"], selectbackground=C["accent2"])
        self.console.pack(fill="both", expand=True, padx=10, pady=(0,8))
        self.console.config(state="disabled")
        self._log(f"\u2b21 HexPad v{VERSION} ready — theme: {self.C['name']}")

    # ── Prog pills ────────────────────────────────────────────────────────────
    def _build_prog_btns(self):
        for w in self.prog_frame.winfo_children(): w.destroy()
        self.prog_btns = {}
        C = self.C
        for key, prog in self.config.get("programs",{}).items():
            mode = prog.get("mode","debug")
            col  = MODE_COLORS.get(mode, C["dim"])
            name = prog.get("name", mode)[:6].upper()
            b = tk.Button(self.prog_frame,
                text=f"{key}\n{name}",
                font=("Courier",7,"bold"), bg=C["btn"], fg=col,
                activebackground=col, activeforeground=C["bg"],
                relief="flat", padx=6, pady=5, width=5, cursor="hand2",
                command=lambda k=key: self._select_program(k))
            b.pack(side="left", padx=2)
            self.prog_btns[key] = (b, col)

    # ── Combo buttons ─────────────────────────────────────────────────────────
    def _build_combo_buttons(self):
        C = self.C
        for w in self.combo_frame.winfo_children(): w.destroy()
        combos = self.profiles.get_combos()
        if not combos:
            tk.Label(self.combo_frame, text="Aucun combo — editez game_profiles.json",
                     font=("Courier",7), fg=C["dim"], bg=C["bg"]).pack(anchor="w")
            return
        cols = 2
        for i, (key, combo) in enumerate(combos.items()):
            col_idx = i % cols
            row_idx = i // cols
            label = combo.get("label", key)
            seq   = combo.get("sequence", "")
            loop  = combo.get("loop", False)
            btn = tk.Button(self.combo_frame,
                text=f"\u25b6 {label}",
                font=("Courier",8,"bold"), bg=C["btn"], fg=C["combo"],
                activebackground=C["combo"], activeforeground=C["bg"],
                relief="flat", padx=6, pady=5, cursor="hand2",
                command=lambda s=seq, l=loop, lb=label: self._fire_combo(s,l,lb))
            btn.grid(row=row_idx, column=col_idx, padx=2, pady=2, sticky="ew")
        self.combo_frame.columnconfigure(0, weight=1)
        self.combo_frame.columnconfigure(1, weight=1)

    def _fire_combo(self, seq, loop, label):
        self._log(f"[COMBO] \u25b6 {label}")
        self.combo_engine.execute(seq, loop=loop)

    # ── Profile logic ─────────────────────────────────────────────────────────
    def _on_profile_changed(self, event=None):
        name = self.profile_var.get()
        self.profiles.active = name
        prof = self.profiles.get_profile(name)
        if prof:
            prog = prof.get("program","1")
            if prog in self.config["programs"]:
                self._select_program(prog)
        self._build_combo_buttons()
        # Update label
        for w in self.root.winfo_children():
            pass  # combo_hdr label updated via rebuild
        self._log(f"[PROFILE] {name}")

    def _sync_profile(self):
        self._build_combo_buttons()

    # ── Preset logic ──────────────────────────────────────────────────────────
    def _get_current_preset(self):
        return self.config["programs"].get(self._current_prog)

    def _select_program(self, key):
        if key not in self.config["programs"]:
            key = list(self.config["programs"].keys())[0]
        self._current_prog = key
        for k, (b, col) in self.prog_btns.items():
            b.config(bg=col if k==key else self.C["btn"],
                     fg=self.C["bg"] if k==key else col)
        self._log(f"[PROG] {key} — {self.config['programs'][key].get('name','')}")

    # ── Monitor MIDI ──────────────────────────────────────────────────────────
    def _start_monitor(self):
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
                            if msg and msg.type=="note_on" and msg.velocity>0:
                                ns = str(msg.note)
                                if ns in self._pad_btns:
                                    b   = self._pad_btns[ns]
                                    vel = msg.velocity
                                    r   = int(vel/127*0xff)
                                    g   = int((1-vel/127)*0xe7)
                                    hc  = f"#{r:02x}{0xff:02x}{g:02x}"
                                    self.root.after(0, b.config, {"bg":hc,"fg":self.C["bg"]})
                                    self.root.after(200, b.config,
                                                   {"bg":self.C["pad_off"],"fg":self.C["dim"]})
                                if self._learn_target:
                                    self.root.after(0, self._on_learn_received, msg.note)
                            time.sleep(0.001)
                except Exception:
                    time.sleep(1)
        threading.Thread(target=run, daemon=True).start()

    def _on_learn_received(self, note):
        if not self._learn_target: return
        _, var, btn = self._learn_target
        self._log(f"[LEARN] Note {note}")
        btn.config(bg=self.C["panel2"], fg=self.C["dim"])
        self._learn_target = None

    # ── Log ───────────────────────────────────────────────────────────────────
    def _log(self, msg):
        self.console.config(state="normal")
        self.console.insert("end", msg+"\n")
        self.console.see("end")
        self.console.config(state="disabled")

    # ── Start / Stop ──────────────────────────────────────────────────────────
    def _build_bridge(self, prog):
        mode = prog.get("mode","debug")
        if mode=="gamepad":   return GamepadBridge(prog), mode
        if mode=="websocket": return WebSocketBridge(prog.get("ws_url","ws://localhost:8765")), mode
        if mode=="macro":     return MacroBridge(prog), mode
        if mode=="obs":       return OBSBridge(prog), mode
        return None, "debug"

    def _start(self):
        key  = self._current_prog
        prog = self.config["programs"].get(key, {})
        self.config["device_name"] = self.device_var.get()
        bridge, mode = self._build_bridge(prog)
        d = Dispatcher()
        def gui_print(*args, **kw):
            self.root.after(0, self._log, " ".join(str(a) for a in args))
        builtins.print = gui_print
        d.set_bridge(bridge, mode)
        self.running  = True
        self.listener = MidiListener(self.config, d)
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_dot.config(fg=self.C["green"])
        self._log(f"\u25b6 {mode} | prog {key} | {self.device_var.get()}")
        def run():
            try:    self.listener.start()
            except Exception as e:
                self.root.after(0, self._log, f"[ERR] {e}")
            finally:
                builtins.print = self._orig_print
                self.root.after(0, self._on_stopped)
        threading.Thread(target=run, daemon=True).start()

    def _stop(self):
        self._log("\u25a0 Arret...")
        if self.listener: self.listener.stop()

    def _on_stopped(self):
        builtins.print = self._orig_print
        self.running   = False
        self.listener  = None
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_dot.config(fg=self.C["red"])
        self._log("\u25a0 Arrete.")

    # ── Editor window (Preset Editor) ─────────────────────────────────────────
    def _open_editor(self):
        if self._editor_win and self._editor_win.winfo_exists():
            self._editor_win.lift(); return
        win = tk.Toplevel(self.root)
        win.title("HexPad — Preset Editor")
        win.configure(bg=self.C["bg"])
        win.geometry("480x620")
        win.resizable(True, True)
        self._editor_win = win
        self._build_editor(win)

    def _build_editor(self, win):
        C = self.C
        tk.Label(win, text="\u25a0 PRESET EDITOR", font=("Courier",9,"bold"),
                 fg=C["accent"], bg=C["bg"]).pack(anchor="w", padx=12, pady=(10,3))
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=12, pady=2)

        top = tk.Frame(win, bg=C["bg"]); top.pack(fill="x", padx=12, pady=6)
        def row(r, label, widget_fn):
            tk.Label(top, text=label, font=("Courier",8), fg=C["dim"],
                     bg=C["bg"]).grid(row=r, column=0, sticky="w", pady=3)
            widget_fn(top, r)

        self.preset_name_var = tk.StringVar()
        self.preset_mode_var = tk.StringVar(value="gamepad")
        self.ws_url_var      = tk.StringVar(value="ws://localhost:8765")
        self.obs_host_var    = tk.StringVar(value="localhost")
        self.obs_port_var    = tk.StringVar(value="4455")
        self.obs_pass_var    = tk.StringVar(value="")
        self.pitch_var       = tk.StringVar(value="axis_x")
        self.mod_var         = tk.StringVar(value="axis_y")

        def entry(parent, r, var, w=22):
            tk.Entry(parent, textvariable=var, bg=C["btn"], fg=C["accent"],
                     font=("Courier",9), relief="flat",
                     insertbackground=C["accent"], width=w).grid(
                row=r, column=1, padx=8, sticky="w")
        def combo_w(parent, r, var, values, w=14):
            ttk.Combobox(parent, textvariable=var, values=values,
                         width=w, state="readonly",
                         style="H.TCombobox").grid(row=r, column=1, padx=8, sticky="w")

        row(0, "Nom",          lambda p,r: entry(p,r,self.preset_name_var))
        row(1, "Mode",         lambda p,r: combo_w(p,r,self.preset_mode_var,list(MODE_COLORS.keys())))
        row(2, "WS URL",       lambda p,r: entry(p,r,self.ws_url_var))
        row(3, "OBS host",     lambda p,r: entry(p,r,self.obs_host_var,14))
        row(4, "OBS port",     lambda p,r: entry(p,r,self.obs_port_var,6))
        row(5, "OBS password", lambda p,r: entry(p,r,self.obs_pass_var))
        row(6, "Pitch (X)",    lambda p,r: combo_w(p,r,self.pitch_var,[""]+AXIS_OPTIONS))
        row(7, "Mod   (Y)",    lambda p,r: combo_w(p,r,self.mod_var,[""]+AXIS_OPTIONS))

        # Sync mode -> refresh pads
        for cb in top.winfo_children():
            if isinstance(cb, ttk.Combobox) and cb.cget("textvariable") == str(self.preset_mode_var):
                cb.bind("<<ComboboxSelected>>", lambda e: self._editor_refresh(win))

        # Hint
        tk.Label(win,
            text="  Tokens macro : j,k,l  |  j+k  |  50 (ms)  |  ctrl+z",
            font=("Courier",7), fg=C["dim"], bg=C["bg"]).pack(anchor="w", padx=12)
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=12, pady=4)

        # Bank toggle
        bank_row = tk.Frame(win, bg=C["bg"]); bank_row.pack(fill="x", padx=12)
        tk.Label(bank_row, text="BANK", font=("Courier",8,"bold"),
                 fg=C["accent2"], bg=C["bg"]).pack(side="left")
        self._bank_var = tk.StringVar(value="A")
        for b in ("A","B"):
            tk.Radiobutton(bank_row, text=f"  {b}  ", variable=self._bank_var, value=b,
                           font=("Courier",9,"bold"), bg=C["bg"], fg=C["accent"],
                           selectcolor=C["btn"], activebackground=C["bg"],
                           command=lambda: self._editor_refresh(win)).pack(side="left", padx=2)

        # Pad grid
        tk.Label(win, text="PADS", font=("Courier",8,"bold"),
                 fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=12, pady=(4,0))
        self.pad_frame = tk.Frame(win, bg=C["bg"])
        self.pad_frame.pack(fill="x", padx=12, pady=4)
        self.pad_vars = {}
        self._build_pad_grid()

        # Knob grid
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=12, pady=4)
        tk.Label(win, text="ENCODEURS", font=("Courier",8,"bold"),
                 fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=12)
        self.knob_frame = tk.Frame(win, bg=C["bg"])
        self.knob_frame.pack(fill="x", padx=12, pady=4)
        self.knob_vars = {}
        self._build_knob_grid()

        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=12, pady=6)

        # Save/New/Del
        btns = tk.Frame(win, bg=C["bg"]); btns.pack(fill="x", padx=12, pady=6)
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

        # Load current preset into editor fields
        self._load_preset_into_editor()

    def _load_preset_into_editor(self):
        prog = self._get_current_preset()
        if not prog: return
        self.preset_name_var.set(prog.get("name", f"Programme {self._current_prog}"))
        self.preset_mode_var.set(prog.get("mode", "debug"))
        self.ws_url_var.set(prog.get("ws_url","ws://localhost:8765"))
        self.obs_host_var.set(prog.get("obs_host","localhost"))
        self.obs_port_var.set(str(prog.get("obs_port",4455)))
        self.obs_pass_var.set(prog.get("obs_password",""))
        self.pitch_var.set(prog.get("pitchwheel",""))
        self.mod_var.set(prog.get("modwheel",""))
        self._build_pad_grid()
        self._build_knob_grid()

    def _editor_refresh(self, win=None):
        self._build_pad_grid()
        self._build_knob_grid()

    # ── Pad grid ──────────────────────────────────────────────────────────────
    def _build_pad_grid(self):
        C = self.C
        if not hasattr(self, "pad_frame"): return
        for w in self.pad_frame.winfo_children(): w.destroy()
        self.pad_vars = {}
        mode  = self.preset_mode_var.get() if hasattr(self,"preset_mode_var") else "gamepad"
        bank  = self._bank_var.get()        if hasattr(self,"_bank_var")        else "A"
        notes = PAD_BANK_A if bank=="A" else PAD_BANK_B
        prog  = self._get_current_preset()
        pads  = prog.get("pads",{}) if prog else {}
        if mode=="gamepad":  opts = BTN_OPTIONS
        elif mode=="macro":  opts = MACRO_OPTIONS
        elif mode=="obs":    opts = OBS_ACTIONS
        else:                opts = []
        for i, note in enumerate(notes):
            ns = str(note)
            col, row_idx = i%4, i//4
            cell = tk.Frame(self.pad_frame, bg=C["panel2"], padx=3, pady=3)
            cell.grid(row=row_idx, column=col, padx=3, pady=3, sticky="nsew")
            hrow = tk.Frame(cell, bg=C["panel2"]); hrow.pack(fill="x")
            tk.Label(hrow, text=f"P{i+1} n{note}", font=("Courier",7),
                     fg=C["dim"], bg=C["panel2"]).pack(side="left")
            lb = tk.Button(hrow, text="\u25ce", font=("Courier",8),
                           bg=C["panel2"], fg=C["dim"], relief="flat", cursor="hand2")
            lb.pack(side="right")
            var = tk.StringVar(value=pads.get(ns,""))
            self.pad_vars[ns] = var
            if opts:
                ttk.Combobox(cell, textvariable=var, values=[""] + opts,
                             width=9, state="normal",
                             style="H.TCombobox").pack(fill="x")
            else:
                tk.Entry(cell, textvariable=var, bg=C["btn"], fg=C["accent"],
                         font=("Courier",8), relief="flat").pack(fill="x")
            lb.config(command=lambda ns=ns,v=var,b=lb: self._midi_learn(ns,v,b))

    def _midi_learn(self, note_str, var, btn):
        if self._learn_target:
            self._learn_target[2].config(bg=self.C["panel2"], fg=self.C["dim"])
        self._learn_target = (note_str, var, btn)
        btn.config(bg=self.C["learn"], fg="white")
        self._log("[LEARN] Attente MIDI...")

    # ── Knob grid ─────────────────────────────────────────────────────────────
    def _build_knob_grid(self):
        C = self.C
        if not hasattr(self, "knob_frame"): return
        for w in self.knob_frame.winfo_children(): w.destroy()
        self.knob_vars = {}
        prog  = self._get_current_preset()
        knobs = prog.get("knobs",{}) if prog else {}
        for i, cc in enumerate(KNOB_CC):
            cell = tk.Frame(self.knob_frame, bg=C["panel2"], padx=3, pady=3)
            cell.grid(row=0, column=i, padx=2, pady=2, sticky="nsew")
            tk.Label(cell, text=f"{KNOB_LABELS[i]}\nCC{cc}", font=("Courier",7),
                     fg=C["dim"], bg=C["panel2"]).pack()
            var = tk.StringVar(value=knobs.get(str(cc),""))
            self.knob_vars[str(cc)] = var
            ttk.Combobox(cell, textvariable=var, values=[""]+AXIS_OPTIONS,
                         width=7, state="normal",
                         style="H.TCombobox").pack()

    # ── Preset CRUD ───────────────────────────────────────────────────────────
    def _collect_preset(self):
        mode = self.preset_mode_var.get()
        prog = {"mode": mode, "name": self.preset_name_var.get()}
        if mode=="websocket": prog["ws_url"]      = self.ws_url_var.get()
        if mode=="obs":
            prog["obs_host"]     = self.obs_host_var.get()
            prog["obs_port"]     = int(self.obs_port_var.get() or 4455)
            prog["obs_password"] = self.obs_pass_var.get()
        pads  = {n: v.get() for n,v in self.pad_vars.items()  if v.get()}
        knobs = {c: v.get() for c,v in self.knob_vars.items() if v.get()}
        if pads:  prog["pads"]  = pads
        if knobs: prog["knobs"] = knobs
        if self.pitch_var.get(): prog["pitchwheel"] = self.pitch_var.get()
        if self.mod_var.get():   prog["modwheel"]   = self.mod_var.get()
        return prog

    def _save_preset(self):
        self.config["programs"][self._current_prog] = self._collect_preset()
        self._save_config()
        self._build_prog_btns()
        self._select_program(self._current_prog)
        self._log(f"[CONFIG] Preset {self._current_prog} sauvegarde")

    def _new_preset(self):
        keys = list(self.config["programs"].keys())
        new_key = str(max(int(k) for k in keys)+1)
        self.config["programs"][new_key] = {"mode":"debug","name":f"Programme {new_key}"}
        self._save_config()
        self._build_prog_btns()
        self._select_program(new_key)
        self._load_preset_into_editor()

    def _delete_preset(self):
        if len(self.config["programs"]) <= 1:
            messagebox.showwarning("Suppression","Impossible de supprimer le dernier preset.")
            return
        if messagebox.askyesno("Supprimer",f"Supprimer le programme {self._current_prog} ?"):
            del self.config["programs"][self._current_prog]
            self._save_config()
            self._build_prog_btns()

    # ── Close ─────────────────────────────────────────────────────────────────
    def _open_wizard(self):
        os.system("start cmd /k python wizard.py")

    def on_close(self):
        self._mon_stop.set()
        self.combo_engine.stop()
        if self.listener: self.listener.stop()
        self.root.destroy()


# ─────────────────────────────────────────────────────────────────────────────
def main():
    root = tk.Tk()
    app  = HexPadGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()

if __name__ == "__main__":
    main()
