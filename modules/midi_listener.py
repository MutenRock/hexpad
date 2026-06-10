import mido
import threading

class MidiListener:
    def __init__(self, config, dispatcher):
        self.device_name = config["device_name"]
        self.dispatcher  = dispatcher
        self._stop_event = threading.Event()

    def _resolve_device(self):
        available = mido.get_input_names()
        if self.device_name in available:
            return self.device_name
        matches = [n for n in available if self.device_name.lower() in n.lower()]
        if matches:
            print(f"[MIDI] Auto-detect : '{self.device_name}' -> '{matches[0]}'")
            return matches[0]
        return None

    def list_devices(self):
        print("[MIDI] Appareils disponibles :")
        for name in mido.get_input_names():
            print(f"  - {name}")

    def stop(self):
        """Demande l'arret propre du listener."""
        self._stop_event.set()

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
                print("[MIDI] En ecoute... (Ctrl+C ou STOP pour quitter)")
                # Mode non-bloquant avec polling pour pouvoir stopper proprement
                port.close = port.close  # keep ref
                while not self._stop_event.is_set():
                    msg = port.poll()
                    if msg is not None:
                        self.dispatcher.handle(msg)
                print("[MIDI] Arret propre.")
        except KeyboardInterrupt:
            print("\n[MIDI] Arret.")
        except Exception as e:
            print(f"[MIDI] Erreur : {e}")
