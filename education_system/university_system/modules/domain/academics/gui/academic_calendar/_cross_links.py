"""Academic Calendar → other-GUI cross-links.

Mirrors the pattern in
``academics/gui/library/_cross_links.py``. Right-click on an event row
gains "Open in <other module>" jumps that fire IPC requests through
``shared.gui.main.features.academic_link_bar.request_open``. The
parent ``UnifiedManagementGUI`` poller picks them up within ~1.5s,
lifts the main window, and dispatches to the matching ``show_*``
method.

Destinations used (all already registered in ``_MODULES`` /
``_EXTRA_DESTINATIONS``):

  - ``email_manager``    — open Email Manager scoped to the event
  - ``audit_viewer``     — pre-filtered by ``event_id``
  - ``building_mgmt``    — buildings GUI (subprocess; context degrades
                            to "just open buildings", but the user gets
                            there in one click)
  - ``room_booking``     — the existing study-room GUI
  - ``course_mgmt``      — only offered when we can extract a course
                            code from the event (description pattern
                            or ``module_code`` / ``course_code`` key)
  - ``attendance``       — open the attendance GUI scoped to event_id
  - ``student_records``  — from a per-attendee popup
  - ``printing``         — pre-fills the print-job form with the
                            event title, see ``_prefill_printing_job``
                            in 8.117.11

The "view attendees" item opens an in-process popup that runs against
``unified_event_registrations`` directly — same shape as the loyalty /
careers snapshots in ``library/_cross_links.show_*_snapshot``.
"""
from __future__ import annotations

import logging
import re
import tkinter as tk

logger = logging.getLogger(__name__)

try:
    from education_system.university_system.modules.shared.gui.main.features.academic_link_bar import (
        request_open as _request_open,
    )
except Exception:  # pragma: no cover
    def _request_open(action, context=None):  # type: ignore
        logger.debug("link-bar unavailable; ignoring request_open(%s)", action)


def _jump(action: str, context: dict | None = None):
    try:
        _request_open(action, context or {})
    except Exception:
        logger.exception("calendar cross-jump failed: %s ctx=%s", action, context)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Event IDs in the calendar are sometimes prefixed (``assignment_42``,
# ``trip_7``, ``fee_19``, ``library_loan_3``) because the events_view
# aggregates from multiple sources. Strip the prefix for cross-system
# lookups so audit log queries can find the bare numeric id.
_PREFIXED_ID_RE = re.compile(r"^[a-z_]+_(\d+)$")


def _normalise_event_id(value):
    """Return ``(bare_id, source)``. ``source`` is the prefix or
    ``None`` for native calendar events."""
    if value is None:
        return None, None
    s = str(value)
    m = _PREFIXED_ID_RE.match(s)
    if m:
        return m.group(1), s.rsplit("_", 1)[0]
    return s, None


def _extract_course_code(event: dict) -> str | None:
    """Best-effort: pull a course/module code out of an event dict.

    Looks at structured keys first (``module_code``, ``course_code``,
    ``course_id``); falls back to scanning ``description`` for
    ``(SOMECODE)`` — the format used by ``_get_assignment_events`` when
    it aggregates assignment due dates."""
    for key in ("module_code", "course_code", "course_id"):
        v = event.get(key)
        if v:
            return str(v)
    desc = event.get("description") or ""
    m = re.search(r"\(([A-Z][A-Z0-9_-]{1,15})\)", desc)
    if m:
        return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Attendees popup — minimum useful surface, in-process
# ---------------------------------------------------------------------------

def show_event_attendees(event_id, parent=None):
    """Read-only popup listing registrants from
    ``unified_event_registrations``. Right-click a row to jump to that
    student's record. Self-contained — runs against the central DB
    directly so it works regardless of whether the calendar's manager
    is initialised."""
    if not event_id:
        return
    import sqlite3
    from tkinter import ttk, messagebox
    from education_system.university_system.core.paths import (
        DEFAULT_DB_PATH,
    )

    bare, _src = _normalise_event_id(event_id)

    rows = []
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        try:
            cur = conn.execute(
                "SELECT registration_id, user_id, user_type, "
                "       COALESCE(status, 'registered'), created_at "
                "FROM unified_event_registrations "
                "WHERE event_id = ? "
                "ORDER BY registration_id DESC LIMIT 200",
                (bare,)
            )
            rows = cur.fetchall()
        except sqlite3.OperationalError:
            # Older schema — try the legacy table name. Tolerate
            # absence; the popup just shows an empty list.
            try:
                cur = conn.execute(
                    "SELECT id, user_id, 'student', "
                    "       COALESCE(status, 'registered'), created_at "
                    "FROM event_attendance WHERE event_id = ? "
                    "ORDER BY id DESC LIMIT 200",
                    (bare,)
                )
                rows = cur.fetchall()
            except sqlite3.OperationalError:
                rows = []
        conn.close()
    except Exception as exc:
        logger.exception("event attendees lookup failed")
        messagebox.showerror(
            "Lookup failed",
            f"Could not query attendees:\n{exc}",
            parent=parent)
        return

    win = tk.Toplevel(parent)
    win.title(f"Attendees — event {event_id}")
    win.geometry("700x420")
    if parent is not None:
        try:
            win.transient(parent)
        except Exception:
            pass

    header = tk.Frame(win, bg="#2c3e50", height=44)
    header.pack(fill="x")
    header.pack_propagate(False)
    tk.Label(header,
             text=f"👥  Attendees · event {event_id}",
             font=("Arial", 12, "bold"),
             bg="#2c3e50", fg="white").pack(side="left", padx=14, pady=10)
    tk.Label(header, text=f"{len(rows)} registration(s)",
             font=("Arial", 10), bg="#2c3e50",
             fg="#bdc3c7").pack(side="right", padx=14)

    body = ttk.Frame(win, padding=8)
    body.pack(fill="both", expand=True)

    cols = ("reg_id", "user_id", "user_type", "status", "registered_at")
    tree = ttk.Treeview(body, columns=cols, show="headings", height=14)
    for c, w in zip(cols, (70, 110, 90, 100, 160)):
        tree.heading(c, text=c.replace("_", " ").title())
        tree.column(c, width=w, anchor="w")
    tree.pack(side="left", fill="both", expand=True)
    sb = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
    sb.pack(side="right", fill="y")
    tree.configure(yscrollcommand=sb.set)

    if rows:
        for r in rows:
            tree.insert("", "end", values=(
                r[0], r[1] or "", r[2] or "", r[3] or "",
                (r[4] or "")[:19],
            ))
    else:
        tree.insert("", "end", values=(
            "—", "(no registrations)", "", "", ""))

    def _attendee_menu(ev):
        try:
            row_iid = tree.identify_row(ev.y)
            if not row_iid:
                return
            tree.selection_set(row_iid)
            vals = tree.item(row_iid).get("values") or []
            uid = vals[1] if len(vals) > 1 else None
            if not uid or uid == "(no registrations)":
                return
            menu = tk.Menu(tree, tearoff=0)
            menu.add_command(
                label="👤 Open student profile",
                command=lambda u=uid: _jump("student_records", {"student_id": str(u)}),
            )
            menu.add_command(
                label="📨 Open in Email Manager",
                command=lambda u=uid: _jump("email_manager", {"student_id": str(u)}),
            )
            try:
                menu.tk_popup(ev.x_root, ev.y_root)
            finally:
                menu.grab_release()
        except Exception:
            logger.exception("attendee row menu failed")

    tree.bind("<Button-3>", _attendee_menu, add="+")
    ttk.Button(win, text="Close",
               command=win.destroy).pack(pady=(0, 10))


# ---------------------------------------------------------------------------
# Menu builder — returns (label, callable) pairs for an event row
# ---------------------------------------------------------------------------

def event_menu_items(event: dict | None, parent=None):
    """Build the cross-link menu items for a calendar event row.

    *event* is the dict pulled out of the events tree's hidden
    ``full_data`` column (see ``events_view._load_events_data``).
    Items that don't apply (e.g. course jump when no code is found)
    are silently omitted instead of greyed out — the menu stays
    short."""
    if not event:
        return []

    raw_id = event.get("id")
    bare_id, source = _normalise_event_id(raw_id)
    title = event.get("name") or event.get("title") or ""
    # Strip leading icon ("📚 Title" → "Title") for cleaner forwarding.
    if title and " " in title:
        head, _, rest = title.partition(" ")
        if not any(c.isalnum() for c in head):
            title = rest.strip() or title
    location = event.get("location") or ""
    date = event.get("date") or event.get("date_start") or ""
    course_code = _extract_course_code(event)

    items: list[tuple[str, callable]] = []

    if raw_id:
        items.append(
            ("📨 Open in Email Manager",
             lambda eid=raw_id, t=title: _jump(
                 "email_manager",
                 {"event_id": str(eid),
                  **({"event_title": t} if t else {})})),
        )
        items.append(
            ("🕓 View audit log for this event",
             lambda b=bare_id: _jump("audit_viewer", {"event_id": str(b)})),
        )
        items.append(
            ("👥 View attendees",
             lambda eid=raw_id: show_event_attendees(eid, parent=parent)),
        )
        items.append(
            ("✅ Mark attendance",
             lambda eid=raw_id: _jump(
                 "attendance",
                 {"event_id": str(eid),
                  **({"event_title": title} if title else {})})),
        )

    if location:
        items.append(
            ("🏢 Show event location (Buildings)",
             lambda loc=location: _jump(
                 "building_mgmt", {"event_location": str(loc)})),
        )

    if date:
        items.append(
            ("🪑 Book a room for this event",
             lambda d=date, c=event.get("capacity"): _jump(
                 "room_booking",
                 {"event_date": str(d),
                  **({"capacity": int(c)} if isinstance(c, int) and c else {})})),
        )

    if course_code:
        items.append(
            (f"🎓 Open course {course_code}",
             lambda cc=course_code: _jump(
                 "course_mgmt", {"course_code": cc})),
        )

    if title:
        items.append(
            ("🖨 Print event flyer",
             lambda t=title: _jump("printing", {"book_title": t})),
        )

    return items


def append_to_menu(menu: tk.Menu, items):
    """Append (separator + menu items) to an existing tk.Menu.
    Used by ``events_view._create_events_context_menu`` to stitch the
    cross-link items onto the bottom of the calendar's existing
    edit/delete/details menu."""
    if not items:
        return
    try:
        menu.add_separator()
    except Exception:
        pass
    for label, cmd in items:
        try:
            menu.add_command(label=label, command=cmd)
        except Exception:
            logger.exception("append_to_menu: add_command failed: %s", label)
