"""
Macros clavier OS — mappe les pads sur des raccourcis clavier.
Requiert : pip install pynput
"""
try:
    from pynput.keyboard import Controller, Key
    PYNPUT_OK = True
except ImportError:
    PYNPUT_OK = False
    print("[MACRO] pynput manquant — pip install pynput")

KEY_MAP = {
    "ctrl": "Key.ctrl", "alt": "Key.alt", "shift": "Key.shift",
    "enter": "Key.enter", "space": "Key.space", "esc": "Key.esc",
    "up": "Key.up", "down": "Key.down", "left": "Key.left", "right": "Key.right",
    **{f"f{i}": f"Key.f{i}" for i in range(1, 13)},
}

class MacroBridge:
    def __init__(self, mapping):
        self.pads = mapping.get("pads", {})
        if PYNPUT_OK:
            self.kb = Controller()

    def _resolve(self, token):
        from pynput.keyboard import Key
        token = token.strip().lower()
        if token in KEY_MAP:
            return eval(KEY_MAP[token])
        return token

    def _fire(self, combo):
        keys = [self._resolve(p) for p in combo.split("+")]
        for k in keys:   self.kb.press(k)
        for k in reversed(keys): self.kb.release(k)
        print(f"[MACRO] {combo}")

    def handle(self, msg):
        if not PYNPUT_OK:
            return
        if msg.type == "note_on" and msg.velocity > 0:
            combo = self.pads.get(str(msg.note))
            if combo:
                self._fire(combo)
