#!/usr/bin/env python3
"""
HexPad GUI v2.3.0
  - Fenêtre unique redimensionnable
  - Mapping Editor en Toplevel dédié (bouton ⚙ dans le header)
  - Console rétractable (toggle ▾/▴)
  - Panneau TEST intégré (notebook) : MIDI monitor, HTTP, WebSocket, Bridges, OLED
  - Mode/taille de fenêtre sauvegardés silencieusement
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

try:
    from modules.music_bridge import MusicBridge
    MUSIC_OK = True
except ImportError:
    MUSIC_OK = False

VERSION = "2.3.0"

DEFAULT_W, DEFAULT_H = 520, 820
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
        self._learn_target = None
        self._pad_btns     = {}
        self._current_prog = "1"
        self._editor_win   = None
        self._console_visible = True
        self.config        = self._load_config()
        self.profiles      = GameProfiles()
        self.combo_engine  = ComboEngine()
        theme_name = self.config.get("theme", "dark")
        self.C = get_theme(theme_name)
        self._apply_window()
        self._build_ui()
        if self.config.get("programs"):
            self._select_program(self._current_prog)
        self._sync_profile()
        self._mon_stop = threading.Event()
        self._start_monitor()

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
        if self.listener: self.listener.stop()
        self.root.destroy()

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        self._style()
        self.root.configure(bg=self.C["bg"])
        self._build_header(self.root)
        self._build_device_row(self.root)
        self._sep(self.root)
        # Notebook : RUN / TEST
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
            cursor="hand2", command=self._open_editor).pack(side="right", padx=6)

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
        self.profile_var = tk.StringVar(value=self.profiles.active)
        self.profile_cb = ttk.Combobox(dp, textvariable=self.profile_var,
            values=self.profiles.names, width=12, state="readonly", style="H.TCombobox")
        self.profile_cb.pack(side="left", padx=2)
        self.profile_cb.bind("<<ComboboxSelected>>", self._on_profile_changed)

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
        music_status = "" if MUSIC_OK else "  ⚠ pip install pygame sounddevice"
        self._log(f"⬡ HexPad v{VERSION} ready  theme:{self.C['name']}{music_status}")

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
                                if self._learn_target:
                                    self.root.after(0, self._on_learn_received, msg.note)
                                # Feed test MIDI log if active
                                if hasattr(self, "_test_midi_log"):
                                    label = f"note_on  note={msg.note} ({note_name(msg.note)})  vel={msg.velocity}"
                                    self.root.after(0, self._test_append, label)
                            elif msg and msg.type == "control_change":
                                if hasattr(self, "_test_midi_log"):
                                    label = f"cc       cc={msg.control}  val={msg.value}"
                                    self.root.after(0, self._test_append, label)
                            time.sleep(0.001)
                except Exception: time.sleep(1)
        threading.Thread(target=run, daemon=True).start()

    def _on_learn_received(self, note):
        if not self._learn_target: return
        pad_key, btn = self._learn_target
        self._log(f"[LEARN] Note {note} ({note_name(note)}) → pad {pad_key}")
        btn.config(bg=self.C["panel2"], fg=self.C["dim"])
        self._learn_target = None
        if hasattr(self, "_me_pad_frame"): self._me_build_pad_grid()

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

        # ── Onglet MIDI
        t_midi = tk.Frame(nb, bg=C["bg"])
        nb.add(t_midi, text="  MIDI  ")
        self._build_test_midi(t_midi)

        # ── Onglet HTTP
        t_http = tk.Frame(nb, bg=C["bg"])
        nb.add(t_http, text="  HTTP  ")
        self._build_test_http(t_http)

        # ── Onglet WebSocket
        t_ws = tk.Frame(nb, bg=C["bg"])
        nb.add(t_ws, text="  WS  ")
        self._build_test_ws(t_ws)

        # ── Onglet Bridges
        t_br = tk.Frame(nb, bg=C["bg"])
        nb.add(t_br, text="  Bridges  ")
        self._build_test_bridges(t_br)

        # ── Onglet OLED
        t_oled = tk.Frame(nb, bg=C["bg"])
        nb.add(t_oled, text="  🖥 OLED  ")
        self._build_test_oled(t_oled)

    # ── TEST : OLED ───────────────────────────────────────────────────────────
    def _build_test_oled(self, parent):
        """Instancie OLEDPanel dans l'onglet OLED du panneau TEST."""
        panel = OLEDPanel(parent, self)
        panel.pack(fill="both", expand=True)

    # ── TEST : MIDI monitor ───────────────────────────────────────────────────
    def _build_test_midi(self, parent):
        C = self.C
        row = tk.Frame(parent, bg=C["bg"])
        row.pack(fill="x", padx=10, pady=8)
        tk.Label(row, text="Device :", font=("Courier", 8), fg=C["dim"], bg=C["bg"]).pack(side="left")
        self._test_midi_dev_var = tk.StringVar()
        devices = mido.get_input_names() or ["Aucun"]
        cb = ttk.Combobox(row, textvariable=self._test_midi_dev_var,
            values=devices, width=20, state="readonly", style="H.TCombobox")
        cb.pack(side="left", padx=6)
        if devices and devices[0] != "Aucun":
            self._test_midi_dev_var.set(devices[0])
        self._test_midi_active = False
        self._test_midi_btn = tk.Button(row, text="▶ Écouter",
            font=("Courier", 8, "bold"), bg=C["green"], fg=C["bg"],
            relief="flat", padx=8, cursor="hand2",
            command=self._test_midi_toggle)
        self._test_midi_btn.pack(side="left", padx=6)
        tk.Button(row, text="✕ Vider", font=("Courier", 8),
            bg=C["btn"], fg=C["dim"], relief="flat", padx=6, cursor="hand2",
            command=self._test_clear_midi).pack(side="left")
        self._test_midi_log = scrolledtext.ScrolledText(
            parent, bg=C["console_bg"], fg=C["console_fg"],
            font=("Courier", 8), relief="flat", height=10,
            insertbackground=C["accent"])
        self._test_midi_log.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self._test_midi_log.config(state="disabled")
        self._test_append("[MIDI TEST] Sélectionne un device et clique Écouter.")

    def _test_midi_toggle(self):
        C = self.C
        if not self._test_midi_active:
            self._test_midi_active = True
            self._test_midi_btn.config(text="■ Stop", bg=C["red"], fg="white")
            self._test_append(f"[MIDI] Écoute sur : {self._test_midi_dev_var.get()}")
        else:
            self._test_midi_active = False
            self._test_midi_btn.config(text="▶ Écouter", bg=C["green"], fg=C["bg"])
            self._test_append("[MIDI] Arrêt écoute.")

    def _test_clear_midi(self):
        self._test_midi_log.config(state="normal")
        self._test_midi_log.delete("1.0", "end")
        self._test_midi_log.config(state="disabled")

    def _test_append(self, msg):
        if not hasattr(self, "_test_midi_log"): return
        if not self._test_midi_active and not msg.startswith("[MIDI TEST]") and not msg.startswith("[MIDI] "): return
        self._test_midi_log.config(state="normal")
        ts = time.strftime("%H:%M:%S")
        self._test_midi_log.insert("end", f"{ts}  {msg}\n")
        self._test_midi_log.see("end")
        self._test_midi_log.config(state="disabled")

    # ── TEST : HTTP ───────────────────────────────────────────────────────────
    def _build_test_http(self, parent):
        C = self.C
        f = tk.Frame(parent, bg=C["bg"])
        f.pack(fill="x", padx=10, pady=8)
        tk.Label(f, text="Méthode", font=("Courier", 8), fg=C["dim"], bg=C["bg"]).grid(row=0, column=0, sticky="w")
        self._test_http_method = tk.StringVar(value="GET")
        ttk.Combobox(f, textvariable=self._test_http_method,
            values=HTTP_METHODS, width=7, state="readonly",
            style="H.TCombobox").grid(row=0, column=1, padx=4, sticky="w")
        tk.Label(f, text="URL", font=("Courier", 8), fg=C["dim"], bg=C["bg"]).grid(row=0, column=2, sticky="w", padx=(8,0))
        self._test_http_url = tk.StringVar(value="http://localhost:8080/test")
        tk.Entry(f, textvariable=self._test_http_url,
            bg=C["btn"], fg=C["accent"], font=("Courier", 9),
            relief="flat", width=28,
            insertbackground=C["accent"]).grid(row=0, column=3, padx=4, sticky="ew")
        f.columnconfigure(3, weight=1)
        f2 = tk.Frame(parent, bg=C["bg"])
        f2.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(f2, text="Body JSON", font=("Courier", 8), fg=C["dim"], bg=C["bg"]).pack(side="left")
        self._test_http_body = tk.StringVar(value="")
        tk.Entry(f2, textvariable=self._test_http_body,
            bg=C["btn"], fg=C["accent2"], font=("Courier", 9),
            relief="flat", insertbackground=C["accent"]).pack(side="left", fill="x", expand=True, padx=6)
        tk.Button(f2, text="▶ Envoyer",
            font=("Courier", 8, "bold"), bg=C["green"], fg=C["bg"],
            relief="flat", padx=8, cursor="hand2",
            command=self._test_http_send).pack(side="left")
        self._test_http_log = scrolledtext.ScrolledText(
            parent, bg=C["console_bg"], fg=C["console_fg"],
            font=("Courier", 8), relief="flat", height=8,
            insertbackground=C["accent"])
        self._test_http_log.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self._test_http_log.config(state="disabled")

    def _test_http_send(self):
        import urllib.request, urllib.error
        method = self._test_http_method.get()
        url    = self._test_http_url.get().strip()
        body   = self._test_http_body.get().strip()
        if not url:
            self._test_http_append("[ERR] URL vide."); return
        def do():
            try:
                data = body.encode() if body else None
                req  = urllib.request.Request(url, data=data, method=method)
                if data: req.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(req, timeout=5) as r:
                    resp = r.read().decode(errors="replace")[:500]
                    self.root.after(0, self._test_http_append,
                        f"[{r.status}] {resp}")
            except urllib.error.HTTPError as e:
                self.root.after(0, self._test_http_append, f"[HTTP {e.code}] {e.reason}")
            except Exception as e:
                self.root.after(0, self._test_http_append, f"[ERR] {e}")
        self._test_http_append(f"→ {method} {url}")
        threading.Thread(target=do, daemon=True).start()

    def _test_http_append(self, msg):
        self._test_http_log.config(state="normal")
        ts = time.strftime("%H:%M:%S")
        self._test_http_log.insert("end", f"{ts}  {msg}\n")
        self._test_http_log.see("end")
        self._test_http_log.config(state="disabled")

    # ── TEST : WebSocket ──────────────────────────────────────────────────────
    def _build_test_ws(self, parent):
        C = self.C
        row = tk.Frame(parent, bg=C["bg"])
        row.pack(fill="x", padx=10, pady=8)
        tk.Label(row, text="URL WS :", font=("Courier", 8), fg=C["dim"], bg=C["bg"]).pack(side="left")
        self._test_ws_url = tk.StringVar(value="ws://localhost:8765")
        tk.Entry(row, textvariable=self._test_ws_url,
            bg=C["btn"], fg=C["accent"], font=("Courier", 9),
            relief="flat", width=24,
            insertbackground=C["accent"]).pack(side="left", padx=6)
        self._test_ws_conn_btn = tk.Button(row, text="⚡ Connecter",
            font=("Courier", 8, "bold"), bg=C["green"], fg=C["bg"],
            relief="flat", padx=8, cursor="hand2",
            command=self._test_ws_connect)
        self._test_ws_conn_btn.pack(side="left")
        self._test_ws_dot = tk.Label(row, text="●", font=("Courier", 10),
            fg=C["red"], bg=C["bg"])
        self._test_ws_dot.pack(side="left", padx=4)
        send_row = tk.Frame(parent, bg=C["bg"])
        send_row.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(send_row, text="Message :", font=("Courier", 8), fg=C["dim"], bg=C["bg"]).pack(side="left")
        self._test_ws_msg = tk.StringVar(value='{"action": "ping"}')
        tk.Entry(send_row, textvariable=self._test_ws_msg,
            bg=C["btn"], fg=C["accent"], font=("Courier", 9),
            relief="flat", insertbackground=C["accent"]).pack(side="left", fill="x", expand=True, padx=6)
        tk.Button(send_row, text="▶ Envoyer",
            font=("Courier", 8, "bold"), bg=C["accent2"], fg=C["bg"],
            relief="flat", padx=8, cursor="hand2",
            command=self._test_ws_send).pack(side="left")
        self._test_ws_log = scrolledtext.ScrolledText(
            parent, bg=C["console_bg"], fg=C["console_fg"],
            font=("Courier", 8), relief="flat", height=8,
            insertbackground=C["accent"])
        self._test_ws_log.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self._test_ws_log.config(state="disabled")
        self._test_ws_sock = None

    def _test_ws_connect(self):
        C = self.C
        if self._test_ws_sock:
            try: self._test_ws_sock.close()
            except: pass
            self._test_ws_sock = None
            self._test_ws_conn_btn.config(text="⚡ Connecter", bg=C["green"], fg=C["bg"])
            self._test_ws_dot.config(fg=C["red"])
            self._test_ws_append("[WS] Déconnecté.")
            return
        url = self._test_ws_url.get().strip()
        def do():
            try:
                import websocket
                ws = websocket.WebSocket()
                ws.connect(url, timeout=5)
                self._test_ws_sock = ws
                self.root.after(0, self._test_ws_dot.config, {"fg": C["green"]})
                self.root.after(0, self._test_ws_conn_btn.config,
                    {"text": "✕ Déconnecter", "bg": C["red"], "fg": "white"})
                self.root.after(0, self._test_ws_append, f"[WS] Connecté à {url}")
            except Exception as e:
                self.root.after(0, self._test_ws_append, f"[ERR] {e}")
        threading.Thread(target=do, daemon=True).start()

    def _test_ws_send(self):
        if not self._test_ws_sock:
            self._test_ws_append("[ERR] Non connecté."); return
        msg = self._test_ws_msg.get()
        def do():
            try:
                self._test_ws_sock.send(msg)
                resp = self._test_ws_sock.recv()
                self.root.after(0, self._test_ws_append, f"→ {msg}")
                self.root.after(0, self._test_ws_append, f"← {resp}")
            except Exception as e:
                self.root.after(0, self._test_ws_append, f"[ERR] {e}")
        threading.Thread(target=do, daemon=True).start()

    def _test_ws_append(self, msg):
        self._test_ws_log.config(state="normal")
        ts = time.strftime("%H:%M:%S")
        self._test_ws_log.insert("end", f"{ts}  {msg}\n")
        self._test_ws_log.see("end")
        self._test_ws_log.config(state="disabled")

    # ── TEST : Bridges ────────────────────────────────────────────────────────
    def _build_test_bridges(self, parent):
        C = self.C
        tk.Label(parent,
            text="  Teste chaque bridge sans démarrer le listener MIDI.",
            font=("Courier", 7), fg=C["dim"], bg=C["bg"]
        ).pack(anchor="w", padx=12, pady=(8, 4))

        # Sélecteur de preset à tester
        row = tk.Frame(parent, bg=C["bg"])
        row.pack(fill="x", padx=10, pady=4)
        tk.Label(row, text="Preset :", font=("Courier", 8), fg=C["dim"], bg=C["bg"]).pack(side="left")
        self._test_br_prog_var = tk.StringVar(value=self._current_prog)
        prog_keys   = list(self.config.get("programs", {}).keys())
        prog_labels = [f"{k} — {self.config['programs'][k].get('name','')}" for k in prog_keys]
        self._test_br_prog_map = dict(zip(prog_labels, prog_keys))
        cb = ttk.Combobox(row, textvariable=self._test_br_prog_var,
            values=prog_labels, width=26, state="readonly", style="H.TCombobox")
        cb.pack(side="left", padx=6)
        for label, key in self._test_br_prog_map.items():
            if key == self._current_prog:
                self._test_br_prog_var.set(label); break

        # Grille de pads cliquables
        tk.Label(parent, text="  Cliquer un pad = simuler note_on",
            font=("Courier", 7, "bold"), fg=C["accent2"], bg=C["bg"]
        ).pack(anchor="w", padx=12, pady=(6, 2))
        self._test_pad_frame = tk.Frame(parent, bg=C["bg"])
        self._test_pad_frame.pack(padx=12, pady=4)
        self._build_test_pad_grid()
        cb.bind("<<ComboboxSelected>>", lambda e: self._build_test_pad_grid())

        self._test_br_log = scrolledtext.ScrolledText(
            parent, bg=C["console_bg"], fg=C["console_fg"],
            font=("Courier", 8), relief="flat", height=6,
            insertbackground=C["accent"])
        self._test_br_log.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self._test_br_log.config(state="disabled")
        self._test_br_append("[BRIDGE TEST] Clique un pad pour simuler un event MIDI.")

    def _build_test_pad_grid(self):
        C = self.C
        for w in self._test_pad_frame.winfo_children(): w.destroy()
        label = self._test_br_prog_var.get()
        key   = self._test_br_prog_map.get(label, self._current_prog)
        prog  = self.config["programs"].get(key, {})
        pads  = prog.get("pads", {})
        notes = PAD_BANK_A
        layout = [notes[4:8], notes[0:4]]
        for row_idx, row_notes in enumerate(layout):
            for col_idx, note in enumerate(row_notes):
                ns      = str(note)
                pad_num = notes.index(note) + 1
                action  = pads.get(ns, "—")
                short   = (action if isinstance(action, str) else action.get("action", "?") if isinstance(action, dict) else "?")[:8]
                btn = tk.Button(
                    self._test_pad_frame,
                    text=f"P{pad_num}\n{short}",
                    font=("Courier", 8, "bold"),
                    bg=C["pad_off"], fg=C["accent"],
                    activebackground=C["accent"], activeforeground=C["bg"],
                    relief="flat", width=7, pady=8, cursor="hand2",
                    command=lambda n=note, p=prog, k=key: self._test_simulate_pad(n, p, k)
                )
                btn.grid(row=row_idx, column=col_idx, padx=3, pady=3)

    def _test_simulate_pad(self, note, prog, key):
        self._test_br_append(f"[SIM] note_on note={note} ({note_name(note)}) — preset {key}")
        def do():
            try:
                bridge, mode = self._build_bridge(prog)
                if bridge is None:
                    self.root.after(0, self._test_br_append, f"[DEBUG] mode={mode}, no bridge")
                    return
                d = Dispatcher()
                d.set_bridge(bridge, mode)
                import mido as _mido
                msg = _mido.Message("note_on", note=note, velocity=100)
                d.dispatch(msg)
                self.root.after(0, self._test_br_append, f"[OK] dispatché → {mode}")
            except Exception as e:
                self.root.after(0, self._test_br_append, f"[ERR] {e}")
        threading.Thread(target=do, daemon=True).start()

    def _test_br_append(self, msg):
        self._test_br_log.config(state="normal")
        ts = time.strftime("%H:%M:%S")
        self._test_br_log.insert("end", f"{ts}  {msg}\n")
        self._test_br_log.see("end")
        self._test_br_log.config(state="disabled")

    # ─────────────────────────────────────────────────────────────────────────
    # MAPPING EDITOR — fenêtre Toplevel dédiée
    # ─────────────────────────────────────────────────────────────────────────
    def _open_editor(self):
        if self._editor_win and self._editor_win.winfo_exists():
            self._editor_win.lift(); return
        win = tk.Toplevel(self.root)
        win.title("HexPad — Mapping Editor")
        win.configure(bg=self.C["bg"])
        win.geometry("600x800")
        win.resizable(True, True)
        win.minsize(500, 600)
        self._editor_win = win
        self._build_mapping_editor(win)

    def _build_mapping_editor(self, parent):
        C = self.C
        hdr = tk.Frame(parent, bg=C["panel2"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="◈ MAPPING EDITOR", font=("Courier", 10, "bold"),
            fg=C["accent"], bg=C["panel2"]).pack(side="left", padx=12, pady=8)
        self._me_save_indicator = tk.Label(hdr, text="", font=("Courier", 8),
            fg=C["green"], bg=C["panel2"])
        self._me_save_indicator.pack(side="right", padx=12)
        tk.Button(hdr, text="↑ Export", font=("Courier", 8), bg=C["btn"], fg=C["accent2"],
            relief="flat", padx=6, pady=4, cursor="hand2",
            command=self._me_export_preset).pack(side="right", padx=2)
        tk.Button(hdr, text="↓ Import", font=("Courier", 8), bg=C["btn"], fg=C["accent2"],
            relief="flat", padx=6, pady=4, cursor="hand2",
            command=self._me_import_preset).pack(side="right", padx=2)

        canvas = tk.Canvas(parent, bg=C["bg"], bd=0, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(canvas, bg=C["bg"])
        body_win = canvas.create_window((0, 0), window=body, anchor="nw")

        def _on_configure(e): canvas.configure(scrollregion=canvas.bbox("all"))
        def _on_canvas_resize(e): canvas.itemconfig(body_win, width=e.width)
        body.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_canvas_resize)
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        prow = tk.Frame(body, bg=C["bg"])
        prow.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(prow, text="Preset :", font=("Courier", 9, "bold"),
            fg=C["dim"], bg=C["bg"]).pack(side="left")
        self._me_prog_var = tk.StringVar(value=self._current_prog)
        prog_keys   = list(self.config.get("programs", {}).keys())
        prog_labels = [f"{k} — {self.config['programs'][k].get('name','')}" for k in prog_keys]
        self._me_prog_map = dict(zip(prog_labels, prog_keys))
        self._me_prog_cb = ttk.Combobox(prow, textvariable=self._me_prog_var,
            values=prog_labels, width=28, state="readonly", style="H.TCombobox")
        self._me_prog_cb.pack(side="left", padx=8)
        for label, key in self._me_prog_map.items():
            if key == self._current_prog:
                self._me_prog_var.set(label); break
        self._me_prog_cb.bind("<<ComboboxSelected>>", self._me_on_prog_changed)
        tk.Button(prow, text="+ Nouveau", font=("Courier", 8), bg=C["btn"], fg=C["accent2"],
            relief="flat", padx=6, pady=4, cursor="hand2",
            command=self._me_new_preset).pack(side="left", padx=4)
        tk.Button(prow, text="✕ Suppr", font=("Courier", 8), bg=C["btn"], fg=C["red"],
            relief="flat", padx=6, pady=4, cursor="hand2",
            command=self._me_delete_preset).pack(side="left")

        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", padx=12, pady=6)

        meta = tk.Frame(body, bg=C["bg"])
        meta.pack(fill="x", padx=12)
        tk.Label(meta, text="Nom", font=("Courier", 8),
            fg=C["dim"], bg=C["bg"]).grid(row=0, column=0, sticky="w", pady=3)
        self._me_name_var = tk.StringVar()
        tk.Entry(meta, textvariable=self._me_name_var,
            bg=C["btn"], fg=C["accent"], font=("Courier", 9),
            relief="flat", width=20,
            insertbackground=C["accent"]).grid(row=0, column=1, padx=8, sticky="w")
        tk.Label(meta, text="Mode", font=("Courier", 8),
            fg=C["dim"], bg=C["bg"]).grid(row=0, column=2, sticky="w", padx=(12, 0))
        self._me_mode_var = tk.StringVar(value="gamepad")
        mode_cb = ttk.Combobox(meta, textvariable=self._me_mode_var,
            values=list(MODE_COLORS.keys()), width=14,
            state="readonly", style="H.TCombobox")
        mode_cb.grid(row=0, column=3, padx=8, sticky="w")
        mode_cb.bind("<<ComboboxSelected>>", lambda e: self._me_refresh_mode_fields())

        self._me_conn_frame = tk.Frame(body, bg=C["bg"])
        self._me_conn_frame.pack(fill="x", padx=12, pady=4)
        self._me_ws_url_var       = tk.StringVar(value="ws://localhost:8765")
        self._me_obs_host_var     = tk.StringVar(value="localhost")
        self._me_obs_port_var     = tk.StringVar(value="4455")
        self._me_obs_pass_var     = tk.StringVar(value="")
        self._me_pitch_var        = tk.StringVar(value="")
        self._me_mod_var          = tk.StringVar(value="")
        self._me_sounds_dir_var   = tk.StringVar(value="sounds")
        self._me_http_timeout_var = tk.StringVar(value="3")
        self._me_music_vol_var    = tk.StringVar(value="1.0")
        self._me_music_dev_var    = tk.StringVar(value="")

        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", padx=12, pady=6)

        bank_row = tk.Frame(body, bg=C["bg"])
        bank_row.pack(fill="x", padx=12)
        tk.Label(bank_row, text="BANK", font=("Courier", 9, "bold"),
            fg=C["accent2"], bg=C["bg"]).pack(side="left")
        self._me_bank_var = tk.StringVar(value="A")
        for bank in ("A", "B"):
            tk.Radiobutton(bank_row, text=f"  {bank}  ",
                variable=self._me_bank_var, value=bank,
                font=("Courier", 9, "bold"),
                bg=C["bg"], fg=C["accent"],
                selectcolor=C["btn"], activebackground=C["bg"],
                command=self._me_build_pad_grid).pack(side="left", padx=4)
        self._me_show_note_var = tk.BooleanVar(value=True)
        tk.Checkbutton(bank_row, text="noms de notes",
            variable=self._me_show_note_var,
            font=("Courier", 7), bg=C["bg"], fg=C["dim"],
            selectcolor=C["btn"], activebackground=C["bg"],
            command=self._me_build_pad_grid).pack(side="right", padx=8)

        tk.Label(body, text="  PADS — layout physique MPK",
            font=("Courier", 8, "bold"), fg=C["accent2"], bg=C["bg"]
        ).pack(anchor="w", padx=12, pady=(8, 2))
        self._me_pad_frame = tk.Frame(body, bg=C["bg"])
        self._me_pad_frame.pack(fill="x", padx=12, pady=4)
        self._me_pad_vars     = {}
        self._me_pad_sub_vars = {}

        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", padx=12, pady=6)

        tk.Label(body, text="  ENCODEURS (CC)", font=("Courier", 8, "bold"),
            fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=12)
        self._me_knob_frame = tk.Frame(body, bg=C["bg"])
        self._me_knob_frame.pack(fill="x", padx=12, pady=4)
        self._me_knob_vars = {}

        pm_row = tk.Frame(body, bg=C["bg"])
        pm_row.pack(fill="x", padx=12, pady=4)
        for label, var in (("Pitchwheel →", self._me_pitch_var), ("Modwheel →", self._me_mod_var)):
            tk.Label(pm_row, text=label, font=("Courier", 8),
                fg=C["dim"], bg=C["bg"]).pack(side="left")
            ttk.Combobox(pm_row, textvariable=var,
                values=[""] + AXIS_OPTIONS, width=10,
                state="normal", style="H.TCombobox").pack(side="left", padx=(4, 16))

        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", padx=12, pady=8)

        btns = tk.Frame(body, bg=C["bg"])
        btns.pack(fill="x", padx=12, pady=(0, 16))
        tk.Button(btns, text="💾  SAUVEGARDER", font=("Courier", 10, "bold"),
            bg=C["accent"], fg=C["bg"], relief="flat", padx=16, pady=10,
            cursor="hand2", command=self._me_save).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="↺  Recharger", font=("Courier", 9),
            bg=C["btn"], fg=C["dim"], relief="flat", padx=10, pady=10,
            cursor="hand2", command=self._me_load_preset).pack(side="left")

        self._me_loaded = True
        self._me_load_preset()

    def _me_export_preset(self):
        prog = self._get_current_preset()
        if not prog:
            messagebox.showwarning("Export", "Aucun preset sélectionné."); return
        path = filedialog.asksaveasfilename(
            title="Exporter le preset",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Tous", "*.*")],
            initialfile=f"hexpad_preset_{self._current_prog}.json"
        )
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(prog, f, indent=2, ensure_ascii=False)
            self._log(f"[EXPORT] {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Export", str(e))

    def _me_import_preset(self):
        path = filedialog.askopenfilename(
            title="Importer un preset",
            filetypes=[("JSON", "*.json"), ("Tous", "*.*")])
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "mode" not in data:
                messagebox.showerror("Import", "Fichier invalide : clé 'mode' manquante."); return
            choice = messagebox.askyesnocancel(
                "Import",
                f"Importer dans le preset {self._current_prog} (Oui)\n"
                f"ou créer un nouveau slot (Non) ?")
            if choice is None: return
            key = self._current_prog if choice else str(
                max(int(k) for k in self.config["programs"].keys()) + 1)
            self.config["programs"][key] = data
            self._save_config()
            self._current_prog = key
            self._build_prog_btns(); self._select_program(key)
            prog_keys   = list(self.config["programs"].keys())
            prog_labels = [f"{k} — {self.config['programs'][k].get('name','')}" for k in prog_keys]
            self._me_prog_map = dict(zip(prog_labels, prog_keys))
            self._me_prog_cb.config(values=prog_labels)
            for label, k in self._me_prog_map.items():
                if k == key:
                    self._me_prog_var.set(label); break
            self._me_load_preset()
            self._log(f"[IMPORT] preset {key} chargé")
        except Exception as e:
            messagebox.showerror("Import", str(e))

    def _me_on_prog_changed(self, event=None):
        label = self._me_prog_var.get()
        key   = self._me_prog_map.get(label, self._current_prog)
        self._current_prog = key
        self._select_program(key)
        self._me_load_preset()

    def _me_new_preset(self):
        new_key = str(max(int(k) for k in self.config["programs"].keys()) + 1)
        self.config["programs"][new_key] = {
            "name": f"Preset {new_key}", "mode": "gamepad", "pads": {}, "knobs": {}}
        self._save_config()
        self._build_prog_btns()
        prog_keys   = list(self.config["programs"].keys())
        prog_labels = [f"{k} — {self.config['programs'][k].get('name','')}" for k in prog_keys]
        self._me_prog_map = dict(zip(prog_labels, prog_keys))
        self._me_prog_cb.config(values=prog_labels)
        self._current_prog = new_key
        for label, k in self._me_prog_map.items():
            if k == new_key: self._me_prog_var.set(label); break
        self._me_load_preset()
        self._log(f"[ME] Nouveau preset {new_key}")

    def _me_delete_preset(self):
        if len(self.config["programs"]) <= 1:
            messagebox.showwarning("Suppr", "Impossible de supprimer le dernier preset."); return
        key = self._current_prog
        if not messagebox.askyesno("Supprimer", f"Supprimer le preset {key} ?"):
            return
        del self.config["programs"][key]
        self._save_config()
        self._current_prog = list(self.config["programs"].keys())[0]
        self._build_prog_btns(); self._select_program(self._current_prog)
        prog_keys   = list(self.config["programs"].keys())
        prog_labels = [f"{k} — {self.config['programs'][k].get('name','')}" for k in prog_keys]
        self._me_prog_map = dict(zip(prog_labels, prog_keys))
        self._me_prog_cb.config(values=prog_labels)
        for label, k in self._me_prog_map.items():
            if k == self._current_prog: self._me_prog_var.set(label); break
        self._me_load_preset()
        self._log(f"[ME] Preset {key} supprimé")

    def _me_refresh_mode_fields(self):
        C = self.C
        for w in self._me_conn_frame.winfo_children(): w.destroy()
        mode = self._me_mode_var.get()
        def row(label, var, width=22):
            f = tk.Frame(self._me_conn_frame, bg=C["bg"])
            f.pack(fill="x", pady=2)
            tk.Label(f, text=label, font=("Courier", 8), fg=C["dim"],
                bg=C["bg"], width=14, anchor="w").pack(side="left")
            tk.Entry(f, textvariable=var, bg=C["btn"], fg=C["accent"],
                font=("Courier", 9), relief="flat", width=width,
                insertbackground=C["accent"]).pack(side="left", padx=4)
        if mode == "websocket":  row("WS URL", self._me_ws_url_var)
        elif mode == "obs":
            row("OBS Host",     self._me_obs_host_var, 16)
            row("OBS Port",     self._me_obs_port_var, 6)
            row("OBS Password", self._me_obs_pass_var, 16)
        elif mode == "sound_preset": row("sounds dir", self._me_sounds_dir_var, 18)
        elif mode == "http":    row("Timeout (s)", self._me_http_timeout_var, 6)
        elif mode == "music":
            row("Volume (0-1)", self._me_music_vol_var, 6)
            row("Audio device", self._me_music_dev_var, 20)

    def _me_build_pad_grid(self):
        C = self.C
        for w in self._me_pad_frame.winfo_children(): w.destroy()
        self._me_pad_vars     = {}
        self._me_pad_sub_vars = {}
        bank   = self._me_bank_var.get()
        notes  = PAD_BANK_A if bank == "A" else PAD_BANK_B
        layout = [notes[4:8], notes[0:4]]
        prog   = self._get_current_preset() or {}
        pads   = prog.get("pads", {})
        mode   = prog.get("mode", "debug")

        for row_idx, row_notes in enumerate(layout):
            for col_idx, note in enumerate(row_notes):
                ns      = str(note)
                pad_num = notes.index(note) + 1
                note_lbl = note_name(note) if self._me_show_note_var.get() else ""
                raw     = pads.get(ns, {})
                cell = tk.Frame(self._me_pad_frame, bg=C["panel2"], padx=4, pady=4)
                cell.grid(row=row_idx, column=col_idx, padx=3, pady=3, sticky="nsew")
                self._me_pad_frame.columnconfigure(col_idx, weight=1)

                lbl_row = tk.Frame(cell, bg=C["panel2"])
                lbl_row.pack(fill="x")
                tk.Label(lbl_row, text=f"P{pad_num}",
                    font=("Courier", 8, "bold"), fg=C["accent"], bg=C["panel2"]).pack(side="left")
                if note_lbl:
                    tk.Label(lbl_row, text=f" {note_lbl}",
                        font=("Courier", 7), fg=C["dim"], bg=C["panel2"]).pack(side="left")

                # Bouton LEARN
                learn_btn = tk.Button(lbl_row, text="L",
                    font=("Courier", 6, "bold"),
                    bg=C["btn"], fg=C["accent2"],
                    relief="flat", padx=3, pady=1,
                    cursor="hand2")
                learn_btn.pack(side="right", padx=2)
                learn_btn.config(command=lambda nb=learn_btn, nk=ns: self._me_start_learn(nk, nb))

                if mode in ("gamepad",):
                    var = tk.StringVar(value=raw if isinstance(raw, str) else raw.get("action", ""))
                    self._me_pad_vars[ns] = var
                    cb = ttk.Combobox(cell, textvariable=var,
                        values=[""] + BTN_OPTIONS + AXIS_OPTIONS,
                        width=10, style="H.TCombobox")
                    cb.pack(fill="x", pady=2)
                elif mode == "macro":
                    var = tk.StringVar(value=raw if isinstance(raw, str) else raw.get("action", ""))
                    self._me_pad_vars[ns] = var
                    cb = ttk.Combobox(cell, textvariable=var,
                        values=[""] + MACRO_OPTIONS,
                        width=10, style="H.TCombobox")
                    cb.pack(fill="x", pady=2)
                elif mode == "obs":
                    act_var = tk.StringVar(value=raw.get("action", "") if isinstance(raw, dict) else "")
                    sub_var = tk.StringVar(value=raw.get("scene", raw.get("source", raw.get("name", ""))) if isinstance(raw, dict) else "")
                    self._me_pad_vars[ns]     = act_var
                    self._me_pad_sub_vars[ns] = sub_var
                    ttk.Combobox(cell, textvariable=act_var,
                        values=[""] + OBS_ACTIONS,
                        width=10, style="H.TCombobox").pack(fill="x", pady=2)
                    tk.Entry(cell, textvariable=sub_var,
                        bg=C["btn"], fg=C["accent2"], font=("Courier", 8),
                        relief="flat", insertbackground=C["accent"]).pack(fill="x", pady=1)
                elif mode == "http":
                    meth_var = tk.StringVar(value=raw.get("method", "GET") if isinstance(raw, dict) else "GET")
                    url_var  = tk.StringVar(value=raw.get("url", "")  if isinstance(raw, dict) else "")
                    self._me_pad_vars[ns]     = meth_var
                    self._me_pad_sub_vars[ns] = url_var
                    ttk.Combobox(cell, textvariable=meth_var,
                        values=HTTP_METHODS, width=7, style="H.TCombobox").pack(fill="x", pady=2)
                    tk.Entry(cell, textvariable=url_var,
                        bg=C["btn"], fg=C["accent2"], font=("Courier", 8),
                        relief="flat", insertbackground=C["accent"]).pack(fill="x", pady=1)
                elif mode in ("websocket", "sound_preset", "music", "debug"):
                    var = tk.StringVar(value=raw if isinstance(raw, str) else raw.get("action", "") if isinstance(raw, dict) else "")
                    self._me_pad_vars[ns] = var
                    tk.Entry(cell, textvariable=var,
                        bg=C["btn"], fg=C["accent"], font=("Courier", 8),
                        relief="flat", insertbackground=C["accent"]).pack(fill="x", pady=2)
                else:
                    var = tk.StringVar(value=raw if isinstance(raw, str) else "")
                    self._me_pad_vars[ns] = var
                    tk.Entry(cell, textvariable=var,
                        bg=C["btn"], fg=C["accent"], font=("Courier", 8),
                        relief="flat", insertbackground=C["accent"]).pack(fill="x", pady=2)

    def _me_start_learn(self, pad_key, btn):
        btn.config(bg=self.C["accent"], fg=self.C["bg"])
        self._learn_target = (pad_key, btn)
        self._log(f"[LEARN] En attente note pour pad {pad_key}…")

    def _me_build_knob_grid(self):
        C = self.C
        for w in self._me_knob_frame.winfo_children(): w.destroy()
        self._me_knob_vars = {}
        prog  = self._get_current_preset() or {}
        knobs = prog.get("knobs", {})
        mode  = prog.get("mode", "debug")
        for i, cc in enumerate(KNOB_CC):
            cs  = str(cc)
            raw = knobs.get(cs, {})
            cell = tk.Frame(self._me_knob_frame, bg=C["panel2"], padx=4, pady=4)
            cell.grid(row=i // 4, column=i % 4, padx=3, pady=3, sticky="nsew")
            self._me_knob_frame.columnconfigure(i % 4, weight=1)
            tk.Label(cell, text=f"K{i+1}  CC{cc}",
                font=("Courier", 7, "bold"), fg=C["accent"], bg=C["panel2"]).pack(anchor="w")
            if mode == "gamepad":
                var = tk.StringVar(value=raw if isinstance(raw, str) else raw.get("action", ""))
                self._me_knob_vars[cs] = (var,)
                ttk.Combobox(cell, textvariable=var,
                    values=[""] + AXIS_OPTIONS,
                    width=9, style="H.TCombobox").pack(fill="x", pady=2)
            else:
                var = tk.StringVar(value=raw if isinstance(raw, str) else raw.get("action", "") if isinstance(raw, dict) else "")
                self._me_knob_vars[cs] = (var,)
                tk.Entry(cell, textvariable=var,
                    bg=C["btn"], fg=C["accent"], font=("Courier", 8),
                    relief="flat", insertbackground=C["accent"]).pack(fill="x", pady=2)

    def _me_load_preset(self):
        prog = self._get_current_preset()
        if not prog: return
        self._me_name_var.set(prog.get("name", ""))
        self._me_mode_var.set(prog.get("mode", "gamepad"))
        self._me_ws_url_var.set(prog.get("ws_url", "ws://localhost:8765"))
        self._me_obs_host_var.set(prog.get("obs_host", "localhost"))
        self._me_obs_port_var.set(str(prog.get("obs_port", 4455)))
        self._me_obs_pass_var.set(prog.get("obs_password", ""))
        self._me_pitch_var.set(prog.get("pitchwheel", ""))
        self._me_mod_var.set(prog.get("modwheel", ""))
        self._me_sounds_dir_var.set(prog.get("sounds_dir", "sounds"))
        self._me_http_timeout_var.set(str(prog.get("timeout", 3)))
        self._me_music_vol_var.set(str(prog.get("volume", 1.0)))
        self._me_music_dev_var.set(prog.get("audio_device", ""))
        self._me_refresh_mode_fields()
        self._me_build_pad_grid()
        self._me_build_knob_grid()

    def _me_save(self):
        key  = self._current_prog
        prog = self.config["programs"].get(key, {})
        prog["name"] = self._me_name_var.get().strip() or f"Preset {key}"
        prog["mode"] = self._me_mode_var.get()
        mode = prog["mode"]
        if mode == "websocket":  prog["ws_url"]       = self._me_ws_url_var.get()
        elif mode == "obs":
            prog["obs_host"]     = self._me_obs_host_var.get()
            prog["obs_port"]     = int(self._me_obs_port_var.get() or 4455)
            prog["obs_password"] = self._me_obs_pass_var.get()
        elif mode == "sound_preset": prog["sounds_dir"] = self._me_sounds_dir_var.get()
        elif mode == "http":    prog["timeout"] = int(self._me_http_timeout_var.get() or 3)
        elif mode == "music":
            try: prog["volume"] = float(self._me_music_vol_var.get())
            except ValueError: pass
            prog["audio_device"] = self._me_music_dev_var.get()
        prog["pitchwheel"] = self._me_pitch_var.get()
        prog["modwheel"]   = self._me_mod_var.get()

        # Pads
        pads = {}
        for ns, var in self._me_pad_vars.items():
            val = var.get().strip()
            if not val: continue
            if ns in self._me_pad_sub_vars:
                sub = self._me_pad_sub_vars[ns].get().strip()
                if mode == "obs":
                    entry = {"action": val}
                    if val in OBS_NEEDS_SCENE:  entry["scene"]  = sub
                    if val in OBS_NEEDS_SOURCE: entry["source"] = sub
                    pads[ns] = entry
                elif mode == "http":
                    pads[ns] = {"method": val, "url": sub}
                else:
                    pads[ns] = val
            else:
                pads[ns] = val
        prog["pads"] = pads

        # Knobs
        knobs = {}
        for cs, var_tuple in self._me_knob_vars.items():
            val = var_tuple[0].get().strip() if var_tuple else ""
            if val: knobs[cs] = val
        prog["knobs"] = knobs

        self.config["programs"][key] = prog
        self._save_config()
        self._build_prog_btns()
        self._select_program(key)
        self._me_save_indicator.config(text="✓ sauvegardé")
        self.after_idle = self.root.after(2000, lambda: self._me_save_indicator.config(text=""))
        self._log(f"[ME] Preset {key} sauvegardé")


# ─────────────────────────────────────────────────────────────────────────────
def main():
    root = tk.Tk()
    app  = HexPadGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
