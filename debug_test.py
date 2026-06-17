import json
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext

import mido

from modules.themes import get as get_theme

VERSION = "2.3.1"
HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]


class DebugTestWindow:
    def __init__(self, root):
        self.root = root
        self.C = get_theme("dark")
        self.midi_running = False
        self.midi_stop = threading.Event()
        self.ws_sock = None

        root.title(f"HexPad Debug / Test v{VERSION}")
        root.geometry("760x660")
        root.minsize(600, 500)
        root.configure(bg=self.C["bg"])
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._build()

    def _style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("H.TNotebook", background=self.C["bg"], borderwidth=0)
        s.configure("H.TNotebook.Tab", background=self.C["panel2"], foreground=self.C["dim"], padding=[12, 5])
        s.map("H.TNotebook.Tab", background=[("selected", self.C["panel"])], foreground=[("selected", self.C["accent"])])
        s.configure("H.TCombobox", fieldbackground=self.C["btn"], background=self.C["btn"], foreground=self.C["accent"])

    def _build(self):
        self._style()
        C = self.C
        header = tk.Frame(self.root, bg=C["panel"], pady=8)
        header.pack(fill="x")
        tk.Label(header, text="⬡ Debug / Test", fg=C["text"], bg=C["panel"], font=("Courier", 14, "bold")).pack(side="left", padx=12)
        tk.Button(header, text="↺ Refresh MIDI", bg=C["accent2"], fg=C["bg"], relief="flat", command=self.refresh_devices).pack(side="right", padx=10)

        self.nb = ttk.Notebook(self.root, style="H.TNotebook")
        self.nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.tab_midi = tk.Frame(self.nb, bg=C["bg"])
        self.tab_sysex = tk.Frame(self.nb, bg=C["bg"])
        self.tab_http = tk.Frame(self.nb, bg=C["bg"])
        self.tab_ws = tk.Frame(self.nb, bg=C["bg"])
        self.nb.add(self.tab_midi, text=" MIDI RAW ")
        self.nb.add(self.tab_sysex, text=" AKAI / SYSEX ")
        self.nb.add(self.tab_http, text=" HTTP ")
        self.nb.add(self.tab_ws, text=" WEBSOCKET ")
        self._build_midi(self.tab_midi)
        self._build_sysex(self.tab_sysex)
        self._build_http(self.tab_http)
        self._build_ws(self.tab_ws)

    def _entry(self, parent, var, width=30):
        return tk.Entry(parent, textvariable=var, width=width, bg=self.C["btn"], fg=self.C["accent"], insertbackground=self.C["accent"], relief="flat", font=("Courier", 9))

    def _logbox(self, parent):
        box = scrolledtext.ScrolledText(parent, bg=self.C["console_bg"], fg=self.C["console_fg"], insertbackground=self.C["accent"], relief="flat", font=("Courier", 8))
        box.pack(fill="both", expand=True, padx=10, pady=10)
        box.config(state="disabled")
        return box

    def _append(self, box, msg):
        box.config(state="normal")
        box.insert("end", f"{time.strftime('%H:%M:%S')}  {msg}\n")
        box.see("end")
        box.config(state="disabled")

    def _pick_akai(self, devices):
        if not devices or devices == ["Aucun"]:
            return ""
        for d in devices:
            if any(x in d.lower() for x in ("mpk", "mini", "akai", "pad")):
                return d
        return devices[0]

    def _input_devices(self):
        return mido.get_input_names() or ["Aucun"]

    def _output_devices(self):
        return mido.get_output_names() or ["Aucun"]

    # MIDI RAW ----------------------------------------------------------------
    def _build_midi(self, parent):
        row = tk.Frame(parent, bg=self.C["bg"], pady=8)
        row.pack(fill="x", padx=10)
        tk.Label(row, text="Input", fg=self.C["dim"], bg=self.C["bg"]).pack(side="left")
        self.midi_var = tk.StringVar()
        self.midi_cb = ttk.Combobox(row, textvariable=self.midi_var, values=self._input_devices(), width=34, state="readonly", style="H.TCombobox")
        self.midi_cb.pack(side="left", padx=8)
        self.refresh_devices()
        self.midi_btn = tk.Button(row, text="▶ Ecouter", bg=self.C["green"], fg=self.C["bg"], relief="flat", command=self.toggle_midi)
        self.midi_btn.pack(side="left", padx=4)
        tk.Button(row, text="✕ Vider", bg=self.C["btn"], fg=self.C["dim"], relief="flat", command=self.clear_midi).pack(side="left", padx=4)
        self.midi_log = self._logbox(parent)
        self._append(self.midi_log, "Selectionne un input puis clique Ecouter.")
        self._append(self.midi_log, "Astuce : pour voir une reponse SysEx, lance l'ecoute MIDI puis utilise l'onglet AKAI / SYSEX.")

    def refresh_devices(self):
        inputs = self._input_devices()
        outputs = self._output_devices()
        if hasattr(self, "midi_cb"):
            self.midi_cb.config(values=inputs)
            chosen = self._pick_akai(inputs)
            if chosen and self.midi_var.get() not in inputs:
                self.midi_var.set(chosen)
        if hasattr(self, "sysex_out_cb"):
            self.sysex_out_cb.config(values=outputs)
            chosen = self._pick_akai(outputs)
            if chosen and self.sysex_out_var.get() not in outputs:
                self.sysex_out_var.set(chosen)

    def toggle_midi(self):
        if self.midi_running:
            self.midi_stop.set()
            self.midi_running = False
            self.midi_btn.config(text="▶ Ecouter", bg=self.C["green"])
            self._append(self.midi_log, "Arret demande.")
            return
        device = self.midi_var.get()
        if not device or device == "Aucun":
            self._append(self.midi_log, "[ERR] Aucun input MIDI.")
            return
        self.midi_stop.clear()
        self.midi_running = True
        self.midi_btn.config(text="■ Stop", bg=self.C["red"], fg="white")
        threading.Thread(target=self._midi_thread, args=(device,), daemon=True).start()

    def _midi_thread(self, device):
        self.root.after(0, self._append, self.midi_log, f"Connexion MIDI input : {device}")
        try:
            with mido.open_input(device) as port:
                while not self.midi_stop.is_set():
                    msg = port.poll()
                    if msg:
                        self.root.after(0, self._append, self.midi_log, str(msg))
                    time.sleep(0.001)
        except Exception as e:
            self.root.after(0, self._append, self.midi_log, f"[ERR] {e}")
        finally:
            self.midi_running = False
            self.root.after(0, self.midi_btn.config, {"text": "▶ Ecouter", "bg": self.C["green"], "fg": self.C["bg"]})

    def clear_midi(self):
        self.midi_log.config(state="normal")
        self.midi_log.delete("1.0", "end")
        self.midi_log.config(state="disabled")

    # AKAI / SYSEX -------------------------------------------------------------
    def _build_sysex(self, parent):
        C = self.C
        row = tk.Frame(parent, bg=C["bg"], pady=8)
        row.pack(fill="x", padx=10)
        tk.Label(row, text="Output", fg=C["dim"], bg=C["bg"]).pack(side="left")
        self.sysex_out_var = tk.StringVar()
        self.sysex_out_cb = ttk.Combobox(row, textvariable=self.sysex_out_var, values=self._output_devices(), width=36, state="readonly", style="H.TCombobox")
        self.sysex_out_cb.pack(side="left", padx=8)
        tk.Button(row, text="Identity Request", bg=C["accent2"], fg=C["bg"], relief="flat", command=self.send_identity_request).pack(side="left", padx=4)

        info = (
            "Test sortie MIDI/SysEx pour l'Akai. Le controle exact de l'ecran MPK est firmware-specific :\n"
            "commence par Identity Request + MIDI RAW pour verifier que l'output et les reponses SysEx fonctionnent."
        )
        tk.Label(parent, text=info, fg=C["dim"], bg=C["bg"], justify="left", font=("Courier", 8)).pack(anchor="w", padx=12, pady=(0, 8))

        raw = tk.LabelFrame(parent, text=" SysEx brut ", bg=C["bg"], fg=C["accent"], font=("Courier", 8, "bold"))
        raw.pack(fill="x", padx=10, pady=4)
        self.sysex_raw_var = tk.StringVar(value="F0 7E 7F 06 01 F7")
        self._entry(raw, self.sysex_raw_var, 72).pack(side="left", fill="x", expand=True, padx=8, pady=8)
        tk.Button(raw, text="Envoyer", bg=C["green"], fg=C["bg"], relief="flat", command=self.send_raw_sysex).pack(side="left", padx=8)

        text_box = tk.LabelFrame(parent, text=" Texte ecran experimental ", bg=C["bg"], fg=C["accent"], font=("Courier", 8, "bold"))
        text_box.pack(fill="x", padx=10, pady=4)
        line1 = tk.Frame(text_box, bg=C["bg"])
        line1.pack(fill="x", padx=8, pady=(8, 2))
        tk.Label(line1, text="Header", fg=C["dim"], bg=C["bg"]).pack(side="left")
        self.sysex_header_var = tk.StringVar(value="47 7F 7C")
        self._entry(line1, self.sysex_header_var, 24).pack(side="left", padx=8)
        tk.Label(line1, text="payload ASCII 7-bit", fg=C["dim"], bg=C["bg"]).pack(side="left")

        line2 = tk.Frame(text_box, bg=C["bg"])
        line2.pack(fill="x", padx=8, pady=(2, 8))
        tk.Label(line2, text="Texte", fg=C["dim"], bg=C["bg"]).pack(side="left")
        self.sysex_text_var = tk.StringVar(value="HEXPAD TEST")
        self._entry(line2, self.sysex_text_var, 40).pack(side="left", fill="x", expand=True, padx=8)
        tk.Button(line2, text="Tester", bg=C["accent"], fg=C["bg"], relief="flat", command=self.send_experimental_text).pack(side="left")

        tk.Label(parent, text="Note : si rien ne s'affiche, ce n'est pas forcement une erreur : il faudra capturer/identifier le protocole ecran exact.", fg=C["dim"], bg=C["bg"], justify="left", font=("Courier", 8)).pack(anchor="w", padx=12, pady=(4, 0))
        self.sysex_log = self._logbox(parent)
        self.refresh_devices()
        self._append(self.sysex_log, "Pret. Selectionne l'output AKAI puis envoie Identity Request ou un SysEx brut.")

    def _hex_to_bytes(self, text):
        clean = text.replace(",", " ").replace("0x", " ").replace("0X", " ")
        parts = [p for p in clean.split() if p]
        values = []
        for p in parts:
            values.append(int(p, 16))
        if not values:
            raise ValueError("SysEx vide")
        if values[0] == 0xF0:
            values = values[1:]
        if values and values[-1] == 0xF7:
            values = values[:-1]
        for v in values:
            if v < 0 or v > 127:
                raise ValueError(f"Octet invalide pour data SysEx 7-bit: {v:02X}")
        return values

    def _send_sysex_data(self, data, label="SysEx"):
        out = self.sysex_out_var.get()
        if not out or out == "Aucun":
            self._append(self.sysex_log, "[ERR] Aucun output MIDI.")
            return
        try:
            msg = mido.Message("sysex", data=data)
            with mido.open_output(out) as port:
                port.send(msg)
            as_hex = "F0 " + " ".join(f"{b:02X}" for b in data) + " F7"
            self._append(self.sysex_log, f"[{label}] -> {out}")
            self._append(self.sysex_log, as_hex)
        except Exception as e:
            self._append(self.sysex_log, f"[ERR] {e}")

    def send_identity_request(self):
        # Universal Non-Realtime Identity Request: F0 7E 7F 06 01 F7
        self._send_sysex_data([0x7E, 0x7F, 0x06, 0x01], "Identity Request")
        self._append(self.sysex_log, "Si l'Akai repond, regarde l'onglet MIDI RAW en ecoute sur l'input AKAI.")

    def send_raw_sysex(self):
        try:
            data = self._hex_to_bytes(self.sysex_raw_var.get())
            self._send_sysex_data(data, "Raw")
        except Exception as e:
            self._append(self.sysex_log, f"[ERR] {e}")

    def send_experimental_text(self):
        try:
            header = self._hex_to_bytes(self.sysex_header_var.get())
            text = self.sysex_text_var.get().encode("ascii", errors="replace")[:32]
            payload = [b & 0x7F for b in text]
            self._send_sysex_data(header + payload, "Text experimental")
        except Exception as e:
            self._append(self.sysex_log, f"[ERR] {e}")

    # HTTP --------------------------------------------------------------------
    def _build_http(self, parent):
        row = tk.Frame(parent, bg=self.C["bg"], pady=8)
        row.pack(fill="x", padx=10)
        self.http_method = tk.StringVar(value="GET")
        ttk.Combobox(row, textvariable=self.http_method, values=HTTP_METHODS, width=8, state="readonly", style="H.TCombobox").pack(side="left")
        self.http_url = tk.StringVar(value="http://localhost:8080/test")
        self._entry(row, self.http_url, 48).pack(side="left", fill="x", expand=True, padx=8)
        tk.Button(row, text="▶ Envoyer", bg=self.C["green"], fg=self.C["bg"], relief="flat", command=self.send_http).pack(side="left")
        row2 = tk.Frame(parent, bg=self.C["bg"])
        row2.pack(fill="x", padx=10)
        tk.Label(row2, text="Body JSON", fg=self.C["dim"], bg=self.C["bg"]).pack(side="left")
        self.http_body = tk.StringVar(value="")
        self._entry(row2, self.http_body, 60).pack(side="left", fill="x", expand=True, padx=8)
        self.http_log = self._logbox(parent)

    def send_http(self):
        import urllib.request, urllib.error
        method = self.http_method.get()
        url = self.http_url.get().strip()
        body = self.http_body.get().strip()
        if not url:
            self._append(self.http_log, "[ERR] URL vide")
            return
        self._append(self.http_log, f"-> {method} {url}")
        def run():
            try:
                data = body.encode("utf-8") if body else None
                req = urllib.request.Request(url, data=data, method=method)
                if data:
                    req.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(req, timeout=5) as r:
                    resp = r.read().decode(errors="replace")[:800]
                    self.root.after(0, self._append, self.http_log, f"[{r.status}] {resp}")
            except urllib.error.HTTPError as e:
                self.root.after(0, self._append, self.http_log, f"[HTTP {e.code}] {e.reason}")
            except Exception as e:
                self.root.after(0, self._append, self.http_log, f"[ERR] {e}")
        threading.Thread(target=run, daemon=True).start()

    # WEBSOCKET ---------------------------------------------------------------
    def _build_ws(self, parent):
        row = tk.Frame(parent, bg=self.C["bg"], pady=8)
        row.pack(fill="x", padx=10)
        self.ws_url = tk.StringVar(value="ws://localhost:8765")
        self._entry(row, self.ws_url, 40).pack(side="left", fill="x", expand=True, padx=6)
        self.ws_btn = tk.Button(row, text="⚡ Connecter", bg=self.C["green"], fg=self.C["bg"], relief="flat", command=self.ws_connect)
        self.ws_btn.pack(side="left", padx=4)
        row2 = tk.Frame(parent, bg=self.C["bg"])
        row2.pack(fill="x", padx=10)
        self.ws_msg = tk.StringVar(value='{"action":"ping"}')
        self._entry(row2, self.ws_msg, 54).pack(side="left", fill="x", expand=True, padx=6)
        tk.Button(row2, text="▶ Envoyer", bg=self.C["accent2"], fg=self.C["bg"], relief="flat", command=self.ws_send).pack(side="left")
        self.ws_log = self._logbox(parent)

    def ws_connect(self):
        if self.ws_sock:
            try:
                self.ws_sock.close()
            except Exception:
                pass
            self.ws_sock = None
            self.ws_btn.config(text="⚡ Connecter", bg=self.C["green"], fg=self.C["bg"])
            self._append(self.ws_log, "Deconnecte.")
            return
        try:
            import websocket
            self.ws_sock = websocket.create_connection(self.ws_url.get().strip(), timeout=3)
            self.ws_btn.config(text="■ Deconnecter", bg=self.C["red"], fg="white")
            self._append(self.ws_log, "Connecte.")
        except Exception as e:
            self._append(self.ws_log, f"[ERR] {e}")

    def ws_send(self):
        if not self.ws_sock:
            self._append(self.ws_log, "[ERR] Non connecte.")
            return
        msg = self.ws_msg.get()
        try:
            self.ws_sock.send(msg)
            self._append(self.ws_log, f"-> {msg}")
        except Exception as e:
            self._append(self.ws_log, f"[ERR] {e}")

    def close(self):
        self.midi_stop.set()
        if self.ws_sock:
            try:
                self.ws_sock.close()
            except Exception:
                pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    DebugTestWindow(root)
    root.mainloop()
