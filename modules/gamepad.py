"""
Gamepad bridge — inspired by:
  https://github.com/c0redumb/midi2vjoy
  https://github.com/pepitooo/midi2vjoy
Requires: pip install pyvjoy + vJoy driver installed.
Supports: note_on/off, control_change, pitchwheel.
"""
try:
    import pyvjoy
    VJOY_OK = True
except ImportError:
    VJOY_OK = False
    print("[GAMEPAD] pyvjoy manquant - pip install pyvjoy")

AXIS_MAP = {
    "axis_x":   0x30, "axis_y":  0x31, "axis_z":  0x32,
    "axis_rx":  0x33, "axis_ry": 0x34, "axis_rz": 0x35,
    "axis_sl0": 0x36, "axis_sl1": 0x37,
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
                print("[GAMEPAD] vJoy device 1 initialise")
            except Exception as e:
                print(f"[GAMEPAD] vJoy erreur : {e}")
                print("[GAMEPAD] Installe/active le driver vJoy puis relance HexPad.")

    @property
    def ready(self):
        return self.j is not None

    def stop(self):
        """Release all mapped buttons when stopping."""
        if not self.j:
            return
        for btn_id in self.btns.values():
            try:
                self.j.set_button(btn_id, 0)
            except Exception:
                pass

    def _set_axis(self, axis_name, value_0_32767):
        axis_id = AXIS_MAP.get(axis_name)
        if axis_id and self.j:
            self.j.set_axis(axis_id, max(0, min(32767, int(value_0_32767))))

    def _set_button_from_note(self, note, velocity):
        if not self.j:
            return
        key = str(note)
        if key in self.pads:
            btn_id = self.btns.get(self.pads[key], 1)
            state  = 1 if velocity > 0 else 0
            self.j.set_button(btn_id, state)
            print(f"[GAMEPAD] pad {key} -> btn_{btn_id} {'ON' if state else 'OFF'}")

    # Dispatcher v2 callbacks -------------------------------------------------
    def on_note(self, note, velocity):
        self._set_button_from_note(note, velocity)

    def on_cc(self, control, value):
        if not self.j:
            return
        key = str(control)
        # Modwheel / MPK joystick vertical axis.
        if key == "1" and self.modwheel:
            val = int((value / 127) * 32767)
            self._set_axis(self.modwheel, val)
            print(f"[GAMEPAD] modwheel -> {self.modwheel} = {val}")
        elif key in self.knobs:
            val = int((value / 127) * 32767)
            self._set_axis(self.knobs[key], val)
            print(f"[GAMEPAD] CC{key} -> {self.knobs[key]} = {val}")

    def on_pitchwheel(self, pitch):
        if not self.j or not self.pitch:
            return
        # pitch range: -8192 .. +8191 -> 0 .. 32767
        val = int((pitch + 8192) / 16383 * 32767)
        self._set_axis(self.pitch, val)
        print(f"[GAMEPAD] pitchwheel -> {self.pitch} = {val}")

    # Legacy compat -----------------------------------------------------------
    def handle(self, msg):
        if msg.type == "note_on":
            self.on_note(msg.note, msg.velocity)
        elif msg.type == "note_off":
            self.on_note(msg.note, 0)
        elif msg.type == "control_change":
            self.on_cc(msg.control, msg.value)
        elif msg.type == "pitchwheel":
            self.on_pitchwheel(msg.pitch)
