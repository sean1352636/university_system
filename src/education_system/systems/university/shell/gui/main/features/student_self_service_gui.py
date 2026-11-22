"""Student self-service windows: My Attendance, My Mitigating Circumstances,
My Parking and My Placement.

Each window shows only the signed-in student's own records — the student id
is resolved once from the session (application/self_service/identity) and
never typed in. Staff windows for the same areas (Attendance, Mitigating
Circumstances, Parking Management, Placement Hours) list everyone and stay
where they are; these are the student's view of them.

Every window loads its data off the Tk thread and parents its dialogs to
itself. Open them with ``open_<name>(parent, auth)``.
"""

from __future__ import annotations

import logging
import tkinter as tk
from contextlib import closing
from datetime import date
from tkinter import messagebox, ttk

from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)

_PREFIX = "gui.shell.main.features.student_self_service"


def _tr(key: str, default: str, **kwargs) -> str:
    return _t(f"{_PREFIX}.{key}", default=default, **kwargs)


# ----------------------------------------------------------------------
# Shared plumbing
# ----------------------------------------------------------------------

def _connection():
    from education_system.systems.university.infrastructure.database.db import get_connection
    return closing(get_connection())


def _transaction():
    from education_system.systems.university.infrastructure.database.db import transaction
    return transaction()


def _student(conn, auth):
    from education_system.systems.university.application.self_service.identity import (
        require_student,
        session_user,
    )
    return require_student(conn, session_user(auth))


def _window(parent, title: str) -> tk.Toplevel:
    try:
        from education_system.platform.delivery.gui.window_sizing import install
        install()
    except Exception:
        logger.debug("window_sizing unavailable", exc_info=True)
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("1400x900")
    win.minsize(1200, 800)
    try:
        win.transient(parent)
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)
    return win


def _tree(parent, columns: list[tuple[str, str, int]], height: int = 12) -> ttk.Treeview:
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True, padx=10, pady=6)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", height=height)
    for key, label, width in columns:
        tree.heading(key, text=label)
        tree.column(key, width=width, anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    tree.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    return tree


def _fill(tree: ttk.Treeview, rows: list[dict], keys: list[str], empty: str) -> None:
    tree.delete(*tree.get_children())
    for row in rows:
        tree.insert("", "end", values=[_cell(row.get(k)) for k in keys])
    if not rows:
        tree.insert("", "end", values=[empty] + [""] * (len(keys) - 1))


def _cell(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _load(win, work, done) -> None:
    """Run ``work()`` off the Tk thread and hand its result (or error) to
    ``done(result, error)`` on the Tk thread."""
    from education_system.platform.delivery.gui.tk_threads import start_thread, ui

    def _worker():
        try:
            result = work()
        except Exception as exc:  # shown to the user, never swallowed
            logger.info("Self-service load refused/failed: %s", exc)
            ui(win, _deliver, None, exc)
            return
        ui(win, _deliver, result, None)

    def _deliver(result, error):
        try:
            if win.winfo_exists():
                done(result, error)
        except tk.TclError:
            pass

    start_thread(win, _worker)


def _error_page(win, error) -> None:
    for child in win.winfo_children():
        child.destroy()
    ttk.Label(win, text=str(error), font=("Arial", 12), wraplength=900,
              foreground="#c0392b").pack(padx=30, pady=40)
    ttk.Button(win, text=_t("common.close", default="Close"), command=win.destroy).pack()


def _header(win, title: str, subtitle: str = "") -> None:
    bar = tk.Frame(win, bg="#2c3e50", height=48)
    bar.pack(fill="x")
    bar.pack_propagate(False)
    tk.Label(bar, text=title, font=("Arial", 15, "bold"), bg="#2c3e50",
             fg="white").pack(side="left", padx=20)
    if subtitle:
        tk.Label(bar, text=subtitle, font=("Arial", 10), bg="#2c3e50",
                 fg="#bdc3c7").pack(side="right", padx=20)


def _ask_fields(win, title: str, fields: list[tuple[str, str, object]]) -> dict | None:
    """Modal form; each field is ``(key, label, kind)`` where kind is
    ``"entry"``, ``"text"`` or a tuple of choices. Returns the values or None."""
    dlg = tk.Toplevel(win)
    dlg.title(title)
    dlg.transient(win)
    dlg.grab_set()
    widgets: dict[str, object] = {}
    for key, label, kind in fields:
        ttk.Label(dlg, text=label).pack(anchor="w", padx=12, pady=(8, 0))
        if kind == "text":
            widget = tk.Text(dlg, height=4, width=60)
        elif isinstance(kind, tuple):
            widget = ttk.Combobox(dlg, values=list(kind), state="readonly", width=40)
        else:
            widget = ttk.Entry(dlg, width=60)
        widget.pack(fill="x", padx=12)
        widgets[key] = widget
    result: dict = {}

    def _ok():
        for key, widget in widgets.items():
            result[key] = (widget.get("1.0", "end").strip() if isinstance(widget, tk.Text)
                           else widget.get().strip())
        dlg.destroy()

    row = ttk.Frame(dlg)
    row.pack(pady=12)
    ttk.Button(row, text=_t("common.ok", default="OK"), command=_ok).pack(side="left", padx=6)
    ttk.Button(row, text=_t("common.cancel", default="Cancel"),
               command=dlg.destroy).pack(side="left", padx=6)
    dlg.wait_window()
    return result or None


# ----------------------------------------------------------------------
# My Attendance
# ----------------------------------------------------------------------

_OUTCOME_LABELS = {"present": "Present", "late": "Late", "excused": "Excused",
                   "absent": "Absent", "no_register": "No register taken"}


def open_my_attendance(parent, auth) -> tk.Toplevel:
    """The student's own attendance: summary, by module, each session,
    self-certifications and (for Student route visa holders) the UKVI run."""
    win = _window(parent, _tr("attendance.title", "My Attendance"))
    _header(win, _tr("attendance.title", "My Attendance"))
    body = ttk.Frame(win)
    body.pack(fill="both", expand=True)
    ttk.Label(body, text=_tr("loading", "Loading…")).pack(pady=30)
    state: dict = {}

    def work():
        from education_system.systems.university.application.self_service.attendance import (
            my_attendance,
        )
        with _connection() as conn:
            student = _student(conn, auth)
            return student, my_attendance(conn, student.student_id)

    def done(result, error):
        if error:
            _error_page(win, error)
            return
        state["student"], data = result
        _render_attendance(win, body, data, on_certify=lambda: _certify(win, state, refresh))

    def refresh():
        _load(win, work, done)

    refresh()
    return win


def _render_attendance(win, body, data, on_certify) -> None:
    for child in body.winfo_children():
        child.destroy()
    s = data["summary"]
    start, end = data["window"]
    top = ttk.LabelFrame(body, text=_tr("attendance.summary", "Summary ({start} to {end})",
                                        start=start, end=end), padding=10)
    top.pack(fill="x", padx=10, pady=8)
    pct = f"{s['attendance_pct']}%" if s.get("attendance_pct") is not None else "—"
    cover = f"{s['coverage_pct']}%" if s.get("coverage_pct") is not None else "—"
    for label, value in (("Attendance rate", pct), ("Sessions expected", s["expected"]),
                         ("Registers taken", cover), ("Missed in a row", s["consecutive_missed"])):
        card = ttk.Frame(top)
        card.pack(side="left", expand=True)
        ttk.Label(card, text=label).pack()
        ttk.Label(card, text=str(value), font=("Arial", 18, "bold")).pack()
    ttk.Label(body, wraplength=1200, foreground="#555", text=_tr(
        "attendance.rule", "The rate counts present and late over sessions where a register "
        "was taken. Excused absences count neither way; sessions with no register are listed "
        "but not counted.")).pack(anchor="w", padx=12)
    if data.get("ukvi"):
        u = data["ukvi"]
        box = ttk.LabelFrame(body, text=_tr("attendance.ukvi", "Student route visa — engagement"),
                             padding=8)
        box.pack(fill="x", padx=10, pady=6)
        text = _tr("attendance.ukvi_text",
                   "You have missed {missed} timetabled contact points in a row. The university "
                   "must report {limit} in a row to UKVI. Last attended: {last}.",
                   missed=u["consecutive_missed"], limit=u["limit"], last=u["last_engaged"] or "—")
        ttk.Label(box, text=text, wraplength=1200,
                  foreground="#c0392b" if u["at_risk"] else "#2c3e50").pack(anchor="w")
    tabs = ttk.Notebook(body)
    tabs.pack(fill="both", expand=True, padx=10, pady=6)
    mod_tab, ses_tab, cert_tab = ttk.Frame(tabs), ttk.Frame(tabs), ttk.Frame(tabs)
    tabs.add(mod_tab, text=_tr("attendance.by_module", "By module"))
    tabs.add(ses_tab, text=_tr("attendance.sessions", "Sessions"))
    tabs.add(cert_tab, text=_tr("attendance.self_cert", "Self-certifications"))
    cols = [("module_code", "Module", 140), ("expected", "Expected", 90), ("present", "Present", 90),
            ("late", "Late", 80), ("excused", "Excused", 90), ("absent", "Absent", 90),
            ("no_register", "No register", 110), ("attendance_pct", "Rate %", 90)]
    _fill(_tree(mod_tab, cols), data["modules"], [c[0] for c in cols],
          _tr("attendance.none", "No timetabled sessions in this period."))
    sessions = [dict(x, outcome=_OUTCOME_LABELS.get(x.get("outcome"), x.get("outcome")))
                for x in reversed(data["sessions"])]
    scols = [("date", "Date", 120), ("module_code", "Module", 140), ("start_time", "Start", 90),
             ("end_time", "End", 90), ("outcome", "Outcome", 160)]
    _fill(_tree(ses_tab, scols), sessions, [c[0] for c in scols],
          _tr("attendance.none", "No timetabled sessions in this period."))
    ccols = [("date", "From", 140), ("date_end", "To", 140), ("reason", "Reason", 600)]
    _fill(_tree(cert_tab, ccols), data["self_certifications"], [c[0] for c in ccols],
          _tr("attendance.no_certs", "No self-certified absences this academic year."))
    ttk.Button(cert_tab, text=_tr("attendance.certify", "Self-certify an absence…"),
               command=on_certify).pack(anchor="w", padx=10, pady=6)


def _certify(win, state, refresh) -> None:
    from education_system.systems.university.application.self_service.attendance import (
        certify_own_absence,
    )
    values = _ask_fields(win, _tr("attendance.certify", "Self-certify an absence…"), [
        ("start", "First day absent (YYYY-MM-DD)", "entry"),
        ("end", "Last day absent (YYYY-MM-DD)", "entry"),
        ("reason", "Reason", "text"),
    ])
    if not values:
        return
    try:
        start = date.fromisoformat(values["start"])
        end = date.fromisoformat(values["end"] or values["start"])
        with _transaction() as conn:
            certify_own_absence(conn, state["student"].student_id, start, end, values["reason"])
    except Exception as exc:
        messagebox.showerror(_tr("attendance.certify", "Self-certify an absence…"), str(exc),
                             parent=win)
        return
    messagebox.showinfo(_tr("attendance.certified", "Absence self-certified"),
                        _tr("attendance.certified_text",
                            "Your absence has been recorded as self-certified."), parent=win)
    refresh()


# ----------------------------------------------------------------------
# My Mitigating Circumstances
# ----------------------------------------------------------------------

def _mc_service():
    from education_system.systems.university.domains.assessment.domain.mitigating_circumstances.services.mitigating_circumstances_service import (
        VALID_GROUNDS,
        MitigatingCircumstancesService,
    )
    return MitigatingCircumstancesService(), VALID_GROUNDS


def open_my_mitigating_circumstances(parent, auth) -> tk.Toplevel:
    """Submit, follow, evidence and withdraw the student's own MC/EC claims."""
    title = _tr("mc.title", "My Mitigating Circumstances")
    win = _window(parent, title)
    _header(win, title)
    state: dict = {}
    tabs = ttk.Notebook(win)
    tabs.pack(fill="both", expand=True, padx=10, pady=8)
    claims_tab, ext_tab = ttk.Frame(tabs), ttk.Frame(tabs)
    tabs.add(claims_tab, text=_tr("mc.claims", "My claims"))
    tabs.add(ext_tab, text=_tr("mc.extensions", "Extensions granted"))
    ttk.Label(claims_tab, wraplength=1200, foreground="#555", text=_tr(
        "mc.intro", "Tell us about circumstances outside your control that affected an "
        "assessment. A panel reviews each claim with its evidence; you will see the outcome "
        "here. You can add evidence to, or withdraw, a claim until it is decided.")).pack(
        anchor="w", padx=12, pady=(8, 0))
    bar = ttk.Frame(claims_tab)
    bar.pack(fill="x", padx=10, pady=6)
    cols = [("id", "#", 60), ("module_code", "Module", 110), ("assessment_ref", "Assessment", 160),
            ("grounds", "Grounds", 120), ("status", "Status", 140), ("submitted_at", "Submitted", 170)]
    claims = _tree(claims_tab, cols)
    ecols = [("module_code", "Module", 120), ("assessment_ref", "Assessment", 160),
             ("original_deadline", "Original deadline", 160), ("new_deadline", "New deadline", 160),
             ("extension_days", "Days", 80), ("reason", "Reason", 400)]
    extensions = _tree(ext_tab, ecols)

    def work():
        from education_system.systems.university.application.self_service import (
            mitigating_circumstances as mc,
        )
        with _connection() as conn:
            student = _student(conn, auth)
        service, grounds = _mc_service()
        return student, service, grounds, mc.own_claims(service, student.student_id), \
            mc.own_extensions(service, student.student_id)

    def done(result, error):
        if error:
            _error_page(win, error)
            return
        state["student"], state["service"], state["grounds"], rows, exts = result
        _fill(claims, rows, [c[0] for c in cols], _tr("mc.none", "You have no claims."))
        _fill(extensions, exts, [c[0] for c in ecols], _tr("mc.no_ext", "No extensions granted."))

    def refresh():
        _load(win, work, done)

    def selected():
        sel = claims.selection()
        value = claims.item(sel[0], "values")[0] if sel else None
        if not value or not str(value).isdigit():
            messagebox.showinfo(title, _tr("mc.select", "Select one of your claims first."),
                                parent=win)
            return None
        return int(value)

    def act(fn):
        try:
            fn()
        except Exception as exc:
            messagebox.showerror(title, str(exc), parent=win)
            return
        refresh()

    for label, command in (
            (_tr("mc.new", "New claim…"), lambda: act(lambda: _mc_submit(win, state))),
            (_tr("mc.view", "View claim"), lambda: _mc_view(win, state, selected())),
            (_tr("mc.evidence", "Add evidence…"),
             lambda: act(lambda: _mc_evidence(win, state, selected()))),
            (_tr("mc.withdraw", "Withdraw claim"),
             lambda: act(lambda: _mc_withdraw(win, state, selected()))),
            (_t("common.refresh", default="Refresh"), refresh)):
        ttk.Button(bar, text=label, command=command).pack(side="left", padx=3)
    refresh()
    return win


def _mc_submit(win, state) -> None:
    from education_system.systems.university.application.self_service import (
        mitigating_circumstances as mc,
    )
    values = _ask_fields(win, _tr("mc.new", "New claim…"), [
        ("module_code", "Module code (e.g. CS101)", "entry"),
        ("assessment_ref", "Assessment (e.g. Coursework 1, January exam)", "entry"),
        ("grounds", "Grounds", tuple(state["grounds"])),
        ("period_start", "Affected from (YYYY-MM-DD)", "entry"),
        ("period_end", "Affected until (YYYY-MM-DD)", "entry"),
        ("description", "What happened", "text"),
        ("impact_statement", "How it affected your assessment", "text"),
        ("requested_remedy", "What you are asking for (e.g. extension, deferral)", "entry"),
    ])
    if not values:
        return
    student = state["student"]
    claim_id = mc.submit_own_claim(state["service"], student.student_id, student.username,
                                   values, state["grounds"])
    messagebox.showinfo(_tr("mc.submitted", "Claim submitted"), _tr(
        "mc.submitted_text", "Claim #{id} submitted. Add your evidence to it next.", id=claim_id),
        parent=win)


def _mc_view(win, state, claim_id) -> None:
    from education_system.systems.university.application.self_service import (
        mitigating_circumstances as mc,
    )
    if claim_id is None:
        return
    try:
        sid = state["student"].student_id
        claim = mc.own_claim(state["service"], sid, claim_id)
        evidence = mc.own_evidence(state["service"], sid, claim_id)
    except Exception as exc:
        messagebox.showerror(_tr("mc.title", "My Mitigating Circumstances"), str(exc), parent=win)
        return
    lines = [f"Claim #{claim['id']} — {claim['status']}",
             f"Module: {claim.get('module_code') or '—'}   Assessment: "
             f"{claim.get('assessment_ref') or '—'}",
             f"Grounds: {claim.get('grounds') or '—'}",
             f"Period: {claim.get('period_start') or '—'} to {claim.get('period_end') or '—'}",
             "", claim.get("description") or "", "",
             f"Impact: {claim.get('impact_statement') or '—'}",
             f"Requested: {claim.get('requested_remedy') or '—'}", "", "Evidence:"]
    lines += [f"  • {e.get('evidence_type')}: {e.get('description') or ''} "
              f"({'verified' if e.get('verified') else 'awaiting check'})" for e in evidence] \
        or ["  none yet"]
    messagebox.showinfo(f"Claim #{claim_id}", "\n".join(lines), parent=win)


def _mc_evidence(win, state, claim_id) -> None:
    from education_system.systems.university.application.self_service import (
        mitigating_circumstances as mc,
    )
    if claim_id is None:
        return
    values = _ask_fields(win, _tr("mc.evidence", "Add evidence…"), [
        ("evidence_type", "Type of evidence", tuple(mc.EVIDENCE_TYPES)),
        ("description", "What it is (e.g. GP note dated 3 March)", "entry"),
        ("document_ref", "Reference or where it was sent (optional)", "entry"),
    ])
    if values:
        mc.add_own_evidence(state["service"], state["student"].student_id, claim_id,
                            values["evidence_type"], values["description"], values["document_ref"])


def _mc_withdraw(win, state, claim_id) -> None:
    from education_system.systems.university.application.self_service import (
        mitigating_circumstances as mc,
    )
    if claim_id is None:
        return
    if messagebox.askyesno(_tr("mc.withdraw", "Withdraw claim"),
                           _tr("mc.withdraw_confirm", "Withdraw claim #{id}? This cannot be undone.",
                               id=claim_id), parent=win):
        mc.withdraw_own_claim(state["service"], state["student"].student_id, claim_id)


# ----------------------------------------------------------------------
# My Parking
# ----------------------------------------------------------------------

def open_my_parking(parent, auth) -> tk.Toplevel:
    """The student's own parking permits, registered vehicles and fines."""
    title = _tr("parking.title", "My Parking")
    win = _window(parent, title)
    _header(win, title)
    summary = ttk.Label(win, text=_tr("loading", "Loading…"), font=("Arial", 12, "bold"))
    summary.pack(anchor="w", padx=14, pady=8)
    ttk.Label(win, foreground="#555", wraplength=1200, text=_tr(
        "parking.office", "To apply for or renew a permit, register a vehicle, pay a fine or "
        "appeal one, contact the Parking office.")).pack(anchor="w", padx=14)
    tabs = ttk.Notebook(win)
    tabs.pack(fill="both", expand=True, padx=10, pady=8)
    specs = {
        "permits": ([("permit_number", "Permit", 140), ("zone", "Zone", 100),
                     ("permit_type", "Type", 120), ("start_date", "From", 120),
                     ("end_date", "To", 120), ("active_status", "Status", 120),
                     ("vehicle_id", "Vehicle", 120)], "No permits on record."),
        "vehicles": ([("license_plate", "Registration", 140), ("make", "Make", 140),
                      ("model", "Model", 140), ("color", "Colour", 100),
                      ("vehicle_type", "Type", 120)], "No vehicles registered."),
        "violations": ([("violation_date", "Date", 140), ("license_plate", "Registration", 140),
                        ("violation_type", "Offence", 200), ("location", "Location", 160),
                        ("fine_amount", "Fine £", 90), ("payment_status", "Payment", 120)],
                       "No parking fines."),
    }
    trees = {}
    for key, (cols, _empty) in specs.items():
        tab = ttk.Frame(tabs)
        tabs.add(tab, text=key.capitalize())
        trees[key] = _tree(tab, cols)

    def work():
        from education_system.systems.university.application.self_service.parking import my_parking
        with _connection() as conn:
            return my_parking(conn, _student(conn, auth))

    def done(data, error):
        if error:
            _error_page(win, error)
            return
        for key, (cols, empty) in specs.items():
            _fill(trees[key], data[key], [c[0] for c in cols], empty)
        summary.config(text=_tr("parking.summary",
                                "{permits} permit(s), {vehicles} vehicle(s), £{owed:.2f} in "
                                "unpaid fines", permits=len(data["permits"]),
                                vehicles=len(data["vehicles"]), owed=data["outstanding"]))

    _load(win, work, done)
    return win


# ----------------------------------------------------------------------
# My Placement
# ----------------------------------------------------------------------

def open_my_placement(parent, auth) -> tk.Toplevel:
    """The student's own placement enrolment and hours log (read-only)."""
    title = _tr("placement.title", "My Placement")
    win = _window(parent, title)
    _header(win, title)
    info = ttk.LabelFrame(win, text=_tr("placement.details", "Placement"), padding=10)
    info.pack(fill="x", padx=10, pady=8)
    info_label = ttk.Label(info, text=_tr("loading", "Loading…"), justify="left")
    info_label.pack(anchor="w")
    progress = ttk.Progressbar(info, maximum=100, length=500)
    progress.pack(anchor="w", pady=6)
    ttk.Label(win, foreground="#555", wraplength=1200, text=_tr(
        "placement.office", "Hours are logged and signed off by your placement supervisor and "
        "the placement office. If something here is wrong, contact the placement office.")).pack(
        anchor="w", padx=14)
    cols = [("log_date", "Date", 120), ("hours", "Hours", 80), ("activity", "Activity", 400),
            ("signed", "Signed off", 100), ("notes", "Notes", 400)]
    tree = _tree(win, cols)

    def work():
        from education_system.systems.university.application.self_service.placements import (
            my_placement,
        )
        with _connection() as conn:
            return my_placement(conn, _student(conn, auth).student_id)

    def done(data, error):
        if error:
            _error_page(win, error)
            return
        p = data["profile"]
        if not p:
            info_label.config(text=_tr("placement.none", "You are not enrolled on a placement."))
        else:
            info_label.config(text="\n".join([
                f"Employer: {p.get('employer') or '—'}    Supervisor: {p.get('supervisor') or '—'}",
                f"Cohort: {p.get('cohort') or '—'}    Dates: {p.get('start_date') or '—'} to "
                f"{p.get('end_date') or '—'}",
                f"Hours logged: {data['total']:g}    Signed off: {data['signed_off']:g} of "
                f"{data['required']}    Still needed: {data['remaining']:g}"]))
        progress["value"] = min(100, data["signed_off"] / data["required"] * 100) \
            if data["required"] else 0
        rows = [dict(h, signed="Yes" if h["signed_off"] else "No") for h in data["hours"]]
        _fill(tree, rows, [c[0] for c in cols], _tr("placement.no_hours", "No hours logged yet."))

    _load(win, work, done)
    return win
