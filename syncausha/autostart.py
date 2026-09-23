"""Lancement au démarrage de Windows via HKCU\\...\\Run (sans droits administrateur)."""
from __future__ import annotations

import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "SyncAusha"


def launch_command() -> str:
    """Commande enregistrée dans Run : l'exe empaqueté, ou pythonw + script en développement."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    script = Path(__file__).resolve().parent.parent / "run_syncausha.py"
    return f'"{pythonw}" "{script}" --minimized'


def is_enabled(value_name: str = VALUE_NAME) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, value_name)
            return True
    except FileNotFoundError:
        return False


def set_enabled(enabled: bool, value_name: str = VALUE_NAME, command: str | None = None) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, command or launch_command())
            return
        try:
            winreg.DeleteValue(key, value_name)
        except FileNotFoundError:
            pass
