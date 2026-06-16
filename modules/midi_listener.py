#!/usr/bin/env python3
"""
HexPad — MidiListener v2.1
- Partage de port avec le GUI monitor (callback on_raw)
- Arrêt propre via threading.Event
"""
from __future__ import annotations
import mido
import threading
from typing import Callable, Optional


class MidiListener:
    def __init__(self, config: dict, dispatcher,
                 on_raw: Optional[Callable] = None):
        """
        on_raw : callback(msg) appelé pour CHAQUE message reçu,
                 en plus du dispatcher. Utilisé par le GUI monitor
                 pour flasher les pads sans ouvrir un second port.
        """
        self.device_name = config["device_name"]
        self.dispatcher  = dispatcher
        self.on_raw      = on_raw
        self._stop_event = threading.Event()

    def _resolve_device(self) -> Optional[str]:
        available = mido.get_input_names()
        if self.device_name in available:
            return self.device_name
        matches = [n for n in available
                   if self.device_name.lower() in n.lower()]
        if matches:
            print(f"[MIDI] Auto-detect : '{self.device_name}' → '{matches[0]}'")
            return matches[0]
        return None

    def stop(self):
        self._stop_event.set()

    def start(self):
        device = self._resolve_device()
        if not device:
            print(f"[MIDI] ERREUR : aucun appareil '{self.device_name}'")
            avail = mido.get_input_names()
            print(f"[MIDI] Disponibles : {avail}")
            return
        print(f"[MIDI] Connexion : {device}")
        try:
            with mido.open_input(device) as port:
                print("[MIDI] En écoute… (STOP pour quitter)")
                while not self._stop_event.is_set():
                    msg = port.poll()
                    if msg is not None:
                        if self.on_raw:
                            try:
                                self.on_raw(msg)
                            except Exception:
                                pass
                        self.dispatcher.handle(msg)
                print("[MIDI] Arrêt propre.")
        except Exception as e:
            print(f"[MIDI] Erreur : {e}")
