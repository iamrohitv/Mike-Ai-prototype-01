import subprocess
import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Mike Desktop"
APP_PATH = Path(__file__).resolve().parent / "app.py"


def _pythonw():
    exe = Path(sys.executable)
    return exe.with_name("pythonw.exe")


def startup_command():
    return f'"{_pythonw()}" "{APP_PATH}" --hidden'


def is_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
        return True
    except FileNotFoundError:
        return False


def enable():
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, startup_command())
    return True


def disable():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        pass
    return True


def main():
    args = sys.argv[1:]
    if "--enable" in args:
        if is_enabled():
            print("Mike already starts with Windows.")
        else:
            enable()
            print(f"Enabled: {startup_command()}")
    elif "--disable" in args:
        disable()
        print("Disabled: Mike will no longer start with Windows.")
    elif "--status" in args:
        print("enabled" if is_enabled() else "disabled")
    else:
        print("usage: python -m interfaces.desktop.autostart --enable|--disable|--status")


if __name__ == "__main__":
    main()