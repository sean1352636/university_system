"""GUI start-up and navigation (app.gui_main, app.bootstrap) on scratch databases.

The main window opens for a signed-in member of staff, lands on My Day,
builds the sidebar from the menu catalogue filtered by role, and every
sidebar entry opens its page (or the "not built yet" page) without an
error. Restricted entries are refused for staff without the role, and
closing / logging out ends the activity-log session.

Marked ``gui`` (needs a display); skipped when Tk can't open one. Every
message box is replaced so nothing waits for a click. Entries that open a
modal dialog or picker are checked through their method, not clicked.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pytest

from education_system.systems.secondary.app import bootstrap, gui_main, routing
from education_system.systems.secondary.core.permissions import access
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.database import connection as database
from education_system.systems.secondary.infrastructure.logging import activity_log

pytestmark = pytest.mark.gui

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="ann", role="teacher")

#: Sidebar entries that open a modal dialog or picker (they wait for the
#: user), so the window is checked to have a handler rather than clicked.
MODAL = {"add_pupil", "pupil_profile", "parent_contacts", "change_password", "mfa"}
#: Sidebar entries with no screen yet - shown as "not built yet". Remove a
#: key here when it is built (the test fails until you do).
NOT_BUILT = {"year6_transition"}


def _display_or_skip() -> None:
    try:
        root = tk.Tk()
    except tk.TclError as e:
        pytest.skip(f"no display for Tk: {e}")
    root.destroy()


class FakeAuth:
    """The launcher's shared session, as far as the window uses it."""

    def __init__(self, principal: Principal) -> None:
        self.current_user = {"username": principal.username, "role": principal.role,
                             "id": 1}
        self.logged_out = 0

    def logout(self) -> None:
        self.logged_out += 1


def _point_at(tmp, *, fresh: bool) -> None:
    """Point the database, auth.db and activity log at *tmp* (never the live files)."""
    database.use_database(tmp / "secondary.db")
    accounts.use_auth_db(tmp / "auth.db")
    activity_log.use_log_file(tmp / "activity.log")
    if fresh:
        from education_system.platform.identity.auth.schema import initialise_auth_db
        initialise_auth_db(str(tmp / "auth.db"))


def _release() -> None:
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


@pytest.fixture(scope="module")
def boxes():
    """Every message box the window shows, as (kind, title, text)."""
    shown: list[tuple[str, str, str]] = []
    mp = pytest.MonkeyPatch()
    for kind in ("showerror", "showinfo", "showwarning"):
        mp.setattr(gui_main.messagebox, kind,
                   lambda title="", text="", *_a, _k=kind, **_kw: shown.append((_k, title, text)))
    mp.setattr(gui_main.messagebox, "askyesno", lambda *_a, **_kw: False)
    yield shown
    mp.undo()


@pytest.fixture(scope="module")
def admin_dir(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("sec-gui-admin")
    _point_at(tmp, fresh=True)
    _release()
    return tmp


@pytest.fixture(autouse=True)
def scratch(request, tmp_path):
    """Every test runs on scratch files: the shared admin window's own, or a
    fresh set. Re-pointed per test because tests may run in any order."""
    if "admin_window" in request.fixturenames:
        _point_at(request.getfixturevalue("admin_dir"), fresh=False)
    else:
        _point_at(tmp_path, fresh=True)
    yield tmp_path
    _release()


def _open_window(principal: Principal) -> gui_main.SecondaryMainGUI:
    win = gui_main.SecondaryMainGUI(FakeAuth(principal), principal)
    win.root.withdraw()
    return win


def _close(win: gui_main.SecondaryMainGUI) -> None:
    try:
        win._on_close()
    except tk.TclError:
        pass


@pytest.fixture(scope="module")
def admin_window(admin_dir, boxes):
    _display_or_skip()
    _point_at(admin_dir, fresh=False)
    win = _open_window(ADMIN)
    yield win
    _point_at(admin_dir, fresh=False)      # closing writes session.end - keep it off the live log
    try:
        _close(win)
    finally:
        _release()


def _buttons(widget: tk.Misc) -> list[str]:
    out = []
    for child in widget.winfo_children():
        if isinstance(child, ttk.Button):
            out.append(str(child.cget("text")))
        out += _buttons(child)
    return out


def _texts(widget: tk.Misc) -> str:
    out = []
    for child in widget.winfo_children():
        try:
            out.append(str(child.cget("text")))
        except tk.TclError:
            pass
        out.append(_texts(child))
    return " ".join(out)


# ── Start-up ─────────────────────────────────────────────────────────

def test_window_opens_on_my_day_with_the_user_and_session(admin_window, admin_dir) -> None:
    win = admin_window
    assert win.root.title() == gui_main.SYSTEM_NAME
    assert win.current_user_var.get() == "admin2"
    assert win.status_var.get() == "Opened: Staff Portal"
    assert win.content_frame is not None and win.content_frame.winfo_children()
    log = (admin_dir / "activity.log").read_text(encoding="utf-8")
    assert "user=admin2 | role=admin | gui | session.start" in log


def test_header_has_the_standard_buttons(admin_window) -> None:
    texts = _buttons(admin_window.root)
    for wanted in ("🏠 Dashboard", "👤 My Day", "Logout", "Switch to CLI"):
        assert wanted in texts
    assert "Switch System" not in texts           # superadmin only


def test_sidebar_has_every_category_the_admin_may_open(admin_window) -> None:
    texts = _buttons(admin_window.root)
    for category, _items in access.visible_categories(ADMIN, routing.CATEGORIES):
        assert f"{category}  ▶" in texts


def test_dashboard_draws(admin_window) -> None:
    admin_window._show_welcome()
    assert admin_window.content_frame.winfo_children()


def test_sidebar_search_lists_matching_entries(admin_window) -> None:
    entry = admin_window.nav_search_entry
    entry.delete(0, tk.END)
    entry.insert(0, "detent")
    admin_window.root.update_idletasks()
    texts = _buttons(admin_window.root)
    assert "Detentions" in texts
    entry.delete(0, tk.END)
    entry.insert(0, "zzzz-no-such-entry")
    admin_window.root.update_idletasks()
    assert "No matches" in _texts(admin_window.root)
    entry.delete(0, tk.END)


# ── Every sidebar entry ──────────────────────────────────────────────

_ENTRIES = [(label, key) for label, key in routing.all_entries() if key not in MODAL]


@pytest.mark.parametrize(("label", "key"), _ENTRIES, ids=[k for _l, k in _ENTRIES])
def test_every_sidebar_entry_opens_its_page(admin_window, boxes, label: str,
                                            key: str) -> None:
    before = len(boxes)
    admin_window._handler(key, label)()
    admin_window.root.update_idletasks()
    errors = [b for b in boxes[before:] if b[0] == "showerror"]
    assert not errors, f"{label} showed an error: {errors}"
    assert admin_window.content_frame.winfo_children(), f"{label} drew nothing"
    if key in NOT_BUILT:
        assert "hasn't been built yet" in _texts(admin_window.content_frame)
    else:
        assert "hasn't been built yet" not in _texts(admin_window.content_frame), \
            f"{label} is not built - add it to NOT_BUILT or build it"


@pytest.mark.parametrize("key", sorted(MODAL))
def test_modal_entries_have_a_handler(key: str) -> None:
    assert callable(getattr(gui_main.SecondaryMainGUI, f"open_{key}", None))


def test_pages_can_pop_out_into_their_own_window(admin_window) -> None:
    admin_window._handler("behaviour", "Behaviour & Rewards")()
    before = set(admin_window.root.winfo_children())
    admin_window._open_current_page_in_window()
    new = [w for w in admin_window.root.winfo_children() if w not in before]
    assert any(isinstance(w, tk.Toplevel) for w in new)
    for w in new:
        w.destroy()


# ── Access ───────────────────────────────────────────────────────────

def test_teacher_sees_no_restricted_entry_and_is_refused_one(scratch, boxes) -> None:
    _display_or_skip()
    restricted = [(label, key) for label, key in routing.all_entries()
                  if not TEACHER.can_open(label)]
    assert restricted, "no restricted entries to check"
    for _category, items in access.visible_categories(TEACHER, routing.CATEGORIES):
        assert all(TEACHER.can_open(label) for label, _key in items)
    win = _open_window(TEACHER)
    try:
        label, key = restricted[0]
        before = len(boxes)
        win._handler(key, label)()
        assert boxes[before:] and boxes[before][0] == "showwarning"
        assert "doesn't have access" in boxes[before][2]
        log = (scratch / "activity.log").read_text(encoding="utf-8")
        assert f"menu.open | target={label} | outcome=denied" in log
    finally:
        _close(win)


# ── Closing ──────────────────────────────────────────────────────────

def test_logout_ends_the_session_and_asks_for_the_login(scratch, boxes, monkeypatch) -> None:
    _display_or_skip()
    from education_system import switch
    requested = []
    monkeypatch.setattr(switch, "request_logout", lambda mode="gui": requested.append(mode))
    win = _open_window(ADMIN)
    win._logout()
    assert requested == ["gui"] and win.auth.logged_out == 1
    assert activity_log.current_session()["id"] is None
    assert "reason=logout" in (scratch / "activity.log").read_text(encoding="utf-8")


def test_closing_the_window_ends_the_session(scratch, boxes) -> None:
    _display_or_skip()
    win = _open_window(ADMIN)
    win._on_close()
    assert win.auth.logged_out == 1
    assert activity_log.current_session()["id"] is None
    assert "reason=window_closed" in (scratch / "activity.log").read_text(encoding="utf-8")


# ── run() / bootstrap ────────────────────────────────────────────────

def test_run_refuses_without_the_launchers_session() -> None:
    with pytest.raises(RuntimeError, match="GUI must be launched via python -m education_system"):
        gui_main.run(shared_auth=None)
    with pytest.raises(RuntimeError, match="GUI must be launched"):
        bootstrap.require_shared_session(object(), "gui")     # no current_user


def test_run_refuses_a_login_with_no_school_role(scratch, monkeypatch) -> None:
    shown = []
    monkeypatch.setattr(gui_main, "_show_refusal", shown.append)
    assert gui_main.run(shared_auth=FakeAuth(Principal("visitor", "guest"))) == 0
    assert shown and "only for school staff" in shown[0]
    assert "reason=refused_not_staff" in (scratch / "activity.log").read_text(encoding="utf-8")


def test_run_opens_the_window_for_staff(scratch, monkeypatch) -> None:
    _display_or_skip()
    opened = []

    class Window(gui_main.SecondaryMainGUI):
        def __init__(self, auth, principal):
            super().__init__(auth, principal)
            self.root.withdraw()
            self.root.mainloop = lambda *_a: None   # don't wait for the user
            opened.append(self)

    monkeypatch.setattr(gui_main, "SecondaryMainGUI", Window)
    monkeypatch.setattr(bootstrap, "roll_year_if_due", lambda _p: [])
    try:
        assert gui_main.run(shared_auth=FakeAuth(ADMIN), role="admin") == 0
        assert opened and opened[0].principal.username == "admin2"
        assert opened[0].status_var.get() == "Opened: Staff Portal"
    finally:
        for w in opened:
            _close(w)
