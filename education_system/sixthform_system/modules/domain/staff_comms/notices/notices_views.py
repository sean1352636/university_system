"""Tkinter views for Sixth Form Notices & Bulletins."""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Callable
from education_system.sixthform_system.modules.domain.staff_comms.notices import notices
from education_system.sixthform_system.modules.domain.staff_comms.notices import notices as data
from education_system.sixthform_system.modules.domain.staff_comms.staff import staff as staff_data
from education_system.shared import branding
from education_system.sixthform_system.modules.domain.staff_comms.notices.notices import (
    AUDIENCES,
    CATEGORIES,
    DEFAULT_AUDIENCE,
    DEFAULT_CATEGORY,
    DEFAULT_PRIORITY,
    DEFAULT_STATUS,
    Notice,
    PRIORITIES,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_notices_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Notices & Bulletins — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    BoardTab(nb)
    AllNoticesTab(nb)
    FeedTab(nb)
    SummaryTab(nb)


def _author_names() -> dict[str, str]:
    return {t.staff_id: t.full_name for t in staff_data.list_staff()}


def _staff_options(active_only: bool = True) -> list[tuple[str, str]]:
    rows = sorted(
        staff_data.list_staff(active_only=active_only),
        key=lambda s: (s.last_name, s.first_name))
    return [(t.staff_id,
              f"{t.staff_id} — {t.full_name} ({t.role})")
            for t in rows]


# ══ Board tab (today's visible notices) ═══════════════════════════

class BoardTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Board")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Showing notices visible today.").pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="right", padx=(4, 0))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")
        ttk.Button(bar, text="Auto-Archive Expired",
                    command=self._auto_archive).pack(side="right", padx=4)

        canvas = tk.Canvas(self.frame, borderwidth=0,
                              highlightthickness=0)
        scroll = ttk.Scrollbar(self.frame, orient="vertical",
                                  command=canvas.yview)
        self.inner = ttk.Frame(canvas)
        self.inner.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True, padx=8, pady=4)
        scroll.pack(side="right", fill="y")

        self.status_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.status_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        for w in self.inner.winfo_children():
            w.destroy()
        rows = data.list_notices(active_on=_date.today().isoformat())
        authors = _author_names()
        if not rows:
            ttk.Label(self.inner, text="No notices visible today.",
                       foreground="#666").pack(anchor="w", padx=6, pady=20)
        for n in rows:
            self._render_card(n, authors)
        self.status_var.set(f"{len(rows)} notice(s) visible today.")

    def _render_card(self, n: Notice, authors: dict[str, str]) -> None:
        bg = {
            "Urgent": "#ffd0d0",
            "High":   "#ffe6d0",
            "Normal": "#f7f7f7",
            "Low":    "#f0f0f0",
        }.get(n.priority, "#f7f7f7")
        card = tk.Frame(self.inner, bg=bg, bd=1, relief="solid")
        card.pack(fill="x", padx=4, pady=4)
        head = tk.Frame(card, bg=bg)
        head.pack(fill="x", padx=8, pady=(8, 0))
        pinned = "★ " if n.pinned else ""
        tk.Label(head, text=f"{pinned}{n.title}", bg=bg,
                  font=("", 12, "bold"), anchor="w").pack(side="left")
        tk.Label(head, text=f"#{n.notice_id}",
                  bg=bg, fg="#666").pack(side="right")
        meta = tk.Frame(card, bg=bg)
        meta.pack(fill="x", padx=8, pady=(0, 4))
        author = (authors.get(n.author_staff_id, n.author_staff_id)
                   if n.author_staff_id else "—")
        info = (f"{n.priority}  •  {n.category}  •  {n.audience}  •  "
                f"{n.publish_from or '—'}"
                + (f" → {n.publish_until}" if n.publish_until else "")
                + f"  •  by {author}  •  {n.view_count} views")
        tk.Label(meta, text=info, bg=bg, fg="#444",
                  font=("", 9), anchor="w").pack(side="left")

        body = tk.Label(card, text=n.body, bg="white",
                          wraplength=1100, justify="left", anchor="w")
        body.pack(fill="x", padx=8, pady=(2, 6))

        if n.attachments_note:
            tk.Label(card, text=f"📎 {n.attachments_note}", bg=bg,
                      fg="#225", font=("", 9, "italic"),
                      anchor="w").pack(fill="x", padx=8, pady=(0, 4))

        actions = tk.Frame(card, bg=bg)
        actions.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(actions, text="View",
                    command=lambda: self._view(n.notice_id)).pack(side="left")
        ttk.Button(actions, text="Edit",
                    command=lambda: self._edit(n.notice_id)
                    ).pack(side="left", padx=4)
        ttk.Button(actions,
                    text="Unpin" if n.pinned else "Pin",
                    command=lambda: self._toggle_pin(n.notice_id)
                    ).pack(side="left", padx=4)
        ttk.Button(actions, text="Archive",
                    command=lambda: self._archive(n.notice_id)
                    ).pack(side="left", padx=4)

    def _view(self, nid: int) -> None:
        data.increment_view(nid)
        n = data.get_notice(nid)
        if n is None:
            return
        authors = _author_names()
        author = (authors.get(n.author_staff_id, n.author_staff_id)
                   if n.author_staff_id else "—")
        lines = [
            f"Notice    : #{n.notice_id}",
            f"Title     : {n.title}",
            f"Status    : {n.status}"
            + ("  (★ pinned)" if n.pinned else ""),
            f"Category  : {n.category}",
            f"Audience  : {n.audience}",
            f"Priority  : {n.priority}",
            f"Author    : {author}",
            f"From / To : "
            f"{n.publish_from or '—'}  /  {n.publish_until or '—'}",
            f"Visible   : "
            f"{'Yes' if n.is_visible_today else 'No'}",
            f"Views     : {n.view_count}",
        ]
        if n.attachments_note:
            lines.append(f"Attached  : {n.attachments_note}")
        lines.extend(["", "Body:", n.body])
        messagebox.showinfo(f"Notice #{n.notice_id}", "\n".join(lines))

    def _edit(self, nid: int) -> None:
        n = data.get_notice(nid)
        if n is None:
            return
        NoticeDialog(self.frame.winfo_toplevel(), existing=n,
                      on_save=self.refresh)

    def _new(self) -> None:
        NoticeDialog(self.frame.winfo_toplevel(), existing=None,
                      on_save=self.refresh)

    def _toggle_pin(self, nid: int) -> None:
        n = data.get_notice(nid)
        if n is None:
            return
        try:
            data.set_pinned(nid, not n.pinned)
        except Exception as e:
            messagebox.showerror("Failed", str(e))
            return
        self.refresh()

    def _archive(self, nid: int) -> None:
        if not messagebox.askyesno("Archive",
                                     f"Archive notice #{nid}?"):
            return
        try:
            data.archive(nid)
        except Exception as e:
            messagebox.showerror("Failed", str(e))
            return
        self.refresh()

    def _auto_archive(self) -> None:
        if not messagebox.askyesno(
                "Auto-Archive",
                "Move all expired Published notices to Archived?"):
            return
        n = data.auto_archive_expired()
        messagebox.showinfo("Done", f"Archived {n} notice(s).")
        self.refresh()


# ══ All Notices tab ═══════════════════════════════════════════════

class AllNoticesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="All Notices")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Search:").pack(side="left")
        self.q_e = ttk.Entry(bar, width=24)
        self.q_e.pack(side="left", padx=(2, 10))
        self.q_e.bind("<Return>", lambda _e: self.refresh())
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                        state="readonly", width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Category:").pack(side="left")
        self.f_cat = ttk.Combobox(bar, values=("",) + CATEGORIES,
                                     state="readonly", width=18)
        self.f_cat.current(0)
        self.f_cat.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Audience:").pack(side="left")
        self.f_aud = ttk.Combobox(bar, values=("",) + AUDIENCES,
                                     state="readonly", width=20)
        self.f_aud.current(0)
        self.f_aud.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Priority:").pack(side="left")
        self.f_pri = ttk.Combobox(bar, values=("",) + PRIORITIES,
                                     state="readonly", width=10)
        self.f_pri.current(0)
        self.f_pri.pack(side="left", padx=(2, 10))
        self.f_pin = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Pinned only",
                          variable=self.f_pin,
                          command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(10, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "pin", "status", "pri", "cat", "aud",
                "from", "until", "views", "title")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 60, "pin": 30, "status": 80, "pri": 70,
                  "cat": 130, "aud": 160, "from": 100, "until": 100,
                  "views": 60, "title": 400}
        headings = {"id": "#", "pin": "★", "status": "Status",
                    "pri": "Priority", "cat": "Category",
                    "aud": "Audience", "from": "From", "until": "Until",
                    "views": "Views", "title": "Title"}
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
        self.tree.tag_configure("Archived", foreground="#888")
        self.tree.tag_configure("Draft", foreground="#666",
                                  background="#f0f0f0")
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
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(bar, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Publish",
                    command=self._publish_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Archive",
                    command=self._archive_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Toggle Pin",
                    command=self._pin_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.q_e.delete(0, "end")
        self.f_status.current(0)
        self.f_cat.current(0)
        self.f_aud.current(0)
        self.f_pri.current(0)
        self.f_pin.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        q = self.q_e.get().strip()
        try:
            if q:
                rows = data.search_notices(q)
            else:
                rows = data.list_notices(
                    status=self.f_status.get() or None,
                    category=self.f_cat.get() or None,
                    audience=self.f_aud.get() or None,
                    priority=self.f_pri.get() or None,
                    pinned_only=self.f_pin.get(),
                )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for n in rows:
            tags = []
            if n.priority in ("Urgent", "High"):
                tags.append(n.priority)
            if n.status in ("Archived", "Draft"):
                tags.append(n.status)
            self.tree.insert("", "end", iid=str(n.notice_id), values=(
                n.notice_id, "★" if n.pinned else "",
                n.status, n.priority, n.category, n.audience,
                n.publish_from or "—", n.publish_until or "—",
                n.view_count, n.title,
            ), tags=tuple(tags))
        self.count_var.set(f"{len(rows)} notice(s).")
        self._build_actions()

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _view_selected(self) -> None:
        nid = self._selected_id()
        if nid is None:
            messagebox.showinfo("View", "Select a notice first.")
            return
        data.increment_view(nid)
        n = data.get_notice(nid)
        if n is None:
            return
        authors = _author_names()
        author = (authors.get(n.author_staff_id, n.author_staff_id)
                   if n.author_staff_id else "—")
        lines = [
            f"Notice    : #{n.notice_id}",
            f"Title     : {n.title}",
            f"Status    : {n.status}"
            + ("  (★ pinned)" if n.pinned else ""),
            f"Category  : {n.category}",
            f"Audience  : {n.audience}",
            f"Priority  : {n.priority}",
            f"Author    : {author}",
            f"From / To : "
            f"{n.publish_from or '—'}  /  {n.publish_until or '—'}",
            f"Visible   : {'Yes' if n.is_visible_today else 'No'}",
            f"Views     : {n.view_count}",
        ]
        if n.attachments_note:
            lines.append(f"Attached  : {n.attachments_note}")
        lines.extend(["", "Body:", n.body])
        messagebox.showinfo(f"Notice #{n.notice_id}", "\n".join(lines))

    def _new(self) -> None:
        NoticeDialog(self.frame.winfo_toplevel(), existing=None,
                      on_save=self.refresh)

    def _edit_selected(self) -> None:
        nid = self._selected_id()
        if nid is None:
            messagebox.showinfo("Edit", "Select a notice first.")
            return
        n = data.get_notice(nid)
        if n is None:
            return
        NoticeDialog(self.frame.winfo_toplevel(), existing=n,
                      on_save=self.refresh)

    def _publish_selected(self) -> None:
        nid = self._selected_id()
        if nid is None:
            messagebox.showinfo("Publish", "Select a notice first.")
            return
        try:
            data.publish(nid)
        except Exception as e:
            messagebox.showerror("Failed", str(e))
            return
        self.refresh()

    def _archive_selected(self) -> None:
        nid = self._selected_id()
        if nid is None:
            messagebox.showinfo("Archive", "Select a notice first.")
            return
        if not messagebox.askyesno("Archive",
                                     f"Archive notice #{nid}?"):
            return
        try:
            data.archive(nid)
        except Exception as e:
            messagebox.showerror("Failed", str(e))
            return
        self.refresh()

    def _pin_selected(self) -> None:
        nid = self._selected_id()
        if nid is None:
            messagebox.showinfo("Pin", "Select a notice first.")
            return
        n = data.get_notice(nid)
        if n is None:
            return
        try:
            data.set_pinned(nid, not n.pinned)
        except Exception as e:
            messagebox.showerror("Failed", str(e))
            return
        self.refresh()

    def _delete_selected(self) -> None:
        nid = self._selected_id()
        if nid is None:
            messagebox.showinfo("Delete", "Select a notice first.")
            return
        n = data.get_notice(nid)
        if n is None:
            return
        if not messagebox.askyesno(
                "Delete", f"Delete notice #{nid} ({n.title!r})?"):
            return
        try:
            data.delete_notice(nid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


class NoticeDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Notice | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Notice" if existing else "New Notice")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0

        ttk.Label(form, text="Title:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.title_e = ttk.Entry(form, width=60)
        if self.existing:
            self.title_e.insert(0, self.existing.title)
        self.title_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Body:").grid(row=r, column=0,
                                              sticky="ne", pady=3)
        self.body_text = tk.Text(form, width=70, height=10, wrap="word")
        if self.existing:
            self.body_text.insert("1.0", self.existing.body)
        self.body_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Category:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.cat_cb = ttk.Combobox(form, values=CATEGORIES,
                                      state="readonly", width=22)
        self.cat_cb.set(self.existing.category if self.existing
                          else DEFAULT_CATEGORY)
        self.cat_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Audience:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.aud_cb = ttk.Combobox(form, values=AUDIENCES,
                                      state="readonly", width=24)
        self.aud_cb.set(self.existing.audience if self.existing
                          else DEFAULT_AUDIENCE)
        self.aud_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Priority:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.pri_cb = ttk.Combobox(form, values=PRIORITIES,
                                      state="readonly", width=12)
        self.pri_cb.set(self.existing.priority if self.existing
                          else DEFAULT_PRIORITY)
        self.pri_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.status_cb = ttk.Combobox(form, values=STATUSES,
                                          state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Author:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        opts = _staff_options(active_only=False)
        labels = ["(none)"] + [l for _, l in opts]
        ids = [None] + [s for s, _ in opts]
        self._author_ids = ids
        self.author_cb = ttk.Combobox(form, values=labels,
                                          state="readonly", width=42)
        if self.existing and self.existing.author_staff_id in ids:
            self.author_cb.current(ids.index(self.existing.author_staff_id))
        else:
            self.author_cb.current(0)
        self.author_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Publish from:").grid(row=r, column=0,
                                                      sticky="e", pady=3)
        self.from_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.publish_from:
            self.from_e.insert(0, self.existing.publish_from)
        elif not self.existing:
            self.from_e.insert(0, _date.today().isoformat())
        self.from_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Publish until:").grid(row=r, column=0,
                                                       sticky="e", pady=3)
        self.until_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.publish_until:
            self.until_e.insert(0, self.existing.publish_until)
        self.until_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Flags:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.pin_var = tk.BooleanVar(
            value=self.existing.pinned if self.existing else False)
        ttk.Checkbutton(form, text="Pinned (★)",
                          variable=self.pin_var).grid(row=r, column=1,
                                                         sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Attachments note:").grid(row=r, column=0,
                                                          sticky="e", pady=3)
        self.att_e = ttk.Entry(form, width=60)
        if self.existing and self.existing.attachments_note:
            self.att_e.insert(0, self.existing.attachments_note)
        self.att_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        idx = self.author_cb.current()
        author_id = self._author_ids[idx] if idx >= 0 else None
        payload = {
            "title":            self.title_e.get().strip(),
            "body":             self.body_text.get("1.0", "end").strip(),
            "category":         self.cat_cb.get(),
            "audience":         self.aud_cb.get(),
            "priority":         self.pri_cb.get(),
            "status":           self.status_cb.get(),
            "author_staff_id":  author_id or "",
            "publish_from":     self.from_e.get().strip(),
            "publish_until":    self.until_e.get().strip(),
            "pinned":           self.pin_var.get(),
            "attachments_note": self.att_e.get().strip(),
        }
        try:
            if self.existing:
                data.update_notice(self.existing.notice_id, payload)
            else:
                data.create_notice(payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save notice failed")
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Feed tab (per-audience preview) ═══════════════════════════════

class FeedTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Feed")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Audience:").pack(side="left")
        self.aud_cb = ttk.Combobox(bar, values=AUDIENCES,
                                      state="readonly", width=24)
        self.aud_cb.set(DEFAULT_AUDIENCE)
        self.aud_cb.pack(side="left", padx=6)
        self.aud_cb.bind("<<ComboboxSelected>>",
                            lambda _e: self.refresh())
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left", padx=6)

        self.text = tk.Text(self.frame, wrap="word", state="disabled")
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def refresh(self) -> None:
        rows = data.feed(self.aud_cb.get())
        authors = _author_names()
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        if not rows:
            self.text.insert("1.0",
                              "(no notices visible to this audience)")
        else:
            for n in rows:
                pin = "★ " if n.pinned else ""
                author = (authors.get(n.author_staff_id, n.author_staff_id)
                           if n.author_staff_id else "—")
                self.text.insert(
                    "end",
                    f"{pin}#{n.notice_id}  [{n.priority}]  {n.title}\n"
                    f"  {n.category} • {n.audience} • "
                    f"{n.publish_from or '—'}"
                    + (f" → {n.publish_until}" if n.publish_until else "")
                    + f" • by {author}\n\n"
                    f"  {n.body}\n\n"
                    f"  {'─' * 80}\n\n")
        self.text.configure(state="disabled")


# ══ Summary tab ═══════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Expiring window (days):").pack(side="left")
        self.window_e = ttk.Entry(bar, width=4)
        self.window_e.insert(0, "7")
        self.window_e.pack(side="left", padx=6)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left", padx=8)
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10), state="disabled")
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def refresh(self) -> None:
        try:
            window = int(self.window_e.get().strip() or "7")
        except ValueError:
            messagebox.showerror("Summary", "Window must be a whole number.")
            return
        summ = data.summary(expiring_window_days=window)
        L: list[str] = []
        L.append("Counts")
        L.append("------")
        L.append(f"  Total       : {summ.total}")
        L.append(f"  Drafts      : {summ.drafts}")
        L.append(f"  Published   : {summ.published}")
        L.append(f"  Archived    : {summ.archived}")
        L.append("")
        L.append("Right now")
        L.append("---------")
        L.append(f"  Visible today    : {summ.visible_today}")
        L.append(f"  Pinned visible   : {summ.pinned}")
        L.append(f"  Urgent visible   : {summ.urgent_visible}")
        L.append(f"  Expiring in {window}d : {summ.expiring_within}")
        L.append("")
        L.append("By category")
        L.append("-----------")
        for c in CATEGORIES:
            n = summ.by_category.get(c, 0)
            if n:
                L.append(f"  {c:<22} : {n}")
        L.append("")
        L.append("By audience")
        L.append("-----------")
        for a in AUDIENCES:
            n = summ.by_audience.get(a, 0)
            if n:
                L.append(f"  {a:<22} : {n}")
        L.append("")
        L.append("By priority")
        L.append("-----------")
        for p in PRIORITIES:
            L.append(f"  {p:<10} : {summ.by_priority.get(p, 0)}")
        if summ.top_viewed:
            L.append("")
            L.append("Top viewed")
            L.append("----------")
            for nid, title, views in summ.top_viewed:
                L.append(f"  #{nid:<4}  {views:>5} views  {title[:60]}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(L))
        self.text.configure(state="disabled")
