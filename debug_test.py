import json
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext

import mido

from modules.themes import get as get_theme

VERSION = "2.3.0"
HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]


class DebugTestWindow:
    def __init__(self, root):
        self.root = root
        self.C = get_theme("dark")
        self.midi_running = False
        self.midi_stop = threading.Event()
        self.ws_sock = None

        root.title(f"HexPad Debug / Test v{VERSION}")
        root.geometry("720x620")
        root.minsize(560, 460)
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
        self.tab_http = tk.Frame(self.nb, bg=C["bg"])
        self.tab_ws = tk.Frame(self.nb, bg=C["bg"])
        self.nb.add(self.tab_midi, text=" MIDI RAW ")
        self.nb.add(self.tab_http, text=" HTTP ")
        self.nb.add(self.tab_ws, text=" WEBSOCKET ")
        self._build_midi(self.tab_midi)
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

    def _build_midi(self, parent):
        row = tk.Frame(parent, bg=self.C["bg"], pady=8)
        row.pack(fill="x", padx=10)
        tk.Label(row, text="Device", fg=self.C["dim"], bg=self.C["bg"]).pack(side="left")
        self.midi_var = tk.StringVar()
        self.midi_cb = ttk.Combobox(row, textvariable=self.midi_var, values=mido.get_input_names(), width=34, state="readonly", style="H.TCombobox")
        self.midi_cb.pack(side="left", padx=8)
        self.refresh_devices()
        self.midi_btn = tk.Button(row, text="▶ Ecouter", bg=self.C["green"], fg=self.C["bg"], relief="flat", command=self.toggle_midi)
        self.midi_btn.pack(side="left", padx=4)
        tk.Button(row, text="✕ Vider", bg=self.C["btn"], fg=self.C["dim"], relief="flat", command=self.clear_midi).pack(side="left", padx=4)
        self.midi_log = self._logbox(parent)
        self._append(self.midi_log, "Selectionne un device puis clique Ecouter.")

    def refresh_devices(self):
        devices = mido.get_input_names() or ["Aucun"]
        if hasattr(self, "midi_cb"):
            self.midi_cb.config(values=devices)
            if devices and devices[0] != "Aucun":
                current = self.midi_var.get()
                if current not in devices:
                    for d in devices:
                        if any(x in d.lower() for x in ("mpk", "mini", "akai", "pad")):
                            self.midi_var.set(d)
                            return
                    self.midi_var.set(devices[0])

    def toggle_midi(self):
        if self.midi_running:
            self.midi_stop.set()
            self.midi_running = False
            self.midi_btn.config(text="▶ Ecouter", bg=self.C["green"])
            self._append(self.midi_log, "Arret demande.")
            return
        device = self.midi_var.get()
        if not device or device == "Aucun":
            self._append(self.midi_log, "[ERR] Aucun device MIDI.")
            return
        self.midi_stop.clear()
        self.midi_running = True
        self.midi_btn.config(text="■ Stop", bg=self.C["red"], fg="white")
        threading.Thread(target=self._midi_thread, args=(device,), daemon=True).start()

    def _midi_thread(self, device):
        self.root.after(0, self._append, self.midi_log, f"Connexion MIDI : {device}")
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
        self._append(self.http_log, f"→ {method} {url}")
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
            self._append(self.ws_log, f"→ {msg}")
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
