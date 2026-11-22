"""E-mail from the admissions screens that is actually sent.

Every message goes through ``admissions_comms`` (the outbox), which may
hold it under the current delivery mode; the result shown is the honest
``QueuedMessage.label`` ("Queued (held by delivery mode)", "Sent", …),
never a blanket "sent". Preview / copy stays available.

Referee e-mails go through the reference tracker (``references``), so
there is one reference system.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui import window_sizing
from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    make_toplevel,
    messagebox,
)
from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
)
from education_system.systems.sixth_form.domain.admissions import (
    applicant_reports as reports,
)

from . import applicant_actions as act

logger = logging.getLogger(__name__)


def _comms():
    from education_system.systems.sixth_form.domain.admissions import (
        admissions_comms,
    )
    return admissions_comms


def _refs():
    from education_system.systems.sixth_form.domain.admissions import (
        references,
    )
    return references


class ComposeDialog:
    """Subject + body with Send (through the outbox), Copy and Save.

    *send* is called with ``(subject, body, include_parents)`` and returns
    the queued message(s). When *editable* is False the text is a fixed
    letter (an offer letter) and only the send options change.
    """

    def __init__(self, parent: tk.Misc, applicant_id: str, *, title: str,
                 subject: str, body: str,
                 send: Callable[[str, str, bool], object],
                 editable: bool = True, parents_option: bool = True,
                 on_sent: Callable[[], None] | None = None) -> None:
        self.aid = applicant_id
        self.send_fn = send
        self.on_sent = on_sent
        self.win = make_toplevel(parent)
        self.win.title(title)
        window_sizing.fit(self.win, "820x620", (600, 420))
        a = data.get_applicant(applicant_id)
        # Action bar first so it is never clipped on a short screen.
        bar = ttk.Frame(self.win, padding=(10, 6))
        bar.pack(side="bottom", fill="x")
        self.parents = tk.BooleanVar(value=False)
        if parents_option:
            ttk.Checkbutton(bar, text="Also send to parents/carers who "
                            "receive correspondence",
                            variable=self.parents).pack(side="left")
        self.send_btn = ttk.Button(bar, text="Send", command=self._send)
        self.send_btn.pack(side="right")
        act.gate(self.send_btn, act.can_admissions())
        ttk.Button(bar, text="Close", command=self.win.destroy).pack(
            side="right", padx=6)
        ttk.Button(bar, text="Save…", command=self._save).pack(side="right")
        ttk.Button(bar, text="Copy", command=self._copy).pack(side="right",
                                                              padx=6)
        frm = ttk.Frame(self.win, padding=10)
        frm.pack(fill="both", expand=True)
        to = (a.email if a and a.email else "(no e-mail on file)")
        ttk.Label(frm, text=f"To: {a.full_name if a else applicant_id} "
                  f"<{to}>").pack(anchor="w")
        try:
            from education_system.systems.sixth_form.domain.admissions import (
                applicant_details,
            )
            cc = applicant_details.correspondence_contacts(applicant_id)
            if cc and parents_option:
                ttk.Label(frm, foreground="#555", text="Parents/carers: " + ", ".join(
                    f"{c.name} <{c.email}>" for c in cc)).pack(anchor="w")
        except Exception:  # noqa: BLE001 — display only
            logger.debug("no contacts for %s", applicant_id, exc_info=True)
        ttk.Label(frm, text="Subject:").pack(anchor="w", pady=(6, 0))
        self.subj = ttk.Entry(frm, width=80)
        self.subj.insert(0, subject)
        self.subj.pack(fill="x")
        ttk.Label(frm, text="Message:").pack(anchor="w", pady=(6, 0))
        self.body = tk.Text(frm, wrap="word", height=18)
        self.body.insert("1.0", body)
        self.body.pack(fill="both", expand=True)
        if not editable:
            self.subj.configure(state="readonly")
            self.body.configure(state="disabled")

    def _text(self) -> tuple[str, str]:
        return self.subj.get().strip(), self.body.get("1.0", "end").strip()

    def _copy(self) -> None:
        s, b = self._text()
        self.win.clipboard_clear()
        self.win.clipboard_append(f"Subject: {s}\n\n{b}")
        messagebox.showinfo("Copy", "Copied to the clipboard.",
                            parent=self.win)

    def _save(self) -> None:
        s, b = self._text()
        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension=".txt",
            initialfile=f"email_{self.aid}.txt")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(f"Subject: {s}\n\n{b}\n")
        except OSError as e:
            messagebox.showerror("Save", str(e), parent=self.win)
            return
        messagebox.showinfo("Save", f"Saved to {path}", parent=self.win)

    def _send(self) -> None:
        s, b = self._text()
        ok, msgs = act.attempt(self.win, "Send e-mail", self.send_fn, s, b,
                               self.parents.get())
        if not ok:
            return
        act.show_queued(self.win, "E-mail", msgs)
        if self.on_sent:
            self.on_sent()
        self.win.destroy()


def email_applicant(parent: tk.Misc, applicant_id: str,
                    on_sent: Callable[[], None] | None = None) -> None:
    """The status e-mail for where the application is now (editable)."""
    a = data.get_applicant(applicant_id)
    if a is None:
        return
    ok, rendered = act.attempt(parent, "E-mail",
                               reports.render_status_email, applicant_id)
    if not ok:
        return
    subject, body = rendered
    ComposeDialog(
        parent, applicant_id, title=f"E-mail — {applicant_id}",
        subject=subject, body=body, on_sent=on_sent,
        send=lambda s, b, p: _comms().send_to_applicant(
            applicant_id, s, b, include_parents=p, kind="status"))


def custom_email(parent: tk.Misc, applicant_id: str,
                 on_sent: Callable[[], None] | None = None) -> None:
    a = data.get_applicant(applicant_id)
    if a is None:
        return
    try:
        subject, body = reports.render_status_email(applicant_id)
    except Exception:  # noqa: BLE001 — start from a blank message
        subject, body = "", f"Dear {a.first_name},\n\n"
    ComposeDialog(
        parent, applicant_id, title=f"Custom e-mail — {applicant_id}",
        subject=subject, body=body, on_sent=on_sent,
        send=lambda s, b, p: _comms().send_to_applicant(
            applicant_id, s, b, include_parents=p, kind="custom"))


def offer_letter(parent: tk.Misc, applicant_id: str,
                 on_sent: Callable[[], None] | None = None) -> None:
    """Preview the offer letter; Send e-mails it (with parents if
    ticked)."""
    a = data.get_applicant(applicant_id)
    if a is None or not a.offer_type:
        messagebox.showinfo("Offer letter", "No offer has been made yet.",
                            parent=parent.winfo_toplevel())
        return
    ok, body = act.attempt(parent, "Offer letter",
                           reports.render_offer_letter, applicant_id)
    if not ok:
        return
    ComposeDialog(
        parent, applicant_id, title=f"Offer letter — {applicant_id}",
        subject="Your offer of a place in our Sixth Form", body=body,
        editable=False, on_sent=on_sent,
        send=lambda _s, _b, p: _comms().send_offer_letter(
            applicant_id, include_parents=p))


def expiry_warning(parent: tk.Misc, applicant_id: str,
                   on_sent: Callable[[], None] | None = None) -> None:
    if not messagebox.askyesno(
            "Offer expiry", "E-mail the applicant a reminder that their "
            "offer expires soon?", parent=parent.winfo_toplevel()):
        return
    ok, msgs = act.attempt(parent, "Offer expiry",
                           _comms().send_offer_expiry_warning, applicant_id)
    if ok:
        act.show_queued(parent, "Offer expiry reminder", msgs)
        if on_sent:
            on_sent()


# ── References (one tracker) ───────────────────────────────────────

def _open_reference(parent: tk.Misc, applicant_id: str):
    """The applicant's open tracked reference, starting one from the
    referee on the application when none is tracked yet."""
    refs = _refs()
    open_refs = [r for r in refs.list_references(applicant_id=applicant_id)
                 if r.is_open]
    if len(open_refs) == 1:
        return open_refs[0]
    if len(open_refs) > 1:
        labels = [f"#{r.reference_id} {r.referee_name} ({r.status})"
                  for r in open_refs]
        got = act.pick(parent, "Chase referee", "Which reference?", labels)
        return open_refs[labels.index(got[0])] if got else None
    a = data.get_applicant(applicant_id)
    if a is None or not a.reference_name:
        messagebox.showinfo(
            "Chase referee", "No open reference request and no referee on "
            "the application. Use 'References workflow…' to request one.",
            parent=parent.winfo_toplevel())
        return None
    if not messagebox.askyesno(
            "Chase referee",
            f"No reference is being tracked yet. Start one from the referee "
            f"on the application ({a.reference_name}, "
            f"{a.reference_contact or 'no contact'})?",
            parent=parent.winfo_toplevel()):
        return None
    ok, ref = act.attempt(parent, "Reference", refs.adopt_legacy_reference,
                          applicant_id)
    return ref if ok else None


def chase_referee(parent: tk.Misc, applicant_id: str,
                  on_done: Callable[[], None] | None = None) -> None:
    """E-mail the referee: the request if it has not gone yet, otherwise
    a reminder (recorded as a chase)."""
    ref = _open_reference(parent, applicant_id)
    if ref is not None:
        email_reference(parent, ref.reference_id, on_done)


def email_reference(parent: tk.Misc, reference_id: int,
                    on_done: Callable[[], None] | None = None) -> None:
    """E-mail one tracked reference: the request when not yet sent,
    otherwise a reminder."""
    refs = _refs()
    ref = refs.get_reference(reference_id)
    if ref is None:
        return
    if not ref.is_open:
        messagebox.showinfo("Reference", f"Reference #{reference_id} is "
                            f"{ref.status} — nothing to send.",
                            parent=parent.winfo_toplevel())
        return
    applicant_id = ref.applicant_id
    first = ref.status == "Requested"
    ok, rendered = act.attempt(
        parent, "Chase referee",
        refs.render_request if first else refs.render_chase,
        ref.reference_id)
    if not ok:
        return
    subject, body = rendered
    if not ref.referee_email:
        choice = act.choose_action(
            parent, "Chase referee",
            f"{ref.referee_name} has no e-mail address on the reference, "
            "so it cannot be e-mailed. Record a chase by letter/phone?",
            ["Record chase", "Edit referee…"])
        if choice == "Record chase":
            act.attempt(parent, "Chase referee", refs.chase, ref.reference_id)
        elif choice == "Edit referee…":
            from . import references_views
            references_views.edit_referee(parent, ref.reference_id)
        if on_done:
            on_done()
        return
    send = (_comms().send_reference_request if first
            else _comms().send_reference_chase)
    ComposeDialog(
        parent, applicant_id,
        title=("Reference request" if first else "Reference reminder")
        + f" — {ref.referee_name}",
        subject=subject, body=body, editable=False, parents_option=False,
        on_sent=on_done, send=lambda _s, _b, _p: send(ref.reference_id))


def chase_all(parent: tk.Misc, on_done: Callable[[], None] | None = None
              ) -> None:
    """E-mail every open reference: requests not yet sent go as the
    request, the rest as a reminder. Each failure is reported."""
    refs = _refs()
    ok, rows = act.attempt(parent, "Chase references",
                           refs.list_references, open_only=True)
    if not ok:
        return
    if not rows:
        messagebox.showinfo("Chase references",
                            "No reference requests are outstanding.",
                            parent=parent.winfo_toplevel())
        return
    due = [r for r in rows if r.status == "Requested" or r.chase_due]
    choice = act.choose_action(
        parent, "Chase references",
        f"{len(rows)} reference request(s) are open; {len(due)} have not "
        "been sent yet or are overdue and due a chase.\n\nE-mail which?",
        [f"Due only ({len(due)})", f"All open ({len(rows)})"])
    if choice is None:
        return
    targets = due if choice.startswith("Due") else rows
    sent, failed = [], []
    comms = _comms()
    for r in targets:
        try:
            if r.status == "Requested":
                m = comms.send_reference_request(r.reference_id)
                what = "request"
            else:
                m = comms.send_reference_chase(r.reference_id)
                what = "reminder"
            sent.append(f"#{r.reference_id} {r.applicant_id} "
                        f"{r.referee_name}: {what} — {m.label}")
        except Exception as e:  # noqa: BLE001 — reported per row
            failed.append(f"#{r.reference_id} {r.applicant_id} "
                          f"{r.referee_name}: "
                          f"{act.describe(e).splitlines()[-1]}")
    if on_done:
        on_done()
    lines = [f"E-mailed {len(sent)} of {len(targets)}."]
    if sent:
        lines += ["", *sent]
    if failed:
        lines += ["", f"Not sent ({len(failed)}):", *failed]
    from . import _admissions_ui as ui
    ui.show_text(parent.winfo_toplevel(), "Reference chase", "\n".join(lines))

