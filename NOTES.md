# HexPad — Notes de développement

## Architecture actuelle (v2.0.0)

```
hexpad/
├── gui.py                       # GUI Tkinter v2.0.0 — point d'entrée unique
├── main.py                      # (legacy — utilise gui.py)
├── wizard.py                    # Mapping wizard interactif
├── config.json                  # programmes configurés
├── game_profiles.json           # profils jeu + combos
├── requirements.txt
├── hexpad.spec                  # PyInstaller one-file spec
├── version_info.txt             # métadonnées Windows exe
├── build_exe.bat                # build local → dist/HexPad.exe
├── .github/workflows/build.yml  # CI → Release automatique sur tag
├── assets/
│   ├── make_icon.py             # génère icon.ico (Pillow)
│   └── icon.ico                 # (généré, ignoré par git)
├── modules/
│   ├── midi_listener.py         # écoute MIDI (poll + stop propre)
│   ├── dispatcher.py            # router de messages
│   ├── gamepad.py               # gamepad vJoy (pads/knobs/joystick)
│   ├── websocket_bridge.py      # bridge WS pour jeux web JS
│   ├── macros.py                # macros clavier OS (pynput)
│   ├── obs_bridge.py            # OBS Studio (obs-websocket v5)
│   ├── http_bridge.py           # HTTP GET/POST par pad ← NEW
│   ├── lightfx_bridge.py        # RGB : OpenRGB / AlienFX
│   ├── visualizer_bridge.py     # visualiseur MIDI temps réel
│   ├── sound_preset_bridge.py   # sampler .wav/.mp3/.ogg (pygame)
│   ├── music_bridge.py          # player musical (pygame + sounddevice)
│   ├── game_profiles.py         # profils + combos
│   ├── combo_engine.py          # moteur de combos
│   └── themes.py                # palettes dark/light
├── presets/                     # SysEx MPK Mini
└── sounds/                      # samples pour le mode Sampler
```

## Flux de données

```
MPK Mini 3
    | (MIDI via rtmidi)
    v
MidiListener  <-- stop() via threading.Event
    |
    v
Dispatcher.handle(msg)
    |
    +-- GamepadBridge      → vJoy axes/buttons
    +-- WebSocketBridge    → JSON sur ws://
    +-- MacroBridge        → pynput keypress
    +-- OBSBridge          → obsws-python
    +-- HttpBridge         → GET/POST urllib  ← NEW
    +-- LightFXBridge      → OpenRGB SDK
    +-- VisualizerBridge   → Tkinter canvas
    +-- SoundPresetBridge  → pygame.mixer
    +-- MusicBridge        → pygame + sounddevice
    +-- [debug]            → print
```

## Roadmap

### Fait ✅
- [x] 3 modes fenêtre : COMPACT / NORMAL / WIDE
- [x] Mapping Editor complet (Bank A/B, tous modes)
- [x] Import / Export preset JSON
- [x] Bouton Refresh devices MIDI
- [x] Mode HTTP : GET/POST par pad (stdlib)
- [x] Mode Music (pygame + sounddevice)
- [x] Palette violet/bleu/blanc
- [x] Build PyInstaller one-file (`hexpad.spec`)
- [x] CI GitHub Actions → Release automatique
- [x] Icône multi-résolution générée via Pillow

### Court terme
- [ ] **Tray icon** — minimiser dans la barre système (pystray)
- [ ] **Auto-update** — vérification GitHub Releases API au démarrage
- [ ] **Mode Serial** — commandes série (Arduino, DMX…)
- [ ] **Mode MIDI out** — retransmettre/transformer vers autre device
- [ ] **Hotkey global** — START/STOP sans focus fenêtre (pynput)

### Moyen terme
- [ ] **Mode clip launcher** (type Ableton)
- [ ] **Mode OSC** — OpenSoundControl pour les DAW
- [ ] **Mode multi-device** — 2 MPK simultanés
- [ ] **Presets Cloud** — sync via GitHub Gist

### Long terme
- [ ] Frontend Electron + backend Python
- [ ] Support Linux / macOS
- [ ] Plugin DAW (VST3 wrapper)

## Dépendances

| Package | Usage |
|---------|-------|
| `mido[ports-rtmidi]` | Lecture MIDI |
| `python-rtmidi` | Backend MIDI natif |
| `pyvjoy` | Gamepad virtuel Windows |
| `websockets` | Bridge WebSocket |
| `pynput` | Macros clavier/souris |
| `obsws-python` | Contrôle OBS |
| `openrgb-python` | RGB via OpenRGB SDK |
| `pygame` | Sampler + Music audio |
| `sounddevice` | Sélection device audio |
| `Pillow` | Génération icône |
| `pyinstaller>=6.0` | Build .exe standalone |

## Notes setup

**vJoy**
- Driver : https://github.com/jshafer817/vJoy/releases
- Config : vJoyConf.exe → 8 boutons + axes X/Y/Z/Rx/Ry/Rz/Sl0/Sl1

**OpenRGB**
- App : https://openrgb.org
- Activer SDK Server : Settings > SDK Server (port 6742)

**OBS**
- obs-websocket inclus dans OBS 28+
- Activer : Outils > obs-websocket (port 4455)

**Mode HTTP**
- Aucune dépendance externe — stdlib `urllib` uniquement
- Idéal pour Home Assistant, Philips Hue, n8n, serveurs locaux
- Timeout configurable par preset (`http_timeout`, défaut 3s)

**Sampler / Music**
- Créer dossier `sounds/` à la racine
- Formats : .wav, .mp3, .ogg
- Samples libres : https://freesound.org
