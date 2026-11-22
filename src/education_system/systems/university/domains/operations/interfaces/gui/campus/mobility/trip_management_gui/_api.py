"""Shared plumbing for the Trip Management screens.

Every screen talks to the trip domain (``trip_management`` package) through
the functions it publishes: they check permissions themselves and raise
PermissionError / ValueError with messages written for users, which
:func:`show_error` shows as they are. Nothing in this package writes to a
trip table directly.

Slow work (anything that e-mails, posts to Finance, or reads across many
participants) runs through :func:`run_async`: the work happens on a worker
thread with its own database connection, and the result is handed back to
the Tk thread with ``after()`` — Tk is never touched from the worker.
"""

import importlib
import logging
import queue
import threading
import tkinter as tk
from tkinter import messagebox

from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)

TM_PACKAGE = ("education_system.systems.university.domains.operations.domain."
              "campus.mobility.services.trip_management")

_KEY = "gui.operations.campus.mobility.trip_management_gui.common"


def tm(module):
    """A trip_management domain module, imported on first use."""
    return importlib.import_module(f"{TM_PACKAGE}.{module}")


def tf(key, default, **values):
    """``_t`` with ``str.format`` applied to the default as well."""
    text = _t(key, default=default)
    try:
        return text.format(**values) if values else text
    except (KeyError, IndexError, ValueError):
        return default.format(**values) if values else default


# ---------------------------------------------------------------------------
# Errors and background work
# ---------------------------------------------------------------------------

def _parent(widget):
    try:
        return widget.winfo_toplevel() if widget is not None else None
    except tk.TclError:
        return None


def show_error(widget, exc, title=None):
    """Show a domain error to the user.

    PermissionError / ValueError carry messages written for users and are
    shown as they are; anything else is logged with its traceback and shown
    with its type, so a real fault is never dressed up as a refusal.
    """
    parent = _parent(widget)
    kw = {'parent': parent} if parent is not None else {}
    if isinstance(exc, PermissionError):
        messagebox.showerror(title or _t(f"{_KEY}.permission_denied", default="Permission Denied"),
                             str(exc) or _t(f"{_KEY}.not_allowed", default="You can't do that."), **kw)
    elif isinstance(exc, ValueError):
        messagebox.showwarning(title or _t(f"{_KEY}.not_possible", default="Not Possible"),
                               str(exc), **kw)
    else:
        logger.error("Trip Management error", exc_info=(type(exc), exc, exc.__traceback__))
        messagebox.showerror(title or _t(f"{_KEY}.error", default="Error"),
                             f"{type(exc).__name__}: {exc}", **kw)


def call(widget, fn, *args, title=None, **kwargs):
    """Run a quick domain call on the Tk thread. Returns ``(ok, result)``."""
    try:
        return True, fn(*args, **kwargs)
    except Exception as exc:  # shown to the user, not swallowed
        show_error(widget, exc, title)
        return False, None


def run_async(widget, work, on_done=None, on_error=None, *, status=None):
    """Run ``work()`` on a worker thread and hand the result back on the Tk thread.

    ``on_done(result)`` / ``on_error(exc)`` run on the Tk thread (polled with
    ``after``). ``status`` is an optional callable given a message while the
    work runs. A widget destroyed meanwhile simply drops the result.
    """
    results = queue.Queue(maxsize=1)

    def target():
        try:
            results.put((True, work()))
        except BaseException as exc:  # handed to the Tk thread
            results.put((False, exc))

    if status:
        try:
            status(_t(f"{_KEY}.working", default="Working..."))
        except Exception:
            logger.debug("status callback failed", exc_info=True)

    def poll():
        try:
            ok, value = results.get_nowait()
        except queue.Empty:
            try:
                widget.after(60, poll)
            except tk.TclError:
                pass
            return
        try:
            if not widget.winfo_exists():
                return
        except tk.TclError:
            return
        if status:
            try:
                status(_t("common.ready", default="Ready"))
            except Exception:
                logger.debug("status callback failed", exc_info=True)
        if ok:
            if on_done:
                on_done(value)
        elif on_error:
            on_error(value)
        else:
            show_error(widget, value)

    threading.Thread(target=target, daemon=True, name="trip-gui-worker").start()
    try:
        widget.after(60, poll)
    except tk.TclError:
        pass


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def money(value):
    try:
        return f"£{float(value or 0):.2f}"
    except (TypeError, ValueError):
        return "£0.00"


def title_case(value, default=""):
    return str(value).replace('_', ' ').title() if value not in (None, '') else default


def trip_label(trip):
    """``"12 - Lake District walk (2026-11-02) [Open]"`` — the picker format."""
    return (f"{trip['id']} - {trip.get('trip_name') or ''} "
            f"({trip.get('start_date') or '?'}) [{title_case(trip.get('status'))}]")


def parse_trip_id(text):
    """The trip id at the front of a picker entry, or ``None``."""
    try:
        return int(str(text).split(' - ')[0].split(':')[0].strip())
    except (TypeError, ValueError, IndexError):
        return None


def has_any(auth, *permissions):
    try:
        return any(auth.check_permission(p) for p in permissions)
    except Exception:
        logger.debug("permission check failed", exc_info=True)
        return False


APPROVER_PERMISSIONS = ('approve_trips_department', 'approve_trips_hs',
                        'approve_trips_finance', 'approve_trips_international')
WORKSPACE_PERMISSIONS = ('manage_trips', 'create_trips', 'manage_trip_participants',
                         'manage_trip_expenses', 'view_trip_reports') + APPROVER_PERMISSIONS


# ---------------------------------------------------------------------------
# Trip lists
# ---------------------------------------------------------------------------

def trips_for(auth, purpose='view', include_archived=False):
    """Trips for a picker.

    'view'   — anyone with ``manage_trips`` / ``create_trips`` / the trip
               workspace sees every trip; anyone else (students) the trips
               they are registered on.
    'manage' — trips the user may manage (``trips.can_manage_trip``),
               checked on one read connection.
    'mine'   — the trips the user is registered on.
    """
    trips = tm('trips')
    if purpose == 'mine' or (purpose == 'view' and not has_any(auth, *WORKSPACE_PERMISSIONS)):
        regs = tm('registrations').list_my_registrations(auth)
        seen, out = set(), []
        for r in regs:
            if r['trip_id'] in seen:
                continue
            seen.add(r['trip_id'])
            out.append({'id': r['trip_id'], 'trip_name': r['trip_name'],
                        'destination': r['destination'], 'start_date': r['start_date'],
                        'end_date': r['end_date'], 'status': r['trip_status']})
        return out
    rows = trips.list_trips(include_archived=include_archived)
    if purpose != 'manage' or auth.check_permission('manage_trips'):
        return rows
    db = tm('database')
    who = trips.actor(auth)
    with db.read_connection() as c:
        return [t for t in rows if trips.can_manage_trip(auth, t, conn=c, who=who)]


# ---------------------------------------------------------------------------
# Reads the domain has no function for yet.
#
# ``staff.py`` and ``itinerary.py`` publish writes only; these two read-only
# queries stand in for ``staff.list_staff`` / ``itinerary.list_items`` until
# the domain grows them. They run on the domain's own read connection.
# ---------------------------------------------------------------------------

def list_trip_staff(trip_id):
    """``[{id, staff_user_id, role, assigned_date, first_aider, dbs_status,
    dbs_checked_at, username, name}]`` for a trip (``staff.list_trip_staff``)."""
    return tm('staff').list_trip_staff(trip_id)


def list_itinerary(trip_id):
    """A trip's itinerary items in order (``itinerary.list_itinerary``)."""
    return tm('itinerary').list_itinerary(trip_id)


def staff_candidates(exclude_user_ids=()):
    """University users who can be put on a trip (the roles ``staff.assign_staff_member`` accepts)."""
    with tm('database').read_connection() as c:
        rows = c.execute(
            "SELECT id, first_name, last_name, username, role FROM users "
            "WHERE LOWER(role) IN ('admin', 'staff', 'instructor') ORDER BY role, last_name, username"
        ).fetchall()
    skip = set(exclude_user_ids or ())
    return [{'id': r[0], 'first_name': r[1], 'last_name': r[2], 'username': r[3], 'role': r[4]}
            for r in rows if r[0] not in skip]


def calendar_links():
    """``{trip_id: (event_id, title)}`` — trips that have an academic-calendar event."""
    try:
        with tm('database').read_connection() as c:
            rows = c.execute(
                "SELECT trip_id, source_event_id, title FROM unified_events "
                "WHERE source_type = 'academic_calendar' AND trip_id IS NOT NULL").fetchall()
    except Exception:
        logger.warning("calendar events could not be read", exc_info=True)
        return {}
    return {r[0]: (r[1], r[2]) for r in rows}


# ---------------------------------------------------------------------------
# Small shared widgets
# ---------------------------------------------------------------------------

def make_tree(parent, columns, *, height=10, show='headings'):
    """A Treeview with a vertical scrollbar, packed to fill ``parent``.

    ``columns`` is ``[(key, heading, width), ...]``. Pack any action bar
    *before* calling this so the bar is not squeezed out.
    """
    from tkinter import ttk
    frame = ttk.Frame(parent)
    frame.pack(fill=tk.BOTH, expand=True)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show=show, height=height)
    for key, heading, width in columns:
        tree.heading(key, text=heading)
        tree.column(key, width=width, stretch=True)
    scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    return tree


def clear_tree(tree):
    tree.delete(*tree.get_children())


def selected_iid(tree):
    sel = tree.selection()
    return sel[0] if sel else None


def text_window(parent, title, text, *, width=760, height=560, save_name="trip.txt"):
    """A read-only text window with Save and Print (``lpr``) buttons."""
    from tkinter import ttk, scrolledtext
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry(f"{width}x{height}")
    try:
        win.transient(_parent(parent))
    except tk.TclError:
        pass
    bar = ttk.Frame(win)
    bar.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=8)
    box = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=('Courier', 10))
    box.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))
    box.insert('1.0', text)
    box.config(state=tk.DISABLED)
    ttk.Button(bar, text=_t(f"{_KEY}.save", default="Save..."),
               command=lambda: save_text(win, text, save_name)).pack(side=tk.LEFT, padx=(0, 5))
    ttk.Button(bar, text=_t(f"{_KEY}.print", default="Print"),
               command=lambda: print_text(win, text)).pack(side=tk.LEFT, padx=5)
    ttk.Button(bar, text=_t(f"{_KEY}.close", default="Close"),
               command=win.destroy).pack(side=tk.RIGHT)
    return win


def save_text(parent, text, default_name):
    from tkinter import filedialog
    filename = filedialog.asksaveasfilename(
        parent=_parent(parent), defaultextension=".txt", initialfile=default_name,
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
    if not filename:
        return None
    try:
        with open(filename, 'w', encoding='utf-8') as fh:
            fh.write(text)
    except OSError as exc:
        show_error(parent, exc)
        return None
    messagebox.showinfo(_t(f"{_KEY}.saved", default="Saved"),
                        tf(f"{_KEY}.saved_to", "Saved to:\n{path}", path=filename),
                        parent=_parent(parent))
    return filename


def print_text(parent, text):
    """Send ``text`` to the default printer with ``lpr`` (or say it isn't there)."""
    import shutil
    import subprocess  # nosec B404 - fixed command, no shell
    lpr = shutil.which('lpr')
    if not lpr:
        messagebox.showwarning(
            _t(f"{_KEY}.print", default="Print"),
            _t(f"{_KEY}.no_printer",
               default="No print command (lpr) is available on this computer. "
                       "Use Save... and print the file instead."),
            parent=_parent(parent))
        return False
    try:
        subprocess.run([lpr], input=text.encode('utf-8'), check=True, timeout=30)  # nosec B603
    except (OSError, subprocess.SubprocessError) as exc:
        show_error(parent, exc)
        return False
    messagebox.showinfo(_t(f"{_KEY}.print", default="Print"),
                        _t(f"{_KEY}.sent_to_printer", default="Sent to the printer."),
                        parent=_parent(parent))
    return True


def ask_text(parent, title, prompt, *, initial="", required=True, height=5):
    """A small modal multi-line text prompt. Returns the text, or ``None`` if cancelled."""
    from tkinter import ttk
    top = tk.Toplevel(parent)
    top.title(title)
    try:
        top.transient(_parent(parent))
    except tk.TclError:
        pass
    ttk.Label(top, text=prompt, wraplength=460, justify=tk.LEFT).pack(anchor=tk.W, padx=12, pady=(12, 4))
    box = tk.Text(top, width=60, height=height, wrap=tk.WORD)
    box.pack(fill=tk.BOTH, expand=True, padx=12)
    box.insert('1.0', initial)
    result = {'value': None}

    def ok():
        value = box.get('1.0', tk.END).strip()
        if required and not value:
            messagebox.showwarning(title, _t(f"{_KEY}.text_required", default="Please enter some text."),
                                   parent=top)
            return
        result['value'] = value
        top.destroy()

    bar = ttk.Frame(top)
    bar.pack(fill=tk.X, padx=12, pady=10)
    ttk.Button(bar, text=_t(f"{_KEY}.ok", default="OK"), command=ok).pack(side=tk.RIGHT, padx=(5, 0))
    ttk.Button(bar, text=_t(f"{_KEY}.cancel", default="Cancel"), command=top.destroy).pack(side=tk.RIGHT)
    box.focus_set()
    try:
        top.grab_set()
    except tk.TclError:
        pass
    top.wait_window()
    return result['value']
