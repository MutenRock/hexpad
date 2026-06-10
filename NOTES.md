# HexPad — Notes de développement

## Architecture actuelle

```
hexpad/
├── main.py
├── gui.py                      # GUI Tkinter v1.3
├── wizard.py                   # Mapping wizard interactif
├── config.json                 # 8 programmes configures
├── requirements.txt
├── build_exe.bat               # PyInstaller -> dist/HexPad.exe
├── modules/
│   ├── midi_listener.py         # Ecoute MIDI (poll + stop propre)
│   ├── dispatcher.py            # Router de messages
│   ├── gamepad.py               # Gamepad vJoy (pads/knobs/joystick)
│   ├── websocket_bridge.py      # Bridge WS pour jeux web JS
│   ├── macros.py                # Macros clavier OS (pynput)
│   ├── obs_bridge.py            # OBS Studio (obs-websocket v5)
│   ├── lightfx_bridge.py        # RGB : OpenRGB / AlienFX
│   ├── visualizer_bridge.py     # Visualiseur MIDI temps reel
│   └── sound_preset_bridge.py   # Sampler .wav/.mp3/.ogg (pygame)
├── presets/                    # SysEx MPK Mini (send_preset.py)
└── sounds/                     # Samples pour le mode Sampler
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
    +-- GamepadBridge      -> vJoy axes/buttons
    +-- WebSocketBridge    -> JSON sur ws://
    +-- MacroBridge        -> pynput keypress
    +-- OBSBridge          -> obsws-python
    +-- LightFXBridge      -> OpenRGB SDK
    +-- VisualizerBridge   -> Tkinter canvas
    +-- SoundPresetBridge  -> pygame.mixer
    +-- [debug]            -> print
```

## Ideas futures

### Court terme
- [ ] Mode **combo** : un pad declenche plusieurs bridges
- [ ] **Import/export preset JSON** depuis la GUI
- [ ] **Auto-update** via GitHub Releases API
- [ ] Icone `.ico` + splash screen PyInstaller

### Moyen terme
- [ ] Mode **HTTP** : GET/POST sur chaque pad
- [ ] Mode **Serial** : commandes serie (Arduino, DMX...)
- [ ] Mode **MIDI out** : retransmettre/transformer vers autre device
- [ ] Mode **clip launcher** (type Ableton)

### Long terme
- [ ] Frontend Electron + backend Python
- [ ] Support OSC pour les DAW
- [ ] Mode multi-device (2 MPK simultanes)

## Dépendances

| Package | Usage |
|---------|-------|
| `mido[ports-rtmidi]` | Lecture MIDI |
| `python-rtmidi` | Backend MIDI natif |
| `pyvjoy` | Gamepad virtuel Windows |
| `websockets` | Bridge WebSocket |
| `pynput` | Macros clavier/souris |
| `obsws-python` | Controle OBS |
| `openrgb-python` | RGB via OpenRGB SDK |
| `pygame` | Sampler audio |
| `pyinstaller` | Build .exe standalone |

## Notes setup

**vJoy**
- Driver : https://github.com/jshafer817/vJoy/releases
- Config : vJoyConf.exe -> 8 boutons + axes X/Y/Z/Rx/Ry/Rz/Sl0/Sl1

**OpenRGB**
- App : https://openrgb.org
- Activer SDK Server : Settings > SDK Server (port 6742)

**OBS**
- obs-websocket inclus dans OBS 28+
- Activer : Outils > obs-websocket (port 4455)

**Sampler**
- Creer dossier `sounds/` a la racine
- Formats : .wav, .mp3, .ogg
- Samples libres : https://freesound.org
