#!/usr/bin/env python3
"""
Combo Engine — execution de macros / combos complexes via pynput.

Format sequence (string, tokens separes par virgules) :
  Touche simple  : "j"          -> press+release j
  Simultanee     : "j+k"        -> press j, press k, release k, release j
  Delai (ms)     : "50"         -> time.sleep(0.050)
  Modificateur   : "ctrl+z"     -> ctrl maintenu pendant z
  Touche speciale: "space", "enter", "esc", "f5", "up", "down", "left", "right"

Exemples :
  BnB 2XKO  : "j,j,k,50,l,80,j+k"
  Super S1   : "i,50,o"
  Dash avant : "d,30,d"

Usage :
  engine = ComboEngine()
  engine.execute("j,j,k,50,l")          # fire and forget
  engine.execute("j+k", blocking=True)  # attend la fin
"""
import threading
import time

try:
    from pynput.keyboard import Key, Controller as KBController
    PYNPUT_OK = True
except ImportError:
    PYNPUT_OK = False
    print("[COMBO] pynput manquant — pip install pynput")

# Mapping noms -> pynput Key
SPECIAL_KEYS = {
    "space":     "space",
    "enter":     "enter",
    "esc":       "esc",
    "tab":       "tab",
    "backspace": "backspace",
    "delete":    "delete",
    "up":        "up",
    "down":      "down",
    "left":      "left",
    "right":     "right",
    "shift":     "shift",
    "ctrl":      "ctrl",
    "alt":       "alt",
    "cmd":       "cmd",
    "f1":"f1","f2":"f2","f3":"f3","f4":"f4","f5":"f5",
    "f6":"f6","f7":"f7","f8":"f8","f9":"f9","f10":"f10",
    "f11":"f11","f12":"f12",
    "comma":     ",",
    "period":    ".",
    "semicolon": ";",
    "slash":     "/",
    "backslash": "\\",
    "minus":     "-",
    "equal":     "=",
    "lbracket":  "[",
    "rbracket":  "]",
}

# Timing par defaut entre chaque token (ms)
DEFAULT_DELAY_MS  = 40
# Duree pression d'une touche (ms)
PRESS_DURATION_MS = 30


class ComboEngine:
    def __init__(self, default_delay=DEFAULT_DELAY_MS, press_duration=PRESS_DURATION_MS):
        self.default_delay   = default_delay / 1000.0
        self.press_duration  = press_duration / 1000.0
        self._kb             = KBController() if PYNPUT_OK else None
        self._running        = threading.Event()
        self._current_thread = None

    def execute(self, sequence: str, blocking=False, loop=False):
        """Lance l'execution d'une sequence combo.
        - sequence : string de tokens (voir format ci-dessus)
        - blocking : attendre la fin avant de retourner
        - loop     : repeter en boucle jusqu'a stop()
        """
        if not PYNPUT_OK:
            print("[COMBO] pynput non disponible")
            return
        self.stop()  # Stoppe le combo precedent si en cours
        self._running.set()
        def run():
            try:
                if loop:
                    while self._running.is_set():
                        self._play(sequence)
                else:
                    self._play(sequence)
            except Exception as e:
                print(f"[COMBO] Erreur execution : {e}")
            finally:
                self._running.clear()
        self._current_thread = threading.Thread(target=run, daemon=True)
        self._current_thread.start()
        if blocking:
            self._current_thread.join()

    def stop(self):
        """Interrompt le combo en cours."""
        self._running.clear()
        if self._current_thread and self._current_thread.is_alive():
            self._current_thread.join(timeout=0.3)

    def _play(self, sequence: str):
        """Execute une sequence token par token."""
        tokens = [t.strip() for t in sequence.split(",")]
        for token in tokens:
            if not self._running.is_set():
                break
            if not token:
                continue
            # Delai numerique
            try:
                delay_ms = int(token)
                time.sleep(delay_ms / 1000.0)
                continue
            except ValueError:
                pass
            # Touches simultanees (j+k) ou modificateur (ctrl+z)
            if "+" in token:
                self._press_chord(token.split("+"))
            else:
                self._press_key(token)
            time.sleep(self.default_delay)

    def _resolve_key(self, name: str):
        """Resout un nom de touche en objet pynput."""
        name = name.strip().lower()
        # Touche speciale
        if name in SPECIAL_KEYS:
            mapped = SPECIAL_KEYS[name]
            if len(mapped) == 1:
                return mapped  # caractere direct
            return getattr(Key, mapped, name)
        # Touche speciale pynput directe (ex: "f5")
        if hasattr(Key, name):
            return getattr(Key, name)
        # Caractere simple
        return name

    def _press_key(self, name: str):
        """Presse et relache une touche simple."""
        key = self._resolve_key(name)
        try:
            self._kb.press(key)
            time.sleep(self.press_duration)
            self._kb.release(key)
        except Exception as e:
            print(f"[COMBO] Touche '{name}' erreur : {e}")

    def _press_chord(self, names: list):
        """Presse simultanement plusieurs touches (ex: j+k, ctrl+z)."""
        keys = [self._resolve_key(n) for n in names]
        try:
            for k in keys:
                self._kb.press(k)
            time.sleep(self.press_duration)
            for k in reversed(keys):
                self._kb.release(k)
        except Exception as e:
            print(f"[COMBO] Accord '{'+'.join(names)}' erreur : {e}")
