# ⬡ HexPad v2

> Transforme ton **MPK Mini** (ou tout contrôleur MIDI USB) en gamepad, macros, contrôleur OBS, sampler et bien plus.

![platform](https://img.shields.io/badge/platform-Windows-blue)
![python](https://img.shields.io/badge/python-3.10%2B-a855f7)
![build](https://github.com/MutenRock/hexpad/actions/workflows/build.yml/badge.svg)

---

## 🚀 Téléchargement rapide

**→ [Releases](https://github.com/MutenRock/hexpad/releases)** — télécharge le dernier `.exe`, pas besoin de Python.

---

## Modes disponibles

| Mode | Description |
|---|---|
| `gamepad` | Émule une manette vJoy (axes + boutons) |
| `macro` | Lance des raccourcis clavier |
| `obs` | Contrôle OBS Studio (scènes, mute, stream…) |
| `websocket` | Envoie des messages WebSocket custom |
| `sound_preset` | Sampler WAV par pad |
| `music` | Player musical avec volume + device audio |
| `lightfx` | Contrôle RGB via OpenRGB |
| `visualizer` | Visualiseur MIDI temps réel |
| `debug` | Affiche les messages MIDI bruts |

---

## 🛠 Build local (développeurs)

```bat
:: Windows
build_exe.bat
```

Ou manuellement :
```bat
pip install -r requirements.txt
python assets/make_icon.py
pyinstaller hexpad.spec --noconfirm --clean
```

Le binaire est dans `dist/HexPad.exe`.

---

## Configuration

Edite `config.json` directement ou utilise le **Mapping Editor** intégré (mode NORMAL ou WIDE).

```json
{
  "device_name": "MPK mini 3 0",
  "theme": "dark",
  "window_mode": "NORMAL",
  "programs": { ... }
}
```

---

## Lancer sans exe (Python)

```bat
pip install -r requirements.txt
python gui.py
```

---

## Dépendances

- `mido` + `python-rtmidi` — MIDI
- `pyvjoy` — gamepad virtuel
- `pynput` — clavier/souris
- `obsws-python` — OBS WebSocket 5
- `pygame` + `sounddevice` — audio
- `openrgb-python` — RGB
- `Pillow` — génération icône
- `pyinstaller` — build exe
