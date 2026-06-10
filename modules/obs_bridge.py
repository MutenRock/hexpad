#!/usr/bin/env python3
"""
OBS Bridge — controle OBS Studio via obs-websocket v5
Requiert : pip install obsws-python

Config exemple dans config.json :
  {
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
  }
"""
try:
    import obsws_python as obs
    OBS_OK = True
except ImportError:
    OBS_OK = False
    print("[OBS] obsws-python manquant — pip install obsws-python")


class OBSBridge:
    def __init__(self, config):
        self.pads     = config.get("pads", {})
        self.host     = config.get("obs_host", "localhost")
        self.port     = config.get("obs_port", 4455)
        self.password = config.get("obs_password", "")
        self.client   = None
        if OBS_OK:
            try:
                self.client = obs.ReqClient(
                    host=self.host, port=self.port,
                    password=self.password, timeout=3
                )
                ver = self.client.get_version()
                print(f"[OBS] Connecte a OBS {ver.obs_version} (ws {ver.obs_web_socket_version})")
            except Exception as e:
                print(f"[OBS] Connexion echouee : {e}")
                print(f"[OBS] Verifie que OBS est ouvert avec obs-websocket actif (port {self.port})")
                self.client = None

    def handle(self, msg):
        if not self.client:
            return
        if msg.type == "note_on" and msg.velocity > 0:
            key = str(msg.note)
            if key not in self.pads:
                return
            action_cfg = self.pads[key]
            if isinstance(action_cfg, str):
                # Format court : "36": "Gaming" -> changer de scene
                self._set_scene(action_cfg)
                return
            action = action_cfg.get("action", "scene")
            try:
                if action == "scene":
                    self._set_scene(action_cfg["scene"])
                elif action == "toggle_mute":
                    self.client.toggle_input_mute(action_cfg["source"])
                    print(f"[OBS] Toggle mute : {action_cfg['source']}")
                elif action == "toggle_stream":
                    self.client.toggle_stream()
                    print("[OBS] Toggle stream")
                elif action == "toggle_record":
                    self.client.toggle_record()
                    print("[OBS] Toggle record")
                elif action == "screenshot":
                    self.client.save_source_screenshot(
                        source_name="Scene",
                        image_format="png",
                        image_file_path=f"screenshot_{msg.note}.png"
                    )
                    print("[OBS] Screenshot")
                elif action == "toggle_source":
                    src = action_cfg["source"]
                    cur = self.client.get_scene_item_enabled(
                        self.client.get_current_program_scene().current_program_scene_name,
                        self.client.get_scene_item_id(
                            self.client.get_current_program_scene().current_program_scene_name,
                            src
                        ).scene_item_id
                    ).scene_item_enabled
                    self.client.set_scene_item_enabled(
                        self.client.get_current_program_scene().current_program_scene_name,
                        self.client.get_scene_item_id(
                            self.client.get_current_program_scene().current_program_scene_name,
                            src
                        ).scene_item_id,
                        not cur
                    )
                    print(f"[OBS] Toggle source : {src}")
                elif action == "hotkey":
                    self.client.trigger_hotkey_by_name(action_cfg["hotkey"])
                    print(f"[OBS] Hotkey : {action_cfg['hotkey']}")
            except Exception as e:
                print(f"[OBS] Erreur action '{action}' : {e}")

    def _set_scene(self, scene_name):
        try:
            self.client.set_current_program_scene(scene_name)
            print(f"[OBS] Scene -> {scene_name}")
        except Exception as e:
            print(f"[OBS] Scene introuvable '{scene_name}' : {e}")
