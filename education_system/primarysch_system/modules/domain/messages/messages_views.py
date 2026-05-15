"""Tkinter views for Primary School Email / Messaging."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.primarysch_system.modules.domain.messages import messages
from education_system.primarysch_system.modules.domain.parent_contacts import parent_contacts
from education_system.primarysch_system.modules.domain.staff import staff
from education_system.primarysch_system.modules.domain.messages import messages as data
from education_system.primarysch_system.modules.domain.parent_contacts import parent_contacts as pc_data
from education_system.primarysch_system.modules.domain.staff import staff as staff_data
from education_system.primarysch_system.modules.domain import _pupils_bridge as student_data
from education_system.shared import branding
from education_system.primarysch_system.modules.domain.messages.messages import (
    CATEGORIES,
    CHANNELS,
    DEFAULT_CATEGORY,
    DEFAULT_CHANNEL,
    DEFAULT_PRIORITY,
    DEFAULT_STATUS,
    DIRECTIONS,
    Message,
    PRIORITIES,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_messages_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    # Pick up the signed-in session so the Compose dialog can offer
    # cross-system recipients (and know who's sending if one is picked).
    auth = getattr(parent, "auth", None)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Email / Messaging — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    MailboxTab(nb, auth=auth)
    ThreadsTab(nb)
    BulkTab(nb)
    SummaryTab(nb)


# ── Cross-system support ──────────────────────────────────────────
# A sixth-form user can address a single message to a colleague at
# any of the other three systems. We surface this as an extra row
# in the Compose dialog rather than a separate window, mirroring
# the university's UnifiedInboxPanel compose flow.

OWN_SYSTEM_KEY: str = "college"

CROSS_SYSTEM_NAMES: dict[str, str] = {
    "university": "University",
    "school":     "Secondary School",
    "primary":    "Primary School",
}


def _recipient_directory() -> list[dict]:
    """Unified list of every recipient the Compose dialog can target.

    Each entry has at least ``label`` + ``kind`` (``student``,
    ``staff``, ``parent``, or ``cross``) plus the fields needed to
    populate the message row when picked. Cross-system entries also
    carry ``id`` + ``system_key`` for the shared messaging service.

    Sorted with sixth-form recipients first (students → staff →
    parents) and cross-system staff last, since the common case is
    talking to someone in our own school.
    """
    entries: list[dict] = []

    # Students
    try:
        for s in sorted(student_data.list_students(),
                         key=lambda x: (x.last_name, x.first_name)):
            entries.append({
                "kind":       "student",
                "label":      f"{s.full_name} (Student) — {s.email}",
                "to_name":    s.full_name,
                "to_address": s.email or "",
                "student_id": s.student_id,
                "staff_id":   "",
                "parent_contact_id": None,
            })
    except Exception:
        logger.exception("Recipient directory: student load failed")

    # Staff
    try:
        for t in sorted(staff_data.list_staff(active_only=False),
                         key=lambda x: (x.last_name, x.first_name)):
            entries.append({
                "kind":       "staff",
                "label":      f"{t.full_name} ({t.role}) — {t.email or ''}",
                "to_name":    t.full_name,
                "to_address": t.email or "",
                "student_id": "",
                "staff_id":   t.staff_id,
                "parent_contact_id": None,
            })
    except Exception:
        logger.exception("Recipient directory: staff load failed")

    # Parent contacts (one entry per contact; we look up the
    # student name so the label is descriptive).
    try:
        student_names = {s.student_id: s.full_name
                          for s in student_data.list_students()}
        for c in pc_data.list_contacts():
            sn = student_names.get(c.student_id, "?")
            email = c.email or ""
            entries.append({
                "kind":       "parent",
                "label":      (f"{c.full_name} (Parent of {sn})"
                                + (f" — {email}" if email else "")),
                "to_name":    c.full_name,
                "to_address": email,
                "student_id": c.student_id,
                "staff_id":   "",
                "parent_contact_id": c.contact_id,
            })
    except Exception:
        logger.exception("Recipient directory: parent-contact load failed")

    # Cross-system staff (university / school / primary)
    for e in _cross_system_directory():
        entries.append({
            "kind":         "cross",
            "label":        e["label"],
            "to_name":      e["display_name"],
            "to_address":   e.get("email") or "",
            "student_id":   "",
            "staff_id":     "",
            "parent_contact_id": None,
            "id":           e["id"],
            "system_key":   e["system_key"],
        })

    return entries


def _cross_system_directory() -> list[dict]:
    """Return staff in every system *except* this one.

    Each entry: ``{id, system_key, display_name, role, label}``.
    Empty list on any error so the Compose dialog still works as a
    local-only message form.
    """
    out: list[dict] = []
    try:
        from education_system.shared.messaging.messaging_service import (
            InterSystemMessagingService,
        )
    except Exception:
        logger.debug("Shared cross-system service unavailable",
                     exc_info=True)
        return out
    try:
        svc = InterSystemMessagingService()
    except Exception:
        logger.exception("Could not construct InterSystemMessagingService")
        return out
    # Cross-system staff come from the InterSystemMessagingService,
    # which queries the auth.db users table but doesn't return the
    # ``email`` column. Pull emails ourselves in one extra query so
    # the Compose dialog can pre-fill the "To address" field with a
    # real address rather than leaving it blank.
    emails: dict[int, str] = {}
    try:
        from education_system.shared.auth.db import connect as _auth_connect
        with _auth_connect() as conn:
            for row in conn.execute(
                "SELECT id, email FROM users WHERE email IS NOT NULL"
            ).fetchall():
                emails[row["id"]] = row["email"]
    except Exception:
        logger.debug("Could not load cross-system emails",
                     exc_info=True)

    for sys_key in CROSS_SYSTEM_NAMES:
        if sys_key == OWN_SYSTEM_KEY:
            continue
        try:
            staff = svc.get_staff_list(sys_key)
        except Exception:
            logger.exception("Staff list for %s failed", sys_key)
            continue
        for s in staff:
            name = s.get("display_name") or s.get("username") or ""
            uid = s.get("id")
            out.append({
                "id":           uid,
                "system_key":   sys_key,
                "display_name": name,
                "role":         s.get("role", ""),
                "email":        emails.get(uid, "") if uid is not None else "",
                "label": (f"{name} ({s.get('role', '')}) — "
                          f"{CROSS_SYSTEM_NAMES.get(sys_key, sys_key)}"),
            })
    return out


# ── Shared helpers ────────────────────────────────────────────────

def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}") for s in rows]


def _staff_options(active_only: bool = True) -> list[tuple[str, str]]:
    rows = sorted(staff_data.list_staff(active_only=active_only),
                   key=lambda s: (s.last_name, s.first_name))
    return [(t.staff_id,
              f"{t.staff_id} — {t.full_name} ({t.role})")
            for t in rows]


def _student_names() -> dict[str, str]:
    return {s.student_id: s.full_name for s in student_data.list_students()}


# ══ Mailbox tab ════════════════════════════════════════════════════

class MailboxTab:
    VIEWS: tuple[str, ...] = (
        "All", "Inbox (Incoming)", "Outbox (Sent)",
        "Drafts", "Queued", "Failed",
    )

    def __init__(self, nb: ttk.Notebook, *, auth=None) -> None:
        self.frame = ttk.Frame(nb)
        self.auth = auth
        nb.add(self.frame, text="Mailbox")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="View:").pack(side="left")
        self.view_cb = ttk.Combobox(bar, values=self.VIEWS,
                                       state="readonly", width=18)
        self.view_cb.current(0)
        self.view_cb.pack(side="left", padx=(2, 10))
        self.view_cb.bind("<<ComboboxSelected>>",
                              lambda _e: self.refresh())

        ttk.Label(bar, text="Search:").pack(side="left")
        self.q_e = ttk.Entry(bar, width=20)
        self.q_e.pack(side="left", padx=(2, 10))
        self.q_e.bind("<Return>", lambda _e: self.refresh())

        ttk.Label(bar, text="Channel:").pack(side="left")
        self.f_chan = ttk.Combobox(bar, values=("",) + CHANNELS,
                                      state="readonly", width=14)
        self.f_chan.current(0)
        self.f_chan.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Category:").pack(side="left")
        self.f_cat = ttk.Combobox(bar, values=("",) + CATEGORIES,
                                     state="readonly", width=18)
        self.f_cat.current(0)
        self.f_cat.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Student:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        # iid format on the tree distinguishes local rows from
        # cross-system inbound rows: local rows use the bare message
        # id (e.g. "42"); cross-system rows use "cs-<id>" (e.g.
        # "cs-7"). This lets the action handlers tell them apart.
        cols = ("id", "dir", "channel", "status", "pri", "when",
                "student", "to", "subject")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 60, "dir": 40, "channel": 90, "status": 90,
                  "pri": 70, "when": 140, "student": 90,
                  "to": 200, "subject": 360}
        headings = {"id": "#", "dir": "Dir", "channel": "Channel",
                    "status": "Status", "pri": "Priority", "when": "When",
                    "student": "Student", "to": "To",
                    "subject": "Subject"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Urgent", background="#ffd0d0")
        self.tree.tag_configure("High", background="#ffe6d0")
        self.tree.tag_configure("Draft", foreground="#666",
                                  background="#f0f0f0")
        self.tree.tag_configure("Failed", background="#ffe0e0")
        self.tree.bind("<Double-1>", lambda _e: self._view_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        self.actions_holder = ttk.Frame(self.frame)
        self.actions_holder.pack(fill="x", padx=8, pady=(4, 8))
        self._build_actions()

    def _build_actions(self) -> None:
        for w in self.actions_holder.winfo_children():
            w.destroy()
        bar = ttk.Frame(self.actions_holder)
        bar.pack(fill="x")
        ttk.Button(bar, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(bar, text="Compose",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(bar, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Reply",
                    command=self._reply_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.q_e.delete(0, "end")
        self.f_chan.current(0)
        self.f_cat.current(0)
        self.f_student.delete(0, "end")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        view = self.view_cb.get()
        q = self.q_e.get().strip()
        try:
            if q:
                rows = data.search_messages(q)
            else:
                kwargs: dict = {
                    "channel":    self.f_chan.get() or None,
                    "category":   self.f_cat.get() or None,
                    "student_id": self.f_student.get().strip() or None,
                }
                if view == "Inbox (Incoming)":
                    kwargs["direction"] = "Incoming"
                elif view == "Outbox (Sent)":
                    kwargs["direction"] = "Outgoing"
                    kwargs["sent_only"] = True
                elif view == "Drafts":
                    kwargs["drafts_only"] = True
                elif view == "Queued":
                    kwargs["status"] = "Queued"
                elif view == "Failed":
                    kwargs["status"] = "Failed"
                rows = data.list_messages(**kwargs)
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for m in rows:
            tags = []
            if m.priority in ("Urgent", "High"):
                tags.append(m.priority)
            if m.status == "Draft":
                tags.append("Draft")
            elif m.status == "Failed":
                tags.append("Failed")
            self.tree.insert("", "end", iid=str(m.message_id), values=(
                m.message_id,
                "OUT" if m.direction == "Outgoing" else "IN",
                m.channel, m.status, m.priority,
                (m.sent_at or m.received_at or m.created_at)[:19],
                m.student_id or "—", m.to_name or "—", m.subject,
            ), tags=tuple(tags))

        # ── Cross-system inbox ──────────────────────────────────────
        # Pull messages from other systems addressed to the signed-in
        # user. They live in ``cross_system_messages`` in auth.db,
        # not in our local messages table, so list_messages() doesn't
        # see them. Mirror them into the tree as virtual rows.
        cross_rows: list[dict] = []
        if view in ("All", "Inbox (Incoming)"):
            cross_rows = self._load_cross_system_inbox()
            for m in cross_rows:
                tags = ["CrossSystem"]
                if not m.get("is_read"):
                    tags.append("CrossUnread")
                sender_system = m.get("sender_system", "")
                sender_label = (CROSS_SYSTEM_NAMES.get(sender_system,
                                                       sender_system)
                                or sender_system)
                from_who = (m.get("sender_name")
                            or f"[{sender_label}]")
                when = (m.get("created_at") or "")[:19]
                self.tree.insert(
                    "", 0,  # newest cross-system rows at the top
                    iid=f"cs-{m['id']}",
                    values=(
                        f"cs{m['id']}",
                        "IN",
                        f"X-{sender_label}",
                        "Read" if m.get("is_read") else "Unread",
                        "Normal",
                        when,
                        m.get("student_id") or "—",
                        from_who,
                        m.get("subject", ""),
                    ),
                    tags=tuple(tags),
                )
        # Visual highlight for the virtual cross-system rows.
        try:
            self.tree.tag_configure(
                "CrossSystem", background="#eef4ff")
            self.tree.tag_configure(
                "CrossUnread", font=("", 10, "bold"))
        except tk.TclError:
            pass

        total = len(rows) + len(cross_rows)
        self.count_var.set(
            f"{total} message(s)"
            + (f" (incl. {len(cross_rows)} cross-system)"
               if cross_rows else "")
            + ".")
        self._build_actions()

    def _current_user_auth_id(self) -> int | None:
        """Resolve the signed-in user's auth.db ``users.id`` so we
        can look up their cross-system inbox. Returns ``None`` if
        the session is missing or doesn't expose a usable id."""
        cu = (self.auth.current_user
              if self.auth and getattr(self.auth, "current_user", None)
              else None)
        if not cu:
            return None
        return (cu.get("shared_auth_id") or cu.get("user_id")
                 or cu.get("id"))

    def _load_cross_system_inbox(self) -> list[dict]:
        uid = self._current_user_auth_id()
        if uid is None:
            return []
        try:
            from education_system.shared.messaging.messaging_service import (
                InterSystemMessagingService,
            )
            svc = InterSystemMessagingService()
            return svc.get_inbox(uid, system=OWN_SYSTEM_KEY)
        except Exception:
            logger.exception("Cross-system inbox load failed")
            return []

    def _selected_iid(self) -> str | None:
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _selected(self) -> Message | None:
        """Return the selected *local* message, or ``None``. For
        cross-system rows (iid starts with ``cs-``) this returns
        ``None`` — callers should test ``_selected_iid()`` first if
        they need to handle the cross-system case."""
        iid = self._selected_iid()
        if iid is None or iid.startswith("cs-"):
            return None
        try:
            return data.get_message(int(iid))
        except ValueError:
            return None

    def _selected_cross(self) -> dict | None:
        """Return the selected cross-system message, or ``None``."""
        iid = self._selected_iid()
        if iid is None or not iid.startswith("cs-"):
            return None
        try:
            cs_id = int(iid.split("-", 1)[1])
        except (ValueError, IndexError):
            return None
        try:
            from education_system.shared.messaging.messaging_service import (
                InterSystemMessagingService,
            )
            return InterSystemMessagingService().get_message(cs_id)
        except Exception:
            logger.exception("Could not load cross-system message %s", iid)
            return None

    def _view_selected(self) -> None:
        cs = self._selected_cross()
        if cs is not None:
            _CrossSystemViewDialog(
                self.frame.winfo_toplevel(), cs,
                on_close=self.refresh)
            return
        m = self._selected()
        if m is None:
            messagebox.showinfo("View", "Select a message first.")
            return
        ViewDialog(self.frame.winfo_toplevel(), m)

    def _new(self) -> None:
        MessageDialog(self.frame.winfo_toplevel(), existing=None,
                        on_save=self.refresh, auth=self.auth)

    def _edit_selected(self) -> None:
        if self._selected_cross() is not None:
            messagebox.showinfo(
                "Edit",
                "Cross-system messages belong to the sending system "
                "and can't be edited here.")
            return
        m = self._selected()
        if m is None:
            messagebox.showinfo("Edit", "Select a message first.")
            return
        MessageDialog(self.frame.winfo_toplevel(), existing=m,
                        on_save=self.refresh, auth=self.auth)

    def _send_selected(self) -> None:
        m = self._selected()
        if m is None:
            messagebox.showinfo("Send", "Select a message first.")
            return
        try:
            data.send_message(m.message_id)
        except ValidationError as e:
            messagebox.showerror("Send failed", str(e))
            return
        self.refresh()

    def _reply_selected(self) -> None:
        cs = self._selected_cross()
        if cs is not None:
            self._reply_cross(cs)
            return
        m = self._selected()
        if m is None:
            messagebox.showinfo("Reply", "Select a message first.")
            return
        MessageDialog(self.frame.winfo_toplevel(),
                        existing=None, reply_to=m,
                        on_save=self.refresh, auth=self.auth)

    def _reply_cross(self, cs: dict) -> None:
        """Open the Compose dialog pre-pointed at the original sender
        of a cross-system message."""
        dlg = MessageDialog(
            self.frame.winfo_toplevel(),
            existing=None, reply_to=None,
            on_save=self.refresh, auth=self.auth)
        # Pre-select the original sender in the unified recipient
        # picker so the send routes back via the cross-system path.
        try:
            for i, entry in enumerate(dlg._recip_dir, start=1):
                if (entry.get("kind") == "cross"
                        and entry.get("id") == cs.get("sender_id")
                        and entry.get("system_key") == cs.get("sender_system")):
                    dlg.recip_cb.current(i)
                    dlg._on_recipient_change()
                    break
            subj = cs.get("subject") or ""
            if subj and not subj.lower().startswith("re:"):
                subj = f"Re: {subj}"
            dlg.subj_e.delete(0, "end")
            dlg.subj_e.insert(0, subj)
            quoted = "\n\n--- Original message ---\n" + (cs.get("body") or "")
            dlg.body_text.insert("1.0", quoted)
        except Exception:
            logger.exception("Pre-fill of cross-system reply failed")

    def _status_selected(self) -> None:
        m = self._selected()
        if m is None:
            messagebox.showinfo("Status", "Select a message first.")
            return
        StatusDialog(self.frame.winfo_toplevel(),
                      title=f"Message #{m.message_id} status",
                      current=m.status, options=list(STATUSES),
                      on_save=lambda s:
                          self._save_status(m.message_id, s))

    def _save_status(self, mid: int, status: str) -> None:
        try:
            data.set_status(mid, status)
        except ValidationError as e:
            messagebox.showerror("Failed", str(e))
            return
        self.refresh()

    def _delete_selected(self) -> None:
        if self._selected_cross() is not None:
            messagebox.showinfo(
                "Delete",
                "Cross-system messages are owned by the sending "
                "system; you can't delete them from here.")
            return
        m = self._selected()
        if m is None:
            messagebox.showinfo("Delete", "Select a message first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete message #{m.message_id} "
                f"({m.subject!r})?"):
            return
        try:
            data.delete_message(m.message_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


class StatusDialog:
    def __init__(self, parent: tk.Misc, *,
                 title: str, current: str, options: list[str],
                 on_save: Callable[[str], None]) -> None:
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=options, state="readonly",
                                  width=20)
        self.cb.set(current)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        v = self.cb.get()
        self.win.destroy()
        self.on_save(v)


class _CrossSystemViewDialog:
    """Read-only viewer for cross-system inbound messages.

    Looks like the regular ``ViewDialog`` so the user has a uniform
    experience, but reads from the ``cross_system_messages`` row
    instead of the local ``messages`` table. Marks the row as read
    on open so the bold-unread highlight clears.
    """

    def __init__(self, parent: tk.Misc, cs: dict,
                  on_close=None) -> None:
        self._on_close = on_close
        sender_sys = cs.get("sender_system", "")
        sender_sys_label = CROSS_SYSTEM_NAMES.get(sender_sys, sender_sys)
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Cross-system message #{cs.get('id')}"
            f" — from {sender_sys_label}")
        self.win.transient(parent)
        self.win.geometry("700x600")

        head = ttk.Frame(self.win)
        head.pack(fill="x", padx=12, pady=(12, 4))
        ttk.Label(head, text=cs.get("subject", "(no subject)"),
                   font=("", 12, "bold"), anchor="w").pack(fill="x")
        info_lines = [
            f"#cs-{cs.get('id')}  •  [Cross-system]  •  "
            f"from {sender_sys_label}",
            f"From: {cs.get('sender_name') or '—'}",
            f"To:   {cs.get('recipient_name') or '—'}  "
            f"({CROSS_SYSTEM_NAMES.get(cs.get('recipient_system',''), cs.get('recipient_system',''))})",
        ]
        if cs.get("student_name") or cs.get("student_id"):
            info_lines.append(
                f"Student: {cs.get('student_id') or '—'}"
                + (f"  ({cs.get('student_name')})"
                    if cs.get("student_name") else ""))
        info_lines.append(f"Sent: {cs.get('created_at') or '—'}")
        ttk.Label(head, text="\n".join(info_lines),
                   foreground="#444", anchor="w",
                   justify="left").pack(fill="x", pady=(4, 4))
        ttk.Separator(self.win).pack(fill="x", padx=12, pady=4)

        body_box = tk.Text(self.win, wrap="word")
        body_box.insert("1.0", cs.get("body", ""))
        body_box.configure(state="disabled")
        body_box.pack(fill="both", expand=True, padx=12, pady=8)

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(bar, text="Close",
                    command=self._close).pack(side="right")

        # Mark read on open (best-effort).
        try:
            from education_system.shared.messaging.messaging_service import (
                InterSystemMessagingService,
            )
            InterSystemMessagingService().mark_read(cs.get("id"))
        except Exception:
            logger.exception("Could not mark cross-system message read")

    def _close(self) -> None:
        self.win.destroy()
        if self._on_close:
            try:
                self._on_close()
            except Exception:
                logger.exception("Cross-system viewer on_close raised")


class ViewDialog:
    def __init__(self, parent: tk.Misc, m: Message) -> None:
        data.set_status  # keep import
        self.win = tk.Toplevel(parent)
        self.win.title(f"Message #{m.message_id}")
        self.win.transient(parent)
        self.win.geometry("700x600")
        names = _student_names()
        head = ttk.Frame(self.win)
        head.pack(fill="x", padx=12, pady=(12, 4))
        ttk.Label(head, text=m.subject,
                   font=("", 12, "bold"), anchor="w").pack(
            fill="x")
        info_lines = [
            f"#{m.message_id}  •  Thread {m.thread_id}"
            + (f"  (reply to #{m.reply_to_message_id})"
                if m.reply_to_message_id else ""),
            f"{m.direction}  •  {m.channel}  •  "
            f"{m.category}  •  {m.priority}  •  {m.status}",
            f"From: {m.from_name or '—'}"
            + (f"  <{m.from_address}>" if m.from_address else ""),
            f"To:   {m.to_name or '—'}"
            + (f"  <{m.to_address}>" if m.to_address else "")
            + (f"   (CC: {m.cc_address})" if m.cc_address else ""),
            f"Student: {m.student_id or '—'}"
            + (f"  ({names.get(m.student_id)})"
                if m.student_id and m.student_id in names else "")
            + f"   Staff: {m.staff_id or '—'}",
            f"Sent: {m.sent_at or '—'}   "
            f"Received: {m.received_at or '—'}",
        ]
        if m.tags:
            info_lines.append(f"Tags: {m.tags}")
        if m.attachments_note:
            info_lines.append(f"Attached: {m.attachments_note}")
        ttk.Label(head, text="\n".join(info_lines),
                   foreground="#444", anchor="w",
                   justify="left").pack(fill="x", pady=(4, 4))
        sep = ttk.Separator(self.win)
        sep.pack(fill="x", padx=12, pady=4)
        body_box = tk.Text(self.win, wrap="word")
        body_box.insert("1.0", m.body)
        if m.notes:
            body_box.insert("end",
                              f"\n\n──────── Notes ────────\n{m.notes}")
        body_box.configure(state="disabled")
        body_box.pack(fill="both", expand=True, padx=12, pady=8)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")


class MessageDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Message | None,
                 reply_to: Message | None = None,
                 on_save: Callable[[], None],
                 auth=None) -> None:
        self.existing = existing
        self.reply_to = reply_to
        self.on_save = on_save
        self.auth = auth
        self.win = tk.Toplevel(parent)
        title = ("Edit Message" if existing
                  else f"Reply to #{reply_to.message_id}" if reply_to
                  else "New Message")
        self.win.title(title)
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _seed(self, field: str, fallback: str = "") -> str:
        if self.existing:
            return getattr(self.existing, field) or fallback
        if self.reply_to:
            return getattr(self.reply_to, field) or fallback
        return fallback

    def _build(self) -> None:
        # ── Window sizing ────────────────────────────────────────────
        # Match the rest of the sixth-form GUIs and pick a default
        # geometry large enough that the bottom button bar always
        # sits in view. The internal form is scrollable as well so
        # the user can't get stuck if the screen is tiny.
        self.win.geometry("780x720")
        self.win.minsize(640, 520)

        # ── Bottom-pinned button bar (outside the scroll region) ────
        # Packed first so it claims its space before the canvas fills
        # the rest, guaranteeing Send is always visible.
        bar = ttk.Frame(self.win, padding=(12, 8))
        bar.pack(side="bottom", fill="x")
        ttk.Separator(self.win, orient="horizontal").pack(
            side="bottom", fill="x")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left")
        if not self.existing:
            ttk.Button(bar, text="Send",
                        command=self._save_and_send,
                        style="Accent.TButton").pack(side="right")
            ttk.Button(bar, text="Save Draft",
                        command=self._save).pack(side="right", padx=8)
        else:
            ttk.Button(bar, text="Save",
                        command=self._save).pack(side="right")

        # ── Scrollable form area ────────────────────────────────────
        outer = ttk.Frame(self.win)
        outer.pack(side="top", fill="both", expand=True)
        canvas = tk.Canvas(outer, highlightthickness=0, borderwidth=0)
        vs = ttk.Scrollbar(outer, orient="vertical",
                            command=canvas.yview)
        canvas.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        form = ttk.Frame(canvas, padding=12)
        win_id = canvas.create_window((0, 0), window=form, anchor="nw")
        form.columnconfigure(1, weight=1)

        def _on_form_config(_e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        form.bind("<Configure>", _on_form_config)

        def _on_canvas_config(e):
            canvas.itemconfigure(win_id, width=e.width)
        canvas.bind("<Configure>", _on_canvas_config)

        # Mouse-wheel scrolling while the pointer is over the form.
        def _on_wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind("<Enter>",
                     lambda _e: canvas.bind_all("<MouseWheel>", _on_wheel))
        canvas.bind("<Leave>",
                     lambda _e: canvas.unbind_all("<MouseWheel>"))

        r = 0

        def label(text: str):
            nonlocal r
            ttk.Label(form, text=text).grid(
                row=r, column=0, sticky="e", padx=(0, 6), pady=4)

        # ── Recipient picker (unified) ──────────────────────────────
        # Replaces the previous separate Student / Staff / Cross-
        # system dropdowns. Picking an entry auto-fills the To
        # name / To address / Student / Staff / parent-contact
        # fields below; the chip shows where the message will be
        # routed.
        label("To:")
        self._recip_dir = (_recipient_directory()
                            if not self.existing else [])
        recip_labels = (["(custom — fill the To fields below)"]
                         + [e["label"] for e in self._recip_dir])
        self.recip_cb = ttk.Combobox(
            form, values=recip_labels, state="readonly", width=58)
        self.recip_cb.current(0)
        self.recip_cb.grid(row=r, column=1, sticky="ew", pady=4)
        self.recip_cb.bind("<<ComboboxSelected>>",
                              self._on_recipient_change)
        if self.existing:
            self.recip_cb.configure(state="disabled")
        r += 1

        self.cs_chip = ttk.Label(
            form, text="", foreground="#2E86AB",
            font=("", 9, "italic"))
        self.cs_chip.grid(row=r, column=1, sticky="w", pady=(0, 6))
        r += 1

        # Auto-filled "To name / To address" — visible, editable.
        label("To name:")
        self.tn_e = ttk.Entry(form)
        if self.existing and self.existing.to_name:
            self.tn_e.insert(0, self.existing.to_name)
        elif self.reply_to and self.reply_to.from_name:
            self.tn_e.insert(0, self.reply_to.from_name)
        self.tn_e.grid(row=r, column=1, sticky="ew", pady=2)
        r += 1

        label("To address:")
        self.ta_e = ttk.Entry(form)
        if self.existing and self.existing.to_address:
            self.ta_e.insert(0, self.existing.to_address)
        elif self.reply_to and self.reply_to.from_address:
            self.ta_e.insert(0, self.reply_to.from_address)
        self.ta_e.grid(row=r, column=1, sticky="ew", pady=2)
        r += 1

        label("Subject:")
        self.subj_e = ttk.Entry(form)
        if self.existing:
            self.subj_e.insert(0, self.existing.subject)
        elif self.reply_to:
            s = self.reply_to.subject
            self.subj_e.insert(
                0, s if s.startswith("Re:") else f"Re: {s}")
        self.subj_e.grid(row=r, column=1, sticky="ew", pady=(8, 2))
        r += 1

        label("CC:")
        self.cc_e = ttk.Entry(form)
        if self.existing and self.existing.cc_address:
            self.cc_e.insert(0, self.existing.cc_address)
        self.cc_e.grid(row=r, column=1, sticky="ew", pady=2)
        r += 1

        label("Body:")
        self.body_text = tk.Text(form, height=12, wrap="word")
        if self.existing:
            self.body_text.insert("1.0", self.existing.body)
        self.body_text.grid(row=r, column=1, sticky="nsew",
                              pady=(8, 4))
        form.rowconfigure(r, weight=1)
        r += 1

        # ── Advanced section (collapsed by default) ─────────────────
        adv_toggle = ttk.Frame(form)
        adv_toggle.grid(row=r, column=0, columnspan=2,
                         sticky="ew", pady=(10, 0))
        r += 1

        self._adv_open = tk.BooleanVar(value=bool(self.existing))
        self._adv_btn = ttk.Button(
            adv_toggle, command=self._toggle_advanced)
        self._adv_btn.pack(side="left")

        adv = ttk.Frame(form)
        adv.columnconfigure(1, weight=1)
        adv.grid(row=r, column=0, columnspan=2, sticky="nsew")
        self._adv_frame = adv
        r += 1

        # Build all the advanced fields inside `adv` using a fresh
        # row counter so they stay self-contained.
        ar = 0

        def adv_label(text: str):
            nonlocal ar
            ttk.Label(adv, text=text).grid(
                row=ar, column=0, sticky="e", padx=(0, 6), pady=2)

        adv_label("Direction:")
        self.dir_cb = ttk.Combobox(adv, values=DIRECTIONS,
                                      state="readonly", width=14)
        if self.existing:
            self.dir_cb.set(self.existing.direction)
        elif self.reply_to:
            self.dir_cb.set("Incoming" if
                               self.reply_to.direction == "Outgoing"
                               else "Outgoing")
        else:
            self.dir_cb.set("Outgoing")
        self.dir_cb.grid(row=ar, column=1, sticky="w", pady=2)
        ar += 1

        adv_label("Channel:")
        self.chan_cb = ttk.Combobox(adv, values=CHANNELS,
                                       state="readonly", width=18)
        self.chan_cb.set(self._seed("channel") or DEFAULT_CHANNEL)
        self.chan_cb.grid(row=ar, column=1, sticky="w", pady=2)
        ar += 1

        adv_label("Category:")
        self.cat_cb = ttk.Combobox(adv, values=CATEGORIES,
                                      state="readonly", width=20)
        self.cat_cb.set(self._seed("category") or DEFAULT_CATEGORY)
        self.cat_cb.grid(row=ar, column=1, sticky="w", pady=2)
        ar += 1

        adv_label("Priority:")
        self.pri_cb = ttk.Combobox(adv, values=PRIORITIES,
                                      state="readonly", width=14)
        self.pri_cb.set(self._seed("priority") or DEFAULT_PRIORITY)
        self.pri_cb.grid(row=ar, column=1, sticky="w", pady=2)
        ar += 1

        adv_label("Status:")
        self.status_cb = ttk.Combobox(adv, values=STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_STATUS)
        self.status_cb.grid(row=ar, column=1, sticky="w", pady=2)
        ar += 1

        adv_label("From name:")
        self.fn_e = ttk.Entry(adv)
        if self.existing and self.existing.from_name:
            self.fn_e.insert(0, self.existing.from_name)
        elif self.reply_to and self.reply_to.to_name:
            self.fn_e.insert(0, self.reply_to.to_name)
        else:
            # Pre-fill from the signed-in user so casual senders
            # don't have to type their own name every time.
            cu = (self.auth.current_user
                  if self.auth and getattr(self.auth, "current_user", None)
                  else None) or {}
            self.fn_e.insert(0, cu.get("display_name")
                                  or cu.get("username") or "")
        self.fn_e.grid(row=ar, column=1, sticky="ew", pady=2)
        ar += 1

        adv_label("From address:")
        self.fa_e = ttk.Entry(adv)
        if self.existing and self.existing.from_address:
            self.fa_e.insert(0, self.existing.from_address)
        elif self.reply_to and self.reply_to.to_address:
            self.fa_e.insert(0, self.reply_to.to_address)
        else:
            # Pre-fill from the signed-in user — same data source as
            # the "From name" field a few lines above. Avoids the
            # validator rejecting Email-channel sends because no
            # from_address was set.
            cu = (self.auth.current_user
                  if self.auth and getattr(self.auth, "current_user", None)
                  else None) or {}
            self.fa_e.insert(0, cu.get("email") or "")
        self.fa_e.grid(row=ar, column=1, sticky="ew", pady=2)
        ar += 1

        adv_label("Student:")
        opts = _student_options()
        labels_s = ["(none)"] + [l for _, l in opts]
        ids_s = [None] + [s for s, _ in opts]
        self._student_ids = ids_s
        self.student_cb = ttk.Combobox(adv, values=labels_s,
                                           state="readonly", width=44)
        seed = (self.existing.student_id if self.existing
                else self.reply_to.student_id if self.reply_to else None)
        if seed in ids_s:
            self.student_cb.current(ids_s.index(seed))
        else:
            self.student_cb.current(0)
        self.student_cb.grid(row=ar, column=1, sticky="w", pady=2)
        ar += 1

        adv_label("Staff:")
        opts_t = _staff_options(active_only=False)
        labels_t = ["(none)"] + [l for _, l in opts_t]
        ids_t = [None] + [s for s, _ in opts_t]
        self._staff_ids = ids_t
        self.staff_cb = ttk.Combobox(adv, values=labels_t,
                                         state="readonly", width=44)
        seed_t = (self.existing.staff_id if self.existing
                   else self.reply_to.staff_id if self.reply_to else None)
        if seed_t in ids_t:
            self.staff_cb.current(ids_t.index(seed_t))
        else:
            self.staff_cb.current(0)
        self.staff_cb.grid(row=ar, column=1, sticky="w", pady=2)
        ar += 1

        # parent_contact_id isn't a dropdown — auto-filled when the
        # picker selects a parent, otherwise left None.
        self._parent_contact_id: int | None = (
            self.existing.parent_contact_id if self.existing else None)

        adv_label("Sent at:")
        self.sent_e = ttk.Entry(adv, width=22)
        if self.existing and self.existing.sent_at:
            self.sent_e.insert(0, self.existing.sent_at)
        self.sent_e.grid(row=ar, column=1, sticky="w", pady=2)
        ar += 1

        adv_label("Received at:")
        self.recv_e = ttk.Entry(adv, width=22)
        if self.existing and self.existing.received_at:
            self.recv_e.insert(0, self.existing.received_at)
        self.recv_e.grid(row=ar, column=1, sticky="w", pady=2)
        ar += 1

        adv_label("Attachments note:")
        self.att_e = ttk.Entry(adv)
        if self.existing and self.existing.attachments_note:
            self.att_e.insert(0, self.existing.attachments_note)
        self.att_e.grid(row=ar, column=1, sticky="ew", pady=2)
        ar += 1

        adv_label("Tags:")
        self.tags_e = ttk.Entry(adv)
        if self.existing and self.existing.tags:
            self.tags_e.insert(0, self.existing.tags)
        self.tags_e.grid(row=ar, column=1, sticky="ew", pady=2)
        ar += 1

        adv_label("Notes:")
        self.notes_text = tk.Text(adv, height=4, wrap="word")
        if self.existing and self.existing.notes:
            self.notes_text.insert("1.0", self.existing.notes)
        self.notes_text.grid(row=ar, column=1, sticky="ew", pady=2)
        ar += 1

        # Apply the initial collapsed/expanded state.
        self._apply_advanced_visibility()

    def _toggle_advanced(self) -> None:
        self._adv_open.set(not self._adv_open.get())
        self._apply_advanced_visibility()

    def _apply_advanced_visibility(self) -> None:
        if self._adv_open.get():
            self._adv_btn.configure(text="▾ Hide advanced options")
            self._adv_frame.grid()
        else:
            self._adv_btn.configure(text="▸ Show advanced options")
            self._adv_frame.grid_remove()

    def _payload(self) -> dict:
        idx_s = self.student_cb.current()
        idx_t = self.staff_cb.current()
        return {
            "direction":    self.dir_cb.get(),
            "channel":      self.chan_cb.get(),
            "category":     self.cat_cb.get(),
            "priority":     self.pri_cb.get(),
            "status":       self.status_cb.get(),
            "subject":      self.subj_e.get().strip(),
            "body":         self.body_text.get("1.0", "end").strip(),
            "from_name":    self.fn_e.get().strip(),
            "from_address": self.fa_e.get().strip(),
            "to_name":      self.tn_e.get().strip(),
            "to_address":   self.ta_e.get().strip(),
            "cc_address":   self.cc_e.get().strip(),
            "student_id":   self._student_ids[idx_s] if idx_s > 0 else "",
            "staff_id":     self._staff_ids[idx_t] if idx_t > 0 else "",
            "parent_contact_id": self._parent_contact_id,
            "sent_at":      self.sent_e.get().strip(),
            "received_at":  self.recv_e.get().strip(),
            "attachments_note": self.att_e.get().strip(),
            "tags":         self.tags_e.get().strip(),
            "notes":        self.notes_text.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        payload = self._payload()
        try:
            if self.existing:
                data.update_message(self.existing.message_id, payload)
            elif self.reply_to:
                data.reply(self.reply_to.message_id, payload)
            else:
                data.create_message(payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save message failed")
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()

    def _selected_recipient(self) -> dict | None:
        """Return the currently chosen directory entry, or ``None``
        if the picker is on the ``(custom)`` row."""
        if not hasattr(self, "recip_cb"):
            return None
        idx = self.recip_cb.current()
        if idx <= 0 or idx - 1 >= len(self._recip_dir):
            return None
        return self._recip_dir[idx - 1]

    def _on_recipient_change(self, _event=None) -> None:
        """Auto-fill the To name / To address / Student / Staff /
        parent-contact fields when a directory entry is chosen, and
        update the routing chip."""
        target = self._selected_recipient()
        if target is None:
            self.cs_chip.config(text="")
            self._parent_contact_id = None
            return

        # Routing chip.
        if target["kind"] == "cross":
            self.cs_chip.config(
                text=f"[Cross-system] → "
                     f"{CROSS_SYSTEM_NAMES.get(target['system_key'], target['system_key'])}"
                     f"   ·   {target['to_name']}",
                foreground="#2E86AB",
            )
        elif target["kind"] == "student":
            self.cs_chip.config(text="[Local] Student message",
                                 foreground="#0d6b2a")
        elif target["kind"] == "staff":
            self.cs_chip.config(text="[Local] Staff message",
                                 foreground="#0d6b2a")
        elif target["kind"] == "parent":
            self.cs_chip.config(text="[Local] Parent contact",
                                 foreground="#0d6b2a")
        else:
            self.cs_chip.config(text="")

        # Overwrite the To fields with the directory values — most
        # users want the auto-fill, and if they don't they can edit
        # afterwards.
        self.tn_e.delete(0, "end")
        self.tn_e.insert(0, target["to_name"])
        self.ta_e.delete(0, "end")
        self.ta_e.insert(0, target["to_address"])

        # Link the student/staff dropdowns + parent_contact_id so
        # the row is properly cross-referenced when stored.
        sid = target.get("student_id") or None
        if sid in self._student_ids:
            self.student_cb.current(self._student_ids.index(sid))
        else:
            self.student_cb.current(0)
        tid = target.get("staff_id") or None
        if tid in self._staff_ids:
            self.staff_cb.current(self._staff_ids.index(tid))
        else:
            self.staff_cb.current(0)
        self._parent_contact_id = target.get("parent_contact_id")

    def _save_and_send(self) -> None:
        target = self._selected_recipient()
        if target is not None and target["kind"] == "cross":
            # Adapt the unified entry to the cross-system call shape.
            self._save_and_send_cross({
                "id":           target["id"],
                "system_key":   target["system_key"],
                "display_name": target["to_name"],
            })
            return

        payload = self._payload()
        # Stamp both status AND sent_at in the same row so we don't
        # try to "send" an already-Sent row a moment later (which
        # ``data.send_message`` rejects with "already Sent").
        payload["status"] = "Sent"
        if not payload.get("sent_at"):
            payload["sent_at"] = data._now()
        try:
            if self.reply_to:
                data.reply(self.reply_to.message_id, payload)
            else:
                data.create_message(payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save+send failed")
            messagebox.showerror("Send failed", str(e))
            return
        self.win.destroy()
        self.on_save()

    def _save_and_send_cross(self, target: dict) -> None:
        """Send a message to another system's staff member via the
        shared ``InterSystemMessagingService`` AND record a local copy
        in the Sent folder so the user has a single audit trail."""
        cu = (self.auth.current_user
              if self.auth is not None and getattr(self.auth, "current_user", None)
              else None)
        if not cu:
            messagebox.showerror(
                "Send failed",
                "No active session — cross-system messaging requires "
                "an authenticated user.")
            return
        sender_id = (cu.get("shared_auth_id")
                     or cu.get("user_id") or cu.get("id"))
        sender_name = cu.get("display_name") or cu.get("username") or ""
        subject = self.subj_e.get().strip()
        if not subject:
            messagebox.showwarning("Validation",
                                   "Subject is required.", parent=self.win)
            return
        body = self.body_text.get("1.0", "end").strip()
        if not body:
            messagebox.showwarning("Validation",
                                   "Message body is empty.", parent=self.win)
            return

        # Local copy in Sent — tagged so it's easy to find later.
        payload = self._payload()
        payload["status"] = "Sent"
        payload["channel"] = "Email"
        payload["to_name"] = target["display_name"]
        existing_tags = payload.get("tags", "") or ""
        payload["tags"] = (existing_tags + " cross-system").strip()
        cs_note = (f"Cross-system → "
                   f"{CROSS_SYSTEM_NAMES.get(target['system_key'], target['system_key'])} "
                   f"({target['display_name']})")
        existing_notes = payload.get("notes", "") or ""
        payload["notes"] = (
            (existing_notes + "\n" + cs_note).strip()
            if existing_notes else cs_note)

        # Stamp sent_at on the local row up-front so we don't have to
        # follow up with a separate ``send_message`` call (which would
        # then refuse because the row is already at status=Sent).
        if not payload.get("sent_at"):
            payload["sent_at"] = data._now()
        try:
            data.create_message(payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e), parent=self.win)
            return
        except Exception as e:
            logger.exception("local copy of cross-system message failed")
            messagebox.showerror("Send failed", str(e), parent=self.win)
            return

        try:
            from education_system.shared.messaging.messaging_service import (
                InterSystemMessagingService,
            )
            svc = InterSystemMessagingService()
            svc.send_message(
                sender_id=sender_id,
                sender_system=OWN_SYSTEM_KEY,
                sender_name=sender_name,
                recipient_id=target["id"],
                recipient_system=target["system_key"],
                recipient_name=target["display_name"],
                student_name="",
                student_id=payload.get("student_id") or "",
                subject=subject,
                body=body,
            )
        except Exception as e:
            logger.exception("cross-system delivery failed")
            messagebox.showerror(
                "Cross-system send failed",
                f"The message was saved to your Sent folder but "
                f"delivery to the other system failed:\n\n{e}",
                parent=self.win,
            )
            return

        logger.info(
            "Cross-system message sent: sixth-form → %s (recipient #%s)",
            target["system_key"], target.get("id"))
        self.win.destroy()
        self.on_save()


# ══ Threads tab ════════════════════════════════════════════════════

class ThreadsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Threads")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Staff:").pack(side="left")
        self.f_staff = ttk.Entry(bar, width=12)
        self.f_staff.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        paned = ttk.Panedwindow(self.frame, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=4)

        left = ttk.Frame(paned)
        cols = ("thread", "msgs", "last", "status", "subject")
        self.tree = ttk.Treeview(left, columns=cols, show="headings")
        widths = {"thread": 110, "msgs": 50, "last": 140,
                  "status": 90, "subject": 240}
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(left, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>",
                          lambda _e: self._show_thread())
        paned.add(left, weight=1)

        right = ttk.Frame(paned)
        self.detail = tk.Text(right, wrap="word", state="disabled")
        ds = ttk.Scrollbar(right, orient="vertical",
                            command=self.detail.yview)
        self.detail.configure(yscrollcommand=ds.set)
        self.detail.pack(side="left", fill="both", expand=True)
        ds.pack(side="right", fill="y")
        paned.add(right, weight=2)

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_staff.delete(0, "end")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = data.list_threads(
            student_id=self.f_student.get().strip() or None,
            staff_id=self.f_staff.get().strip() or None)
        for t in rows:
            self.tree.insert("", "end", iid=t.thread_id, values=(
                t.thread_id, t.message_count, (t.last_at or "")[:19],
                t.last_status, t.subject,
            ))
        self.count_var.set(f"{len(rows)} thread(s).")

    def _show_thread(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        tid = sel[0]
        rows = data.thread(tid)
        names = _student_names()
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("end", f"Thread {tid}\n\n")
        for m in rows:
            arrow = "▶" if m.direction == "Outgoing" else "◀"
            when = m.sent_at or m.received_at or m.created_at
            who = (f"From {m.from_name or '—'}  →  "
                   f"To {m.to_name or '—'}")
            student = (f"  [student {m.student_id} — "
                       f"{names.get(m.student_id, '?')}]"
                       if m.student_id else "")
            self.detail.insert(
                "end",
                f"{arrow}  #{m.message_id}  {when[:19] if when else ''}  "
                f"[{m.status}]  {m.subject}\n"
                f"   {who}{student}\n"
                f"   {m.body}\n\n"
                f"   {'─' * 78}\n\n")
        self.detail.configure(state="disabled")


# ══ Bulk Send tab ══════════════════════════════════════════════════

class BulkTab:
    AUDIENCES = (
        "All Students", "All Parent Contacts",
        "Primary Parent Contacts", "All Active Staff",
    )

    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Bulk Send")
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.frame)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0
        ttk.Label(form, text="Recipient set:").grid(row=r, column=0,
                                                      sticky="e", pady=3)
        self.aud_cb = ttk.Combobox(form, values=self.AUDIENCES,
                                       state="readonly", width=32)
        self.aud_cb.current(0)
        self.aud_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Channel:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.chan_cb = ttk.Combobox(form, values=CHANNELS,
                                        state="readonly", width=18)
        self.chan_cb.set(DEFAULT_CHANNEL)
        self.chan_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Category:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.cat_cb = ttk.Combobox(form, values=CATEGORIES,
                                      state="readonly", width=22)
        self.cat_cb.set(DEFAULT_CATEGORY)
        self.cat_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Priority:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.pri_cb = ttk.Combobox(form, values=PRIORITIES,
                                      state="readonly", width=12)
        self.pri_cb.set(DEFAULT_PRIORITY)
        self.pri_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Sender (staff):").grid(row=r, column=0,
                                                       sticky="e", pady=3)
        opts = _staff_options(active_only=True)
        labels = ["(none)"] + [l for _, l in opts]
        ids = [None] + [s for s, _ in opts]
        self._sender_ids = ids
        self.sender_cb = ttk.Combobox(form, values=labels,
                                          state="readonly", width=40)
        self.sender_cb.current(0)
        self.sender_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Subject:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.subj_e = ttk.Entry(form, width=60)
        self.subj_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Body:").grid(row=r, column=0,
                                              sticky="ne", pady=3)
        self.body_text = tk.Text(form, width=70, height=10, wrap="word")
        self.body_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Tags:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.tags_e = ttk.Entry(form, width=60)
        self.tags_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        self.immediate_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="Mark as Sent immediately",
                          variable=self.immediate_var).grid(
            row=r, column=1, sticky="w", padx=6, pady=4)
        r += 1

        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Send",
                    command=self._send).pack(side="left")

    def _send(self) -> None:
        subject = self.subj_e.get().strip()
        body = self.body_text.get("1.0", "end").strip()
        if not subject or not body:
            messagebox.showerror("Bulk",
                                  "Subject and body are required.")
            return
        sel = self.aud_cb.get()
        student_ids: list[str] = []
        contact_ids: list[int] = []
        staff_ids: list[str] = []
        if sel == "All Students":
            student_ids = [s.student_id
                            for s in student_data.list_students()]
        elif sel == "All Parent Contacts":
            contact_ids = [c.contact_id for c in pc_data.list_contacts()]
        elif sel == "Primary Parent Contacts":
            contact_ids = [c.contact_id
                            for c in pc_data.list_contacts(
                                primary_only=True)]
        elif sel == "All Active Staff":
            staff_ids = [t.staff_id
                          for t in staff_data.list_staff(active_only=True)]
        if not (student_ids or contact_ids or staff_ids):
            messagebox.showinfo("Bulk", "No recipients in that set.")
            return
        if not messagebox.askyesno(
                "Bulk Send",
                f"Send to {len(student_ids) + len(contact_ids) + len(staff_ids)} "
                f"recipient(s)?"):
            return
        idx = self.sender_cb.current()
        sender = self._sender_ids[idx] if idx > 0 else None
        try:
            result = data.bulk_send(
                subject=subject, body=body,
                student_ids=student_ids, contact_ids=contact_ids,
                staff_ids=staff_ids,
                channel=self.chan_cb.get(),
                category=self.cat_cb.get(),
                priority=self.pri_cb.get(),
                status="Sent" if self.immediate_var.get() else "Draft",
                sender_staff_id=sender,
                tags=self.tags_e.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Bulk", str(e))
            return
        except Exception as e:
            logger.exception("bulk send failed")
            messagebox.showerror("Bulk", str(e))
            return
        msg = (f"Thread: {result.thread_id}\n"
               f"Created: {len(result.created)}\n"
               f"Failed:  {len(result.failed)}")
        if result.failed:
            msg += "\n\nFailures:\n" + "\n".join(
                f"  {label}: {reason}"
                for label, reason in result.failed[:20])
        messagebox.showinfo("Bulk Send", msg)


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10), state="disabled")
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def refresh(self) -> None:
        summ = data.summary()
        L: list[str] = []
        L.append("Counts")
        L.append("------")
        L.append(f"  Total       : {summ.total}")
        L.append(f"  Drafts      : {summ.drafts}")
        L.append(f"  Queued      : {summ.queued}")
        L.append(f"  Sent        : {summ.sent}")
        L.append(f"  Failed      : {summ.failed}")
        L.append(f"  Incoming    : {summ.incoming}")
        L.append(f"  Outgoing    : {summ.outgoing}")
        L.append(f"  Threads     : {summ.threads}")
        L.append("")
        L.append("By channel")
        L.append("----------")
        for c in CHANNELS:
            n = summ.by_channel.get(c, 0)
            if n:
                L.append(f"  {c:<18} : {n}")
        L.append("")
        L.append("By category")
        L.append("-----------")
        for c in CATEGORIES:
            n = summ.by_category.get(c, 0)
            if n:
                L.append(f"  {c:<22} : {n}")
        L.append("")
        L.append("By status")
        L.append("---------")
        for s in STATUSES:
            n = summ.by_status.get(s, 0)
            if n:
                L.append(f"  {s:<14} : {n}")
        L.append("")
        L.append("By priority")
        L.append("-----------")
        for p in PRIORITIES:
            L.append(f"  {p:<10} : {summ.by_priority.get(p, 0)}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(L))
        self.text.configure(state="disabled")
