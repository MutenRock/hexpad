#!/usr/bin/env python3
"""
Envoie un preset SysEx au MPK Mini MK3.

Usage:
    python presets/send_preset.py presets/Preset1-Chromatic
    python presets/send_preset.py presets/Preset3-MPC --device "MPK mini 3 0"
"""
import mido, argparse, sys

def list_outputs():
    print("[SYSEX] Sorties MIDI disponibles :")
    for name in mido.get_output_names():
        print(f"  - {name}")

def auto_detect():
    for name in mido.get_output_names():
        if any(x in name.lower() for x in ("mpk", "mini", "akai")):
            return name
    return None

def send(preset_file, device=None):
    list_outputs()
    target = device or auto_detect()
    if not target:
        print("[SYSEX] Aucun MPK d\u00e9tect\u00e9. Sp\u00e9cifie --device.")
        sys.exit(1)
    with open(preset_file, "r") as f:
        data = list(map(int, f.read().split()))
    print(f"[SYSEX] Envoi de {preset_file} -> {target}")
    with mido.open_output(target) as port:
        port.send(mido.Message.from_bytes(data))
    print("[SYSEX] Preset envoy\u00e9 !")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Envoie un preset SysEx au MPK Mini")
    parser.add_argument("preset", help="Chemin vers le fichier preset")
    parser.add_argument("--device", default=None, help="Nom du device MIDI de sortie")
    args = parser.parse_args()
    send(args.preset, args.device)
