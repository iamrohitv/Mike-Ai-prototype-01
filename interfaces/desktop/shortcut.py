import sys
from pathlib import Path

APP_PATH = Path(__file__).resolve().parent / "app.py"


def _pythonw():
    exe = Path(sys.executable)
    return exe.with_name("pythonw.exe")


def desktop_path():
    try:
        from win32com.client import Dispatch
        shell = Dispatch("WScript.Shell")
        return Path(shell.SpecialFolders("Desktop"))
    except Exception:  # noqa: BLE001
        return Path.home() / "Desktop"


def create_shortcut():
    from win32com.client import Dispatch

    target = str(_pythonw())
    args = f'"{APP_PATH}"'
    workdir = str(APP_PATH.parent.parent.parent)
    desktop = desktop_path()
    link_path = desktop / "MIKE.lnk"

    shell = Dispatch("WScript.Shell")
    shortcut = shell.CreateShortcut(str(link_path))
    shortcut.TargetPath = target
    shortcut.Arguments = args
    shortcut.WorkingDirectory = workdir
    shortcut.IconLocation = ",0"
    shortcut.Description = "Mike - your personal AI counterpart"
    shortcut.Save()
    return link_path


def has_shortcut():
    return (desktop_path() / "MIKE.lnk").exists()


def remove_shortcut():
    link = desktop_path() / "MIKE.lnk"
    if link.exists():
        link.unlink()
        return True
    return False


def main():
    args = sys.argv[1:]
    if "--create" in args or not args:
        if has_shortcut():
            print("Desktop shortcut already exists.")
        else:
            try:
                path = create_shortcut()
                print(f"Created desktop shortcut: {path}")
            except ImportError:
                print("Need pywin32. Install with: pip install pywin32")
            except Exception as exc:  # noqa: BLE001
                print(f"Could not create shortcut: {exc}")
    elif "--remove" in args:
        print("Removed shortcut." if remove_shortcut() else "No shortcut found.")
    elif "--status" in args:
        print("exists" if has_shortcut() else "missing")
    else:
        print("usage: python -m interfaces.desktop.shortcut --create|--remove|--status")


if __name__ == "__main__":
    main()