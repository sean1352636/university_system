"""Quick-switch toolbar + cross-process IPC for the 6 linked academic modules.

Modules surfaced on the bar:
    course_mgmt, module_scheduling, timetable,
    building_mgmt, attendance, study_matching, hub

In-process windows attach the bar via :func:`attach_quickbar`. Each
button calls a ``show_*`` method on the parent ``UnifiedManagementGUI``.

Building Management runs as a subprocess so it can't call the parent
directly. It writes a JSON request to :data:`IPC_FILE`; the parent's
poller (started by :func:`start_ipc_poller` from ``main_gui``) reads
the file every ~1.5 s, dispatches, and deletes it.
"""
from __future__ import annotations

import json
import logging
import pathlib
import tkinter as tk

logger = logging.getLogger(__name__)

IPC_FILE = (pathlib.Path.home() / ".cache" / "edu_system"
            / "academic_open_request.json")


# (key, button label, attribute on parent app to dispatch to)
_MODULES = [
    ("hub",               "🏛 Hub",        "show_academic_hub"),
    ("course_mgmt",       "🎓 Courses",    "show_course_management"),
    ("module_scheduling", "🗓 Scheduling", "show_module_scheduling"),
    ("timetable",         "📅 Timetable",  "show_student_timetable_gui"),
    ("building_mgmt",     "🏢 Buildings",  "show_new_feature_building_management"),
    ("attendance",        "✅ Attendance", "open_attendance_gui"),
    ("study_matching",    "🤝 Study Match","show_study_matching_gui"),
    ("library",           "📚 Library",    "show_library_management"),
]


# Cross-module jump destinations available to right-click menus but not
# rendered on the bar. Mapped just like _MODULES so the IPC poller can
# dispatch to them.
_EXTRA_DESTINATIONS = {
    "student_records": "show_student_records",
    "email_manager":   "show_email_manager",
    "finance_mgmt":    "show_finance_management",
    "student_finance": "show_student_finance_account",
    "audit_viewer":    "show_audit_log_viewer",
    "user_mgmt":       "show_user_management",
    "university_shop": "show_university_shop",
    "textbook_store":  "show_textbook_store_gui",
    "marketplace":     "show_marketplace_gui",
}


def attach_quickbar(window, parent_app, current: str = "", before=None):
    """Pack a colour-coded quick-switch toolbar at the top of *window*.

    *parent_app* must be a ``UnifiedManagementGUI`` instance. *current*
    is the key of the module the window represents — that button is
    highlighted to show 'you are here'. If *before* is given, the bar is
    packed above that already-packed widget (useful when the inner GUI
    has already packed a notebook before we get a chance to add the bar).
    """
    try:
        bar = tk.Frame(window, bg="#34495e")
        if before is not None:
            bar.pack(side="top", fill="x", before=before)
        else:
            bar.pack(side="top", fill="x")
        tk.Label(bar, text="Linked academic modules:",
                 bg="#34495e", fg="white",
                 font=("Arial", 9, "bold")).pack(side="left",
                                                  padx=(8, 6), pady=4)
        for key, label, attr in _MODULES:
            is_current = (key == current)
            btn = tk.Button(
                bar, text=label,
                relief="flat",
                bg="#1abc9c" if is_current else "#ecf0f1",
                fg="white" if is_current else "#2c3e50",
                font=("Arial", 9, "bold" if is_current else "normal"),
                padx=8, pady=2,
                command=(lambda a=attr: _dispatch(parent_app, a)),
            )
            btn.pack(side="left", padx=2, pady=3)
    except Exception:
        logger.exception("attach_quickbar failed")


def _dispatch(parent_app, attr: str, context: dict | None = None):
    """Dispatch a quickbar / IPC click to the parent's ``show_*`` method.

    Context (e.g. ``{"room_id": 42}``) is stashed on the parent as
    ``_last_academic_context`` before the handler runs. Handlers that
    are context-aware can read+consume it; handlers that aren't simply
    ignore it. Always set (including ``None``) so a stale context from a
    prior dispatch can't bleed into the next plain bar click.
    """
    try:
        try:
            parent_app._last_academic_context = context
        except Exception:
            pass
        fn = getattr(parent_app, attr, None)
        if not callable(fn):
            logger.warning("Quickbar dispatch: %s missing on parent", attr)
            return
        fn()
    except Exception:
        logger.exception("Quickbar dispatch %s failed", attr)


def consume_context(parent_app) -> dict | None:
    """Pop and return the pending academic context, if any.

    Receiver-side helper — call from a ``show_*`` method right after the
    Toplevel is created to find out if the user came from a contextual
    right-click."""
    ctx = getattr(parent_app, "_last_academic_context", None)
    try:
        parent_app._last_academic_context = None
    except Exception:
        pass
    return ctx or None


# ---------------------------------------------------------------------------
# Defensive ttk-style guard
# ---------------------------------------------------------------------------
# Several legacy GUIs (attendance_tracker, absence_tracking, exam_management,
# blockchain_credentials, plagiarism, etc.) directly call
# ``style.configure("TButton", …)`` / ``"Treeview"`` / ``"TLabelframe"`` on
# base ttk style names. Because ``ttk.Style`` is process-global, those edits
# bleed into every other widget in the running app — opening one of these
# child windows visibly changes the parent GUI's button, frame, and box
# colours. Patching each call site is impractical (50+ files); instead the
# launcher snapshots the base styles before constructing the child and
# restores them immediately after. The child keeps its own custom-named
# styles (Primary.TButton, Custom.TNotebook.Tab, etc.) — only the shared
# base styles are reverted.
_BASE_TTK_STYLES = (
    "TFrame", "TLabel", "TButton", "TLabelframe", "TLabelframe.Label",
    "TNotebook", "TNotebook.Tab", "TEntry", "TCombobox",
    "Treeview", "Treeview.Heading", "TScrollbar",
    "TCheckbutton", "TRadiobutton", "TMenubutton",
    "TSeparator", "TPanedwindow", "TProgressbar", "TScale", "TSpinbox",
)


def _snapshot_base_styles():
    """Capture (theme_name, {style: (configure_dict, map_dict)})."""
    try:
        from tkinter import ttk
        style = ttk.Style()
        theme = None
        try:
            theme = style.theme_use()
        except Exception:
            pass
        snap = {}
        for name in _BASE_TTK_STYLES:
            try:
                cfg = dict(style.configure(name) or {})
            except Exception:
                cfg = {}
            try:
                mp = dict(style.map(name) or {})
            except Exception:
                mp = {}
            snap[name] = (cfg, mp)
        return theme, snap
    except Exception:
        logger.exception("snapshot_base_styles failed")
        return None, {}


def _restore_base_styles(theme, snap, parent=None):
    """Re-apply each captured (configure, map) pair so any global mutations
    a child window made are reverted. Forces a parent redraw at the end."""
    try:
        from tkinter import ttk
        style = ttk.Style()
        if theme:
            try:
                if style.theme_use() != theme:
                    style.theme_use(theme)
            except Exception:
                pass
        for name, (cfg, mp) in (snap or {}).items():
            if cfg:
                try:
                    style.configure(name, **cfg)
                except Exception:
                    pass
            if mp:
                try:
                    style.map(name, **mp)
                except Exception:
                    pass
        if parent is not None:
            try:
                parent.update_idletasks()
            except Exception:
                pass
    except Exception:
        logger.exception("restore_base_styles failed")


def style_guarded(parent_root, child_window=None):
    """Context-manager: snapshot base ttk styles on enter, restore on exit
    (and on the child window's ``<Destroy>`` if one is supplied).

    Usage::

        with style_guarded(self.root, child_window=win):
            HeavyLegacyGUI(win, ...)
    """
    import contextlib

    @contextlib.contextmanager
    def _guard():
        theme, snap = _snapshot_base_styles()
        try:
            yield
        finally:
            _restore_base_styles(theme, snap, parent=parent_root)
            if child_window is not None:
                # Re-restore once more when the child is closed, in case the
                # child mutates styles dynamically after construction.
                try:
                    child_window.bind(
                        "<Destroy>",
                        lambda _e, t=theme, s=snap, p=parent_root:
                            _restore_base_styles(t, s, parent=p),
                        add="+",
                    )
                except Exception:
                    pass
    return _guard()


def format_context(ctx: dict | None) -> str:
    """Pretty-print a context dict for window-title suffixes."""
    if not ctx:
        return ""
    parts = []
    for k, v in ctx.items():
        if k == "room_id":
            parts.append(f"Room #{v}")
        elif k == "building_id":
            parts.append(f"Building #{v}")
        elif k == "course_id":
            parts.append(f"Course #{v}")
        elif k == "module_id":
            parts.append(f"Module #{v}")
        else:
            parts.append(f"{k}={v}")
    return " · ".join(parts)


# ---------------------------------------------------------------------------
# Cross-process IPC (used by Building Management subprocess)
# ---------------------------------------------------------------------------
def request_open(action: str, context: dict | None = None) -> None:
    """From a subprocess, ask the parent GUI to open another module."""
    try:
        IPC_FILE.parent.mkdir(parents=True, exist_ok=True)
        IPC_FILE.write_text(json.dumps(
            {"action": action, "context": context or {}}))
        logger.info("IPC open request: %s", action)
    except Exception:
        logger.exception("request_open failed")


def start_ipc_poller(parent_app, interval_ms: int = 1500) -> None:
    """Start the parent-side poller. Call once from main GUI startup."""
    valid = {key: attr for key, _, attr in _MODULES}
    valid.update(_EXTRA_DESTINATIONS)

    def _tick():
        try:
            if IPC_FILE.exists():
                data = {}
                try:
                    data = json.loads(IPC_FILE.read_text() or "{}")
                except Exception:
                    logger.exception("IPC: malformed request file")
                try:
                    IPC_FILE.unlink()
                except Exception:
                    pass
                action = data.get("action")
                ctx = data.get("context") or None
                if action in valid:
                    try:
                        parent_app.root.lift()
                        parent_app.root.focus_force()
                    except Exception:
                        pass
                    _dispatch(parent_app, valid[action], context=ctx)
        except Exception:
            logger.exception("IPC poller tick failed")
        finally:
            try:
                parent_app.root.after(interval_ms, _tick)
            except Exception:
                logger.exception("IPC poller scheduling failed")

    try:
        parent_app.root.after(interval_ms, _tick)
        logger.info("Academic IPC poller started")
    except Exception:
        logger.exception("Could not start IPC poller")


# ---------------------------------------------------------------------------
# Subprocess-side helper: build a Tk-only quickbar that uses request_open
# ---------------------------------------------------------------------------
def attach_subprocess_quickbar(window, current: str = ""):
    """Variant of :func:`attach_quickbar` for subprocess apps. Each
    button writes an IPC request instead of calling a parent method."""
    try:
        bar = tk.Frame(window, bg="#34495e")
        bar.pack(side="top", fill="x")
        tk.Label(bar, text="Linked academic modules:",
                 bg="#34495e", fg="white",
                 font=("Arial", 9, "bold")).pack(side="left",
                                                  padx=(8, 6), pady=4)
        for key, label, _attr in _MODULES:
            is_current = (key == current)
            btn = tk.Button(
                bar, text=label,
                relief="flat",
                bg="#1abc9c" if is_current else "#ecf0f1",
                fg="white" if is_current else "#2c3e50",
                font=("Arial", 9, "bold" if is_current else "normal"),
                padx=8, pady=2,
                command=(lambda k=key: request_open(k)),
            )
            btn.pack(side="left", padx=2, pady=3)
    except Exception:
        logger.exception("attach_subprocess_quickbar failed")
