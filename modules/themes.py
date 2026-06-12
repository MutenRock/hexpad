#!/usr/bin/env python3
"""
HexPad Themes — palettes dark et light.
"""

DARK = {
    "name":    "dark",
    "bg":      "#0a0a12",
    "panel":   "#11111f",
    "panel2":  "#16162a",
    "border":  "#1e1e3a",
    "accent":  "#00ffe7",
    "accent2": "#7f00ff",
    "accent3": "#ff006e",
    "text":    "#c8c8e8",
    "dim":     "#555577",
    "green":   "#00ff99",
    "red":     "#ff4455",
    "yellow":  "#ffd700",
    "btn":     "#1a1a30",
    "pad_off": "#1a1a30",
    "learn":   "#ff006e",
    "combo":   "#ffd700",
    "console_bg": "#06060e",
    "console_fg": "#00ffe7",
    "toggle_icon": "\u2600",
}

LIGHT = {
    "name":    "light",
    "bg":      "#f0f0f8",
    "panel":   "#e2e2f0",
    "panel2":  "#d8d8ec",
    "border":  "#b0b0cc",
    "accent":  "#0055cc",
    "accent2": "#6600cc",
    "accent3": "#cc0055",
    "text":    "#1a1a2e",
    "dim":     "#8888aa",
    "green":   "#007744",
    "red":     "#cc2233",
    "yellow":  "#aa7700",
    "btn":     "#c8c8e0",
    "pad_off": "#c8c8e0",
    "learn":   "#cc0055",
    "combo":   "#aa7700",
    "console_bg": "#ffffff",
    "console_fg": "#0055cc",
    "toggle_icon": "\u25d0",
}

MODE_COLORS = {
    "gamepad":      "#00ffe7",
    "websocket":    "#7f00ff",
    "macro":        "#ffd700",
    "debug":        "#ff006e",
    "obs":          "#ff6600",
    "lightfx":      "#ff00aa",
    "visualizer":   "#00bfff",
    "sound_preset": "#88ff00",
}


def get(name):
    return DARK if name == "dark" else LIGHT
