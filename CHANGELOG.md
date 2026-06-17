# Changelog — HexPad

## v2.3.1 — 2026-06-17

### AKAI / SysEx debug
- `debug_test.py` ajoute un onglet `AKAI / SYSEX`.
- Selection d'output MIDI separee de l'input MIDI RAW.
- Bouton `Identity Request` pour verifier la sortie MIDI et observer une reponse dans MIDI RAW.
- Envoi de SysEx brut en hexadecimal (`F0 ... F7`).
- Test texte experimental avec header configurable pour explorer le controle de l'ecran/afficheur Akai sans hardcoder un protocole non verifie.

---

## v2.3.0 — 2026-06-17

### Simplification UX
- `launcher.py` — nouvelle fenêtre de pré-lancement avec trois entrées : Simple Manette AKAI, HexPad complet, Debug/Test.
- `launch.bat` ouvre maintenant le pré-lanceur au lieu de lancer directement la GUI complète.
- `simple_gamecontroller.py` — mode simple dédié : auto-détecte AKAI/MPK, lance vJoy gamecontroller automatiquement, pads 1-8 vers boutons 1-8, joystick MPK vers axes X/Y.
- `debug_test.py` — fenêtre séparée pour MIDI raw monitor, HTTP test et WebSocket test.

### Gamepad fix
- `modules/gamepad.py` expose désormais `on_note`, `on_cc` et `on_pitchwheel`, compatibles avec `Dispatcher v2`.
- `stop()` relâche les boutons vJoy mappés à l'arrêt.

---

## v2.2.3 — 2026-06-17

### Device presence UX
- `sitecustomize.py` surveille maintenant les entrées MIDI pendant que la GUI tourne.
- Si un MPK/pad est branché, le device est sélectionné automatiquement dans la première combobox.
- Le point de statut passe en bleu quand un pad est détecté mais que le mode n'est pas encore lancé.
- Le bouton START affiche `PAD READY` ou `NO PAD` pour éviter l'ambiguïté.

---

## v2.2.2 — 2026-06-17

### Fix Windows encoding
- `modules/config_defaults.py` réécrit désormais toujours `config.json` en JSON ASCII-safe (`ensure_ascii=True`).
- Évite l'erreur Windows `charmap codec can't decode byte ...` quand un ancien chemin lit la config sans encodage explicite.
- Le bootstrap tente aussi une lecture `cp1252` en fallback avant de sauvegarder/régénérer une config cassée.

---

## v2.2.1 — 2026-06-17

### Config bootstrap
- `modules/config_defaults.py` — valeurs par défaut centralisées pour générer une configuration locale complète.
- `sitecustomize.py` — bootstrap automatique : `python gui.py` crée désormais un `config.json` local si absent.
- `bootstrap_config.py` — commande explicite pour créer/réparer la config locale.
- `config.example.json` — template versionné, séparé du vrai `config.json` local.
- `.gitignore` — ignore aussi les backups `config.backup*.json`.

### Comportement
- Si `config.json` est absent : création automatique depuis les defaults.
- Si `config.json` est invalide : sauvegarde en `config.backup-YYYYMMDD-HHMMSS.json`, puis régénération propre.
- Si `config.json` est ancien mais valide : ajout uniquement des clés manquantes, sans écraser les réglages utilisateur.

### Documentation
- README mis à jour avec lancement local, bootstrap config, reset config et dépannage rapide.

---

## v2.2.0 — 2026-06-15

### GUI
- Fenêtre unique redimensionnable.
- Mapping Editor déplacé en fenêtre dédiée via le bouton `⚙ Mapping`.
- Console rétractable avec toggle `▾/▸ Console`.
- Panneau `TEST` intégré via notebook : MIDI monitor, HTTP, WebSocket et Bridges.
- Sauvegarde silencieuse de la taille de fenêtre (`window_w`, `window_h`).
- Version interne GUI : `VERSION = "2.2.0"`.

---

## v2.1.0 — 2026-06-15

### Stabilisation interface
- Consolidation des modes fenêtre et du Mapping Editor après la branche v2.0.
- Amélioration du workflow de test sans relancer l'application.
- Préparation de l'interface v2.2 avec console rétractable et panneaux de diagnostic.

---

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
