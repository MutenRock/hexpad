"""
HotkeyManager — global hotkey listener via pynput.

Usage:
    hm = HotkeyManager()
    hm.bind('<ctrl>+<f9>', my_callback)
    hm.start()
    ...
    hm.stop()
"""
from __future__ import annotations
import threading
from typing import Callable, Dict

try:
    from pynput import keyboard as _kb
    PYNPUT_OK = True
except ImportError:
    PYNPUT_OK = False


class HotkeyManager:
    """Register global hotkeys that fire even when the window is unfocused."""

    def __init__(self) -> None:
        self._bindings: Dict[str, Callable] = {}
        self._listener = None
        self._thread: threading.Thread | None = None
        self._running = False
        self.available = PYNPUT_OK

    # ── Public API ───────────────────────────────────────────────────

    def bind(self, hotkey: str, callback: Callable) -> None:
        """Register a hotkey string (pynput syntax) -> callback."""
        self._bindings[hotkey] = callback

    def rebind_all(self, bindings: Dict[str, Callable]) -> None:
        """Replace all bindings. Restarts listener if already running."""
        was_running = self._running
        if was_running:
            self.stop()
        self._bindings = dict(bindings)
        if was_running:
            self.start()

    def start(self) -> None:
        """Start listening in a daemon thread. No-op if already running."""
        if not PYNPUT_OK or self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="HotkeyManager")
        self._thread.start()

    def stop(self) -> None:
        """Stop the listener cleanly."""
        self._running = False
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
        self._listener = None

    # ── Internal ─────────────────────────────────────────────────────

    def _run(self) -> None:
        if not self._bindings:
            self._running = False
            return
        try:
            self._listener = _kb.GlobalHotKeys(self._bindings)
            self._listener.run()   # blocks until stop() is called
        except Exception as exc:
            print(f"[HOTKEY] Erreur listener: {exc}")
        finally:
            self._running = False
