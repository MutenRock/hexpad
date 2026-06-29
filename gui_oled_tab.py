"""
gui_oled_tab.py

Mixin GUI pour l'onglet OLED du panel TEST de HexPad.

Intégration dans gui.py :

  1) En haut du fichier :
       from gui_oled_tab import build_test_oled

  2) Dans _build_test_tab(), après le bloc Bridges :
       t_oled = tk.Frame(nb, bg=C["bg"])
       nb.add(t_oled, text="  OLED  ")
       build_test_oled(self, t_oled)
"""

import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext
import mido

# CC des 8 knobs MPK Mini MK3 (preset par défaut)
KNOB_CC = [70, 71, 72, 73, 74, 75, 76, 77]


def build_test_oled(gui, parent):
    """
    Injecte l'onglet OLED dans `parent`.
    `gui` est l'instance HexPadGUI — accès à gui.C, gui.root, gui.device_var.
    """
    C = gui.C

    # ── Titre ─────────────────────────────────────────────────────────────
    tk.Label(parent,
        text="  ⬡ AKAI MPK Mini MK3 — Noms OLED des knobs",
        font=("Courier", 8, "bold"), fg=C["accent"], bg=C["bg"]
    ).pack(anchor="w", padx=12, pady=(10, 1))
    tk.Label(parent,
        text="  Envoi en RAM (temporaire). Pour rendre permanent : appuyer sur PRESET sur le MPK.",
        font=("Courier", 7), fg=C["dim"], bg=C["bg"]
    ).pack(anchor="w", padx=12, pady=(0, 6))

    # ── Port MIDI out ─────────────────────────────────────────────────────
    port_row = tk.Frame(parent, bg=C["bg"])
    port_row.pack(fill="x", padx=12, pady=4)
    tk.Label(port_row, text="Port MIDI :",
        font=("Courier", 8), fg=C["dim"], bg=C["bg"]).pack(side="left")

    gui._oled_port_var = tk.StringVar()
    out_names = mido.get_output_names() or ["Aucun"]
    port_cb = ttk.Combobox(port_row, textvariable=gui._oled_port_var,
        values=out_names, width=26, state="readonly", style="H.TCombobox")
    port_cb.pack(side="left", padx=6)

    # Auto-select AKAI
    _auto_select_port(gui._oled_port_var, out_names)

    def _refresh_ports():
        new_names = mido.get_output_names() or ["Aucun"]
        port_cb.config(values=new_names)
        _auto_select_port(gui._oled_port_var, new_names)
        _log("[OLED] Ports MIDI rafraîchis.")

    tk.Button(port_row, text="↺",
        font=("Courier", 9, "bold"), bg=C["bg"], fg=C["accent2"],
        relief="flat", padx=4, cursor="hand2",
        command=_refresh_ports).pack(side="left")

    # ── Grille 8 knobs (2 rangées x 4) ─────────────────────────────────────
    tk.Label(parent, text="  Noms affichés sur l'OLED (max 8 car. ASCII)",
        font=("Courier", 7, "bold"), fg=C["accent2"], bg=C["bg"]
    ).pack(anchor="w", padx=12, pady=(8, 2))

    grid_frame = tk.Frame(parent, bg=C["bg"])
    grid_frame.pack(fill="x", padx=12, pady=4)

    gui._oled_knob_vars = []

    for i in range(8):
        col = i % 4
        row = i // 4
        card = tk.Frame(grid_frame, bg=C["panel2"], padx=6, pady=6)
        card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
        grid_frame.columnconfigure(col, weight=1)

        tk.Label(card,
            text=f"K{i+1}  CC{KNOB_CC[i]}",
            font=("Courier", 7, "bold"),
            fg=C["accent"], bg=C["panel2"]
        ).pack(anchor="w")

        var = tk.StringVar(value=f"K{i+1}")
        gui._oled_knob_vars.append(var)

        entry = tk.Entry(card, textvariable=var,
            bg=C["btn"], fg=C["accent"],
            font=("Courier", 10, "bold"),
            relief="flat", width=9,
            insertbackground=C["accent"],
            justify="center")
        entry.pack(fill="x", pady=(4, 0))

        # Limite 8 chars
        def _limit(sv=var):
            v = sv.get()
            if len(v) > 8:
                sv.set(v[:8])
        var.trace_add("write", lambda *a, sv=var: _limit(sv))

    # ── Séparateur ──────────────────────────────────────────────────────────
    tk.Frame(parent, bg=C["border"], height=1).pack(fill="x", padx=12, pady=8)

    # ── Boutons d'action ───────────────────────────────────────────────────
    btn_row = tk.Frame(parent, bg=C["bg"])
    btn_row.pack(fill="x", padx=12, pady=4)

    def _send_to_ram():
        from modules.akai_oled import AkaiPreset, send_preset
        port = gui._oled_port_var.get()
        if not port or port == "Aucun":
            _log("[OLED] Aucun port sélectionné."); return
        preset = AkaiPreset()
        for i, var in enumerate(gui._oled_knob_vars):
            preset.set_knob_name(i, var.get())
        names_preview = ", ".join(v.get() for v in gui._oled_knob_vars)
        _log(f"[OLED] Envoi → {names_preview}")
        def do():
            msg = send_preset(port, preset)
            gui.root.after(0, _log, msg)
        threading.Thread(target=do, daemon=True).start()

    def _request_dump():
        port = gui._oled_port_var.get()
        if not port or port == "Aucun":
            _log("[OLED] Aucun port sélectionné."); return
        _log(f"[OLED] Lecture preset depuis {port}…")
        def do():
            from modules.akai_oled import request_preset_dump, parse_knob_names_from_dump
            raw, status = request_preset_dump(port)
            gui.root.after(0, _log, status)
            if raw:
                names = parse_knob_names_from_dump(raw)
                def apply_names():
                    for i, name in enumerate(names):
                        if i < len(gui._oled_knob_vars):
                            gui._oled_knob_vars[i].set(name)
                    _log("[OLED] Noms importés depuis le MPK ✓")
                gui.root.after(0, apply_names)
        threading.Thread(target=do, daemon=True).start()

    def _reset_names():
        for i, var in enumerate(gui._oled_knob_vars):
            var.set(f"K{i+1}")
        _log("[OLED] Noms remis à K1–K8.")

    tk.Button(btn_row,
        text="📤  Envoyer en RAM",
        font=("Courier", 9, "bold"),
        bg=C["accent"], fg=C["bg"],
        relief="flat", padx=14, pady=10,
        cursor="hand2", command=_send_to_ram
    ).pack(side="left", padx=(0, 6))

    tk.Button(btn_row,
        text="📥  Lire MPK",
        font=("Courier", 9, "bold"),
        bg=C["accent2"], fg=C["bg"],
        relief="flat", padx=10, pady=10,
        cursor="hand2", command=_request_dump
    ).pack(side="left", padx=(0, 6))

    tk.Button(btn_row,
        text="↺ Reset",
        font=("Courier", 8),
        bg=C["btn"], fg=C["dim"],
        relief="flat", padx=8, pady=10,
        cursor="hand2", command=_reset_names
    ).pack(side="left")

    # ── Note info ───────────────────────────────────────────────────────────
    tk.Frame(parent, bg=C["border"], height=1).pack(fill="x", padx=12, pady=(10, 4))
    tk.Label(parent,
        text="ℹ  Les noms sont en RAM — ils disparaissent si tu éteins le MPK.\n"
             "   Après 'Envoyer en RAM', maintenir SHIFT + PRESET sur le MPK pour sauvegarder.",
        font=("Courier", 7), fg=C["dim"], bg=C["bg"], justify="left"
    ).pack(anchor="w", padx=12, pady=(0, 4))

    # ── Log console ─────────────────────────────────────────────────────────
    gui._oled_log_widget = scrolledtext.ScrolledText(
        parent,
        bg=C["console_bg"], fg=C["console_fg"],
        font=("Courier", 8), relief="flat", height=5,
        insertbackground=C["accent"]
    )
    gui._oled_log_widget.pack(fill="both", expand=True, padx=12, pady=(4, 8))
    gui._oled_log_widget.config(state="disabled")

    def _log(msg):
        w = gui._oled_log_widget
        w.config(state="normal")
        ts = time.strftime("%H:%M:%S")
        w.insert("end", f"{ts}  {msg}\n")
        w.see("end")
        w.config(state="disabled")

    _log("[OLED] Panneau prêt. Sélectionne ton port MIDI et nomme tes knobs.")


def _auto_select_port(var: tk.StringVar, names: list):
    """Auto-sélectionne le port AKAI si disponible, sinon le premier."""
    for n in names:
        if any(x in n.lower() for x in ("mpk", "mini", "akai")):
            var.set(n)
            return
    if names:
        var.set(names[0])
