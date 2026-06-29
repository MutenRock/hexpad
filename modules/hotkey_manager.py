"""
hotkey_manager.py — Hotkeys globaux HexPad via pynput.

Dépendance optionnelle : pynput
    pip install pynput

Si pynput n'est pas disponible, HotKeyManager se crée sans erreur
mais ne fait rien (fallback silencieux).

Configuration dans config.json :

    "hotkeys": {
        "start_stop"     : "<ctrl>+<alt>+h",
        "next_profile"   : "<ctrl>+<alt>+n",
        "prev_profile"   : "<ctrl>+<alt>+b",
        "mute_console"   : "<ctrl>+<alt>+m"
    }

Toutes les clés sont optionnelles. Les valeurs suivent la syntaxe
pynput HotKey : touches spéciales entre <>, combinaisons avec +.
Exemples valides :
    "<ctrl>+<shift>+h"
    "<f9>"
    "<ctrl>+<alt>+p"
"""
from __future__ import annotations

from typing import Callable, Dict

try:
    from pynput import keyboard as _kb
    PYNPUT_OK = True
except ImportError:
    PYNPUT_OK = False

_DEFAULT_HOTKEYS: Dict[str, str] = {
    "start_stop"   : "<ctrl>+<alt>+h",
    "next_profile" : "<ctrl>+<alt>+n",
    "prev_profile" : "<ctrl>+<alt>+b",
    "mute_console" : "<ctrl>+<alt>+m",
}


class HotKeyManager:
    """
    Gère les raccourcis clavier globaux HexPad.

    Paramètres
    ----------
    config      : dict issu de config.json (clé optionnelle ``hotkeys``)
    callbacks   : dict action → callable, ex. {"start_stop": self._toggle}

    Méthodes publiques
    ------------------
    start()     : démarre le listener (thread daemon)
    stop()      : arrête le listener proprement
    is_active() : True si le listener tourne
    """

    def __init__(self, config: dict, callbacks: Dict[str, Callable]) -> None:
        self._config    = config.get("hotkeys", {})
        self._callbacks = callbacks
        self._listener  = None
        self._hotkeys   = {}   # combinaison → HotKey pynput

    # ──────────────────────────────────────────────────────────────
    def start(self) -> None:
        if not PYNPUT_OK:
            return
        self.stop()
        hotkey_map: Dict[str, Callable] = {}
        for action, default_combo in _DEFAULT_HOTKEYS.items():
            combo = self._config.get(action, default_combo)
            cb    = self._callbacks.get(action)
            if cb is not None:
                hotkey_map[combo] = cb
        if not hotkey_map:
            return
        # Construire les HotKey pynput
        def for_canonical(listener):
            return lambda k: listener.canonical(k)
        triggers = {
            _kb.HotKey.parse(combo): cb
            for combo, cb in hotkey_map.items()
        }
        def on_press(key):
            for hotkey_keys, cb in triggers.items():
                # pynput HotKey est un objet à utiliser avec GlobalHotKeys
                pass
        # Utiliser GlobalHotKeys (API haut niveau pynput)
        self._listener = _kb.GlobalHotKeys(
            {combo: cb for combo, cb in hotkey_map.items()}
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def is_active(self) -> bool:
        return self._listener is not None and self._listener.is_alive()

    def get_combo(self, action: str) -> str:
        """Retourne la combinaison configurée pour une action."""
        return self._config.get(action, _DEFAULT_HOTKEYS.get(action, ""))

    def update_combo(self, action: str, combo: str) -> None:
        """
        Met à jour la combinaison d'une action à chaud.
        Redémarre le listener si il était actif.
        """
        was_active = self.is_active()
        self._config[action] = combo
        if was_active:
            self.start()

    @staticmethod
    def available() -> bool:
        """True si pynput est installé."""
        return PYNPUT_OK

    @staticmethod
    def default_combos() -> Dict[str, str]:
        return dict(_DEFAULT_HOTKEYS)
