class Dispatcher:
    def __init__(self):
        self.bridge = None
        self.mode = "debug"

    def set_bridge(self, bridge, mode):
        self.bridge = bridge
        self.mode = mode
        print(f"[DISPATCHER] Mode actif : {mode}")

    def handle(self, msg):
        if self.mode == "debug":
            print(f"[DEBUG MIDI] {msg}")
        elif self.bridge:
            self.bridge.handle(msg)
