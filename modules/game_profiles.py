#!/usr/bin/env python3
"""
Game Profiles Manager — gestion dynamique des profils clavier par jeu.

Charge/sauvegarde game_profiles.json.
Permet de switcher de profil a chaud depuis la GUI ou en CLI.

Structure game_profiles.json :
{
  "active": "2XKO",
  "profiles": {
    "2XKO": {
      "name": "2XKO",
      "description": "Leverless layout optimise pour 2XKO",
      "program": "9",
      "combos": {
        "bnb_light": {"label": "BnB Light",    "sequence": "j,j,k,50,l,80,j+k",   "loop": false},
        "bnb_heavy": {"label": "BnB Heavy",    "sequence": "j,j,k,50,l,80,l+k",   "loop": false},
        "super_s1":  {"label": "Super S1",     "sequence": "i,50,o",              "loop": false},
        "super_s2":  {"label": "Super S2",     "sequence": "k,50,l",              "loop": false},
        "parry":     {"label": "Parry",        "sequence": "u",                   "loop": false},
        "dash_fwd":  {"label": "Dash Forward", "sequence": "d,30,d",              "loop": false},
        "dash_back": {"label": "Dash Back",    "sequence": "a,30,a",              "loop": false},
        "tag_combo": {"label": "Tag Combo",    "sequence": "j,k,50,comma,80,j",  "loop": false}
      }
    },
    "SF6": {
      "name": "Street Fighter 6",
      "description": "Layout SF6 Modern / Classic",
      "program": "1",
      "combos": {
        "drive_rush":  {"label": "Drive Rush",   "sequence": "f,f",                 "loop": false},
        "drive_impact":{"label": "Drive Impact", "sequence": "hp+hk",               "loop": false},
        "sa1":         {"label": "SA1",          "sequence": "lp+mp+hp",            "loop": false},
        "sa2":         {"label": "SA2",          "sequence": "lk+mk+hk",            "loop": false},
        "bnb_modern":  {"label": "BnB Modern",   "sequence": "sp,50,mp,50,hp",      "loop": false},
        "throw":       {"label": "Throw",        "sequence": "lp+lk",               "loop": false}
      }
    },
    "Custom": {
      "name": "Custom",
      "description": "Profil libre",
      "program": "1",
      "combos": {}
    }
  }
}

Format sequence :
  - Touches separees par virgules : "j,k,l"
  - Delai en ms (nombre seul) : "j,50,k" = j, attendre 50ms, k
  - Simultanee avec + : "j+k" = j et k en meme temps
  - Tout combo de pynput Key est valide : "ctrl+z", "f5", "space"...
"""
import json
import os

PROFILES_FILE = "game_profiles.json"

DEFAULT_PROFILES = {
    "active": "2XKO",
    "profiles": {
        "2XKO": {
            "name": "2XKO",
            "description": "Leverless layout optimise pour 2XKO",
            "program": "9",
            "combos": {
                "bnb_light": {"label": "BnB Light",    "sequence": "j,j,k,50,l,80,j+k",  "loop": False},
                "bnb_heavy": {"label": "BnB Heavy",    "sequence": "j,j,k,50,l,80,l+k",  "loop": False},
                "super_s1":  {"label": "Super S1",     "sequence": "i,50,o",             "loop": False},
                "super_s2":  {"label": "Super S2",     "sequence": "k,50,l",             "loop": False},
                "parry":     {"label": "Parry",        "sequence": "u",                  "loop": False},
                "dash_fwd":  {"label": "Dash Fwd",     "sequence": "d,30,d",             "loop": False},
                "dash_back": {"label": "Dash Back",    "sequence": "a,30,a",             "loop": False},
                "tag_combo": {"label": "Tag Combo",    "sequence": "j,k,50,comma,80,j", "loop": False}
            }
        },
        "SF6": {
            "name": "Street Fighter 6",
            "description": "Layout SF6 Modern / Classic",
            "program": "1",
            "combos": {
                "drive_rush":   {"label": "Drive Rush",   "sequence": "f,f",           "loop": False},
                "drive_impact": {"label": "Drive Impact", "sequence": "hp+hk",        "loop": False},
                "sa1":          {"label": "SA1",          "sequence": "lp+mp+hp",     "loop": False},
                "sa2":          {"label": "SA2",          "sequence": "lk+mk+hk",     "loop": False},
                "bnb_modern":   {"label": "BnB Modern",   "sequence": "sp,50,mp,50,hp","loop": False},
                "throw":        {"label": "Throw",        "sequence": "lp+lk",        "loop": False}
            }
        },
        "Custom": {
            "name": "Custom",
            "description": "Profil libre",
            "program": "1",
            "combos": {}
        }
    }
}


class GameProfiles:
    def __init__(self):
        self.data = self._load()

    def _load(self):
        if os.path.exists(PROFILES_FILE):
            try:
                with open(PROFILES_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[PROFILES] Erreur lecture {PROFILES_FILE} : {e} — profils par defaut")
        return json.loads(json.dumps(DEFAULT_PROFILES))  # deep copy

    def save(self):
        with open(PROFILES_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        print(f"[PROFILES] Sauvegarde OK ({PROFILES_FILE})")

    @property
    def active(self):
        return self.data.get("active", "Custom")

    @active.setter
    def active(self, name):
        if name in self.data["profiles"]:
            self.data["active"] = name
            print(f"[PROFILES] Profil actif : {name}")
        else:
            print(f"[PROFILES] Profil inconnu : {name}")

    @property
    def active_profile(self):
        return self.data["profiles"].get(self.active, {})

    @property
    def names(self):
        return list(self.data["profiles"].keys())

    def get_profile(self, name):
        return self.data["profiles"].get(name)

    def get_combos(self, profile_name=None):
        name = profile_name or self.active
        return self.data["profiles"].get(name, {}).get("combos", {})

    def get_combo(self, combo_key, profile_name=None):
        return self.get_combos(profile_name).get(combo_key)

    def set_combo(self, combo_key, label, sequence, loop=False, profile_name=None):
        name = profile_name or self.active
        if name not in self.data["profiles"]:
            print(f"[PROFILES] Profil '{name}' introuvable")
            return
        self.data["profiles"][name]["combos"][combo_key] = {
            "label": label, "sequence": sequence, "loop": loop
        }

    def delete_combo(self, combo_key, profile_name=None):
        name = profile_name or self.active
        self.data["profiles"][name]["combos"].pop(combo_key, None)

    def add_profile(self, name, description="", program="1"):
        if name in self.data["profiles"]:
            print(f"[PROFILES] Profil '{name}' existe deja")
            return
        self.data["profiles"][name] = {
            "name": name, "description": description,
            "program": program, "combos": {}
        }
        print(f"[PROFILES] Profil '{name}' cree")

    def delete_profile(self, name):
        if name == self.active:
            print("[PROFILES] Impossible de supprimer le profil actif")
            return
        self.data["profiles"].pop(name, None)
        print(f"[PROFILES] Profil '{name}' supprime")
