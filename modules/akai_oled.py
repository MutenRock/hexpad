"""
modules/akai_oled.py

Gère l'écran OLED du MPK Mini MK3 via SysEx.

Capacités :
  - Nommer les 8 knobs (affichés sur l'OLED quand on tourne un knob)
  - Envoyer un preset complet en RAM (sans sauvegarder dans la flash)
  - Lire le preset actif depuis le MPK (dump request)

Référence : AKAI MPK Mini MK3 MIDI Implementation (section SysEx)
Format preset RAM send : F0 47 00 49 30 00 <len_msb> <len_lsb> <preset_bytes> F7
"""

import mido
import time

# ── Constantes AKAI ───────────────────────────────────────────────────────────
AKAI_MFR          = 0x47          # Akai manufacturer ID
AKAI_DEVICE       = 0x00          # device ID (broadcast)
AKAI_MPK_MINI_MK3 = 0x49          # MPK Mini MK3 product ID
SYSEX_PRESET_SEND = 0x30          # command : send preset to RAM
SYSEX_PRESET_REQ  = 0x31          # command : request preset dump
SYSEX_PRESET_RECV = 0x30          # response command byte

KNOB_NAME_MAX    = 8              # max chars per knob label on OLED
NUM_KNOBS        = 8
NUM_PADS         = 16             # 8 bank A + 8 bank B

# Offsets dans le bloc preset
# Le preset fait 172 bytes de payload (hors header/footer SysEx)
PRESET_SIZE       = 172
OFFSET_KNOB_NAMES = 104           # 8 * 8 bytes = 64 bytes de noms knobs


# ── Helpers ───────────────────────────────────────────────────────────────────

def _encode_len(n: int):
    """Encode la longueur en 2 bytes MSB/LSB pour le header SysEx AKAI."""
    return (n >> 7) & 0x7F, n & 0x7F


def _pad_name(name: str, length: int = KNOB_NAME_MAX) -> list:
    """Encode un nom en ASCII, tronqué/paddé à `length` bytes, retourne liste int."""
    encoded = name.encode("ascii", errors="replace")[:length]
    return list(encoded) + [0x00] * (length - len(encoded))


def _safe_7bit(data: list) -> list:
    """Masque les bytes à 7 bits (SysEx ne supporte pas les valeurs >= 0x80)."""
    return [b & 0x7F for b in data]


# ── Preset builder ────────────────────────────────────────────────────────────

class AkaiPreset:
    """
    Représentation d'un preset MPK Mini MK3.

    Seuls les noms de knobs sont exposés pour l'instant ;
    les autres bytes du preset sont conservés à leurs valeurs par défaut
    (zéros) pour ne pas casser la config hardware existante lors d'un
    send-to-RAM.
    """

    def __init__(self):
        self._data = [0x00] * PRESET_SIZE
        self.knob_names: list = [""] * NUM_KNOBS

    def set_knob_name(self, index: int, name: str):
        """Définit le nom affiché sur l'OLED pour le knob `index` (0-7)."""
        if not 0 <= index < NUM_KNOBS:
            raise ValueError(f"Index knob invalide : {index} (attendu 0-7)")
        self.knob_names[index] = name[:KNOB_NAME_MAX]

    def to_bytes(self) -> list:
        """Sérialise le preset en liste d'ints prête à être insérée dans SysEx."""
        payload = list(self._data)
        for i, name in enumerate(self.knob_names):
            offset = OFFSET_KNOB_NAMES + i * KNOB_NAME_MAX
            chars  = _pad_name(name, KNOB_NAME_MAX)
            payload[offset : offset + KNOB_NAME_MAX] = chars
        return _safe_7bit(payload)


# ── Envoi / réception SysEx ───────────────────────────────────────────────────

def build_preset_sysex(preset: AkaiPreset) -> list:
    """
    Construit le message SysEx complet pour envoyer un preset en RAM.
    Retourne une liste d'ints (sans F0/F7, ajoutés automatiquement par mido).
    """
    payload  = preset.to_bytes()
    msb, lsb = _encode_len(len(payload))
    return [
        AKAI_MFR,
        AKAI_DEVICE,
        AKAI_MPK_MINI_MK3,
        SYSEX_PRESET_SEND,
        msb, lsb,
        *payload
    ]


def build_preset_request() -> list:
    """
    Construit le message SysEx de demande de dump preset actif.
    Retourne une liste d'ints (sans F0/F7).
    """
    return [
        AKAI_MFR,
        AKAI_DEVICE,
        AKAI_MPK_MINI_MK3,
        SYSEX_PRESET_REQ,
        0x00, 0x00   # longueur = 0 (requête vide)
    ]


def send_preset(port_name: str, preset: AkaiPreset) -> str:
    """
    Envoie un preset en RAM via le port de sortie MIDI `port_name`.
    Retourne un message de statut (str).
    """
    out_names = mido.get_output_names()
    if port_name not in out_names:
        matches = [n for n in out_names if port_name.lower() in n.lower()]
        if not matches:
            return f"[OLED] Port MIDI introuvable : {port_name}\nDisponibles : {out_names}"
        port_name = matches[0]

    data = build_preset_sysex(preset)
    msg  = mido.Message("sysex", data=data)
    try:
        with mido.open_output(port_name) as port:
            port.send(msg)
        return f"[OLED] ✓ Preset envoyé sur {port_name}"
    except Exception as e:
        return f"[OLED] Erreur envoi : {e}"


def request_preset_dump(port_name: str, timeout: float = 2.0):
    """
    Envoie une requête dump et attend la réponse.
    Retourne (raw_bytes: list | None, status_msg: str).
    """
    out_names   = mido.get_output_names()
    in_names    = mido.get_input_names()
    matches_out = [n for n in out_names if port_name.lower() in n.lower()]
    matches_in  = [n for n in in_names  if port_name.lower() in n.lower()]
    if not matches_out or not matches_in:
        return None, f"[OLED] Port introuvable. Out:{out_names}  In:{in_names}"

    req_msg = mido.Message("sysex", data=build_preset_request())
    try:
        with mido.open_output(matches_out[0]) as out_port, \
             mido.open_input(matches_in[0])  as in_port:
            out_port.send(req_msg)
            deadline = time.time() + timeout
            while time.time() < deadline:
                msg = in_port.poll()
                if msg and msg.type == "sysex":
                    d = list(msg.data)
                    if (len(d) > 4
                            and d[0] == AKAI_MFR
                            and d[2] == AKAI_MPK_MINI_MK3
                            and d[3] == SYSEX_PRESET_RECV):
                        return d, f"[OLED] ✓ Dump reçu ({len(d)} bytes)"
                time.sleep(0.01)
        return None, "[OLED] Timeout — aucun dump reçu."
    except Exception as e:
        return None, f"[OLED] Erreur dump : {e}"


def parse_knob_names_from_dump(raw: list) -> list:
    """
    Extrait les 8 noms de knobs depuis un dump brut SysEx.
    Retourne une liste de 8 str.
    Header SysEx = 6 bytes (mfr + dev + prod + cmd + len_msb + len_lsb).
    """
    payload = raw[6:]
    names   = []
    for i in range(NUM_KNOBS):
        offset = OFFSET_KNOB_NAMES + i * KNOB_NAME_MAX
        chunk  = payload[offset : offset + KNOB_NAME_MAX]
        name   = bytes(b & 0x7F for b in chunk).rstrip(b"\x00").decode("ascii", errors="replace")
        names.append(name)
    return names
