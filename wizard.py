#!/usr/bin/env python3
"""
HexPad Mapping Wizard
=====================
Capture interactive de tes touches/encodeurs MPK Mini
et génération automatique de config.json.

Usage:
    python wizard.py
"""
import mido, json, time, os

PROGRAM_MODES = ["gamepad", "websocket", "macro", "debug"]
BTN_NAMES  = [f"btn_{i}" for i in range(1, 17)]
AXIS_NAMES = ["axis_x", "axis_y", "axis_z", "axis_rx", "axis_ry", "axis_rz", "axis_sl0", "axis_sl1"]
MACRO_EXAMPLES = ["ctrl+z", "ctrl+s", "ctrl+c", "f5", "esc", "space"]

def pick_device():
    devices = mido.get_input_names()
    if not devices:
        print("[WIZARD] Aucun appareil MIDI détecté.")
        exit(1)
    if len(devices) == 1:
        print(f"[WIZARD] Appareil détecté : {devices[0]}")
        return devices[0]
    print("[WIZARD] Appareils disponibles :")
    for i, d in enumerate(devices):
        print(f"  [{i}] {d}")
    idx = int(input("Choix : "))
    return devices[idx]

def wait_for_message(port, timeout=10):
    """Attend un message MIDI et le retourne."""
    start = time.time()
    for msg in port:
        if msg.type in ("note_on", "control_change", "pitchwheel") and time.time() - start < timeout:
            if msg.type == "note_on" and msg.velocity == 0:
                continue
            return msg
        if time.time() - start >= timeout:
            return None

def wizard_program(port, prog_num):
    print(f"\n{'='*40}")
    print(f" Programme {prog_num}")
    print(f"{'='*40}")
    mode = input(f" Mode ? ({'/'.join(PROGRAM_MODES)}) [debug] : ").strip() or "debug"
    prog = {"mode": mode}

    if mode == "websocket":
        prog["ws_url"] = input(" WebSocket URL [ws://localhost:8765] : ").strip() or "ws://localhost:8765"
        return prog

    if mode == "debug":
        return prog

    pads  = {}
    knobs = {}

    # Capture pads
    n_pads = int(input(" Combien de pads à mapper ? [8] : ").strip() or "8")
    for i in range(1, n_pads + 1):
        target = input(f"  Pad {i} -> ({'/'.join(BTN_NAMES[:8])} ou macro ex ctrl+s) : ").strip()
        print(f"  >>> Appuie sur le pad {i} maintenant...")
        msg = wait_for_message(port)
        if msg and msg.type == "note_on":
            pads[str(msg.note)] = target
            print(f"      Capturé : note {msg.note} -> {target}")
        else:
            print("      Timeout, pad ignoré.")
    if pads:
        prog["pads"] = pads

    # Capture encodeurs
    n_knobs = int(input(" Combien d'encodeurs à mapper ? [0] : ").strip() or "0")
    for i in range(1, n_knobs + 1):
        target = input(f"  Encodeur {i} -> ({'/'.join(AXIS_NAMES[:4])}) : ").strip()
        print(f"  >>> Tourne l'encodeur {i} maintenant...")
        msg = wait_for_message(port)
        if msg and msg.type == "control_change":
            knobs[str(msg.control)] = target
            print(f"      Capturé : CC {msg.control} -> {target}")
        else:
            print("      Timeout, encodeur ignoré.")
    if knobs:
        prog["knobs"] = knobs

    # Joystick
    use_joy = input(" Mapper le joystick ? (pitchwheel + modwheel) [o/n] : ").strip().lower()
    if use_joy == "o":
        prog["pitchwheel"] = input("  Pitchwheel (gauche/droite) -> axe ? [axis_x] : ").strip() or "axis_x"
        prog["modwheel"]   = input("  Modwheel (haut/bas) -> axe ? [axis_y] : ").strip() or "axis_y"

    return prog

def main():
    print("\n██ HexPad Mapping Wizard")
    print("Génère ton config.json en capturant tes touches en direct.\n")

    device = pick_device()
    n_prog = int(input("Combien de programmes à configurer ? [4] : ").strip() or "4")

    config = {"device_name": device, "programs": {}}

    with mido.open_input(device) as port:
        for p in range(1, n_prog + 1):
            config["programs"][str(p)] = wizard_program(port, p)

    out = "config.json"
    backup = "config.backup.json"
    if os.path.exists(out):
        os.rename(out, backup)
        print(f"\n[WIZARD] Ancien config sauvegardé -> {backup}")

    with open(out, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n[WIZARD] ✅ config.json généré !")
    print(json.dumps(config, indent=2))

if __name__ == "__main__":
    main()
