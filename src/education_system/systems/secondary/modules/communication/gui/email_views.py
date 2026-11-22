"""E-mail screens: the outbox page, a message's details and the compose window.

Delivery runs on a background thread (``tk_threads``) so a slow mail server
never freezes the window; results come back to the Tk thread through ``ui``.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui import tk_threads, window_sizing
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel, messagebox
from education_system.systems.secondary.modules.communication.domain import email_outbox as E
from education_system.systems.secondary.core.permissions import access
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log

logger = logging.getLogger(__name__)

_MODE_COLOURS = {"inbox_only": "#555", "sandbox": "#a60", "live": "#060"}


def _mode_banner(parent: tk.Misc) -> ttk.Label:
    mode = E.delivery_mode()
    return ttk.Label(parent, text="Delivery: " + E.MODE_DESCRIPTIONS.get(mode, mode),
                     foreground=_MODE_COLOURS.get(mode, "#555"))


def deliver_in_background(widget: tk.Misc, message_id: int, principal: Principal,
                          done: Callable[[E.DeliveryReport | None, str | None], None]) -> None:
    """Deliver *message_id* off the Tk thread, then call ``done(report, error)``."""
    def work() -> None:
        try:
            report = E.deliver(message_id, principal=principal)
        except Exception as e:  # noqa: BLE001
            logger.exception("E-mail delivery failed")
            tk_threads.ui(widget, done, None, str(e))
            return
        tk_threads.ui(widget, done, report, None)

    tk_threads.start_thread(widget, work, name="secondary-email-deliver")


def _report_text(report: E.DeliveryReport) -> str:
    return ", ".join(f"{n} {E.STATUS_LABELS[s].lower()}" for s, n in report.counts.items()) \
        or "nothing to deliver"


# ── Outbox ───────────────────────────────────────────────────────────

def draw_outbox(parent: ttk.Frame, *, principal: Principal,
                open_message: Callable[[int], None]) -> None:
    head = ttk.Frame(parent)
    head.pack(fill="x", pady=(0, 6))
    ttk.Label(head, text="Email", font=("", 16, "bold")).pack(side="left")
    _mode_banner(parent).pack(anchor="w", pady=(0, 6))
    scope = ("All messages sent from the school." if principal.role in access.EMAIL_ADMINS
             else "Messages you have sent.")
    ttk.Label(parent, text=scope, foreground="#666").pack(anchor="w", pady=(0, 6))

    cols = (("id", "No.", 50), ("when", "Sent", 140), ("by", "From", 100),
            ("subject", "Subject", 280), ("to", "To", 220), ("status", "Status", 260))
    table = ttk.Frame(parent)
    table.pack(fill="both", expand=True)
    tree = ttk.Treeview(table, columns=[c for c, _h, _w in cols], show="headings",
                        selectmode="browse", height=16)
    for col, heading, width in cols:
        tree.heading(col, text=heading)
        tree.column(col, width=width, anchor="w", stretch=col in {"subject", "status"})
    sb = ttk.Scrollbar(table, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    empty = ttk.Label(parent, text="", foreground="#888")
    empty.pack(anchor="w", pady=(4, 0))

    def refresh() -> None:
        tree.delete(*tree.get_children())
        try:
            msgs = E.list_messages(actor=principal)
        except Exception as e:  # noqa: BLE001
            logger.exception("Outbox load failed")
            empty.configure(text=f"Couldn't load messages: {e}", foreground="#a00")
            return
        for m in msgs:
            tree.insert("", "end", iid=str(m.message_id), values=(
                m.message_id, m.created_at, m.sender_username, m.subject, m.audience_label,
                m.status_text or "—"))
        empty.configure(text="" if msgs else "No messages yet. Use New email to write one.")
        activity_log.record("email.list", results=len(msgs))

    def view(_e=None) -> None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Email", "Select a message first.", parent=parent)
            return
        open_message(int(sel[0]))

    def compose() -> None:
        open_compose(parent, principal=principal, on_sent=lambda _mid: refresh())

    tree.bind("<Double-1>", view)
    tree.bind("<Return>", view)
    ttk.Button(head, text="Refresh", command=refresh).pack(side="right")
    ttk.Button(head, text="Open", command=view).pack(side="right", padx=4)
    ttk.Button(head, text="✉ New email", command=compose).pack(side="right")
    refresh()


def draw_message(parent: ttk.Frame, message_id: int, *, principal: Principal,
                 on_back: Callable[[], None], on_changed: Callable[[], None]) -> None:
    try:
        msg, recipients = E.get_message(message_id, actor=principal)
    except (E.PermissionDenied, E.NotFound) as e:
        ttk.Label(parent, text=str(e), foreground="#a00").pack(anchor="w")
        ttk.Button(parent, text="← Back to Email", command=on_back).pack(anchor="w", pady=6)
        return
    head = ttk.Frame(parent)
    head.pack(fill="x", pady=(0, 6))
    ttk.Label(head, text=msg.subject, font=("", 15, "bold")).pack(side="left")
    ttk.Button(head, text="← Back to Email", command=on_back).pack(side="right")
    retryable = [r for r in recipients
                 if r["status"] == "failed" and r["attempts"] < E.MAX_ATTEMPTS]
    if retryable:
        def retry() -> None:
            n = E.retry_failed(message_id, actor=principal)
            if not n:
                return
            btn.configure(state="disabled", text="Retrying…")
            deliver_in_background(parent, message_id, principal,
                                  lambda report, err: _after_retry(report, err))

        def _after_retry(report, err) -> None:
            if err:
                messagebox.showerror("Email", f"Delivery failed:\n{err}", parent=parent)
            else:
                messagebox.showinfo("Email", "Retry finished: " + _report_text(report),
                                    parent=parent)
            on_changed()

        btn = ttk.Button(head, text=f"Retry {len(retryable)} failed", command=retry)
        btn.pack(side="right", padx=6)

    info = ttk.Frame(parent)
    info.pack(fill="x")
    for r, (k, v) in enumerate((("From", msg.sender_username), ("Sent", msg.created_at),
                                ("To", msg.audience_label), ("Status", msg.status_text))):
        ttk.Label(info, text=f"{k}:", foreground="#555").grid(row=r, column=0, sticky="w",
                                                               padx=(0, 10))
        ttk.Label(info, text=v or "—").grid(row=r, column=1, sticky="w")
    body = tk.Text(parent, height=10, wrap="word")
    body.insert("1.0", msg.body)
    body.configure(state="disabled")
    body.pack(fill="x", pady=8)

    box = ttk.LabelFrame(parent, text=f"Recipients ({len(recipients)})", padding=6)
    box.pack(fill="both", expand=True)
    cols = (("name", "Name", 150), ("address", "Address", 220), ("pupil", "Pupil", 90),
            ("status", "Status", 170), ("tries", "Tries", 50), ("error", "Problem", 260))
    tree = ttk.Treeview(box, columns=[c for c, _h, _w in cols], show="headings", height=10)
    for col, heading, width in cols:
        tree.heading(col, text=heading)
        tree.column(col, width=width, anchor="w", stretch=col == "error")
    sb = ttk.Scrollbar(box, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    for r in recipients:
        tree.insert("", "end", values=(r["display_name"] or "", r["address"],
                                       r["admission_no"] or "—",
                                       E.STATUS_LABELS.get(r["status"], r["status"]),
                                       r["attempts"], r["last_error"] or ""))


# ── Compose ──────────────────────────────────────────────────────────

def open_compose(parent: tk.Misc, *, principal: Principal,
                 on_sent: Callable[[int], None], pupil_ids: list[int] | None = None) -> None:
    """The New email window. *pupil_ids* pre-selects pupils (e.g. from a profile)."""
    activity_log.record("email.compose.open", preselected=len(pupil_ids or []) or None)
    win = make_toplevel(parent.winfo_toplevel())
    win.title("New email")
    window_sizing.fit(win, "900x760", (760, 600))
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    frm.columnconfigure(1, weight=1)
    _mode_banner(frm).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

    # Audience
    aud = ttk.LabelFrame(frm, text="To", padding=8)
    aud.grid(row=1, column=0, columnspan=2, sticky="nsew")
    aud.columnconfigure(0, weight=1)
    aud.columnconfigure(2, weight=1)
    kind = tk.StringVar(value="pupils")
    radios = ttk.Frame(aud)
    radios.grid(row=0, column=0, columnspan=3, sticky="w")
    bulk_state = "normal" if principal.can_email_bulk else "disabled"
    for text, value, state in (("Contacts of chosen pupils", "pupils", "normal"),
                               ("A form group", "form", bulk_state),
                               ("A year group", "year", bulk_state),
                               ("Whole school", "school", bulk_state),
                               ("Only the addresses below", "none", "normal")):
        ttk.Radiobutton(radios, text=text, value=value, variable=kind, state=state,
                        command=lambda: sync()).pack(side="left", padx=(0, 10))
    if not principal.can_email_bulk:
        ttk.Label(aud, text="E-mailing a whole form, year or the school needs an "
                            "administrator account.", foreground="#888").grid(
            row=1, column=0, columnspan=3, sticky="w")

    pick = ttk.Frame(aud)
    pick.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(6, 0))
    pick.columnconfigure(0, weight=1)
    pick.columnconfigure(2, weight=1)
    search_var = tk.StringVar()
    ttk.Label(pick, text="Find pupils").grid(row=0, column=0, sticky="w")
    ttk.Label(pick, text="Chosen").grid(row=0, column=2, sticky="w")
    search = ttk.Entry(pick, textvariable=search_var)
    search.grid(row=1, column=0, sticky="ew")
    found = tk.Listbox(pick, height=6, selectmode="extended", exportselection=False)
    found.grid(row=2, column=0, sticky="nsew")
    chosen = tk.Listbox(pick, height=7, selectmode="extended", exportselection=False)
    chosen.grid(row=1, column=2, rowspan=2, sticky="nsew")
    mid = ttk.Frame(pick)
    mid.grid(row=1, column=1, rowspan=2, padx=6)
    found_ids: list[int] = []
    chosen_ids: list[int] = []

    def label_for(p: P.Pupil) -> str:
        return (f"{p.display_name} · {p.admission_no} · Y{p.year_group}"
                f"{' ' + p.form_group if p.form_group else ''}")

    def do_search(*_a) -> None:
        found.delete(0, "end")
        found_ids.clear()
        text = search_var.get().strip()
        if not text:
            return
        for p in P.list_pupils(search=text)[:100]:
            found_ids.append(p.pupil_id)
            found.insert("end", label_for(p))

    def add_chosen(_e=None) -> None:
        for i in found.curselection():
            pid = found_ids[i]
            if pid not in chosen_ids:
                chosen_ids.append(pid)
                p = P.get_pupil(pid)
                chosen.insert("end", label_for(p) if p else f"Pupil {pid}")
        refresh_count()

    def remove_chosen() -> None:
        for i in reversed(chosen.curselection()):
            chosen.delete(i)
            del chosen_ids[i]
        refresh_count()

    for pid in pupil_ids or []:
        p = P.get_pupil(pid)
        if p and pid not in chosen_ids:
            chosen_ids.append(pid)
            chosen.insert("end", label_for(p))
    search_var.trace_add("write", do_search)
    found.bind("<Double-1>", add_chosen)
    ttk.Button(mid, text="Add →", command=add_chosen).pack(pady=2)
    ttk.Button(mid, text="← Remove", command=remove_chosen).pack(pady=2)

    group = ttk.Frame(aud)
    group.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))
    form_var = tk.StringVar()
    year_var = tk.StringVar()
    ttk.Label(group, text="Form group").pack(side="left")
    form_box = ttk.Combobox(group, textvariable=form_var, state="readonly", width=10,
                            values=P.form_groups_in_use())
    form_box.pack(side="left", padx=(4, 16))
    ttk.Label(group, text="Year group").pack(side="left")
    year_box = ttk.Combobox(group, textvariable=year_var, state="readonly", width=6,
                            values=[str(y) for y in P.YEAR_GROUPS])
    year_box.pack(side="left", padx=4)

    extra_var = tk.StringVar()
    ttk.Label(aud, text="Other addresses (separate with commas)").grid(
        row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))
    ttk.Entry(aud, textvariable=extra_var).grid(row=5, column=0, columnspan=3, sticky="ew")
    count_var = tk.StringVar()
    ttk.Label(aud, textvariable=count_var, foreground="#555", wraplength=820,
              justify="left").grid(row=6, column=0, columnspan=3, sticky="w", pady=(6, 0))

    # Message
    ttk.Label(frm, text="Subject").grid(row=2, column=0, sticky="w", pady=(10, 2))
    subject_var = tk.StringVar()
    ttk.Entry(frm, textvariable=subject_var).grid(row=2, column=1, sticky="ew", pady=(10, 2))
    body = tk.Text(frm, height=12, wrap="word", undo=True)
    body.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=4)
    frm.rowconfigure(3, weight=1)
    ph = ttk.Frame(frm)
    ph.grid(row=4, column=0, columnspan=2, sticky="w")
    ttk.Label(ph, text="Insert:", foreground="#555").pack(side="left")
    for key, desc in E.PLACEHOLDERS.items():
        b = ttk.Button(ph, text="{" + key + "}",
                       command=lambda k=key: (body.insert("insert", "{" + k + "}"),
                                              body.focus_set()))
        b.pack(side="left", padx=2)
        _tooltip(b, desc)

    def audience() -> E.Audience:
        k = kind.get()
        year = int(year_var.get()) if year_var.get().isdigit() else None
        return E.Audience(kind=k, pupil_ids=list(chosen_ids) if k == "pupils" else [],
                          form_group=form_var.get() or None, year_group=year,
                          extra_addresses=E.parse_addresses(extra_var.get()))

    def refresh_count(*_a) -> None:
        try:
            r = E.resolve(audience())
        except Exception as e:  # noqa: BLE001
            count_var.set(str(e))
            return
        text = f"Will go to {len(r.recipients)} address{'es' if len(r.recipients) != 1 else ''}"
        if r.pupils:
            text += f" for {r.pupils} pupil{'s' if r.pupils != 1 else ''}"
        if r.pupils_without_email:
            names = ", ".join(p.display_name for p in r.pupils_without_email[:5])
            more = len(r.pupils_without_email) - 5
            text += (f". {len(r.pupils_without_email)} pupil(s) have no contact who accepts "
                     f"e-mail: {names}{f' and {more} more' if more > 0 else ''}")
        if r.invalid_addresses:
            text += ". Not valid: " + ", ".join(r.invalid_addresses)
        count_var.set(text + ".")

    def sync() -> None:
        k = kind.get()
        state = "normal" if k == "pupils" else "disabled"
        for w in (search, found, chosen):
            w.configure(state=state)
        form_box.configure(state="readonly" if k == "form" else "disabled")
        year_box.configure(state="readonly" if k == "year" else "disabled")
        refresh_count()

    form_var.trace_add("write", refresh_count)
    year_var.trace_add("write", refresh_count)
    extra_var.trace_add("write", refresh_count)

    sending = {"busy": False}

    def send() -> None:
        if sending["busy"]:
            return
        aud_ = audience()
        try:
            n = len(E.resolve(aud_).recipients)
        except Exception:  # noqa: BLE001
            n = 0
        mode = E.delivery_mode()
        note = {"inbox_only": "\n\nDelivery is set to inbox only, so it will be saved "
                              "but not sent.",
                "sandbox": "\n\nDelivery is set to sandbox, so it will be written to "
                           "files, not sent."}.get(mode, "")
        if n and not messagebox.askyesno("Send email", f"Send this email to {n} "
                                         f"address{'es' if n != 1 else ''}?{note}", parent=win):
            activity_log.record("email.send", outcome="cancelled", audience=aud_.kind,
                                recipients=n)
            return
        try:
            result = E.send_message(subject_var.get(), body.get("1.0", "end"), aud_,
                                    actor=principal)
        except (E.ValidationError, E.PermissionDenied) as e:
            messagebox.showerror("Email", str(e), parent=win)
            return
        except Exception as e:  # noqa: BLE001
            logger.exception("Saving e-mail failed")
            messagebox.showerror("Email", f"Could not save the email:\n{e}", parent=win)
            return
        sending["busy"] = True
        send_btn.configure(state="disabled", text="Sending…")
        win.protocol("WM_DELETE_WINDOW", lambda: None)

        def done(report, err) -> None:
            sending["busy"] = False
            owner = parent.winfo_toplevel()
            try:
                win.destroy()
            except tk.TclError:
                pass
            if err:
                messagebox.showerror("Email", f"The email was saved (no. {result.message_id}) "
                                              f"but delivery failed:\n{err}\n\nOpen it in "
                                              "Email to retry.", parent=owner)
            else:
                messagebox.showinfo("Email", f"Email no. {result.message_id}: "
                                             f"{_report_text(report)}.", parent=owner)
            on_sent(result.message_id)

        deliver_in_background(win, result.message_id, principal, done)

    def cancel() -> None:
        if sending["busy"]:
            return
        if body.get("1.0", "end").strip() and not messagebox.askyesno(
                "Discard email", "Discard this email without sending it?", parent=win):
            return
        activity_log.record("email.compose.cancel")
        win.destroy()

    bar = ttk.Frame(frm)
    bar.grid(row=5, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="Cancel", command=cancel).pack(side="right")
    send_btn = ttk.Button(bar, text="Send", command=send)
    send_btn.pack(side="right", padx=(0, 6))
    win.protocol("WM_DELETE_WINDOW", cancel)
    sync()
    search.focus_set()


def _tooltip(widget: tk.Misc, text: str) -> None:
    tip: dict = {"w": None}

    def show(_e) -> None:
        if tip["w"] is not None:
            return
        w = tk.Toplevel(widget)
        w.wm_overrideredirect(True)
        w.geometry(f"+{widget.winfo_rootx()}+{widget.winfo_rooty() + widget.winfo_height()}")
        tk.Label(w, text=text, background="#ffffe0", relief="solid", borderwidth=1,
                 padx=4).pack()
        tip["w"] = w

    def hide(_e) -> None:
        if tip["w"] is not None:
            tip["w"].destroy()
            tip["w"] = None

    widget.bind("<Enter>", show, add="+")
    widget.bind("<Leave>", hide, add="+")
