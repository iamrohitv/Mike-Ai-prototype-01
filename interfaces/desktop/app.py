import math
import queue
import re
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from interfaces.desktop.hud import (
    arc_coords,
    blend,
    format_battery,
    format_percent,
    particle_field,
    pulse_radius,
    state_color,
    state_status,
    tri,
    waveform_heights,
)
from interfaces.text.cli import Mike

BG = "#020409"
BG_DEEP = "#01030a"
PANEL = "#0b1120"
PANEL_EDGE = "#1a2542"
GRID = "#0a1226"
CYAN = "#00e5ff"
VIOLET = "#7c4dff"
PINK = "#ff2e88"
TEXT = "#e6ecff"
DIM = "#8b93b8"
GLASS = "#0b1120"

TAG_RE = re.compile(r"^\s*\(brain: .*\)$")

WAKE_WORDS = ["hey mike", "okay mike", "ok mike", "hello mike", "mike"]
FILLERS = {"uh", "um", "umm", "hmm", "ah", "er", "thanks", "ok", "okay"}


def clean(text):
    return TAG_RE.sub("", text).strip()


def strip_wake(text):
    lowered = text.lower()
    for wake in WAKE_WORDS:
        if lowered.startswith(wake):
            rest = text[len(wake):].strip(" ,.!?")
            return rest or text
    return text


class MikeDesktop(tk.Tk):
    def __init__(self, hidden=False):
        super().__init__()
        self.title("MIKE")
        self.geometry("1200x760")
        self.configure(bg=BG)
        self.minsize(900, 560)

        self.mike = Mike()
        self.state_label_text = tk.StringVar(value="initializing...")
        self._state = "idle"
        self._tray = None
        self._tray_running = threading.Event()
        self._awareness = self._start_awareness()
        self._wire_tray_notifications()

        self.rec_queue = queue.Queue()
        self.running = threading.Event()
        self.running.set()

        self._build_layout()
        self._bind_resize()
        self._start_anim()
        self._start_metrics()
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

        self._build_dock()
        self._build_metrics()

        self.chat_panel = tk.Frame(self, bg=PANEL, bd=1, relief="solid",
                                   highlightbackground=PANEL_EDGE)
        self.chat_panel.grid(row=0, column=1, sticky="ns")

        self.chat_header = tk.Label(
            self.chat_panel, text="◈ EXCHANGE", bg=PANEL, fg=CYAN,
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

        self.input_bar = tk.Frame(self.chat_panel, bg=PANEL)
        self.input_bar.pack(fill="x", side="bottom")

        self.text_input = tk.Entry(
            self.input_bar, bg=PANEL_EDGE, fg=TEXT, bd=0, relief="flat",
            font=("Segoe UI", 11), insertbackground=CYAN,
            highlightthickness=1, highlightbackground=PANEL_EDGE,
            highlightcolor=CYAN,
        )
        self.text_input.pack(fill="x", padx=8, pady=(6, 4))
        self.text_input.insert(0, "type here or speak...")
        self.text_input.bind("<FocusIn>", lambda e: self.text_input.delete(0, "end"))
        self.text_input.bind("<Return>", lambda e: self._send_text())

        self.text_send = tk.Button(
            self.input_bar, text="SEND", bg=PANEL_EDGE, fg=CYAN,
            bd=0, relief="flat", activebackground=CYAN, activeforeground=BG,
            font=("Segoe UI", 9, "bold"), cursor="hand2",
        )
        self.text_send.pack(fill="x", padx=8, pady=(0, 8))
        self.text_send.configure(command=self._send_text)

        self._append_chat("state", "voice exchange ready")
        self._update_chat_width()

    def _build_dock(self):
        self.dock = tk.Frame(self.visual, bg=BG)
        self.dock.pack(fill="x", side="bottom", pady=(0, 14))

        def dock_button(label, command):
            return tk.Button(
                self.dock, text=label, bg=BG, fg=CYAN, bd=0,
                relief="flat", padx=18, pady=6, cursor="hand2",
                activebackground=CYAN, activeforeground=BG,
                highlightthickness=1, highlightbackground=GRID,
                highlightcolor=blend(BG, CYAN, 0.6),
                font=("Consolas", 9, "bold"), command=command,
            )

        for label, cmd in [
            ("◈ BRIEFING", self._dock_briefing),
            ("▣ SCREENSHOT", self._dock_screenshot),
            ("◉ COMPACT", self._dock_compact),
            ("– HIDE", self._hide_to_tray),
        ]:
            b = dock_button(label, cmd)
            b.pack(side="left", padx=8, expand=True)

    def _build_metrics(self):
        self.metrics = tk.Frame(
            self.canvas, bg=PANEL, highlightthickness=1,
            highlightbackground=GRID, bd=0,
        )
        self.metrics.place(x=18, y=18)
        tk.Label(
            self.metrics, text="TELEMETRY", bg=PANEL, fg=DIM,
            font=("Consolas", 8, "bold"), padx=10, pady=4,
        ).pack(anchor="w")
        self.metric_vars = {}
        for key, label in [
            ("cpu", "CPU"),
            ("mem", "MEM"),
            ("disk", "DISK"),
            ("battery", "BATT"),
            ("tasks", "TASKS"),
        ]:
            row = tk.Frame(self.metrics, bg=PANEL)
            row.pack(fill="x", padx=10, pady=1)
            tk.Label(row, text=label, bg=PANEL, fg=DIM, width=7,
                     anchor="w", font=("Consolas", 9)).pack(side="left")
            var = tk.StringVar(value="—")
            tk.Label(row, textvariable=var, bg=PANEL, fg=CYAN,
                     anchor="e", font=("Consolas", 9)).pack(side="right")
            self.metric_vars[key] = var

    def _bind_resize(self):
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, _event=None):
        self._update_chat_width()

    def _update_chat_width(self):
        width = max(240, int(self.winfo_width() * 0.2))
        self.chat_panel.configure(width=width)
        self.chat.configure(width=int(width / 8))

    # ---------- metrics ----------
    def _start_metrics(self):
        self._metrics_tick()

    def _metrics_tick(self):
        try:
            import psutil
            self.metric_vars["cpu"].set(format_percent(psutil.cpu_percent(interval=0.5)))
            self.metric_vars["mem"].set(format_percent(psutil.virtual_memory().percent))
            try:
                self.metric_vars["disk"].set(format_percent(psutil.disk_usage("C:\\").percent))
            except (OSError, PermissionError):
                self.metric_vars["disk"].set("—")
            battery = psutil.sensors_battery()
            if battery is not None:
                self.metric_vars["battery"].set(
                    format_battery(battery.percent, battery.power_plugged)
                )
            else:
                self.metric_vars["battery"].set("—")
            pending = self.mike.memory.recent_pending_tasks(limit=100)
            self.metric_vars["tasks"].set(str(len(pending)))
        except ImportError:
            pass
        except Exception:  # noqa: BLE001
            pass
        if self.running.is_set():
            self.after(2000, self._metrics_tick)

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

    def _send_text(self):
        text = self.text_input.get().strip()
        if not text:
            return
        self.text_input.delete(0, "end")
        self._show_user(text)
        self._set_state("thinking")
        threading.Thread(target=self._process_text, args=(text,), daemon=True).start()

    def _process_text(self, text):
        try:
            reply = self.mike.handle(text)
        except Exception as exc:  # noqa: BLE001
            reply = f"I hit an issue while thinking: {exc}"
        self.after(0, lambda r=reply: self._show_mike(r))
        threading.Thread(target=self._speak_async, args=(reply,), daemon=True).start()

    def _show_mike(self, text):
        self._append_chat("mike", clean(text))
        self._set_state("speaking")

    # ---------- dock actions ----------
    def _dock_briefing(self):
        threading.Thread(target=self._run_dock_briefing, daemon=True).start()

    def _run_dock_briefing(self):
        try:
            reply = self.mike.briefings.build()
            if not reply:
                reply = "Nothing to brief you on right now."
        except Exception as exc:  # noqa: BLE001
            reply = f"Briefing failed: {exc}"
        self.after(0, lambda: self._show_mike(reply))
        threading.Thread(target=self._speak_async, args=(reply,), daemon=True).start()

    def _dock_screenshot(self):
        threading.Thread(target=self._run_dock_screenshot, daemon=True).start()

    def _run_dock_screenshot(self):
        tool = next((t for t in self.mike.tools if t.name == "screenshot"), None)
        if tool is None:
            reply = "Screenshot tool isn't available."
        else:
            try:
                reply = tool.run("take a screenshot")
            except Exception as exc:  # noqa: BLE001
                reply = f"Screenshot failed: {exc}"
        self.after(0, lambda: self._show_mike(reply))

    def _dock_compact(self):
        threading.Thread(target=self._run_dock_compact, daemon=True).start()

    def _run_dock_compact(self):
        try:
            reply = self.mike.handle("compact memory")
        except Exception as exc:  # noqa: BLE001
            reply = f"Compact failed: {exc}"
        self.after(0, lambda: self._show_mike(reply))

    # ---------- HUD orb ----------
    def _start_anim(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width() or 880
        h = self.canvas.winfo_height() or 620
        self._draw_static_hud(w, h)
        self._frame = 0
        self._particles = particle_field(42, count=26)
        self.after(50, self._anim_tick)

    def _draw_static_hud(self, w, h):
        self._hud_w, self._hud_h = w, h
        margin = 12
        inset = 26
        self.canvas.create_rectangle(
            margin, margin, w - margin, h - margin,
            outline=GRID, width=1, tags="static",
        )
        bracket_len = 34
        for cx, cy, dx, dy in [
            (margin, margin, 1, 1),
            (w - margin, margin, -1, 1),
            (margin, h - margin, 1, -1),
            (w - margin, h - margin, -1, -1),
        ]:
            self.canvas.create_line(
                cx, cy, cx + dx * bracket_len, cy, fill=CYAN, width=2,
                tags="static",
            )
            self.canvas.create_line(
                cx, cy, cx, cy + dy * bracket_len, fill=CYAN, width=2,
                tags="static",
            )
            self.canvas.create_line(
                cx + dx * 3, cy, cx + dx * 3, cy + dy * 3, fill=blend(BG, CYAN, 0.4),
                width=1, tags="static",
            )
        self.title_id = self.canvas.create_text(
            w // 2, 30, text="M I K E", fill=CYAN,
            font=("Consolas", 22, "bold"), tags="static",
        )
        self.state_label = self.canvas.create_text(
            w // 2, 56, text="", fill=DIM,
            font=("Consolas", 10), tags="static",
        )
        self.clock_id = self.canvas.create_text(
            w - margin - inset, 30, text="", fill=DIM,
            font=("Consolas", 10), tags="static", anchor="e",
        )

    def _anim_tick(self):
        if not self.running.is_set():
            return
        self._frame += 1
        w = self.canvas.winfo_width() or 880
        h = self.canvas.winfo_height() or 620
        if w < 50 or h < 50:
            self.after(50, self._anim_tick)
            return
        if w != getattr(self, "_hud_w", 0) or h != getattr(self, "_hud_h", 0):
            self.canvas.delete("all")
            self._draw_static_hud(w, h)

        frame = self._frame
        self.canvas.delete("dynamic")
        cx, cy = w // 2, h // 2 + 8
        base = min(w, h) * 0.19
        state = self._current_state()
        color = state_color(state)

        try:
            self.canvas.itemconfigure(self.clock_id, text=time.strftime("%H:%M"))
        except tk.TclError:
            pass

        # drifting background particles
        for i, (px, py, pr) in enumerate(self._particles):
            drift = tri(frame / 60.0 + i * 0.05)
            dx = (px * 0.5 + drift * 0.02) * w
            dy = (py * 0.5 + (tri(frame / 45.0 + i * 0.13) - 0.5) * 0.04) * h
            r = pr * 3.0
            self.canvas.create_oval(
                dx - r, dy - r, dx + r, dy + r,
                fill=blend(BG, CYAN, 0.25), outline="", tags="dynamic",
            )

        # soft glow layers behind orb
        for alpha, mult in [(0.10, 2.6), (0.18, 2.0), (0.30, 1.5)]:
            rr = base * mult
            self.canvas.create_oval(
                cx - rr, cy - rr, cx + rr, cy + rr,
                outline=blend(BG, color, alpha), width=2, tags="dynamic",
            )

        # rotating arc segments (the JARVIS rings)
        for i, (speed, radius_mult, arc_deg, width, alpha) in enumerate([
            (0.020, 1.35, 118, 3, 0.95),
            (-0.013, 1.62, 88, 3, 0.75),
            (0.009, 1.92, 64, 2, 0.55),
        ]):
            start = (frame * speed * 360) % 360
            r = base * radius_mult * pulse_radius(base, frame, scale=0.02) / base
            x0, y0, x1, y1, sx, sy, ex, ey = arc_coords(cx, cy, r, start, arc_deg)
            self.canvas.create_arc(
                x0, y0, x1, y1, start=start, extent=arc_deg,
                outline=blend(BG, color, alpha), width=width, style="arc",
                tags="dynamic",
            )
            self.canvas.create_line(
                sx, sy, ex, ey, fill=blend(BG, color, min(1.0, alpha + 0.2)),
                width=2, tags="dynamic",
            )

        # orbiting node dots
        for i, (speed, radius_mult) in enumerate([(0.030, 1.35), (-0.021, 1.62), (0.015, 1.92)]):
            ang = (frame * speed * 360 + i * 120) % 360
            rad = math.radians(ang)
            r = base * radius_mult
            nx = cx + r * math.cos(rad)
            ny = cy + r * math.sin(rad)
            self.canvas.create_oval(
                nx - 3, ny - 3, nx + 3, ny + 3,
                fill=color, outline="", tags="dynamic",
            )

        # core orb with pulse
        core_r = pulse_radius(base, frame, scale=0.06)
        x0, y0 = cx - core_r, cy - core_r
        x1, y1 = cx + core_r, cy + core_r
        self.canvas.create_oval(x0, y0, x1, y1, fill=color, outline=color, tags="dynamic")
        inner = core_r * 0.68
        self.canvas.create_oval(
            cx - inner, cy - inner, cx + inner, cy + inner,
            fill=blend(color, BG, 0.35), outline="", tags="dynamic",
        )
        core_inner = core_r * 0.40
        self.canvas.create_oval(
            cx - core_inner, cy - core_inner, cx + core_inner, cy + core_inner,
            fill=BG, outline="", tags="dynamic",
        )
        # core eye glow
        eye_r = core_inner * 0.5
        self.canvas.create_oval(
            cx - eye_r, cy - eye_r, cx + eye_r, cy + eye_r,
            fill=blend(BG, color, 0.6), outline="", tags="dynamic",
        )

        # waveform bars
        heights = waveform_heights(frame, state, bars=23)
        bar_w = 5
        gap = 7
        total = len(heights) * gap
        bx = cx - total / 2
        by = cy + base * 1.15 + 14
        for i, hv in enumerate(heights):
            bh = max(2, hv * 22)
            x = bx + i * gap
            self.canvas.create_rectangle(
                x, by - bh, x + bar_w, by,
                fill=blend(BG, color, 0.4 + 0.6 * (hv / 1.0)),
                outline="", tags="dynamic",
            )

        # state status line under waveform
        self.canvas.create_text(
            cx, by + 24, text=state_status(state), fill=blend(BG, color, 0.85),
            font=("Consolas", 9, "bold"), tags="dynamic",
        )
        self.after(50, self._anim_tick)

    def _current_state(self):
        return self._state

    def _set_state(self, state):
        self._state = state
        label = state_status(state)
        self.state_label_text.set(label)
        try:
            self.canvas.itemconfigure(self.state_label, text=label)
        except (tk.TclError, AttributeError):
            pass

    # ---------- awareness ----------
    def _start_awareness(self):
        try:
            from awareness.monitors import (
                DiskMonitor, MetricMonitor, ReminderMonitor,
                RoutineMonitor, TaskMonitor,
            )
            scheduler = self.mike.enable_awareness()
            scheduler.add_monitor(DiskMonitor(self.mike.events))
            scheduler.add_monitor(TaskMonitor(self.mike.events, self.mike.memory))
            scheduler.add_monitor(
                ReminderMonitor(self.mike.events, self.mike.memory)
            )
            scheduler.add_monitor(MetricMonitor(self.mike.events, self.mike.memory))
            runner = self.mike.load_operations()
            scheduler.add_monitor(RoutineMonitor(self.mike.events, runner))
            self._wire_reminder_popups()
            return scheduler
        except Exception:  # noqa: BLE001
            return None

    def _wire_reminder_popups(self):
        def on_reminder(event):
            if event.kind != "monitor.reminders":
                return
            due = event.payload.get("due", [])
            if not due:
                return
            text = "Reminder: " + "; ".join(due)
            self.after(0, lambda: self._append_chat("mike", text))
            self.after(0, lambda: self._set_state("speaking"))
            threading.Thread(
                target=self._speak_async, args=(text,), daemon=True
            ).start()

        self.mike.events.subscribe(on_reminder)

    def _speak_async(self, text):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
            self.after(0, lambda: self._set_state("listening"))
        except Exception:  # noqa: BLE001
            pass

    def _wire_tray_notifications(self):
        def on_event(event):
            if not event.kind.startswith("guardian."):
                return
            level = event.payload.get("level") if event.kind == "guardian.evaluated" else event.kind.split(".")[-1]
            if level not in ("unusual", "emergency"):
                return
            title = "MIKE GUARDIAN"
            message = f"{event.kind}: {event.payload}"
            self.after(0, lambda: self._tray_notify(title, message))
            self.after(0, lambda: self._append_chat("state", message))

        self.mike.events.subscribe(on_event)

    def _tray_notify(self, title, message):
        try:
            if self._tray is not None:
                self._tray.notify(message, title)
        except Exception:  # noqa: BLE001
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
        if self._awareness is not None:
            self._awareness.stop()
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
                if text.lower().strip(" .!?") in FILLERS:
                    continue
                text = strip_wake(text)
                if not text.strip():
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


def main():
    hidden = "--hidden" in sys.argv
    app = MikeDesktop(hidden=hidden)
    app.mainloop()


if __name__ == "__main__":
    main()