"""Tkinter views for the Email / Messaging centre (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Shows the message log with a tree + toolbar, a compose/edit form
dialog, a reader and a send-from-template dialog — the GUI counterpart of
``email_centre_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.nursery_system.modules.domain.email_centre import (
    email_centre as data,
)
from education_system.nursery_system.modules.domain.email_centre import (
    email_templates,
)
from education_system.nursery_system.modules.domain.email_centre.email_centre import (
    CATEGORIES,
    CHANNELS,
    DIRECTIONS,
    PRIORITIES,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)

NURSERY_SYSTEM_KEY = "nursery"


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


# (key, label, kind) — kind drives the widget in the form dialog.
_FIELDS: list[tuple[str, str, str]] = [
    ("direction",    "Direction",          "direction"),
    ("channel",      "Channel",            "channel"),
    ("category",     "Category",           "category"),
    ("priority",     "Priority",           "priority"),
    ("subject",      "Subject",            "entry"),
    ("body",         "Body",               "text"),
    ("to_name",      "To name",            "entry"),
    ("to_address",   "To address",         "entry"),
    ("from_name",    "From name",          "entry"),
    ("from_address", "From address",       "entry"),
    ("pupil_id",     "Child",              "pupil"),
    ("staff_id",     "Staff ID",           "entry"),
    ("status",       "Status",             "status"),
]


def _clear(host) -> ttk.Frame:
    host._clear_content()
    assert host.content_frame is not None
    return host.content_frame


def _header(parent: ttk.Frame, title: str) -> None:
    ttk.Label(parent, text=title, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _pupil_choices() -> list[tuple[str, str]]:
    try:
        return data.list_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        return []


@_safe_view
def open_manager(host) -> None:
    """Unified Email / Messaging screen.

    A notebook with two tabs: the local **Email Centre** (compose / send /
    templates against the nursery's own message log) and **Cross-System Email**
    (the shared inter-system staff messaging panel). They used to be two
    separate menu entries; they are now one feature.
    """
    logger.debug("GUI: email_centre open_manager")
    root = _clear(host)
    _header(root, "Email / Messaging")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)
    email_tab = ttk.Frame(nb, padding=(0, 8, 0, 0))
    cross_tab = ttk.Frame(nb, padding=(0, 8, 0, 0))
    nb.add(email_tab, text="Email Centre")
    nb.add(cross_tab, text="Cross-System Email")

    _build_email_centre(host, email_tab)
    _build_cross_system(host, cross_tab)
    host.status_var.set("Email / Messaging loaded")


def _build_email_centre(host, container: ttk.Frame) -> None:
    """Build (or rebuild in place) the local Email Centre into ``container``.

    Stored on ``host._email_refresh`` so the action handlers can redraw just
    this tab after a compose / send / edit / delete without tearing down the
    surrounding notebook (which would otherwise snap the user back off the
    Cross-System tab)."""
    for w in container.winfo_children():
        w.destroy()
    host._email_refresh = lambda: _build_email_centre(host, container)

    filt = tk.StringVar(value="All")

    bar = ttk.Frame(container)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Compose",
               command=lambda: open_compose(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Open",
               command=lambda: _read_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Send Template",
               command=lambda: open_send_template(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Send Draft",
               command=lambda: _send_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _build_email_centre(host, container)).pack(
                   side="left", padx=2)
    ttk.Label(bar, text="Show:").pack(side="left", padx=(12, 2))
    ttk.Combobox(bar, textvariable=filt, state="readonly", width=12,
                 values=["All", "Outgoing", "Incoming", "Draft", "Sent",
                         "Failed"]).pack(side="left")

    cols = ("id", "dir", "to", "subject", "category", "status", "when")
    tree = ttk.Treeview(container, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 75), ("dir", "Dir", 75), ("to", "To", 200),
        ("subject", "Subject", 220), ("category", "Category", 100),
        ("status", "Status", 80), ("when", "When", 140),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _read_selected(tree, host))

    def _do_refresh(*_a) -> None:
        _refresh(tree, filt.get())
    filt.trace_add("write", _do_refresh)

    _refresh(tree, filt.get())


def _build_cross_system(host, container: ttk.Frame) -> None:
    """Embed the shared cross-system messaging panel into ``container``.

    Lets nursery staff message — and read replies from — staff in the
    University, Sixth Form, Secondary and Primary systems, keyed by ``auth.db``
    user id."""
    ttk.Label(
        container,
        text="Message staff across the University, Sixth Form, Secondary, "
             "Primary and Nursery systems.",
        foreground="#555",
    ).pack(anchor="w", pady=(0, 8))
    try:
        from education_system.shared.messaging.cross_system_panel import (
            CrossSystemMessagePanel,
        )
    except Exception:
        logger.exception("Cross-system messaging panel unavailable")
        ttk.Label(
            container,
            text="Cross-system messaging is unavailable — see logs for details.",
            foreground="#a00",
        ).pack(anchor="w")
        return
    panel = CrossSystemMessagePanel(
        container, auth=host.auth, system_key=NURSERY_SYSTEM_KEY)
    panel.pack(fill="both", expand=True)


def _refresh_email_centre(host) -> None:
    """Redraw the Email Centre tab after a mutating action, if it is open."""
    cb = getattr(host, "_email_refresh", None)
    if cb is not None:
        cb()


def _refresh(tree: ttk.Treeview, filt: str = "All") -> None:
    for i in tree.get_children():
        tree.delete(i)
    direction = filt if filt in ("Outgoing", "Incoming") else None
    status = filt if filt in ("Draft", "Sent", "Failed") else None
    try:
        rows = data.list_messages(direction=direction, status=status)
    except Exception:
        logger.exception("Could not refresh email messages")
        return
    for m in rows:
        to = m.to_address or m.to_name or (m.child_name or "-")
        tree.insert("", "end", iid=m.message_id, values=(
            m.message_id, m.direction, to, m.subject, m.category,
            m.status, m.sent_at or m.created_at or "-"))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Email / Messaging", f"Select a message to {verb}.",
                            parent=host.root)
        return None
    return sel


# ── Reader ───────────────────────────────────────────────────────────────────

def _read_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "open")
    if sel:
        open_reader(host, sel)


@_safe_view
def open_reader(host, message_id: str) -> None:
    m = data.get_message(message_id)
    if m is None:
        messagebox.showerror("Email / Messaging", f"No message {message_id}",
                             parent=host.root)
        return
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Message {m.message_id}")
    dlg.transient(host.root)
    dlg.geometry("560x520")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    meta = [
        ("Subject", m.subject),
        ("Direction", f"{m.direction} · {m.channel} · {m.priority}"),
        ("Category", m.category),
        ("Status", m.status),
        ("From", f"{m.from_name or '-'} <{m.from_address or '-'}>"),
        ("To", f"{m.to_name or '-'} <{m.to_address or '-'}>"),
        ("Child", f"{m.child_name} ({m.pupil_id})" if m.child_name else "-"),
        ("Handled by", f"{m.staff_name} ({m.staff_id})" if m.staff_name else "-"),
        ("Sent at", m.sent_at or "-"),
        ("Created", m.created_at or "-"),
    ]
    for i, (label, val) in enumerate(meta):
        ttk.Label(frm, text=f"{label}:", foreground="#555").grid(
            row=i, column=0, sticky="nw", padx=(0, 10), pady=1)
        ttk.Label(frm, text=val, wraplength=420, justify="left").grid(
            row=i, column=1, sticky="w", pady=1)
    ttk.Separator(frm, orient="horizontal").grid(
        row=len(meta), column=0, columnspan=2, sticky="ew", pady=8)
    body = tk.Text(frm, wrap="word", height=12, width=60)
    body.grid(row=len(meta) + 1, column=0, columnspan=2, sticky="nsew")
    body.insert("1.0", m.body or "(empty)")
    body.config(state="disabled")
    frm.columnconfigure(1, weight=1)
    frm.rowconfigure(len(meta) + 1, weight=1)
    ttk.Button(frm, text="Close", command=dlg.destroy).grid(
        row=len(meta) + 2, column=1, sticky="e", pady=(8, 0))


# ── Compose / edit ───────────────────────────────────────────────────────────

def _recipient_directory() -> list[dict[str, Any]]:
    try:
        return data.recipient_directory()
    except Exception:
        logger.exception("Could not load recipient directory")
        return []


def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None
                 ) -> dict[str, Any] | None:
    """Compose/edit form with a recipient picker that auto-fills the To fields.

    Picking a parent or staff member from the "To" dropdown fills in the To
    name / To address and links the child or staff id, and a chip shows where
    the message routes. The message metadata (direction, channel, category,
    priority, status) lives in a collapsible Advanced section with sensible
    defaults, exactly like the other systems' compose dialog.
    """
    is_edit = bool(initial)
    initial = initial or {}
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("540x640")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    frm.columnconfigure(1, weight=1)

    # Hidden links populated by the recipient picker (or carried from edit).
    pupil_id = tk.StringVar(value=str(initial.get("pupil_id") or ""))
    staff_id = tk.StringVar(value=str(initial.get("staff_id") or ""))

    recips = [] if is_edit else _recipient_directory()
    recip_by_label = {e["label"]: e for e in recips}
    recip_labels = ["(custom — type the To fields below)"] + [
        e["label"] for e in recips]

    r = 0

    def label(text: str) -> None:
        nonlocal r
        ttk.Label(frm, text=text).grid(row=r, column=0, sticky="e",
                                       padx=(0, 6), pady=4)

    # ── Recipient picker ─────────────────────────────────────────────
    label("To:")
    recip_var = tk.StringVar(value=recip_labels[0])
    recip_cb = ttk.Combobox(frm, textvariable=recip_var, values=recip_labels,
                            state="readonly" if recips else "disabled", width=52)
    recip_cb.grid(row=r, column=1, sticky="ew", pady=4)
    r += 1

    chip = ttk.Label(frm, text="", foreground="#2E86AB", font=("", 9, "italic"))
    chip.grid(row=r, column=1, sticky="w", pady=(0, 6))
    r += 1

    label("To name:")
    to_name = tk.StringVar(value=str(initial.get("to_name") or ""))
    ttk.Entry(frm, textvariable=to_name).grid(row=r, column=1, sticky="ew", pady=2)
    r += 1

    label("To address:")
    to_address = tk.StringVar(value=str(initial.get("to_address") or ""))
    ttk.Entry(frm, textvariable=to_address).grid(row=r, column=1, sticky="ew",
                                                 pady=2)
    r += 1

    def _on_recipient(_e=None) -> None:
        entry = recip_by_label.get(recip_var.get())
        if not entry:
            chip.config(text="")
            return
        to_name.set(entry["to_name"])
        to_address.set(entry["to_address"])
        pupil_id.set(entry.get("pupil_id") or "")
        staff_id.set(entry.get("staff_id") or "")
        dest = entry["to_address"] or "no email on file"
        chip.config(text=f"↪ {entry['kind']}: {dest}")
    recip_cb.bind("<<ComboboxSelected>>", _on_recipient)

    label("Subject:")
    subject = tk.StringVar(value=str(initial.get("subject") or ""))
    ttk.Entry(frm, textvariable=subject).grid(row=r, column=1, sticky="ew",
                                              pady=(8, 2))
    r += 1

    label("Body:")
    body = tk.Text(frm, height=9, wrap="word")
    if initial.get("body"):
        body.insert("1.0", str(initial["body"]))
    body.grid(row=r, column=1, sticky="nsew", pady=(2, 4))
    frm.rowconfigure(r, weight=1)
    r += 1

    # ── Advanced (collapsible) ───────────────────────────────────────
    adv_open = tk.BooleanVar(value=is_edit)
    adv_btn = ttk.Button(frm)
    adv_btn.grid(row=r, column=0, columnspan=2, sticky="w", pady=(8, 0))
    r += 1
    adv = ttk.Frame(frm)
    adv.grid(row=r, column=0, columnspan=2, sticky="ew")
    adv.columnconfigure(1, weight=1)
    r += 1

    combos = {
        "direction": list(DIRECTIONS), "channel": list(CHANNELS),
        "category": list(CATEGORIES), "priority": list(PRIORITIES),
        "status": list(STATUSES),
    }
    defaults = {"direction": "Outgoing", "channel": "Email",
                "category": "General", "priority": "Normal", "status": "Draft"}
    adv_vars: dict[str, tk.StringVar] = {}
    for ar, (key, lbl) in enumerate((
        ("direction", "Direction"), ("channel", "Channel"),
        ("category", "Category"), ("priority", "Priority"),
        ("status", "Status"),
    )):
        ttk.Label(adv, text=f"{lbl}:").grid(row=ar, column=0, sticky="e",
                                            padx=(0, 6), pady=2)
        v = tk.StringVar(value=str(initial.get(key) or defaults[key]))
        ttk.Combobox(adv, textvariable=v, values=combos[key], state="readonly",
                     width=22).grid(row=ar, column=1, sticky="w", pady=2)
        adv_vars[key] = v
    # Optional From name/address, also advanced.
    from_name = tk.StringVar(value=str(initial.get("from_name") or ""))
    from_address = tk.StringVar(value=str(initial.get("from_address") or ""))
    for ar, (var, lbl) in enumerate((
        (from_name, "From name"), (from_address, "From address"),
    ), start=5):
        ttk.Label(adv, text=f"{lbl}:").grid(row=ar, column=0, sticky="e",
                                            padx=(0, 6), pady=2)
        ttk.Entry(adv, textvariable=var, width=24).grid(
            row=ar, column=1, sticky="ew", pady=2)

    def _toggle_advanced() -> None:
        if adv_open.get():
            adv.grid_remove()
            adv_btn.config(text="▸ Advanced options")
            adv_open.set(False)
        else:
            adv.grid()
            adv_btn.config(text="▾ Advanced options")
            adv_open.set(True)
    adv_btn.config(command=_toggle_advanced)
    # Initialise collapsed/expanded state.
    if not adv_open.get():
        adv.grid_remove()
        adv_btn.config(text="▸ Advanced options")
    else:
        adv_btn.config(text="▾ Advanced options")

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "subject": subject.get().strip(),
            "body": body.get("1.0", "end").strip(),
            "to_name": to_name.get().strip(),
            "to_address": to_address.get().strip(),
            "from_name": from_name.get().strip(),
            "from_address": from_address.get().strip(),
            "pupil_id": pupil_id.get().strip(),
            "staff_id": staff_id.get().strip(),
            **{k: v.get().strip() for k, v in adv_vars.items()},
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=r, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_compose(host) -> None:
    fields = _form_dialog(host, "Compose message")
    if not fields:
        host.status_var.set("Compose cancelled")
        return
    try:
        m = data.create_message(fields)
    except ValidationError as e:
        messagebox.showerror("Compose", str(e), parent=host.root)
        return
    host.status_var.set(f"Created message {m.message_id}")
    if m.status != "Sent" and m.direction == "Outgoing" and \
            messagebox.askyesno("Send now?",
                                f"Message {m.message_id} saved as a draft. "
                                "Send it now?", parent=host.root):
        data.send_message(m.message_id)
        host.status_var.set(f"Sent message {m.message_id}")
    _refresh_email_centre(host)


def _edit_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "edit")
    if sel:
        open_edit(host, sel)


@_safe_view
def open_edit(host, message_id: str) -> None:
    m = data.get_message(message_id)
    if m is None:
        messagebox.showerror("Edit", f"No message {message_id}", parent=host.root)
        return
    initial = {key: getattr(m, key) for key, _l, _k in _FIELDS}
    fields = _form_dialog(host, f"Edit {m.message_id}", initial=initial)
    if not fields:
        return
    try:
        data.update_message(message_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated message {message_id}")
    _refresh_email_centre(host)


def _send_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "send")
    if not sel:
        return
    try:
        m = data.send_message(sel)
    except ValidationError as e:
        messagebox.showerror("Send", str(e), parent=host.root)
        return
    host.status_var.set(f"Sent message {m.message_id}")
    _refresh_email_centre(host)


def _delete_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "delete")
    if not sel:
        return
    if not messagebox.askyesno("Delete message", f"Delete message {sel}?",
                               parent=host.root):
        return
    try:
        data.delete_message(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete email message %s", sel)
        messagebox.showerror("Delete message", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    host.status_var.set(f"Deleted message {sel}")
    _refresh_email_centre(host)


# ── Send from template ───────────────────────────────────────────────────────

@_safe_view
def open_send_template(host) -> None:
    names = email_templates.list_templates()
    if not names:
        messagebox.showinfo("Send Template", "No templates are available.",
                            parent=host.root)
        return
    dlg = tk.Toplevel(host.root)
    dlg.title("Send from template")
    dlg.transient(host.root)
    dlg.geometry("500x520")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    tpl = tk.StringVar(value=names[0])
    to_name = tk.StringVar()
    to_address = tk.StringVar()
    pupil_choices = _pupil_choices()
    pupil_id_by_label = {lbl: pid for pid, lbl in pupil_choices}
    pupil = tk.StringVar()

    grid = ttk.Frame(frm)
    grid.pack(fill="x")
    rows = [
        ("Template", ttk.Combobox(grid, textvariable=tpl, values=names,
                                  state="readonly", width=34)),
        ("To name", ttk.Entry(grid, textvariable=to_name, width=36)),
        ("To address", ttk.Entry(grid, textvariable=to_address, width=36)),
        ("Child", ttk.Combobox(grid, textvariable=pupil,
                               values=[""] + [lbl for _i, lbl in pupil_choices],
                               state="readonly" if pupil_choices else "normal",
                               width=34)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(grid, text=f"{label}:").grid(row=i, column=0, sticky="w", pady=3)
        widget.grid(row=i, column=1, sticky="ew", pady=3)
    grid.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Context (one key=value per line, fills {{tokens}}):",
              foreground="#555").pack(anchor="w", pady=(10, 2))
    ctx = tk.Text(frm, height=8, width=52, wrap="none")
    ctx.pack(fill="both", expand=True)
    ctx.insert("1.0", "setting_name=Sunbeam Nursery\nfirst_name=\nparent_name=\n")

    def _prefill_from_child(*_a) -> None:
        pid = pupil_id_by_label.get(pupil.get())
        if not pid:
            return
        name, email = data.pupil_parent_email(pid)
        if email and not to_address.get():
            to_address.set(email)
        if name and not to_name.get():
            to_name.set(name)
    pupil.trace_add("write", _prefill_from_child)

    def _go() -> None:
        context: dict[str, str] = {}
        for line in ctx.get("1.0", "end").splitlines():
            line = line.strip()
            if line and "=" in line:
                k, _, v = line.partition("=")
                context[k.strip()] = v.strip()
        pid = pupil_id_by_label.get(pupil.get()) or None
        try:
            m = email_templates.send_from_template(
                tpl.get(), context,
                to_name=to_name.get().strip() or None,
                to_address=to_address.get().strip() or None,
                pupil_id=pid)
        except (ValidationError, email_templates.TemplateError) as e:
            messagebox.showerror("Send Template", str(e), parent=dlg)
            return
        host.status_var.set(f"Sent template as {m.message_id}")
        messagebox.showinfo("Template sent",
                            f"Sent '{tpl.get()}' as {m.message_id}.", parent=dlg)
        dlg.destroy()
        _refresh_email_centre(host)

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Send", command=_go).pack(side="right")
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(
        side="right", padx=(0, 8))


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Email / Messaging", font=("", 14, "bold")).pack(
        anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Email / Messaging from the navigation menu.").pack(
        anchor="w")
    return frame
