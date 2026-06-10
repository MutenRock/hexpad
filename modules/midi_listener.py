import mido

class MidiListener:
    def __init__(self, config, dispatcher):
        self.device = config["device_name"]
        self.dispatcher = dispatcher

    def list_devices(self):
        print("[MIDI] Appareils disponibles :")
        for name in mido.get_input_names():
            print(f"  - {name}")

    def start(self):
        self.list_devices()
        print(f"[MIDI] Connexion sur : {self.device}")
        try:
            with mido.open_input(self.device) as port:
                for msg in port:
                    self.dispatcher.handle(msg)
        except Exception as e:
            print(f"[MIDI] Erreur : {e}")
            print("[MIDI] V\u00e9rifie le nom du device dans config.json")
