import mido

class MidiListener:
    def __init__(self, config, dispatcher):
        self.device_name = config["device_name"]
        self.dispatcher = dispatcher

    def _resolve_device(self):
        """Exact match d'abord, sinon match partiel automatique."""
        available = mido.get_input_names()
        # 1) Exact
        if self.device_name in available:
            return self.device_name
        # 2) Partial match (ex: config="MPK mini 3" -> trouve "MPK mini 3 0")
        matches = [n for n in available if self.device_name.lower() in n.lower()]
        if matches:
            print(f"[MIDI] Auto-detect : '{self.device_name}' -> '{matches[0]}'")
            return matches[0]
        return None

    def list_devices(self):
        print("[MIDI] Appareils disponibles :")
        for name in mido.get_input_names():
            print(f"  - {name}")

    def start(self):
        self.list_devices()
        device = self._resolve_device()
        if not device:
            print(f"[MIDI] ERREUR : aucun appareil correspondant a '{self.device_name}'")
            print("[MIDI] Corrige 'device_name' dans config.json avec le nom exact ci-dessus.")
            return
        print(f"[MIDI] Connexion sur : {device}")
        try:
            with mido.open_input(device) as port:
                print("[MIDI] En ecoute... (Ctrl+C pour quitter)")
                for msg in port:
                    self.dispatcher.handle(msg)
        except KeyboardInterrupt:
            print("\n[MIDI] Arret.")
        except Exception as e:
            print(f"[MIDI] Erreur : {e}")
