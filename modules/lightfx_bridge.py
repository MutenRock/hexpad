#!/usr/bin/env python3
"""
LightFX Bridge — controle RGB via OpenRGB SDK ou AlienFX
Requiert : pip install openrgb-python

Config exemple :
  {
    "mode": "lightfx",
    "backend": "openrgb",
    "openrgb_host": "localhost",
    "openrgb_port": 6742,
    "pads": {
      "36": {"action": "color",  "r": 255, "g": 0,   "b": 0},
      "37": {"action": "color",  "r": 0,   "g": 255, "b": 0},
      "38": {"action": "color",  "r": 0,   "g": 0,   "b": 255},
      "39": {"action": "effect", "effect": "breathing"},
      "40": {"action": "effect", "effect": "rainbow"},
      "41": {"action": "effect", "effect": "static"},
      "42": {"action": "off"},
      "43": {"action": "color",  "r": 255, "g": 100, "b": 0}
    }
  }
"""
try:
    from openrgb import OpenRGBClient
    from openrgb.utils import RGBColor
    OPENRGB_OK = True
except ImportError:
    OPENRGB_OK = False

try:
    import lightfx
    LIGHTFX_OK = True
except ImportError:
    LIGHTFX_OK = False


class LightFXBridge:
    def __init__(self, config):
        self.pads    = config.get("pads", {})
        self.backend = config.get("backend", "openrgb")
        self.client  = None

        if self.backend == "openrgb":
            if not OPENRGB_OK:
                print("[LIGHTFX] openrgb-python manquant — pip install openrgb-python")
                return
            try:
                host = config.get("openrgb_host", "localhost")
                port = config.get("openrgb_port", 6742)
                self.client = OpenRGBClient(host, port)
                print(f"[LIGHTFX] OpenRGB connecte sur {host}:{port} — {len(self.client.devices)} device(s)")
            except Exception as e:
                print(f"[LIGHTFX] OpenRGB connexion echouee : {e}")
                print("[LIGHTFX] Lance OpenRGB avec SDK Server actif (Settings > SDK Server, port 6742)")

        elif self.backend == "lightfx":
            if not LIGHTFX_OK:
                print("[LIGHTFX] lightfx manquant — installe AlienFX SDK")
                return
            try:
                lightfx.initialize()
                self.client = "lightfx"
                print("[LIGHTFX] AlienFX initialise")
            except Exception as e:
                print(f"[LIGHTFX] AlienFX erreur : {e}")

    def handle(self, msg):
        if not self.client:
            return
        if msg.type == "note_on" and msg.velocity > 0:
            key = str(msg.note)
            if key not in self.pads:
                return
            cfg    = self.pads[key]
            action = cfg.get("action", "color")
            try:
                if action == "color":
                    r, g, b = cfg.get("r", 255), cfg.get("g", 255), cfg.get("b", 255)
                    self._set_color(r, g, b)
                elif action == "off":
                    self._set_color(0, 0, 0)
                elif action == "effect":
                    self._set_effect(cfg.get("effect", "static"))
                print(f"[LIGHTFX] pad {key} -> {action} (vel={msg.velocity})")
            except Exception as e:
                print(f"[LIGHTFX] Erreur action '{action}' : {e}")

    def _set_color(self, r, g, b):
        if self.backend == "openrgb":
            color = RGBColor(r, g, b)
            for device in self.client.devices:
                device.set_color(color)
        elif self.backend == "lightfx":
            packed = (r << 16) | (g << 8) | b
            lightfx.set_light_color(0, packed)
            lightfx.update()

    def _set_effect(self, effect_name):
        if self.backend == "openrgb":
            for device in self.client.devices:
                for mode in device.modes:
                    if effect_name.lower() in mode.name.lower():
                        device.set_mode(mode)
                        print(f"[LIGHTFX] Effect '{mode.name}' applique")
                        return
            print(f"[LIGHTFX] Effect '{effect_name}' non trouve")
