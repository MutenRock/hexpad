"""
Gamepad bridge — inspiré de :
  https://github.com/c0redumb/midi2vjoy
  https://github.com/pepitooo/midi2vjoy
Requiert : pip install pyvjoy + driver vJoy installé
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
        self.pads  = mapping.get("pads",  {})
        self.knobs = mapping.get("knobs", {})
        self.btns  = {f"btn_{i}": i for i in range(1, 17)}
        if VJOY_OK:
            self.j = pyvjoy.VJoyDevice(1)
            print("[GAMEPAD] vJoy device 1 initialisé")

    def handle(self, msg):
        if not VJOY_OK:
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
            if key in self.knobs:
                axis_id = AXIS_MAP.get(self.knobs[key])
                if axis_id:
                    val = int((msg.value / 127) * 32767)
                    self.j.set_axis(axis_id, val)
                    print(f"[GAMEPAD] CC{key} -> {self.knobs[key]} = {val}")
