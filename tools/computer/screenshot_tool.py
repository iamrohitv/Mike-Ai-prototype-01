import os
from datetime import datetime

from policies.engine import Level
from tools.base import Tool


class ScreenshotTool(Tool):
    name = "screenshot"
    description = "capture the screen and save it to disk"
    level = Level.YELLOW

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)

    def matches(self, request):
        lowered = request.lower()
        return any(
            phrase in lowered
            for phrase in [
                "take a screenshot",
                "capture the screen",
                "screenshot",
                "screen capture",
                "snapshot of my screen",
            ]
        )

    def run(self, request):
        try:
            from PIL import ImageGrab
        except ImportError:
            return "Screenshot tool needs Pillow, which isn't installed."
        screenshots_dir = os.path.join(os.path.dirname(self.memory.db_path), "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        filename = "screen-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".png"
        path = os.path.join(screenshots_dir, filename)
        try:
            image = ImageGrab.grab()
            image.save(path, "PNG")
        except Exception as exc:  # noqa: BLE001
            return f"Could not capture the screen: {exc}"
        size_kb = os.path.getsize(path) / 1024
        return (
            f"Captured the screen -> {path} "
            f"({image.size[0]}x{image.size[1]}, {size_kb:.0f} KB)"
        )

    def verify(self, result):
        if "Could not" in result or "needs Pillow" in result:
            return "failed"
        if "Captured the screen" in result:
            return "verified: screenshot saved to disk"
        return "completed"