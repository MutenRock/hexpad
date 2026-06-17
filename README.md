# ⬡ HexPad v2

> Transforme ton **MPK Mini** ou tout contrôleur MIDI USB en gamepad, macros, contrôleur OBS, sampler, contrôleur HTTP/WebSocket, mini-synthé, visualizer et bien plus.

![platform](https://img.shields.io/badge/platform-Windows-blue)
![python](https://img.shields.io/badge/python-3.10%2B-a855f7)
![build](https://github.com/MutenRock/hexpad/actions/workflows/build.yml/badge.svg)

---

## 🚀 Téléchargement rapide

**→ [Releases](https://github.com/MutenRock/hexpad/releases)** — télécharge le dernier `.exe`, pas besoin de Python.

---

## Lancement recommandé

Sous Windows, double-clique sur :

```bat
launch.bat
```

Cela ouvre une **fenêtre de pré-lancement** avec 4 choix :

| Entrée | Usage |
|---|---|
| **Play Sound / Studio** | Branche l'Akai, choisis un preset, choisis la sortie audio, joue directement |
| **Simple Manette AKAI** | Détecte automatiquement le MPK/Akai et le transforme en manette vJoy |
| **HexPad complet** | Ouvre l'interface complète avec presets, mapping editor, OBS, HTTP, sampler, RGB... |
| **Debug / Test** | Ouvre une fenêtre séparée pour tester MIDI brut, AKAI/SysEx, HTTP et WebSocket |

---

## Lancer en local avec Python

```bat
git clone https://github.com/MutenRock/hexpad.git
cd hexpad
pip install -r requirements.txt
python launcher.py
```

Entrées directes possibles :

```bat
python studio_play.py             :: jouer du son directement
python simple_gamecontroller.py   :: mode manette automatique
python gui.py                     :: HexPad complet
python debug_test.py              :: tests séparés
```

Au premier lancement, HexPad crée automatiquement un `config.json` local si le fichier n'existe pas encore. Ce fichier est volontairement ignoré par git, car il contient tes réglages machine : nom du contrôleur MIDI, taille de fenêtre, thème, sortie audio, presets modifiés, OBS, etc.

Pour créer ou réparer manuellement la config :

```bat
python bootstrap_config.py
```

Pour repartir de zéro :

```bat
del config.json
python launcher.py
```

HexPad recréera une configuration propre depuis les valeurs par défaut.

---

## Mode Play Sound / Studio

`studio_play.py` est fait pour le cas simple : **je branche l'Akai et je veux m'amuser à faire du son**.

Fonctions incluses :

- auto-détection de l'input MIDI Akai / MPK ;
- choix de la sortie audio via `sounddevice` ;
- mini-synthé interne temps réel ;
- presets : `Piano Bell`, `Bass`, `Lead`, `Soft Pad`, `Drums` ;
- volume contrôlable depuis l'interface, et via CC1/CC7 si le contrôleur l'envoie ;
- boutons de lancement pour outils externes si installés : Carla, LMMS, VCV Rack, BespokeSynth ;
- lancement optionnel de FluidSynth avec un fichier `.sf2`.

Ce mode ne remplace pas un DAW complet : il sert de point d'entrée fun et rapide. Pour composer sérieusement, utilise plutôt LMMS/Ardour/Carla en complément.

---

## Mode Simple Manette AKAI

Le mode `simple_gamecontroller.py` est pensé pour jouer sans toucher au Mapping Editor :

- auto-détection AKAI / MPK / pad MIDI ;
- lancement automatique dès que le contrôleur est vu ;
- mapping direct vers vJoy device 1 ;
- pads 1-8 → boutons 1-8 ;
- joystick MPK pitch/mod → axes X/Y ;
- affichage clair : rouge = pas de pad, bleu = pad prêt, vert = manette active.

Pré-requis : vJoy doit être installé et actif pour que Windows voie la manette virtuelle.

---

## Debug / Test

`debug_test.py` regroupe les tests qui ne doivent pas polluer HexPad complet :

- **MIDI RAW** : écoute brute des notes, CC, pitchwheel et messages SysEx reçus ;
- **AKAI / SYSEX** : sortie MIDI, Identity Request, SysEx brut, test texte expérimental et test réel MPK Mini MK3 par preset RAM ;
- **HTTP** : requête GET/POST/PUT/PATCH/DELETE rapide ;
- **WebSocket** : connexion et envoi de message.

Pour tester l'écran/afficheur Akai MPK Mini MK3 :

1. Ouvre `Debug / Test`.
2. Onglet `AKAI / SYSEX` : choisis l'output Akai.
3. Dans `MPK Mini MK3 OLED - preset RAM`, clique `Envoyer preset RAM`.
4. Tourne un knob ou change de programme sur le MPK pour forcer l'affichage.
5. Clique ensuite `Envoyer noms knobs`, puis tourne les knobs K1-K8.

Note : ce test n'envoie pas un simple texte libre ; il envoie un preset RAM Akai complet. C'est le comportement actuellement le plus plausible pour le MPK Mini MK3.

---

## Modes disponibles dans HexPad complet

| Mode | Description |
|---|---|
| `gamepad` | Émule une manette vJoy : axes, boutons, pitchwheel/modwheel |
| `macro` | Lance des raccourcis clavier ou des séquences de touches |
| `obs` | Contrôle OBS Studio via obs-websocket v5 |
| `websocket` | Envoie des messages WebSocket custom |
| `http` | Envoie des requêtes HTTP GET/POST/PUT/PATCH/DELETE par pad |
| `sound_preset` | Sampler WAV/MP3/OGG par pad |
| `music` | Sampler musical avec volume global et choix de sortie audio |
| `lightfx` | Contrôle RGB via OpenRGB |
| `visualizer` | Visualiseur MIDI temps réel |
| `debug` | Affiche les messages MIDI bruts |

---

## Configuration

- `config.example.json` : template versionné, utile pour comprendre la structure.
- `config.json` : vraie config locale, générée automatiquement, ignorée par git.
- `modules/config_defaults.py` : valeurs par défaut utilisées par le bootstrap.

Extrait minimal :

```json
{
  "device_name": "MPK mini 3 0",
  "theme": "dark",
  "window_w": 520,
  "window_h": 820,
  "programs": {
    "1": { "name": "Gamepad", "mode": "gamepad" },
    "4": { "name": "Debug", "mode": "debug" }
  }
}
```

Si ton MPK apparaît sous un autre nom Windows, utilise `Debug / Test` ou le bouton `↺` dans HexPad complet.

---

## Build local développeur

```bat
build_exe.bat
```

Ou manuellement :

```bat
pip install -r requirements.txt
python assets/make_icon.py
pyinstaller hexpad.spec --noconfirm --clean
```

Le binaire est généré dans `dist/HexPad.exe`.

---

## Dépendances principales

- `mido` + `python-rtmidi` — MIDI
- `sounddevice` + `numpy` — mini-synthé Play Sound et choix de sortie audio
- `pyvjoy` — gamepad virtuel
- `pynput` — clavier/souris
- `obsws-python` — OBS WebSocket 5
- `pygame` + `sounddevice` — modes sampler/music
- `openrgb-python` — contrôle RGB
- `pyinstaller` — build `.exe`

---

## Dépannage rapide

**La fenêtre de pré-lancement ne s'ouvre pas**

```bat
python launcher.py 2>&1 | more
```

**Le mode Play Sound ne sort pas de son**

```bat
pip install sounddevice numpy
python studio_play.py
```

Vérifie ensuite que la bonne sortie audio est sélectionnée dans `Audio output`.

**La GUI complète ne se lance pas ou se ferme direct**

```bat
python gui.py 2>&1 | more
```

**Config JSON cassée après conflit git**

```bat
python bootstrap_config.py
```

Le fichier cassé sera sauvegardé en `config.backup-YYYYMMDD-HHMMSS.json`, puis une config propre sera recréée.

**vJoy non activé**

Le mode `gamepad` et le mode **Simple Manette AKAI** nécessitent vJoy installé et activé. Les autres modes peuvent fonctionner sans vJoy.

**OBS ne répond pas**

Ouvre OBS → Outils → obs-websocket → active le serveur WebSocket, port `4455`.
