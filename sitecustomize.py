"""
Auto-bootstrap HexPad local config and live MIDI device presence.

Python imports sitecustomize automatically at startup when this file is on the
import path. Keeping this small hook at repository root lets python gui.py work
on a fresh clone even though config.json is intentionally git-ignored.
"""
from pathlib import Path

try:
    from modules.config_defaults import ensure_local_config

    root = Path.cwd()
    if (root / "gui.py").exists():
        ensure_local_config(root, silent=True)
except Exception:
    pass


# Live device presence for the Tk GUI.
# This is intentionally best-effort: it must never prevent the app from starting.
try:
    import tkinter as _tk
    import mido as _mido

    _ORIG_MAINLOOP = _tk.Tk.mainloop
    _DEVICE_HINTS = ("mpk", "mini", "akai", "pad")

    def _devices():
        try:
            return [d for d in _mido.get_input_names() if d and d.lower() != "aucun"]
        except Exception:
            return []

    def _choose_device(devices):
        if not devices:
            return None
        for d in devices:
            dl = d.lower()
            if any(h in dl for h in _DEVICE_HINTS):
                return d
        return devices[0]

    def _walk(widget):
        out = [widget]
        for child in widget.winfo_children():
            out.extend(_walk(child))
        return out

    def _set_first_combobox(root, device):
        for w in _walk(root):
            try:
                if w.winfo_class() == "TCombobox":
                    w.configure(values=_devices() or ["Aucun"])
                    if device:
                        w.set(device)
                    return
            except Exception:
                pass

    def _set_status_dot(root, connected):
        color = "#3b82f6" if connected else "#ef4444"
        for w in _walk(root):
            try:
                if w.winfo_class() == "Label" and w.cget("text") == "●":
                    # Do not override active/running green if already set by the app.
                    current = str(w.cget("fg")).lower()
                    if current not in ("#22c55e", "green"):
                        w.configure(fg=color)
                    return
            except Exception:
                pass

    def _set_start_label(root, connected):
        for w in _walk(root):
            try:
                if w.winfo_class() == "Button" and "START" in str(w.cget("text")):
                    if connected:
                        w.configure(text="▶▶  START — PAD READY")
                    else:
                        w.configure(text="▶▶  START — NO PAD")
                    return
            except Exception:
                pass

    def _poll(root, last=[None]):
        try:
            devices = _devices()
            device = _choose_device(devices)
            connected = device is not None
            _set_first_combobox(root, device)
            _set_status_dot(root, connected)
            _set_start_label(root, connected)
            last[0] = device
        except Exception:
            pass
        try:
            root.after(1000, lambda: _poll(root, last))
        except Exception:
            pass

    def _mainloop_with_device_presence(self, *args, **kwargs):
        try:
            self.after(100, lambda: _poll(self))
        except Exception:
            pass
        return _ORIG_MAINLOOP(self, *args, **kwargs)

    if not getattr(_tk.Tk, "_hexpad_device_presence", False):
        _tk.Tk.mainloop = _mainloop_with_device_presence
        _tk.Tk._hexpad_device_presence = True
except Exception:
    pass
