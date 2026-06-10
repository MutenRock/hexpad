# HexPad 🎹

> **Akai MPK Mini Cyber Controller Manager** — gamepad virtuel, WebSocket bridge, macros OS.

![Python](https://img.shields.io/badge/Python-3.8+-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![Sterenna](https://img.shields.io/badge/by-Sterenna%20EI-purple)

## Projets de référence

- [c0redumb/midi2vjoy](https://github.com/c0redumb/midi2vjoy) — MIDI → vJoy mapping
- [pepitooo/midi2vjoy](https://github.com/pepitooo/midi2vjoy) — version JSON-config simplifiée
- [oscaracena/mdevtk](https://github.com/oscaracena/mdevtk) — Python MIDI device toolkit

## Installation

```bash
git clone https://github.com/MutenRock/hexpad.git
cd hexpad
pip install -r requirements.txt
```

> Mode Gamepad : installe aussi le driver [vJoy](https://github.com/jshafer817/vJoy/releases).

## Lancement

Double-clique sur **`launch.bat`** ou :

```bash
python main.py --mode debug      # Voir les messages MIDI
python main.py --program 1       # Gamepad (vJoy)
python main.py --program 2       # WebSocket bridge
python main.py --program 3       # Macros clavier OS
```

## Configuration

Édite `config.json` :

```json
{
  "device_name": "MPK mini 3",
  "programs": {
    "1": {
      "mode": "gamepad",
      "pads":  { "36": "btn_1", "37": "btn_2" },
      "knobs": { "70": "axis_x", "71": "axis_y" }
    },
    "2": { "mode": "websocket", "ws_url": "ws://localhost:8765" },
    "3": { "mode": "macro", "pads": { "36": "ctrl+z", "37": "ctrl+s" } }
  }
}
```

## Architecture

```
hexpad/
├── main.py
├── config.json
├── requirements.txt
├── launch.bat / install.bat / launch_*.bat
└── modules/
    ├── midi_listener.py       # Écoute MIDI (mido + rtmidi)
    ├── dispatcher.py          # Router de messages
    ├── gamepad.py             # Gamepad virtuel (pyvjoy + vJoy)
    ├── websocket_bridge.py    # Bridge WebSocket (jeux web JS)
    └── macros.py              # Macros clavier OS (pynput)
```

## WebSocket — Intégration JS

```javascript
const ws = new WebSocket('ws://localhost:8765');
ws.onmessage = (e) => {
  const { type, note, control, value } = JSON.parse(e.data);
  if (type === 'note_on')        handlePad(note, value);
  if (type === 'control_change') handleKnob(control, value);
};
```

## Tables MIDI MPK Mini MK3

| Pad | Bank A | Bank B |   | Encodeur | CC |
|-----|--------|--------|---|----------|----|
| 1   | 36     | 44     |   | K1       | 70 |
| 2   | 37     | 45     |   | K2       | 71 |
| 3   | 38     | 46     |   | K3       | 72 |
| 4   | 39     | 47     |   | K4       | 73 |
| 5   | 40     | 48     |   | K5       | 74 |
| 6   | 41     | 49     |   | K6       | 75 |
| 7   | 42     | 50     |   | K7       | 76 |
| 8   | 43     | 51     |   | K8       | 77 |

---
*Made with 🎹 by [Sterenna EI](https://github.com/MutenRock)*
