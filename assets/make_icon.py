#!/usr/bin/env python3
"""
Genere assets/icon.ico — hexagone violet sur fond sombre.
Requiert Pillow : pip install Pillow
"""
import os, math
try:
    from PIL import Image, ImageDraw
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'Pillow', '--quiet'])
    from PIL import Image, ImageDraw

def hex_points(cx, cy, r, flat_top=False):
    pts = []
    for i in range(6):
        angle = math.radians(60 * i + (0 if flat_top else 30))
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return pts

def make_frame(size):
    img  = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    r_outer = size * 0.46
    r_inner = size * 0.30
    # Fond sombre arrondi
    pad = size * 0.06
    draw.rounded_rectangle([pad, pad, size-pad, size-pad],
                           radius=size*0.18, fill=(14, 10, 26, 255))
    # Hexagone exterieur violet
    draw.polygon(hex_points(cx, cy, r_outer), fill=(168, 85, 247, 255))
    # Hexagone interieur (fond)
    draw.polygon(hex_points(cx, cy, r_inner), fill=(14, 10, 26, 230))
    # Petit hex central accent bleu
    draw.polygon(hex_points(cx, cy, r_inner * 0.45), fill=(59, 130, 246, 255))
    return img

os.makedirs('assets', exist_ok=True)
sizes   = [256, 128, 64, 48, 32, 16]
frames  = [make_frame(s) for s in sizes]
out     = 'assets/icon.ico'
frames[0].save(out, format='ICO', sizes=[(s, s) for s in sizes],
               append_images=frames[1:])
print(f'[OK] {out} genere ({os.path.getsize(out)} octets)')
