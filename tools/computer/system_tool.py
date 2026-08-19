import os
import platform
import shutil

from policies.engine import Level
from tools.base import Tool


class SystemTool(Tool):
    name = "system"
    description = "report the machine state: OS, disk, battery, memory"
    level = Level.GREEN

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)

    def matches(self, request):
        lowered = request.lower()
        return any(
            phrase in lowered
            for phrase in [
                "system status",
                "system info",
                "machine status",
                "how is my system",
                "check the system",
                "disk space",
                "battery status",
                "how much space",
                "free space",
                "system health",
            ]
        )

    def run(self, request):
        parts = []
        parts.append(f"OS: {platform.system()} {platform.release()}")
        parts.append(f"Host: {platform.node()}")
        parts.append(f"Machine: {platform.machine()}")

        usage = shutil.disk_usage(os.getcwd())
        total_gb = usage.total / (1024 ** 3)
        free_gb = usage.free / (1024 ** 3)
        used_pct = usage.used / usage.total * 100
        parts.append(
            f"Disk: {free_gb:.1f} GB free of {total_gb:.1f} GB "
            f"({used_pct:.0f}% used)"
        )

        battery = self._battery()
        if battery:
            parts.append(battery)

        return "\n".join(parts)

    def _battery(self):
        try:
            import psutil
            if not hasattr(psutil, "sensors_battery"):
                return None
            bat = psutil.sensors_battery()
            if bat is None:
                return None
            charging = "charging" if bat.power_plugged else "on battery"
            return f"Battery: {bat.percent:.0f}% ({charging})"
        except (ImportError, AttributeError):
            return None

    def verify(self, result):
        if "OS:" in result:
            return "verified: system info collected"
        return "failed"