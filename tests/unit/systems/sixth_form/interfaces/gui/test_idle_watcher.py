"""An unattended warning dialog must not stop the sixth form idle logout."""
from unittest.mock import MagicMock

from education_system.systems.sixth_form.interfaces.gui import idle_timeout as it


def _watcher(monkeypatch, idle_seconds, warning=None):
    root = MagicMock()
    on_timeout = MagicMock()
    watcher = it.IdleTimeoutWatcher(
        root, on_timeout=on_timeout, timeout_minutes=30, warning_lead_seconds=60)
    monkeypatch.setattr(watcher, "idle_seconds", lambda: idle_seconds)
    monkeypatch.setattr(it.messagebox, "showwarning", warning or MagicMock())
    return watcher, root, on_timeout


def test_next_check_is_scheduled_before_the_modal_warning(monkeypatch):
    seen = {}
    def warning(*a, **kw):
        seen["scheduled_when_shown"] = root.after.called
    watcher, root, _ = _watcher(monkeypatch, 30 * 60 - 30, warning)
    watcher._tick()
    assert seen["scheduled_when_shown"] is True


def test_timeout_fires_while_the_warning_is_still_open(monkeypatch):
    watcher, root, on_timeout = _watcher(monkeypatch, 30 * 60 - 30)
    watcher._tick()
    monkeypatch.setattr(watcher, "idle_seconds", lambda: 30 * 60)
    watcher._tick()
    on_timeout.assert_called_once()


def test_activity_before_the_threshold_does_not_log_out(monkeypatch):
    watcher, root, on_timeout = _watcher(monkeypatch, 60)
    watcher._tick()
    on_timeout.assert_not_called()
