import math
import shutil
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog

import mido

from modules.config_defaults import ensure_local_config
from modules.themes import get as get_theme

try:
    import numpy as np
    import sounddevice as sd
    AUDIO_OK = True
except Exception:
    np = None
    sd = None
    AUDIO_OK = False

VERSION = "2.4.0"
DEVICE_HINTS = ("mpk", "mini", "akai", "pad")
PRESETS = {
    "Piano Bell": {"wave": "sine", "attack": 0.005, "release": 0.35, "sustain": 0.28},
    "Bass": {"wave": "square", "attack": 0.003, "release": 0.18, "sustain": 0.45, "octave": -1},
    "Lead": {"wave": "saw", "attack": 0.002, "release": 0.12, "sustain": 0.35},
    "Soft Pad": {"wave": "sine", "attack": 0.08, "release": 0.9, "sustain": 0.22},
    "Drums": {"wave": "drums", "attack": 0.001, "release": 0.22, "sustain": 0.8},
}


def midi_inputs():
    try:
        return [d for d in mido.get_input_names() if d and d.lower() != "aucun"] or ["Aucun"]
    except Exception:
        return ["Aucun"]


def pick_akai(devices):
    if not devices or devices == ["Aucun"]:
        return ""
    for d in devices:
        dl = d.lower()
        if any(h in dl for h in DEVICE_HINTS):
            return d
    return devices[0]


def midi_note_freq(note):
    return 440.0 * (2 ** ((note - 69) / 12))


def common_tool_paths():
    return {
        "Carla": ["carla", "Carla.exe"],
        "LMMS": ["lmms", "lmms.exe"],
        "VCV Rack": ["Rack", "Rack.exe", "VCV Rack.exe"],
        "BespokeSynth": ["BespokeSynth", "BespokeSynth.exe", "bespoke"],
        "FluidSynth": ["fluidsynth", "fluidsynth.exe"],
    }


class TinySynth:
    def __init__(self, log):
        self.log = log
        self.sample_rate = 44100
        self.preset_name = "Piano Bell"
        self.preset = PRESETS[self.preset_name]
        self.stream = None
        self.voices = []
        self.lock = threading.RLock()
        self.volume = 0.25

    def set_preset(self, name):
        self.preset_name = name if name in PRESETS else "Piano Bell"
        self.preset = PRESETS[self.preset_name]
        self.log(f"[SYNTH] Preset : {self.preset_name}")

    def set_volume(self, value):
        try:
            self.volume = max(0.0, min(1.0, float(value)))
        except Exception:
            self.volume = 0.25

    def start(self, output_device=None):
        if not AUDIO_OK:
            raise RuntimeError("sounddevice/numpy manquants")
        self.stop()
        self.stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=2,
            dtype="float32",
            device=output_device,
            callback=self._callback,
            blocksize=512,
        )
        self.stream.start()

    def stop(self):
        with self.lock:
            self.voices.clear()
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

    def note_on(self, note, velocity):
        velocity = max(0, min(127, int(velocity)))
        if velocity == 0:
            self.note_off(note)
            return
        with self.lock:
            if self.preset.get("wave") == "drums":
                self.voices.append({"note": note, "phase": 0.0, "age": 0, "vel": velocity / 127.0, "released": False, "drum": True})
            else:
                octave = self.preset.get("octave", 0)
                self.voices.append({"note": note, "freq": midi_note_freq(note + 12 * octave), "phase": 0.0, "age": 0, "vel": velocity / 127.0, "released": False, "release_age": 0})

    def note_off(self, note):
        with self.lock:
            for voice in self.voices:
                if voice.get("note") == note:
                    voice["released"] = True
                    voice["release_age"] = 0

    def _wave(self, phase, wave):
        if wave == "square":
            return np.where(np.sin(phase) >= 0, 1.0, -1.0)
        if wave == "saw":
            return 2.0 * ((phase / (2.0 * math.pi)) % 1.0) - 1.0
        return np.sin(phase)

    def _drum(self, voice, frames):
        t = (np.arange(frames) + voice["age"]) / self.sample_rate
        note = voice.get("note", 36)
        vel = voice.get("vel", 0.8)
        if note in (36, 40):
            freq = 55.0 + 55.0 * np.exp(-t * 28.0)
            sig = np.sin(2 * math.pi * freq * t) * np.exp(-t * 10.0)
        elif note in (37, 38):
            sig = (np.random.rand(frames) * 2 - 1) * np.exp(-t * 18.0)
        else:
            sig = np.sin(2 * math.pi * 360.0 * t) * np.exp(-t * 22.0)
        return sig * vel

    def _callback(self, outdata, frames, time_info, status):
        if status:
            pass
        mix = np.zeros(frames, dtype=np.float32)
        remove = []
        with self.lock:
            voices = list(self.voices)
            for voice in voices:
                if voice.get("drum"):
                    sig = self._drum(voice, frames)
                    voice["age"] += frames
                    if voice["age"] > int(self.sample_rate * 0.8):
                        remove.append(voice)
                    mix += sig.astype(np.float32)
                    continue

                freq = voice["freq"]
                phase = voice["phase"] + 2 * math.pi * freq * np.arange(frames) / self.sample_rate
                sig = self._wave(phase, self.preset.get("wave", "sine"))
                voice["phase"] = float((phase[-1] + 2 * math.pi * freq / self.sample_rate) % (2 * math.pi))
                voice["age"] += frames
                age_s = voice["age"] / self.sample_rate
                attack = max(0.001, self.preset.get("attack", 0.005))
                sustain = self.preset.get("sustain", 0.3)
                if voice.get("released"):
                    voice["release_age"] += frames
                    release_s = max(0.03, self.preset.get("release", 0.2))
                    amp = max(0.0, 1.0 - (voice["release_age"] / self.sample_rate) / release_s) * sustain
                    if amp <= 0.001:
                        remove.append(voice)
                else:
                    amp = min(1.0, age_s / attack) * sustain
                mix += (sig * amp * voice.get("vel", 1.0)).astype(np.float32)
            for voice in remove:
                if voice in self.voices:
                    self.voices.remove(voice)
        mix *= self.volume
        mix = np.clip(mix, -0.95, 0.95)
        outdata[:, 0] = mix
        outdata[:, 1] = mix


class StudioPlay:
    def __init__(self, root):
        ensure_local_config(silent=True)
        self.root = root
        self.C = get_theme("dark")
        self.midi_stop = threading.Event()
        self.midi_thread = None
        self.running = False
        self.synth = TinySynth(self.log)
        self.sf2_path = tk.StringVar(value="")

        root.title(f"HexPad Play Sound / Studio v{VERSION}")
        root.geometry("620x680")
        root.minsize(520, 520)
        root.configure(bg=self.C["bg"])
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._style()
        self._build()

    def _style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("H.TCombobox", fieldbackground=self.C["btn"], background=self.C["btn"], foreground=self.C["accent"], arrowcolor=self.C["accent"])

    def _build(self):
        C = self.C
        header = tk.Frame(self.root, bg=C["panel"], pady=10)
        header.pack(fill="x")
        tk.Label(header, text="HexPad Play Sound", fg=C["text"], bg=C["panel"], font=("Courier", 15, "bold")).pack(side="left", padx=14)
        tk.Button(header, text="Refresh", bg=C["accent2"], fg=C["bg"], relief="flat", command=self.refresh).pack(side="right", padx=10)

        form = tk.Frame(self.root, bg=C["bg"], pady=10)
        form.pack(fill="x", padx=14)

        tk.Label(form, text="MIDI input", fg=C["dim"], bg=C["bg"]).grid(row=0, column=0, sticky="w")
        self.midi_var = tk.StringVar()
        self.midi_cb = ttk.Combobox(form, textvariable=self.midi_var, values=midi_inputs(), width=45, state="readonly", style="H.TCombobox")
        self.midi_cb.grid(row=0, column=1, sticky="ew", padx=8, pady=3)

        tk.Label(form, text="Audio output", fg=C["dim"], bg=C["bg"]).grid(row=1, column=0, sticky="w")
        self.audio_var = tk.StringVar()
        self.audio_cb = ttk.Combobox(form, textvariable=self.audio_var, values=self.audio_outputs(), width=45, state="readonly", style="H.TCombobox")
        self.audio_cb.grid(row=1, column=1, sticky="ew", padx=8, pady=3)

        tk.Label(form, text="Preset", fg=C["dim"], bg=C["bg"]).grid(row=2, column=0, sticky="w")
        self.preset_var = tk.StringVar(value="Piano Bell")
        self.preset_cb = ttk.Combobox(form, textvariable=self.preset_var, values=list(PRESETS.keys()), width=45, state="readonly", style="H.TCombobox")
        self.preset_cb.grid(row=2, column=1, sticky="ew", padx=8, pady=3)
        self.preset_cb.bind("<<ComboboxSelected>>", lambda e: self.synth.set_preset(self.preset_var.get()))

        tk.Label(form, text="Volume", fg=C["dim"], bg=C["bg"]).grid(row=3, column=0, sticky="w")
        self.volume_var = tk.DoubleVar(value=0.25)
        tk.Scale(form, variable=self.volume_var, from_=0.0, to=1.0, resolution=0.01, orient="horizontal", bg=C["bg"], fg=C["dim"], highlightthickness=0, command=lambda v: self.synth.set_volume(v)).grid(row=3, column=1, sticky="ew", padx=8, pady=3)
        form.columnconfigure(1, weight=1)

        controls = tk.Frame(self.root, bg=C["bg"], pady=6)
        controls.pack(fill="x", padx=14)
        self.start_btn = tk.Button(controls, text="START PLAY SOUND", bg=C["green"], fg=C["bg"], relief="flat", pady=10, font=("Courier", 11, "bold"), command=self.start)
        self.start_btn.pack(fill="x", pady=(0, 6))
        self.stop_btn = tk.Button(controls, text="STOP", bg=C["red"], fg="white", relief="flat", pady=8, font=("Courier", 10, "bold"), state="disabled", command=self.stop)
        self.stop_btn.pack(fill="x")

        ext = tk.LabelFrame(self.root, text=" Outils externes optionnels ", bg=C["bg"], fg=C["accent"], font=("Courier", 8, "bold"))
        ext.pack(fill="x", padx=14, pady=8)
        row = tk.Frame(ext, bg=C["bg"])
        row.pack(fill="x", padx=8, pady=8)
        for name in ("Carla", "LMMS", "VCV Rack", "BespokeSynth"):
            tk.Button(row, text=name, bg=C["btn"], fg=C["accent"], relief="flat", command=lambda n=name: self.open_tool(n)).pack(side="left", padx=4)

        sf = tk.Frame(ext, bg=C["bg"])
        sf.pack(fill="x", padx=8, pady=(0, 8))
        tk.Button(sf, text="SoundFont", bg=C["btn"], fg=C["accent"], relief="flat", command=self.choose_soundfont).pack(side="left", padx=4)
        tk.Entry(sf, textvariable=self.sf2_path, bg=C["btn"], fg=C["dim"], relief="flat").pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(sf, text="FluidSynth", bg=C["accent2"], fg=C["bg"], relief="flat", command=self.launch_fluidsynth).pack(side="left", padx=4)

        self.console = scrolledtext.ScrolledText(self.root, height=14, bg=C["console_bg"], fg=C["console_fg"], insertbackground=C["accent"], relief="flat", font=("Courier", 8))
        self.console.pack(fill="both", expand=True, padx=14, pady=10)
        self.console.config(state="disabled")
        self.refresh()
        self.log("Mode Play Sound pret.")
        if not AUDIO_OK:
            self.log("[ERR] sounddevice/numpy indisponibles : pip install sounddevice numpy")

    def log(self, msg):
        if not hasattr(self, "console"):
            return
        self.console.config(state="normal")
        self.console.insert("end", f"{time.strftime('%H:%M:%S')}  {msg}\n")
        self.console.see("end")
        self.console.config(state="disabled")

    def audio_outputs(self):
        if not AUDIO_OK:
            return ["Aucun"]
        values = []
        try:
            for idx, dev in enumerate(sd.query_devices()):
                if dev.get("max_output_channels", 0) > 0:
                    values.append(f"{idx}: {dev.get('name')}")
        except Exception:
            pass
        return values or ["Default"]

    def selected_audio_index(self):
        text = self.audio_var.get()
        if not text or text == "Default":
            return None
        try:
            return int(text.split(":", 1)[0])
        except Exception:
            return None

    def refresh(self):
        inputs = midi_inputs()
        outputs = self.audio_outputs()
        self.midi_cb.config(values=inputs)
        self.audio_cb.config(values=outputs)
        if self.midi_var.get() not in inputs:
            self.midi_var.set(pick_akai(inputs))
        if self.audio_var.get() not in outputs:
            self.audio_var.set(outputs[0])
        self.log("Devices rafraichis.")

    def start(self):
        if self.running:
            return
        midi = self.midi_var.get()
        if not midi or midi == "Aucun":
            self.log("[ERR] Aucun input MIDI.")
            return
        self.synth.set_preset(self.preset_var.get())
        self.synth.set_volume(self.volume_var.get())
        try:
            self.synth.start(self.selected_audio_index())
        except Exception as e:
            self.log(f"[ERR] Audio: {e}")
            return
        self.midi_stop.clear()
        self.running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.midi_thread = threading.Thread(target=self._midi_loop, args=(midi,), daemon=True)
        self.midi_thread.start()
        self.log(f"[START] {midi} -> {self.audio_var.get()} | {self.preset_var.get()}")

    def _midi_loop(self, midi):
        try:
            with mido.open_input(midi) as port:
                while not self.midi_stop.is_set():
                    msg = port.poll()
                    if msg:
                        if msg.type == "note_on":
                            self.synth.note_on(msg.note, msg.velocity)
                        elif msg.type == "note_off":
                            self.synth.note_off(msg.note)
                        elif msg.type == "control_change" and msg.control in (1, 7):
                            self.volume_var.set(msg.value / 127.0)
                            self.synth.set_volume(msg.value / 127.0)
                    time.sleep(0.001)
        except Exception as e:
            self.root.after(0, self.log, f"[ERR] MIDI: {e}")
        finally:
            self.root.after(0, self._stopped)

    def stop(self):
        self.midi_stop.set()
        self.synth.stop()
        self._stopped()

    def _stopped(self):
        if not self.running:
            return
        self.running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.log("[STOP] Play Sound arrete.")

    def open_tool(self, name):
        candidates = common_tool_paths().get(name, [])
        for exe in candidates:
            path = shutil.which(exe)
            if path:
                subprocess.Popen([path])
                self.log(f"[OPEN] {name}: {path}")
                return
        self.log(f"[MISS] {name} introuvable dans le PATH. Installe-le ou ajoute-le au PATH.")

    def choose_soundfont(self):
        path = filedialog.askopenfilename(title="Choisir un SoundFont", filetypes=[("SoundFont", "*.sf2 *.sf3"), ("Tous", "*.*")])
        if path:
            self.sf2_path.set(path)

    def launch_fluidsynth(self):
        path = shutil.which("fluidsynth") or shutil.which("fluidsynth.exe")
        if not path:
            self.log("[MISS] FluidSynth introuvable dans le PATH.")
            return
        sf2 = self.sf2_path.get().strip()
        if not sf2:
            self.log("[ERR] Choisis un fichier .sf2 avant de lancer FluidSynth.")
            return
        cmd = [path, "-i", "-m", "winmidi", sf2]
        subprocess.Popen(cmd)
        self.log("[OPEN] FluidSynth lance. Choisis l'input Akai dans le port MIDI FluidSynth si besoin.")

    def close(self):
        try:
            self.stop()
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    StudioPlay(root)
    root.mainloop()
