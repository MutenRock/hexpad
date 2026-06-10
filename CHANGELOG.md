# Changelog

## [1.3.0] - 2026-06-10

### Ajouté
- `modules/obs_bridge.py` — mode OBS : changer de scène, mute micro, toggle stream/record/source via obs-websocket v5
- `build_exe.bat` — génère `dist/HexPad.exe` standalone via PyInstaller
- **MIDI Learn** dans le preset editor — clic sur ◎ puis appuie sur un pad pour capturer la note
- **Live pad feedback** — les pads du monitor s'allument en couleur (intensité = vélocité) à chaque frappe
- **Sélecteur Bank A / Bank B** dans le preset editor (notes 36-43 vs 44-51)
- Config `programme 5 : OBS` ajoutée dans `config.json`
- `requirements.txt` mis à jour : `obsws-python`, `pyinstaller`

### Corrigé
- **Stop propre** : `MidiListener` utilise maintenant `port.poll()` + `threading.Event`, le STOP dans la GUI arrête réellement le thread
- Fermeture de fenêtre propre (`WM_DELETE_WINDOW` hookée)

## [1.2.0] - 2026-06-10
### Ajouté
- GUI 2 colonnes avec preset editor visuel (pads, knobs, joystick)
- Boutons sauvegarder / nouveau / supprimer preset
- Couleurs par mode

## [1.1.0] - 2026-06-10
### Ajouté
- `gui.py` Tkinter, `wizard.py`, `launch_gui.bat`
- Support pitchwheel + modwheel dans gamepad.py

## [1.0.0] - 2026-06-10
### Ajouté
- Modes Gamepad, WebSocket, Macros, Debug
- 4 programmes configurables, fichiers .bat Windows
