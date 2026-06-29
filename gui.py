#!/usr/bin/env python3
"""
HexPad GUI v2.4.0
  - Fenêtre unique redimensionnable
  - Mapping Editor en Toplevel dédié (bouton ⚙ dans le header)
  - Console rétractable (toggle ▾/▴)
  - Panneau TEST intégré (notebook) : MIDI monitor, HTTP, WebSocket, Bridges, OLED
  - Mode/taille de fenêtre sauvegardés silencieusement
  - [NEW] MIDI Learn dans le Mapping Editor (appuie physiquement sur un pad)
  - [NEW] Hotkeys globaux configurables (Ctrl+Shift+S, +◀▶, +1-4)
  - [NEW] Bouton [🖥 OLED] dans le header → fenêtre rapide OLED sans passer par TEST
  - [NEW] Flèches ◀ ▶ dans la device row pour switcher de profil instantanément
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
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
from modules.http_bridge      import HttpBridge
from modules.sound_preset_bridge import SoundPresetBridge
from modules.display_panel    import OLEDPanel
from modules.hotkey_manager   import HotKeyManager

try:
    from modules.music_bridge import MusicBridge
    MUSIC_OK = True
except ImportError:
    MUSIC_OK = False

VERSION = "2.4.0"

DEFAULT_W, DEFAULT_H = 520, 840
MIN_W,     MIN_H     = 460, 600

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
HTTP_METHODS  = ["GET", "POST", "PUT", "DELETE", "PATCH"]

_NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
def note_name(n): return f"{_NOTE_NAMES[n%12]}{(n//12)-1}"


# ─────────────────────────────────────────────────────────────────────────────
class HexPadGUI:
    def __init__(self, root):
        self.root          = root
        self._orig_print   = builtins.print
        self.running       = False
        self.listener      = None
        self._learn_target = None  # (pad_key, btn_widget) quand MIDI Learn actif
        self._learn_type   = None  # "note" ou "cc"
        self._pad_btns     = {}
        self._current_prog = "1"
        self._editor_win   = None
        self._oled_win     = None
        self._hotkey_win   = None
        self._console_visible = True
        self.config        = self._load_config()
        self.profiles      = GameProfiles()
        self.combo_engine  = ComboEngine()
        theme_name = self.config.get("theme", "dark")
        self.C = get_theme(theme_name)
        # Hotkey manager
        self.hotkey_mgr = HotKeyManager(self.config, log_fn=self._log)
        self._register_hotkeys()
        self.hotkey_mgr.start()
        self._apply_window()
        self._build_ui()
        if self.config.get("programs"):
            self._select_program(self._current_prog)
        self._sync_profile()
        self._mon_stop = threading.Event()
        self._start_monitor()

    # ── Hotkeys ───────────────────────────────────────────────────────────────
    def _register_hotkeys(self):
        self.hotkey_mgr.register("start_stop",   self._hotkey_start_stop)
        self.hotkey_mgr.register("profile_next", self._hotkey_profile_next)
        self.hotkey_mgr.register("profile_prev", self._hotkey_profile_prev)
        for i in range(1, 9):
            self.hotkey_mgr.register(f"profile_{i}", lambda idx=i: self._hotkey_profile_index(idx))

    def _hotkey_start_stop(self):
        self.root.after(0, lambda: self._stop() if self.running else self._start())

    def _hotkey_profile_next(self):
        self.root.after(0, self._profile_step, +1)

    def _hotkey_profile_prev(self):
        self.root.after(0, self._profile_step, -1)

    def _hotkey_profile_index(self, idx: int):
        self.root.after(0, self._profile_by_index, idx - 1)

    def _profile_step(self, delta: int):
        names = self.profiles.names
        if not names: return
        cur = self.profile_var.get()
        try: i = names.index(cur)
        except ValueError: i = 0
        new_i = (i + delta) % len(names)
        self.profile_var.set(names[new_i])
        self._on_profile_changed()

    def _profile_by_index(self, idx: int):
        names = self.profiles.names
        if 0 <= idx < len(names):
            self.profile_var.set(names[idx])
            self._on_profile_changed()

    # ── Window ────────────────────────────────────────────────────────────────
    def _apply_window(self):
        C = self.C
        w = self.config.get("window_w", DEFAULT_W)
        h = self.config.get("window_h", DEFAULT_H)
        self.root.title(f"HexPad v{VERSION}")
        self.root.configure(bg=C["bg"])
        self.root.resizable(True, True)
        self.root.minsize(MIN_W, MIN_H)
        self.root.geometry(f"{w}x{h}")
        self.root.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        if event.widget is self.root:
            self.config["window_w"] = event.width
            self.config["window_h"] = event.height

    def _load_config(self):
        try:
            with open("config.json") as f: return json.load(f)
        except Exception as e:
            messagebox.showerror("Erreur config", str(e)); sys.exit(1)

    def _save_config(self):
        with open("config.json", "w") as f:
            json.dump(self.config, f, indent=2)

    def _toggle_theme(self):
        new_name = "light" if self.C["name"] == "dark" else "dark"
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
            font=("Courier", 8, "bold"), padding=[10, 4])
        s.map("H.TNotebook.Tab",
            background=[("selected", C["panel"])],
            foreground=[("selected", C["accent"])])

    def _sep(self, parent):
        tk.Frame(parent, bg=self.C["border"], height=1).pack(fill="x", padx=12, pady=4)

    def on_close(self):
        self._save_config()
        self._mon_stop.set()
        self.hotkey_mgr.stop()
        if self.listener: self.listener.stop()
        self.root.destroy()

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        self._style()
        self.root.configure(bg=self.C["bg"])
        self._build_header(self.root)
        self._build_device_row(self.root)
        self._sep(self.root)
        self._nb = ttk.Notebook(self.root, style="H.TNotebook")
        self._nb.pack(fill="both", expand=True, padx=0, pady=0)
        self._tab_run  = tk.Frame(self._nb, bg=self.C["bg"])
        self._tab_test = tk.Frame(self._nb, bg=self.C["bg"])
        self._nb.add(self._tab_run,  text="  ▶ RUN  ")
        self._nb.add(self._tab_test, text="  ⚗ TEST  ")
        self._build_run_tab(self._tab_run)
        self._build_test_tab(self._tab_test)

    def _build_run_tab(self, parent):
        self._build_prog_section(parent)
        self._sep(parent)
        self._build_pad_monitor(parent)
        self._sep(parent)
        self._build_combos(parent)
        self._sep(parent)
        self._build_start_stop(parent)
        self._sep(parent)
        self._build_console_section(parent)

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self, parent):
        C = self.C
        hdr = tk.Frame(parent, bg=C["panel"], pady=7)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⬡", font=("Courier", 20, "bold"),
            fg=C["accent"], bg=C["panel"]).pack(side="left", padx=(10, 2))
        tk.Label(hdr, text="HexPad", font=("Courier", 14, "bold"),
            fg=C["text"], bg=C["panel"]).pack(side="left")
        tk.Label(hdr, text=f" v{VERSION}", font=("Courier", 7),
            fg=C["dim"], bg=C["panel"]).pack(side="left")
        # Boutons droite
        tk.Button(hdr, text="✕", font=("Courier", 10, "bold"),
            bg=C["panel"], fg=C["dim"], relief="flat", padx=8,
            cursor="hand2", command=self.on_close).pack(side="right", padx=2)
        tk.Button(hdr, text="–", font=("Courier", 10, "bold"),
            bg=C["panel"], fg=C["dim"], relief="flat", padx=8,
            cursor="hand2", command=self.root.iconify).pack(side="right", padx=2)
        tk.Button(hdr, text=C["toggle_icon"], font=("Courier", 10),
            bg=C["panel"], fg=C["accent"], relief="flat", padx=8,
            cursor="hand2", command=self._toggle_theme).pack(side="right", padx=2)
        tk.Button(hdr, text="⚙ Mapping", font=("Courier", 8, "bold"),
            bg=C["accent2"], fg=C["bg"], relief="flat", padx=10, pady=2,
            cursor="hand2", command=self._open_editor).pack(side="right", padx=4)
        # [NEW] Bouton OLED rapide
        tk.Button(hdr, text="🖥 OLED", font=("Courier", 8, "bold"),
            bg=C["panel2"], fg=C["accent"], relief="flat", padx=8, pady=2,
            cursor="hand2", command=self._open_oled_window).pack(side="right", padx=4)
        # [NEW] Bouton Hotkeys
        hk_color = C["green"] if HotKeyManager.is_available() else C["dim"]
        tk.Button(hdr, text="⌨ Keys", font=("Courier", 8, "bold"),
            bg=C["panel2"], fg=hk_color, relief="flat", padx=8, pady=2,
            cursor="hand2", command=self._open_hotkey_window).pack(side="right", padx=4)

    # ── Device row ────────────────────────────────────────────────────────────
    def _build_device_row(self, parent):
        C = self.C
        dp = tk.Frame(parent, bg=C["bg"], pady=4)
        dp.pack(fill="x", padx=10)
        self.status_dot = tk.Label(dp, text="●", font=("Courier", 12, "bold"),
            fg=C["red"], bg=C["bg"])
        self.status_dot.pack(side="left", padx=(0, 2))
        devices = mido.get_input_names() or ["Aucun"]
        self.device_var = tk.StringVar(value=self.config.get("device_name", ""))
        self._dev_cb = ttk.Combobox(dp, textvariable=self.device_var,
            values=devices, width=18, state="readonly", style="H.TCombobox")
        self._dev_cb.pack(side="left", padx=2)
        for d in devices:
            if any(x in d.lower() for x in ("mpk", "mini", "akai")):
                self.device_var.set(d); break
        tk.Button(dp, text="↺", font=("Courier", 10, "bold"),
            bg=C["bg"], fg=C["accent2"], relief="flat", padx=4,
            cursor="hand2", command=self._refresh_devices).pack(side="left", padx=2)
        tk.Label(dp, text="|", fg=C["border"], bg=C["bg"],
            font=("Courier", 10)).pack(side="left", padx=4)
        # [NEW] flèches profil rapide ◀ ▶
        tk.Button(dp, text="◀", font=("Courier", 9, "bold"),
            bg=C["bg"], fg=C["dim"], relief="flat", padx=3,
            cursor="hand2", command=lambda: self._profile_step(-1)).pack(side="left")
        self.profile_var = tk.StringVar(value=self.profiles.active)
        self.profile_cb = ttk.Combobox(dp, textvariable=self.profile_var,
            values=self.profiles.names, width=12, state="readonly", style="H.TCombobox")
        self.profile_cb.pack(side="left", padx=2)
        self.profile_cb.bind("<<ComboboxSelected>>", self._on_profile_changed)
        tk.Button(dp, text="▶", font=("Courier", 9, "bold"),
            bg=C["bg"], fg=C["dim"], relief="flat", padx=3,
            cursor="hand2", command=lambda: self._profile_step(+1)).pack(side="left")

    def _refresh_devices(self):
        devices = mido.get_input_names() or ["Aucun"]
        self._dev_cb.config(values=devices)
        self._log(f"[MIDI] {len(devices)} device(s) trouvé(s)")
        for d in devices:
            if any(x in d.lower() for x in ("mpk", "mini", "akai")):
                self.device_var.set(d); break

    # ── Programmes ────────────────────────────────────────────────────────────
    def _build_prog_section(self, parent):
        C = self.C
        tk.Label(parent, text="  PROGRAMME", font=("Courier", 7, "bold"),
            fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=12)
        self.prog_frame = tk.Frame(parent, bg=C["bg"])
        self.prog_frame.pack(fill="x", padx=10, pady=4)
        self.prog_btns = {}
        self._build_prog_btns()

    def _build_prog_btns(self):
        for w in self.prog_frame.winfo_children(): w.destroy()
        self.prog_btns = {}; C = self.C
        for key, prog in self.config.get("programs", {}).items():
            mode = prog.get("mode", "debug")
            col  = MODE_COLORS.get(mode, C["dim"])
            name = prog.get("name", mode)[:6].upper()
            b = tk.Button(self.prog_frame,
                text=f"{key}\n{name}",
                font=("Courier", 8, "bold"),
                bg=C["btn"], fg=col,
                activebackground=col, activeforeground=C["bg"],
                relief="flat", padx=6, pady=6, width=6, cursor="hand2",
                command=lambda k=key: self._select_program(k))
            b.pack(side="left", padx=2)
            self.prog_btns[key] = (b, col)

    # ── Pad monitor ───────────────────────────────────────────────────────────
    def _build_pad_monitor(self, parent):
        C = self.C
        tk.Label(parent, text="  PAD MONITOR", font=("Courier", 7, "bold"),
            fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=12)
        pf = tk.Frame(parent, bg=C["bg"])
        pf.pack(padx=10, pady=4)
        self._pad_btns = {}
        for i, note in enumerate(PAD_BANK_A):
            col, row_idx = i % 4, i // 4
            btn = tk.Label(pf, text=f"P{i+1}",
                font=("Courier", 10, "bold"),
                bg=C["pad_off"], fg=C["dim"],
                width=6, pady=9, relief="flat")
            btn.grid(row=row_idx, column=col, padx=3, pady=3)
            self._pad_btns[str(note)] = btn

    # ── Combos ────────────────────────────────────────────────────────────────
    def _build_combos(self, parent):
        C = self.C
        combo_hdr = tk.Frame(parent, bg=C["bg"])
        combo_hdr.pack(fill="x", padx=10)
        tk.Label(combo_hdr, text="  COMBOS", font=("Courier", 7, "bold"),
            fg=C["combo"], bg=C["bg"]).pack(side="left")
        tk.Label(combo_hdr, text=self.profiles.active, font=("Courier", 7),
            fg=C["dim"], bg=C["bg"]).pack(side="left", padx=6)
        self.combo_frame = tk.Frame(parent, bg=C["bg"])
        self.combo_frame.pack(fill="x", padx=10, pady=4)
        self._build_combo_buttons()

    def _build_combo_buttons(self):
        C = self.C
        for w in self.combo_frame.winfo_children(): w.destroy()
        combos = self.profiles.get_combos()
        if not combos:
            tk.Label(self.combo_frame,
                text="Aucun combo — editez game_profiles.json",
                font=("Courier", 7), fg=C["dim"], bg=C["bg"]).pack(anchor="w")
            return
        for i, (key, combo) in enumerate(combos.items()):
            label = combo.get("label", key)
            seq   = combo.get("sequence", "")
            loop  = combo.get("loop", False)
            btn = tk.Button(self.combo_frame,
                text=f"▶ {label}",
                font=("Courier", 9, "bold"),
                bg=C["btn"], fg=C["combo"],
                activebackground=C["combo"], activeforeground=C["bg"],
                relief="flat", padx=6, pady=6, cursor="hand2",
                command=lambda s=seq, l=loop, lb=label: self._fire_combo(s, l, lb))
            btn.grid(row=i // 2, column=i % 2, padx=2, pady=2, sticky="ew")
        self.combo_frame.columnconfigure(0, weight=1)
        self.combo_frame.columnconfigure(1, weight=1)

    def _fire_combo(self, seq, loop, label):
        self._log(f"[COMBO] ▶ {label}")
        self.combo_engine.execute(seq, loop=loop)

    # ── Profile ───────────────────────────────────────────────────────────────
    def _on_profile_changed(self, event=None):
        name = self.profile_var.get()
        self.profiles.active = name
        prof = self.profiles.get_profile(name)
        if prof:
            prog = prof.get("program", "1")
            if prog in self.config["programs"]:
                self._select_program(prog)
        self._build_combo_buttons()
        self._log(f"[PROFILE] {name}")

    def _sync_profile(self): self._build_combo_buttons()

    def _get_current_preset(self):
        return self.config["programs"].get(self._current_prog)

    def _select_program(self, key):
        if key not in self.config["programs"]:
            key = list(self.config["programs"].keys())[0]
        self._current_prog = key
        for k, (b, col) in self.prog_btns.items():
            b.config(
                bg=col if k == key else self.C["btn"],
                fg=self.C["sel_fg"] if k == key else col
            )
        self._log(f"[PROG] {key} — {self.config['programs'][key].get('name', '')}")
        if hasattr(self, "_me_loaded"):
            self._me_load_preset()

    # ── Start / Stop ──────────────────────────────────────────────────────────
    def _build_start_stop(self, parent):
        C = self.C
        ctrl = tk.Frame(parent, bg=C["bg"])
        ctrl.pack(fill="x", padx=10, pady=4)
        # label hotkey hint
        hk_cfg = self.config.get("hotkeys", {})
        ss_combo = next((k for k, v in hk_cfg.items() if v == "start_stop"), "Ctrl+Shift+S")
        tk.Label(ctrl, text=f"hotkey : {ss_combo}",
            font=("Courier", 7), fg=C["dim"], bg=C["bg"]).pack(anchor="e")
        self.start_btn = tk.Button(ctrl,
            text="▶▶  START", font=("Courier", 12, "bold"),
            bg=C["green"], fg=C["bg"], relief="flat", pady=12,
            cursor="hand2", command=self._start)
        self.start_btn.pack(fill="x", pady=(0, 4))
        self.stop_btn = tk.Button(ctrl,
            text="■  STOP", font=("Courier", 12, "bold"),
            bg=C["red"], fg="white", relief="flat", pady=10,
            state="disabled", cursor="hand2", command=self._stop)
        self.stop_btn.pack(fill="x")

    def _build_bridge(self, prog):
        mode = prog.get("mode", "debug")
        if mode == "gamepad":      return GamepadBridge(prog), mode
        if mode == "websocket":    return WebSocketBridge(prog.get("ws_url", "ws://localhost:8765")), mode
        if mode == "macro":        return MacroBridge(prog), mode
        if mode == "obs":          return OBSBridge(prog), mode
        if mode == "http":         return HttpBridge(prog), mode
        if mode == "sound_preset": return SoundPresetBridge(prog), mode
        if mode == "music":
            if MUSIC_OK:
                return MusicBridge(prog), mode
            else:
                self._log("[MUSIC] ⚠ pygame/sounddevice manquants — mode debug utilisé")
                return None, "debug"
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
            try: self.listener.start()
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
        self.running  = False
        self.listener = None
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_dot.config(fg=self.C["red"])
        self._log("■ Arrete.")

    # ── Console rétractable ───────────────────────────────────────────────────
    def _build_console_section(self, parent):
        C = self.C
        tog_row = tk.Frame(parent, bg=C["bg"])
        tog_row.pack(fill="x", padx=10)
        self._console_toggle_btn = tk.Button(
            tog_row, text="▾ Console",
            font=("Courier", 7, "bold"),
            bg=C["bg"], fg=C["dim"],
            relief="flat", padx=4, pady=2,
            cursor="hand2", anchor="w",
            command=self._toggle_console
        )
        self._console_toggle_btn.pack(side="left")
        self._console_frame = tk.Frame(parent, bg=C["bg"])
        self._console_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.console = scrolledtext.ScrolledText(
            self._console_frame,
            bg=C["console_bg"], fg=C["console_fg"],
            font=("Courier", 8), relief="flat", height=6,
            insertbackground=C["accent"],
            selectbackground=C["accent2"]
        )
        self.console.pack(fill="both", expand=True)
        self.console.config(state="disabled")
        hk_status = "✓ pynput" if HotKeyManager.is_available() else "⚠ pip install pynput"
        music_status = "" if MUSIC_OK else "  ⚠ pip install pygame sounddevice"
        self._log(f"⬡ HexPad v{VERSION} ready  theme:{self.C['name']}  {hk_status}{music_status}")

    def _toggle_console(self):
        self._console_visible = not self._console_visible
        if self._console_visible:
            self._console_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))
            self._console_toggle_btn.config(text="▾ Console")
        else:
            self._console_frame.pack_forget()
            self._console_toggle_btn.config(text="▸ Console")

    def _log(self, msg):
        if not hasattr(self, "console"): return
        self.console.config(state="normal")
        self.console.insert("end", msg + "\n")
        self.console.see("end")
        self.console.config(state="disabled")

    # ── Monitor MIDI ──────────────────────────────────────────────────────────
    def _start_monitor(self):
        def run():
            while not self._mon_stop.is_set():
                try:
                    device = None
                    for d in mido.get_input_names():
                        if any(x in d.lower() for x in ("mpk", "mini", "akai")):
                            device = d; break
                    if not device: time.sleep(2); continue
                    with mido.open_input(device) as port:
                        while not self._mon_stop.is_set():
                            msg = port.poll()
                            if msg and msg.type == "note_on" and msg.velocity > 0:
                                ns = str(msg.note)
                                if ns in self._pad_btns:
                                    b  = self._pad_btns[ns]
                                    hc = self.C["accent"]
                                    self.root.after(0, b.config, {"bg": hc, "fg": self.C["bg"]})
                                    self.root.after(200, b.config, {"bg": self.C["pad_off"], "fg": self.C["dim"]})
                                # MIDI Learn : note
                                if self._learn_target and self._learn_type == "note":
                                    self.root.after(0, self._on_learn_received, "note", msg.note)
                                # Feed test MIDI log if active
                                if hasattr(self, "_test_midi_log"):
                                    label = f"note_on  note={msg.note} ({note_name(msg.note)})  vel={msg.velocity}"
                                    self.root.after(0, self._test_append, label)
                            elif msg and msg.type == "control_change":
                                # MIDI Learn : CC
                                if self._learn_target and self._learn_type == "cc":
                                    self.root.after(0, self._on_learn_received, "cc", msg.control)
                                if hasattr(self, "_test_midi_log"):
                                    label = f"cc       cc={msg.control}  val={msg.value}"
                                    self.root.after(0, self._test_append, label)
                            time.sleep(0.001)
                except Exception: time.sleep(1)
        threading.Thread(target=run, daemon=True).start()

    def _on_learn_received(self, msg_type: str, value: int):
        """Appelé depuis le monitor quand un message MIDI arrive pendant le Learn."""
        if not self._learn_target: return
        target_info, btn, callback = self._learn_target
        self._learn_target = None
        self._learn_type   = None
        name = note_name(value) if msg_type == "note" else f"CC{value}"
        self._log(f"[LEARN] {msg_type.upper()} {value} ({name}) → {target_info}")
        btn.config(bg=self.C["panel2"], fg=self.C["dim"], text="🎹 Learn")
        if callback:
            callback(msg_type, value)

    def _start_learn(self, target_info: str, btn_widget, msg_type: str, callback):
        """Active le mode MIDI Learn pour un champ."""
        # Annule un learn précédent
        if self._learn_target:
            _, old_btn, _ = self._learn_target
            old_btn.config(bg=self.C["panel2"], fg=self.C["dim"], text="🎹 Learn")
        self._learn_target = (target_info, btn_widget, callback)
        self._learn_type   = msg_type
        btn_widget.config(bg=self.C["accent"], fg=self.C["bg"], text="⏳ Attend...")
        self._log(f"[LEARN] En attente de {msg_type.upper()} pour '{target_info}'...")

    # ── Fenêtre OLED rapide ───────────────────────────────────────────────────
    def _open_oled_window(self):
        """Ouvre un Toplevel dédié au panneau OLED (accessible sans passer par TEST)."""
        if self._oled_win and self._oled_win.winfo_exists():
            self._oled_win.lift()
            return
        C = self.C
        win = tk.Toplevel(self.root)
        win.title("HexPad — OLED Display")
        win.configure(bg=C["bg"])
        win.resizable(True, True)
        win.geometry("540x480")
        win.transient(self.root)
        tk.Label(win, text="🖥 AKAI OLED", font=("Courier", 10, "bold"),
            fg=C["accent"], bg=C["bg"]).pack(anchor="w", padx=12, pady=(10, 2))
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=12, pady=2)
        panel = OLEDPanel(win, self)
        panel.pack(fill="both", expand=True, padx=8, pady=8)
        self._oled_win = win

    # ── Fenêtre Hotkeys config ────────────────────────────────────────────────
    def _open_hotkey_window(self):
        """Fenêtre de visualisation et configuration des hotkeys globaux."""
        if self._hotkey_win and self._hotkey_win.winfo_exists():
            self._hotkey_win.lift()
            return
        C = self.C
        win = tk.Toplevel(self.root)
        win.title("HexPad — Hotkeys globaux")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        win.geometry("480x420")
        win.transient(self.root)
        self._hotkey_win = win

        tk.Label(win, text="⌨ HOTKEYS GLOBAUX", font=("Courier", 10, "bold"),
            fg=C["accent"], bg=C["bg"]).pack(anchor="w", padx=12, pady=(10, 2))
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=12, pady=2)

        if not HotKeyManager.is_available():
            tk.Label(win,
                text="⚠  pynput non installé\npip install pynput",
                font=("Courier", 9), fg=C["red"], bg=C["bg"],
                justify="center").pack(pady=20)
            return

        info = tk.Label(win,
            text="Les raccourcis fonctionnent même quand la fenêtre n'a pas le focus.",
            font=("Courier", 7), fg=C["dim"], bg=C["bg"], wraplength=440, justify="left")
        info.pack(anchor="w", padx=12, pady=(0, 8))

        hk_config = self.hotkey_mgr.get_hotkeys_config()
        actions   = HotKeyManager.available_actions()

        # Grille combo → action
        grid_frame = tk.Frame(win, bg=C["bg"])
        grid_frame.pack(fill="x", padx=12)
        tk.Label(grid_frame, text="Raccourci clavier", font=("Courier", 8, "bold"),
            fg=C["accent2"], bg=C["bg"]).grid(row=0, column=0, sticky="w", padx=4, pady=2)
        tk.Label(grid_frame, text="Action", font=("Courier", 8, "bold"),
            fg=C["accent2"], bg=C["bg"]).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        self._hk_vars = {}  # combo_str -> StringVar(action)
        for row_i, (combo, action) in enumerate(hk_config.items(), start=1):
            tk.Label(grid_frame, text=combo, font=("Courier", 8),
                fg=C["text"], bg=C["btn"], padx=6, pady=2,
                relief="flat").grid(row=row_i, column=0, sticky="w", padx=4, pady=2)
            var = tk.StringVar(value=action)
            cb  = ttk.Combobox(grid_frame, textvariable=var,
                values=actions, width=18, state="readonly", style="H.TCombobox")
            cb.grid(row=row_i, column=1, padx=4, pady=2)
            self._hk_vars[combo] = var

        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=12, pady=8)

        btn_row = tk.Frame(win, bg=C["bg"])
        btn_row.pack(fill="x", padx=12, pady=4)

        def _apply():
            new_cfg = {combo: var.get() for combo, var in self._hk_vars.items()}
            self.hotkey_mgr.set_hotkeys_config(new_cfg)
            self.hotkey_mgr.restart()
            self._save_config()
            self._log("[HOTKEY] Config mise à jour et rechargée.")
            win.destroy()

        def _reset():
            from modules.hotkey_manager import DEFAULT_HOTKEYS
            self.hotkey_mgr.set_hotkeys_config(dict(DEFAULT_HOTKEYS))
            self.hotkey_mgr.restart()
            self._save_config()
            self._log("[HOTKEY] Config réinitialisée aux valeurs par défaut.")
            win.destroy()
            self._open_hotkey_window()

        tk.Button(btn_row, text="✓ Appliquer", font=("Courier", 9, "bold"),
            bg=C["green"], fg=C["bg"], relief="flat", padx=14, pady=6,
            cursor="hand2", command=_apply).pack(side="left", padx=4)
        tk.Button(btn_row, text="↺ Réinitialiser", font=("Courier", 9),
            bg=C["btn"], fg=C["dim"], relief="flat", padx=10, pady=6,
            cursor="hand2", command=_reset).pack(side="left", padx=4)
        tk.Button(btn_row, text="✕ Fermer", font=("Courier", 9),
            bg=C["btn"], fg=C["dim"], relief="flat", padx=10, pady=6,
            cursor="hand2", command=win.destroy).pack(side="right", padx=4)

        # Tableau récapitulatif des actions disponibles
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=12, pady=4)
        tk.Label(win, text="Actions disponibles :",
            font=("Courier", 7, "bold"), fg=C["dim"], bg=C["bg"]).pack(anchor="w", padx=12)
        desc = "  start_stop · profile_next · profile_prev · profile_1 … profile_8"
        tk.Label(win, text=desc, font=("Courier", 7), fg=C["dim"],
            bg=C["bg"], wraplength=440, justify="left").pack(anchor="w", padx=12)

    # ── Mapping Editor (ouverture) ────────────────────────────────────────────
    def _open_editor(self):
        if self._editor_win and self._editor_win.winfo_exists():
            self._editor_win.lift(); return
        C = self.C
        win = tk.Toplevel(self.root)
        win.title("HexPad — Mapping Editor")
        win.configure(bg=C["bg"])
        win.resizable(True, True)
        win.geometry("600x700")
        win.transient(self.root)
        self._editor_win = win
        self._me_loaded  = True
        self._build_mapping_editor(win)

    def _build_mapping_editor(self, parent):
        C = self.C
        # Header
        hdr = tk.Frame(parent, bg=C["panel"], pady=6)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚙ MAPPING EDITOR", font=("Courier", 10, "bold"),
            fg=C["accent"], bg=C["panel"]).pack(side="left", padx=12)

        # [NEW] Bouton MIDI Learn global dans l'éditeur
        self._me_learn_active = False
        self._me_learn_btn = tk.Button(hdr,
            text="🎹 MIDI Learn",
            font=("Courier", 8, "bold"),
            bg=C["panel2"], fg=C["accent2"],
            relief="flat", padx=8, pady=2, cursor="hand2",
            command=self._me_toggle_learn_mode)
        self._me_learn_btn.pack(side="right", padx=6)

        tk.Button(hdr, text="💾 Sauvegarder", font=("Courier", 8, "bold"),
            bg=C["green"], fg=C["bg"], relief="flat", padx=10, pady=2,
            cursor="hand2", command=self._me_save).pack(side="right", padx=4)

        tk.Label(parent, text="  Sélectionnez un programme :",
            font=("Courier", 7), fg=C["dim"], bg=C["bg"]).pack(anchor="w", padx=12, pady=(8, 0))

        # Programme selector
        prog_row = tk.Frame(parent, bg=C["bg"])
        prog_row.pack(fill="x", padx=12, pady=4)
        self._me_prog_var = tk.StringVar(value=self._current_prog)
        for key in self.config.get("programs", {}).keys():
            tk.Radiobutton(prog_row, text=f"Prog {key}",
                variable=self._me_prog_var, value=key,
                font=("Courier", 8), bg=C["bg"], fg=C["text"],
                selectcolor=C["panel"], activebackground=C["bg"],
                command=self._me_load_preset).pack(side="left", padx=6)

        tk.Frame(parent, bg=C["border"], height=1).pack(fill="x", padx=12, pady=4)

        # [NEW] Indicateur Learn Mode
        self._me_learn_status = tk.Label(parent,
            text="",
            font=("Courier", 8), fg=C["accent"], bg=C["bg"])
        self._me_learn_status.pack(anchor="w", padx=12)

        # Scrollable area
        container = tk.Frame(parent, bg=C["bg"])
        container.pack(fill="both", expand=True, padx=0, pady=0)
        canvas = tk.Canvas(container, bg=C["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._me_inner = tk.Frame(canvas, bg=C["bg"])
        self._me_win_id = canvas.create_window((0, 0), window=self._me_inner, anchor="nw")
        self._me_inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(self._me_win_id, width=e.width))
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        self._me_canvas = canvas
        self._me_load_preset()

    def _me_toggle_learn_mode(self):
        """Active/désactive le mode MIDI Learn global dans l'éditeur."""
        self._me_learn_active = not self._me_learn_active
        C = self.C
        if self._me_learn_active:
            self._me_learn_btn.config(bg=C["accent"], fg=C["bg"], text="⏹ Arrêter Learn")
            self._me_learn_status.config(
                text="🔴 Mode MIDI Learn actif — Clique sur [🎹] d'un pad/CC puis appuie sur l'AKAI")
        else:
            self._me_learn_btn.config(bg=C["panel2"], fg=C["accent2"], text="🎹 MIDI Learn")
            self._me_learn_status.config(text="")
            # Annule tout learn en cours
            if self._learn_target:
                _, old_btn, _ = self._learn_target
                old_btn.config(bg=C["panel2"], fg=C["dim"], text="🎹 Learn")
            self._learn_target = None
            self._learn_type   = None

    def _me_load_preset(self):
        for w in self._me_inner.winfo_children(): w.destroy()
        key  = self._me_prog_var.get()
        prog = self.config["programs"].get(key, {})
        mode = prog.get("mode", "debug")
        C = self.C
        # ── Pads
        tk.Label(self._me_inner, text=" PADS — Bank A",
            font=("Courier", 8, "bold"), fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=8, pady=(8,2))
        self._me_pad_vars   = {}
        self._me_pad_frame  = tk.Frame(self._me_inner, bg=C["bg"])
        self._me_pad_frame.pack(fill="x", padx=8)
        self._me_build_pad_grid()
        # ── Knobs
        tk.Frame(self._me_inner, bg=C["border"], height=1).pack(fill="x", padx=8, pady=6)
        tk.Label(self._me_inner, text=" KNOBS",
            font=("Courier", 8, "bold"), fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=8, pady=(0,2))
        knobs = prog.get("knobs", {})
        self._me_knob_vars = {}
        for i, (cc, label) in enumerate(zip(KNOB_CC, KNOB_LABELS)):
            self._me_build_knob_row(i, cc, label, knobs)
        # ── Mode-specific
        tk.Frame(self._me_inner, bg=C["border"], height=1).pack(fill="x", padx=8, pady=6)
        if mode == "gamepad":
            self._me_build_gamepad_section(prog)
        elif mode == "obs":
            self._me_build_obs_section(prog)
        elif mode == "http":
            self._me_build_http_section(prog)
        elif mode == "macro":
            self._me_build_macro_section(prog)

    def _me_build_pad_grid(self):
        """Construit la grille des pads avec boutons MIDI Learn individuels."""
        for w in self._me_pad_frame.winfo_children(): w.destroy()
        C = self.C
        key  = self._me_prog_var.get()
        prog = self.config["programs"].get(key, {})
        pads = prog.get("pads", {})
        mode = prog.get("mode", "debug")
        self._me_pad_vars = {}

        for col_i, note in enumerate(PAD_BANK_A):
            pad_key = str(note)
            pad_cfg = pads.get(pad_key, {})
            col_frame = tk.Frame(self._me_pad_frame, bg=C["bg"])
            col_frame.grid(row=0, column=col_i, padx=3, pady=3)

            # Label note
            tk.Label(col_frame, text=note_name(note),
                font=("Courier", 7), fg=C["dim"], bg=C["bg"]).pack()

            # Champ action
            opts = BTN_OPTIONS if mode == "gamepad" else MACRO_OPTIONS
            var = tk.StringVar(value=pad_cfg.get("action", opts[0] if opts else ""))
            cb = ttk.Combobox(col_frame, textvariable=var,
                values=opts, width=8, state="readonly", style="H.TCombobox")
            cb.pack()
            self._me_pad_vars[pad_key] = var

            # [NEW] Bouton Learn individuel
            learn_btn = tk.Button(col_frame, text="🎹 Learn",
                font=("Courier", 6), bg=C["panel2"], fg=C["dim"],
                relief="flat", padx=2, pady=1, cursor="hand2")
            learn_btn.pack(pady=(2, 0))

            def _make_learn_cb(p_key, l_btn):
                def _cb(msg_type, value):
                    # Met à jour le mapping dans config
                    k = self._me_prog_var.get()
                    p = self.config["programs"].get(k, {})
                    p.setdefault("pads", {})
                    p["pads"].setdefault(p_key, {})
                    p["pads"][p_key]["note"] = value
                    self._log(f"[LEARN] Pad {p_key} → note {value} ({note_name(value)})")
                    self._me_build_pad_grid()
                return _cb

            def _make_learn_cmd(p_key, l_btn):
                def _cmd():
                    if not self._me_learn_active:
                        self._me_toggle_learn_mode()
                    self._start_learn(f"pad {p_key}", l_btn, "note", _make_learn_cb(p_key, l_btn))
                return _cmd

            learn_btn.config(command=_make_learn_cmd(pad_key, learn_btn))

    def _me_build_knob_row(self, idx, cc, label, knobs):
        C = self.C
        row = tk.Frame(self._me_inner, bg=C["bg"])
        row.pack(fill="x", padx=8, pady=1)
        tk.Label(row, text=f"{label} (CC{cc})", font=("Courier", 8),
            fg=C["dim"], bg=C["bg"], width=12, anchor="w").pack(side="left")
        knob_cfg = knobs.get(str(cc), {})
        axis_var = tk.StringVar(value=knob_cfg.get("axis", AXIS_OPTIONS[idx % len(AXIS_OPTIONS)]))
        cb = ttk.Combobox(row, textvariable=axis_var,
            values=AXIS_OPTIONS, width=12, state="readonly", style="H.TCombobox")
        cb.pack(side="left", padx=4)
        self._me_knob_vars[str(cc)] = axis_var

        # [NEW] Bouton Learn CC
        learn_btn = tk.Button(row, text="🎹 Learn CC",
            font=("Courier", 6), bg=C["panel2"], fg=C["dim"],
            relief="flat", padx=4, pady=1, cursor="hand2")
        learn_btn.pack(side="left", padx=4)

        def _make_cc_learn_cb(cc_key, l_btn):
            def _cb(msg_type, value):
                k = self._me_prog_var.get()
                p = self.config["programs"].get(k, {})
                p.setdefault("knobs", {})
                p["knobs"].setdefault(cc_key, {})
                p["knobs"][cc_key]["cc"] = value
                self._log(f"[LEARN] Knob {cc_key} → CC{value}")
                self._me_load_preset()
            return _cb

        def _make_cc_learn_cmd(cc_key, l_btn):
            def _cmd():
                if not self._me_learn_active:
                    self._me_toggle_learn_mode()
                self._start_learn(f"knob CC{cc_key}", l_btn, "cc", _make_cc_learn_cb(cc_key, l_btn))
            return _cmd

        learn_btn.config(command=_make_cc_learn_cmd(str(cc), learn_btn))

    def _me_build_gamepad_section(self, prog):
        C = self.C
        tk.Label(self._me_inner, text=" GAMEPAD — Joysticks & Mode",
            font=("Courier", 8, "bold"), fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=8, pady=(0,4))
        joystick = prog.get("joystick", {})
        row_l = tk.Frame(self._me_inner, bg=C["bg"]); row_l.pack(fill="x", padx=8, pady=1)
        tk.Label(row_l, text="Pitch → Axis :", font=("Courier", 8),
            fg=C["dim"], bg=C["bg"], width=14, anchor="w").pack(side="left")
        self._me_js_pitch = tk.StringVar(value=joystick.get("pitch", "axis_x"))
        ttk.Combobox(row_l, textvariable=self._me_js_pitch,
            values=AXIS_OPTIONS, width=12, state="readonly", style="H.TCombobox").pack(side="left", padx=4)
        row_m = tk.Frame(self._me_inner, bg=C["bg"]); row_m.pack(fill="x", padx=8, pady=1)
        tk.Label(row_m, text="Mod → Axis :", font=("Courier", 8),
            fg=C["dim"], bg=C["bg"], width=14, anchor="w").pack(side="left")
        self._me_js_mod = tk.StringVar(value=joystick.get("modwheel", "axis_y"))
        ttk.Combobox(row_m, textvariable=self._me_js_mod,
            values=AXIS_OPTIONS, width=12, state="readonly", style="H.TCombobox").pack(side="left", padx=4)

    def _me_build_obs_section(self, prog):
        C = self.C
        tk.Label(self._me_inner, text=" OBS — Host & Port",
            font=("Courier", 8, "bold"), fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=8, pady=(0,4))
        row = tk.Frame(self._me_inner, bg=C["bg"]); row.pack(fill="x", padx=8, pady=1)
        tk.Label(row, text="host:port", font=("Courier", 8),
            fg=C["dim"], bg=C["bg"], width=12, anchor="w").pack(side="left")
        self._me_obs_host = tk.StringVar(value=prog.get("host", "localhost"))
        tk.Entry(row, textvariable=self._me_obs_host, font=("Courier", 8),
            bg=C["btn"], fg=C["text"], insertbackground=C["accent"],
            relief="flat", width=14).pack(side="left", padx=4)
        self._me_obs_port = tk.StringVar(value=str(prog.get("port", 4455)))
        tk.Entry(row, textvariable=self._me_obs_port, font=("Courier", 8),
            bg=C["btn"], fg=C["text"], insertbackground=C["accent"],
            relief="flat", width=6).pack(side="left", padx=2)

    def _me_build_http_section(self, prog):
        C = self.C
        tk.Label(self._me_inner, text=" HTTP — Base URL",
            font=("Courier", 8, "bold"), fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=8, pady=(0,4))
        row = tk.Frame(self._me_inner, bg=C["bg"]); row.pack(fill="x", padx=8, pady=1)
        tk.Label(row, text="base_url", font=("Courier", 8),
            fg=C["dim"], bg=C["bg"], width=12, anchor="w").pack(side="left")
        self._me_http_url = tk.StringVar(value=prog.get("base_url", "http://localhost"))
        tk.Entry(row, textvariable=self._me_http_url, font=("Courier", 8),
            bg=C["btn"], fg=C["text"], insertbackground=C["accent"],
            relief="flat", width=28).pack(side="left", padx=4)

    def _me_build_macro_section(self, prog):
        C = self.C
        tk.Label(self._me_inner, text=" MACRO — delay (ms)",
            font=("Courier", 8, "bold"), fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=8, pady=(0,4))
        row = tk.Frame(self._me_inner, bg=C["bg"]); row.pack(fill="x", padx=8, pady=1)
        tk.Label(row, text="delay_ms", font=("Courier", 8),
            fg=C["dim"], bg=C["bg"], width=12, anchor="w").pack(side="left")
        self._me_macro_delay = tk.StringVar(value=str(prog.get("delay_ms", 50)))
        tk.Entry(row, textvariable=self._me_macro_delay, font=("Courier", 8),
            bg=C["btn"], fg=C["text"], insertbackground=C["accent"],
            relief="flat", width=8).pack(side="left", padx=4)

    def _me_save(self):
        key  = self._me_prog_var.get()
        prog = self.config["programs"].get(key, {})
        # Pads
        pads = prog.setdefault("pads", {})
        for pad_key, var in self._me_pad_vars.items():
            pads.setdefault(pad_key, {})["action"] = var.get()
        # Knobs
        knobs = prog.setdefault("knobs", {})
        for cc_key, var in self._me_knob_vars.items():
            knobs.setdefault(cc_key, {})["axis"] = var.get()
        # Gamepad joystick
        if hasattr(self, "_me_js_pitch"):
            prog.setdefault("joystick", {})["pitch"]    = self._me_js_pitch.get()
            prog.setdefault("joystick", {})["modwheel"] = self._me_js_mod.get()
        # OBS
        if hasattr(self, "_me_obs_host"):
            prog["host"] = self._me_obs_host.get()
            try: prog["port"] = int(self._me_obs_port.get())
            except ValueError: pass
        # HTTP
        if hasattr(self, "_me_http_url"):
            prog["base_url"] = self._me_http_url.get()
        # Macro
        if hasattr(self, "_me_macro_delay"):
            try: prog["delay_ms"] = int(self._me_macro_delay.get())
            except ValueError: pass
        self._save_config()
        self._log(f"[EDITOR] Prog {key} sauvegardé.")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST PANEL
    # ─────────────────────────────────────────────────────────────────────────
    def _build_test_tab(self, parent):
        C = self.C
        tk.Label(parent, text="  ⚗ TEST — Vérification indépendante des features",
            font=("Courier", 8, "bold"), fg=C["accent2"], bg=C["bg"]
        ).pack(anchor="w", padx=12, pady=(10, 4))
        nb = ttk.Notebook(parent, style="H.TNotebook")
        nb.pack(fill="both", expand=True, padx=8, pady=4)
        t_midi = tk.Frame(nb, bg=C["bg"])
        nb.add(t_midi, text="  MIDI  ")
        self._build_test_midi(t_midi)
        t_http = tk.Frame(nb, bg=C["bg"])
        nb.add(t_http, text="  HTTP  ")
        self._build_test_http(t_http)
        t_ws = tk.Frame(nb, bg=C["bg"])
        nb.add(t_ws, text="  WS  ")
        self._build_test_ws(t_ws)
        t_br = tk.Frame(nb, bg=C["bg"])
        nb.add(t_br, text="  Bridges  ")
        self._build_test_bridges(t_br)
        t_oled = tk.Frame(nb, bg=C["bg"])
        nb.add(t_oled, text="  🖥 OLED  ")
        self._build_test_oled(t_oled)

    def _build_test_oled(self, parent):
        panel = OLEDPanel(parent, self)
        panel.pack(fill="both", expand=True)

    def _build_test_midi(self, parent):
        C = self.C
        row = tk.Frame(parent, bg=C["bg"])
        row.pack(fill="x", padx=10, pady=8)
        tk.Label(row, text="Device :", font=("Courier", 8), fg=C["dim"], bg=C["bg"]).pack(side="left")
        self._te_midi_dev = tk.StringVar(value=self.device_var.get())
        ttk.Combobox(row, textvariable=self._te_midi_dev,
            values=mido.get_input_names() or ["Aucun"], width=22,
            state="readonly", style="H.TCombobox").pack(side="left", padx=6)
        tk.Button(row, text="▶ Monitor", font=("Courier", 8, "bold"),
            bg=C["green"], fg=C["bg"], relief="flat", padx=8, pady=2,
            cursor="hand2", command=self._te_start_midi_monitor).pack(side="left", padx=4)
        tk.Button(row, text="■ Stop", font=("Courier", 8),
            bg=C["red"], fg="white", relief="flat", padx=6, pady=2,
            cursor="hand2", command=self._te_stop_midi_monitor).pack(side="left", padx=2)
        self._test_midi_log = scrolledtext.ScrolledText(parent,
            bg=C["console_bg"], fg=C["console_fg"],
            font=("Courier", 8), relief="flat", height=12,
            insertbackground=C["accent"])
        self._test_midi_log.pack(fill="both", expand=True, padx=10, pady=4)
        self._test_midi_log.config(state="disabled")
        self._te_midi_running = False

    def _te_start_midi_monitor(self): self._te_midi_running = True
    def _te_stop_midi_monitor(self):  self._te_midi_running = False

    def _test_append(self, msg):
        if not hasattr(self, "_test_midi_log"): return
        if not self._te_midi_running: return
        self._test_midi_log.config(state="normal")
        self._test_midi_log.insert("end", msg + "\n")
        self._test_midi_log.see("end")
        self._test_midi_log.config(state="disabled")

    def _build_test_http(self, parent):
        C = self.C
        row = tk.Frame(parent, bg=C["bg"]); row.pack(fill="x", padx=10, pady=8)
        tk.Label(row, text="URL :", font=("Courier", 8), fg=C["dim"], bg=C["bg"]).pack(side="left")
        self._te_http_url = tk.StringVar(value="http://localhost:8080/test")
        tk.Entry(row, textvariable=self._te_http_url, font=("Courier", 8),
            bg=C["btn"], fg=C["text"], insertbackground=C["accent"],
            relief="flat", width=28).pack(side="left", padx=6)
        self._te_http_method = tk.StringVar(value="GET")
        ttk.Combobox(row, textvariable=self._te_http_method,
            values=HTTP_METHODS, width=7, state="readonly",
            style="H.TCombobox").pack(side="left", padx=2)
        tk.Button(row, text="Send", font=("Courier", 8, "bold"),
            bg=C["green"], fg=C["bg"], relief="flat", padx=8, pady=2,
            cursor="hand2", command=self._te_send_http).pack(side="left", padx=4)
        self._te_http_log = scrolledtext.ScrolledText(parent,
            bg=C["console_bg"], fg=C["console_fg"],
            font=("Courier", 8), relief="flat", height=10,
            insertbackground=C["accent"])
        self._te_http_log.pack(fill="both", expand=True, padx=10, pady=4)
        self._te_http_log.config(state="disabled")

    def _te_send_http(self):
        import urllib.request
        url    = self._te_http_url.get()
        method = self._te_http_method.get()
        def _do():
            try:
                req = urllib.request.Request(url, method=method)
                with urllib.request.urlopen(req, timeout=5) as r:
                    body = r.read(200).decode("utf-8", errors="replace")
                self.root.after(0, self._te_http_append, f"[{r.status}] {body[:120]}")
            except Exception as e:
                self.root.after(0, self._te_http_append, f"[ERR] {e}")
        threading.Thread(target=_do, daemon=True).start()

    def _te_http_append(self, msg):
        self._te_http_log.config(state="normal")
        self._te_http_log.insert("end", msg + "\n")
        self._te_http_log.see("end")
        self._te_http_log.config(state="disabled")

    def _build_test_ws(self, parent):
        C = self.C
        row = tk.Frame(parent, bg=C["bg"]); row.pack(fill="x", padx=10, pady=8)
        tk.Label(row, text="URL :", font=("Courier", 8), fg=C["dim"], bg=C["bg"]).pack(side="left")
        self._te_ws_url = tk.StringVar(value="ws://localhost:8765")
        tk.Entry(row, textvariable=self._te_ws_url, font=("Courier", 8),
            bg=C["btn"], fg=C["text"], insertbackground=C["accent"],
            relief="flat", width=28).pack(side="left", padx=6)
        tk.Button(row, text="Ping", font=("Courier", 8, "bold"),
            bg=C["green"], fg=C["bg"], relief="flat", padx=8, pady=2,
            cursor="hand2", command=self._te_ws_ping).pack(side="left", padx=4)
        self._te_ws_log = scrolledtext.ScrolledText(parent,
            bg=C["console_bg"], fg=C["console_fg"],
            font=("Courier", 8), relief="flat", height=10,
            insertbackground=C["accent"])
        self._te_ws_log.pack(fill="both", expand=True, padx=10, pady=4)
        self._te_ws_log.config(state="disabled")

    def _te_ws_ping(self):
        try:
            import websockets, asyncio
            async def _ping():
                async with websockets.connect(self._te_ws_url.get(), open_timeout=3) as ws:
                    await ws.send('{"type":"ping"}')
                    resp = await asyncio.wait_for(ws.recv(), timeout=3)
                    self.root.after(0, self._te_ws_append, f"[PONG] {resp[:120]}")
            def _run():
                try: asyncio.run(_ping())
                except Exception as e:
                    self.root.after(0, self._te_ws_append, f"[ERR] {e}")
            threading.Thread(target=_run, daemon=True).start()
        except ImportError:
            self._te_ws_append("[ERR] pip install websockets")

    def _te_ws_append(self, msg):
        self._te_ws_log.config(state="normal")
        self._te_ws_log.insert("end", msg + "\n")
        self._te_ws_log.see("end")
        self._te_ws_log.config(state="disabled")

    def _build_test_bridges(self, parent):
        C = self.C
        tk.Label(parent,
            text="  Testez chaque bridge indépendamment depuis l'onglet TEST.",
            font=("Courier", 8), fg=C["dim"], bg=C["bg"]).pack(anchor="w", padx=12, pady=16)


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app  = HexPadGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
