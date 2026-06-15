# Changelog — HexPad

## v2.0.0 — 2026-06-15

### Nouveau module
- `modules/http_bridge.py` — bridge HTTP GET/POST par pad
  - stdlib urllib uniquement (pas de dépendance externe)
  - Fire-and-forget async (thread daemon par pad)
  - Supporte `method`, `url`, `body` (JSON auto-sérialisé), `headers` custom
  - `http_timeout` configurable (défaut 3s)
  - `test_pad()` déclenche manuellement depuis la GUI
  - `last_status()` expose le dernier code HTTP reçu

### GUI v2.0.0
- **Import preset** — charge un `.json` dans le slot courant ou un nouveau slot
- **Export preset** — sauvegarde le preset courant en `.json`
- **Refresh devices** — bouton `↺` dans la device row, rafraîchit la liste MIDI sans redémarrer
- **Mode HTTP dans l'éditeur** — champs method (GET/POST/PUT…) + URL + body JSON par pad
- **Validation HTTP** — erreur si une URL de pad est vide avant sauvegarde
- Flash pad : accent violet (cohérent avec la palette v1.7.0)
- `sel_fg` utilisé systématiquement pour le texte des boutons preset sélectionnés
- Import `filedialog` ajouté
- `_build_bridge()` route `mode=="http"` → `HttpBridge`

### Build & Distribution
- `hexpad.spec` — spec PyInstaller one-file, sans console, icon, version info Windows
- `version_info.txt` — métadonnées Windows intégrées dans l'exe
- `assets/make_icon.py` — génère `icon.ico` multi-résolution via Pillow
- `build_exe.bat` — script build complet avec vérifications
- `.github/workflows/build.yml` — CI GitHub Actions, release automatique sur tag `v*.*.*`

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
- `modules/music_bridge.py` — nouveau module (pygame + sounddevice)
- Flash pad : couleur accent violet
- `config.json` : ajout `"theme": "dark"` et `"window_mode": "NORMAL"`

## v1.6.x — antérieur
- 3 modes fenêtre : COMPACT / NORMAL / WIDE
- Bridges : gamepad, macro, OBS, WebSocket, LightFX, Visualizer, Sampler
- Profils de jeu + moteur de combos
