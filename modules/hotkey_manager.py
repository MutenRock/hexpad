#!/usr/bin/env python3
"""
HotKeyManager v2.0
  Raccourcis clavier globaux (hors focus fenêtre) via pynput.
  Actions disponibles :
    start_stop      – démarre ou arrête le listener MIDI
    profile_next    – profil suivant dans la liste
    profile_prev    – profil précédent dans la liste
    profile_1..8    – sélection directe d'un profil par index

  Configuration dans config.json :
    "hotkeys": {
      "<ctrl>+<shift>+s": "start_stop",
      "<ctrl>+<shift>+right": "profile_next",
      "<ctrl>+<shift>+left":  "profile_prev",
      "<ctrl>+<shift>+1":     "profile_1"
    }

  Dépendance : pip install pynput
"""
from __future__ import annotations
import threading
from typing import Callable, Dict, Optional

try:
    from pynput import keyboard as _kb
    PYNPUT_OK = True
except ImportError:
    PYNPUT_OK = False


DEFAULT_HOTKEYS: Dict[str, str] = {
    "<ctrl>+<shift>+s":     "start_stop",
    "<ctrl>+<shift>+right": "profile_next",
    "<ctrl>+<shift>+left":  "profile_prev",
    "<ctrl>+<shift>+1":     "profile_1",
    "<ctrl>+<shift>+2":     "profile_2",
    "<ctrl>+<shift>+3":     "profile_3",
    "<ctrl>+<shift>+4":     "profile_4",
}


class HotKeyManager:
    """
    Gère les raccourcis clavier globaux et les dispatche vers des callbacks.

    Usage :
        hkm = HotKeyManager(config, log_fn=self._log)
        hkm.register("start_stop",   self._start_or_stop)
        hkm.register("profile_next", self._profile_next)
        hkm.register("profile_prev", self._profile_prev)
        for i in range(1, 9):
            hkm.register(f"profile_{i}", lambda i=i: self._select_profile_by_index(i))
        hkm.start()
        # ... later ...
        hkm.stop()
    """

    def __init__(self, config: dict, log_fn: Optional[Callable] = None):
        self._config   = config
        self._log      = log_fn or (lambda msg: None)
        self._actions: Dict[str, Callable] = {}
        self._listener: Optional[object]   = None
        self._lock     = threading.Lock()
        self.enabled   = PYNPUT_OK

    # ── Registration ──────────────────────────────────────────────────────────
    def register(self, action: str, callback: Callable) -> None:
        """Enregistre un callback pour une action nommée."""
        self._actions[action] = callback

    # ── Build hotkey map from config ──────────────────────────────────────────
    def _build_hotkey_map(self) -> Dict[str, Callable]:
        raw = self._config.get("hotkeys", DEFAULT_HOTKEYS)
        mapping: Dict[str, Callable] = {}
        for combo, action in raw.items():
            cb = self._actions.get(action)
            if cb is None:
                self._log(f"[HOTKEY] action inconnue : '{action}' (combo ignoré: {combo})")
                continue
            mapping[combo] = cb
        return mapping

    # ── Start / Stop ──────────────────────────────────────────────────────────
    def start(self) -> None:
        """Démarre l'écoute des hotkeys globaux dans un thread daemon."""
        if not PYNPUT_OK:
            self._log("[HOTKEY] ⚠ pynput non installé — pip install pynput")
            return
        with self._lock:
            if self._listener is not None:
                return
            hk_map = self._build_hotkey_map()
            if not hk_map:
                self._log("[HOTKEY] Aucun hotkey configuré.")
                return
            try:
                self._listener = _kb.GlobalHotKeys(hk_map)
                self._listener.daemon = True
                self._listener.start()
                combos = ", ".join(hk_map.keys())
                self._log(f"[HOTKEY] Actif — {combos}")
            except Exception as e:
                self._log(f"[HOTKEY] Erreur démarrage : {e}")
                self._listener = None

    def stop(self) -> None:
        """Arrête l'écoute des hotkeys."""
        with self._lock:
            if self._listener is not None:
                try:
                    self._listener.stop()
                except Exception:
                    pass
                self._listener = None
                self._log("[HOTKEY] Arrêté.")

    def restart(self) -> None:
        """Redémarre (utile après modification de config)."""
        self.stop()
        self.start()

    # ── Config helpers ────────────────────────────────────────────────────────
    def get_hotkeys_config(self) -> Dict[str, str]:
        """Retourne le mapping combo→action actuellement en config."""
        return dict(self._config.get("hotkeys", DEFAULT_HOTKEYS))

    def set_hotkeys_config(self, mapping: Dict[str, str]) -> None:
        """Met à jour le mapping en mémoire (pas de save disque ici)."""
        self._config["hotkeys"] = mapping

    @staticmethod
    def available_actions() -> list:
        actions = ["start_stop", "profile_next", "profile_prev"]
        actions += [f"profile_{i}" for i in range(1, 9)]
        return actions

    @staticmethod
    def is_available() -> bool:
        return PYNPUT_OK
