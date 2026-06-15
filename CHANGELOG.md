# Changelog — HexPad

## v2.0.0 — 2026-06-15

### Build & Distribution
- `hexpad.spec` — spec PyInstaller one-file, sans console, avec icône, version info Windows
- `version_info.txt` — métadonnées Windows (FileVersion, ProductName, Copyright)
- `assets/make_icon.py` — génère `icon.ico` multi-résolution (256/128/64/48/32/16px) via Pillow
  - Hexagone violet `#a855f7` + inner hex fond sombre + accent bleu `#3b82f6`
- `build_exe.bat` — script build amélioré : vérif Python, install deps, génération icône, clean, build, affiche taille
- `requirements.txt` — ajout Pillow, pin `pyinstaller>=6.0`

### CI/CD GitHub Actions
- `.github/workflows/build.yml` — pipeline automatique :
  - Trigger sur tag `v*.*.*` ou `workflow_dispatch`
  - Runner `windows-latest`, Python 3.11, cache pip
  - Build → artifact nommé `HexPad-{tag}-windows.exe`
  - Création automatique de GitHub Release avec notes générées

### Documentation
- `README.md` — refondu : badge build CI, tableau des modes, instructions build, config

---

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
- Flash pad : couleur accent violet au lieu du vert
- `config.json` : ajout `"theme": "dark"` et `"window_mode": "NORMAL"`

## v1.6.x — antérieur
- 3 modes fenêtre : COMPACT / NORMAL / WIDE
- PanedWindow en mode NORMAL, 3 colonnes en WIDE
- Bridges : gamepad, macro, OBS, WebSocket, LightFX, Visualizer, Sampler
- Profils de jeu + moteur de combos
