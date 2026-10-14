"""Tkinter views for Secondary School Attachments."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.platform import branding
from education_system.systems.secondary.domain.operations.attachments import (
    attachments as data,
)
from education_system.systems.secondary.domain.operations.attachments.attachments import (
    Attachment,
    CATEGORIES,
    DEFAULT_CATEGORY,
    DEFAULT_ENTITY_TYPE,
    DEFAULT_STATUS,
    DEFAULT_VISIBILITY,
    ENTITY_TYPES,
    STATUSES,
    ValidationError,
    VISIBILITY,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Active":      ("#e6f7e6", "#0d6b2a"),
    "Quarantined": ("#fff7e6", "#7a5800"),
    "Archived":    ("#dddddd", "#444444"),
    "Deleted":     ("#ffd1d1", "#8c0d0d"),
}


def open_attachments_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Attachments — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    AttachmentsTab(nb, scope="active",       label="Active")
    AttachmentsTab(nb, scope="pii",          label="Contains PII")
    AttachmentsTab(nb, scope="retention",    label="Retention Expired")
    AttachmentsTab(nb, scope="quarantined",  label="Quarantined")
    AttachmentsTab(nb, scope="all",          label="All")
    SummaryTab(nb)


class AttachmentsTab:
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
        ttk.Label(bar, text="Entity type:").pack(side="left")
        self.f_et = ttk.Combobox(
            bar, values=("",) + ENTITY_TYPES,
            state="readonly", width=14)
        self.f_et.current(0)
        self.f_et.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Entity id:").pack(side="left")
        self.f_eid = ttk.Entry(bar, width=12)
        self.f_eid.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Category:").pack(side="left")
        self.f_cat = ttk.Combobox(
            bar, values=("",) + CATEGORIES,
            state="readonly", width=14)
        self.f_cat.current(0)
        self.f_cat.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Visibility:").pack(side="left")
        self.f_vis = ttk.Combobox(
            bar, values=("",) + VISIBILITY,
            state="readonly", width=14)
        self.f_vis.current(0)
        self.f_vis.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(
                bar, values=("",) + STATUSES,
                state="readonly", width=12)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None
        ttk.Label(bar, text="Title:").pack(side="left")
        self.f_title = ttk.Entry(bar, width=16)
        self.f_title.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                 padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left",
                                              padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True,
                            padx=8, pady=4)
        cols = ("id", "pii", "ret", "entity", "title",
                "category", "visibility", "format",
                "uploaded", "uploader", "size", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "pii": 40, "ret": 40,
                   "entity": 200, "title": 240,
                   "category": 110, "visibility": 110,
                   "format": 70, "uploaded": 100,
                   "uploader": 120, "size": 70,
                   "status": 110}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "pii",
                                                  "ret",
                                                  "size")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.tag_configure("retention_expired",
                                  background="#ffd1d1",
                                  foreground="#8c0d0d")
        self.tree.tag_configure("confidential",
                                  background="#fff0c2",
                                  foreground="#7a5800")
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",           self._edit),
                ("Quarantine",     self._quarantine),
                ("Restore",        self._restore),
                ("Archive",        self._archive),
                ("Soft-delete",    self._soft_delete),
                ("Change status",  self._set_status),
                ("Record access",  self._record_access),
                ("Purge ret.exp",  self._purge_retention),
                ("Hard delete",    self._delete),
                ("Refresh",        self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_et.get():
            f["entity_type"] = self.f_et.get()
        if self.f_eid.get().strip():
            f["entity_id"] = self.f_eid.get().strip()
        if self.f_cat.get():
            f["category"] = self.f_cat.get()
        if self.f_vis.get():
            f["visibility"] = self.f_vis.get()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.f_title.get().strip():
            f["title_like"] = self.f_title.get().strip()
        if self.scope == "active":
            f["active_only"] = True
        elif self.scope == "pii":
            f["pii_only"] = True
        elif self.scope == "retention":
            f["retention_expired_only"] = True
        elif self.scope == "quarantined":
            f["status"] = "Quarantined"
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_attachments(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Attachments", str(e),
                                    parent=self.frame)
            return
        for a in rows:
            if a.is_expired_retention:
                tag = "retention_expired"
            elif a.visibility == "Confidential":
                tag = "confidential"
            else:
                tag = a.status
            ent = f"{a.entity_type}: {a.entity_id}"
            size = (f"{a.file_size_kb}kB"
                      if a.file_size_kb is not None else "—")
            self.tree.insert(
                "", "end", iid=str(a.attachment_id),
                values=(a.attachment_id,
                         "P" if a.contains_pii else "",
                         "!" if a.is_expired_retention else "",
                         ent, a.title, a.category,
                         a.visibility, a.file_format or "—",
                         a.uploaded_on[:10],
                         a.uploaded_by or "—",
                         size, a.status),
                tags=(tag,))
        self.count.config(text=f"{len(rows)} attachment(s)")

    def _selected(self) -> Attachment | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Attachments",
                                  "Select an attachment first.",
                                  parent=self.frame)
            return None
        return data.get_attachment(int(sel[0]))

    def _new(self) -> None:
        if AttachmentEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        a = self._selected()
        if a and AttachmentEditor(
                self.frame,
                attachment=a).result is not None:
            self.refresh()

    def _quarantine(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.quarantine(a.attachment_id)
        except ValidationError as e:
            messagebox.showerror("Attachments", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _restore(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.restore(a.attachment_id)
        except ValidationError as e:
            messagebox.showerror("Attachments", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _archive(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.archive(a.attachment_id)
        except ValidationError as e:
            messagebox.showerror("Attachments", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _soft_delete(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.soft_delete(a.attachment_id)
        except ValidationError as e:
            messagebox.showerror("Attachments", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        a = self._selected()
        if not a:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES),
                                default=a.status)
        if not new:
            return
        try:
            data.set_status(a.attachment_id, new)
        except ValidationError as e:
            messagebox.showerror("Attachments", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _record_access(self) -> None:
        a = self._selected()
        if not a:
            return
        try:
            data.record_access(a.attachment_id)
        except ValidationError as e:
            messagebox.showerror("Attachments", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _purge_retention(self) -> None:
        hard = messagebox.askyesno(
            "Attachments",
            "Hard-delete retention-expired? "
            "(No = soft-delete)",
            parent=self.frame)
        n = data.purge_expired_retention(hard_delete=hard)
        messagebox.showinfo(
            "Attachments",
            f"{n} attachment(s) "
            f"{'hard-deleted' if hard else 'soft-deleted'}.",
            parent=self.frame)
        self.refresh()

    def _delete(self) -> None:
        a = self._selected()
        if not a:
            return
        if not messagebox.askyesno(
                "Attachments",
                f"Hard-delete attachment #{a.attachment_id}?",
                parent=self.frame):
            return
        data.delete_attachment(a.attachment_id)
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
        self.text.pack(fill="both", expand=True, padx=8,
                          pady=(4, 8))
        self.refresh()

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "Attachments Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total                : {s.total}\n"
                            f"Active               : {s.active}\n"
                            f"Quarantined          : {s.quarantined}\n"
                            f"Archived             : {s.archived}\n"
                            f"Deleted              : {s.deleted}\n"
                            f"Confidential         : {s.confidential}\n"
                            f"Contains PII         : {s.contains_pii}\n"
                            f"Retention expired    : {s.retention_expired}\n"
                            f"Total size (kB)      : {s.total_size_kb}\n"
                            f"Total downloads      : {s.total_downloads}\n"
                            f"Distinct entities    : {s.distinct_entities}\n\n")
        self.text.insert("end", "By entity type:\n")
        for k in ENTITY_TYPES:
            n = s.by_entity_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy category:\n")
        for k in CATEGORIES:
            n = s.by_category.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy visibility:\n")
        for k in VISIBILITY:
            n = s.by_visibility.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nBy format:\n")
        for fmt, n in sorted(s.by_format.items(),
                                  key=lambda kv: -kv[1]):
            if n:
                self.text.insert("end", f"  {fmt:<14}: {n}\n")
        self.text.config(state="disabled")


# ── Editor ──────────────────────────────────────────────

class AttachmentEditor:
    def __init__(self, parent, *,
                 attachment: Attachment | None = None) -> None:
        self.attachment = attachment
        self.result: Attachment | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Edit attachment #{attachment.attachment_id}"
            if attachment else "New attachment")
        self.win.geometry("900x780")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if attachment:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.bools: dict[str, tk.BooleanVar] = {}
        self.texts: dict[str, tk.Text] = {}

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w",
                padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w",
                padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        combo(0, 0, "Entity type*", "entity_type",
                 ENTITY_TYPES)
        entry(0, 2, "Entity id*", "entity_id")
        entry(1, 0, "Title*", "title", width=48)
        entry(2, 0, "File ref / URL*", "file_ref", width=48)
        entry(3, 0, "File name", "file_name")
        entry(3, 2, "File format", "file_format")
        entry(4, 0, "File size (kB)", "file_size_kb")
        entry(4, 2, "MIME type", "mime_type")
        entry(5, 0, "Checksum", "checksum")
        entry(5, 2, "Uploaded by", "uploaded_by")
        entry(6, 0, "Uploaded on (YYYY-MM-DD)", "uploaded_on")
        entry(6, 2, "Retention until (YYYY-MM-DD)",
                 "retention_until")
        combo(7, 0, "Category*", "category", CATEGORIES)
        combo(7, 2, "Visibility*", "visibility", VISIBILITY)
        combo(8, 0, "Status*", "status", STATUSES)
        entry(9, 0, "Keywords (CSV)", "tagged_keywords",
                 width=48)

        flags = ttk.LabelFrame(body, text="Flags")
        flags.grid(row=10, column=0, columnspan=4,
                      sticky="ew", padx=4, pady=(8, 4))
        for col, (key, label) in enumerate((
                ("contains_pii",     "Contains PII"),
                ("consent_recorded", "Consent recorded"),
        )):
            v = tk.BooleanVar()
            self.bools[key] = v
            ttk.Checkbutton(flags, text=label,
                             variable=v).grid(
                row=0, column=col, sticky="w",
                padx=6, pady=4)

        row = 11
        for key, label, h in (
                ("description", "Description", 4),
                ("notes",       "Notes", 3),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw",
                padx=4, pady=(6, 2))
            t = tk.Text(body, height=h, width=74, wrap="word")
            t.grid(row=row, column=1, columnspan=3,
                     sticky="ew", padx=4, pady=(6, 2))
            self.texts[key] = t
            row += 1

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right",
                                               padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        import datetime as _dt
        self.vars["entity_type"].set(DEFAULT_ENTITY_TYPE)
        self.vars["category"].set(DEFAULT_CATEGORY)
        self.vars["visibility"].set(DEFAULT_VISIBILITY)
        self.vars["status"].set(DEFAULT_STATUS)
        self.vars["uploaded_on"].set(
            _dt.date.today().isoformat())

    def _load(self) -> None:
        a = self.attachment
        assert a is not None
        for key in ("entity_type", "entity_id", "title",
                     "file_ref", "file_name", "file_format",
                     "mime_type", "checksum", "uploaded_by",
                     "uploaded_on", "retention_until",
                     "category", "visibility", "status",
                     "tagged_keywords"):
            self.vars[key].set(getattr(a, key) or "")
        self.vars["file_size_kb"].set(
            str(a.file_size_kb or ""))
        for k in self.bools:
            self.bools[k].set(getattr(a, k))
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(a, k) or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, b in self.bools.items():
            payload[k] = b.get()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.attachment:
                self.result = data.update_attachment(
                    self.attachment.attachment_id, payload)
            else:
                self.result = data.create_attachment(payload)
        except ValidationError as exc:
            messagebox.showerror("Attachments", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


def _prompt_choice(parent, title: str, options: list[str], *,
                    default: str | None = None) -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("360x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(
        value=default or (options[0] if options else ""))
    ttk.Combobox(win, textvariable=var, values=options,
                  state="readonly").pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right",
                                                    padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


__all__ = ["open_attachments_window"]
