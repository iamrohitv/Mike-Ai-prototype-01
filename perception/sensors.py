import datetime
import os
import platform
import shutil


class Sensor:
    name = "base"
    description = ""

    def read(self):
        raise NotImplementedError

    def available(self):
        return True


class SystemSensor(Sensor):
    name = "system"
    description = "current OS, disk and machine state"

    def read(self):
        usage = shutil.disk_usage(os.getcwd())
        return {
            "os": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "disk_used_percent": round(usage.used / usage.total * 100, 1),
            "time": datetime.datetime.now().isoformat(),
        }


class ScreenSensor(Sensor):
    name = "screen"
    description = "detect whether the display is active"

    def __init__(self, active=True):
        self._active = active

    def available(self):
        return True

    def read(self):
        return {"active": self._active}


class CameraSensor(Sensor):
    name = "camera"
    description = "capture a frame from a webcam if present"

    def __init__(self, backend=None):
        self.backend = backend
        self._available = None

    def available(self):
        if self._available is None:
            self._available = self._probe()
        return self._available

    def _probe(self):
        try:
            import cv2  # noqa: F401
        except ImportError:
            return False
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            ok = cap.isOpened()
            cap.release()
            return ok
        except Exception:  # noqa: BLE001
            return False

    def read(self):
        if not self.available():
            return {"available": False, "error": "no camera"}
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            ok, frame = cap.read()
            cap.release()
            if not ok:
                return {"available": True, "error": "capture failed"}
            h, w = frame.shape[:2]
            return {"available": True, "width": w, "height": h, "captured": True}
        except Exception as exc:  # noqa: BLE001
            return {"available": True, "error": str(exc)}


class PerceptionHub:
    def __init__(self, event_bus, sensors=None):
        self.event_bus = event_bus
        self.sensors = sensors or [SystemSensor()]

    def add_sensor(self, sensor):
        self.sensors.append(sensor)

    def sense_all(self):
        readings = {}
        for sensor in self.sensors:
            try:
                if sensor.available():
                    readings[sensor.name] = sensor.read()
            except Exception:  # noqa: BLE001
                continue
        self.event_bus.emit("perception.readings", readings)
        return readings

    def sense(self, name):
        for sensor in self.sensors:
            if sensor.name == name:
                if sensor.available():
                    return sensor.read()
                return {"available": False}
        return None