#!/usr/bin/env python3
"""
Visualizer Bridge — fenetre Tkinter temps reel ~30fps
  - Barres de velocite 8 pads (fade progressif)
  - Piano roll notes actives
  - Historique CC (encodeurs/joystick)

Config : { "mode": "visualizer", "show_piano": true, "show_cc": true }
"""
import tkinter as tk
import threading
import collections

NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
PAD_NOTES  = [36,37,38,39,40,41,42,43]

CV = {
    "bg":     "#0a0a12",
    "panel":  "#11111f",
    "accent": "#00ffe7",
    "dim":    "#333355",
    "yellow": "#ffd700",
    "pad":    "#7f00ff",
}


class VisualizerBridge:
    def __init__(self, config):
        self.show_piano   = config.get("show_piano", True)
        self.show_cc      = config.get("show_cc", True)
        self.active_notes = {}
        self.pad_vel      = {str(n): 0 for n in PAD_NOTES}
        self.cc_history   = collections.deque(maxlen=32)
        self._win         = None
        self._canvas      = None
        threading.Thread(target=self._launch_window, daemon=True).start()

    def _launch_window(self):
        root = tk.Tk()
        root.title("HexPad Visualizer")
        root.configure(bg=CV["bg"])
        root.geometry("620x360")
        self._win    = root
        self._canvas = tk.Canvas(root, bg=CV["bg"], highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        self._loop()
        root.mainloop()

    def _loop(self):
        self._draw()
        if self._win:
            self._win.after(33, self._loop)

    def _draw(self):
        c = self._canvas
        c.delete("all")
        w = c.winfo_width()  or 620
        h = c.winfo_height() or 360

        c.create_text(10, 8, text="\u2b21 HexPad Visualizer", anchor="nw",
                      fill=CV["accent"], font=("Courier", 10, "bold"))

        # ─ Pad bars
        bar_w   = (w - 40) // 8
        bar_max = h // 2 - 40
        c.create_text(10, 26, text="PADS", anchor="nw", fill=CV["dim"], font=("Courier", 8))
        for i, note in enumerate(PAD_NOTES):
            ns  = str(note)
            vel = self.pad_vel.get(ns, 0)
            bh  = int(vel / 127 * bar_max)
            x0  = 20 + i * bar_w
            x1  = x0 + bar_w - 4
            base_y = 42 + bar_max
            c.create_rectangle(x0, 42, x1, base_y - bh, fill=CV["panel"], outline="")
            # Color: low vel=purple, high vel=cyan
            t = vel / 127
            r = int((1-t)*0x7f)
            g = int(t*0xff)
            b_col = int(t*0xe7 + (1-t)*0xff)
            c.create_rectangle(x0, base_y - bh, x1, base_y,
                               fill=f"#{r:02x}{g:02x}{b_col:02x}", outline="")
            c.create_text(x0 + (bar_w-4)//2, base_y + 8,
                          text=f"P{i+1}", fill=CV["dim"], font=("Courier", 7))
            if vel > 0:
                self.pad_vel[ns] = max(0, vel - 5)

        # ─ Piano roll
        if self.show_piano:
            roll_y = h // 2 + 20
            c.create_text(10, roll_y - 14, text="PIANO ROLL",
                          anchor="nw", fill=CV["dim"], font=("Courier", 8))
            roll_h = h // 3
            for note, vel in list(self.active_notes.items()):
                x   = 20 + (note - 21) * (w - 40) // 88
                bh2 = int(vel / 127 * roll_h)
                c.create_rectangle(x, roll_y + roll_h - bh2, x + 7,
                                   roll_y + roll_h, fill=CV["accent"], outline="")
                c.create_text(x + 3, roll_y + roll_h + 7,
                              text=NOTE_NAMES[note % 12],
                              fill=CV["dim"], font=("Courier", 6))

        # ─ CC history
        if self.show_cc and self.cc_history:
            cc_y = h - 28
            c.create_text(10, cc_y - 13, text="CC",
                          anchor="nw", fill=CV["dim"], font=("Courier", 8))
            hist = list(self.cc_history)[-16:]
            seg  = (w - 40) // max(len(hist), 1)
            for i, (ctrl, val) in enumerate(hist):
                x   = 20 + i * seg
                bh3 = int(val / 127 * 22)
                c.create_rectangle(x, cc_y - bh3, x + seg - 2, cc_y,
                                   fill=CV["yellow"], outline="")

    def handle(self, msg):
        if msg.type == "note_on":
            if msg.velocity > 0:
                self.active_notes[msg.note] = msg.velocity
                if str(msg.note) in self.pad_vel:
                    self.pad_vel[str(msg.note)] = msg.velocity
            else:
                self.active_notes.pop(msg.note, None)
        elif msg.type == "note_off":
            self.active_notes.pop(msg.note, None)
        elif msg.type == "control_change":
            self.cc_history.append((msg.control, msg.value))
