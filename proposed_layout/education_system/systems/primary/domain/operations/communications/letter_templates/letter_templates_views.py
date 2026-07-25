"""Tkinter views for Primary School Letter Templates."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.platform import branding
from education_system.systems.primary.domain.operations.communications.letter_templates import (
    letter_templates as data,
)
from education_system.systems.primary.domain.operations.communications.letter_templates.letter_templates import (
    CATEGORIES,
    DEFAULT_CATEGORY,
    DEFAULT_FORMAT,
    DEFAULT_RECIPIENT_TYPE,
    DEFAULT_STATUS,
    FORMATS,
    RECIPIENT_TYPES,
    STATUSES,
    Template,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Draft":    ("#fff7e6", "#7a5800"),
    "Active":   ("#e6f7e6", "#0d6b2a"),
    "Archived": ("#eeeeee", "#666666"),
    "Retired":  ("#dddddd", "#444444"),
}


def open_letter_templates_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Letter Templates — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    TemplatesTab(nb, scope="active",   label="Active")
    TemplatesTab(nb, scope="drafts",   label="Drafts")
    TemplatesTab(nb, scope="archived", label="Archived")
    TemplatesTab(nb, scope="all",      label="All")
    SummaryTab(nb)


class TemplatesTab:
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
        ttk.Label(bar, text="Category:").pack(side="left")
        self.f_cat = ttk.Combobox(
            bar, values=("",) + CATEGORIES,
            state="readonly", width=22)
        self.f_cat.current(0)
        self.f_cat.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Recipient:").pack(side="left")
        self.f_rt = ttk.Combobox(
            bar, values=("",) + RECIPIENT_TYPES,
            state="readonly", width=16)
        self.f_rt.current(0)
        self.f_rt.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Format:").pack(side="left")
        self.f_fmt = ttk.Combobox(
            bar, values=("",) + FORMATS,
            state="readonly", width=18)
        self.f_fmt.current(0)
        self.f_fmt.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Name:").pack(side="left")
        self.f_name = ttk.Entry(bar, width=20)
        self.f_name.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                 padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left",
                                              padx=(16, 0))

        paned = ttk.PanedWindow(self.frame, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=4)

        left = ttk.Frame(paned)
        paned.add(left, weight=2)
        cols = ("id", "name", "category", "recipient",
                "format", "status", "uses")
        self.tree = ttk.Treeview(left, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "name": 280, "category": 180,
                   "recipient": 130, "format": 160,
                   "status": 90, "uses": 60}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "uses")
                                       else "w"))
        vsb = ttk.Scrollbar(left, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.bind("<<TreeviewSelect>>",
                         lambda _e: self._show_preview())
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        right = ttk.Frame(paned)
        paned.add(right, weight=3)
        ttk.Label(right, text="Preview").pack(
            anchor="w", padx=4, pady=(0, 2))
        self.preview = tk.Text(right, wrap="word",
                                  font=("TkFixedFont", 10))
        self.preview.pack(fill="both", expand=True,
                            padx=4, pady=4)
        self.preview.config(state="disabled")

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",          self._edit),
                ("Activate",      self._activate),
                ("Archive",       self._archive),
                ("Retire",        self._retire),
                ("Change status", self._set_status),
                ("Duplicate",     self._duplicate),
                ("Render",        self._render),
                ("Record use",    self._record_use),
                ("Delete",        self._delete),
                ("Refresh",       self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_cat.get():
            f["category"] = self.f_cat.get()
        if self.f_rt.get():
            f["recipient_type"] = self.f_rt.get()
        if self.f_fmt.get():
            f["format"] = self.f_fmt.get()
        if self.f_name.get().strip():
            f["name_like"] = self.f_name.get().strip()
        if self.scope == "active":
            f["active_only"] = True
        elif self.scope == "drafts":
            f["status"] = "Draft"
        elif self.scope == "archived":
            f["status"] = "Archived"
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_templates(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Letter Templates", str(e),
                                    parent=self.frame)
            return
        for t in rows:
            self.tree.insert(
                "", "end", iid=str(t.template_id),
                values=(t.template_id, t.name, t.category,
                         t.recipient_type, t.format,
                         t.status, t.use_count),
                tags=(t.status,))
        self.count.config(text=f"{len(rows)} template(s)")
        self._set_preview("")

    def _selected(self) -> Template | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Letter Templates",
                                  "Select a template first.",
                                  parent=self.frame)
            return None
        return data.get_template(int(sel[0]))

    def _show_preview(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        t = data.get_template(int(sel[0]))
        if not t:
            return
        lines: list[str] = []
        lines.append(f"#{t.template_id}  {t.name}")
        lines.append(f"Category : {t.category}")
        lines.append(f"Recipient: {t.recipient_type}")
        lines.append(f"Format   : {t.format}")
        lines.append(f"Status   : {t.status}")
        if t.merge_fields:
            lines.append(f"Fields   : {t.merge_fields}")
        if t.subject_line:
            lines.append("")
            lines.append(f"Subject: {t.subject_line}")
        lines.append("")
        lines.append("Body:")
        lines.append(t.body or "")
        self._set_preview("\n".join(lines))

    def _set_preview(self, text: str) -> None:
        self.preview.config(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.config(state="disabled")

    def _new(self) -> None:
        if TemplateEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        t = self._selected()
        if t and TemplateEditor(
                self.frame, template=t).result is not None:
            self.refresh()

    def _activate(self) -> None:
        t = self._selected()
        if not t:
            return
        try:
            data.activate(t.template_id)
        except ValidationError as e:
            messagebox.showerror("Letter Templates", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _archive(self) -> None:
        t = self._selected()
        if not t:
            return
        try:
            data.archive(t.template_id)
        except ValidationError as e:
            messagebox.showerror("Letter Templates", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _retire(self) -> None:
        t = self._selected()
        if not t:
            return
        try:
            data.retire(t.template_id)
        except ValidationError as e:
            messagebox.showerror("Letter Templates", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        t = self._selected()
        if not t:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES),
                                default=t.status)
        if not new:
            return
        try:
            data.set_status(t.template_id, new)
        except ValidationError as e:
            messagebox.showerror("Letter Templates", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _duplicate(self) -> None:
        t = self._selected()
        if not t:
            return
        new_name = _prompt_text(self.frame, "New name",
                                  initial=f"{t.name} (copy)")
        if not new_name:
            return
        try:
            data.duplicate(t.template_id, new_name=new_name)
        except ValidationError as e:
            messagebox.showerror("Letter Templates", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _render(self) -> None:
        t = self._selected()
        if not t:
            return
        RenderDialog(self.frame, template=t)
        self.refresh()

    def _record_use(self) -> None:
        t = self._selected()
        if not t:
            return
        try:
            data.record_use(t.template_id)
        except ValidationError as e:
            messagebox.showerror("Letter Templates", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        t = self._selected()
        if not t:
            return
        if not messagebox.askyesno(
                "Letter Templates",
                f"Delete template #{t.template_id} "
                f"({t.name})?",
                parent=self.frame):
            return
        data.delete_template(t.template_id)
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
        self.text.insert("end", "Letter Templates Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total            : {s.total}\n"
                            f"Active           : {s.active}\n"
                            f"Drafts           : {s.drafts}\n"
                            f"Archived         : {s.archived}\n"
                            f"Retired          : {s.retired}\n"
                            f"Total uses       : {s.total_uses}\n")
        if s.most_used_name:
            self.text.insert(
                "end",
                f"Most used        : {s.most_used_name} "
                f"({s.most_used_count} uses)\n")
        self.text.insert("end", "\nBy category:\n")
        for k in CATEGORIES:
            n = s.by_category.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy recipient type:\n")
        for k in RECIPIENT_TYPES:
            n = s.by_recipient_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<18}: {n}\n")
        self.text.insert("end", "\nBy format:\n")
        for k in FORMATS:
            n = s.by_format.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.config(state="disabled")


# ── Editor ──────────────────────────────────────────────

class TemplateEditor:
    def __init__(self, parent, *,
                 template: Template | None = None) -> None:
        self.template = template
        self.result: Template | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Edit template #{template.template_id}"
            if template else "New template")
        self.win.geometry("900x820")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if template:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
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

        entry(0, 0, "Name*", "name", width=48)
        combo(1, 0, "Category*", "category", CATEGORIES)
        combo(1, 2, "Recipient*", "recipient_type",
                 RECIPIENT_TYPES)
        combo(2, 0, "Format*", "format", FORMATS)
        combo(2, 2, "Status*", "status", STATUSES)
        entry(3, 0, "Subject line", "subject_line", width=48)
        entry(4, 0, "Sender role", "sender_role")
        entry(4, 2, "Created by", "created_by")
        entry(5, 0, "Attachments ref", "attachments_ref")
        entry(5, 2, "Merge fields (CSV; blank = auto)",
                 "merge_fields")
        entry(6, 0, "Description", "description", width=48)

        row = 7
        for key, label, h in (
                ("letterhead", "Letterhead", 3),
                ("body",       "Body* (use {{placeholder}})", 8),
                ("signature",  "Signature", 3),
                ("footer",     "Footer", 2),
                ("notes",      "Notes", 2),
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

        self.vars["category"].set(DEFAULT_CATEGORY)
        self.vars["recipient_type"].set(DEFAULT_RECIPIENT_TYPE)
        self.vars["format"].set(DEFAULT_FORMAT)
        self.vars["status"].set(DEFAULT_STATUS)

    def _load(self) -> None:
        t = self.template
        assert t is not None
        for key in ("name", "category", "recipient_type",
                     "format", "status", "subject_line",
                     "sender_role", "created_by",
                     "attachments_ref", "merge_fields",
                     "description"):
            self.vars[key].set(getattr(t, key) or "")
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(t, k) or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.template:
                self.result = data.update_template(
                    self.template.template_id, payload)
            else:
                self.result = data.create_template(payload)
        except ValidationError as exc:
            messagebox.showerror("Letter Templates", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


# ── Render dialog ─────────────────────────────────────────

class RenderDialog:
    def __init__(self, parent, *, template: Template) -> None:
        self.template = template
        self.win = tk.Toplevel(parent)
        self.win.title(f"Render — {template.name}")
        self.win.geometry("780x680")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self.entries: dict[str, tk.StringVar] = {}
        self._build()
        self.win.wait_window()

    def _build(self) -> None:
        top = ttk.Frame(self.win)
        top.pack(fill="x", padx=12, pady=10)
        ttk.Label(
            top,
            text=f"Template: {self.template.name} "
                  f"({self.template.format})").pack(anchor="w")

        placeholders = self.template.detected_placeholders
        fields_frame = ttk.LabelFrame(self.win,
                                         text="Merge fields")
        fields_frame.pack(fill="x", padx=12, pady=4)
        if not placeholders:
            ttk.Label(fields_frame,
                       text="(this template has no placeholders)"
                       ).grid(row=0, column=0, padx=8, pady=4)
        else:
            fields_frame.grid_columnconfigure(1, weight=1)
            for i, p in enumerate(placeholders):
                ttk.Label(fields_frame, text=p).grid(
                    row=i, column=0, sticky="w",
                    padx=4, pady=2)
                v = tk.StringVar()
                self.entries[p] = v
                ttk.Entry(fields_frame, textvariable=v,
                            width=60).grid(
                    row=i, column=1, sticky="ew",
                    padx=4, pady=2)

        ttk.Label(self.win, text="Output").pack(
            anchor="w", padx=12, pady=(8, 2))
        self.output = tk.Text(self.win, wrap="word",
                                 font=("TkFixedFont", 10))
        self.output.pack(fill="both", expand=True,
                            padx=12, pady=4)

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Render",
                    command=self._render).pack(side="left",
                                                  padx=4)
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")

    def _render(self) -> None:
        ctx = {k: v.get() for k, v in self.entries.items()
                if v.get()}
        try:
            r = data.render(self.template, ctx)
        except ValidationError as exc:
            messagebox.showerror("Letter Templates", str(exc),
                                    parent=self.win)
            return
        self.output.config(state="normal")
        self.output.delete("1.0", "end")
        if r.subject is not None:
            self.output.insert("end",
                                  f"Subject: {r.subject}\n\n")
        self.output.insert("end", r.body)
        if r.missing_fields:
            self.output.insert(
                "end",
                "\n\n---\nMissing fields: "
                f"{', '.join(r.missing_fields)}")
        self.output.config(state="disabled")


def _prompt_text(parent, title: str, *,
                  initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("420x140")
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
    ttk.Button(bar, text="OK", command=ok).pack(side="right",
                                                    padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


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


__all__ = ["open_letter_templates_window"]
