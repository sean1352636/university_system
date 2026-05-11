"""Tkinter views for Sixth Form Email / Messaging."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.sixthform_system.modules.domain.messages import messages
from education_system.sixthform_system.modules.domain.parent_contacts import parent_contacts
from education_system.sixthform_system.modules.domain.staff import staff
from education_system.sixthform_system.modules.domain.students import students as data
from education_system.sixthform_system.modules.domain.parent_contacts import parent_contacts as pc_data
from education_system.sixthform_system.modules.domain.staff import staff as staff_data
from education_system.sixthform_system.modules.domain.students import students as student_data
from education_system.sixthform_system.modules.domain.messages.messages import (
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
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title("Email / Messaging — Sixth Form System")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    MailboxTab(nb)
    ThreadsTab(nb)
    BulkTab(nb)
    SummaryTab(nb)


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

    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
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
        ttk.Button(bar, text="Send",
                    command=self._send_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Reply",
                    command=self._reply_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Status",
                    command=self._status_selected).pack(side="left", padx=4)
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
        self.count_var.set(f"{len(rows)} message(s).")
        self._build_actions()

    def _selected(self) -> Message | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return data.get_message(int(sel[0]))

    def _view_selected(self) -> None:
        m = self._selected()
        if m is None:
            messagebox.showinfo("View", "Select a message first.")
            return
        ViewDialog(self.frame.winfo_toplevel(), m)

    def _new(self) -> None:
        MessageDialog(self.frame.winfo_toplevel(), existing=None,
                        on_save=self.refresh)

    def _edit_selected(self) -> None:
        m = self._selected()
        if m is None:
            messagebox.showinfo("Edit", "Select a message first.")
            return
        MessageDialog(self.frame.winfo_toplevel(), existing=m,
                        on_save=self.refresh)

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
        m = self._selected()
        if m is None:
            messagebox.showinfo("Reply", "Select a message first.")
            return
        MessageDialog(self.frame.winfo_toplevel(),
                        existing=None, reply_to=m,
                        on_save=self.refresh)

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
        self.win.grab_set()
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
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.reply_to = reply_to
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        title = ("Edit Message" if existing
                  else f"Reply to #{reply_to.message_id}" if reply_to
                  else "New Message")
        self.win.title(title)
        self.win.transient(parent)
        self.win.grab_set()
        self._build()

    def _seed(self, field: str, fallback: str = "") -> str:
        if self.existing:
            return getattr(self.existing, field) or fallback
        if self.reply_to:
            return getattr(self.reply_to, field) or fallback
        return fallback

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0

        def label(text: str):
            nonlocal r
            ttk.Label(form, text=text).grid(row=r, column=0,
                                              sticky="e", pady=3)

        label("Direction:")
        self.dir_cb = ttk.Combobox(form, values=DIRECTIONS,
                                      state="readonly", width=12)
        if self.existing:
            self.dir_cb.set(self.existing.direction)
        elif self.reply_to:
            self.dir_cb.set("Incoming" if
                               self.reply_to.direction == "Outgoing"
                               else "Outgoing")
        else:
            self.dir_cb.set("Outgoing")
        self.dir_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Channel:")
        self.chan_cb = ttk.Combobox(form, values=CHANNELS,
                                       state="readonly", width=18)
        self.chan_cb.set(self._seed("channel") or DEFAULT_CHANNEL)
        self.chan_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Category:")
        self.cat_cb = ttk.Combobox(form, values=CATEGORIES,
                                      state="readonly", width=18)
        self.cat_cb.set(self._seed("category") or DEFAULT_CATEGORY)
        self.cat_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Priority:")
        self.pri_cb = ttk.Combobox(form, values=PRIORITIES,
                                      state="readonly", width=12)
        self.pri_cb.set(self._seed("priority") or DEFAULT_PRIORITY)
        self.pri_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Status:")
        self.status_cb = ttk.Combobox(form, values=STATUSES,
                                          state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Subject:")
        self.subj_e = ttk.Entry(form, width=60)
        if self.existing:
            self.subj_e.insert(0, self.existing.subject)
        elif self.reply_to:
            s = self.reply_to.subject
            self.subj_e.insert(0,
                                 s if s.startswith("Re:") else f"Re: {s}")
        self.subj_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("From name:")
        self.fn_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.from_name:
            self.fn_e.insert(0, self.existing.from_name)
        elif self.reply_to and self.reply_to.to_name:
            self.fn_e.insert(0, self.reply_to.to_name)
        self.fn_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("From address:")
        self.fa_e = ttk.Entry(form, width=40)
        if self.existing and self.existing.from_address:
            self.fa_e.insert(0, self.existing.from_address)
        elif self.reply_to and self.reply_to.to_address:
            self.fa_e.insert(0, self.reply_to.to_address)
        self.fa_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("To name:")
        self.tn_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.to_name:
            self.tn_e.insert(0, self.existing.to_name)
        elif self.reply_to and self.reply_to.from_name:
            self.tn_e.insert(0, self.reply_to.from_name)
        self.tn_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("To address:")
        self.ta_e = ttk.Entry(form, width=40)
        if self.existing and self.existing.to_address:
            self.ta_e.insert(0, self.existing.to_address)
        elif self.reply_to and self.reply_to.from_address:
            self.ta_e.insert(0, self.reply_to.from_address)
        self.ta_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("CC:")
        self.cc_e = ttk.Entry(form, width=40)
        if self.existing and self.existing.cc_address:
            self.cc_e.insert(0, self.existing.cc_address)
        self.cc_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Student:")
        opts = _student_options()
        labels_s = ["(none)"] + [l for _, l in opts]
        ids_s = [None] + [s for s, _ in opts]
        self._student_ids = ids_s
        self.student_cb = ttk.Combobox(form, values=labels_s,
                                          state="readonly", width=40)
        seed = (self.existing.student_id if self.existing
                else self.reply_to.student_id if self.reply_to else None)
        if seed in ids_s:
            self.student_cb.current(ids_s.index(seed))
        else:
            self.student_cb.current(0)
        self.student_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Staff:")
        opts_t = _staff_options(active_only=False)
        labels_t = ["(none)"] + [l for _, l in opts_t]
        ids_t = [None] + [s for s, _ in opts_t]
        self._staff_ids = ids_t
        self.staff_cb = ttk.Combobox(form, values=labels_t,
                                        state="readonly", width=42)
        seed_t = (self.existing.staff_id if self.existing
                   else self.reply_to.staff_id if self.reply_to else None)
        if seed_t in ids_t:
            self.staff_cb.current(ids_t.index(seed_t))
        else:
            self.staff_cb.current(0)
        self.staff_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Body:")
        self.body_text = tk.Text(form, width=70, height=10, wrap="word")
        if self.existing:
            self.body_text.insert("1.0", self.existing.body)
        self.body_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Sent at:")
        self.sent_e = ttk.Entry(form, width=20)
        if self.existing and self.existing.sent_at:
            self.sent_e.insert(0, self.existing.sent_at)
        self.sent_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Received at:")
        self.recv_e = ttk.Entry(form, width=20)
        if self.existing and self.existing.received_at:
            self.recv_e.insert(0, self.existing.received_at)
        self.recv_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Attachments note:")
        self.att_e = ttk.Entry(form, width=60)
        if self.existing and self.existing.attachments_note:
            self.att_e.insert(0, self.existing.attachments_note)
        self.att_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Tags:")
        self.tags_e = ttk.Entry(form, width=60)
        if self.existing and self.existing.tags:
            self.tags_e.insert(0, self.existing.tags)
        self.tags_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        label("Notes:")
        self.notes_text = tk.Text(form, width=70, height=3, wrap="word")
        if self.existing and self.existing.notes:
            self.notes_text.insert("1.0", self.existing.notes)
        self.notes_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        if not self.existing:
            ttk.Button(bar, text="Save & Send",
                        command=self._save_and_send).pack(side="left", padx=8)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

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

    def _save_and_send(self) -> None:
        payload = self._payload()
        payload["status"] = "Sent"
        try:
            if self.reply_to:
                m = data.reply(self.reply_to.message_id, payload)
            else:
                m = data.create_message(payload)
            if not m.sent_at:
                data.send_message(m.message_id)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save+send failed")
            messagebox.showerror("Send failed", str(e))
            return
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
