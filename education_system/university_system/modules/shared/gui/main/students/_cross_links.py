"""Student records → other-GUI cross-links.

Mirrors the patterns established by
``academics/gui/library/_cross_links.py`` and
``academics/gui/academic_calendar/_cross_links.py``. Right-click on a
row in the student records tree opens jumps to every module in the
system that's keyed by ``student_id``. Most destinations were already
registered in ``_EXTRA_DESTINATIONS`` for the library cross-link work
in 8.117.6–8.117.13; this module is the wiring that finally points
*outward* from the student record (the canonical hub) instead of just
pointing inward.

Also contains :func:`audit_student_view` — a small wrapper around
``infrastructure.security.audit_trail.get_audit_logger`` that records
who opened which student detail window. Closes a GDPR gap: viewing a
student record is a sensitive operation but was previously invisible
to the audit log.
"""
from __future__ import annotations

import logging
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
        logger.exception("student records cross-jump failed: %s", action)


# ---------------------------------------------------------------------------
# GDPR audit hook
# ---------------------------------------------------------------------------

def audit_student_view(viewer_user_id, viewer_username, student_id,
                       *, action: str = "view_student_record"):
    """Record a student-record view in the audit log.

    Best-effort — never raises. Failure logs at debug only because we
    don't want a transient DB hiccup to block the GUI from showing
    the record. The compliance signal is strongest when the audit
    write *and* the GUI render happen together; if writes start
    failing systematically the audit log itself will show a gap, which
    is a different (and detectable) problem."""
    try:
        from education_system.university_system.infrastructure.security.audit_trail import (
            get_audit_logger,
        )
    except Exception:
        logger.debug("audit_trail unavailable; student view not logged")
        return
    try:
        get_audit_logger().log(
            action=action,
            resource_type="student",
            resource_id=str(student_id) if student_id else None,
            user_id=viewer_user_id,
            username=viewer_username,
            module_name="shared.gui.main.students.student_records_gui",
            function_name="show_student_details",
            success=True,
        )
    except Exception:
        logger.debug("audit_student_view write failed", exc_info=True)


# ---------------------------------------------------------------------------
# Right-click menu builder
# ---------------------------------------------------------------------------

def student_menu_items(values, *, parent=None, app=None):
    """Return ``(label, callable)`` pairs for a right-click on a
    student record row.

    *values* is the row's ``values`` tuple — by convention the records
    tree uses
    ``(student_id, full_name, email_address, course, registration_date)``.

    *app* is the ``UnifiedManagementGUI`` instance. When supplied,
    permission-checked action items are appended (Edit / Manage Grades
    / View Attendance / View Timetable / Export / Send Email) — the
    same list the detail-window's Actions tab exposes, surfaced here
    so users don't have to drill into the detail window just to fire
    one. Items that don't apply (no email, no course, missing perms)
    are omitted rather than greyed out so the menu stays tight.
    """
    if not values:
        return []
    student_id = values[0] if len(values) > 0 else None
    full_name = values[1] if len(values) > 1 else None
    email = values[2] if len(values) > 2 else None
    course = values[3] if len(values) > 3 else None
    if not student_id:
        return []

    sid = str(student_id)
    items: list[tuple[str, callable]] = []

    items.append(
        ("📨 Open in Email Manager",
         lambda u=sid: _jump("email_manager", {"student_id": u})),
    )
    items.append(
        ("💰 Open finance account",
         lambda u=sid: _jump("student_finance", {"student_id": u})),
    )
    items.append(
        ("📚 Open library activity",
         lambda u=sid: _jump("library", {"student_id": u})),
    )
    items.append(
        ("🕓 View audit log for this student (GDPR)",
         lambda u=sid: _jump("audit_viewer", {"student_id": u})),
    )

    # In-process snapshots reused from the library cross-link work
    # (8.117.13). They run directly off the loyalty / careers buses,
    # so they render straight from a right-click without a full
    # launcher round-trip.
    items.append(
        ("⭐ Loyalty snapshot",
         lambda u=sid: _open_loyalty_snapshot(u, parent=parent)),
    )
    items.append(
        ("💼 Careers engagements",
         lambda u=sid: _open_careers_snapshot(u, parent=parent)),
    )

    if course:
        items.append(
            (f"🎓 Open course management ({course})",
             lambda c=course: _jump("course_mgmt", {"course_code": str(c)})),
        )

    if email:
        items.append(
            ("✉ Copy email address",
             lambda e=email: _copy_to_clipboard(e, parent=parent)),
        )

    # ── Action items folded in from the detail-window's Actions tab ──
    # All gated on permissions; absent perms means the item simply
    # isn't appended. Names are a (first, last) tuple split from the
    # full_name column for callsites that want them separated.
    if app is not None:
        first, last = _split_name(full_name)
        auth = getattr(app, "auth", None)
        own_record = (auth and auth.current_user and
                      auth.current_user.get('student_id') == sid)

        def _has(perm):
            try:
                return bool(auth and auth.check_permission(perm))
            except Exception:
                return False

        if _has('update_any_student'):
            items.append(
                ("✏ Edit student record",
                 lambda u=sid: app.update_student_dialog(u)),
            )
        if _has('manage_grades'):
            items.append(
                ("📊 Manage grades",
                 lambda u=sid, f=first, l=last: app.manage_student_grades(u, f, l)),
            )
        if _has('manage_attendance') or own_record:
            items.append(
                ("✅ View attendance record",
                 lambda u=sid, e=email, f=first, l=last:
                     app.view_student_attendance(u, e, f, l)),
            )
        items.append(
            ("📅 View timetable",
             lambda u=sid, f=first, l=last: app.view_student_timetable(u, f, l)),
        )
        if _has('export_data'):
            items.append(
                ("⬇ Export this student's data",
                 lambda u=sid, f=first, l=last:
                     app.export_individual_student_data(u, f, l)),
            )
        if email:
            items.append(
                ("📧 Send email (templated)",
                 lambda e=email, f=first, l=last:
                     app.send_email_to_student(e, f, l)),
            )

    return items


def _split_name(full_name):
    """Best-effort first/last split from a single string. The records
    tree stores the full name as a single column; callees that want
    them separated do this on-the-fly. Empty input returns ('', '')."""
    if not full_name:
        return "", ""
    parts = str(full_name).strip().split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[-1]


def _open_loyalty_snapshot(user_id, parent=None):
    try:
        from education_system.university_system.modules.domain.academics.gui.library._cross_links import (
            show_loyalty_snapshot,
        )
        show_loyalty_snapshot(user_id, parent=parent)
    except Exception:
        logger.exception("loyalty snapshot reuse failed")


def _open_careers_snapshot(user_id, parent=None):
    try:
        from education_system.university_system.modules.domain.academics.gui.library._cross_links import (
            show_careers_snapshot,
        )
        show_careers_snapshot(user_id, parent=parent)
    except Exception:
        logger.exception("careers snapshot reuse failed")


def _copy_to_clipboard(text, parent=None):
    """Copy *text* to the system clipboard. Used for the Copy Email
    item — small enough to live here rather than spinning up another
    helper module."""
    if not text:
        return
    try:
        root = parent if parent is not None else tk._default_root
        if root is None:
            return
        root.clipboard_clear()
        root.clipboard_append(str(text))
        root.update()  # Required on Linux for the clipboard to stick
    except Exception:
        logger.debug("clipboard copy failed", exc_info=True)


def attach_cross_link_menu(tree, *, parent=None, app=None):
    """Bind a fresh right-click menu on *tree*. Same shape as the
    library helper of the same name — the menu is rebuilt per click
    so items can omit themselves based on the selected row's data
    *and* the current user's permissions.

    *app* (the ``UnifiedManagementGUI`` instance) is forwarded into
    ``student_menu_items`` so permission-checked action items can
    invoke methods on it."""
    def _show(event):
        try:
            row_iid = tree.identify_row(event.y)
            if row_iid:
                tree.selection_set(row_iid)
            sel = tree.selection()
            if not sel:
                return
            values = tree.item(sel[0]).get("values") or []
            items = student_menu_items(values, parent=parent, app=app)
            if not items:
                return
            menu = tk.Menu(tree, tearoff=0)
            for label, cmd in items:
                menu.add_command(label=label, command=cmd)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
        except Exception:
            logger.exception("student records right-click menu failed")
    try:
        tree.bind("<Button-3>", _show, add="+")
    except Exception:
        logger.exception("attach_cross_link_menu bind failed")
