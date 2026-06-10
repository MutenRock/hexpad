# Presets MPK Mini MK3

Ce dossier contient des presets **SysEx** prêts à envoyer au MPK Mini MK3.
Chaque fichier est un message SysEx binaire (`F0 47 7F 7C 61 ...`).

## Presets disponibles

| Fichier | Description |
|---------|-------------|
| `Preset1-Chromatic` | Pads chromatiques depuis note 36 (C2) |
| `Preset2-WhiteKeys` | Touches blanches uniquement (gamme C majeure) |
| `Preset3-MPC` | Disposition MPC classique (kick, snare, hi-hat...) |
| `Preset4-ChromaticFrom60` | Pads chromatiques depuis note 60 (C4, Do central) |

## Envoyer un preset au MPK Mini

### Via Python (mido)

```python
import mido

# Lire le fichier preset (octets séparés par espaces)
with open('presets/Preset1-Chromatic', 'r') as f:
    data = list(map(int, f.read().split()))

# Envoyer en SysEx
with mido.open_output('MPK mini 3 0') as port:
    msg = mido.Message.from_bytes(data)
    port.send(msg)
    print('Preset envoyé !')
```

### Via le MPK Mini Editor (Akai officiel)
Importe le fichier `.mk3` ou envoie le SysEx depuis ton DAW.

## Décodage SysEx MPK Mini MK3

```
F0 47 7F 7C 61 00 [len_hi] [len_lo] [prog_num] ...
  00 04 [tempo_hi] [tempo_lo]   <- BPM
  00 05 [time_div]              <- Division temporelle
  00 03 [arp_mode]              <- Mode arpégiateur
  [pad_index] [note] [pc]       <- Mapping pad -> note
  [cc_index] [cc_val] [toggle]  <- Mapping encodeur -> CC
F7
```
