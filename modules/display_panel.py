"""
display_panel.py — Widget panneau OLED AKAI MPK Mini MK3 pour HexPad GUI.

Intègre :
  - 8 champs de noms de knobs éditables (max 16 chars chacun)
  - Champ nom de preset OLED (16 chars)
  - Bouton ▶ Envoyer → construit le SysEx et l'envoie via mido
  - Bouton ↺ Reset    → recharge les noms depuis le Mapping Editor
  - Auto-remplissage depuis gui._me_knob_vars si disponible
  - Indicateur de statut (✓ OK / ✗ ERR / ⚠ No MK3)
  - Bouton « Copier SysEx » pour debug

Usage dans gui.py :

    from modules.display_panel import OLEDPanel
    # Dans _build_test_tab ou un onglet dédié :
    panel = OLEDPanel(parent_frame, self)
    panel.pack(fill='both', expand=True)
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

try:
    import mido
    MIDO_OK = True
except ImportError:
    MIDO_OK = False

from modules.mpk_mini_mk3_display import (
    build_display_sysex_data,
    format_sysex,
    KNOB_NAME_LENGTH,
)

_MAX_PRESET_NAME = 16
_KNOB_COUNT = 8


class OLEDPanel(tk.Frame):
    """
    Widget autonome — s'intègre dans n'importe quel Frame Tkinter.
    `gui` est l'instance HexPadGUI ; seuls .C (thème) et
    .device_var (StringVar du device MIDI) sont requis.
    """

    def __init__(self, parent: tk.Widget, gui, **kw) -> None:
        C = gui.C
        kw.setdefault("bg", C["bg"])
        super().__init__(parent, **kw)
        self._gui = gui
        self._C   = C
        self._knob_vars:   list[tk.StringVar] = [tk.StringVar(value=f"Knob {i+1}") for i in range(_KNOB_COUNT)]
        self._preset_var:  tk.StringVar        = tk.StringVar(value="HEXPAD")
        self._status_var:  tk.StringVar        = tk.StringVar(value="")
        self._build()

    # ──────────────────────────────────────────────────────────────
    # Construction UI
    # ──────────────────────────────────────────────────────────────
    def _build(self) -> None:
        C = self._C

        # ── Titre
        hdr = tk.Frame(self, bg=C["panel"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="◈ AKAI OLED — MPK Mini MK3",
                 font=("Courier", 9, "bold"),
                 fg=C["accent"], bg=C["panel"]).pack(side="left", padx=10, pady=6)
        tk.Label(hdr,
                 text="Envoie un preset RAM via SysEx",
                 font=("Courier", 7), fg=C["dim"], bg=C["panel"]
                 ).pack(side="left")

        # ── Nom du preset
        name_row = tk.Frame(self, bg=C["bg"])
        name_row.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(name_row, text="Nom preset (OLED)",
                 font=("Courier", 8), fg=C["dim"], bg=C["bg"]).pack(side="left")
        tk.Entry(name_row, textvariable=self._preset_var,
                 bg=C["btn"], fg=C["accent"], font=("Courier", 9),
                 relief="flat", width=18,
                 insertbackground=C["accent"],
                 validate="key",
                 validatecommand=(
                     self.register(lambda v: len(v) <= _MAX_PRESET_NAME), "%P")
                 ).pack(side="left", padx=8)
        tk.Label(name_row, text=f"max {_MAX_PRESET_NAME} car.",
                 font=("Courier", 7), fg=C["dim"], bg=C["bg"]).pack(side="left")

        # ── Séparateur
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x", padx=12, pady=4)

        # ── Grille 4×2 des knobs
        tk.Label(self, text="  NOMS DES KNOBS",
                 font=("Courier", 7, "bold"),
                 fg=C["accent2"], bg=C["bg"]).pack(anchor="w", padx=12)
        grid = tk.Frame(self, bg=C["bg"])
        grid.pack(fill="x", padx=12, pady=4)
        for i in range(_KNOB_COUNT):
            row, col = divmod(i, 4)
            cell = tk.Frame(grid, bg=C["panel2"], padx=4, pady=4)
            cell.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")
            grid.columnconfigure(col, weight=1)
            tk.Label(cell,
                     text=f"K{i+1}  CC{70+i}",
                     font=("Courier", 7, "bold"),
                     fg=C["accent"], bg=C["panel2"]).pack(anchor="w")
            ent = tk.Entry(cell, textvariable=self._knob_vars[i],
                           bg=C["btn"], fg=C["text"] if "text" in C else C["accent"],
                           font=("Courier", 8), relief="flat", width=14,
                           insertbackground=C["accent"],
                           validate="key",
                           validatecommand=(
                               self.register(lambda v: len(v) <= KNOB_NAME_LENGTH), "%P")
                           )
            ent.pack(fill="x")

        # ── Séparateur
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x", padx=12, pady=6)

        # ── Boutons d'action
        btn_row = tk.Frame(self, bg=C["bg"])
        btn_row.pack(fill="x", padx=12, pady=(0, 4))

        tk.Button(btn_row, text="▶  Envoyer sur AKAI",
                  font=("Courier", 9, "bold"),
                  bg=C["accent"], fg=C["bg"],
                  relief="flat", padx=12, pady=8,
                  cursor="hand2",
                  command=self._send).pack(side="left", padx=(0, 6))

        tk.Button(btn_row, text="↺  Auto-fill",
                  font=("Courier", 8),
                  bg=C["btn"], fg=C["dim"],
                  relief="flat", padx=8, pady=8,
                  cursor="hand2",
                  command=self._autofill).pack(side="left", padx=(0, 6))

        tk.Button(btn_row, text="⎘  Copier SysEx",
                  font=("Courier", 8),
                  bg=C["btn"], fg=C["dim"],
                  relief="flat", padx=8, pady=8,
                  cursor="hand2",
                  command=self._copy_sysex).pack(side="left")

        # ── Indicateur de statut
        self._status_lbl = tk.Label(self, textvariable=self._status_var,
                                    font=("Courier", 8),
                                    fg=C["green"], bg=C["bg"],
                                    anchor="w")
        self._status_lbl.pack(fill="x", padx=14, pady=(2, 8))

        # ── Log SysEx (collapsible)
        tog_row = tk.Frame(self, bg=C["bg"])
        tog_row.pack(fill="x", padx=12)
        self._log_visible  = False
        self._toggle_btn = tk.Button(
            tog_row, text="▸ SysEx brut",
            font=("Courier", 7, "bold"),
            bg=C["bg"], fg=C["dim"],
            relief="flat", padx=4, pady=2,
            cursor="hand2", anchor="w",
            command=self._toggle_log)
        self._toggle_btn.pack(side="left")
        self._log_frame = tk.Frame(self, bg=C["bg"])
        from tkinter import scrolledtext
        self._log_box = scrolledtext.ScrolledText(
            self._log_frame,
            bg=C["console_bg"], fg=C["console_fg"],
            font=("Courier", 7), relief="flat", height=4,
            insertbackground=C["accent"],
            wrap="word",
            state="disabled")
        self._log_box.pack(fill="both", expand=True)

    # ──────────────────────────────────────────────────────────────
    # Logique
    # ──────────────────────────────────────────────────────────────
    def _get_device_name(self) -> str | None:
        """Retourne le device MK3 si trouvé dans les sorties MIDI."""
        if not MIDO_OK:
            return None
        try:
            outputs = mido.get_output_names()
        except Exception:
            return None
        # Préférer le device sélectionné dans la GUI
        preferred = getattr(self._gui, "device_var", None)
        if preferred:
            name = preferred.get()
            if name in outputs:
                return name
        # Sinon chercher AKAI/MPK parmi les sorties
        for n in outputs:
            if any(k in n.lower() for k in ("mpk", "mini", "akai")):
                return n
        return None

    def _build_sysex(self) -> list[int]:
        preset_name = self._preset_var.get().strip() or "HEXPAD"
        knob_names  = [v.get().strip() or f"Knob {i+1}" for i, v in enumerate(self._knob_vars)]
        return build_display_sysex_data(preset_name, knob_names)

    def _send(self) -> None:
        """Envoie le preset SysEx sur le port MIDI AKAI (thread)."""
        def do():
            device = self._get_device_name()
            if device is None:
                self._set_status("⚠ Aucun device AKAI/MPK trouvé", error=True)
                return
            try:
                sysex_data = self._build_sysex()
                self._append_log(format_sysex(sysex_data))
                with mido.open_output(device) as port:
                    msg = mido.Message("sysex", data=sysex_data)
                    port.send(msg)
                self._set_status(f"✓ Envoyé sur {device}", error=False)
            except Exception as exc:
                self._set_status(f"✗ Erreur : {exc}", error=True)
        threading.Thread(target=do, daemon=True).start()

    def _autofill(self) -> None:
        """
        Copie les noms de knobs depuis le Mapping Editor (gui._me_knob_vars)
        si disponible, sinon depuis les labels du preset courant.
        """
        gui = self._gui

        # Depuis le Mapping Editor ouvert
        if hasattr(gui, "_me_knob_vars") and gui._me_knob_vars:
            for i, (cc, var_tuple) in enumerate(gui._me_knob_vars.items()):
                if i >= _KNOB_COUNT:
                    break
                # var_tuple = (action_var,) ou (label_var, ...) selon implémentation
                # On tente d'extraire un label lisible
                label = f"CC{cc}"
                if isinstance(var_tuple, (list, tuple)) and len(var_tuple) > 0:
                    try:
                        label = var_tuple[0].get()[:KNOB_NAME_LENGTH] or label
                    except Exception:
                        pass
                elif hasattr(var_tuple, "get"):
                    try:
                        label = var_tuple.get()[:KNOB_NAME_LENGTH] or label
                    except Exception:
                        pass
                self._knob_vars[i].set(label)
            self._set_status("↺ Noms chargés depuis le Mapping Editor", error=False)
            return

        # Depuis le preset courant
        if hasattr(gui, "_get_current_preset"):
            prog = gui._get_current_preset() or {}
            knobs = prog.get("knobs", {})
            for i in range(_KNOB_COUNT):
                cc  = 70 + i
                raw = knobs.get(str(cc), {})
                label = (raw.get("label", "") if isinstance(raw, dict) else "") or f"Knob {i+1}"
                self._knob_vars[i].set(label[:KNOB_NAME_LENGTH])
            preset_name = prog.get("name", "HEXPAD")[:_MAX_PRESET_NAME]
            self._preset_var.set(preset_name)
            self._set_status("↺ Noms chargés depuis le preset", error=False)

    def _copy_sysex(self) -> None:
        try:
            sysex_data = self._build_sysex()
            txt = format_sysex(sysex_data)
            self.clipboard_clear()
            self.clipboard_append(txt)
            self._set_status("⎘ SysEx copié dans le presse-papiers", error=False)
            self._append_log(txt)
            if not self._log_visible:
                self._toggle_log()
        except Exception as exc:
            self._set_status(f"✗ {exc}", error=True)

    # ──────────────────────────────────────────────────────────────
    # Helpers UI
    # ──────────────────────────────────────────────────────────────
    def _set_status(self, msg: str, error: bool = False) -> None:
        color = self._C.get("red", "#ff5555") if error else self._C.get("green", "#50fa7b")
        self.after(0, lambda: (
            self._status_var.set(msg),
            self._status_lbl.config(fg=color)
        ))

    def _append_log(self, msg: str) -> None:
        def do():
            self._log_box.config(state="normal")
            self._log_box.insert("end", msg + "\n")
            self._log_box.see("end")
            self._log_box.config(state="disabled")
        self.after(0, do)

    def _toggle_log(self) -> None:
        self._log_visible = not self._log_visible
        if self._log_visible:
            self._log_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))
            self._toggle_btn.config(text="▾ SysEx brut")
        else:
            self._log_frame.pack_forget()
            self._toggle_btn.config(text="▸ SysEx brut")
