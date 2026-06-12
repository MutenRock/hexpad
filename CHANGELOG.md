# Changelog

## [1.5.0] - 2026-06-12

### Ajouté
- `modules/game_profiles.py` — Gestionnaire de profils par jeu
  - Charge/sauvegarde `game_profiles.json`
  - Switch de profil à chaud depuis la GUI
  - Chaque profil : nom, description, programme lié, combos
  - API : `profiles.active`, `get_combos()`, `set_combo()`, `add_profile()`
- `modules/combo_engine.py` — Moteur de macros / combos complexes
  - Format token : `j,k,l` (séquentiel), `j+k` (simultané), `50` (délai ms)
  - Touches spéciales : `space`, `enter`, `esc`, `f1-f12`, `ctrl`, `comma`...
  - Thread dédié par combo, interruptible via `stop()`
  - Support `loop=true` pour les combos répétitifs
- `game_profiles.json` — 3 profils prêts à l'emploi
  - **2XKO** (profil actif) : BnB Light/Heavy, Super S1/S2, Dash, Tag Combo, BnB Extend, Wake Up Super
  - **SF6** : Drive Rush, Drive Impact, Drive Parry, SA1, SA2, BnB Modern, Throw, OD Special
  - **Custom** : profil vide à personnaliser
- `gui.py` v1.5.0
  - Sélecteur **GAME PROFILE** avec description inline (colonne gauche)
  - Boutons **COMBOS** générés dynamiquement depuis le profil actif
  - Hint token macro visible dans le Preset Editor
  - Bouton **+ NEW** / **×** pour créer/supprimer des profils
  - `combo_engine.stop()` appelé à la fermeture de fenêtre

## [1.4.1] - 2026-06-12
### Ajouté
- Preset 9 **2XKO** (mode macro, layout leverless)

## [1.4.0] - 2026-06-10
### Ajouté
- `modules/lightfx_bridge.py`, `visualizer_bridge.py`, `sound_preset_bridge.py`
- Presets 6 (RGB), 7 (Visualizer), 8 (Sampler)
- `NOTES.md`, `sounds/.gitkeep`

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
