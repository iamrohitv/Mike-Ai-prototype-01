import queue
import re
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from interfaces.text.cli import Mike

BG = "#05060f"
PANEL = "#0d1124"
PANEL_EDGE = "#1c2240"
CYAN = "#00f0ff"
VIOLET = "#7c4dff"
PINK = "#ff4d8d"
TEXT = "#e6ecff"
DIM = "#8b93b8"

TAG_RE = re.compile(r"^\s*\(brain: .*\)$")


def clean(text):
    return TAG_RE.sub("", text).strip()


class MikeDesktop(tk.Tk):
    def __init__(self, hidden=False):
        super().__init__()
        self.title("MIKE")
        self.geometry("1100x700")
        self.configure(bg=BG)
        self.minsize(820, 520)

        self.mike = Mike()
        self.state_label_text = tk.StringVar(value="initializing...")
        self._state = "idle"
        self._tray = None
        self._tray_running = threading.Event()

        self.rec_queue = queue.Queue()
        self.running = threading.Event()
        self.running.set()

        self._build_layout()
        self._bind_resize()
        self._start_anim()
        self._start_tray()
        self.protocol("WM_DELETE_WINDOW", self._hide_to_tray)
        if hidden:
            self.withdraw()
        self.after(600, self._start_voice)

    # ---------- layout ----------
    def _build_layout(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        self.visual = tk.Frame(self, bg=BG)
        self.visual.grid(row=0, column=0, sticky="nsew")

        self.canvas = tk.Canvas(
            self.visual, bg=BG, highlightthickness=0, bd=0
        )
        self.canvas.pack(fill="both", expand=True)

        self.chat_panel = tk.Frame(self, bg=PANEL, bd=1, relief="solid",
                                   highlightbackground=PANEL_EDGE)
        self.chat_panel.grid(row=0, column=1, sticky="ns")

        self.chat_header = tk.Label(
            self.chat_panel, text="EXCHANGE", bg=PANEL, fg=CYAN,
            font=("Segoe UI", 10, "bold"), padx=14, pady=12
        )
        self.chat_header.pack(fill="x")

        self.chat = tk.Text(
            self.chat_panel, bg=PANEL, fg=TEXT, bd=0, wrap="word",
            font=("Segoe UI", 11), padx=12, pady=8,
            state="disabled", cursor="arrow",
            highlightthickness=0,
        )
        self.chat.pack(fill="both", expand=True)
        self.chat.tag_configure("user", foreground=CYAN, lmargin1=4, lmargin2=4)
        self.chat.tag_configure("mike", foreground=VIOLET, lmargin1=4, lmargin2=4)
        self.chat.tag_configure("name_user", foreground="#aef5ff", font=("Segoe UI", 10, "bold"))
        self.chat.tag_configure("name_mike", foreground="#c9b6ff", font=("Segoe UI", 10, "bold"))
        self.chat.tag_configure("state", foreground=DIM, font=("Segoe UI", 10, "italic"),
                                spacing1=8, spacing3=8)

        self._append_chat("state", "voice exchange ready")
        self._update_chat_width()

    def _bind_resize(self):
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, _event=None):
        self._update_chat_width()

    def _update_chat_width(self):
        width = max(240, int(self.winfo_width() * 0.2))
        self.chat_panel.configure(width=width)
        self.chat.configure(width=int(width / 8))

    # ---------- chat ----------
    def _append_chat(self, kind, text):
        self.chat.configure(state="normal")
        if kind in ("user", "mike"):
            name = "YOU" if kind == "user" else "MIKE"
            name_tag = f"name_{kind}"
            self.chat.insert("end", f"{name}\n", (name_tag,))
            self.chat.insert("end", f"{text}\n\n", (kind,))
        else:
            self.chat.insert("end", f"— {text} —\n", (kind,))
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _show_user(self, text):
        self._append_chat("user", text)

    def _show_mike(self, text):
        self._append_chat("mike", clean(text))
        self._set_state("speaking")

    # ---------- orb ----------
    def _start_anim(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width() or 800
        h = self.canvas.winfo_height() or 600
        self._draw_orb(w, h)
        self._frame = 0
        self.after(50, self._anim_tick)

    def _draw_orb(self, w, h):
        cx, cy = w // 2, h // 2
        self.orb_r = min(w, h) * 0.16
        self.cx, self.cy = cx, cy
        self.canvas.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill=CYAN, outline="")
        self.canvas.create_text(
            cx, h - 46, text="MIKE", fill=CYAN, font=("Segoe UI", 26, "bold"),
            justify="center",
        )
        self.state_label = self.canvas.create_text(
            cx, h - 14, text="", fill=DIM, font=("Segoe UI", 11),
            justify="center",
        )

    def _anim_tick(self):
        if not self.running.is_set():
            return
        self._frame += 1
        t = self._frame / 12.0
        w = self.canvas.winfo_width() or 800
        h = self.canvas.winfo_height() or 600
        if w < 50 or h < 50:
            self.after(50, self._anim_tick)
            return
        self.canvas.delete("ring")
        cx, cy = w // 2, h // 2
        base = self.orb_r
        state = self._current_state()
        colors = {"listening": CYAN, "thinking": VIOLET, "speaking": PINK,
                  "idle": CYAN}[state]
        for i, (scale, phase, width, alpha) in enumerate([
            (1.0, 0.0, 2, 1.0),
            (1.35, 1.2, 2, 0.8),
            (1.75, 2.4, 1, 0.55),
            (2.2, 0.6, 1, 0.35),
        ]):
            r = base * scale
            rr = r * (0.85 + 0.15 * _tri(t + phase))
            x0, y0 = cx - rr, cy - rr
            x1, y1 = cx + rr, cy + rr
            self.canvas.create_oval(x0, y0, x1, y1, outline=_blend(BG, colors, alpha),
                                    width=width, tags="ring")
        core_r = base * (0.42 + 0.03 * _tri(t))
        x0, y0 = cx - core_r, cy - core_r
        x1, y1 = cx + core_r, cy + core_r
        self.canvas.create_oval(x0, y0, x1, y1, fill=colors,
                                outline=colors, tags="ring")
        self.canvas.create_oval(x0 + core_r * 0.28, y0 + core_r * 0.28,
                                x1 - core_r * 0.28, y1 - core_r * 0.28,
                                fill=BG, outline="", tags="ring")
        self.after(50, self._anim_tick)

    def _current_state(self):
        return self._state

    def _set_state(self, state):
        self._state = state
        label = {
            "listening": "LISTENING — speak to me",
            "thinking": "THINKING...",
            "speaking": "SPEAKING",
            "idle": "",
        }[state]
        self.state_label_text.set(label)
        try:
            self.canvas.itemconfigure(self.state_label, text=label)
        except (tk.TclError, AttributeError):
            pass

    # ---------- tray ----------
    def _start_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError:
            return
        image = Image.new("RGB", (64, 64), BG)
        draw = ImageDraw.Draw(image)
        draw.ellipse((8, 8, 56, 56), outline=CYAN, width=4)
        draw.ellipse((20, 20, 44, 44), fill=CYAN)
        menu = pystray.Menu(
            pystray.MenuItem("Open Mike", self._show_from_tray, default=True),
            pystray.MenuItem("Quit", self._quit),
        )
        self._tray = pystray.Icon("mike", image, "MIKE", menu)
        self._tray_running.set()
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _hide_to_tray(self):
        if self._tray is not None:
            self.withdraw()
        else:
            self.destroy()

    def _show_from_tray(self, icon=None, item=None):
        self.after(0, self.deiconify)
        self.after(0, self.lift)
        self.after(0, self.focus_force)

    def _quit(self, icon=None, item=None):
        self.running.clear()
        if self._tray is not None:
            self._tray.stop()
        self.after(0, self.destroy)

    def _greeting(self):
        from datetime import datetime
        hour = datetime.now().hour
        if hour < 12:
            part = "morning"
        elif hour < 17:
            part = "afternoon"
        else:
            part = "evening"
        recent = self.mike.memory.recent_memories(limit=3)
        if recent:
            last = recent[0]["content"].strip()
            return (
                f"Good {part}, Rohit. I'm Mike. "
                f"Last time we spoke, you were on '{last}'. I'm listening."
            )
        return (
            f"Good {part}, Rohit. I'm Mike, your personal counterpart. "
            "I'm here and I'm listening."
        )

    # ---------- voice ----------
    def _start_voice(self):
        self._set_state("listening")
        threading.Thread(target=self._voice_loop, daemon=True).start()

    def _voice_loop(self):
        import speech_recognition as sr
        import pyttsx3

        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        preferred = None
        for v in voices:
            if "zira" in v.id.lower() or "hazel" in v.id.lower():
                preferred = v
                break
        if preferred:
            engine.setProperty("voice", preferred.id)
        rate = engine.getProperty("rate")
        engine.setProperty("rate", rate - 20)

        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.8

        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1.0)
            greeting = self._greeting()
            self.after(0, lambda: self._append_chat("mike", greeting))
            self.after(0, lambda: self._set_state("speaking"))
            engine.say(greeting)
            engine.runAndWait()
            self.after(0, lambda: self._set_state("listening"))
            while self.running.is_set():
                try:
                    audio = recognizer.listen(source, timeout=3, phrase_time_limit=30)
                except sr.WaitTimeoutError:
                    continue
                except Exception:
                    continue
                try:
                    text = recognizer.recognize_google(audio).strip()
                except sr.UnknownValueError:
                    continue
                except sr.RequestError:
                    self.after(0, lambda: self._append_chat(
                        "state", "speech recognition unreachable"))
                    continue
                if not text:
                    continue
                self.after(0, lambda t=text: self._show_user(t))
                self.after(0, lambda: self._set_state("thinking"))
                try:
                    reply = self.mike.handle(text)
                except Exception as exc:  # noqa: BLE001
                    reply = f"I hit an issue while thinking: {exc}"
                self.after(0, lambda r=reply: self._show_mike(r))
                engine.say(clean(reply))
                engine.runAndWait()
                self.after(0, lambda: self._set_state("listening"))


def _tri(x):
    val = (x % 1.0) * 2.0
    return 1.0 - abs(val - 1.0)


def _blend(c1, c2, alpha):
    def comp(a, b):
        return int(a + (b - a) * alpha)
    r1, g1, b1 = (int(c1[i:i+2], 16) for i in (1, 3, 5))
    r2, g2, b2 = (int(c2[i:i+2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % (comp(r1, r2), comp(g1, g2), comp(b1, b2))


def main():
    hidden = "--hidden" in sys.argv
    app = MikeDesktop(hidden=hidden)
    app.mainloop()


if __name__ == "__main__":
    main()
