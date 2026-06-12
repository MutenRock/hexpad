# Changelog

## [1.6.0] - 2026-06-12

### Ajouté
- `modules/themes.py` — palettes Dark et Light découplées du GUI
  - `DARK` : thème original cyan/violet/noir
  - `LIGHT` : thème clair bleu/gris/blanc, mêmes accents
  - `get(name)` pour switch dynamique
- `gui.py` v1.6.0 — refonte **compact widget style**
  - Taille fixe 420×580 px, verticale
  - **Header** : logo + version + toggle thème `☀/◐` + minimise + close
  - **Ligne device/profil** : device combobox + game profile + bouton `⚙` éditeur
  - **Programme pills** : boutons compacts colorés par mode, scrollables
  - **PAD Monitor** : grille 4×2 compacte avec flash vélocité couleur
  - **COMBOS** : boutons 2 colonnes générés depuis le profil actif
  - **START/STOP** pleine largeur
  - **Console** inline 4 lignes
  - **Toggle thème** persisté dans `config.json` → `"theme": "dark"|"light"`
  - **Preset Editor** → fenêtre séparée (Toplevel) via bouton `⚙`, ne pollue plus le widget

### Modifié
- Preset Editor déplacé dans `_build_editor()` / `Toplevel` — ne s'ouvre qu'à la demande
- Pad/Knob grids maintenant dans la fenêtre éditeur uniquement

## [1.5.0] - 2026-06-12
### Ajouté
- `modules/game_profiles.py`, `modules/combo_engine.py`, `game_profiles.json`
- GUI v1.5.0 : sélecteur de profil + boutons combos dynamiques + hint token macro

## [1.4.1] - 2026-06-12
### Ajouté
- Preset 9 **2XKO** (mode macro, layout leverless)

## [1.4.0] - 2026-06-10
### Ajouté
- `modules/lightfx_bridge.py`, `visualizer_bridge.py`, `sound_preset_bridge.py`
- Presets 6 (RGB), 7 (Visualizer), 8 (Sampler)

## [1.3.1] - 2026-06-10
### Corrigé
- `gui.py` : AttributeError `preset_name_var` au démarrage

## [1.3.0] - 2026-06-10
### Ajouté
- Stop propre MidiListener, `obs_bridge.py`, MIDI Learn, Bank A/B, `build_exe.bat`

## [1.2.0] - 2026-06-10
### Ajouté
- GUI 2 colonnes avec preset editor visuel

## [1.1.0] - 2026-06-10
### Ajouté
- `gui.py`, `wizard.py`, pitchwheel/modwheel

## [1.0.0] - 2026-06-10
### Ajouté
- Modes Gamepad, WebSocket, Macros, Debug
