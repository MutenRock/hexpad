#!/usr/bin/env python3
"""
HexPad local configuration bootstrap.

config.json is intentionally ignored by git because it contains machine-specific
MIDI/audio/OBS settings. This module provides a safe default config and can create
or repair the local config on first launch.

Important Windows note: config.json is always written with ensure_ascii=True so
it stays pure ASCII. That avoids cp1252/charmap crashes in older code paths that
open the file without an explicit UTF-8 encoding.
"""
from __future__ import annotations

import json
import shutil
import time
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "_comment": "Local HexPad config. This file is generated automatically and ignored by git.",
    "device_name": "MPK mini 3 0",
    "theme": "dark",
    "window_mode": "NORMAL",
    "window_w": 520,
    "window_h": 820,
    "http_timeout": 3,
    "programs": {
        "1": {
            "name": "Gamepad",
            "mode": "gamepad",
            "pads": {
                "36": "btn_1", "37": "btn_2", "38": "btn_3", "39": "btn_4",
                "40": "btn_5", "41": "btn_6", "42": "btn_7", "43": "btn_8"
            },
            "knobs": {
                "70": "axis_z", "71": "axis_rx", "72": "axis_ry", "73": "axis_rz",
                "74": "axis_sl0", "75": "axis_sl1", "76": "axis_x", "77": "axis_y"
            },
            "pitchwheel": "axis_x",
            "modwheel": "axis_y"
        },
        "2": {
            "name": "WebSocket",
            "mode": "websocket",
            "ws_url": "ws://localhost:8765"
        },
        "3": {
            "name": "Macros",
            "mode": "macro",
            "pads": {
                "36": "ctrl+z", "37": "ctrl+s", "38": "ctrl+c", "39": "ctrl+v",
                "40": "ctrl+shift+z", "41": "f5", "42": "f11", "43": "esc"
            }
        },
        "4": {
            "name": "Debug",
            "mode": "debug"
        },
        "5": {
            "name": "OBS",
            "mode": "obs",
            "obs_host": "localhost",
            "obs_port": 4455,
            "obs_password": "",
            "pads": {
                "36": {"action": "scene", "scene": "Gaming"},
                "37": {"action": "scene", "scene": "Cam only"},
                "38": {"action": "toggle_mute", "source": "Mic/Aux"},
                "39": {"action": "toggle_stream"},
                "40": {"action": "toggle_record"},
                "41": {"action": "screenshot"},
                "42": {"action": "toggle_source", "source": "Webcam"},
                "43": {"action": "hotkey", "hotkey": "OBSBasic.StartReplayBuffer"}
            }
        },
        "6": {
            "name": "RGB",
            "mode": "lightfx",
            "backend": "openrgb",
            "openrgb_host": "localhost",
            "openrgb_port": 6742,
            "pads": {
                "36": {"action": "color", "r": 168, "g": 85, "b": 247},
                "37": {"action": "color", "r": 59, "g": 130, "b": 246},
                "38": {"action": "color", "r": 255, "g": 255, "b": 255},
                "39": {"action": "effect", "effect": "breathing"},
                "40": {"action": "effect", "effect": "rainbow"},
                "41": {"action": "off"},
                "42": {"action": "color", "r": 0, "g": 0, "b": 255},
                "43": {"action": "color", "r": 255, "g": 0, "b": 255}
            }
        },
        "7": {
            "name": "Visualizer",
            "mode": "visualizer",
            "show_piano": True,
            "show_cc": True
        },
        "8": {
            "name": "Sampler",
            "mode": "sound_preset",
            "sounds_dir": "sounds",
            "pads": {
                "36": {"file": "kick.wav", "volume": 1.0},
                "37": {"file": "snare.wav", "volume": 0.9},
                "38": {"file": "hihat.wav", "volume": 0.7},
                "39": {"file": "clap.wav", "volume": 0.8},
                "40": {"file": "bass.wav", "volume": 1.0, "loop": True},
                "41": {"file": "melody.wav", "volume": 0.8},
                "42": {"file": "fx.wav", "volume": 0.6},
                "43": "stop_all"
            }
        },
        "9": {
            "name": "2XKO",
            "mode": "macro",
            "pads": {
                "36": "j", "37": "k", "38": "l", "39": "i",
                "40": "m", "41": "u", "42": "space", "43": "o"
            },
            "pads_bank_b": {
                "44": "p", "45": "comma", "46": "period", "47": "r",
                "48": "a", "49": "d", "50": "w", "51": "s"
            }
        },
        "10": {
            "name": "Music",
            "mode": "music",
            "sounds_dir": "sounds",
            "music_volume": 1.0,
            "music_device": "",
            "pads": {
                "36": {"file": "kick.wav", "volume": 1.0},
                "37": {"file": "snare.wav", "volume": 0.9},
                "38": {"file": "hihat.wav", "volume": 0.7},
                "39": {"file": "clap.wav", "volume": 0.8},
                "40": {"file": "bass.wav", "volume": 1.0, "loop": True},
                "41": {"file": "melody.wav", "volume": 0.8},
                "42": {"file": "fx.wav", "volume": 0.6},
                "43": "stop_all"
            }
        },
        "11": {
            "name": "HTTP",
            "mode": "http",
            "http_timeout": 3,
            "pads": {
                "36": {"method": "GET", "url": "http://localhost:8080/pad/1"},
                "37": {"method": "GET", "url": "http://localhost:8080/pad/2"},
                "38": {"method": "POST", "url": "http://localhost:8080/pad/3", "body": {"pad": 3}},
                "39": {"method": "POST", "url": "http://localhost:8080/pad/4", "body": {"pad": 4}}
            }
        }
    }
}


def _deep_fill_missing(current: Any, default: Any) -> tuple[Any, bool]:
    """Return current with missing keys filled from default, preserving user edits."""
    if not isinstance(current, dict) or not isinstance(default, dict):
        return current, False

    changed = False
    for key, value in default.items():
        if key not in current:
            current[key] = deepcopy(value)
            changed = True
        else:
            merged, sub_changed = _deep_fill_missing(current[key], value)
            current[key] = merged
            changed = changed or sub_changed
    return current, changed


def _backup_path(config_path: Path) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return config_path.with_name(f"config.backup-{stamp}.json")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def write_default_config(path: Path) -> None:
    _write_json(path, DEFAULT_CONFIG)


def ensure_local_config(root: str | Path | None = None, *, silent: bool = False) -> Path:
    """
    Ensure a valid local config.json exists.

    - If missing: create it from DEFAULT_CONFIG.
    - If invalid JSON: back it up and recreate a clean config.
    - If valid but old: fill only missing default keys; preserve user changes.
    - Always rewrite as ASCII-safe JSON to avoid Windows charmap errors.
    """
    root_path = Path(root or Path.cwd())
    config_path = root_path / "config.json"

    # Avoid surprising side effects when imported outside the HexPad repository.
    if not (root_path / "gui.py").exists():
        return config_path

    if not config_path.exists():
        write_default_config(config_path)
        if not silent:
            print(f"[CONFIG] Created {config_path.name} from defaults")
        return config_path

    try:
        current = json.loads(config_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        try:
            current = json.loads(config_path.read_text(encoding="cp1252"))
        except Exception as exc:
            backup = _backup_path(config_path)
            shutil.move(str(config_path), str(backup))
            write_default_config(config_path)
            if not silent:
                print(f"[CONFIG] Invalid config backed up to {backup.name}: {exc}")
                print(f"[CONFIG] Created fresh {config_path.name}")
            return config_path
    except Exception as exc:
        backup = _backup_path(config_path)
        shutil.move(str(config_path), str(backup))
        write_default_config(config_path)
        if not silent:
            print(f"[CONFIG] Invalid config backed up to {backup.name}: {exc}")
            print(f"[CONFIG] Created fresh {config_path.name}")
        return config_path

    merged, changed = _deep_fill_missing(current, DEFAULT_CONFIG)
    # Always rewrite: this normalizes valid UTF-8 configs to ASCII-safe JSON.
    _write_json(config_path, merged)
    if not silent:
        if changed:
            print(f"[CONFIG] Updated {config_path.name} with missing default keys")
        print(f"[CONFIG] Normalized {config_path.name} as ASCII-safe JSON")

    return config_path


if __name__ == "__main__":
    ensure_local_config(silent=False)
