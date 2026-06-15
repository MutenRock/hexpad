# Changelog — HexPad

## v1.9.0 — 2026-06-15
- Mapping Editor complet : layout physique MPK 2×4, Bank A/B éditables
- Champs contextuels par mode (gamepad / macro / obs / sampler / websocket / music)
- Noms de notes MIDI (C2, D#3…) affichés sur les pads
- OBS : champs action + scene/source/hotkey
- Sampler/Music : champs file / volume / loop par pad
- Validation basique avant sauvegarde
- Nouveau preset mode `music` dans config.json

## v1.7.0 — 2026-06-14
- Palette violet / bleu / blanc (`accent #a855f7`, `accent2 #3b82f6`, `text #ffffff`)
- `sel_fg #000000` — texte noir sur bouton preset sélectionné (dark) / blanc (light)
- `MODE_COLORS` mis à jour + entrée `music: #8b5cf6`
- `modules/music_bridge.py` — nouveau module (pygame + sounddevice)
  - `list_output_devices()` — liste les sorties audio système
  - `set_volume()` à chaud
  - Sérialise `music_volume` + `music_device` dans config
- `gui.py` : route `mode=="music"` → `MusicBridge`
- Flash pad : couleur accent violet au lieu du vert
- Champs connexion music : slider Volume + combobox Device
- `config.json` : ajout `"theme": "dark"` et `"window_mode": "NORMAL"`

## v1.6.x — antérieur
- 3 modes fenêtre : COMPACT / NORMAL / WIDE
- PanedWindow en mode NORMAL, 3 colonnes en WIDE
- Mode persisté dans `config.json → window_mode`
- Dialogue de sélection de mode au lancement
- Bouton bascule thème clair/sombre
- Profils de jeu + moteur de combos
- Bridges : gamepad, macro, OBS, WebSocket, LightFX, Visualizer, Sampler
