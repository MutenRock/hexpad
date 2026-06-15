# -*- mode: python ; coding: utf-8 -*-
# HexPad v2.0 — PyInstaller spec
# Build : pyinstaller hexpad.spec

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# --- Collecte des données embarquées ---
datas = [
    ('config.json',          '.'),
    ('game_profiles.json',   '.'),
    ('modules',              'modules'),
    ('presets',              'presets'),
    ('sounds',               'sounds'),
    ('assets',               'assets'),
]

# rtmidi DLL Windows
hidden_imports = [
    'mido',
    'mido.backends.rtmidi',
    'rtmidi',
    'pyvjoy',
    'websockets',
    'pynput',
    'pynput.keyboard',
    'pynput.mouse',
    'obsws_python',
    'pygame',
    'sounddevice',
    'openrgb',
    'modules.dispatcher',
    'modules.midi_listener',
    'modules.gamepad',
    'modules.websocket_bridge',
    'modules.macros',
    'modules.obs_bridge',
    'modules.game_profiles',
    'modules.combo_engine',
    'modules.themes',
    'modules.music_bridge',
    'modules.sound_preset_bridge',
    'modules.lightfx_bridge',
    'modules.visualizer_bridge',
]

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'PIL', 'cv2', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='HexPad',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # pas de fenetre console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
    version='version_info.txt',
)
