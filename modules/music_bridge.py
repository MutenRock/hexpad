#!/usr/bin/env python3
"""
HexPad Music Bridge v1.7.0
Mode "music" : sampler haute qualité avec sélecteur de sortie audio.

Différences vs SoundPresetBridge :
  - Sélecteur de périphérique audio (sounddevice)
  - Volume global persisté dans config ("music_volume")
  - Chargement depuis sounds_dir (même structure que sound_preset)

Dépendances :
    pip install pygame sounddevice

Config exemple :
{
  "mode": "music",
  "sounds_dir": "sounds",
  "music_volume": 1.0,
  "music_device": "",        # nom du périphérique sounddevice, "" = défaut
  "pads": {
    "36": {"file": "kick.wav",  "volume": 1.0},
    "37": {"file": "snare.wav", "volume": 0.9},
    "43": "stop_all"
  }
}
"""
import os

# ── sounddevice (optionnel — sert à lister les périphériques) ────────────────
try:
    import sounddevice as sd
    SD_OK = True
except ImportError:
    SD_OK = False
    print("[MUSIC] sounddevice manquant — pip install sounddevice")

# ── pygame (moteur audio) ──────────────────────────────────────────
try:
    import pygame
    _mixer_init = False
    PYGAME_OK = True
except ImportError:
    PYGAME_OK = False
    print("[MUSIC] pygame manquant — pip install pygame")


def list_output_devices():
    """Retourne [(index, nom)] des périphériques de sortie audio."""
    if not SD_OK:
        return []
    try:
        devices = sd.query_devices()
        return [(i, d["name"]) for i, d in enumerate(devices) if d["max_output_channels"] > 0]
    except Exception as e:
        print(f"[MUSIC] Erreur liste devices : {e}")
        return []


def get_default_output_device():
    """Retourne le nom du périphérique de sortie par défaut."""
    if not SD_OK:
        return ""
    try:
        idx = sd.default.device[1]
        return sd.query_devices(idx)["name"]
    except Exception:
        return ""


class MusicBridge:
    """
    Sampler audio pour le mode 'music'.
    Utilise pygame.mixer pour la lecture multi-canal.
    """

    def __init__(self, config: dict):
        self.pads       = config.get("pads", {})
        self.sounds_dir = config.get("sounds_dir", "sounds")
        self.volume     = float(config.get("music_volume", 1.0))
        self.device     = config.get("music_device", "")
        self.sounds: dict = {}   # note_str -> (Sound, loop, base_vol)
        self.channels: dict = {}

        if PYGAME_OK:
            self._init_mixer()
            self._preload()

    # ── Init ─────────────────────────────────────────────────────────────────

    def _init_mixer(self):
        global _mixer_init
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            _mixer_init = True
            print(f"[MUSIC] pygame.mixer initialisé  device='{self.device or 'défaut'}'")
        except Exception as e:
            print(f"[MUSIC] pygame.mixer erreur : {e}")

    # ── Preload ─────────────────────────────────────────────────────────────

    def _preload(self):
        os.makedirs(self.sounds_dir, exist_ok=True)
        for note, cfg in self.pads.items():
            fname  = cfg if isinstance(cfg, str) else cfg.get("file", "")
            volume = 1.0 if isinstance(cfg, str) else float(cfg.get("volume", 1.0))
            loop   = False if isinstance(cfg, str) else cfg.get("loop", False)
            if fname in ("stop_all", ""):
                continue
            path = os.path.join(self.sounds_dir, fname)
            if not os.path.exists(path):
                print(f"[MUSIC] Fichier manquant : {path}")
                continue
            try:
                sound = pygame.mixer.Sound(path)
                sound.set_volume(min(1.0, volume * self.volume))
                self.sounds[note] = (sound, loop, volume)
                print(f"[MUSIC] Chargé : {fname}  (note {note}, loop={loop})")
            except Exception as e:
                print(f"[MUSIC] Erreur '{fname}' : {e}")

    # ── Volume global ──────────────────────────────────────────────────────

    def set_volume(self, vol: float):
        """Mise à jour du volume global [0.0–1.0] à chaud."""
        self.volume = max(0.0, min(1.0, vol))
        for note, (sound, loop, base_vol) in self.sounds.items():
            sound.set_volume(min(1.0, base_vol * self.volume))
        print(f"[MUSIC] Volume global → {self.volume:.2f}")

    # ── Handle MIDI ───────────────────────────────────────────────────────

    def handle(self, msg):
        if not PYGAME_OK or not _mixer_init:
            return
        key = str(msg.note)

        if msg.type == "note_on" and msg.velocity > 0:
            if key not in self.pads:
                return
            cfg   = self.pads[key]
            fname = cfg if isinstance(cfg, str) else cfg.get("file", "")

            if fname == "stop_all":
                pygame.mixer.stop()
                print("[MUSIC] Stop all")
                return

            if key not in self.sounds:
                return

            sound, loop, base_vol = self.sounds[key]
            vel_factor = msg.velocity / 127
            sound.set_volume(min(1.0, base_vol * self.volume * vel_factor))

            ch = sound.play(loops=-1 if loop else 0)
            if ch:
                self.channels[key] = ch
            print(f"[MUSIC] ▶ {fname}  vel={msg.velocity}")

        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            cfg  = self.pads.get(key, {})
            loop = cfg.get("loop", False) if isinstance(cfg, dict) else False
            if loop and key in self.channels:
                self.channels[key].stop()
                print(f"[MUSIC] ■ stop loop note={key}")

    # ── Cleanup ────────────────────────────────────────────────────────────

    def stop(self):
        if PYGAME_OK and _mixer_init:
            pygame.mixer.stop()
