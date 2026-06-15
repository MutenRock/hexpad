#!/usr/bin/env python3
"""
HexPad — HTTP Bridge
Chaque pad déclenche une requête HTTP GET ou POST configurable.

Config exemple dans config.json :
  {
    "mode": "http",
    "name": "HTTP Remote",
    "http_timeout": 3,
    "pads": {
      "36": {"method": "GET",  "url": "http://localhost:5000/action/1"},
      "37": {"method": "POST", "url": "http://localhost:5000/toggle",
             "body": {"key": "lights", "value": true},
             "headers": {"Authorization": "Bearer TOKEN"}},
      "38": {"method": "GET",  "url": "http://homeassistant.local:8123/api/services/light/toggle",
             "headers": {"Authorization": "Bearer HA_TOKEN"}}
    }
  }
"""
import threading
import json
try:
    import urllib.request as _req
    import urllib.error   as _err
except ImportError:
    pass


class HttpBridge:
    """
    Bridge HTTP — exécute GET/POST async sur chaque note_on.
    Utilise uniquement la stdlib (urllib) → pas de dépendance externe.
    """

    def __init__(self, prog: dict):
        self.prog    = prog
        self.timeout = int(prog.get("http_timeout", 3))
        self._last   = {}   # note → dernier status code

    # ── Interface attendue par Dispatcher ────────────────────────────────────

    def on_note(self, note: int, velocity: int):
        if velocity == 0:
            return
        ns  = str(note)
        cfg = self.prog.get("pads", {}).get(ns)
        if not cfg:
            print(f"[HTTP] pad {ns} : aucune config")
            return
        # fire-and-forget dans un thread pour ne pas bloquer MIDI
        threading.Thread(
            target=self._fire,
            args=(ns, cfg),
            daemon=True
        ).start()

    def on_cc(self, cc: int, value: int):
        """CC non géré en HTTP (ignoré silencieusement)."""
        pass

    def on_pitchwheel(self, pitch: int):
        pass

    def stop(self):
        pass

    # ── Internals ─────────────────────────────────────────────────────────────

    def _fire(self, pad_key: str, cfg: dict):
        method  = str(cfg.get("method", "GET")).upper()
        url     = cfg.get("url", "")
        body    = cfg.get("body")          # dict ou None
        headers = dict(cfg.get("headers", {}))

        if not url:
            print(f"[HTTP] pad {pad_key} : URL vide")
            return

        try:
            data = None
            if body is not None:
                data = json.dumps(body).encode("utf-8")
                headers.setdefault("Content-Type", "application/json")

            request = _req.Request(
                url,
                data=data,
                headers=headers,
                method=method
            )
            with _req.urlopen(request, timeout=self.timeout) as resp:
                status = resp.status
                self._last[pad_key] = status
                print(f"[HTTP] pad {pad_key} → {method} {url}  ✓ {status}")

        except _err.HTTPError as e:
            print(f"[HTTP] pad {pad_key} → {method} {url}  ✗ HTTP {e.code}: {e.reason}")
        except _err.URLError as e:
            print(f"[HTTP] pad {pad_key} → {method} {url}  ✗ URLError: {e.reason}")
        except Exception as e:
            print(f"[HTTP] pad {pad_key} → {method} {url}  ✗ {type(e).__name__}: {e}")

    # ── Helpers exposés à la GUI ───────────────────────────────────────────────

    def last_status(self, pad_key: str) -> str:
        """Retourne le dernier code HTTP reçu pour ce pad ('' si jamais appelé)."""
        return str(self._last.get(str(pad_key), ""))

    def test_pad(self, pad_key: str) -> bool:
        """Déclenche manuellement le pad (test depuis la GUI). Retourne True si config trouvée."""
        cfg = self.prog.get("pads", {}).get(str(pad_key))
        if not cfg:
            return False
        threading.Thread(target=self._fire, args=(str(pad_key), cfg), daemon=True).start()
        return True
