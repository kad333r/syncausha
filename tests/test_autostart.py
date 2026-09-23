import pytest

winreg = pytest.importorskip("winreg")

from syncausha import autostart  # noqa: E402

NAME = "SyncAushaTest"


@pytest.fixture(autouse=True)
def cleanup():
    yield
    autostart.set_enabled(False, NAME)


def test_enable_then_disable():
    assert not autostart.is_enabled(NAME)
    autostart.set_enabled(True, NAME, command='"C:\\x.exe" --minimized')
    assert autostart.is_enabled(NAME)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, autostart.RUN_KEY) as key:
        assert winreg.QueryValueEx(key, NAME)[0] == '"C:\\x.exe" --minimized'
    autostart.set_enabled(False, NAME)
    assert not autostart.is_enabled(NAME)
    autostart.set_enabled(False, NAME)  # idempotent


def test_launch_command_in_dev_mode():
    command = autostart.launch_command()
    assert command.endswith("--minimized")
    assert "run_syncausha.py" in command


def test_unreadable_registry_counts_as_disabled(monkeypatch):
    def denied(*args):
        raise PermissionError(13, "Accès refusé")

    monkeypatch.setattr(autostart.winreg, "OpenKey", denied)
    assert autostart.is_enabled(NAME) is False
