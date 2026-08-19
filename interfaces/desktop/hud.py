import math

STATE_COLORS = {
    "listening": "#00e5ff",
    "thinking": "#7c4dff",
    "speaking": "#ff2e88",
    "idle": "#00e5ff",
}

STATUS_TEXT = {
    "listening": "LISTENING — speak to me",
    "thinking": "THINKING...",
    "speaking": "SPEAKING",
    "idle": "STANDBY",
}


def state_color(state):
    return STATE_COLORS.get(state, STATE_COLORS["idle"])


def state_status(state):
    return STATUS_TEXT.get(state, STATUS_TEXT["idle"])


def tri(x):
    val = (x % 1.0) * 2.0
    return 1.0 - abs(val - 1.0)


def blend(c1, c2, alpha):
    def comp(a, b):
        return int(a + (b - a) * alpha)
    r1, g1, b1 = (int(c1[i:i + 2], 16) for i in (1, 3, 5))
    r2, g2, b2 = (int(c2[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % (comp(r1, r2), comp(g1, g2), comp(b1, b2))


def arc_coords(cx, cy, r, start_deg, extent_deg):
    start = math.radians(start_deg)
    sweep = math.radians(extent_deg)
    x0 = cx - r
    y0 = cy - r
    x1 = cx + r
    y1 = cy + r
    sx = cx + r * math.cos(start)
    sy = cy + r * math.sin(start)
    ex = cx + r * math.cos(start + sweep)
    ey = cy + r * math.sin(start + sweep)
    return x0, y0, x1, y1, sx, sy, ex, ey


def waveform_heights(frame, state, bars=21, amplitude=1.0):
    if state in ("idle", "thinking"):
        base = 2.0 if state == "thinking" else 1.0
        return [base] * bars
    energy = 0.8 if state == "listening" else 1.0
    heights = []
    for i in range(bars):
        angle = (frame / 8.0) + (i * 0.55)
        wave = math.sin(angle) * 0.5 + math.sin(angle * 2.3) * 0.3
        if state == "listening":
            wave += math.sin(angle * 0.7) * 0.4
        raw = max(0.0, 0.2 + wave)
        heights.append(round(raw * amplitude * energy, 3))
    return heights


def pulse_radius(base, frame, scale=0.05):
    return base * (1.0 + scale * tri(frame / 12.0))


def particle_field(seed, count=24):
    points = []
    rnd = (seed * 9301 + 49297) % 233280
    for i in range(count):
        rnd = (rnd * 9301 + 49297) % 233280
        x = (rnd / 233280.0) * 2.0 - 1.0
        rnd = (rnd * 9301 + 49297) % 233280
        y = (rnd / 233280.0) * 2.0 - 1.0
        rnd = (rnd * 9301 + 49297) % 233280
        r = 0.15 + (rnd / 233280.0) * 0.55
        points.append((x, y, r))
    return points


def format_percent(value):
    if value is None:
        return "—"
    return f"{value:.0f}%"


def format_battery(percent, plugged):
    if percent is None:
        return "—"
    plug = "⚡" if plugged else "🔋"
    return f"{plug} {percent:.0f}%"