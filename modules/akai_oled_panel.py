"""
akai_oled_panel.py

Helper standalone functions for the OLED panel tab in HexPadGUI.
All SysEx construction is delegated to mpk_mini_mk3_display.
This module only handles the "find MIDI output port" logic so gui.py
stays clean.
"""
from __future__ import annotations
import mido
from modules.mpk_mini_mk3_display import build_display_sysex_data, format_sysex


AKAI_KEYWORDS = ("mpk", "mini", "akai")


def find_akai_output() -> str | None:
    """Return the first MIDI output port name that looks like an AKAI MPK Mini."""
    for name in mido.get_output_names():
        if any(k in name.lower() for k in AKAI_KEYWORDS):
            return name
    return None


def send_oled_preset(
    port_name: str,
    program_name: str,
    knob_names: list[str],
) -> str:
    """
    Build the SysEx payload and send it to *port_name*.
    Returns a human-readable status string.
    Raises RuntimeError on any MIDI error.
    """
    data = build_display_sysex_data(program_name, knob_names)
    msg  = mido.Message("sysex", data=data)
    with mido.open_output(port_name) as port:
        port.send(msg)
    return f"[OLED] ✓ envoyé → {port_name}  (preset={program_name!r})"


def preview_sysex(program_name: str, knob_names: list[str]) -> str:
    """Return the hex SysEx string for display without sending."""
    data = build_display_sysex_data(program_name, knob_names)
    return format_sysex(data)
