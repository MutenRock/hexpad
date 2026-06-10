"""
Gamepad bridge — inspiré de :
  https://github.com/c0redumb/midi2vjoy
  https://github.com/pepitooo/midi2vjoy
Requiert : pip install pyvjoy + driver vJoy installé
Supporte : note_on/off, control_change, pitchwheel
"""
try:
    import pyvjoy
    VJOY_OK = True
except ImportError:
    VJOY_OK = False
    print("[GAMEPAD] pyvjoy manquant — pip install pyvjoy")

AXIS_MAP = {
    "axis_x":   0x30, "axis_y":  0x31, "axis_z":  0x32,
    "axis_rx":  0x33, "axis_ry": 0x34, "axis_rz": 0x35,
    "axis_sl0": 0x36, "axis_sl1":0x37,
}

class GamepadBridge:
    def __init__(self, mapping):
        self.pads      = mapping.get("pads",  {})
        self.knobs     = mapping.get("knobs", {})
        self.pitch     = mapping.get("pitchwheel", None)   # ex: "axis_x"
        self.modwheel  = mapping.get("modwheel",    None)  # CC1 -> ex: "axis_y"
        self.btns      = {f"btn_{i}": i for i in range(1, 17)}
        self.j         = None
        if VJOY_OK:
            try:
                self.j = pyvjoy.VJoyDevice(1)
                print("[GAMEPAD] vJoy device 1 initialisé")
            except Exception as e:
                print(f"[GAMEPAD] vJoy erreur : {e}")
                print("[GAMEPAD] Installe le driver vJoy : https://github.com/jshafer817/vJoy/releases")

    def _set_axis(self, axis_name, value_0_32767):
        axis_id = AXIS_MAP.get(axis_name)
        if axis_id and self.j:
            self.j.set_axis(axis_id, max(0, min(32767, value_0_32767)))

    def handle(self, msg):
        if not self.j:
            return

        if msg.type in ("note_on", "note_off"):
            key = str(msg.note)
            if key in self.pads:
                btn_id = self.btns.get(self.pads[key], 1)
                state  = 1 if (msg.type == "note_on" and msg.velocity > 0) else 0
                self.j.set_button(btn_id, state)
                print(f"[GAMEPAD] pad {key} -> btn_{btn_id} {'ON' if state else 'OFF'}")

        elif msg.type == "control_change":
            key = str(msg.control)
            # Modwheel (CC1) -> axe
            if key == "1" and self.modwheel:
                val = int((msg.value / 127) * 32767)
                self._set_axis(self.modwheel, val)
                print(f"[GAMEPAD] modwheel -> {self.modwheel} = {val}")
            # Encodeurs configurés
            elif key in self.knobs:
                val = int((msg.value / 127) * 32767)
                self._set_axis(self.knobs[key], val)
                print(f"[GAMEPAD] CC{key} -> {self.knobs[key]} = {val}")

        elif msg.type == "pitchwheel" and self.pitch:
            # pitch range: -8192 .. +8191 -> 0 .. 32767
            val = int((msg.pitch + 8192) / 16383 * 32767)
            self._set_axis(self.pitch, val)
            print(f"[GAMEPAD] pitchwheel -> {self.pitch} = {val}")
