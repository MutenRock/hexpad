# Changelog

## [1.4.0] - 2026-06-10

### Ajouté
- `modules/lightfx_bridge.py` — Mode **RGB** : controle couleurs/effets OpenRGB ou AlienFX
  - Actions : `color` (R/G/B), `effect` (breathing/rainbow/static), `off`
  - Backend configurable : `openrgb` | `lightfx`
- `modules/visualizer_bridge.py` — Mode **Visualizer** : fenetre Tkinter ~30fps
  - Barres de velocite des 8 pads avec fade progressif
  - Piano roll notes actives
  - Historique CC (encodeurs/joystick)
- `modules/sound_preset_bridge.py` — Mode **Sampler** : .wav/.mp3/.ogg via pygame
  - Volume dynamique selon velocite MIDI
  - Support loops (stop sur note_off)
  - Pad `stop_all` pour couper tous les canaux
- `config.json` : presets 6 (RGB), 7 (Visualizer), 8 (Sampler)
- `requirements.txt` : + `openrgb-python`, `pygame`
- `NOTES.md` : architecture, flux de donnees, ideas futures, notes setup
- `sounds/.gitkeep` : dossier versionne pour les samples

## [1.3.0] - 2026-06-10
### Ajouté
- Stop propre MidiListener (poll + Event)
- `modules/obs_bridge.py` (OBS scenes/mute/stream/record)
- MIDI Learn, live pad feedback, Bank A/B dans la GUI
- `build_exe.bat` PyInstaller

## [1.2.0] - 2026-06-10
### Ajouté
- GUI 2 colonnes avec preset editor visuel

## [1.1.0] - 2026-06-10
### Ajouté
- `gui.py`, `wizard.py`, `launch_gui.bat`
- Support pitchwheel + modwheel

## [1.0.0] - 2026-06-10
### Ajouté
- Modes Gamepad, WebSocket, Macros, Debug
- 4 programmes configurables, fichiers .bat Windows
