#!/usr/bin/env python3
"""
HexPad Themes — palettes dark et light.
v1.7.0 : palette violet/bleu/blanc
"""

DARK = {
    "name":    "dark",
    "bg":      "#0a0a12",
    "panel":   "#11111f",
    "panel2":  "#16162a",
    "border":  "#1e1e3a",
    "accent":  "#a855f7",   # violet
    "accent2": "#3b82f6",   # bleu
    "accent3": "#f43f5e",
    "text":    "#ffffff",   # blanc pur
    "dim":     "#6b7280",
    "green":   "#22c55e",
    "red":     "#ef4444",
    "yellow":  "#fbbf24",
    "btn":     "#1e1b4b",
    "pad_off": "#1e1b4b",
    "learn":   "#f43f5e",
    "combo":   "#fbbf24",
    "sel_fg":  "#000000",   # texte sur bouton preset sélectionné
    "console_bg": "#06060e",
    "console_fg": "#a855f7",
    "toggle_icon": "\u2600",
}

LIGHT = {
    "name":    "light",
    "bg":      "#f5f3ff",
    "panel":   "#ede9fe",
    "panel2":  "#ddd6fe",
    "border":  "#c4b5fd",
    "accent":  "#7c3aed",   # violet foncé
    "accent2": "#2563eb",   # bleu
    "accent3": "#e11d48",
    "text":    "#1e1b4b",   # quasi-noir violet
    "dim":     "#6d28d9",
    "green":   "#16a34a",
    "red":     "#dc2626",
    "yellow":  "#d97706",
    "btn":     "#ddd6fe",
    "pad_off": "#ddd6fe",
    "learn":   "#e11d48",
    "combo":   "#d97706",
    "sel_fg":  "#ffffff",   # texte sur bouton preset sélectionné
    "console_bg": "#ffffff",
    "console_fg": "#7c3aed",
    "toggle_icon": "\u25d0",
}

MODE_COLORS = {
    "gamepad":      "#a855f7",
    "websocket":    "#3b82f6",
    "macro":        "#fbbf24",
    "debug":        "#f43f5e",
    "obs":          "#f97316",
    "lightfx":      "#ec4899",
    "visualizer":   "#06b6d4",
    "sound_preset": "#84cc16",
    "music":        "#8b5cf6",
}


def get(name):
    return DARK if name == "dark" else LIGHT
