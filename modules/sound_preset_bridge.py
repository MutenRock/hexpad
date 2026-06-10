#!/usr/bin/env python3
"""
Sound Preset Bridge — sampler .wav/.mp3/.ogg via pygame
Requiert : pip install pygame

Config :
  {
    "mode": "sound_preset",
    "sounds_dir": "sounds",
    "pads": {
      "36": {"file": "kick.wav",  "volume": 1.0},
      "37": {"file": "snare.wav", "volume": 0.9},
      "40": {"file": "bass.wav",  "volume": 1.0, "loop": true},
      "43": {"file": "stop_all"}
    }
  }

Mets tes samples dans le dossier sounds/ a la racine.
Samples libres de droits : https://freesound.org
"""
import os

try:
    import pygame
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    PYGAME_OK = True
    print("[SOUND] pygame.mixer initialise")
except ImportError:
    PYGAME_OK = False
    print("[SOUND] pygame manquant — pip install pygame")
except Exception as e:
    PYGAME_OK = False
    print(f"[SOUND] pygame erreur init : {e}")


class SoundPresetBridge:
    def __init__(self, config):
        self.pads       = config.get("pads", {})
        self.sounds_dir = config.get("sounds_dir", "sounds")
        self.sounds     = {}   # note_str -> (Sound, loop)
        self.channels   = {}   # note_str -> Channel
        if PYGAME_OK:
            self._preload()

    def _preload(self):
        os.makedirs(self.sounds_dir, exist_ok=True)
        for note, cfg in self.pads.items():
            fname  = cfg if isinstance(cfg, str) else cfg.get("file", "")
            volume = 1.0 if isinstance(cfg, str) else cfg.get("volume", 1.0)
            loop   = False if isinstance(cfg, str) else cfg.get("loop", False)
            if fname in ("stop_all", ""):
                continue
            path = os.path.join(self.sounds_dir, fname)
            if not os.path.exists(path):
                print(f"[SOUND] Fichier manquant : {path}")
                continue
            try:
                sound = pygame.mixer.Sound(path)
                sound.set_volume(volume)
                self.sounds[note] = (sound, loop)
                print(f"[SOUND] Charge : {fname} (note {note})")
            except Exception as e:
                print(f"[SOUND] Erreur '{fname}' : {e}")

    def handle(self, msg):
        if not PYGAME_OK:
            return
        key = str(msg.note)
        if msg.type == "note_on" and msg.velocity > 0:
            if key not in self.pads:
                return
            cfg   = self.pads[key]
            fname = cfg if isinstance(cfg, str) else cfg.get("file", "")
            if fname == "stop_all":
                pygame.mixer.stop()
                print("[SOUND] Stop all")
                return
            if key not in self.sounds:
                return
            sound, loop = self.sounds[key]
            base_vol = 1.0 if isinstance(cfg, str) else cfg.get("volume", 1.0)
            sound.set_volume((msg.velocity / 127) * base_vol)
            ch = sound.play(loops=-1 if loop else 0)
            if ch:
                self.channels[key] = ch
            print(f"[SOUND] Play {fname} vel={msg.velocity}")

        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            cfg  = self.pads.get(key, {})
            loop = cfg.get("loop", False) if isinstance(cfg, dict) else False
            if loop and key in self.channels:
                self.channels[key].stop()
                print(f"[SOUND] Stop loop {key}")
