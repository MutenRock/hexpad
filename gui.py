#!/usr/bin/env python3
"""
HexPad GUI v1.8.0 — Mode selector at launch + larger windows
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

VERSION = "1.8.0"

# Window modes  (w, h)
WINDOW_MODES = {
    "COMPACT": (480, 680),
    "NORMAL":  (780, 860),
    "WIDE":    (1060, 720),
}

PAD_BANK_A  = [36,37,38,39,40,41,42,43]
PAD_BANK_B  = [44,45,46,47,48,49,50,51]
KNOB_CC     = [70,71,72,73,74,75,76,77]
KNOB_LABELS = ["K1","K2","K3","K4","K5","K6","K7","K8"]
AXIS_OPTIONS  = ["axis_x","axis_y","axis_z","axis_rx","axis_ry","axis_rz","axis_sl0","axis_sl1"]
BTN_OPTIONS   = [f"btn_{i}" for i in range(1,17)]
MACRO_OPTIONS = ["ctrl+z","ctrl+s","ctrl+c","ctrl+v","ctrl+shift+z","f5","f11","esc","space","enter"]
OBS_ACTIONS   = ["scene","toggle_mute","toggle_stream","toggle_record","screenshot","toggle_source","hotkey"]


# ─────────────────────────────────────────────────────────────────────────────
# Mode selector dialog shown at launch
# ─────────────────────────────────────────────────────────────────────────────
def ask_window_mode(default_mode: str, theme_colors: dict) -> str | None:
    """Show a small dialog to pick COMPACT / NORMAL / WIDE.
    Returns chosen mode string, or None if cancelled."""
    C = theme_colors
    dialog = tk.Tk()
    dialog.title("HexPad — Choisir le mode")
    dialog.resizable(False, False)
    dialog.configure(bg=C["bg"])

    # Center on screen
    dw, dh = 360, 260
    dialog.geometry(f"{dw}x{dh}+{(dialog.winfo_screenwidth()-dw)//2}+{(dialog.winfo_screenheight()-dh)//2}")

    # Header
    hdr = tk.Frame(dialog, bg=C["panel"], pady=8)
    hdr.pack(fill="x")
    tk.Label(hdr, text="⬡", font=("Courier",22,"bold"), fg=C["accent"], bg=C["panel"]).pack(side="left", padx=(12,4))
    tk.Label(hdr, text=f"HexPad  v{VERSION}", font=("Courier",12,"bold"), fg=C["text"], bg=C["panel"]).pack(side="left")

    tk.Label(dialog, text="Choisir le mode d'affichage", font=("Courier",9),
             fg=C["dim"], bg=C["bg"]).pack(pady=(14,8))

    chosen = tk.StringVar(value=default_mode)

    desc = {
        "COMPACT": f"480 × 680  —  Widget compact",
        "NORMAL":  f"780 × 860  —  Preset Editor intégré",
        "WIDE":    f"1060 × 720 —  3 colonnes",
    }

    btn_frame = tk.Frame(dialog, bg=C["bg"])
    btn_frame.pack(pady=4)

    mode_btns = {}
    for mode in ("COMPACT","NORMAL","WIDE"):
        is_sel = mode == default_mode
        col = C["accent"] if is_sel else C["btn"]
        fg  = C["bg"]     if is_sel else C["text"]
        b = tk.Button(btn_frame,
            text=f"  {mode}\n  {desc[mode]}",
            font=("Courier",9,"bold" if is_sel else "normal"),
            bg=col, fg=fg, relief="flat", padx=16, pady=10,
            cursor="hand2", anchor="w", justify="left",
            command=lambda m=mode: _select(m))
        b.pack(fill="x", pady=3, ipady=2)
        mode_btns[mode] = b

    def _select(m):
        chosen.set(m)
        for k, btn in mode_btns.items():
            sel = k == m
            btn.config(
                bg=C["accent"] if sel else C["btn"],
                fg=C["bg"]     if sel else C["text"],
                font=("Courier",9,"bold" if sel else "normal"),
            )

    tk.Frame(dialog, bg=C["border"], height=1).pack(fill="x", padx=12, pady=8)

    ok_btn = tk.Button(dialog, text="▶  Lancer",
        font=("Courier",10,"bold"), bg=C["green"], fg=C["bg"],
        relief="flat", padx=20, pady=8, cursor="hand2",
        command=dialog.destroy)
    ok_btn.pack()

    dialog.mainloop()
    return chosen.get()


# ─────────────────────────────────────────────────────────────────────────────
class HexPadGUI:
    def __init__(self, root, window_mode="NORMAL"):
        self.root         = root
        self._orig_print  = builtins.print
        self.running      = False
        self.listener     = None
        self._learn_target= None
        self._pad_btns    = {}
        self._current_prog= "1"
        self._editor_win  = None
        self.window_mode  = window_mode
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
        w, h = WINDOW_MODES.get(self.window_mode, WINDOW_MODES["NORMAL"])
        self.root.title(f"HexPad v{VERSION}  [{self.window_mode}]")
        self.root.configure(bg=C["bg"])
        self.root.resizable(True, True)
        self.root.minsize(w, h)
        self.root.geometry(f"{w}x{h}")

    # ── Config ────────────────────────────────────────────────────────────────
    def _load_config(self):
        try:
            with open("config.json") as f:
                return json.load(f)
        except Exception as e:
            messagebox.showerror("Erreur config", str(e))
            sys.exit(1)

    def _save_config(self):
        self.config["window_mode"] = self.window_mode
        with open("config.json", "w") as f:
            json.dump(self.config, f, indent=2)

    # ── Theme toggle ─────────────────────────────────────────────────────────
    def _toggle_theme(self):
        new_name = "light" if self.C["name"] == "dark" else "dark"
        self.C = get_theme(new_name)
        self.config["theme"] = new_name
        self._save_config()
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

        if self.window_mode == "WIDE":
            self._build_wide()
        elif self.window_mode == "NORMAL":
            self._build_normal()
        else:
            self._build_compact()

    # ─── COMPACT layout ───────────────────────────────────────────────────────
    def _build_compact(self):
        C = self.C
        self._build_header(self.root)
        self._build_device_row(self.root)
        self._sep(self.root)
        self._build_prog_section(self.root)
        self._sep(self.root)
        self._build_pad_monitor(self.root)
        self._sep(self.root)
        self._build_combos(self.root)
        self._sep(self.root)
        self._build_start_stop(self.root)
        self._sep(self.root)
        self._build_console(self.root)

    # ─── NORMAL layout ────────────────────────────────────────────────────────
    def _build_normal(self):
        C = self.C
        self._build_header(self.root)

        paned = tk.PanedWindow(self.root, orient="horizontal",
                               bg=C["bg"], sashwidth=4, sashrelief="flat")
        paned.pack(fill="both", expand=True)

        left = tk.Frame(paned, bg=C["bg"])
        paned.add(left, minsize=380)

        self._build_device_row(left)
        self._sep(left)
        self._build_prog_section(left)
        self._sep(left)
        self._build_pad_monitor(left)
        self._sep(left)
        self._build_combos(left)
        self._sep(left)
        self._build_start_stop(left)
        self._sep(left)
        self._build_console(left)

        right = tk.Frame(paned, bg=C["bg"])
        paned.add(right, minsize=360)
        self._build_inline_editor(right)

    # ─── WIDE layout ──────────────────────────────────────────────────────────
    def _build_wide(self):
        C = self.C
        self._build_header(self.root)

        cols = tk.Frame(self.root, bg=C["bg"])
        cols.pack(fill="both", expand=True)
        cols.columnconfigure(0, weight=1, minsize=300)
        cols.columnconfigure(1, weight=2, minsize=380)
        cols.columnconfigure(2, weight=2, minsize=340)

        # Column 1: controls
        col1 = tk.Frame(cols, bg=C["bg"])
        col1.grid(row=0, column=0, sticky="nsew", padx=(6,2), pady=6)
        self._build_device_row(col1)
        self._sep(col1)
        self._build_prog_section(col1)
        self._sep(col1)
        self._build_pad_monitor(col1)
        self._sep(col1)
        self._build_start_stop(col1)

        # Column 2: combos + console
        col2 = tk.Frame(cols, bg=C["bg"])
        col2.grid(row=0, column=1, sticky="nsew", padx=2, pady=6)
        self._build_combos(col2)
        self._sep(col2)
        self._build_console(col2)

        # Column 3: inline editor
        col3 = tk.Frame(cols, bg=C["bg"])
        col3.grid(row=0, column=2, sticky="nsew", padx=(2,6), pady=6)
        self._build_inline_editor(col3)

    # ─── Shared sections ──────────────────────────────────────────────────────
    def _build_header(self, parent):
        C = self.C
        hdr = tk.Frame(parent, bg=C["panel"], pady=7)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⬡", font=("Courier",20,"bold"),
                 fg=C["accent"], bg=C["panel"]).pack(side="left", padx=(10,2))
        tk.Label(hdr, text="HexPad", font=("Courier",14,"bold"),
                 fg=C["text"], bg=C["panel"]).pack(side="left")
        tk.Label(hdr, text=f" v{VERSION}", font=("Courier",7),
                 fg=C["dim"], bg=C["panel"]).pack(side="left")
        # Mode badge
        tk.Label(hdr, text=f"[{self.window_mode}]", font=("Courier",7,"bold"),
                 fg=C["accent2"], bg=C["panel"]).pack(side="left", padx=6)

        tk.Button(hdr, text="✕", font=("Courier",10,"bold"),
                  bg=C["panel"], fg=C["dim"], relief="flat", padx=8,
                  cursor="hand2", command=self.on_close).pack(side="right", padx=2)
        tk.Button(hdr, text="–", font=("Courier",10,"bold"),
                  bg=C["panel"], fg=C["dim"], relief="flat", padx=8,
                  cursor="hand2", command=self.root.iconify).pack(side="right", padx=2)
        self._theme_btn = tk.Button(hdr, text=C["toggle_icon"],
                  font=("Courier",10), bg=C["panel"], fg=C["accent"],
                  relief="flat", padx=8, cursor="hand2",
                  command=self._toggle_theme)
        self._theme_btn.pack(side="right", padx=2)

    def _build_device_row(self, parent):
        C = self.C
        dp = tk.Frame(parent, bg=C["bg"], pady=4)
        dp.pack(fill="x", padx=10)
        self.status_dot = tk.Label(dp, text="●", font=("Courier",12,"bold"),
                                   fg=C["red"], bg=C["bg"])
        self.status_dot.pack(side="left", padx=(0,2))
        devices = mido.get_input_names() or ["Aucun"]
        self.device_var = tk.StringVar(value=self.config.get("device_name",""))
        dev_cb = ttk.Combobox(dp, textvariable=self.device_var, values=devices,
                              width=16, state="readonly", style="H.TCombobox")
        dev_cb.pack(side="left", padx=2)
        for d in devices:
            if any(x in d.lower() for x in ("mpk","mini","akai")):
                self.device_var.set(d); break
        tk.Label(dp, text="|", fg=C["border"], bg=C["bg"],
                 font=("Courier",10)).pack(side="left", padx=4)
        self.profile_var = tk.StringVar(value=self.profiles.active)
        self.profile_cb  = ttk.Combobox(dp, textvariable=self.profile_var,
                                        values=self.profiles.names,
                                        width=12, state="readonly",
                                        style="H.TCombobox")
        self.profile_cb.pack(side="left", padx=2)
        self.profile_cb.bind("<<ComboboxSelected>>", self._on_profile_changed)
        if self.window_mode == "COMPACT":
            tk.Button(dp, text="⚙", font=("Courier",10), bg=C["bg"],
                      fg=C["accent2"], relief="flat", padx=4, cursor="hand2",
                      command=self._open_editor).pack(side="right")

    def _build_prog_section(self, parent):
        C = self.C
        tk.Label(parent, text="  PROGRAMME", font=("Courier",7,"bold"),
                 fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=12)
        self.prog_frame = tk.Frame(parent, bg=C["bg"])
        self.prog_frame.pack(fill="x", padx=10, pady=4)
        self.prog_btns = {}
        self._build_prog_btns()

    def _build_pad_monitor(self, parent):
        C = self.C
        tk.Label(parent, text="  PAD MONITOR", font=("Courier",7,"bold"),
                 fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=12)
        pf = tk.Frame(parent, bg=C["bg"])
        pf.pack(padx=10, pady=4)
        self._pad_btns = {}
        for i, note in enumerate(PAD_BANK_A):
            col, row_idx = i % 4, i // 4
            btn = tk.Label(pf, text=f"P{i+1}",
                           font=("Courier",10,"bold"),
                           bg=C["pad_off"], fg=C["dim"],
                           width=6, pady=9, relief="flat")
            btn.grid(row=row_idx, column=col, padx=3, pady=3)
            self._pad_btns[str(note)] = btn

    def _build_combos(self, parent):
        C = self.C
        combo_hdr = tk.Frame(parent, bg=C["bg"])
        combo_hdr.pack(fill="x", padx=10)
        tk.Label(combo_hdr, text="  COMBOS", font=("Courier",7,"bold"),
                 fg=C["combo"], bg=C["bg"]).pack(side="left")
        tk.Label(combo_hdr, text=self.profiles.active,
                 font=("Courier",7), fg=C["dim"], bg=C["bg"]).pack(side="left", padx=6)
        self.combo_frame = tk.Frame(parent, bg=C["bg"])
        self.combo_frame.pack(fill="x", padx=10, pady=4)
        self._build_combo_buttons()

    def _build_start_stop(self, parent):
        C = self.C
        ctrl = tk.Frame(parent, bg=C["bg"])
        ctrl.pack(fill="x", padx=10, pady=4)
        self.start_btn = tk.Button(ctrl, text="▶▶  START",
            font=("Courier",12,"bold"), bg=C["green"], fg=C["bg"],
            relief="flat", pady=12, cursor="hand2", command=self._start)
        self.start_btn.pack(fill="x", pady=(0,4))
        self.stop_btn = tk.Button(ctrl, text="■  STOP",
            font=("Courier",12,"bold"), bg=C["red"], fg="white",
            relief="flat", pady=10, state="disabled", cursor="hand2",
            command=self._stop)
        self.stop_btn.pack(fill="x")

    def _build_console(self, parent):
        C = self.C
        self.console = scrolledtext.ScrolledText(
            parent, bg=C["console_bg"], fg=C["console_fg"],
            font=("Courier",8), relief="flat", height=5,
            insertbackground=C["accent"], selectbackground=C["accent2"])
        self.console.pack(fill="both", expand=True, padx=10, pady=(0,8))
        self.console.config(state="disabled")
        self._log(f"⬡ HexPad v{VERSION} ready — mode: {self.window_mode}  theme: {self.C['name']}")

    # ── Inline editor (for NORMAL / WIDE) ────────────────────────────────────
    def _build_inline_editor(self, parent):
        self._build_editor(parent)

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
                font=("Courier",8,"bold"), bg=C["btn"], fg=col,
                activebackground=col, activeforeground=C["bg"],
                relief="flat", padx=6, pady=6, width=6, cursor="hand2",
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
                text=f"▶ {label}",
                font=("Courier",9,"bold"), bg=C["btn"], fg=C["combo"],
                activebackground=C["combo"], activeforeground=C["bg"],
                relief="flat", padx=6, pady=6, cursor="hand2",
                command=lambda s=seq, l=loop, lb=label: self._fire_combo(s,l,lb))
            btn.grid(row=row_idx, column=col_idx, padx=2, pady=2, sticky="ew")
        self.combo_frame.columnconfigure(0, weight=1)
        self.combo_frame.columnconfigure(1, weight=1)

    def _fire_combo(self, seq, loop, label):
        self._log(f"[COMBO] ▶ {label}")
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
        if not hasattr(self, "console"): return
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
        self._log(f"▶ {mode} | prog {key} | {self.device_var.get()}")
        def run():
            try:    self.listener.start()
            except Exception as e:
                self.root.after(0, self._log, f"[ERR] {e}")
            finally:
                builtins.print = self._orig_print
                self.root.after(0, self._on_stopped)
        threading.Thread(target=run, daemon=True).start()

    def _stop(self):
        self._log("■ Arret...")
        if self.listener: self.listener.stop()

    def _on_stopped(self):
        builtins.print = self._orig_print
        self.running   = False
        self.listener  = None
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_dot.config(fg=self.C["red"])
        self._log("■ Arrete.")

    # ── Editor window (COMPACT only) ──────────────────────────────────────────
    def _open_editor(self):
        if self._editor_win and self._editor_win.winfo_exists():
            self._editor_win.lift(); return
        win = tk.Toplevel(self.root)
        win.title("HexPad — Preset Editor")
        win.configure(bg=self.C["bg"])
        win.geometry("520x680")
        win.resizable(True, True)
        self._editor_win = win
        self._build_editor(win)

    def _build_editor(self, win):
        C = self.C
        tk.Label(win, text="▪ PRESET EDITOR", font=("Courier",9,"bold"),
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

        tk.Label(win,
            text="  Tokens macro : j,k,l  |  j+k  |  50 (ms)  |  ctrl+z",
            font=("Courier",7), fg=C["dim"], bg=C["bg"]).pack(anchor="w", padx=12)
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=12, pady=4)

        bank_row = tk.Frame(win, bg=C["bg"]); bank_row.pack(fill="x", padx=12)
        tk.Label(bank_row, text="BANK", font=("Courier",8,"bold"),
                 fg=C["accent2"], bg=C["bg"]).pack(side="left")
        self._bank_var = tk.StringVar(value="A")
        for b in ("A","B"):
            tk.Radiobutton(bank_row, text=f"  {b}  ", variable=self._bank_var, value=b,
                           font=("Courier",9,"bold"), bg=C["bg"], fg=C["accent"],
                           selectcolor=C["btn"], activebackground=C["bg"],
                           command=lambda: self._editor_refresh(win)).pack(side="left", padx=2)

        tk.Label(win, text="PADS", font=("Courier",8,"bold"),
                 fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=12, pady=(4,0))
        self.pad_frame = tk.Frame(win, bg=C["bg"])
        self.pad_frame.pack(fill="x", padx=12, pady=4)
        self.pad_vars = {}
        self._build_pad_grid()

        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=12, pady=4)
        tk.Label(win, text="ENCODEURS", font=("Courier",8,"bold"),
                 fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=12)
        self.knob_frame = tk.Frame(win, bg=C["bg"])
        self.knob_frame.pack(fill="x", padx=12, pady=4)
        self.knob_vars = {}
        self._build_knob_grid()

        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=12, pady=6)

        btns = tk.Frame(win, bg=C["bg"]); btns.pack(fill="x", padx=12, pady=6)
        tk.Button(btns, text="💾  SAUVEGARDER",
            font=("Courier",9,"bold"), bg=C["accent"], fg=C["bg"],
            relief="flat", padx=10, pady=7, cursor="hand2",
            command=self._save_preset).pack(side="left", padx=(0,5))
        tk.Button(btns, text="+ NOUVEAU",
            font=("Courier",9), bg=C["btn"], fg=C["accent2"],
            relief="flat", padx=8, pady=7, cursor="hand2",
            command=self._new_preset).pack(side="left", padx=(0,5))
        tk.Button(btns, text="✕ SUPPR",
            font=("Courier",9), bg=C["btn"], fg=C["red"],
            relief="flat", padx=8, pady=7, cursor="hand2",
            command=self._delete_preset).pack(side="left")

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
            lb = tk.Button(hrow, text="◎", font=("Courier",8),
                           bg=C["panel2"], fg=C["dim"], relief="flat", cursor="hand2")
            lb.pack(side="right")
            var = tk.StringVar(value=pads.get(ns,""))
            self.pad_vars[ns] = var
            if opts:
                ttk.Combobox(cell, textvariable=var, values=[""]+opts,
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

    def on_close(self):
        self._mon_stop.set()
        self.combo_engine.stop()
        if self.listener: self.listener.stop()
        self._save_config()
        self.root.destroy()


# ─────────────────────────────────────────────────────────────────────────────
def main():
    # Load theme early to colour the selector dialog
    try:
        with open("config.json") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}

    theme_name    = cfg.get("theme", "dark")
    default_mode  = cfg.get("window_mode", "NORMAL")
    C = get_theme(theme_name)

    chosen_mode = ask_window_mode(default_mode, C)
    if not chosen_mode:
        chosen_mode = default_mode

    root = tk.Tk()
    app  = HexPadGUI(root, window_mode=chosen_mode)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()

if __name__ == "__main__":
    main()
