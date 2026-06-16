#!/usr/bin/env python3
"""
HexPad — Mapping Editor (extrait de gui.py)
Toute la logique _me_* vit ici pour alléger gui.py.

Usage :
    from gui.mapping_editor import build_mapping_editor
    build_mapping_editor(parent_widget, app_ref)
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import json
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gui.app import HexPadGUI

# ── Constantes (dupliquées ici pour autonomie du module) ──────────────────────
PAD_BANK_A    = [36, 37, 38, 39, 40, 41, 42, 43]
PAD_BANK_B    = [44, 45, 46, 47, 48, 49, 50, 51]
KNOB_CC       = [70, 71, 72, 73, 74, 75, 76, 77]
KNOB_LABELS   = ["K1", "K2", "K3", "K4", "K5", "K6", "K7", "K8"]
AXIS_OPTIONS  = ["axis_x", "axis_y", "axis_z", "axis_rx", "axis_ry",
                 "axis_rz", "axis_sl0", "axis_sl1"]
BTN_OPTIONS   = [f"btn_{i}" for i in range(1, 17)]
MACRO_OPTIONS = [
    "ctrl+z", "ctrl+s", "ctrl+c", "ctrl+v", "ctrl+shift+z", "ctrl+x",
    "f1","f2","f3","f4","f5","f6","f7","f8","f9","f10","f11","f12",
    "esc", "space", "enter", "tab", "backspace", "delete",
    "up", "down", "left", "right",
    "a","b","c","d","e","f","g","h","i","j","k","l","m",
    "n","o","p","q","r","s","t","u","v","w","x","y","z",
]
OBS_ACTIONS      = ["scene", "toggle_mute", "toggle_stream",
                    "toggle_record", "screenshot", "toggle_source", "hotkey"]
OBS_NEEDS_SCENE  = {"scene"}
OBS_NEEDS_SOURCE = {"toggle_mute", "toggle_source"}
HTTP_METHODS     = ["GET", "POST", "PUT", "DELETE", "PATCH"]
DISPLAY_TYPES    = ["text", "image", "gif", "clear"]

_NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
def note_name(n): return f"{_NOTE_NAMES[n % 12]}{(n // 12) - 1}"


class MappingEditor:
    """
    Panneau Mapping Editor embarqué dans un parent (Frame, Toplevel…).
    app : référence à HexPadGUI pour accéder à config, C, etc.
    """

    def __init__(self, parent: tk.Widget, app: "HexPadGUI"):
        self.parent = parent
        self.app    = app
        self.C      = app.C

        # State variables
        self._me_prog_var        = tk.StringVar()
        self._me_prog_map        = {}
        self._me_name_var        = tk.StringVar()
        self._me_mode_var        = tk.StringVar(value="gamepad")
        self._me_bank_var        = tk.StringVar(value="A")
        self._me_show_note_var   = tk.BooleanVar(value=True)
        self._me_ws_url_var      = tk.StringVar(value="ws://localhost:8765")
        self._me_obs_host_var    = tk.StringVar(value="localhost")
        self._me_obs_port_var    = tk.StringVar(value="4455")
        self._me_obs_pass_var    = tk.StringVar(value="")
        self._me_pitch_var       = tk.StringVar(value="")
        self._me_mod_var         = tk.StringVar(value="")
        self._me_sounds_dir_var  = tk.StringVar(value="sounds")
        self._me_http_timeout_var = tk.StringVar(value="3")
        self._me_music_vol_var   = tk.StringVar(value="1.0")
        self._me_music_dev_var   = tk.StringVar(value="")
        self._me_disp_bg_var     = tk.StringVar(value="#000000")
        self._me_disp_fg_var     = tk.StringVar(value="#ffffff")
        self._me_pad_vars        = {}
        self._me_pad_sub_vars    = {}
        self._me_knob_vars       = {}
        self._me_save_indicator  = None
        self._me_conn_frame      = None
        self._me_pad_frame       = None
        self._me_knob_frame      = None
        self._me_prog_cb         = None

        self._build()
        self._me_load_preset()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build(self):
        C = self.C
        parent = self.parent

        hdr = tk.Frame(parent, bg=C["panel2"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="◈ MAPPING EDITOR", font=("Courier", 10, "bold"),
            fg=C["accent"], bg=C["panel2"]).pack(side="left", padx=12, pady=8)
        self._me_save_indicator = tk.Label(hdr, text="", font=("Courier", 8),
            fg=C["green"], bg=C["panel2"])
        self._me_save_indicator.pack(side="right", padx=12)
        tk.Button(hdr, text="↑ Export", font=("Courier", 8), bg=C["btn"],
            fg=C["accent2"], relief="flat", padx=6, pady=4, cursor="hand2",
            command=self.export_preset).pack(side="right", padx=2)
        tk.Button(hdr, text="↓ Import", font=("Courier", 8), bg=C["btn"],
            fg=C["accent2"], relief="flat", padx=6, pady=4, cursor="hand2",
            command=self.import_preset).pack(side="right", padx=2)

        canvas = tk.Canvas(parent, bg=C["bg"], bd=0, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(canvas, bg=C["bg"])
        body_win = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(
            body_win, width=e.width))
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # Preset selector
        prow = tk.Frame(body, bg=C["bg"])
        prow.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(prow, text="Preset :", font=("Courier", 9, "bold"),
            fg=C["dim"], bg=C["bg"]).pack(side="left")
        prog_keys   = list(self.app.config.get("programs", {}).keys())
        prog_labels = [f"{k} — {self.app.config['programs'][k].get('name','')}" for k in prog_keys]
        self._me_prog_map = dict(zip(prog_labels, prog_keys))
        self._me_prog_cb  = ttk.Combobox(prow, textvariable=self._me_prog_var,
            values=prog_labels, width=28, state="readonly", style="H.TCombobox")
        self._me_prog_cb.pack(side="left", padx=8)
        for label, key in self._me_prog_map.items():
            if key == self.app._current_prog:
                self._me_prog_var.set(label); break
        self._me_prog_cb.bind("<<ComboboxSelected>>", self._me_on_prog_changed)
        tk.Button(prow, text="+ Nouveau", font=("Courier", 8), bg=C["btn"],
            fg=C["accent2"], relief="flat", padx=6, pady=4, cursor="hand2",
            command=self._me_new_preset).pack(side="left", padx=4)
        tk.Button(prow, text="✕ Suppr", font=("Courier", 8), bg=C["btn"],
            fg=C["red"], relief="flat", padx=6, pady=4, cursor="hand2",
            command=self._me_delete_preset).pack(side="left")

        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", padx=12, pady=6)

        # Meta row
        meta = tk.Frame(body, bg=C["bg"])
        meta.pack(fill="x", padx=12)
        tk.Label(meta, text="Nom", font=("Courier", 8), fg=C["dim"],
            bg=C["bg"]).grid(row=0, column=0, sticky="w", pady=3)
        tk.Entry(meta, textvariable=self._me_name_var, bg=C["btn"],
            fg=C["accent"], font=("Courier", 9), relief="flat", width=20,
            insertbackground=C["accent"]).grid(row=0, column=1, padx=8, sticky="w")
        tk.Label(meta, text="Mode", font=("Courier", 8), fg=C["dim"],
            bg=C["bg"]).grid(row=0, column=2, sticky="w", padx=(12, 0))
        from modules.themes import MODE_COLORS
        mode_cb = ttk.Combobox(meta, textvariable=self._me_mode_var,
            values=list(MODE_COLORS.keys()), width=14,
            state="readonly", style="H.TCombobox")
        mode_cb.grid(row=0, column=3, padx=8, sticky="w")
        mode_cb.bind("<<ComboboxSelected>>",
            lambda e: self._me_refresh_mode_fields())

        self._me_conn_frame = tk.Frame(body, bg=C["bg"])
        self._me_conn_frame.pack(fill="x", padx=12, pady=4)

        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", padx=12, pady=6)

        # Bank selector
        bank_row = tk.Frame(body, bg=C["bg"])
        bank_row.pack(fill="x", padx=12)
        tk.Label(bank_row, text="BANK", font=("Courier", 9, "bold"),
            fg=C["accent2"], bg=C["bg"]).pack(side="left")
        for bank in ("A", "B"):
            tk.Radiobutton(bank_row, text=f"  {bank}  ",
                variable=self._me_bank_var, value=bank,
                font=("Courier", 9, "bold"), bg=C["bg"], fg=C["accent"],
                selectcolor=C["btn"], activebackground=C["bg"],
                command=self._me_build_pad_grid).pack(side="left", padx=4)
        tk.Checkbutton(bank_row, text="noms de notes",
            variable=self._me_show_note_var,
            font=("Courier", 7), bg=C["bg"], fg=C["dim"],
            selectcolor=C["btn"], activebackground=C["bg"],
            command=self._me_build_pad_grid).pack(side="right", padx=8)

        tk.Label(body, text="  PADS — layout physique MPK",
            font=("Courier", 8, "bold"), fg=C["accent2"],
            bg=C["bg"]).pack(anchor="w", padx=12, pady=(8, 2))
        self._me_pad_frame = tk.Frame(body, bg=C["bg"])
        self._me_pad_frame.pack(fill="x", padx=12, pady=4)

        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", padx=12, pady=6)

        tk.Label(body, text="  ENCODEURS (CC)", font=("Courier", 8, "bold"),
            fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=12)
        self._me_knob_frame = tk.Frame(body, bg=C["bg"])
        self._me_knob_frame.pack(fill="x", padx=12, pady=4)

        pm_row = tk.Frame(body, bg=C["bg"])
        pm_row.pack(fill="x", padx=12, pady=4)
        for label, var in (("Pitchwheel →", self._me_pitch_var),
                           ("Modwheel →",   self._me_mod_var)):
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

    # ── Load / Refresh ─────────────────────────────────────────────────────────

    def _me_on_prog_changed(self, event=None):
        label = self._me_prog_var.get()
        key   = self._me_prog_map.get(label, label)
        self.app._current_prog = key
        self.app._highlight_prog_btn(key)
        self._me_load_preset()

    def _me_load_preset(self):
        prog = self.app._get_current_preset()
        if not prog: return
        self._me_name_var.set(prog.get("name", f"Programme {self.app._current_prog}"))
        self._me_mode_var.set(prog.get("mode", "debug"))
        self._me_ws_url_var.set(prog.get("ws_url", "ws://localhost:8765"))
        self._me_obs_host_var.set(prog.get("obs_host", "localhost"))
        self._me_obs_port_var.set(str(prog.get("obs_port", 4455)))
        self._me_obs_pass_var.set(prog.get("obs_password", ""))
        self._me_pitch_var.set(prog.get("pitchwheel", ""))
        self._me_mod_var.set(prog.get("modwheel", ""))
        self._me_sounds_dir_var.set(prog.get("sounds_dir", "sounds"))
        self._me_http_timeout_var.set(str(prog.get("http_timeout", 3)))
        self._me_music_vol_var.set(str(prog.get("music_volume", 1.0)))
        self._me_music_dev_var.set(prog.get("music_device", ""))
        self._me_disp_bg_var.set(prog.get("display_bg", "#000000"))
        self._me_disp_fg_var.set(prog.get("display_fg", "#ffffff"))
        self._me_refresh_mode_fields()
        self._me_build_pad_grid()
        self._me_build_knob_grid()

    def refresh_prog_list(self):
        """Appelé par app après create/delete preset."""
        prog_keys   = list(self.app.config.get("programs", {}).keys())
        prog_labels = [f"{k} — {self.app.config['programs'][k].get('name','')}" for k in prog_keys]
        self._me_prog_map = dict(zip(prog_labels, prog_keys))
        self._me_prog_cb.config(values=prog_labels)
        for label, key in self._me_prog_map.items():
            if key == self.app._current_prog:
                self._me_prog_var.set(label); break

    # ── Mode fields ────────────────────────────────────────────────────────────

    def _me_refresh_mode_fields(self):
        C = self.C
        for w in self._me_conn_frame.winfo_children(): w.destroy()
        mode = self._me_mode_var.get()

        def lbl(text):
            return tk.Label(self._me_conn_frame, text=text,
                font=("Courier", 8), fg=C["dim"], bg=C["bg"])
        def ent(var, w=20):
            return tk.Entry(self._me_conn_frame, textvariable=var,
                bg=C["btn"], fg=C["accent"], font=("Courier", 9),
                relief="flat", insertbackground=C["accent"], width=w)

        col = 0
        if mode == "websocket":
            lbl("WS URL").grid(row=0, column=col, sticky="w", padx=(0, 4)); col += 1
            ent(self._me_ws_url_var, 26).grid(row=0, column=col, sticky="w"); col += 1
        elif mode == "obs":
            lbl("Host").grid(row=0, column=col, sticky="w", padx=(0, 4)); col += 1
            ent(self._me_obs_host_var, 14).grid(row=0, column=col, sticky="w"); col += 1
            lbl("Port").grid(row=0, column=col, sticky="w", padx=(8, 4)); col += 1
            ent(self._me_obs_port_var, 5).grid(row=0, column=col, sticky="w"); col += 1
            lbl("Password").grid(row=0, column=col, sticky="w", padx=(8, 4)); col += 1
            ent(self._me_obs_pass_var, 16).grid(row=0, column=col, sticky="w"); col += 1
        elif mode in ("sound_preset", "music"):
            lbl("Sons dir").grid(row=0, column=col, sticky="w", padx=(0, 4)); col += 1
            ent(self._me_sounds_dir_var, 14).grid(row=0, column=col, sticky="w"); col += 1
            if mode == "music":
                lbl("Volume").grid(row=0, column=col, sticky="w", padx=(8, 4)); col += 1
                ent(self._me_music_vol_var, 4).grid(row=0, column=col, sticky="w"); col += 1
                lbl("Device").grid(row=0, column=col, sticky="w", padx=(8, 4)); col += 1
                try:
                    from modules.music_bridge import list_output_devices
                    dev_names = [""] + [d[1] for d in list_output_devices()]
                except Exception:
                    dev_names = [""]
                ttk.Combobox(self._me_conn_frame, textvariable=self._me_music_dev_var,
                    values=dev_names, width=18, state="normal",
                    style="H.TCombobox").grid(row=0, column=col, sticky="w"); col += 1
        elif mode == "http":
            lbl("Timeout (s)").grid(row=0, column=col, sticky="w", padx=(0, 4)); col += 1
            ent(self._me_http_timeout_var, 4).grid(row=0, column=col, sticky="w"); col += 1
            lbl("— méthode + URL par pad ci-dessous").grid(row=0, column=col,
                sticky="w", padx=(12, 0))
        elif mode == "display":
            lbl("BG").grid(row=0, column=col, sticky="w", padx=(0, 4)); col += 1
            ent(self._me_disp_bg_var, 9).grid(row=0, column=col, sticky="w"); col += 1
            lbl("FG").grid(row=0, column=col, sticky="w", padx=(8, 4)); col += 1
            ent(self._me_disp_fg_var, 9).grid(row=0, column=col, sticky="w"); col += 1
            lbl("— type + content par pad ci-dessous").grid(row=0, column=col,
                sticky="w", padx=(12, 0))
        if self._me_pad_frame:
            self._me_build_pad_grid()
        if self._me_knob_frame:
            self._me_build_knob_grid()

    # ── Pad grid ───────────────────────────────────────────────────────────────

    def _me_build_pad_grid(self):
        C = self.C
        for w in self._me_pad_frame.winfo_children(): w.destroy()
        self._me_pad_vars.clear()
        self._me_pad_sub_vars.clear()

        mode     = self._me_mode_var.get()
        bank     = self._me_bank_var.get()
        notes    = PAD_BANK_A if bank == "A" else PAD_BANK_B
        prog     = self.app._get_current_preset() or {}
        pads_key = "pads" if bank == "A" else "pads_bank_b"
        pads     = prog.get(pads_key, {})
        show_note = self._me_show_note_var.get()

        if   mode == "gamepad":                   pad_opts = BTN_OPTIONS
        elif mode == "macro":                     pad_opts = MACRO_OPTIONS
        elif mode == "obs":                       pad_opts = OBS_ACTIONS
        elif mode in ("sound_preset", "music"):   pad_opts = None
        elif mode == "http":                      pad_opts = "http"
        elif mode == "display":                   pad_opts = "display"
        else:                                     pad_opts = None

        layout = [notes[4:8], notes[0:4]]
        for row_idx, row_notes in enumerate(layout):
            for col_idx, note in enumerate(row_notes):
                ns      = str(note)
                pad_num = notes.index(note) + 1
                nn      = note_name(note)
                raw     = pads.get(ns, "")

                card = tk.Frame(self._me_pad_frame, bg=C["panel2"],
                    relief="flat", padx=4, pady=4)
                card.grid(row=row_idx, column=col_idx, padx=3, pady=3, sticky="nsew")
                self._me_pad_frame.columnconfigure(col_idx, weight=1)

                h = tk.Frame(card, bg=C["panel2"]); h.pack(fill="x")
                pad_label = f"P{pad_num}" + (f"  {nn}" if show_note else "")
                tk.Label(h, text=pad_label, font=("Courier", 7, "bold"),
                    fg=C["accent"], bg=C["panel2"]).pack(side="left")
                tk.Label(h, text=f"n{note}", font=("Courier", 6),
                    fg=C["dim"], bg=C["panel2"]).pack(side="left", padx=2)
                learn_btn = tk.Button(h, text="◎", font=("Courier", 7),
                    bg=C["panel2"], fg=C["dim"], relief="flat",
                    cursor="hand2", pady=0, padx=2)
                learn_btn.pack(side="right")
                learn_btn.config(
                    command=lambda ns=ns, b=learn_btn: self.app._me_midi_learn(ns, b))

                # ── Widgets par mode ──────────────────────────────────────────
                if mode == "obs":
                    act_val = raw.get("action", "") if isinstance(raw, dict) else raw or ""
                    sub_val = (raw.get("scene") or raw.get("source") or
                               raw.get("hotkey", "")) if isinstance(raw, dict) else ""
                    act_var = tk.StringVar(value=act_val)
                    sub_var = tk.StringVar(value=sub_val)
                    self._me_pad_vars[ns]     = act_var
                    self._me_pad_sub_vars[ns] = sub_var
                    ttk.Combobox(card, textvariable=act_var,
                        values=[""] + OBS_ACTIONS, width=11,
                        state="normal", style="H.TCombobox").pack(fill="x")
                    tk.Entry(card, textvariable=sub_var, bg=C["btn"],
                        fg=C["accent2"], font=("Courier", 7), relief="flat",
                        width=12, insertbackground=C["accent"]).pack(
                        fill="x", pady=(2, 0))

                elif mode in ("sound_preset", "music"):
                    if isinstance(raw, dict):
                        file_val = raw.get("file", "")
                        vol_val  = str(raw.get("volume", "1.0"))
                        loop_val = raw.get("loop", False)
                    elif raw == "stop_all":
                        file_val, vol_val, loop_val = "stop_all", "1.0", False
                    else:
                        file_val, vol_val, loop_val = raw, "1.0", False
                    file_var = tk.StringVar(value=file_val)
                    vol_var  = tk.StringVar(value=vol_val)
                    loop_var = tk.BooleanVar(value=loop_val)
                    self._me_pad_vars[ns]     = file_var
                    self._me_pad_sub_vars[ns] = (vol_var, loop_var)
                    tk.Entry(card, textvariable=file_var, bg=C["btn"],
                        fg=C["accent"], font=("Courier", 7), relief="flat",
                        insertbackground=C["accent"]).pack(fill="x")
                    vol_row = tk.Frame(card, bg=C["panel2"])
                    vol_row.pack(fill="x", pady=(2, 0))
                    tk.Label(vol_row, text="vol", font=("Courier", 6),
                        fg=C["dim"], bg=C["panel2"]).pack(side="left")
                    tk.Entry(vol_row, textvariable=vol_var, bg=C["btn"],
                        fg=C["accent2"], font=("Courier", 7), relief="flat",
                        width=4, insertbackground=C["accent"]).pack(
                        side="left", padx=2)
                    tk.Checkbutton(vol_row, text="loop", variable=loop_var,
                        font=("Courier", 6), bg=C["panel2"], fg=C["dim"],
                        selectcolor=C["btn"],
                        activebackground=C["panel2"]).pack(side="left", padx=4)

                elif mode == "http":
                    if isinstance(raw, dict):
                        method_val = raw.get("method", "GET")
                        url_val    = raw.get("url", "")
                        body_val   = json.dumps(raw["body"]) if raw.get("body") else ""
                    else:
                        method_val, url_val, body_val = "GET", raw or "", ""
                    method_var = tk.StringVar(value=method_val)
                    url_var    = tk.StringVar(value=url_val)
                    body_var   = tk.StringVar(value=body_val)
                    self._me_pad_vars[ns]     = url_var
                    self._me_pad_sub_vars[ns] = (method_var, body_var)
                    m_row = tk.Frame(card, bg=C["panel2"]); m_row.pack(fill="x")
                    ttk.Combobox(m_row, textvariable=method_var,
                        values=HTTP_METHODS, width=6,
                        state="readonly", style="H.TCombobox").pack(side="left")
                    tk.Entry(m_row, textvariable=url_var, bg=C["btn"],
                        fg=C["accent"], font=("Courier", 7), relief="flat",
                        insertbackground=C["accent"]).pack(
                        side="left", fill="x", expand=True, padx=(2, 0))
                    tk.Entry(card, textvariable=body_var, bg=C["btn"],
                        fg=C["accent2"], font=("Courier", 6), relief="flat",
                        insertbackground=C["accent"]).pack(
                        fill="x", pady=(2, 0))

                elif mode == "display":
                    if isinstance(raw, dict):
                        type_val    = raw.get("type", "text")
                        content_val = raw.get("content", "")
                        color_val   = raw.get("color", "")
                        size_val    = str(raw.get("size", ""))
                    else:
                        type_val, content_val, color_val, size_val = "text", "", "", ""
                    type_var    = tk.StringVar(value=type_val)
                    content_var = tk.StringVar(value=content_val)
                    color_var   = tk.StringVar(value=color_val)
                    size_var    = tk.StringVar(value=size_val)
                    self._me_pad_vars[ns]     = type_var
                    self._me_pad_sub_vars[ns] = (content_var, color_var, size_var)
                    t_row = tk.Frame(card, bg=C["panel2"]); t_row.pack(fill="x")
                    ttk.Combobox(t_row, textvariable=type_var,
                        values=DISPLAY_TYPES, width=6,
                        state="readonly", style="H.TCombobox").pack(side="left")
                    tk.Entry(t_row, textvariable=color_var, bg=C["btn"],
                        fg=C["accent2"], font=("Courier", 7), relief="flat",
                        width=7, insertbackground=C["accent"],
                        ).pack(side="right", padx=(2, 0))
                    tk.Entry(card, textvariable=content_var, bg=C["btn"],
                        fg=C["accent"], font=("Courier", 7), relief="flat",
                        insertbackground=C["accent"]).pack(
                        fill="x", pady=(2, 0))
                    s_row = tk.Frame(card, bg=C["panel2"]); s_row.pack(fill="x", pady=(2,0))
                    tk.Label(s_row, text="size", font=("Courier", 6),
                        fg=C["dim"], bg=C["panel2"]).pack(side="left")
                    tk.Entry(s_row, textvariable=size_var, bg=C["btn"],
                        fg=C["accent2"], font=("Courier", 7), relief="flat",
                        width=4, insertbackground=C["accent"]).pack(
                        side="left", padx=2)

                elif pad_opts is not None:
                    var = tk.StringVar(value=raw if isinstance(raw, str) else "")
                    self._me_pad_vars[ns] = var
                    ttk.Combobox(card, textvariable=var,
                        values=[""] + pad_opts, width=11,
                        state="normal", style="H.TCombobox").pack(fill="x")
                else:
                    var = tk.StringVar(value=raw if isinstance(raw, str) else "")
                    self._me_pad_vars[ns] = var
                    tk.Entry(card, textvariable=var, bg=C["btn"],
                        fg=C["accent"], font=("Courier", 8), relief="flat",
                        insertbackground=C["accent"]).pack(fill="x")

    # ── Knob grid ──────────────────────────────────────────────────────────────

    def _me_build_knob_grid(self):
        C = self.C
        for w in self._me_knob_frame.winfo_children(): w.destroy()
        self._me_knob_vars = {}
        mode  = self._me_mode_var.get()
        prog  = self.app._get_current_preset() or {}
        knobs = prog.get("knobs", {})
        knob_opts = AXIS_OPTIONS if mode == "gamepad" else []
        for i, cc in enumerate(KNOB_CC):
            cell = tk.Frame(self._me_knob_frame, bg=C["panel2"], padx=3, pady=4)
            cell.grid(row=0, column=i, padx=2, pady=2, sticky="nsew")
            self._me_knob_frame.columnconfigure(i, weight=1)
            tk.Label(cell, text=KNOB_LABELS[i], font=("Courier", 8, "bold"),
                fg=C["accent"], bg=C["panel2"]).pack()
            tk.Label(cell, text=f"CC{cc}", font=("Courier", 6),
                fg=C["dim"], bg=C["panel2"]).pack()
            var = tk.StringVar(value=knobs.get(str(cc), ""))
            self._me_knob_vars[str(cc)] = var
            if knob_opts:
                ttk.Combobox(cell, textvariable=var,
                    values=[""] + knob_opts, width=7,
                    state="normal", style="H.TCombobox").pack(fill="x")
            else:
                tk.Entry(cell, textvariable=var, bg=C["btn"], fg=C["accent"],
                    font=("Courier", 7), relief="flat",
                    insertbackground=C["accent"]).pack(fill="x")

    # ── Collect / Validate / Save ──────────────────────────────────────────────

    def _me_collect_preset(self) -> dict:
        mode = self._me_mode_var.get()
        prog = {"mode": mode, "name": self._me_name_var.get()}
        if mode == "websocket":  prog["ws_url"] = self._me_ws_url_var.get()
        if mode == "obs":
            prog["obs_host"] = self._me_obs_host_var.get()
            try:    prog["obs_port"] = int(self._me_obs_port_var.get())
            except: prog["obs_port"] = 4455
            prog["obs_password"] = self._me_obs_pass_var.get()
        if mode in ("sound_preset", "music"):
            prog["sounds_dir"] = self._me_sounds_dir_var.get()
        if mode == "music":
            try:    prog["music_volume"] = float(self._me_music_vol_var.get())
            except: prog["music_volume"] = 1.0
            prog["music_device"] = self._me_music_dev_var.get()
        if mode == "http":
            try:    prog["http_timeout"] = int(self._me_http_timeout_var.get())
            except: prog["http_timeout"] = 3
        if mode == "display":
            prog["display_bg"] = self._me_disp_bg_var.get()
            prog["display_fg"] = self._me_disp_fg_var.get()

        bank     = self._me_bank_var.get()
        pads_key = "pads" if bank == "A" else "pads_bank_b"
        pads     = {}

        for ns, var in self._me_pad_vars.items():
            if mode == "obs":
                act = var.get()
                if not act: continue
                sub_var = self._me_pad_sub_vars.get(ns)
                d = {"action": act}
                if sub_var and sub_var.get():
                    sv = sub_var.get()
                    if act in OBS_NEEDS_SCENE:    d["scene"]  = sv
                    elif act in OBS_NEEDS_SOURCE: d["source"] = sv
                    elif act == "hotkey":          d["hotkey"] = sv
                pads[ns] = d
            elif mode in ("sound_preset", "music"):
                file_v = var.get()
                if not file_v: continue
                if file_v == "stop_all": pads[ns] = "stop_all"; continue
                sub = self._me_pad_sub_vars.get(ns)
                entry = {"file": file_v}
                if sub:
                    vol_var, loop_var = sub
                    try:    entry["volume"] = float(vol_var.get())
                    except: entry["volume"] = 1.0
                    if loop_var.get(): entry["loop"] = True
                pads[ns] = entry
            elif mode == "http":
                url_v = var.get()
                if not url_v: continue
                sub = self._me_pad_sub_vars.get(ns)
                entry = {"url": url_v}
                if sub:
                    method_var, body_var = sub
                    entry["method"] = method_var.get() or "GET"
                    body_str = body_var.get().strip()
                    if body_str:
                        try:    entry["body"] = json.loads(body_str)
                        except: entry["body"] = body_str
                pads[ns] = entry
            elif mode == "display":
                type_v = var.get()
                if not type_v: continue
                sub = self._me_pad_sub_vars.get(ns)
                if type_v == "clear":
                    pads[ns] = {"type": "clear"}
                    continue
                entry = {"type": type_v}
                if sub:
                    content_var, color_var, size_var = sub
                    c = content_var.get()
                    if c: entry["content"] = c
                    col = color_var.get()
                    if col: entry["color"] = col
                    sz = size_var.get()
                    if sz:
                        try: entry["size"] = int(sz)
                        except: pass
                pads[ns] = entry
            else:
                v = var.get()
                if v: pads[ns] = v

        if pads: prog[pads_key] = pads
        existing  = self.app._get_current_preset() or {}
        other_key = "pads_bank_b" if bank == "A" else "pads"
        if other_key in existing: prog[other_key] = existing[other_key]
        knobs = {cc: v.get() for cc, v in self._me_knob_vars.items() if v.get()}
        if knobs: prog["knobs"] = knobs
        pw = self._me_pitch_var.get(); mw = self._me_mod_var.get()
        if pw: prog["pitchwheel"] = pw
        if mw: prog["modwheel"]   = mw
        return prog

    def _me_validate(self, prog: dict) -> list:
        errors = []
        if not prog.get("name"): errors.append("Le nom est vide.")
        if prog.get("mode") == "obs":
            try: int(prog.get("obs_port", ""))
            except: errors.append("OBS port invalide (entier requis).")
        if prog.get("mode") == "http":
            for ns, pad in prog.get("pads", {}).items():
                if isinstance(pad, dict) and not pad.get("url"):
                    errors.append(f"Pad {ns} : URL manquante.")
        if prog.get("mode") == "display":
            for ns, pad in prog.get("pads", {}).items():
                if isinstance(pad, dict) and pad.get("type") not in ("clear", None):
                    if not pad.get("content") and pad.get("type") != "clear":
                        errors.append(f"Pad {ns} : content vide.")
        return errors

    def _me_save(self):
        prog   = self._me_collect_preset()
        errors = self._me_validate(prog)
        if errors:
            messagebox.showerror("Erreur de validation", "\n".join(errors)); return
        self.app.config["programs"][self.app._current_prog] = prog
        self.app._save_config()
        self.refresh_prog_list()
        self.app._build_prog_btns()
        self.app._select_program(self.app._current_prog)
        if self._me_save_indicator:
            self._me_save_indicator.config(text="✓ sauvegardé")
            self.app.root.after(2000,
                lambda: self._me_save_indicator.config(text=""))
        self.app._log(f"[MAP] Preset {self.app._current_prog} sauvegardé")

    # ── Import / Export ────────────────────────────────────────────────────────

    def export_preset(self):
        prog = self.app._get_current_preset()
        if not prog:
            messagebox.showwarning("Export", "Aucun preset sélectionné."); return
        path = filedialog.asksaveasfilename(
            title="Exporter le preset", defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Tous", "*.*")],
            initialfile=f"hexpad_preset_{self.app._current_prog}.json")
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(prog, f, indent=2, ensure_ascii=False)
            self.app._log(f"[EXPORT] {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Export", str(e))

    def import_preset(self):
        path = filedialog.askopenfilename(
            title="Importer un preset",
            filetypes=[("JSON", "*.json"), ("Tous", "*.*")])
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "mode" not in data:
                messagebox.showerror("Import",
                    "Fichier invalide : clé 'mode' manquante."); return
            choice = messagebox.askyesnocancel(
                "Import",
                f"Importer dans le preset {self.app._current_prog} (Oui)\n"
                f"ou créer un nouveau slot (Non) ?")
            if choice is None: return
            if choice:
                key = self.app._current_prog
            else:
                keys = list(self.app.config["programs"].keys())
                key  = str(max(int(k) for k in keys) + 1)
            self.app.config["programs"][key] = data
            self.app._save_config()
            self.app._current_prog = key
            self.app._build_prog_btns()
            self.app._select_program(key)
            self.refresh_prog_list()
            self._me_load_preset()
            self.app._log(f"[IMPORT] {os.path.basename(path)} → slot {key}")
        except Exception as e:
            messagebox.showerror("Import", str(e))

    # ── New / Delete ───────────────────────────────────────────────────────────

    def _me_new_preset(self):
        keys    = list(self.app.config["programs"].keys())
        new_key = str(max(int(k) for k in keys) + 1)
        name    = simpledialog.askstring("Nouveau preset", "Nom :",
            parent=self.parent) or f"Programme {new_key}"
        self.app.config["programs"][new_key] = {"mode": "debug", "name": name}
        self.app._save_config()
        self.app._current_prog = new_key
        self.app._build_prog_btns()
        self.app._select_program(new_key)
        self.refresh_prog_list()
        self._me_load_preset()

    def _me_delete_preset(self):
        if len(self.app.config["programs"]) <= 1:
            messagebox.showwarning("Suppression",
                "Impossible de supprimer le dernier preset."); return
        if messagebox.askyesno("Supprimer",
                f"Supprimer le programme {self.app._current_prog} ?"):
            del self.app.config["programs"][self.app._current_prog]
            self.app._save_config()
            self.app._current_prog = list(
                self.app.config["programs"].keys())[0]
            self.app._build_prog_btns()
            self.app._select_program(self.app._current_prog)
            self.refresh_prog_list()
            self._me_load_preset()
