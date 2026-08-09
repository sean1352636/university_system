"""Tkinter views for Sixth Form Feedback."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.platform import branding
from education_system.systems.primary.domain.pastoral.feedback import (
    feedback as data,
)
from education_system.systems.primary.domain.pastoral.feedback.feedback import (
    CATEGORIES,
    DEFAULT_CATEGORY,
    DEFAULT_FEEDBACK_TYPE,
    DEFAULT_SOURCE,
    DEFAULT_STATUS,
    DEFAULT_SUBMITTER_ROLE,
    FEEDBACK_TYPES,
    Feedback,
    RATINGS,
    SOURCES,
    STATUSES,
    SUBMITTER_ROLES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Received":  ("#fff7e6", "#7a5800"),
    "Reviewing": ("#e6f0ff", "#1a3f8c"),
    "Responded": ("#e6f7e6", "#0d6b2a"),
    "Acted":     ("#d6ffd6", "#0d6b2a"),
    "Closed":    ("#eeeeee", "#444444"),
    "Archived":  ("#dddddd", "#444444"),
}


def open_feedback_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Feedback — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    FBTab(nb, scope="open",      label="Open")
    FBTab(nb, scope="awaiting",  label="Awaiting Response")
    FBTab(nb, scope="public",    label="Public Shareable")
    FBTab(nb, scope="all",       label="All")
    SummaryTab(nb)


class FBTab:
    def __init__(self, nb: ttk.Notebook, *,
                 scope: str, label: str) -> None:
        self.scope = scope
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar,
                                     values=("",) + FEEDBACK_TYPES,
                                     state="readonly", width=14)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Category:").pack(side="left")
        self.f_cat = ttk.Combobox(bar, values=("",) + CATEGORIES,
                                    state="readonly", width=22)
        self.f_cat.current(0)
        self.f_cat.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + STATUSES,
                                           state="readonly", width=12)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None
        ttk.Label(bar, text="Min rating:").pack(side="left")
        self.f_rate = ttk.Combobox(bar,
                                      values=("",) + tuple(str(r)
                                                            for r in RATINGS),
                                      state="readonly", width=4)
        self.f_rate.current(0)
        self.f_rate.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Subject:").pack(side="left")
        self.f_subj = ttk.Entry(bar, width=14)
        self.f_subj.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                  padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "received", "type", "category",
                "subject", "rating", "source",
                "submitter", "status", "flags")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "received": 90, "type": 110,
                   "category": 170, "subject": 240,
                   "rating": 70, "source": 130,
                   "submitter": 140, "status": 110, "flags": 90}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "rating")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.tag_configure("awaiting", background="#fff0d6",
                                  foreground="#7a5800")
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("View / Edit",   self._edit),
                ("Assign",        self._assign),
                ("Respond",       self._respond),
                ("Mark acted",    self._acted),
                ("Close",         self._close),
                ("Archive",       self._archive),
                ("Change status", self._set_status),
                ("Delete",        self._delete),
                ("Refresh",       self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _clear(self) -> None:
        self.f_type.current(0)
        self.f_cat.current(0)
        self.f_rate.current(0)
        self.f_subj.delete(0, "end")
        if self.f_status is not None:
            self.f_status.current(0)
        self.refresh()

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_type.get():
            f["feedback_type"] = self.f_type.get()
        if self.f_cat.get():
            f["category"] = self.f_cat.get()
        if self.f_rate.get():
            f["rating_min"] = int(self.f_rate.get())
        if self.f_subj.get().strip():
            f["subject_like"] = self.f_subj.get().strip()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "open":
            f["open_only"] = True
        elif self.scope == "awaiting":
            f["awaiting_response"] = True
        elif self.scope == "public":
            f["public_only"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_feedback(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Feedback", str(e),
                                    parent=self.frame)
            return
        for f in rows:
            flags = []
            if f.anonymous:
                flags.append("ANON")
            if f.public_shareable:
                flags.append("PUB")
            if (f.is_open and not f.has_response):
                flags.append("AWAIT")
            rate = (f"{f.rating}/5" if f.rating else "—")
            submitter = (f.submitter_name or
                            ("anonymous" if f.anonymous else "—"))
            tag = ("awaiting" if (f.is_open and not f.has_response)
                     else f.status)
            self.tree.insert(
                "", "end", iid=str(f.feedback_id),
                values=(f.feedback_id, f.received_on,
                         f.feedback_type, f.category,
                         f.subject, rate, f.source,
                         submitter, f.status, ",".join(flags)),
                tags=(tag,))
        self.count.config(text=f"{len(rows)} item(s)")

    def _selected(self) -> Feedback | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Feedback",
                                  "Select an item first.",
                                  parent=self.frame)
            return None
        return data.get_feedback(int(sel[0]))

    def _new(self) -> None:
        if FeedbackEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        f = self._selected()
        if f and FeedbackEditor(self.frame,
                                       feedback=f).result is not None:
            self.refresh()

    def _assign(self) -> None:
        f = self._selected()
        if not f:
            return
        to = _prompt_text(self.frame, "Assign to",
                            initial=f.assigned_to or "")
        if not to:
            return
        try:
            data.assign(f.feedback_id, to=to)
        except ValidationError as exc:
            messagebox.showerror("Feedback", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _respond(self) -> None:
        f = self._selected()
        if not f:
            return
        if RespondDialog(self.frame,
                            feedback=f).result is not None:
            self.refresh()

    def _acted(self) -> None:
        f = self._selected()
        if not f:
            return
        notes = _prompt_multiline(self.frame,
                                       "Action notes (optional)")
        if notes is None:
            return
        try:
            data.mark_acted(f.feedback_id,
                                notes=notes or None)
        except ValidationError as exc:
            messagebox.showerror("Feedback", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _close(self) -> None:
        f = self._selected()
        if not f:
            return
        try:
            data.close_feedback(f.feedback_id)
        except ValidationError as exc:
            messagebox.showerror("Feedback", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _archive(self) -> None:
        f = self._selected()
        if not f:
            return
        try:
            data.archive(f.feedback_id)
        except ValidationError as exc:
            messagebox.showerror("Feedback", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        f = self._selected()
        if not f:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES), default=f.status)
        if not new:
            return
        try:
            data.set_status(f.feedback_id, new)
        except ValidationError as exc:
            messagebox.showerror("Feedback", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        f = self._selected()
        if not f:
            return
        if not messagebox.askyesno(
                "Feedback", f"Delete #{f.feedback_id}?",
                parent=self.frame):
            return
        data.delete_feedback(f.feedback_id)
        self.refresh()


class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.refresh()

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "Feedback Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total              : {s.total}\n"
                            f"Open               : {s.open_count}\n"
                            f"Awaiting response  : {s.awaiting_response}\n"
                            f"Positive           : {s.positive_count}\n"
                            f"Negative           : {s.negative_count}\n"
                            f"Suggestions        : {s.suggestions_count}\n"
                            f"Public shareable   : {s.public_count}\n"
                            f"Average rating     : "
                            f"{s.average_rating if s.average_rating is not None else '—'}\n\n")
        self.text.insert("end", "By type:\n")
        for k in FEEDBACK_TYPES:
            n = s.by_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nBy category:\n")
        for k in CATEGORIES:
            n = s.by_category.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<24}: {n}\n")
        self.text.insert("end", "\nBy source:\n")
        for k in SOURCES:
            n = s.by_source.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<18}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        if s.by_rating:
            self.text.insert("end", "\nBy rating:\n")
            for r in RATINGS:
                n = s.by_rating.get(r, 0)
                if n:
                    self.text.insert("end", f"  {r}/5 : {n}\n")
        self.text.config(state="disabled")


# ── Editor + dialogs ──────────────────────────────────────────────

class FeedbackEditor:
    def __init__(self, parent, *,
                 feedback: Feedback | None = None) -> None:
        self.feedback = feedback
        self.result: Feedback | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit feedback #{feedback.feedback_id}"
                          if feedback else "New feedback")
        self.win.geometry("820x780")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if feedback:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}
        self.bools: dict[str, tk.BooleanVar] = {}

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        entry(0, 0, "Subject*", "subject", width=48)
        entry(1, 0, "Received on*", "received_on")
        combo(1, 2, "Source*", "source", SOURCES)
        combo(2, 0, "Submitter role*", "submitter_role",
                 SUBMITTER_ROLES)
        entry(2, 2, "Submitter name", "submitter_name")
        entry(3, 0, "Email", "contact_email")
        entry(3, 2, "Phone", "contact_phone")
        combo(4, 0, "Type*", "feedback_type", FEEDBACK_TYPES)
        combo(4, 2, "Category*", "category", CATEGORIES)
        combo(5, 0, "Rating", "rating",
                 ("", "1", "2", "3", "4", "5"))
        combo(5, 2, "Status*", "status", STATUSES)
        entry(6, 0, "Assigned to", "assigned_to")
        entry(6, 2, "Linked to", "linked_to")
        entry(7, 0, "Response by", "response_by")
        entry(7, 2, "Response on", "response_on")
        entry(8, 0, "Closed on", "closed_on")

        flags = ttk.LabelFrame(body, text="Flags")
        flags.grid(row=9, column=0, columnspan=4,
                     sticky="ew", padx=4, pady=(8, 4))
        for col, (key, label) in enumerate((
                ("anonymous",         "Anonymous"),
                ("public_shareable",  "Public shareable"),
        )):
            v = tk.BooleanVar()
            self.bools[key] = v
            ttk.Checkbutton(flags, text=label,
                             variable=v).grid(
                row=0, column=col, sticky="w", padx=6, pady=4)

        row = 10
        for key, label in (
                ("description", "Description"),
                ("response",    "Response"),
                ("notes",       "Notes"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
            t = tk.Text(body, height=3, width=74, wrap="word")
            t.grid(row=row, column=1, columnspan=3,
                     sticky="ew", padx=4, pady=(6, 2))
            self.texts[key] = t
            row += 1

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["received_on"].set(_dt.date.today().isoformat())
        self.vars["source"].set(DEFAULT_SOURCE)
        self.vars["submitter_role"].set(DEFAULT_SUBMITTER_ROLE)
        self.vars["feedback_type"].set(DEFAULT_FEEDBACK_TYPE)
        self.vars["category"].set(DEFAULT_CATEGORY)
        self.vars["status"].set(DEFAULT_STATUS)

    def _load(self) -> None:
        f = self.feedback
        assert f is not None
        for key in ("subject", "received_on", "source",
                     "submitter_role", "submitter_name",
                     "contact_email", "contact_phone",
                     "feedback_type", "category",
                     "status", "assigned_to", "linked_to",
                     "response_by", "response_on", "closed_on"):
            self.vars[key].set(getattr(f, key) or "")
        self.vars["rating"].set(
            str(f.rating) if f.rating is not None else "")
        for k in self.bools:
            self.bools[k].set(getattr(f, k))
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(f, k) or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        for k, b in self.bools.items():
            payload[k] = b.get()
        try:
            if self.feedback:
                self.result = data.update_feedback(
                    self.feedback.feedback_id, payload)
            else:
                self.result = data.create_feedback(payload)
        except ValidationError as exc:
            messagebox.showerror("Feedback", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class RespondDialog:
    def __init__(self, parent, *, feedback: Feedback) -> None:
        self.feedback = feedback
        self.result: Feedback | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Respond — #{feedback.feedback_id}")
        self.win.geometry("520x420")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Response by*").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.by = tk.StringVar(value=feedback.response_by or "")
        ttk.Entry(body, textvariable=self.by).grid(
            row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Response on").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.when = tk.StringVar(
            value=feedback.response_on
            or _dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when, width=14).grid(
            row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Response*").grid(
            row=2, column=0, sticky="nw", padx=4, pady=4)
        self.response = tk.Text(body, height=10, width=48,
                                   wrap="word")
        self.response.insert("1.0", feedback.response or "")
        self.response.grid(row=2, column=1, sticky="ew",
                              padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.respond(
                self.feedback.feedback_id,
                response=self.response.get("1.0", "end").rstrip(),
                response_by=self.by.get().strip(),
                response_on=self.when.get().strip()
                or _dt.date.today().isoformat())
        except ValidationError as exc:
            messagebox.showerror("Feedback", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


def _prompt_text(parent, title: str, *,
                  initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("360x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=initial)
    ttk.Entry(win, textvariable=var).pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get().strip()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


def _prompt_multiline(parent, title: str, *,
                       initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("500x280")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    txt = tk.Text(win, wrap="word", height=8)
    txt.pack(fill="both", expand=True, padx=8)
    txt.insert("1.0", initial)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = txt.get("1.0", "end").rstrip()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


def _prompt_choice(parent, title: str, options: list[str], *,
                    default: str | None = None) -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("320x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=default or (options[0] if options else ""))
    ttk.Combobox(win, textvariable=var, values=options,
                  state="readonly").pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


__all__ = ["open_feedback_window"]
