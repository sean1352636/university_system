"""Tk views for the SEF builder."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.systems.secondary.domain.assessment.sef_builder import (
    sef_builder as data,
)
from education_system.systems.secondary.domain.assessment.sef_builder.sef_builder import (
    JUDGEMENTS, SEF_STATUSES, DEFAULT_SECTIONS,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError,
)

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror("SEF Builder", str(e),
                                     parent=getattr(host, "root", None))
            except Exception:
                pass
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=getattr(host, "root", None),
                )
            except Exception:
                pass
    return wrapper


def _doc_dialog(host, title: str,
                 initial: dict[str, Any] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("480x440")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ay_var       = tk.StringVar(value=str(initial.get("academic_year")
                                            or ""))
    ver_var      = tk.StringVar(value=str(initial.get("version")
                                             or "v1"))
    title_var    = tk.StringVar(value=str(initial.get("title") or ""))
    status_var   = tk.StringVar(value=str(initial.get("status")
                                            or "Draft"))
    jud_var      = tk.StringVar(value=str(initial.get("headline_judgement")
                                             or "Not yet evaluated"))
    author_var   = tk.StringVar(value=str(initial.get("author") or ""))
    approver_var = tk.StringVar(value=str(initial.get("approved_by")
                                             or ""))
    appdate_var  = tk.StringVar(value=str(initial.get("approved_date")
                                             or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Academic year:", ttk.Entry(frm, textvariable=ay_var,
                                       width=10)),
        ("Version:",       ttk.Entry(frm, textvariable=ver_var,
                                       width=10)),
        ("Title:",         ttk.Entry(frm, textvariable=title_var,
                                       width=40)),
        ("Status:",        ttk.Combobox(frm, textvariable=status_var,
                                         values=list(SEF_STATUSES),
                                         state="readonly", width=12)),
        ("Headline:",      ttk.Combobox(frm, textvariable=jud_var,
                                         values=list(JUDGEMENTS),
                                         state="readonly", width=22)),
        ("Author:",        ttk.Entry(frm, textvariable=author_var,
                                       width=24)),
        ("Approved by:",   ttk.Entry(frm, textvariable=approver_var,
                                       width=24)),
        ("Approved date:", ttk.Entry(frm, textvariable=appdate_var,
                                       width=14)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Notes:").grid(row=len(rows), column=0,
                                        sticky="nw", pady=2)
    notes_w = tk.Text(frm, width=44, height=4, wrap="word")
    notes_w.insert("1.0", str(initial.get("notes") or ""))
    notes_w.grid(row=len(rows), column=1, sticky="ew", pady=2)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "academic_year":      ay_var.get().strip(),
            "version":            ver_var.get().strip(),
            "title":              title_var.get().strip(),
            "status":             status_var.get().strip(),
            "headline_judgement": jud_var.get().strip(),
            "author":             author_var.get().strip(),
            "approved_by":        approver_var.get().strip(),
            "approved_date":      appdate_var.get().strip(),
            "notes":              notes_w.get("1.0", "end").strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


def _section_dialog(host, sef_id: int,
                     initial: dict[str, Any] | None = None
                     ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Section — SEF #{sef_id}")
    dlg.transient(host.root)
    dlg.geometry("580x620")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    code_var  = tk.StringVar(value=str(initial.get("section_code")
                                         or ""))
    title_var = tk.StringVar(value=str(initial.get("section_title")
                                          or ""))
    jud_var   = tk.StringVar(value=str(initial.get("judgement")
                                         or "Not yet evaluated"))
    updby_var = tk.StringVar(value=str(initial.get("last_updated_by")
                                          or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Code:",     ttk.Entry(frm, textvariable=code_var,
                                  width=14,
                                  state=("readonly"
                                          if initial.get("section_code")
                                          else "normal"))),
        ("Title:",    ttk.Entry(frm, textvariable=title_var, width=40)),
        ("Judgement:", ttk.Combobox(frm, textvariable=jud_var,
                                      values=list(JUDGEMENTS),
                                      state="readonly", width=22)),
        ("Updated by:", ttk.Entry(frm, textvariable=updby_var,
                                    width=24)),
    ]
    for label, widget in rows:
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=14).pack(side="left")
        widget.pack(in_=row, side="left", padx=4)

    text_fields = [("Strengths:", "strengths", 3),
                   ("Areas for development:",
                    "areas_for_development", 3),
                   ("Evidence:", "evidence", 3),
                   ("Action plan:", "action_plan", 3)]
    text_widgets: dict[str, tk.Text] = {}
    for label, key, lines in text_fields:
        ttk.Label(frm, text=label).pack(anchor="w", pady=(8, 0))
        t = tk.Text(frm, width=58, height=lines, wrap="word")
        t.insert("1.0", str(initial.get(key) or ""))
        t.pack(fill="x")
        text_widgets[key] = t

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "sef_id":         sef_id,
            "section_code":   code_var.get().strip(),
            "section_title":  title_var.get().strip(),
            "judgement":      jud_var.get().strip(),
            "last_updated_by": updby_var.get().strip(),
        }
        for k, w in text_widgets.items():
            result[k] = w.get("1.0", "end").strip()
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_sef_builder(host) -> None:
    logger.debug("GUI: open_sef_builder")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="SEF Builder",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var, foreground="#666").pack(
        anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Academic year:").pack(side="left", padx=(0, 4))
    ay_var = tk.StringVar(value="")
    ttk.Entry(bar, textvariable=ay_var, width=10).pack(
        side="left", padx=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                 values=["", *SEF_STATUSES], state="readonly",
                 width=12).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Sections",
               command=lambda: _open_sections(host, tree)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Status",
               command=lambda: _status(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "ay", "ver", "title", "status", "headline", "author")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("ay", "Academic year", 100),
        ("ver", "Version", 80), ("title", "Title", 240),
        ("status", "Status", 100), ("headline", "Headline", 180),
        ("author", "Author", 160),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_documents(
                academic_year=ay_var.get().strip() or None,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("SEF Builder", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("SEF refresh failed")
            messagebox.showerror("SEF Builder",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for d in rows:
            tree.insert("", "end", iid=str(d.sef_id), values=(
                d.sef_id, d.academic_year, d.version,
                d.title or "-", d.status, d.headline_judgement,
                d.author or "-",
            ))
        summary_var.set(f"{len(rows)} document(s) listed")
        host.status_var.set(f"SEF Builder: {len(rows)} doc(s)")

    tree.bind("<Double-1>", lambda _e: _open_sections(host, tree))
    status_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("SEF Builder",
                            "Select a document first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _doc_dialog(host, "New SEF document")
    if not fields:
        return
    d = data.create_document(fields, seed_sections=True)
    messagebox.showinfo(
        "SEF Builder",
        f"Created SEF {d.academic_year}/{d.version}\n"
        f"Seeded {len(DEFAULT_SECTIONS)} default section(s).",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    sid = _selected_id(tree, host)
    if sid is None:
        return
    existing = data.get_document(sid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "academic_year", "version", "title", "status",
        "headline_judgement", "author", "approved_by",
        "approved_date", "notes")}
    fields = _doc_dialog(host, f"Edit SEF #{sid}", initial=initial)
    if not fields:
        return
    data.update_document(sid, fields)
    if on_done:
        on_done()


@_safe_view
def _status(host, tree: ttk.Treeview, *, on_done=None) -> None:
    sid = _selected_id(tree, host)
    if sid is None:
        return
    d = data.get_document(sid)
    if d is None:
        return
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Status — SEF #{sid}")
    dlg.transient(host.root)
    dlg.geometry("360x180")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"{d.academic_year}/{d.version}").pack(anchor="w")
    ttk.Label(frm, text=f"Current: {d.status}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    new_var = tk.StringVar(value=d.status)
    ttk.Combobox(frm, textvariable=new_var,
                 values=list(SEF_STATUSES),
                 state="readonly").pack(fill="x")
    approver_var = tk.StringVar(value=d.approved_by or "")
    ttk.Label(frm, text="Approved by (required for Approved):").pack(
        anchor="w", pady=(8, 0))
    ttk.Entry(frm, textvariable=approver_var).pack(fill="x")

    def _save() -> None:
        try:
            data.set_status(sid, new_var.get(),
                             approved_by=approver_var.get().strip()
                             or None)
        except ValidationError as ex:
            messagebox.showerror("SEF Builder", str(ex), parent=dlg)
            return
        dlg.destroy()
        if on_done:
            on_done()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    sid = _selected_id(tree, host)
    if sid is None:
        return
    existing = data.get_document(sid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete SEF",
            f"Delete SEF {existing.academic_year}/{existing.version} "
            f"and ALL its sections?",
            parent=host.root):
        return
    data.delete_document(sid)
    if on_done:
        on_done()


@_safe_view
def _open_sections(host, tree: ttk.Treeview) -> None:
    sid = _selected_id(tree, host)
    if sid is None:
        return
    rec = data.get_document(sid)
    if rec is None:
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Sections — SEF {rec.academic_year}/{rec.version}")
    dlg.transient(host.root)
    dlg.geometry("820x520")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    frm = ttk.Frame(dlg, padding=10)
    frm.pack(fill="both", expand=True)
    header_var = tk.StringVar()
    ttk.Label(frm, textvariable=header_var,
              font=("", 10, "bold")).pack(anchor="w")

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 4))
    ttk.Button(bar, text="Seed defaults",
               command=lambda: _do_seed()).pack(side="left", padx=2)
    ttk.Button(bar, text="Add / new section",
               command=lambda: _do_upsert(None)).pack(side="left",
                                                      padx=2)
    ttk.Button(bar, text="Edit selected",
               command=lambda: _do_upsert("selected")
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete selected",
               command=lambda: _do_delete()).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    t = ttk.Treeview(frm,
                       columns=("id", "code", "title", "judgement",
                                 "updated_by"),
                       show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("code", "Code", 100),
        ("title", "Title", 280), ("judgement", "Judgement", 180),
        ("updated_by", "Updated by", 140),
    ]:
        t.heading(c, text=label)
        t.column(c, width=w, anchor="w")
    t.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in t.get_children():
            t.delete(i)
        try:
            s = data.document_summary(sid)
        except Exception as e:
            logger.exception("document_summary failed")
            messagebox.showerror("SEF Builder",
                                 f"Could not load:\n\n{e}",
                                 parent=dlg)
            return
        d = s["document"]
        header_var.set(
            f"SEF #{d.sef_id} {d.academic_year}/{d.version}    "
            f"Status: {d.status}    Headline: {d.headline_judgement}    "
            f"Sections: {s['section_count']}    "
            f"Evaluated: {s['evaluated']}")
        for sec in s["sections"]:
            t.insert("", "end", iid=str(sec.section_id), values=(
                sec.section_id, sec.section_code, sec.section_title,
                sec.judgement, sec.last_updated_by or "-",
            ))

    def _do_seed() -> None:
        try:
            added = data.init_sections(sid)
        except ValidationError as e:
            messagebox.showerror("SEF Builder", str(e), parent=dlg)
            return
        messagebox.showinfo("SEF Builder",
                            f"Added {added} default section(s).",
                            parent=dlg)
        _refresh()

    def _do_upsert(mode: str | None) -> None:
        initial: dict[str, Any] | None = None
        if mode == "selected":
            sel = t.focus()
            if not sel:
                messagebox.showinfo("SEF Builder",
                                    "Select a section first.",
                                    parent=dlg)
                return
            try:
                existing = data.get_section(int(sel))
            except Exception:
                logger.exception("get_section failed")
                return
            if existing is None:
                return
            initial = {k: getattr(existing, k) for k in (
                "section_code", "section_title", "judgement",
                "strengths", "areas_for_development",
                "evidence", "action_plan", "last_updated_by")}
        fields = _section_dialog(host, sid, initial=initial)
        if not fields:
            return
        try:
            data.upsert_section(fields)
        except ValidationError as e:
            messagebox.showerror("SEF Builder", str(e), parent=dlg)
            return
        _refresh()

    def _do_delete() -> None:
        sel = t.focus()
        if not sel:
            messagebox.showinfo("SEF Builder",
                                "Select a section first.",
                                parent=dlg)
            return
        try:
            sec_id = int(sel)
        except ValueError:
            return
        if not messagebox.askyesno(
                "Delete section",
                f"Delete section #{sec_id}?", parent=dlg):
            return
        data.delete_section(sec_id)
        _refresh()

    t.bind("<Double-1>", lambda _e: _do_upsert("selected"))
    _refresh()
