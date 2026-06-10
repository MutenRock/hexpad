#!/usr/bin/env python3
"""
HexPad — Akai MPK Mini Cyber Controller Manager
Refs: c0redumb/midi2vjoy, pepitooo/midi2vjoy, oscaracena/mdevtk

Usage:
    python main.py [--program 1-4] [--mode gamepad|websocket|macro|debug]
"""
import json, argparse
from modules.midi_listener    import MidiListener
from modules.dispatcher       import Dispatcher
from modules.gamepad          import GamepadBridge
from modules.websocket_bridge import WebSocketBridge
from modules.macros           import MacroBridge

def load_config():
    with open("config.json") as f:
        return json.load(f)

def build_bridge(prog):
    mode = prog.get("mode", "debug")
    if mode == "gamepad":   return GamepadBridge(prog), mode
    if mode == "websocket": return WebSocketBridge(prog["ws_url"]), mode
    if mode == "macro":     return MacroBridge(prog), mode
    return None, "debug"

def main():
    parser = argparse.ArgumentParser(description="HexPad — MPK Mini Cyber Controller")
    parser.add_argument("--program", default="1", help="Programme 1-4")
    parser.add_argument("--mode",    default=None, help="Override mode")
    args = parser.parse_args()

    cfg  = load_config()
    prog = cfg["programs"].get(args.program, cfg["programs"]["1"])
    if args.mode:
        prog["mode"] = args.mode

    bridge, mode = build_bridge(prog)
    d = Dispatcher()
    d.set_bridge(bridge, mode)

    print(f"\n██ HexPad v1.0.0 — mode: {mode} (programme {args.program})\n")
    MidiListener(cfg, d).start()

if __name__ == "__main__":
    main()
