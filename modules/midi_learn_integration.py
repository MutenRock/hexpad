#!/usr/bin/env python3
"""
midi_learn_integration.py — Intégration du MIDI Learn dans le Mapping Editor.

Fournit deux helpers :
  - build_pad_learn_section(parent, gui, prog_key, colors, bank="A")
      → grille 4x2 de pads (layout physique MPK) avec un LearnButton
        par pad et mise à jour de config.json

  - build_knob_learn_section(parent, gui, prog_key, colors)
      → rangée de 8 knobs CC avec un LearnButton chacun

Chaque LearnButton, quand un événement MIDI est détecté :
  1. Écrit le numéro dans config["programs"][prog_key] au bon endroit
  2. Appelle gui._save_config() pour persister
  3. Flash visuel de confirmation sur le label voisin

Convention de config existante :
  pads   → config["programs"][prog_key]["pads"][str(note)] = action
  knobs  → config["programs"][prog_key]["knobs"][str(cc)]  = action
Ici on ne modifie que la clé (le numéro MIDI), pas l'action assignée.
Si le pad/knob n'avait pas encore d'action, on lui met "debug" par défaut.
"""
from __future__ import annotations

import tkinter as tk
from typing import Dict, Any

from modules.midi_learn_widget import LearnButton

# Layout physique de l'AKAI MPK Mini :
# rangée haute = pads 5-8 (notes 40-43), rangée basse = pads 1-4 (notes 36-39)
PAD_LAYOUT_A: list[list[int]] = [
    [40, 41, 42, 43],  # rangée haute — pad 5, 6, 7, 8
    [36, 37, 38, 39],  # rangée basse — pad 1, 2, 3, 4
]
PAD_LAYOUT_B: list[list[int]] = [
    [48, 49, 50, 51],  # rangée haute — pad 5B, 6B, 7B, 8B
    [44, 45, 46, 47],  # rangée basse — pad 1B, 2B, 3B, 4B
]
PAD_LABELS: Dict[int, str] = {
    36: "P1", 37: "P2", 38: "P3", 39: "P4",
    40: "P5", 41: "P6", 42: "P7", 43: "P8",
    44: "P1B", 45: "P2B", 46: "P3B", 47: "P4B",
    48: "P5B", 49: "P6B", 50: "P7B", 51: "P8B",
}
KNOB_CC     = [70, 71, 72, 73, 74, 75, 76, 77]
KNOB_LABELS = ["K1", "K2", "K3", "K4", "K5", "K6", "K7", "K8"]


# ─────────────────────────────────────────────────────────────────────────────
def build_pad_learn_section(
    parent: tk.Widget,
    gui: Any,
    prog_key: str,
    colors: dict,
    bank: str = "A",
) -> tk.Frame:
    """
    Construit et retourne un Frame contenant la grille 4×2 de LearnButtons.

    Paramètres
    ----------
    parent   : widget parent (Frame du Mapping Editor)
    gui      : instance HexPadGUI (pour _save_config, device_var, root)
    prog_key : clé du preset dans config["programs"]
    colors   : dict thème HexPad
    bank     : "A" ou "B"
    """
    C = colors
    frame = tk.Frame(parent, bg=C["bg"])
    layout = PAD_LAYOUT_A if bank == "A" else PAD_LAYOUT_B

    # En-tête
    tk.Label(
        frame,
        text=f"  PADS — Bank {bank}  (clique ⚡ Learn puis appuie sur le pad)",
        font=("Courier", 7, "bold"),
        fg=C["accent2"],
        bg=C["bg"],
    ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(4, 2))

    for row_idx, row_notes in enumerate(layout):
        for col_idx, note in enumerate(row_notes):
            note_str  = str(note)
            pad_label = PAD_LABELS.get(note, "P?")

            pads_cfg = (
                gui.config
                   .get("programs", {})
                   .get(prog_key, {})
                   .get("pads", {})
            )
            current = pads_cfg.get(note_str, "—")
            if isinstance(current, dict):
                current = current.get("action", "?")
            current_short = str(current)[:6]

            cell = tk.Frame(frame, bg=C["bg"])
            cell.grid(row=row_idx + 1, column=col_idx, padx=3, pady=3)

            lbl = tk.Label(
                cell,
                text=f"{pad_label}\nN{note}\n{current_short}",
                font=("Courier", 7),
                fg=C["dim"],
                bg=C["bg"],
                justify="center",
                width=6,
            )
            lbl.pack()

            def make_pad_cb(n: int, lbl_ref: tk.Label):
                def on_learned(kind: str, number: int) -> None:
                    _apply_pad_learn(gui, prog_key, n, kind, number, lbl_ref, C)
                return on_learned

            LearnButton(
                cell,
                root=gui.root,
                device_var=gui.device_var,
                on_learned=make_pad_cb(note, lbl),
                accept=("note",),
                idle_label="⚡ Learn",
                colors=C,
            ).pack(pady=(2, 0))

    return frame


# ─────────────────────────────────────────────────────────────────────────────
def build_knob_learn_section(
    parent: tk.Widget,
    gui: Any,
    prog_key: str,
    colors: dict,
) -> tk.Frame:
    """
    Construit et retourne un Frame contenant la rangée de 8 LearnButtons knobs.
    Les knobs n'acceptent que des messages CC.
    """
    C = colors
    frame = tk.Frame(parent, bg=C["bg"])

    tk.Label(
        frame,
        text="  ENCODEURS CC  (clique ⚡ Learn puis tourne le knob)",
        font=("Courier", 7, "bold"),
        fg=C["accent2"],
        bg=C["bg"],
    ).grid(row=0, column=0, columnspan=8, sticky="w", pady=(4, 2))

    knobs_cfg = (
        gui.config
           .get("programs", {})
           .get(prog_key, {})
           .get("knobs", {})
    )

    for col_idx, (cc, label) in enumerate(zip(KNOB_CC, KNOB_LABELS)):
        cc_str  = str(cc)
        current = knobs_cfg.get(cc_str, "—")
        if isinstance(current, dict):
            current = current.get("action", "?")
        current_short = str(current)[:6]

        cell = tk.Frame(frame, bg=C["bg"])
        cell.grid(row=1, column=col_idx, padx=3, pady=3)

        lbl = tk.Label(
            cell,
            text=f"{label}\nCC{cc}\n{current_short}",
            font=("Courier", 7),
            fg=C["dim"],
            bg=C["bg"],
            justify="center",
            width=6,
        )
        lbl.pack()

        def make_knob_cb(cc_num: int, lbl_ref: tk.Label):
            def on_learned(kind: str, number: int) -> None:
                _apply_knob_learn(gui, prog_key, cc_num, kind, number, lbl_ref, C)
            return on_learned

        LearnButton(
            cell,
            root=gui.root,
            device_var=gui.device_var,
            on_learned=make_knob_cb(cc, lbl),
            accept=("cc",),
            idle_label="⚡ Learn",
            colors=C,
        ).pack(pady=(2, 0))

    return frame


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internes
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_prog(gui: Any, prog_key: str) -> dict:
    """Garantit que le preset existe dans config."""
    progs = gui.config.setdefault("programs", {})
    return progs.setdefault(prog_key, {})


def _apply_pad_learn(
    gui: Any,
    prog_key: str,
    old_note: int,
    kind: str,
    new_note: int,
    lbl: tk.Label,
    C: dict,
) -> None:
    """
    Remap un pad : supprime l'ancienne clé si elle change,
    crée la nouvelle clé avec l'action existante (ou "debug").
    """
    prog = _ensure_prog(gui, prog_key)
    pads = prog.setdefault("pads", {})

    old_str = str(old_note)
    new_str = str(new_note)
    existing_action = pads.get(old_str, "debug")

    if old_str != new_str and old_str in pads:
        del pads[old_str]
    pads[new_str] = existing_action

    gui._save_config()

    pad_label    = PAD_LABELS.get(old_note, "P?")
    action_short = (
        str(existing_action)[:6]
        if isinstance(existing_action, str)
        else existing_action.get("action", "?")[:6]
    )
    try:
        lbl.config(
            text=f"{pad_label}\nN{new_note}\n{action_short}",
            fg=C.get("green", "#22c55e"),
        )
        lbl.after(2000, lambda: lbl.config(fg=C.get("dim", "#6b7280")))
    except tk.TclError:
        pass

    print(f"[MIDI LEARN] Pad {pad_label} → note {new_note} (action: {existing_action})")


def _apply_knob_learn(
    gui: Any,
    prog_key: str,
    old_cc: int,
    kind: str,
    new_cc: int,
    lbl: tk.Label,
    C: dict,
) -> None:
    """
    Remap un knob CC : mêmes principes que les pads.
    """
    prog  = _ensure_prog(gui, prog_key)
    knobs = prog.setdefault("knobs", {})

    old_str = str(old_cc)
    new_str = str(new_cc)
    existing_action = knobs.get(old_str, "debug")

    if old_str != new_str and old_str in knobs:
        del knobs[old_str]
    knobs[new_str] = existing_action

    gui._save_config()

    knob_idx     = KNOB_CC.index(old_cc) if old_cc in KNOB_CC else -1
    knob_label   = KNOB_LABELS[knob_idx] if knob_idx >= 0 else "K?"
    action_short = (
        str(existing_action)[:6]
        if isinstance(existing_action, str)
        else existing_action.get("action", "?")[:6]
    )
    try:
        lbl.config(
            text=f"{knob_label}\nCC{new_cc}\n{action_short}",
            fg=C.get("green", "#22c55e"),
        )
        lbl.after(2000, lambda: lbl.config(fg=C.get("dim", "#6b7280")))
    except tk.TclError:
        pass

    print(f"[MIDI LEARN] Knob {knob_label} → CC {new_cc} (action: {existing_action})")
