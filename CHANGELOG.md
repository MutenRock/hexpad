# Changelog

## [1.1.0] - 2026-06-10

### Ajouté
- `gui.py` — interface graphique Tkinter cyber (sélecteur de programme, console, start/stop)
- `wizard.py` — mapping wizard interactif : capture tes touches en direct et génère config.json
- `launch_gui.bat` — raccourci double-clic pour la GUI
- Support `pitchwheel` dans `gamepad.py` (joystick gauche/droite -> axe vJoy)
- Support `modwheel` (CC1, joystick haut/bas) dans `gamepad.py`
- Config `pitchwheel` et `modwheel` dans config.json programme 1

### Corrigé
- `gamepad.py` : crash vJoy géré proprement (message d'erreur + lien driver)
- `config.json` : device_name corrigé en `MPK mini 3 0`
- `midi_listener.py` : auto-detect partiel du nom de device

## [1.0.0] - 2026-06-10

### Ajouté
- Mode Gamepad (pyvjoy + vJoy)
- Mode WebSocket bridge
- Mode Macros OS (pynput)
- Mode Debug MIDI
- 4 programmes configurables
- Fichiers .bat Windows
