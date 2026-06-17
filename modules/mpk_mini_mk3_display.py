"""
MPK Mini MK3 display helpers.

The MPK Mini MK3 OLED does not behave like a generic text terminal. The usable
method found in community implementations is to write a RAM preset over Akai
SysEx, then update the program name and/or knob names in that preset.

SysEx payload format:
  F0 47 7F 49 64 <len_hi> <len_lo> <246-byte-preset> F7

References used for offsets:
- Akai manufacturer id: 0x47
- MPK Mini MK3 product id: 0x49
- Write command: 0x64
- RAM program: 0x00
"""
from __future__ import annotations

from typing import Iterable

MANUFACTURER_ID = 0x47
DIRECTION_SEND = 0x7F
PRODUCT_ID_MPK_MINI_MK3 = 0x49
CMD_WRITE = 0x64
PGM_NUM_RAM = 0x00
DATA_PAYLOAD_LENGTH = 246
KNOB_NAME_LENGTH = 16

# Offsets are expressed as positions in the final SysEx message by several
# community maps, so payload indexes are offset - 7.
KNOB_NAME_INDEX = {
    1: 96 - 7,
    2: 116 - 7,
    3: 136 - 7,
    4: 156 - 7,
    5: 176 - 7,
    6: 196 - 7,
    7: 216 - 7,
    8: 236 - 7,
}
KNOB_MODE_INDEX = {1: 92 - 7, 2: 112 - 7, 3: 132 - 7, 4: 152 - 7, 5: 172 - 7, 6: 192 - 7, 7: 212 - 7, 8: 232 - 7}
KNOB_CC_INDEX = {1: 93 - 7, 2: 113 - 7, 3: 133 - 7, 4: 153 - 7, 5: 173 - 7, 6: 193 - 7, 7: 213 - 7, 8: 233 - 7}
KNOB_MIN_INDEX = {1: 94 - 7, 2: 114 - 7, 3: 134 - 7, 4: 154 - 7, 5: 174 - 7, 6: 194 - 7, 7: 214 - 7, 8: 234 - 7}
KNOB_MAX_INDEX = {1: 95 - 7, 2: 115 - 7, 3: 135 - 7, 4: 155 - 7, 5: 175 - 7, 6: 195 - 7, 7: 215 - 7, 8: 235 - 7}


def ascii_fixed(text: str, length: int) -> list[int]:
    raw = text.encode("ascii", errors="replace")[:length]
    raw = raw.ljust(length, b" ")
    return [b & 0x7F for b in raw]


def create_default_preset(program_name: str = "HEXPAD") -> list[int]:
    data = [0x00] * DATA_PAYLOAD_LENGTH
    data[0] = PGM_NUM_RAM
    data[1:17] = ascii_fixed(program_name, 16)

    # Sensible baseline values.
    data[17] = 0  # pad MIDI channel
    data[18] = 0  # aftertouch off
    data[19] = 0  # keybed channel
    data[20] = 4  # keybed octave

    for knob in range(1, 9):
        data[KNOB_MODE_INDEX[knob]] = 0
        data[KNOB_CC_INDEX[knob]] = 70 + knob - 1
        data[KNOB_MIN_INDEX[knob]] = 0
        data[KNOB_MAX_INDEX[knob]] = 127
        data[KNOB_NAME_INDEX[knob] : KNOB_NAME_INDEX[knob] + KNOB_NAME_LENGTH] = ascii_fixed(f"Knob {knob}", KNOB_NAME_LENGTH)

    return data


def set_program_name(data: list[int], name: str) -> list[int]:
    data = list(data)
    data[1:17] = ascii_fixed(name, 16)
    return data


def set_knob_name(data: list[int], knob: int, name: str) -> list[int]:
    if knob not in KNOB_NAME_INDEX:
        raise ValueError("knob must be between 1 and 8")
    data = list(data)
    idx = KNOB_NAME_INDEX[knob]
    data[idx : idx + KNOB_NAME_LENGTH] = ascii_fixed(name, KNOB_NAME_LENGTH)
    return data


def set_knob_names(data: list[int], names: Iterable[str]) -> list[int]:
    data = list(data)
    for idx, name in enumerate(names, start=1):
        if idx > 8:
            break
        data = set_knob_name(data, idx, name)
    return data


def build_write_sysex_data(preset_payload: list[int]) -> list[int]:
    if len(preset_payload) != DATA_PAYLOAD_LENGTH:
        raise ValueError(f"preset payload must be {DATA_PAYLOAD_LENGTH} bytes")
    for value in preset_payload:
        if value < 0 or value > 127:
            raise ValueError("SysEx data must be 7-bit values")
    length = len(preset_payload)
    len_hi = (length >> 7) & 0x7F
    len_lo = length & 0x7F
    return [MANUFACTURER_ID, DIRECTION_SEND, PRODUCT_ID_MPK_MINI_MK3, CMD_WRITE, len_hi, len_lo] + list(preset_payload)


def build_display_sysex_data(program_name: str = "HEXPAD", knob_names: Iterable[str] | None = None) -> list[int]:
    preset = create_default_preset(program_name)
    if knob_names is not None:
        preset = set_knob_names(preset, knob_names)
    return build_write_sysex_data(preset)


def format_sysex(data: list[int]) -> str:
    return "F0 " + " ".join(f"{b:02X}" for b in data) + " F7"
