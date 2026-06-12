# Changelog

## [1.4.1] - 2026-06-12

### Ajouté
- `config.json` : preset 9 **2XKO** (mode macro, layout leverless optimisé)
  - **Bank A — Combat (8 pads)**
    - P1 `j` → Light Attack (L)
    - P2 `k` → Medium Attack (M)
    - P3 `l` → Heavy Attack (H)
    - P4 `i` → Throw (L+M)
    - P5 `m` → Special 1
    - P6 `u` → Parry
    - P7 `space` → Dash
    - P8 `o` → Break
  - **Bank B — Utilitaires + Mouvement**
    - P1 `p` → Ultimate
    - P2 `,` → Special 2
    - P3 `.` → Tag/Team
    - P4 `r` → Taunt
    - P5 `a` → Move Left
    - P6 `d` → Move Right
    - P7 `w` → Jump
    - P8 `s` → Crouch
  - Contrôles in-game à recaler sur ces touches dans Settings > Controls > Edit Controls

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
