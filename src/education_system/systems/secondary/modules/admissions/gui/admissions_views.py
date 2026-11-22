"""Admissions screens: the applications list, one application with its
actions and history, the application form, Places (PAN) and allocation.

The rules all live in :mod:`modules.admissions.domain.admissions`; these screens collect input,
show results, and deliver the parent e-mails off the Tk thread.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui import window_sizing
from education_system.platform.delivery.gui.date_picker import DatePicker, recent_years
from education_system.platform.delivery.gui.parented_dialogs import (
    make_toplevel,
    messagebox,
    simpledialog,
)
from education_system.systems.secondary.modules.communication.gui import email_views
from education_system.systems.secondary.modules.admissions.domain import admissions as A
from education_system.systems.secondary.modules.pupils.gui.pupils_views import _debounced_logger
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.layouts.scroll import scrolled_form

logger = logging.getLogger(__name__)

_ALL = "All"
_OPEN = "Open"
_STATUS_FILTER = [_OPEN, _ALL] + list(A.STATUS_LABELS.values())
_STATUS_BY_LABEL = {v: k for k, v in A.STATUS_LABELS.items()}
_LOOKED_AFTER_BY_LABEL = {v: k for k, v in A.LOOKED_AFTER.items()}
_ROUTE_BY_LABEL = {v: k for k, v in A.ROUTES.items()}
_SEN_LABELS = {k: f"{k} - {v}" for k, v in P.SEN_STATUSES.items()}


# ── Running an action ────────────────────────────────────────────────

def _deliver_then(owner: tk.Misc, principal: Principal, title: str, text: str,
                  notes: list[str], has_mail: bool, after: Callable[[], None]) -> None:
    """Deliver queued e-mail (if any) in the background, then report and refresh."""
    extra = [n for n in notes if n and not n.startswith("e-mail to parent queued")]

    def finish(report, err) -> None:
        lines = [text]
        if err:
            lines.append(f"E-mail delivery failed: {err}")
        elif report is not None and report.counts:
            lines.append("E-mail: " + email_views._report_text(report) + ".")
        lines += [f"Note: {n}" for n in extra]
        messagebox.showinfo(title, "\n\n".join(lines), parent=owner)
        after()

    if has_mail:
        email_views.deliver_in_background(owner, None, principal, finish)  # type: ignore[arg-type]
    else:
        finish(None, None)


def _run(owner: tk.Misc, principal: Principal, title: str, fn: Callable[[], A.Outcome],
         done_text: Callable[[A.Outcome], str], after: Callable[[], None]) -> None:
    try:
        outcome = fn()
    except (A.ValidationError, A.PermissionDenied, A.NotFound) as e:
        messagebox.showerror(title, str(e), parent=owner)
        return
    except Exception as e:  # noqa: BLE001
        logger.exception("Admissions action failed")
        messagebox.showerror(title, f"Something went wrong:\n{e}", parent=owner)
        return
    _deliver_then(owner, principal, title, done_text(outcome), outcome.notes,
                  bool(outcome.message_ids), after)


# ── List ─────────────────────────────────────────────────────────────

_COLUMNS = (
    ("ref", "Ref", 80), ("name", "Child", 170), ("year", "Year", 70), ("yg", "Yr", 35),
    ("route", "Route", 110), ("criterion", "Priority", 190), ("distance", "km", 50),
    ("received", "Received", 90), ("status", "Status", 110),
)


def draw_admissions(parent: ttk.Frame, *, principal: Principal,
                    open_application: Callable[[int], None],
                    state: dict | None = None) -> None:
    """The applications page. *state* keeps the filters across redraws."""
    state = state if state is not None else {}
    head = ttk.Frame(parent)
    head.pack(fill="x", pady=(0, 6))
    ttk.Label(head, text="Admissions", font=("", 16, "bold")).pack(side="left")

    filters = ttk.Frame(parent)
    filters.pack(fill="x", pady=(0, 6))
    year_var = tk.StringVar(value=state.get("year", A.next_academic_year()))
    group_var = tk.StringVar(value=state.get("group", "7"))
    status_var = tk.StringVar(value=state.get("status", _OPEN))
    search_var = tk.StringVar(value=state.get("search", ""))
    ttk.Label(filters, text="Year").pack(side="left")
    ttk.Combobox(filters, textvariable=year_var, values=A.academic_year_choices(),
                 state="readonly", width=8).pack(side="left", padx=(4, 12))
    ttk.Label(filters, text="Year group").pack(side="left")
    ttk.Combobox(filters, textvariable=group_var,
                 values=[_ALL] + [str(y) for y in P.YEAR_GROUPS],
                 state="readonly", width=5).pack(side="left", padx=(4, 12))
    ttk.Label(filters, text="Status").pack(side="left")
    ttk.Combobox(filters, textvariable=status_var, values=_STATUS_FILTER,
                 state="readonly", width=16).pack(side="left", padx=(4, 12))
    ttk.Label(filters, text="Search").pack(side="left")
    ttk.Entry(filters, textvariable=search_var, width=22).pack(side="left", padx=4)

    places_var = tk.StringVar()
    places_label = ttk.Label(parent, textvariable=places_var, font=("", 10, "bold"))
    places_label.pack(anchor="w", pady=(0, 4))

    table = ttk.Frame(parent)
    table.pack(fill="both", expand=True)
    tree = ttk.Treeview(table, columns=[c for c, _h, _w in _COLUMNS], show="headings",
                        selectmode="browse", height=16)
    for col, heading, width in _COLUMNS:
        tree.heading(col, text=heading)
        tree.column(col, width=width, anchor="w", stretch=col in {"name", "criterion"})
    sb = ttk.Scrollbar(table, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    count_var = tk.StringVar()
    ttk.Label(parent, textvariable=count_var, foreground="#666").pack(anchor="w", pady=(4, 0))
    log_list = _debounced_logger(tree)

    def group() -> int | None:
        return int(group_var.get()) if group_var.get().isdigit() else None

    def refresh(*_a) -> None:
        state.update(year=year_var.get(), group=group_var.get(), status=status_var.get(),
                     search=search_var.get())
        status = status_var.get()
        tree.delete(*tree.get_children())
        try:
            rows = A.list_applications(
                academic_year=year_var.get() or None, year_group=group(),
                status=_STATUS_BY_LABEL.get(status), search=search_var.get().strip() or None,
                open_only=status == _OPEN)
        except Exception as e:  # noqa: BLE001
            logger.exception("Loading applications failed")
            count_var.set(f"Couldn't load applications: {e}")
            return
        for a in rows:
            tree.insert("", "end", iid=str(a.application_id), values=(
                a.reference, a.child_name, a.academic_year, a.year_group, a.route_label,
                a.criterion_label, "" if a.distance_km is None else f"{a.distance_km:g}",
                a.received_date, a.status_label))
        count_var.set(f"{len(rows)} application{'s' if len(rows) != 1 else ''}"
                      " · listed in oversubscription order")
        if group():
            p = A.places(year_var.get(), group())
            if p.pan is None:
                places_var.set(f"Year {group()} {year_var.get()}: no admission number set "
                               "- use Places")
                places_label.configure(foreground="#a60")
            else:
                extra = f" · {p.on_roll} on roll" if p.on_roll else ""
                over = f" · over by {p.over_by}" if p.over_by else ""
                places_var.set(f"Year {group()} {year_var.get()}: admission number {p.pan}"
                               f" · {p.offered} offered · {p.accepted} accepted{extra} · "
                               f"{p.available} available{over}")
                places_label.configure(foreground="#060" if p.available else "#a00")
        else:
            places_var.set("Choose a year group to see places")
            places_label.configure(foreground="#666")
        log_list("admission.list", year=year_var.get(), year_group=group(), status=status,
                 searched=bool(search_var.get().strip()) or None, results=len(rows))

    def selected() -> int | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Admissions", "Select an application first.", parent=parent)
            return None
        return int(sel[0])

    def view(_e=None) -> None:
        app_id = selected()
        if app_id is not None:
            open_application(app_id)

    def new() -> None:
        open_application_form(parent, principal=principal, app=None,
                              defaults={"academic_year": year_var.get(),
                                        "year_group": group() or 7},
                              on_saved=lambda a: open_application(a.application_id))

    def do_places() -> None:
        open_places_dialog(parent, principal=principal, academic_year=year_var.get(),
                           on_saved=refresh)

    def do_allocate() -> None:
        if not group():
            messagebox.showinfo("Allocate places", "Choose a year group first.", parent=parent)
            return
        allocate_dialog(parent, principal=principal, academic_year=year_var.get(),
                        year_group=group(), after=refresh)  # type: ignore[arg-type]

    def do_lapse() -> None:
        try:
            lapsed = A.lapse_expired_offers(actor=principal)
        except A.PermissionDenied as e:
            messagebox.showerror("Admissions", str(e), parent=parent)
            return
        messagebox.showinfo("Lapse expired offers",
                            f"{len(lapsed)} offer{'s' if len(lapsed) != 1 else ''} passed the "
                            "reply-by date and were marked declined."
                            + ("\n\n" + ", ".join(a.reference for a in lapsed) if lapsed else ""),
                            parent=parent)
        refresh()

    for var in (year_var, group_var, status_var, search_var):
        var.trace_add("write", refresh)
    tree.bind("<Double-1>", view)
    tree.bind("<Return>", view)
    for text, cmd in (("Lapse expired offers", do_lapse), ("Allocate places…", do_allocate),
                      ("Places…", do_places), ("Open", view), ("New application", new)):
        ttk.Button(head, text=text, command=cmd).pack(side="right", padx=(4, 0))
    refresh()


# ── One application ──────────────────────────────────────────────────

def draw_application(parent: ttk.Frame, application_id: int, *, principal: Principal,
                     on_changed: Callable[[], None], on_back: Callable[[], None],
                     open_pupil: Callable[[int], None]) -> None:
    app = A.get_application(application_id)
    if app is None:
        ttk.Label(parent, text="This application no longer exists.", foreground="#a00").pack(
            anchor="w")
        ttk.Button(parent, text="← Back to Admissions", command=on_back).pack(anchor="w")
        return
    activity_log.record("admission.view", target=app.reference)

    head = ttk.Frame(parent)
    head.pack(fill="x", pady=(0, 6))
    ttk.Label(head, text=f"{app.child_name}", font=("", 16, "bold")).pack(side="left")
    ttk.Label(head, text=f"  {app.reference} · Year {app.year_group} {app.academic_year} · "
                         f"{app.route_label}", foreground="#555").pack(side="left", pady=(4, 0))
    ttk.Button(head, text="← Back to Admissions", command=on_back).pack(side="right")

    status = ttk.Frame(parent)
    status.pack(fill="x", pady=(0, 6))
    colour = {"offered": "#060", "accepted": "#060", "admitted": "#060", "refused": "#a00",
              "waiting_list": "#a60", "appeal_lodged": "#a60"}.get(app.status, "#333")
    text = f"Status: {app.status_label}"
    if app.status == "offered" and app.offer_expires:
        text += f" - reply by {app.offer_expires}"
        if app.offer_expires < _dt.date.today().isoformat():
            text += " (passed)"
    pos = A.waiting_position(app)
    if pos:
        text += f" - position {pos}"
    if app.decision_note:
        text += f" · {app.decision_note}"
    ttk.Label(status, text=text, foreground=colour, font=("", 11, "bold")).pack(side="left")
    warning = A.year_group_warning(app)
    if warning:
        ttk.Label(parent, text=f"⚠ {warning}", foreground="#a60").pack(anchor="w")

    _draw_actions(parent, app, principal=principal, on_changed=on_changed,
                  open_pupil=open_pupil)

    cols = ttk.Frame(parent)
    cols.pack(fill="x")
    for i in range(3):
        cols.columnconfigure(i, weight=1, uniform="a")

    def section(col: int, row: int, title: str, items: list[tuple[str, str]]) -> None:
        box = ttk.LabelFrame(cols, text=title, padding=8)
        box.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        for r, (k, v) in enumerate(items):
            ttk.Label(box, text=f"{k}:", foreground="#555").grid(row=r, column=0, sticky="nw",
                                                                  padx=(0, 8))
            ttk.Label(box, text=v or "—", wraplength=240, justify="left").grid(
                row=r, column=1, sticky="w")

    section(0, 0, "Child", [
        ("Legal name", " ".join(x for x in (app.legal_first_name, app.middle_names,
                                             app.legal_last_name) if x)),
        ("Preferred name", app.preferred_name or ""), ("Date of birth", app.date_of_birth),
        ("Gender", app.gender), ("UPN", app.upn or ""),
        ("Current school", app.current_school or "")])
    section(1, 0, "Home", [
        ("Address", ", ".join(x for x in (app.address_line1, app.address_line2) if x)),
        ("Town", app.town or ""), ("Postcode", app.postcode or ""),
        ("Distance", "" if app.distance_km is None else f"{app.distance_km:g} km")])
    section(2, 0, "Oversubscription", [
        ("Priority", app.criterion_label),
        ("SEN", _SEN_LABELS.get(app.sen_status, app.sen_status)),
        ("EHC plan names school", "Yes" if app.ehcp_names_school else "No"),
        ("Looked after", A.LOOKED_AFTER.get(app.looked_after, app.looked_after)),
        ("Sibling on roll", app.sibling_admission_no or "")])
    section(0, 1, "Parent / carer", [
        ("Name", app.parent_name), ("Relationship", app.parent_relationship),
        ("E-mail", app.parent_email or ""), ("Phone", app.parent_phone or "")])
    section(1, 1, "Application", [
        ("Received", app.received_date), ("Recorded by", app.created_by or ""),
        ("Last changed", f"{app.updated_at} by {app.updated_by or '—'}"),
        ("Notes", app.notes or "")])

    hist = ttk.LabelFrame(parent, text="History", padding=6)
    hist.pack(fill="both", expand=True, pady=(6, 0))
    tree = ttk.Treeview(hist, columns=("at", "who", "what", "note"), show="headings", height=6)
    for col, heading, width in (("at", "When", 140), ("who", "By", 100),
                                ("what", "What", 220), ("note", "Note", 420)):
        tree.heading(col, text=heading)
        tree.column(col, width=width, anchor="w", stretch=col == "note")
    tree.pack(fill="both", expand=True)
    for h in A.history(application_id):
        tree.insert("", "end", values=(h["at"], h["actor"], describe_event(h), h["note"] or ""))


def describe_event(h: dict) -> str:
    if h["action"] == "create":
        return "Application recorded"
    if h["action"] == "update":
        fields = (h.get("detail") or {}).get("fields") or []
        return "Changed " + ", ".join(A.FIELD_LABELS.get(f, f) for f in fields)
    to = A.STATUS_LABELS.get(h["to_status"] or "", h["to_status"] or "")
    return {"offer": "Place offered", "appeal_upheld": "Appeal upheld - place offered",
            "lapse": "Offer lapsed"}.get(h["action"], to)


def _draw_actions(parent: ttk.Frame, app: A.Application, *, principal: Principal,
                  on_changed: Callable[[], None], open_pupil: Callable[[int], None]) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(2, 8))
    nxt = app.next_statuses()
    owner = parent

    def act(title: str, fn, text) -> Callable[[], None]:
        return lambda: _run(owner, principal, title, fn, text, on_changed)

    def ask(title: str, prompt: str, required: bool = True) -> str | None:
        value = simpledialog.askstring(title, prompt, parent=owner)
        if value is None or (required and not value.strip()):
            activity_log.record("admission.action", target=app.reference,
                                outcome="cancelled", action=title)
            return None
        return value

    buttons: list[tuple[str, Callable[[], None]]] = []
    if "offered" in nxt and app.status != "appeal_lodged":
        buttons.append(("Offer place", act(
            "Offer place", lambda: A.offer(app.application_id, actor=principal),
            lambda o: f"Place offered. Reply by {o.application.offer_expires}.")))
    if "waiting_list" in nxt:
        buttons.append(("Waiting list", act(
            "Waiting list", lambda: A.put_on_waiting_list(app.application_id, actor=principal),
            lambda o: f"On the waiting list at position "
                      f"{A.waiting_position(o.application) or '-'}.")))

    def refuse() -> None:
        reason = ask("Refuse place", "Reason for refusing (the parent is told this, with "
                                     "their right of appeal):")
        if reason:
            _run(owner, principal, "Refuse place",
                 lambda: A.refuse(app.application_id, actor=principal, reason=reason),
                 lambda o: "Place refused.", on_changed)

    if "refused" in nxt:
        buttons.append(("Refuse…", refuse))
    if "accepted" in nxt:
        buttons.append(("Parent accepted", act(
            "Parent accepted", lambda: A.record_acceptance(app.application_id, actor=principal),
            lambda o: "Acceptance recorded. Admit the pupil on their first day.")))

    def decline() -> None:
        if messagebox.askyesno("Parent declined", "Record that the parent declined the place? "
                               "The place goes back to the pool.", parent=owner):
            _run(owner, principal, "Parent declined",
                 lambda: A.record_decline(app.application_id, actor=principal),
                 lambda o: "Decline recorded.", on_changed)

    if "declined" in nxt:
        buttons.append(("Parent declined", decline))

    def appeal() -> None:
        note = ask("Appeal lodged", "Note (optional, e.g. hearing date):", required=False)
        if note is not None:
            _run(owner, principal, "Appeal lodged",
                 lambda: A.lodge_appeal(app.application_id, actor=principal, note=note),
                 lambda o: "Appeal recorded.", on_changed)

    if "appeal_lodged" in nxt:
        buttons.append(("Appeal lodged…", appeal))
    if app.status == "appeal_lodged":
        def outcome(upheld: bool) -> Callable[[], None]:
            def run() -> None:
                word = "upheld" if upheld else "dismissed"
                if not messagebox.askyesno("Appeal outcome", f"Record that the appeal was "
                                           f"{word}?", parent=owner):
                    return
                _run(owner, principal, "Appeal outcome",
                     lambda: A.decide_appeal(app.application_id, upheld=upheld,
                                             actor=principal),
                     lambda o: f"Appeal {word}." + (" Place offered." if upheld else ""),
                     on_changed)
            return run
        buttons.append(("Appeal upheld", outcome(True)))
        buttons.append(("Appeal dismissed", outcome(False)))
    if app.status == "accepted":
        buttons.append(("Admit…", lambda: admit_dialog(owner, principal=principal, app=app,
                                                       after=on_changed,
                                                       open_pupil=open_pupil)))
    if app.is_open:
        buttons.append(("Edit", lambda: open_application_form(
            owner, principal=principal, app=app, on_saved=lambda _a: on_changed())))

    def withdraw() -> None:
        reason = ask("Withdraw application", "Reason for withdrawing:")
        if reason:
            _run(owner, principal, "Withdraw application",
                 lambda: A.withdraw(app.application_id, actor=principal, reason=reason),
                 lambda o: "Application withdrawn.", on_changed)

    if "withdrawn" in nxt:
        buttons.append(("Withdraw…", withdraw))
    if app.status == "admitted" and app.admitted_pupil_id:
        buttons.append(("Open pupil record", lambda: open_pupil(app.admitted_pupil_id)))
    if not buttons:
        ttk.Label(bar, text="This application is closed.", foreground="#666").pack(side="left")
    for text, cmd in buttons:
        ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(0, 4))


# ── Admit ────────────────────────────────────────────────────────────

def admit_dialog(owner: tk.Misc, *, principal: Principal, app: A.Application,
                 after: Callable[[], None], open_pupil: Callable[[int], None]) -> None:
    activity_log.record("admission.admit.open", target=app.reference)
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Admit {app.child_name}")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=14)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"Admit {app.child_name} to Year {app.year_group}.\n\nThis creates "
                        "their pupil record, login and school e-mail, adds the parent as "
                        "their first contact and e-mails the parent.",
              wraplength=380, justify="left").grid(row=0, column=0, columnspan=2, sticky="w")
    ttk.Label(frm, text="First day *").grid(row=1, column=0, sticky="w", pady=(10, 2))
    date = DatePicker(frm, value=_dt.date.today().isoformat(), years=recent_years(ahead=0))
    date.grid(row=1, column=1, sticky="w", pady=(10, 2))
    ttk.Label(frm, text="Form group").grid(row=2, column=0, sticky="w")
    from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
    from education_system.systems.secondary.modules.pupils.gui.pupils_views import NO_FORM
    form_names = FG.choices_for(app.year_group)
    form_var = tk.StringVar(value=NO_FORM)
    ttk.Combobox(frm, textvariable=form_var, width=12, state="readonly",
                 values=[NO_FORM, *form_names]).grid(row=2, column=1, sticky="w")
    if not form_names:
        ttk.Label(frm, text=f"No forms set up for Year {app.year_group} yet - see Form Groups.",
                  foreground="#888").grid(row=3, column=0, columnspan=2, sticky="w")

    def go(allow_duplicate: bool = False) -> None:
        try:
            outcome = A.admit(app.application_id, actor=principal, admission_date=date.get(),
                              form_group=None if form_var.get() == NO_FORM else form_var.get(),
                              allow_duplicate=allow_duplicate)
        except P.DuplicatePupil as dup:
            if messagebox.askyesno("Possible duplicate", f"{dup}\n\nAdmit as a different "
                                   "pupil anyway?", parent=win):
                go(True)
            return
        except (A.ValidationError, A.PermissionDenied, A.NotFound) as e:
            messagebox.showerror("Admit", str(e), parent=win)
            return
        except Exception as e:  # noqa: BLE001
            logger.exception("Admit failed")
            messagebox.showerror("Admit", f"Something went wrong:\n{e}", parent=win)
            return
        win.destroy()
        pupil = outcome.pupil
        assert pupil is not None
        text = f"{pupil.display_name} is now on roll as {pupil.admission_no}."
        if outcome.login is not None:
            text += (f"\n\nLogin created (note the password now - it won't be shown again):\n"
                     f"    Username:      {outcome.login.account.username}\n"
                     f"    Password:      {outcome.login.password}\n"
                     f"    School e-mail: {outcome.login.account.school_email}")
        _deliver_then(owner, principal, "Admitted", text, outcome.notes,
                      bool(outcome.message_ids), lambda: open_pupil(pupil.pupil_id))

    def cancel() -> None:
        activity_log.record("admission.admit.cancel", target=app.reference)
        win.destroy()

    bar = ttk.Frame(frm)
    bar.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(bar, text="Cancel", command=cancel).pack(side="right")
    ttk.Button(bar, text="Admit", command=go).pack(side="right", padx=(0, 6))
    win.protocol("WM_DELETE_WINDOW", cancel)


# ── Places and allocation ─────────────────────────────────────────────

def open_places_dialog(owner: tk.Misc, *, principal: Principal, academic_year: str,
                       on_saved: Callable[[], None]) -> None:
    activity_log.record("admission.places.open", target=academic_year)
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Places - {academic_year}")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=14)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"Published admission numbers for {academic_year}",
              font=("", 11, "bold")).grid(row=0, column=0, columnspan=4, sticky="w")
    headers = ("Year group", "Admission number", "Used", "Available")
    for c, h in enumerate(headers):
        ttk.Label(frm, text=h, foreground="#555").grid(row=1, column=c, sticky="w", padx=6,
                                                      pady=(8, 2))
    vars_: dict[int, tk.StringVar] = {}
    for r, yg in enumerate(P.YEAR_GROUPS, start=2):
        p = A.places(academic_year, yg)
        vars_[yg] = tk.StringVar(value="" if p.pan is None else str(p.pan))
        ttk.Label(frm, text=f"Year {yg}").grid(row=r, column=0, sticky="w", padx=6)
        ttk.Spinbox(frm, from_=0, to=1000, width=7, textvariable=vars_[yg]).grid(
            row=r, column=1, sticky="w", padx=6, pady=2)
        ttk.Label(frm, text=str(p.used)).grid(row=r, column=2, sticky="w", padx=6)
        ttk.Label(frm, text="—" if p.available is None else str(p.available)).grid(
            row=r, column=3, sticky="w", padx=6)
    ttk.Label(frm, text="Used = offered + accepted (+ pupils on roll, for the current year). "
                        "Leave blank if not set.", foreground="#666", wraplength=380).grid(
        row=8, column=0, columnspan=4, sticky="w", pady=(8, 0))

    def save() -> None:
        try:
            for yg, var in vars_.items():
                value = var.get().strip()
                if value and str(A.get_pan(academic_year, yg)) != value:
                    A.set_pan(academic_year, yg, value, actor=principal)  # type: ignore[arg-type]
        except (A.ValidationError, A.PermissionDenied) as e:
            messagebox.showerror("Places", str(e), parent=win)
            return
        win.destroy()
        on_saved()

    bar = ttk.Frame(frm)
    bar.grid(row=9, column=0, columnspan=4, sticky="e", pady=(12, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))


def allocate_dialog(owner: tk.Misc, *, principal: Principal, academic_year: str,
                    year_group: int, after: Callable[[], None]) -> None:
    p = A.places(academic_year, year_group)
    if p.pan is None:
        messagebox.showinfo("Allocate places", f"Set the admission number for Year {year_group}"
                            f" in {academic_year} first (Places).", parent=owner)
        return
    offer_list, wait_list = A.allocation_preview(academic_year, year_group)
    if not offer_list and not wait_list:
        messagebox.showinfo("Allocate places", "There are no received or waiting applications "
                            "for this year group.", parent=owner)
        return
    new_wait = [a for a in wait_list if a.status != "waiting_list"]
    lines = [f"Year {year_group} {academic_year}: {p.available} place(s) available.", "",
             f"Offer {len(offer_list)}:"]
    lines += [f"  {a.reference}  {a.child_name} - {a.criterion_label}" for a in offer_list[:15]]
    if len(offer_list) > 15:
        lines.append(f"  … and {len(offer_list) - 15} more")
    lines += ["", f"Waiting list: {len(wait_list)} ({len(new_wait)} new)",
              "", "Parents will be e-mailed. Go ahead?"]
    if not messagebox.askyesno("Allocate places", "\n".join(lines), parent=owner):
        activity_log.record("admission.allocate", target=f"{academic_year} Y{year_group}",
                            outcome="cancelled")
        return
    try:
        result = A.allocate(academic_year, year_group, actor=principal)
    except (A.ValidationError, A.PermissionDenied) as e:
        messagebox.showerror("Allocate places", str(e), parent=owner)
        return
    _deliver_then(owner, principal, "Allocate places",
                  f"{len(result.offered)} offered, {len(result.waiting)} on the waiting list.",
                  result.notes, bool(result.message_ids), after)


# ── Application form ─────────────────────────────────────────────────

def open_application_form(owner: tk.Misc, *, principal: Principal, app: A.Application | None,
                          on_saved: Callable[[A.Application], None],
                          defaults: dict | None = None) -> None:
    editing = app is not None
    target = app.reference if app else "new"
    if not principal.can_open(A.MENU_LABEL):
        activity_log.record("admission.form.open", target=target, outcome="denied")
        messagebox.showwarning("Admissions", principal.denied_message(A.MENU_LABEL),
                               parent=owner)
        return
    activity_log.record("admission.form.open", target=target,
                        mode="edit" if editing else "add")
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Edit application {app.reference}" if app else "New application")
    window_sizing.fit(win, "1000x720", (900, 600))
    body, footer = scrolled_form(win)
    body.columnconfigure(0, weight=1)
    body.columnconfigure(1, weight=1)
    defaults = defaults or {}
    widgets: dict[str, tk.Misc] = {}

    def value(name: str, fallback=""):
        if app is not None:
            v = getattr(app, name)
            return "" if v is None else v
        return defaults.get(name, fallback)

    def box(col: int, row: int, title: str) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(body, text=title, padding=8)
        frame.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        return frame

    def entry(frame, r: int, label: str, name: str, *, required=False, width=28) -> None:
        ttk.Label(frame, text=label + (" *" if required else "")).grid(
            row=r, column=0, sticky="w", pady=2, padx=(0, 8))
        e = ttk.Entry(frame, width=width)
        e.insert(0, str(value(name)))
        e.grid(row=r, column=1, sticky="w", pady=2)
        widgets[name] = e

    def combo(frame, r: int, label: str, name: str, values: list[str], current: str, *,
              required=False, width=26) -> ttk.Combobox:
        ttk.Label(frame, text=label + (" *" if required else "")).grid(
            row=r, column=0, sticky="w", pady=2, padx=(0, 8))
        cb = ttk.Combobox(frame, values=values, state="readonly", width=width)
        cb.set(current)
        cb.grid(row=r, column=1, sticky="w", pady=2)
        widgets[name] = cb
        return cb

    def date(frame, r: int, label: str, name: str, years, *, required=False) -> None:
        ttk.Label(frame, text=label + (" *" if required else "")).grid(
            row=r, column=0, sticky="w", pady=2, padx=(0, 8))
        dp = DatePicker(frame, value=str(value(name)) or None, years=years)
        dp.grid(row=r, column=1, sticky="w", pady=2)
        widgets[name] = dp

    this_year = _dt.date.today().year
    birth_years = [str(y) for y in range(this_year - 9, this_year - 18, -1)]

    a = box(0, 0, "Application")
    combo(a, 0, "Route", "route", list(A.ROUTES.values()),
          A.ROUTES[str(value("route", "normal_round"))], required=True)
    combo(a, 1, "Academic year", "academic_year", A.academic_year_choices(),
          str(value("academic_year", A.next_academic_year())), required=True, width=10)
    combo(a, 2, "Year group", "year_group", [str(y) for y in P.YEAR_GROUPS],
          str(value("year_group", 7)), required=True, width=5)
    date(a, 3, "Date received", "received_date", recent_years(ahead=0))
    if not editing:
        widgets["received_date"].set(_dt.date.today().isoformat())  # type: ignore[attr-defined]

    c = box(1, 0, "Child")
    entry(c, 0, "Legal first name", "legal_first_name", required=True)
    entry(c, 1, "Middle names", "middle_names")
    entry(c, 2, "Legal last name", "legal_last_name", required=True)
    entry(c, 3, "Preferred name", "preferred_name")
    date(c, 4, "Date of birth", "date_of_birth", birth_years, required=True)
    combo(c, 5, "Gender", "gender", list(P.GENDERS), str(value("gender")), required=True)
    entry(c, 6, "UPN", "upn")
    entry(c, 7, "Current school", "current_school")

    h = box(0, 1, "Home")
    entry(h, 0, "Address line 1", "address_line1")
    entry(h, 1, "Address line 2", "address_line2")
    entry(h, 2, "Town", "town")
    entry(h, 3, "Postcode", "postcode", width=10)
    entry(h, 4, "Distance to school (km)", "distance_km", width=8)

    o = box(1, 1, "Oversubscription criteria")
    combo(o, 0, "SEN", "sen_status", list(_SEN_LABELS.values()),
          _SEN_LABELS[str(value("sen_status", "N"))])
    ehcp_var = tk.BooleanVar(value=bool(value("ehcp_names_school", False)))
    ttk.Checkbutton(o, text="EHC plan names this school", variable=ehcp_var).grid(
        row=1, column=1, sticky="w")
    combo(o, 2, "Looked after", "looked_after", list(A.LOOKED_AFTER.values()),
          A.LOOKED_AFTER[str(value("looked_after", "no"))])
    entry(o, 3, "Sibling on roll (adm. no)", "sibling_admission_no", width=12)

    pr = box(0, 2, "Parent / carer")
    entry(pr, 0, "Name", "parent_name", required=True)
    combo(pr, 1, "Relationship", "parent_relationship", list(C.RELATIONSHIPS),
          str(value("parent_relationship", "Mother")), required=True)
    entry(pr, 2, "E-mail", "parent_email")
    entry(pr, 3, "Phone", "parent_phone")
    ttk.Label(pr, text="An e-mail address or phone number is required. Decisions are "
                       "e-mailed to the parent.", foreground="#666", wraplength=330).grid(
        row=4, column=0, columnspan=2, sticky="w", pady=(4, 0))

    n = box(1, 2, "Notes")
    notes = tk.Text(n, width=40, height=5, wrap="word")
    notes.insert("1.0", str(value("notes")))
    notes.pack(fill="both", expand=True)

    error_var = tk.StringVar()
    ttk.Label(footer, textvariable=error_var, foreground="#a00", wraplength=900,
              justify="left").pack(side="top", anchor="w")

    def collect() -> dict:
        data: dict = {}
        for name, w in widgets.items():
            data[name] = w.get()  # type: ignore[attr-defined]
        data["route"] = _ROUTE_BY_LABEL.get(data["route"], data["route"])
        data["sen_status"] = (data["sen_status"] or "N")[:1]
        data["looked_after"] = _LOOKED_AFTER_BY_LABEL.get(data["looked_after"], "no")
        data["ehcp_names_school"] = ehcp_var.get()
        data["notes"] = notes.get("1.0", "end").strip()
        return data

    def save(allow_duplicate: bool = False) -> None:
        data = collect()
        error_var.set("")
        warn = A.year_group_warning(data) if data.get("date_of_birth") else None
        if warn and not messagebox.askyesno("Check year group", f"{warn}\n\nSave anyway?",
                                            parent=win):
            return
        try:
            if app is not None:
                saved, _changed = A.update_application(app.application_id, data,
                                                       actor=principal)
                notes_out, mail = [], False
            else:
                outcome = A.create_application(data, actor=principal,
                                               allow_duplicate=allow_duplicate)
                saved, notes_out, mail = outcome.application, outcome.notes, \
                    bool(outcome.message_ids)
        except A.DuplicateApplication as dup:
            if messagebox.askyesno("Possible duplicate", f"{dup}\n\nRecord this as a separate "
                                   "application anyway?", parent=win):
                save(True)
            return
        except A.ValidationError as e:
            error_var.set("Please fix:\n• " + "\n• ".join(e.problems))
            return
        except (A.PermissionDenied, A.NotFound) as e:
            messagebox.showerror("Admissions", str(e), parent=win)
            return
        except Exception as e:  # noqa: BLE001
            logger.exception("Saving application failed")
            messagebox.showerror("Admissions", f"Could not save:\n{e}", parent=win)
            return
        win.destroy()
        if app is None:
            _deliver_then(owner, principal, "Application recorded",
                          f"Application {saved.reference} recorded for {saved.child_name}.",
                          notes_out, mail, lambda: on_saved(saved))
        else:
            on_saved(saved)

    def cancel() -> None:
        activity_log.record("admission.form.cancel", target=target)
        win.destroy()

    bar = ttk.Frame(footer)
    bar.pack(side="top", anchor="e", pady=(4, 0))
    ttk.Button(bar, text="Cancel", command=cancel).pack(side="right")
    ttk.Button(bar, text="Save" if editing else "Record application",
               command=save).pack(side="right", padx=(0, 6))
    win.protocol("WM_DELETE_WINDOW", cancel)
    widgets["legal_first_name"].focus_set()  # type: ignore[attr-defined]
