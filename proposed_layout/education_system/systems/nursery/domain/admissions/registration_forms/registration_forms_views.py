"""Tkinter views for Registration Forms & Signatures (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Three tabs — the versioned form catalogue, the signatures on file
(with a verify action) and the outstanding-forms chase list — the GUI
counterpart of ``registration_forms_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.admissions.registration_forms import (
    registration_forms as data,
)
from education_system.systems.nursery.domain.admissions.registration_forms.registration_forms import (
    FORM_TYPES,
    SOURCES,
    ValidationError,
)

logger = logging.getLogger(__name__)

_REASON_TEXT = {
    "never-signed": "Never signed",
    "superseded": "Signed an older version",
    "expired": "Needs renewing",
    "declined": "Declined",
}


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        parent = getattr(host, "root", None)
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror(func.__name__, str(e), parent=parent)
            except Exception:
                logger.debug("Could not show validation dialog", exc_info=True)
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=parent)
            except Exception:
                logger.debug("Could not show error dialog", exc_info=True)
    return wrapper


def _clear(host) -> ttk.Frame:
    host._clear_content()
    assert host.content_frame is not None
    return host.content_frame


def _tree(parent: ttk.Frame, spec: list[tuple[str, str, int]],
          height: int = 14) -> ttk.Treeview:
    cols = tuple(c for c, _l, _w in spec)
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=height)
    for c, label, w in spec:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.tag_configure("alert", foreground="#c0392b")
    tree.tag_configure("warn", foreground="#b9770e")
    tree.tag_configure("muted", foreground="#7f8c8d")
    tree.tag_configure("ok", foreground="#1e7e34")
    tree.pack(fill="both", expand=True)
    return tree


def _selected(tree: ttk.Treeview, host, what: str, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Registration forms", f"Select {what} to {verb}.",
                            parent=host.root)
        return None
    return sel


def _pupil_choices() -> list[tuple[str, str]]:
    try:
        return data.list_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        return []


# ── Form dialog (entry / choice / bool / pupil / text) ───────────────────────

def _form_dialog(host, title: str, fields: list[tuple[str, str, str, Any]], *,
                 initial: dict[str, Any] | None = None,
                 geometry: str = "560x520") -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry(geometry)
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    vars_: dict[str, Any] = {}
    pupil_by_label: dict[str, str] = {}
    row = 0
    for key, label, kind, choices in fields:
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw",
                                              pady=2)
        cur = initial.get(key)
        if kind == "pupil":
            pupil_by_label = {lbl: pid for pid, lbl in (choices or [])}
            v = tk.StringVar()
            ttk.Combobox(frm, textvariable=v,
                         values=[lbl for _p, lbl in (choices or [])],
                         state="readonly" if choices else "normal",
                         width=44).grid(row=row, column=1, sticky="ew", pady=2)
        elif kind == "choice":
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Combobox(frm, textvariable=v, values=list(choices or []),
                         width=42).grid(row=row, column=1, sticky="ew", pady=2)
        elif kind == "bool":
            v = tk.BooleanVar(value=bool(cur))
            ttk.Checkbutton(frm, variable=v).grid(row=row, column=1, sticky="w",
                                                  pady=2)
        elif kind == "text":
            v = tk.Text(frm, width=46, height=10, wrap="word")
            if cur:
                v.insert("1.0", str(cur))
            v.grid(row=row, column=1, sticky="ew", pady=2)
            frm.rowconfigure(row, weight=1)
        else:
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Entry(frm, textvariable=v, width=44).grid(
                row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, Any] = {}
        for key, _l, kind, _c in fields:
            v = vars_[key]
            if kind == "text":
                out[key] = v.get("1.0", "end").strip()
            elif kind == "pupil":
                out["pupil_id"] = pupil_by_label.get(
                    (str(v.get()) or "").strip(), "")
            elif isinstance(v, tk.BooleanVar):
                out[key] = bool(v.get())
            else:
                out[key] = (str(v.get()) or "").strip()
        result = out
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right",
                                                              padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


# ── Manager ──────────────────────────────────────────────────────────────────

@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: registration_forms open_manager")
    root = _clear(host)
    ttk.Label(root, text="Registration Forms & Signatures",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 2))
    warn = ttk.Label(root, foreground="#a00", wraplength=900)
    warn.pack(anchor="w", pady=(0, 6))
    _refresh_summary(summary, warn)

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)
    template_tab = ttk.Frame(nb, padding=8)
    signature_tab = ttk.Frame(nb, padding=8)
    gap_tab = ttk.Frame(nb, padding=8)
    nb.add(template_tab, text="Forms & Versions")
    nb.add(signature_tab, text="Signatures")
    nb.add(gap_tab, text="Outstanding")

    _build_template_tab(host, template_tab)
    _build_signature_tab(host, signature_tab)
    _build_gap_tab(host, gap_tab)

    host.status_var.set("Registration forms loaded")


def _refresh_summary(summary: ttk.Label, warn: ttk.Label) -> None:
    try:
        s = data.summary()
    except Exception:
        logger.exception("Could not load forms summary")
        summary.config(text="Could not load — see logs.", foreground="#a00")
        return
    summary.config(
        text=f"Forms: {s['templates']} ({s['active_templates']} active, "
             f"{s['required_forms']} required)   Signatures: {s['signed']} "
             f"signed, {s['declined']} declined, {s['superseded']} superseded")
    if s["outstanding"]:
        reasons = ", ".join(f"{_REASON_TEXT[k].lower()}: {v}" for k, v
                            in s["outstanding_by_reason"].items() if v)
        warn.config(text=f"⚠ {s['outstanding']} outstanding form(s) across "
                         f"{s['children_with_gaps']} child(ren) — {reasons}")
    else:
        warn.config(text="")


# ── Forms & versions tab ─────────────────────────────────────────────────────

def _build_template_tab(host, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Publish Form",
               command=lambda: _add_template(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Revise (new version)",
               command=lambda: _revise(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="View Wording",
               command=lambda: _view_template(host, tree)).pack(side="left",
                                                                padx=2)
    ttk.Button(bar, text="History",
               command=lambda: _history(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Retire",
               command=lambda: _retire(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh_templates(tree)).pack(side="left",
                                                              padx=2)

    tree = _tree(parent, [
        ("id", "ID", 70), ("name", "Name", 250), ("type", "Type", 190),
        ("version", "Version", 70), ("required", "Required", 80),
        ("renew", "Renewal", 80), ("status", "Status", 80),
        ("effective", "Effective from", 110),
    ])
    tree.bind("<Double-1>", lambda _e: _view_template(host, tree))
    _refresh_templates(tree)


def _refresh_templates(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_templates()
    except Exception:
        logger.exception("Could not refresh form templates")
        return
    for t in rows:
        tag = "ok" if t.status == "active" else "muted"
        tree.insert("", "end", iid=t.template_id, tags=(tag,), values=(
            t.template_id, t.name, t.form_type, t.version,
            "Yes" if t.required else "No",
            f"{t.renew_months} months" if t.renew_months else "-",
            t.status, t.effective_from or "-"))


@_safe_view
def _add_template(host) -> None:
    fields = _form_dialog(host, "Publish a Form", [
        ("form_type", "Form type", "choice", FORM_TYPES),
        ("name", "Name", "entry", None),
        ("version", "Version", "entry", None),
        ("required", "Required of every child", "bool", None),
        ("renew_months", "Renew every N months (blank = never)", "entry", None),
        ("body", "Wording being signed", "text", None),
        ("notes", "Notes", "entry", None),
    ], initial={"version": "1.0", "required": True})
    if not fields:
        return
    try:
        t = data.create_template(fields)
    except ValidationError as e:
        messagebox.showerror("Publish form", str(e), parent=host.root)
        return
    host.status_var.set(f"Published {t.label}")
    open_manager(host)


@_safe_view
def _revise(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a form", "revise")
    if not sel:
        return
    old = data.get_template(sel)
    if old is None:
        return
    if not messagebox.askyesno(
            "Revise form",
            f"Issuing a new version of {old.label} retires v{old.version} and "
            "marks every signature against it 'superseded', so parents will "
            "need to re-sign.\n\nContinue?", parent=host.root):
        return
    fields = _form_dialog(host, f"Revise {old.label}", [
        ("body", "New wording", "text", None),
        ("version", "New version (blank = auto)", "entry", None),
        ("notes", "What changed", "entry", None),
    ], initial={"body": old.body})
    if not fields:
        return
    try:
        t = data.revise(sel, fields.get("body", ""),
                        version=fields.get("version") or None,
                        notes=fields.get("notes") or None)
    except ValidationError as e:
        messagebox.showerror("Revise form", str(e), parent=host.root)
        return
    host.status_var.set(f"Issued {t.label}")
    open_manager(host)


@_safe_view
def _view_template(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a form", "view")
    if not sel:
        return
    t = data.get_template(sel)
    if t is None:
        return
    messagebox.showinfo(
        f"{t.label} ({t.form_type})",
        f"Status: {t.status}    Required: {'Yes' if t.required else 'No'}\n"
        f"Effective from: {t.effective_from or '-'}\n"
        f"Wording hash: {t.body_hash[:16]}…\n\n{t.body}",
        parent=host.root)


@_safe_view
def _history(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a form", "show the history of")
    if not sel:
        return
    t = data.get_template(sel)
    if t is None:
        return
    lines = []
    for v in data.version_history(t.form_type):
        marker = "current" if v.status == "active" else v.status
        lines.append(f"v{v.version}  {v.effective_from or '-'}  {marker}"
                     + (f"\n    {v.notes}" if v.notes else ""))
    messagebox.showinfo(f"Version history — {t.form_type}",
                        "\n".join(lines) or "(no versions)", parent=host.root)


@_safe_view
def _retire(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a form", "retire")
    if not sel:
        return
    if not messagebox.askyesno("Retire form",
                               f"Retire {sel}? It will stop being issued.",
                               parent=host.root):
        return
    data.retire_template(sel)
    host.status_var.set(f"Retired {sel}")
    open_manager(host)


# ── Signatures tab ───────────────────────────────────────────────────────────

def _build_signature_tab(host, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Record a Signature",
               command=lambda: _sign(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Verify",
               command=lambda: _verify(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="View",
               command=lambda: _view_submission(host, tree)).pack(side="left",
                                                                  padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_submission(host, tree)).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh_submissions(tree)).pack(side="left",
                                                                padx=2)

    tree = _tree(parent, [
        ("id", "ID", 70), ("child", "Child", 170), ("form", "Form", 190),
        ("version", "Version", 70), ("by", "Signed by", 170),
        ("rel", "Relationship", 120), ("when", "Signed", 110),
        ("source", "Source", 90), ("status", "Status", 90),
    ])
    tree.bind("<Double-1>", lambda _e: _view_submission(host, tree))
    _refresh_submissions(tree)


def _refresh_submissions(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_submissions()
    except Exception:
        logger.exception("Could not refresh signatures")
        return
    for s in rows:
        if s.status == "signed":
            tag = "ok"
        elif s.status == "declined":
            tag = "alert"
        else:
            tag = "muted"
        tree.insert("", "end", iid=s.submission_id, tags=(tag,), values=(
            s.submission_id, s.child_name or s.pupil_id, s.form_type,
            s.template_version, s.signature_name or "-",
            s.respondent_relationship or "-", (s.signed_at or "-")[:10],
            s.source, s.status))


@_safe_view
def _sign(host) -> None:
    choices = data.list_template_choices()
    if not choices:
        messagebox.showinfo("Record a signature",
                            "No active forms to sign — publish one first.",
                            parent=host.root)
        return
    labels = {label: tid for tid, label in choices}
    fields = _form_dialog(host, "Record a Signature", [
        ("pupil_id", "Child", "pupil", _pupil_choices()),
        ("template_label", "Form", "choice", list(labels)),
        ("respondent_name", "Signed by (full name)", "entry", None),
        ("respondent_relationship", "Relationship", "entry", None),
        ("signature_name", "Typed signature (blank = same)", "entry", None),
        ("source", "Source", "choice", SOURCES),
        ("witnessed_by", "Witnessed by (staff ID)", "entry", None),
        ("status", "Outcome", "choice", ("signed", "declined")),
        ("notes", "Notes", "entry", None),
    ], initial={"source": "portal", "status": "signed"}, geometry="560x460")
    if not fields:
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Record a signature", "Please choose a child.",
                             parent=host.root)
        return
    template_id = labels.get(fields.pop("template_label", ""), "")
    if not template_id:
        messagebox.showerror("Record a signature", "Please choose a form.",
                             parent=host.root)
        return
    template = data.get_template(template_id)
    if template is not None and fields.get("status") == "signed":
        if not messagebox.askyesno(
                "Confirm the wording",
                f"{template.label}\n\n{template.body}\n\n"
                "Does the parent agree to this wording?", parent=host.root):
            return
    try:
        s = data.sign({**fields, "template_id": template_id})
    except ValidationError as e:
        messagebox.showerror("Record a signature", str(e), parent=host.root)
        return
    host.status_var.set(
        f"Recorded {s.submission_id} — {s.form_type} v{s.template_version}")
    open_manager(host)


@_safe_view
def _verify(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a signature", "verify")
    if not sel:
        return
    ok, message = data.verify_submission(sel)
    if ok:
        messagebox.showinfo("Signature verified", message, parent=host.root)
    else:
        messagebox.showerror("Signature FAILED verification", message,
                             parent=host.root)


@_safe_view
def _view_submission(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a signature", "view")
    if not sel:
        return
    s = data.get_submission(sel)
    if s is None:
        return
    template = data.get_template(s.template_id)
    lines = [
        f"Child:        {s.child_name or '-'} ({s.pupil_id})",
        f"Form:         {s.form_type} v{s.template_version}",
        f"Signed by:    {s.signature_name or '-'} "
        f"({s.respondent_relationship or '-'})",
        f"When:         {s.signed_at or '-'}",
        f"Source:       {s.source}",
        f"Status:       {s.status}",
        f"Wording hash: {s.body_hash[:16]}…",
        f"Signature:    {(s.signature_hash or '-')[:16]}…",
    ]
    if s.answers:
        lines += ["", "Answers:"] + [f"  {k}: {v}" for k, v in s.answers.items()]
    if template is not None:
        lines += ["", "Wording signed:", template.body]
    messagebox.showinfo(f"Signature {s.submission_id}", "\n".join(lines),
                        parent=host.root)


@_safe_view
def _delete_submission(host, tree: ttk.Treeview) -> None:
    sel = _selected(tree, host, "a signature", "delete")
    if not sel:
        return
    if not messagebox.askyesno(
            "Delete signature",
            f"Delete {sel}? Signed forms are part of the child's statutory "
            "record.", parent=host.root):
        return
    data.delete_submission(sel)
    host.status_var.set(f"Deleted signature {sel}")
    open_manager(host)


# ── Outstanding tab ──────────────────────────────────────────────────────────

def _build_gap_tab(host, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Record a Signature",
               command=lambda: _sign(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh_gaps(tree)).pack(side="left", padx=2)

    tree = _tree(parent, [
        ("child", "Child", 220), ("form", "Form", 230),
        ("version", "Version", 80), ("reason", "Why", 220),
        ("name", "Form name", 250),
    ])
    _refresh_gaps(tree)


def _refresh_gaps(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.all_outstanding()
    except Exception:
        logger.exception("Could not refresh outstanding forms")
        return
    for i, g in enumerate(rows):
        tag = "muted" if g.reason == "declined" else "warn"
        tree.insert("", "end", iid=f"gap-{i}", tags=(tag,), values=(
            g.child_name or g.pupil_id, g.template.form_type,
            f"v{g.template.version}",
            _REASON_TEXT.get(g.reason, g.reason), g.template.name))


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Registration Forms & Signatures",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Registration Forms & Signatures from the "
              "navigation menu.").pack(anchor="w")
    return frame
