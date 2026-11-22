"""Shared fixtures for Primary School tests.

``fresh_data_dir`` redirects only ``paths`` (for the path tests). Everything
else that opens a real primary screen or domain module uses
``primary_sandbox``, which each test folder turns on for all of its tests
with an autouse wrapper in its own conftest:

* ``EDU_PRIMARY_DATA_DIR`` and ``EDU_PLATFORM_DATA_DIR`` point at a fresh
  temp directory and ``education_system.paths`` is reloaded; the platform
  ``auth.db`` there is an initialised, empty login database;
* any already-imported ``education_system`` module that copied an old data
  path into a module or class attribute at import time (``DB_PATH =
  paths.PRIMARY_..._DB``) is repointed at the sandbox equivalent, and its
  ``*_READY`` / ``*_INITIALISED`` flags are reset so schemas are created in
  the sandbox;
* ``sqlite3.connect`` refuses any file under the repository's ``var/`` -
  the live ``primary.db``, ``auth.db``, audit and outbox databases - so a
  path the redirect missed fails the test instead of touching live data.

Other fixtures: ``fake_auth``, ``admin_principal``, ``staff_auth`` /
``staff_principal``, ``scripted_input``, ``primary_gui`` (a real
:class:`PrimarySchoolMainGUI`; mark GUI tests ``pytest.mark.gui``),
``content_text``, ``page_text`` and ``toplevels``.
"""

from __future__ import annotations

import importlib



import os
import sqlite3
import sys
from pathlib import Path
from types import ModuleType

import pytest

_REAL_SQLITE_CONNECT = sqlite3.connect
_FLAG_SUFFIXES = ("_READY", "_INITIALISED", "_INITIALIZED", "_INIT_DONE", "_SCHEMA_DONE")


def _repo_var_dir() -> Path:
    from education_system import paths
    return Path(paths.VAR_DIR).resolve()


_AUTH_TEMPLATE: list[Path] = []


def _copy_auth_template(target: Path) -> None:
    """Give the sandbox an initialised (empty) login database, built once per
    test process, so cross-system hooks (login links, the student journey)
    find their tables instead of logging "no such table" on every pupil."""
    if not _AUTH_TEMPLATE:
        import tempfile

        from education_system.platform.cross_system import enrolment_schema
        from education_system.platform.identity.auth import schema as auth_schema
        path = Path(tempfile.mkdtemp(prefix="primary-auth-")) / "auth.db"
        auth_schema.initialise_auth_db(str(path))
        enrolment_schema.ensure_enrolment_schema(str(path))
        _AUTH_TEMPLATE.append(path)
    src, dst = _REAL_SQLITE_CONNECT(_AUTH_TEMPLATE[0]), _REAL_SQLITE_CONNECT(target)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()


class LiveDataTouched(AssertionError):
    """A test tried to open a database under the live ``var/`` directory."""


def _guarded_connect(var_dir: Path):
    def connect(database, *args, **kwargs):
        target = str(database)
        if target not in (":memory:", "") and not target.startswith("file::memory:"):
            raw = target[5:].split("?", 1)[0] if target.startswith("file:") else target
            try:
                resolved = Path(raw).resolve()
            except (OSError, ValueError):
                resolved = None
            if resolved is not None and (resolved == var_dir or var_dir in resolved.parents):
                raise LiveDataTouched(f"test tried to open live database {resolved}")
        return _REAL_SQLITE_CONNECT(database, *args, **kwargs)
    return connect


def _remap(value, prefixes: list[tuple[str, str]]):
    """Return ``value`` with an old data-dir prefix swapped, or None."""
    if isinstance(value, Path):
        text, as_path = str(value), True
    elif isinstance(value, str):
        text, as_path = value, False
    else:
        return None
    for old, new in prefixes:
        if text == old or text.startswith(old + os.sep):
            swapped = new + text[len(old):]
            return Path(swapped) if as_path else swapped
    return None


def _patch_namespace(monkeypatch, owner, namespace: dict, prefixes) -> None:
    for name, value in list(namespace.items()):
        if name.startswith("__"):
            continue
        if isinstance(value, bool) and value and name.upper().endswith(_FLAG_SUFFIXES):
            monkeypatch.setattr(owner, name, False)
            continue
        new = _remap(value, prefixes)
        if new is not None:
            monkeypatch.setattr(owner, name, new)
        elif isinstance(value, dict) and not name.startswith("_"):
            # Path registries such as ``SYSTEM_DB_PATHS`` copied at import.
            for key, item in list(value.items()):
                swapped = _remap(item, prefixes)
                if swapped is not None:
                    monkeypatch.setitem(value, key, swapped)


def _redirect_loaded_modules(monkeypatch, prefixes) -> None:
    for mod_name, module in list(sys.modules.items()):
        if not mod_name.startswith("education_system.") or not isinstance(module, ModuleType):
            continue
        if mod_name == "education_system.paths":
            continue
        try:
            namespace = vars(module)
        except TypeError:
            continue
        _patch_namespace(monkeypatch, module, namespace, prefixes)
        for value in list(namespace.values()):
            if isinstance(value, type) and getattr(value, "__module__", None) == mod_name:
                try:
                    _patch_namespace(monkeypatch, value, dict(vars(value)), prefixes)
                except (TypeError, AttributeError):
                    continue


@pytest.fixture
def primary_sandbox(tmp_path, monkeypatch):
    """Run the test against throwaway primary and platform data dirs."""
    from education_system import paths

    old_primary = str(Path(paths.PRIMARY_DATA_DIR).resolve())
    old_platform = str(Path(paths.PLATFORM_DATA_DIR).resolve())
    real_primary = str((Path(paths.VAR_DIR) / "data" / "primary").resolve())
    real_platform = str((Path(paths.VAR_DIR) / "data" / "platform").resolve())

    primary_dir = (tmp_path / "primary").resolve()
    platform_dir = (tmp_path / "platform").resolve()
    primary_dir.mkdir()
    (platform_dir / "db_files").mkdir(parents=True)
    _copy_auth_template(platform_dir / "db_files" / "auth.db")

    monkeypatch.setenv("EDU_PRIMARY_DATA_DIR", str(primary_dir))
    monkeypatch.setenv("EDU_PLATFORM_DATA_DIR", str(platform_dir))
    monkeypatch.setenv("EDU_EMAIL_MODE", "inbox_only")
    paths = importlib.reload(paths)

    prefixes = []
    for old, new in ((real_primary, primary_dir), (old_primary, primary_dir),
                     (real_platform, platform_dir), (old_platform, platform_dir)):
        if (old, str(new)) not in prefixes and old != str(new):
            prefixes.append((old, str(new)))
    _redirect_loaded_modules(monkeypatch, prefixes)

    # i18n anchors its paths on the repo, not EDU_PLATFORM_DATA_DIR: import it
    # now so its language file always lands in the sandbox (a language change
    # writes JSON, which the sqlite guard cannot see), but keep reading the
    # real shipped locales so translated titles stay the same in every order.
    from education_system.platform.features.i18n import core as i18n_core
    monkeypatch.setattr(i18n_core, "_PLATFORM_DATA_DIR", platform_dir)
    monkeypatch.setattr(i18n_core, "_CONFIG_DIR", platform_dir / "config")
    monkeypatch.setattr(i18n_core, "_LANGUAGE_CONFIG_PATH",
                        platform_dir / "config" / "language_config.json")
    monkeypatch.setattr(i18n_core, "_DEFAULT_LOCALE_DIR", Path(real_platform) / "locales")

    from education_system.platform.cross_system import enrolment_schema
    monkeypatch.setattr(enrolment_schema, "_initialised", set())

    try:
        from education_system.systems.primary.infrastructure import schema_repair
        monkeypatch.setattr(schema_repair, "_done", set())
    except ImportError:
        pass

    monkeypatch.setattr(sqlite3, "connect", _guarded_connect(_repo_var_dir()))
    try:
        yield paths
    finally:
        monkeypatch.undo()
        importlib.reload(paths)
        # Modules first imported during the test copied sandbox paths; point
        # them back where a normal import would have put them.
        back = [(str(primary_dir), old_primary), (str(platform_dir), old_platform)]
        cleanup = pytest.MonkeyPatch()
        _redirect_loaded_modules(cleanup, back)


# ── Who is signed in ─────────────────────────────────────────────────

class FakeAuth:
    """Just enough of ``UserAuth`` for the menus: a ``current_user`` and a
    ``logout``. Never call the real ``UserAuth.login`` in these tests - it
    writes the live university ``login_attempts`` table."""

    def __init__(self, username: str = "admin3", role: str = "admin"):
        self.current_user = {
            "username": username,
            "role": role,
            "user_id": 1,
            "id": 1,
            "email": f"{username}@example.test",
            "display_name": username,
            "systems": [{"system_key": "primary", "role": role}],
        }
        self.logged_out = False

    def get_current_user(self):
        return self.current_user

    def is_authenticated(self) -> bool:
        return self.current_user is not None

    def logout(self) -> None:
        self.logged_out = True


def _principal(auth, monkeypatch):
    """The session principal for *auth*, installed as the policy's current
    one (restored after the test)."""
    from education_system.systems.primary.domain import access
    principal = access.from_auth(auth)
    monkeypatch.setattr(access.POLICY, "_current", principal)
    return principal


@pytest.fixture
def fake_auth():
    return FakeAuth()


@pytest.fixture
def admin_principal(fake_auth, monkeypatch):
    return _principal(fake_auth, monkeypatch)


@pytest.fixture
def staff_auth():
    return FakeAuth(username="teacher1", role="teacher")


@pytest.fixture
def staff_principal(staff_auth, monkeypatch):
    return _principal(staff_auth, monkeypatch)


# ── Scripted terminal input ──────────────────────────────────────────

class OutOfInput(BaseException):
    """The scripted answers ran out: a screen kept asking. BaseException so a
    screen's ``except Exception`` cannot swallow it and loop forever."""


@pytest.fixture
def scripted_input(monkeypatch):
    """``feed(answers)`` makes ``input`` and ``getpass`` return ``answers`` in
    order, then raise :class:`OutOfInput`. Returns the list of prompts seen."""
    prompts: list[str] = []

    def feed(answers):
        queue = list(answers)

        def fake_input(prompt=""):
            prompts.append(str(prompt))
            if not queue:
                raise OutOfInput(f"no scripted answer for prompt {prompt!r}")
            return queue.pop(0)

        monkeypatch.setattr("builtins.input", fake_input)
        monkeypatch.setattr("getpass.getpass", fake_input)
        return prompts

    return feed


# ── The GUI window ───────────────────────────────────────────────────

@pytest.fixture
def primary_gui(fake_auth, admin_principal, monkeypatch):
    """A real ``PrimarySchoolMainGUI`` for an admin, with message boxes
    answered (``askyesno`` → False, the rest → None/OK) and no idle logout.
    Records every messagebox call in ``gui.messages`` as (kind, title, text).
    Skips when there is no display."""
    tk = pytest.importorskip("tkinter")
    try:
        probe = tk.Tk()
        probe.destroy()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")

    from tkinter import messagebox, simpledialog

    from education_system.systems.primary import gui_main

    messages: list[tuple[str, str, str]] = []

    def recorder(kind, result):
        def call(title="", message="", *args, **kwargs):
            messages.append((kind, str(title), str(message)))
            return result
        return call

    for kind, result in (("showinfo", "ok"), ("showwarning", "ok"), ("showerror", "ok"),
                         ("askyesno", False), ("askokcancel", False),
                         ("askyesnocancel", None), ("askquestion", "no"),
                         ("askretrycancel", False)):
        monkeypatch.setattr(messagebox, kind, recorder(kind, result))
    for kind in ("askstring", "askinteger", "askfloat"):
        monkeypatch.setattr(simpledialog, kind, recorder(kind, None))
    monkeypatch.setattr(gui_main, "install_idle_logout", lambda root, logout: (lambda: None))

    gui = gui_main.PrimarySchoolMainGUI(fake_auth, admin_principal)
    gui.messages = messages
    gui.root.withdraw()
    try:
        yield gui
    finally:
        try:
            for child in gui.root.winfo_children():
                child.destroy()
            gui.root.destroy()
        except tk.TclError:
            pass


def _content_text(gui) -> str:
    """All label/button text currently shown in the content frame and in any
    open Toplevel, for asserting a screen opened (or showed an error)."""
    import tkinter as tk

    seen: list[str] = []

    def walk(widget):
        try:
            text = widget.cget("text")
            if text:
                seen.append(str(text))
        except (tk.TclError, AttributeError):
            pass
        for child in widget.winfo_children():
            walk(child)

    walk(gui.root)
    return "\n".join(seen)


def _page_text(gui) -> str:
    """Only the text drawn in the main window's content area (the page the
    last button showed): labels, buttons, notebook tab titles, tree headings
    and Text contents. Unlike :func:`_content_text` it leaves out the sidebar
    (whose buttons carry the same labels as the page headings) and any
    Toplevel, so a heading found here really is on the page."""
    import tkinter as tk
    from tkinter import ttk

    seen: list[str] = []

    def walk(widget):
        try:
            text = widget.cget("text")
            if text:
                seen.append(str(text))
        except (tk.TclError, AttributeError):
            pass
        if isinstance(widget, ttk.Notebook):
            for tab in widget.tabs():
                seen.append(str(widget.tab(tab, "text")))
        if isinstance(widget, ttk.Treeview):
            for col in widget["columns"]:
                seen.append(str(widget.heading(col, "text")))
        if isinstance(widget, tk.Text):
            seen.append(widget.get("1.0", "end"))
        for child in widget.winfo_children():
            if not isinstance(child, tk.Toplevel):
                walk(child)

    walk(gui.content_frame)
    return "\n".join(seen)


def _toplevels(gui) -> list:
    import tkinter as tk
    return [w for w in gui.root.winfo_children() if isinstance(w, tk.Toplevel)]


@pytest.fixture
def content_text():
    """``content_text(gui)`` → every label/button text in the window and its
    Toplevels, joined by newlines."""
    return _content_text


@pytest.fixture
def page_text():
    """``page_text(gui)`` → the text of the page in the content area only
    (no sidebar, no Toplevels), joined by newlines. A screen that opens as a
    page is asserted by its heading being one of these lines."""
    return _page_text


@pytest.fixture
def toplevels():
    """``toplevels(gui)`` → the Toplevel windows currently open."""
    return _toplevels

@pytest.fixture
def fresh_data_dir(tmp_path, monkeypatch):
    """Redirect the primary data dir at a brand-new directory.

    Reloads ``education_system.paths`` so ``DATA_DIR`` / ``PUPILS_DB`` re-read the env
    override, and restores the default module state afterwards so downstream
    tests see the real package paths again.
    """
    import importlib

    target = tmp_path / "data"
    monkeypatch.setenv("EDU_PRIMARY_DATA_DIR", str(target))
    from education_system import paths as paths_mod
    reloaded = importlib.reload(paths_mod)
    try:
        yield reloaded
    finally:
        monkeypatch.delenv("EDU_PRIMARY_DATA_DIR", raising=False)
        importlib.reload(paths_mod)
