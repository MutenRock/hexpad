#!/usr/bin/env python3
"""
HexPad GUI v1.9.0 — Full mapping editor rewrite
  - 2x4 pad layout (physical MPK layout)
  - Bank A/B both fully editable
  - Contextual fields per mode (gamepad/macro/obs/sampler/websocket)
  - MIDI note names (C2, D2…)
  - OBS action + scene/source sub-fields
  - Sampler file/volume/loop fields
  - Basic validation before save
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

VERSION = "1.9.0"

WINDOW_MODES = {
    "COMPACT": (480, 680),
    "NORMAL":  (820, 900),
    "WIDE":    (1100, 760),
}

PAD_BANK_A  = [36,37,38,39,40,41,42,43]
PAD_BANK_B  = [44,45,46,47,48,49,50,51]
KNOB_CC     = [70,71,72,73,74,75,76,77]
KNOB_LABELS = ["K1","K2","K3","K4","K5","K6","K7","K8"]
AXIS_OPTIONS  = ["axis_x","axis_y","axis_z","axis_rx","axis_ry","axis_rz","axis_sl0","axis_sl1"]
BTN_OPTIONS   = [f"btn_{i}" for i in range(1,17)]
MACRO_OPTIONS = [
    "ctrl+z","ctrl+s","ctrl+c","ctrl+v","ctrl+shift+z","ctrl+x",
    "f1","f2","f3","f4","f5","f6","f7","f8","f9","f10","f11","f12",
    "esc","space","enter","tab","backspace","delete",
    "up","down","left","right",
    "a","b","c","d","e","f","g","h","i","j","k","l","m",
    "n","o","p","q","r","s","t","u","v","w","x","y","z",
]
OBS_ACTIONS   = ["scene","toggle_mute","toggle_stream","toggle_record","screenshot","toggle_source","hotkey"]
OBS_NEEDS_SCENE  = {"scene"}
OBS_NEEDS_SOURCE = {"toggle_mute","toggle_source"}

# MIDI note name helper
_NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
def note_name(n): return f"{_NOTE_NAMES[n%12]}{(n//12)-1}"


# ─────────────────────────────────────────────────────────────────────────────
# Launch mode selector
# ─────────────────────────────────────────────────────────────────────────────
def ask_window_mode(default_mode: str, theme_colors: dict) -> str:
    C = theme_colors
    dialog = tk.Tk()
    dialog.title("HexPad — Choisir le mode")
    dialog.resizable(False, False)
    dialog.configure(bg=C["bg"])
    dw, dh = 480, 360
    sw, sh = dialog.winfo_screenwidth(), dialog.winfo_screenheight()
    dialog.geometry(f"{dw}x{dh}+{(sw-dw)//2}+{(sh-dh)//2}")
    hdr = tk.Frame(dialog, bg=C["panel"], pady=12)
    hdr.pack(fill="x")
    tk.Label(hdr, text="⬡", font=("Courier",26,"bold"), fg=C["accent"], bg=C["panel"]).pack(side="left", padx=(16,6))
    tk.Label(hdr, text=f"HexPad  v{VERSION}", font=("Courier",14,"bold"), fg=C["text"], bg=C["panel"]).pack(side="left")
    tk.Label(dialog, text="Choisir le mode d'affichage", font=("Courier",10), fg=C["dim"], bg=C["bg"]).pack(pady=(16,10))
    chosen = tk.StringVar(value=default_mode)
    desc = {
        "COMPACT": "480 × 680  —  Widget compact",
        "NORMAL":  "820 × 900  —  Mapping Editor intégré",
        "WIDE":    "1100 × 760 —  3 colonnes",
    }
    btn_frame = tk.Frame(dialog, bg=C["bg"])
    btn_frame.pack(fill="x", padx=20)
    mode_btns = {}
    def _select(m):
        chosen.set(m)
        for k, b in mode_btns.items():
            sel = k == m
            b.config(bg=C["accent"] if sel else C["btn"], fg=C["bg"] if sel else C["text"],
                     font=("Courier",11,"bold" if sel else "normal"))
    for mode in ("COMPACT","NORMAL","WIDE"):
        is_sel = mode == default_mode
        b = tk.Button(btn_frame, text=f"  {mode}\n  {desc[mode]}",
            font=("Courier",11,"bold" if is_sel else "normal"),
            bg=C["accent"] if is_sel else C["btn"], fg=C["bg"] if is_sel else C["text"],
            relief="flat", padx=18, pady=14, cursor="hand2", anchor="w", justify="left",
            command=lambda m=mode: _select(m))
        b.pack(fill="x", pady=4, ipady=2)
        mode_btns[mode] = b
    tk.Frame(dialog, bg=C["border"], height=1).pack(fill="x", padx=20, pady=10)
    tk.Button(dialog, text="▶  Lancer", font=("Courier",12,"bold"),
        bg=C["green"], fg=C["bg"], relief="flat", padx=24, pady=10,
        cursor="hand2", command=dialog.destroy).pack()
    dialog.mainloop()
    return chosen.get()


# ─────────────────────────────────────────────────────────────────────────────
class HexPadGUI:
    def __init__(self, root, window_mode="NORMAL"):
        self.root          = root
        self._orig_print   = builtins.print
        self.running       = False
        self.listener      = None
        self._learn_target = None
        self._pad_btns     = {}
        self._current_prog = "1"
        self._editor_win   = None
        self.window_mode   = window_mode
        self.config        = self._load_config()
        self.profiles      = GameProfiles()
        self.combo_engine  = ComboEngine()
        theme_name = self.config.get("theme","dark")
        self.C = get_theme(theme_name)
        self._apply_window()
        self._build_ui()
        if self.config.get("programs"):
            self._select_program(self._current_prog)
        self._sync_profile()
        self._mon_stop = threading.Event()
        self._start_monitor()

    def _apply_window(self):
        C = self.C
        w, h = WINDOW_MODES.get(self.window_mode, WINDOW_MODES["NORMAL"])
        self.root.title(f"HexPad v{VERSION}  [{self.window_mode}]")
        self.root.configure(bg=C["bg"])
        self.root.resizable(True, True)
        self.root.minsize(w, h)
        self.root.geometry(f"{w}x{h}")

    def _load_config(self):
        try:
            with open("config.json") as f: return json.load(f)
        except Exception as e:
            messagebox.showerror("Erreur config", str(e)); sys.exit(1)

    def _save_config(self):
        self.config["window_mode"] = self.window_mode
        with open("config.json","w") as f: json.dump(self.config, f, indent=2)

    def _toggle_theme(self):
        new_name = "light" if self.C["name"]=="dark" else "dark"
        self.C = get_theme(new_name)
        self.config["theme"] = new_name
        self._save_config()
        for w in self.root.winfo_children(): w.destroy()
        self._apply_window(); self._build_ui()
        if self.config.get("programs"): self._select_program(self._current_prog)
        self._sync_profile()

    def _style(self):
        C = self.C; s = ttk.Style(); s.theme_use("clam")
        s.configure("H.TCombobox", fieldbackground=C["btn"], background=C["btn"],
            foreground=C["accent"], selectbackground=C["accent2"], arrowcolor=C["accent"])
        s.configure("H.TNotebook", background=C["bg"], borderwidth=0)
        s.configure("H.TNotebook.Tab", background=C["panel2"], foreground=C["dim"],
            font=("Courier",8,"bold"), padding=[10,4])
        s.map("H.TNotebook.Tab",
            background=[("selected",C["panel"])], foreground=[("selected",C["accent"])])

    def _sep(self, parent):
        tk.Frame(parent, bg=self.C["border"], height=1).pack(fill="x", padx=12, pady=4)

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        self._style(); self.root.configure(bg=self.C["bg"])
        if   self.window_mode=="WIDE":    self._build_wide()
        elif self.window_mode=="NORMAL":  self._build_normal()
        else:                             self._build_compact()

    def _build_compact(self):
        self._build_header(self.root); self._build_device_row(self.root)
        self._sep(self.root); self._build_prog_section(self.root)
        self._sep(self.root); self._build_pad_monitor(self.root)
        self._sep(self.root); self._build_combos(self.root)
        self._sep(self.root); self._build_start_stop(self.root)
        self._sep(self.root); self._build_console(self.root)

    def _build_normal(self):
        C = self.C; self._build_header(self.root)
        paned = tk.PanedWindow(self.root, orient="horizontal", bg=C["bg"], sashwidth=4, sashrelief="flat")
        paned.pack(fill="both", expand=True)
        left = tk.Frame(paned, bg=C["bg"]); paned.add(left, minsize=380)
        self._build_device_row(left); self._sep(left)
        self._build_prog_section(left); self._sep(left)
        self._build_pad_monitor(left); self._sep(left)
        self._build_combos(left); self._sep(left)
        self._build_start_stop(left); self._sep(left)
        self._build_console(left)
        right = tk.Frame(paned, bg=C["bg"]); paned.add(right, minsize=400)
        self._build_mapping_editor(right)

    def _build_wide(self):
        C = self.C; self._build_header(self.root)
        cols = tk.Frame(self.root, bg=C["bg"]); cols.pack(fill="both", expand=True)
        cols.columnconfigure(0, weight=1, minsize=300)
        cols.columnconfigure(1, weight=2, minsize=400)
        cols.columnconfigure(2, weight=2, minsize=360)
        col1 = tk.Frame(cols, bg=C["bg"]); col1.grid(row=0, column=0, sticky="nsew", padx=(6,2), pady=6)
        self._build_device_row(col1); self._sep(col1)
        self._build_prog_section(col1); self._sep(col1)
        self._build_pad_monitor(col1); self._sep(col1)
        self._build_start_stop(col1)
        col2 = tk.Frame(cols, bg=C["bg"]); col2.grid(row=0, column=1, sticky="nsew", padx=2, pady=6)
        self._build_combos(col2); self._sep(col2); self._build_console(col2)
        col3 = tk.Frame(cols, bg=C["bg"]); col3.grid(row=0, column=2, sticky="nsew", padx=(2,6), pady=6)
        self._build_mapping_editor(col3)

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self, parent):
        C = self.C
        hdr = tk.Frame(parent, bg=C["panel"], pady=7); hdr.pack(fill="x")
        tk.Label(hdr, text="⬡", font=("Courier",20,"bold"), fg=C["accent"], bg=C["panel"]).pack(side="left", padx=(10,2))
        tk.Label(hdr, text="HexPad", font=("Courier",14,"bold"), fg=C["text"], bg=C["panel"]).pack(side="left")
        tk.Label(hdr, text=f" v{VERSION}", font=("Courier",7), fg=C["dim"], bg=C["panel"]).pack(side="left")
        tk.Label(hdr, text=f"[{self.window_mode}]", font=("Courier",7,"bold"), fg=C["accent2"], bg=C["panel"]).pack(side="left", padx=6)
        tk.Button(hdr, text="✕", font=("Courier",10,"bold"), bg=C["panel"], fg=C["dim"],
            relief="flat", padx=8, cursor="hand2", command=self.on_close).pack(side="right", padx=2)
        tk.Button(hdr, text="–", font=("Courier",10,"bold"), bg=C["panel"], fg=C["dim"],
            relief="flat", padx=8, cursor="hand2", command=self.root.iconify).pack(side="right", padx=2)
        tk.Button(hdr, text=C["toggle_icon"], font=("Courier",10), bg=C["panel"], fg=C["accent"],
            relief="flat", padx=8, cursor="hand2", command=self._toggle_theme).pack(side="right", padx=2)

    def _build_device_row(self, parent):
        C = self.C
        dp = tk.Frame(parent, bg=C["bg"], pady=4); dp.pack(fill="x", padx=10)
        self.status_dot = tk.Label(dp, text="●", font=("Courier",12,"bold"), fg=C["red"], bg=C["bg"])
        self.status_dot.pack(side="left", padx=(0,2))
        devices = mido.get_input_names() or ["Aucun"]
        self.device_var = tk.StringVar(value=self.config.get("device_name",""))
        dev_cb = ttk.Combobox(dp, textvariable=self.device_var, values=devices, width=16, state="readonly", style="H.TCombobox")
        dev_cb.pack(side="left", padx=2)
        for d in devices:
            if any(x in d.lower() for x in ("mpk","mini","akai")): self.device_var.set(d); break
        tk.Label(dp, text="|", fg=C["border"], bg=C["bg"], font=("Courier",10)).pack(side="left", padx=4)
        self.profile_var = tk.StringVar(value=self.profiles.active)
        self.profile_cb = ttk.Combobox(dp, textvariable=self.profile_var, values=self.profiles.names,
            width=12, state="readonly", style="H.TCombobox")
        self.profile_cb.pack(side="left", padx=2)
        self.profile_cb.bind("<<ComboboxSelected>>", self._on_profile_changed)
        if self.window_mode=="COMPACT":
            tk.Button(dp, text="⚙", font=("Courier",10), bg=C["bg"], fg=C["accent2"],
                relief="flat", padx=4, cursor="hand2", command=self._open_editor).pack(side="right")

    def _build_prog_section(self, parent):
        C = self.C
        tk.Label(parent, text="  PROGRAMME", font=("Courier",7,"bold"), fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=12)
        self.prog_frame = tk.Frame(parent, bg=C["bg"]); self.prog_frame.pack(fill="x", padx=10, pady=4)
        self.prog_btns = {}; self._build_prog_btns()

    def _build_pad_monitor(self, parent):
        C = self.C
        tk.Label(parent, text="  PAD MONITOR", font=("Courier",7,"bold"), fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=12)
        pf = tk.Frame(parent, bg=C["bg"]); pf.pack(padx=10, pady=4)
        self._pad_btns = {}
        for i, note in enumerate(PAD_BANK_A):
            col, row_idx = i%4, i//4
            btn = tk.Label(pf, text=f"P{i+1}", font=("Courier",10,"bold"),
                bg=C["pad_off"], fg=C["dim"], width=6, pady=9, relief="flat")
            btn.grid(row=row_idx, column=col, padx=3, pady=3)
            self._pad_btns[str(note)] = btn

    def _build_combos(self, parent):
        C = self.C
        combo_hdr = tk.Frame(parent, bg=C["bg"]); combo_hdr.pack(fill="x", padx=10)
        tk.Label(combo_hdr, text="  COMBOS", font=("Courier",7,"bold"), fg=C["combo"], bg=C["bg"]).pack(side="left")
        tk.Label(combo_hdr, text=self.profiles.active, font=("Courier",7), fg=C["dim"], bg=C["bg"]).pack(side="left", padx=6)
        self.combo_frame = tk.Frame(parent, bg=C["bg"]); self.combo_frame.pack(fill="x", padx=10, pady=4)
        self._build_combo_buttons()

    def _build_start_stop(self, parent):
        C = self.C
        ctrl = tk.Frame(parent, bg=C["bg"]); ctrl.pack(fill="x", padx=10, pady=4)
        self.start_btn = tk.Button(ctrl, text="▶▶  START", font=("Courier",12,"bold"),
            bg=C["green"], fg=C["bg"], relief="flat", pady=12, cursor="hand2", command=self._start)
        self.start_btn.pack(fill="x", pady=(0,4))
        self.stop_btn = tk.Button(ctrl, text="■  STOP", font=("Courier",12,"bold"),
            bg=C["red"], fg="white", relief="flat", pady=10, state="disabled", cursor="hand2", command=self._stop)
        self.stop_btn.pack(fill="x")

    def _build_console(self, parent):
        C = self.C
        self.console = scrolledtext.ScrolledText(parent, bg=C["console_bg"], fg=C["console_fg"],
            font=("Courier",8), relief="flat", height=5,
            insertbackground=C["accent"], selectbackground=C["accent2"])
        self.console.pack(fill="both", expand=True, padx=10, pady=(0,8))
        self.console.config(state="disabled")
        self._log(f"⬡ HexPad v{VERSION} ready — mode: {self.window_mode}  theme: {self.C['name']}")

    # ── Prog pills ────────────────────────────────────────────────────────────
    def _build_prog_btns(self):
        for w in self.prog_frame.winfo_children(): w.destroy()
        self.prog_btns = {}; C = self.C
        for key, prog in self.config.get("programs",{}).items():
            mode = prog.get("mode","debug")
            col  = MODE_COLORS.get(mode, C["dim"])
            name = prog.get("name",mode)[:6].upper()
            b = tk.Button(self.prog_frame, text=f"{key}\n{name}",
                font=("Courier",8,"bold"), bg=C["btn"], fg=col,
                activebackground=col, activeforeground=C["bg"],
                relief="flat", padx=6, pady=6, width=6, cursor="hand2",
                command=lambda k=key: self._select_program(k))
            b.pack(side="left", padx=2)
            self.prog_btns[key] = (b, col)

    # ── Combos ────────────────────────────────────────────────────────────────
    def _build_combo_buttons(self):
        C = self.C
        for w in self.combo_frame.winfo_children(): w.destroy()
        combos = self.profiles.get_combos()
        if not combos:
            tk.Label(self.combo_frame, text="Aucun combo — editez game_profiles.json",
                font=("Courier",7), fg=C["dim"], bg=C["bg"]).pack(anchor="w"); return
        for i, (key, combo) in enumerate(combos.items()):
            label = combo.get("label",key); seq = combo.get("sequence",""); loop = combo.get("loop",False)
            btn = tk.Button(self.combo_frame, text=f"▶ {label}",
                font=("Courier",9,"bold"), bg=C["btn"], fg=C["combo"],
                activebackground=C["combo"], activeforeground=C["bg"],
                relief="flat", padx=6, pady=6, cursor="hand2",
                command=lambda s=seq,l=loop,lb=label: self._fire_combo(s,l,lb))
            btn.grid(row=i//2, column=i%2, padx=2, pady=2, sticky="ew")
        self.combo_frame.columnconfigure(0, weight=1); self.combo_frame.columnconfigure(1, weight=1)

    def _fire_combo(self, seq, loop, label):
        self._log(f"[COMBO] ▶ {label}"); self.combo_engine.execute(seq, loop=loop)

    # ── Profile ───────────────────────────────────────────────────────────────
    def _on_profile_changed(self, event=None):
        name = self.profile_var.get(); self.profiles.active = name
        prof = self.profiles.get_profile(name)
        if prof:
            prog = prof.get("program","1")
            if prog in self.config["programs"]: self._select_program(prog)
        self._build_combo_buttons(); self._log(f"[PROFILE] {name}")

    def _sync_profile(self): self._build_combo_buttons()

    def _get_current_preset(self): return self.config["programs"].get(self._current_prog)

    def _select_program(self, key):
        if key not in self.config["programs"]: key = list(self.config["programs"].keys())[0]
        self._current_prog = key
        for k,(b,col) in self.prog_btns.items():
            b.config(bg=col if k==key else self.C["btn"], fg=self.C["bg"] if k==key else col)
        self._log(f"[PROG] {key} — {self.config['programs'][key].get('name','')}")
        # refresh editor if open
        if hasattr(self, "_me_loaded"): self._me_load_preset()

    # ── Monitor MIDI ──────────────────────────────────────────────────────────
    def _start_monitor(self):
        def run():
            while not self._mon_stop.is_set():
                try:
                    device = None
                    for d in mido.get_input_names():
                        if any(x in d.lower() for x in ("mpk","mini","akai")): device=d; break
                    if not device: time.sleep(2); continue
                    with mido.open_input(device) as port:
                        while not self._mon_stop.is_set():
                            msg = port.poll()
                            if msg and msg.type=="note_on" and msg.velocity>0:
                                ns = str(msg.note)
                                if ns in self._pad_btns:
                                    b=self._pad_btns[ns]; vel=msg.velocity
                                    r=int(vel/127*0xff); g=int((1-vel/127)*0xe7)
                                    hc=f"#{r:02x}{0xff:02x}{g:02x}"
                                    self.root.after(0, b.config, {"bg":hc,"fg":self.C["bg"]})
                                    self.root.after(200, b.config, {"bg":self.C["pad_off"],"fg":self.C["dim"]})
                                if self._learn_target: self.root.after(0, self._on_learn_received, msg.note)
                            time.sleep(0.001)
                except Exception: time.sleep(1)
        threading.Thread(target=run, daemon=True).start()

    def _on_learn_received(self, note):
        if not self._learn_target: return
        pad_key, btn = self._learn_target
        self._log(f"[LEARN] Note {note} ({note_name(note)}) → pad {pad_key}")
        btn.config(bg=self.C["panel2"], fg=self.C["dim"])
        self._learn_target = None
        # refresh pad grid so learned note appears
        if hasattr(self,"_me_pad_frame"): self._me_build_pad_grid()

    def _log(self, msg):
        if not hasattr(self,"console"): return
        self.console.config(state="normal"); self.console.insert("end",msg+"\n")
        self.console.see("end"); self.console.config(state="disabled")

    # ── Start / Stop ──────────────────────────────────────────────────────────
    def _build_bridge(self, prog):
        mode = prog.get("mode","debug")
        if mode=="gamepad":   return GamepadBridge(prog), mode
        if mode=="websocket": return WebSocketBridge(prog.get("ws_url","ws://localhost:8765")), mode
        if mode=="macro":     return MacroBridge(prog), mode
        if mode=="obs":       return OBSBridge(prog), mode
        return None, "debug"

    def _start(self):
        key=self._current_prog; prog=self.config["programs"].get(key,{})
        self.config["device_name"]=self.device_var.get()
        bridge, mode = self._build_bridge(prog)
        d = Dispatcher()
        def gui_print(*args,**kw): self.root.after(0,self._log," ".join(str(a) for a in args))
        builtins.print=gui_print; d.set_bridge(bridge,mode)
        self.running=True; self.listener=MidiListener(self.config,d)
        self.start_btn.config(state="disabled"); self.stop_btn.config(state="normal")
        self.status_dot.config(fg=self.C["green"])
        self._log(f"▶ {mode} | prog {key} | {self.device_var.get()}")
        def run():
            try: self.listener.start()
            except Exception as e: self.root.after(0,self._log,f"[ERR] {e}")
            finally:
                builtins.print=self._orig_print; self.root.after(0,self._on_stopped)
        threading.Thread(target=run,daemon=True).start()

    def _stop(self):
        self._log("■ Arret...")
        if self.listener: self.listener.stop()

    def _on_stopped(self):
        builtins.print=self._orig_print; self.running=False; self.listener=None
        self.start_btn.config(state="normal"); self.stop_btn.config(state="disabled")
        self.status_dot.config(fg=self.C["red"]); self._log("■ Arrete.")

    # ──────────────────────────────────────────────────────────────────────────
    # MAPPING EDITOR (new, complete rewrite)
    # ──────────────────────────────────────────────────────────────────────────

    def _open_editor(self):
        """COMPACT mode: open editor as Toplevel."""
        if self._editor_win and self._editor_win.winfo_exists():
            self._editor_win.lift(); return
        win = tk.Toplevel(self.root)
        win.title("HexPad — Mapping Editor")
        win.configure(bg=self.C["bg"])
        win.geometry("580x760"); win.resizable(True, True)
        self._editor_win = win
        self._build_mapping_editor(win)

    def _build_mapping_editor(self, parent):
        """Full mapping editor — pad 2x4 layout, Bank A/B, contextual fields."""
        C = self.C

        # ── Header
        hdr = tk.Frame(parent, bg=C["panel2"]); hdr.pack(fill="x")
        tk.Label(hdr, text="◈ MAPPING EDITOR", font=("Courier",10,"bold"),
            fg=C["accent"], bg=C["panel2"]).pack(side="left", padx=12, pady=8)
        self._me_save_indicator = tk.Label(hdr, text="", font=("Courier",8),
            fg=C["green"], bg=C["panel2"])
        self._me_save_indicator.pack(side="right", padx=12)

        # scrollable body
        canvas = tk.Canvas(parent, bg=C["bg"], bd=0, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(canvas, bg=C["bg"])
        body_win = canvas.create_window((0,0), window=body, anchor="nw")
        def _on_configure(e): canvas.configure(scrollregion=canvas.bbox("all"))
        def _on_canvas_resize(e): canvas.itemconfig(body_win, width=e.width)
        body.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_canvas_resize)
        def _mousewheel(e): canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _mousewheel)

        # ── Preset selector row
        prow = tk.Frame(body, bg=C["bg"]); prow.pack(fill="x", padx=12, pady=(10,4))
        tk.Label(prow, text="Preset :", font=("Courier",9,"bold"),
            fg=C["dim"], bg=C["bg"]).pack(side="left")
        self._me_prog_var = tk.StringVar(value=self._current_prog)
        prog_keys = list(self.config.get("programs",{}).keys())
        prog_labels = [f"{k} — {self.config['programs'][k].get('name','')}" for k in prog_keys]
        self._me_prog_map = dict(zip(prog_labels, prog_keys))
        self._me_prog_cb = ttk.Combobox(prow, textvariable=self._me_prog_var,
            values=prog_labels, width=28, state="readonly", style="H.TCombobox")
        self._me_prog_cb.pack(side="left", padx=8)
        # set display to current prog
        for label, key in self._me_prog_map.items():
            if key == self._current_prog:
                self._me_prog_var.set(label); break
        self._me_prog_cb.bind("<<ComboboxSelected>>", self._me_on_prog_changed)
        tk.Button(prow, text="+ Nouveau", font=("Courier",8), bg=C["btn"], fg=C["accent2"],
            relief="flat", padx=6, pady=4, cursor="hand2",
            command=self._me_new_preset).pack(side="left", padx=4)
        tk.Button(prow, text="✕ Suppr", font=("Courier",8), bg=C["btn"], fg=C["red"],
            relief="flat", padx=6, pady=4, cursor="hand2",
            command=self._me_delete_preset).pack(side="left")

        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", padx=12, pady=6)

        # ── Meta fields (name + mode)
        meta = tk.Frame(body, bg=C["bg"]); meta.pack(fill="x", padx=12)
        tk.Label(meta, text="Nom", font=("Courier",8), fg=C["dim"], bg=C["bg"]).grid(row=0, column=0, sticky="w", pady=3)
        self._me_name_var = tk.StringVar()
        tk.Entry(meta, textvariable=self._me_name_var, bg=C["btn"], fg=C["accent"],
            font=("Courier",9), relief="flat", width=20,
            insertbackground=C["accent"]).grid(row=0, column=1, padx=8, sticky="w")
        tk.Label(meta, text="Mode", font=("Courier",8), fg=C["dim"], bg=C["bg"]).grid(row=0, column=2, sticky="w", padx=(12,0))
        self._me_mode_var = tk.StringVar(value="gamepad")
        mode_cb = ttk.Combobox(meta, textvariable=self._me_mode_var,
            values=list(MODE_COLORS.keys()), width=14, state="readonly", style="H.TCombobox")
        mode_cb.grid(row=0, column=3, padx=8, sticky="w")
        mode_cb.bind("<<ComboboxSelected>>", lambda e: self._me_refresh_mode_fields())

        # ── Mode-specific connection fields
        self._me_conn_frame = tk.Frame(body, bg=C["bg"]); self._me_conn_frame.pack(fill="x", padx=12, pady=4)

        # ws url
        self._me_ws_url_var = tk.StringVar(value="ws://localhost:8765")
        # obs
        self._me_obs_host_var = tk.StringVar(value="localhost")
        self._me_obs_port_var = tk.StringVar(value="4455")
        self._me_obs_pass_var = tk.StringVar(value="")
        # pitch/mod
        self._me_pitch_var = tk.StringVar(value="")
        self._me_mod_var   = tk.StringVar(value="")
        # sampler
        self._me_sounds_dir_var = tk.StringVar(value="sounds")

        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", padx=12, pady=6)

        # ── Bank selector
        bank_row = tk.Frame(body, bg=C["bg"]); bank_row.pack(fill="x", padx=12)
        tk.Label(bank_row, text="BANK", font=("Courier",9,"bold"),
            fg=C["accent2"], bg=C["bg"]).pack(side="left")
        self._me_bank_var = tk.StringVar(value="A")
        for bank in ("A","B"):
            tk.Radiobutton(bank_row, text=f"  {bank}  ", variable=self._me_bank_var, value=bank,
                font=("Courier",9,"bold"), bg=C["bg"], fg=C["accent"],
                selectcolor=C["btn"], activebackground=C["bg"],
                command=self._me_build_pad_grid).pack(side="left", padx=4)
        # note label checkbox
        self._me_show_note_var = tk.BooleanVar(value=True)
        tk.Checkbutton(bank_row, text="noms de notes", variable=self._me_show_note_var,
            font=("Courier",7), bg=C["bg"], fg=C["dim"],
            selectcolor=C["btn"], activebackground=C["bg"],
            command=self._me_build_pad_grid).pack(side="right", padx=8)

        # ── Pad grid (2x4 physical layout)
        tk.Label(body, text="  PADS — layout physique MPK", font=("Courier",8,"bold"),
            fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=12, pady=(8,2))
        self._me_pad_frame = tk.Frame(body, bg=C["bg"])
        self._me_pad_frame.pack(fill="x", padx=12, pady=4)
        self._me_pad_vars = {}
        self._me_pad_sub_vars = {}  # for obs sub-fields

        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", padx=12, pady=6)

        # ── Knob row
        tk.Label(body, text="  ENCODEURS (CC)", font=("Courier",8,"bold"),
            fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=12)
        self._me_knob_frame = tk.Frame(body, bg=C["bg"])
        self._me_knob_frame.pack(fill="x", padx=12, pady=4)
        self._me_knob_vars = {}

        # ── Pitch / Mod row
        pm_row = tk.Frame(body, bg=C["bg"]); pm_row.pack(fill="x", padx=12, pady=4)
        for label, var in (("Pitchwheel →", self._me_pitch_var),("Modwheel →", self._me_mod_var)):
            tk.Label(pm_row, text=label, font=("Courier",8), fg=C["dim"], bg=C["bg"]).pack(side="left")
            ttk.Combobox(pm_row, textvariable=var, values=[""]+AXIS_OPTIONS,
                width=10, state="normal", style="H.TCombobox").pack(side="left", padx=(4,16))

        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", padx=12, pady=8)

        # ── Save button
        btns = tk.Frame(body, bg=C["bg"]); btns.pack(fill="x", padx=12, pady=(0,16))
        tk.Button(btns, text="💾  SAUVEGARDER", font=("Courier",10,"bold"),
            bg=C["accent"], fg=C["bg"], relief="flat", padx=16, pady=10,
            cursor="hand2", command=self._me_save).pack(side="left", padx=(0,8))
        tk.Button(btns, text="↺  Recharger", font=("Courier",9), bg=C["btn"], fg=C["dim"],
            relief="flat", padx=10, pady=10, cursor="hand2",
            command=self._me_load_preset).pack(side="left")

        self._me_loaded = True
        self._me_load_preset()

    # ── Mapping Editor logic ──────────────────────────────────────────────────

    def _me_on_prog_changed(self, event=None):
        label = self._me_prog_var.get()
        key   = self._me_prog_map.get(label, label)
        self._current_prog = key
        for k,(b,col) in self.prog_btns.items():
            b.config(bg=col if k==key else self.C["btn"], fg=self.C["bg"] if k==key else col)
        self._me_load_preset()

    def _me_load_preset(self):
        prog = self._get_current_preset()
        if not prog: return
        self._me_name_var.set(prog.get("name", f"Programme {self._current_prog}"))
        self._me_mode_var.set(prog.get("mode","debug"))
        self._me_ws_url_var.set(prog.get("ws_url","ws://localhost:8765"))
        self._me_obs_host_var.set(prog.get("obs_host","localhost"))
        self._me_obs_port_var.set(str(prog.get("obs_port",4455)))
        self._me_obs_pass_var.set(prog.get("obs_password",""))
        self._me_pitch_var.set(prog.get("pitchwheel",""))
        self._me_mod_var.set(prog.get("modwheel",""))
        self._me_sounds_dir_var.set(prog.get("sounds_dir","sounds"))
        self._me_refresh_mode_fields()
        self._me_build_pad_grid()
        self._me_build_knob_grid()

    def _me_refresh_mode_fields(self):
        """Show/hide connection fields based on current mode."""
        C = self.C
        for w in self._me_conn_frame.winfo_children(): w.destroy()
        mode = self._me_mode_var.get()

        def lbl(text): return tk.Label(self._me_conn_frame, text=text,
            font=("Courier",8), fg=C["dim"], bg=C["bg"])
        def ent(var, w=20): return tk.Entry(self._me_conn_frame, textvariable=var,
            bg=C["btn"], fg=C["accent"], font=("Courier",9), relief="flat",
            insertbackground=C["accent"], width=w)

        col = 0
        if mode=="websocket":
            lbl("WS URL").grid(row=0, column=col, sticky="w", padx=(0,4)); col+=1
            ent(self._me_ws_url_var, 26).grid(row=0, column=col, sticky="w"); col+=1
        elif mode=="obs":
            lbl("Host").grid(row=0, column=col, sticky="w", padx=(0,4)); col+=1
            ent(self._me_obs_host_var, 14).grid(row=0, column=col, sticky="w"); col+=1
            lbl("Port").grid(row=0, column=col, sticky="w", padx=(8,4)); col+=1
            ent(self._me_obs_port_var, 5).grid(row=0, column=col, sticky="w"); col+=1
            lbl("Password").grid(row=0, column=col, sticky="w", padx=(8,4)); col+=1
            ent(self._me_obs_pass_var, 16).grid(row=0, column=col, sticky="w"); col+=1
        elif mode in ("sound_preset","music"):
            lbl("Sons dir").grid(row=0, column=col, sticky="w", padx=(0,4)); col+=1
            ent(self._me_sounds_dir_var, 18).grid(row=0, column=col, sticky="w"); col+=1
        # rebuild pad grid because options change with mode
        if hasattr(self,"_me_pad_frame"): self._me_build_pad_grid()
        if hasattr(self,"_me_knob_frame"): self._me_build_knob_grid()

    def _me_build_pad_grid(self):
        C = self.C
        for w in self._me_pad_frame.winfo_children(): w.destroy()
        self._me_pad_vars.clear(); self._me_pad_sub_vars.clear()

        mode  = self._me_mode_var.get() if hasattr(self,"_me_mode_var") else "gamepad"
        bank  = self._me_bank_var.get() if hasattr(self,"_me_bank_var") else "A"
        notes = PAD_BANK_A if bank=="A" else PAD_BANK_B
        prog  = self._get_current_preset() or {}
        pads_key = "pads" if bank=="A" else "pads_bank_b"
        pads  = prog.get(pads_key, {})
        show_note = self._me_show_note_var.get() if hasattr(self,"_me_show_note_var") else True

        # options per mode
        if   mode=="gamepad":             pad_opts = BTN_OPTIONS
        elif mode=="macro":               pad_opts = MACRO_OPTIONS
        elif mode=="obs":                 pad_opts = OBS_ACTIONS
        elif mode in ("sound_preset","music"): pad_opts = None  # free text (filename)
        else:                             pad_opts = None

        # MPK physical layout: row0 = P5-P8 (top), row1 = P1-P4 (bottom)
        # MIDI notes: bank A → 36-43, physical top row = notes[4:8], bottom = notes[0:4]
        layout = [notes[4:8], notes[0:4]]  # top row first, then bottom

        for row_idx, row_notes in enumerate(layout):
            for col_idx, note in enumerate(row_notes):
                ns  = str(note)
                pad_num = notes.index(note) + 1
                nn  = note_name(note)
                raw = pads.get(ns, "")

                # card
                card = tk.Frame(self._me_pad_frame, bg=C["panel2"],
                    relief="flat", padx=4, pady=4)
                card.grid(row=row_idx, column=col_idx, padx=3, pady=3, sticky="nsew")
                self._me_pad_frame.columnconfigure(col_idx, weight=1)

                # header row
                h = tk.Frame(card, bg=C["panel2"]); h.pack(fill="x")
                pad_label = f"P{pad_num}" + (f"  {nn}" if show_note else "")
                tk.Label(h, text=pad_label, font=("Courier",7,"bold"),
                    fg=C["accent"], bg=C["panel2"]).pack(side="left")
                tk.Label(h, text=f"n{note}", font=("Courier",6),
                    fg=C["dim"], bg=C["panel2"]).pack(side="left", padx=2)
                # MIDI learn button
                learn_btn = tk.Button(h, text="◎", font=("Courier",7),
                    bg=C["panel2"], fg=C["dim"], relief="flat", cursor="hand2",
                    pady=0, padx=2)
                learn_btn.pack(side="right")
                learn_btn.config(command=lambda ns=ns, b=learn_btn: self._me_midi_learn(ns, b))

                # ─ Mode-specific fields ─
                if mode=="obs":
                    # action is a dict: {action, scene/source/…}
                    if isinstance(raw, dict):
                        act_val = raw.get("action","")
                        sub_val = raw.get("scene", raw.get("source", raw.get("hotkey","")))
                    else:
                        act_val = raw if raw else ""
                        sub_val = ""
                    act_var = tk.StringVar(value=act_val)
                    sub_var = tk.StringVar(value=sub_val)
                    self._me_pad_vars[ns]     = act_var
                    self._me_pad_sub_vars[ns] = sub_var
                    act_cb = ttk.Combobox(card, textvariable=act_var, values=[""]+OBS_ACTIONS,
                        width=11, state="normal", style="H.TCombobox")
                    act_cb.pack(fill="x")
                    sub_entry = tk.Entry(card, textvariable=sub_var, bg=C["btn"], fg=C["accent2"],
                        font=("Courier",7), relief="flat", width=12,
                        insertbackground=C["accent"])
                    sub_entry.pack(fill="x", pady=(2,0))
                    # placeholder
                    def _update_sub_placeholder(act_var=act_var, sub_entry=sub_entry):
                        act = act_var.get()
                        if act in OBS_NEEDS_SCENE:  ph="scene name"
                        elif act in OBS_NEEDS_SOURCE: ph="source name"
                        elif act=="hotkey":           ph="hotkey id"
                        else:                         ph=""
                        sub_entry.config(fg=C["dim"] if not sub_var.get() else C["accent2"])
                    act_cb.bind("<<ComboboxSelected>>", lambda e, f=_update_sub_placeholder: f())

                elif mode in ("sound_preset","music"):
                    # dict: {file, volume, loop} or "stop_all"
                    if isinstance(raw, dict):
                        file_val   = raw.get("file","")
                        vol_val    = str(raw.get("volume","1.0"))
                        loop_val   = raw.get("loop", False)
                    elif raw=="stop_all":
                        file_val, vol_val, loop_val = "stop_all", "1.0", False
                    else:
                        file_val, vol_val, loop_val = raw, "1.0", False
                    file_var = tk.StringVar(value=file_val)
                    vol_var  = tk.StringVar(value=vol_val)
                    loop_var = tk.BooleanVar(value=loop_val)
                    self._me_pad_vars[ns]     = file_var
                    self._me_pad_sub_vars[ns] = (vol_var, loop_var)
                    tk.Entry(card, textvariable=file_var, bg=C["btn"], fg=C["accent"],
                        font=("Courier",7), relief="flat",
                        insertbackground=C["accent"]).pack(fill="x")
                    vol_row = tk.Frame(card, bg=C["panel2"]); vol_row.pack(fill="x", pady=(2,0))
                    tk.Label(vol_row, text="vol", font=("Courier",6), fg=C["dim"], bg=C["panel2"]).pack(side="left")
                    tk.Entry(vol_row, textvariable=vol_var, bg=C["btn"], fg=C["accent2"],
                        font=("Courier",7), relief="flat", width=4,
                        insertbackground=C["accent"]).pack(side="left", padx=2)
                    tk.Checkbutton(vol_row, text="loop", variable=loop_var,
                        font=("Courier",6), bg=C["panel2"], fg=C["dim"],
                        selectcolor=C["btn"], activebackground=C["panel2"]).pack(side="left", padx=4)

                elif pad_opts is not None:
                    var = tk.StringVar(value=raw if isinstance(raw,str) else "")
                    self._me_pad_vars[ns] = var
                    ttk.Combobox(card, textvariable=var, values=[""]+pad_opts,
                        width=11, state="normal", style="H.TCombobox").pack(fill="x")
                else:
                    var = tk.StringVar(value=raw if isinstance(raw,str) else "")
                    self._me_pad_vars[ns] = var
                    tk.Entry(card, textvariable=var, bg=C["btn"], fg=C["accent"],
                        font=("Courier",8), relief="flat",
                        insertbackground=C["accent"]).pack(fill="x")

    def _me_build_knob_grid(self):
        C = self.C
        for w in self._me_knob_frame.winfo_children(): w.destroy()
        self._me_knob_vars = {}
        mode = self._me_mode_var.get() if hasattr(self,"_me_mode_var") else "gamepad"
        prog = self._get_current_preset() or {}
        knobs = prog.get("knobs",{})
        knob_opts = AXIS_OPTIONS if mode=="gamepad" else []
        for i, cc in enumerate(KNOB_CC):
            cell = tk.Frame(self._me_knob_frame, bg=C["panel2"], padx=3, pady=4)
            cell.grid(row=0, column=i, padx=2, pady=2, sticky="nsew")
            self._me_knob_frame.columnconfigure(i, weight=1)
            tk.Label(cell, text=KNOB_LABELS[i], font=("Courier",8,"bold"),
                fg=C["accent"], bg=C["panel2"]).pack()
            tk.Label(cell, text=f"CC{cc}", font=("Courier",6),
                fg=C["dim"], bg=C["panel2"]).pack()
            var = tk.StringVar(value=knobs.get(str(cc),""))
            self._me_knob_vars[str(cc)] = var
            if knob_opts:
                ttk.Combobox(cell, textvariable=var, values=[""]+knob_opts,
                    width=7, state="normal", style="H.TCombobox").pack(fill="x")
            else:
                tk.Entry(cell, textvariable=var, bg=C["btn"], fg=C["accent"],
                    font=("Courier",7), relief="flat",
                    insertbackground=C["accent"]).pack(fill="x")

    def _me_midi_learn(self, pad_key, btn):
        if self._learn_target: self._learn_target[1].config(bg=self.C["panel2"], fg=self.C["dim"])
        self._learn_target = (pad_key, btn)
        btn.config(bg=self.C["learn"], fg="white")
        self._log(f"[LEARN] Appuie sur le pad physique…")

    def _me_collect_preset(self):
        mode = self._me_mode_var.get()
        prog = {"mode": mode, "name": self._me_name_var.get()}
        if mode=="websocket": prog["ws_url"] = self._me_ws_url_var.get()
        if mode=="obs":
            prog["obs_host"]     = self._me_obs_host_var.get()
            try: prog["obs_port"] = int(self._me_obs_port_var.get())
            except: prog["obs_port"] = 4455
            prog["obs_password"] = self._me_obs_pass_var.get()
        if mode in ("sound_preset","music"): prog["sounds_dir"] = self._me_sounds_dir_var.get()

        # pads bank A
        bank = self._me_bank_var.get()
        pads_key = "pads" if bank=="A" else "pads_bank_b"
        pads = {}
        for ns, var in self._me_pad_vars.items():
            if mode=="obs":
                act = var.get()
                if not act: continue
                sub_var = self._me_pad_sub_vars.get(ns)
                d = {"action": act}
                if sub_var and sub_var.get():
                    sv = sub_var.get()
                    if act in OBS_NEEDS_SCENE:   d["scene"]  = sv
                    elif act in OBS_NEEDS_SOURCE: d["source"] = sv
                    elif act=="hotkey":           d["hotkey"] = sv
                pads[ns] = d
            elif mode in ("sound_preset","music"):
                file_v = var.get()
                if not file_v: continue
                if file_v=="stop_all": pads[ns]="stop_all"; continue
                sub = self._me_pad_sub_vars.get(ns)
                entry = {"file": file_v}
                if sub:
                    vol_var, loop_var = sub
                    try: entry["volume"] = float(vol_var.get())
                    except: entry["volume"] = 1.0
                    if loop_var.get(): entry["loop"] = True
                pads[ns] = entry
            else:
                v = var.get()
                if v: pads[ns] = v

        if pads: prog[pads_key] = pads

        # keep the OTHER bank untouched
        existing = self._get_current_preset() or {}
        other_key = "pads_bank_b" if bank=="A" else "pads"
        if other_key in existing: prog[other_key] = existing[other_key]

        # knobs
        knobs = {cc: v.get() for cc,v in self._me_knob_vars.items() if v.get()}
        if knobs: prog["knobs"] = knobs

        pw = self._me_pitch_var.get(); mw = self._me_mod_var.get()
        if pw: prog["pitchwheel"] = pw
        if mw: prog["modwheel"]   = mw
        return prog

    def _me_validate(self, prog):
        errors = []
        if not prog.get("name"): errors.append("Le nom est vide.")
        if prog.get("mode")=="obs":
            try: int(prog.get("obs_port",""))
            except: errors.append("OBS port invalide (doit être un entier).")
        return errors

    def _me_save(self):
        prog   = self._me_collect_preset()
        errors = self._me_validate(prog)
        if errors:
            messagebox.showerror("Erreur de validation", "\n".join(errors)); return
        self.config["programs"][self._current_prog] = prog
        self._save_config()
        # rebuild prog pills
        prog_keys   = list(self.config["programs"].keys())
        prog_labels = [f"{k} — {self.config['programs'][k].get('name','')}" for k in prog_keys]
        self._me_prog_map = dict(zip(prog_labels, prog_keys))
        self._me_prog_cb.config(values=prog_labels)
        for label,key in self._me_prog_map.items():
            if key==self._current_prog: self._me_prog_var.set(label); break
        self._build_prog_btns(); self._select_program(self._current_prog)
        self._me_save_indicator.config(text="✓ sauvegardé")
        self.root.after(2000, lambda: self._me_save_indicator.config(text=""))
        self._log(f"[MAP] Preset {self._current_prog} sauvegardé")

    def _me_new_preset(self):
        keys    = list(self.config["programs"].keys())
        new_key = str(max(int(k) for k in keys)+1)
        name    = simpledialog.askstring("Nouveau preset", "Nom :", parent=self.root) or f"Programme {new_key}"
        self.config["programs"][new_key] = {"mode":"debug","name":name}
        self._save_config()
        self._current_prog = new_key
        self._build_prog_btns(); self._select_program(new_key)
        # rebuild cb
        prog_keys   = list(self.config["programs"].keys())
        prog_labels = [f"{k} — {self.config['programs'][k].get('name','')}" for k in prog_keys]
        self._me_prog_map = dict(zip(prog_labels, prog_keys))
        self._me_prog_cb.config(values=prog_labels)
        for label,key in self._me_prog_map.items():
            if key==new_key: self._me_prog_var.set(label); break
        self._me_load_preset()

    def _me_delete_preset(self):
        if len(self.config["programs"]) <= 1:
            messagebox.showwarning("Suppression","Impossible de supprimer le dernier preset."); return
        if messagebox.askyesno("Supprimer",f"Supprimer le programme {self._current_prog} ?"):
            del self.config["programs"][self._current_prog]
            self._save_config()
            self._current_prog = list(self.config["programs"].keys())[0]
            self._build_prog_btns(); self._select_program(self._current_prog)
            prog_keys   = list(self.config["programs"].keys())
            prog_labels = [f"{k} — {self.config['programs'][k].get('name','')}" for k in prog_keys]
            self._me_prog_map = dict(zip(prog_labels, prog_keys))
            self._me_prog_cb.config(values=prog_labels)
            for label,key in self._me_prog_map.items():
                if key==self._current_prog: self._me_prog_var.set(label); break
            self._me_load_preset()

    def on_close(self):
        self._mon_stop.set(); self.combo_engine.stop()
        if self.listener: self.listener.stop()
        self._save_config(); self.root.destroy()


# ─────────────────────────────────────────────────────────────────────────────
def main():
    try:
        with open("config.json") as f: cfg = json.load(f)
    except Exception: cfg = {}
    theme_name   = cfg.get("theme","dark")
    default_mode = cfg.get("window_mode","NORMAL")
    C = get_theme(theme_name)
    chosen_mode = ask_window_mode(default_mode, C) or default_mode
    root = tk.Tk()
    app  = HexPadGUI(root, window_mode=chosen_mode)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()

if __name__ == "__main__":
    main()
