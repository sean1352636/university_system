"""Pupil screens: directory, search, profile, add, edit and delete.

Every page here is a ``draw(parent)`` function so the main window can show it
in the content area or in a pop-out window. The rules (who may edit, what is
valid, the audit trail) all live in :mod:`modules.pupils.domain.pupils`; these screens only
collect input and show results.
"""

from __future__ import annotations

import json
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
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log

logger = logging.getLogger(__name__)

#: The form dropdown's "no form" entry.
NO_FORM = "(no form)"

#: Wait this long after the last keystroke or filter change before logging a
#: list/search, so typing a name writes one line rather than one per letter.
_LOG_DELAY_MS = 1200


def _debounced_logger(widget: tk.Misc) -> Callable[..., None]:
    """``log(action, **fields)`` that only writes the last call in a burst."""
    pending: dict = {"job": None, "line": None}

    def flush(_e=None) -> None:
        # Also runs when the screen closes, so the last search isn't lost.
        if _e is not None and _e.widget is not widget:
            return
        if pending["job"] is not None:
            try:
                widget.after_cancel(pending["job"])
            except tk.TclError:
                pass
            pending["job"] = None
        if pending["line"] is not None:
            action, fields = pending["line"]
            pending["line"] = None
            activity_log.record(action, **fields)

    def log(action: str, **fields) -> None:
        if pending["job"] is not None:
            try:
                widget.after_cancel(pending["job"])
            except tk.TclError:
                pass
        pending["line"] = (action, fields)
        try:
            pending["job"] = widget.after(_LOG_DELAY_MS, flush)
        except tk.TclError:
            flush()

    widget.bind("<Destroy>", flush, add="+")
    return log


_STATUS_FILTERS = {"On roll": "on_roll", "Left": "left", "All": None}
_COLUMNS = (
    ("admission_no", "Adm. no", 90),
    ("name", "Name", 200),
    ("year", "Year", 50),
    ("form", "Form", 60),
    ("dob", "Date of birth", 100),
    ("upn", "UPN", 120),
    ("sen", "SEN", 50),
    ("status", "Status", 70),
)


# ── Directory / search ───────────────────────────────────────────────

def draw_directory(parent: ttk.Frame, *, principal: Principal,
                   open_profile: Callable[[int], None],
                   focus_search: bool = False, title: str = "Pupil Directory") -> None:
    """The list of pupils with filters and the CRUD buttons."""
    ttk.Label(parent, text=title, font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Search:").pack(side="left")
    search_var = tk.StringVar()
    search = ttk.Entry(bar, textvariable=search_var, width=28)
    search.pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Year:").pack(side="left")
    year_cb = ttk.Combobox(bar, state="readonly", width=5,
                           values=["All"] + [str(y) for y in P.YEAR_GROUPS])
    year_cb.set("All")
    year_cb.pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Form:").pack(side="left")
    form_cb = ttk.Combobox(bar, state="readonly", width=7)
    form_cb.pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Status:").pack(side="left")
    status_cb = ttk.Combobox(bar, state="readonly", width=8, values=list(_STATUS_FILTERS))
    status_cb.set("On roll")
    status_cb.pack(side="left", padx=(4, 12))
    count_var = tk.StringVar()
    ttk.Label(bar, textvariable=count_var, foreground="#555").pack(side="right")

    table = ttk.Frame(parent)
    table.pack(fill="both", expand=True)
    tree = ttk.Treeview(table, columns=[c for c, _h, _w in _COLUMNS],
                        show="headings", height=18, selectmode="browse")
    for col, heading, width in _COLUMNS:
        tree.heading(col, text=heading)
        tree.column(col, width=width, anchor="w", stretch=col == "name")
    vs = ttk.Scrollbar(table, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vs.set)
    tree.pack(side="left", fill="both", expand=True)
    vs.pack(side="left", fill="y")

    log_list = _debounced_logger(tree)

    def refresh(*_a) -> None:
        forms = ["All"] + P.form_groups_in_use()
        form_cb.configure(values=forms)
        if form_cb.get() not in forms:
            form_cb.set("All")
        year = year_cb.get()
        form = form_cb.get()
        try:
            rows = P.list_pupils(
                search=search_var.get(),
                year_group=int(year) if year != "All" else None,
                form_group=form if form != "All" else None,
                roll_status=_STATUS_FILTERS[status_cb.get()])
        except Exception as e:  # noqa: BLE001 - show, don't swallow
            logger.exception("Pupil list failed")
            activity_log.record("pupil.list", outcome="error", error=type(e).__name__)
            messagebox.showerror("Pupils", f"Could not load pupils:\n{e}",
                                 parent=parent.winfo_toplevel())
            return
        tree.delete(*tree.get_children())
        for p in rows:
            tree.insert("", "end", iid=str(p.pupil_id), values=(
                p.admission_no, p.display_name, p.year_group, p.form_group or "",
                p.date_of_birth, p.upn or "", p.sen_status, p.roll_status_label))
        count_var.set(f"{len(rows)} pupil{'s' if len(rows) != 1 else ''}")
        # Filters and result count only - never the text typed (see activity_log).
        log_list("pupil.search" if search_var.get().strip() else "pupil.list",
                 year=year, form=form, status=status_cb.get(), results=len(rows))

    def selected() -> int | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Pupils", "Select a pupil first.",
                                parent=parent.winfo_toplevel())
            return None
        return int(sel[0])

    def do_view() -> None:
        pid = selected()
        if pid is not None:
            open_profile(pid)

    def do_add() -> None:
        open_pupil_form(parent, principal=principal, pupil=None, on_saved=lambda _p: refresh())

    def do_edit() -> None:
        pid = selected()
        if pid is None:
            return
        pupil = P.get_pupil(pid)
        if pupil is None:
            refresh()
            return
        open_pupil_form(parent, principal=principal, pupil=pupil,
                        on_saved=lambda _p: refresh())

    def do_delete() -> None:
        pid = selected()
        if pid is not None and confirm_delete(parent, principal=principal, pupil_id=pid):
            refresh()

    buttons = ttk.Frame(parent)
    buttons.pack(fill="x", pady=(8, 0))
    ttk.Button(buttons, text="View profile", command=do_view).pack(side="left")
    if principal.can_edit_pupils:
        ttk.Button(buttons, text="Add pupil", command=do_add).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Edit", command=do_edit).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Delete", command=do_delete).pack(side="left", padx=(6, 0))
    from education_system.systems.secondary.modules.progression.domain import (
        sixth_form_progression as SFP,
    )
    if SFP.is_sender(principal):
        def do_move() -> None:
            pid = selected()
            pupil = P.get_pupil(pid) if pid is not None else None
            if pupil is None:
                return
            from education_system.systems.secondary.modules.progression.gui import (
                sixth_form_progression_views as SFV,
            )
            SFV.send_dialog(parent, principal=principal, pupil=pupil, after=refresh)

        ttk.Button(buttons, text="Move to Sixth Form", command=do_move).pack(
            side="left", padx=(6, 0))
    if not principal.can_edit_pupils:
        ttk.Label(buttons, text="Your account can view pupils but not change them.",
                  foreground="#777").pack(side="left", padx=(12, 0))
    ttk.Button(buttons, text="↻ Refresh", command=refresh).pack(side="right")

    tree.bind("<Double-1>", lambda _e: do_view())
    tree.bind("<Return>", lambda _e: do_view())
    search_var.trace_add("write", refresh)
    for cb in (year_cb, form_cb, status_cb):
        cb.bind("<<ComboboxSelected>>", refresh)
    refresh()
    if focus_search:
        search.focus_set()


# ── Profile ──────────────────────────────────────────────────────────

def _draw_enrolment_section(parent: ttk.Frame, pupil: P.Pupil, *, principal: Principal,
                            on_changed: Callable[[], None]) -> None:
    """Leaving actions + leaving history, for staff who may use Enrolment & Leavers
    (it holds exclusion / missing-education details, so others see nothing)."""
    from education_system.systems.secondary.modules.pupils.domain import enrolment as EN
    if not principal.can_open(EN.MENU_LABEL):
        return
    from education_system.systems.secondary.modules.pupils.gui import enrolment_views as EV
    box = ttk.LabelFrame(parent, text="Enrolment & leaving", padding=8)
    box.pack(fill="x", pady=(8, 0))
    bar = ttk.Frame(box)
    bar.pack(fill="x")
    if pupil.roll_status == "on_roll":
        ttk.Label(bar, text=f"On roll since {pupil.admission_date}.").pack(side="left")
        ttk.Button(bar, text="Record as leaver…", command=lambda: EV.record_leaver_dialog(
            parent, principal=principal, pupil=pupil, after=on_changed)).pack(side="right")
    else:
        todo = EN.LeaverView(pupil, EN.current_leaving(pupil.pupil_id)).actions()
        ttk.Label(bar, text=("Still to do: " + "; ".join(todo)) if todo
                  else "Leaving follow-up complete.",
                  foreground="#a60" if todo else "#060", wraplength=700,
                  justify="left").pack(side="left")
        ttk.Button(bar, text="Reinstate…", command=lambda: EV.reinstate_dialog(
            parent, principal=principal, pupil_id=pupil.pupil_id, after=on_changed)).pack(
            side="right")
        ttk.Button(bar, text="Leaving details…", command=lambda: EV.details_dialog(
            parent, principal=principal, pupil_id=pupil.pupil_id, after=on_changed)).pack(
            side="right", padx=(0, 6))
    from education_system.systems.secondary.modules.pupils.domain import alumni as AL
    if principal.can_open(AL.MENU_LABEL):
        alum = AL.for_pupil(pupil.pupil_id)
        if alum is not None:
            ttk.Label(box, text=f"Alumni record {alum.alumni_ref} ({alum.status_label}) - "
                                "see Alumni.", foreground="#555").pack(anchor="w", pady=(4, 0))
        elif pupil.roll_status == "left":
            def to_alumni() -> None:
                try:
                    a = AL.add_from_pupil(pupil.pupil_id, actor=principal)
                except (AL.ValidationError, AL.PermissionDenied, AL.NotFound) as e:
                    messagebox.showerror("Alumni", "\n".join(getattr(e, "problems", [str(e)])),
                                         parent=parent)
                    return
                messagebox.showinfo("Alumni", f"Added as {a.alumni_ref}. Add their personal "
                                    "e-mail and consent in Alumni.", parent=parent)
                on_changed()

            ttk.Button(bar, text="Add to alumni", command=to_alumni).pack(
                side="right", padx=(0, 6))
    for lv in EN.leaving_history(pupil.pupil_id):
        dest = lv.post16_destination or lv.destination_school or ""
        line = f"Left {lv.leaving_date}: {lv.reason}" + (f" → {dest}" if dest else "")
        if lv.status == "reinstated":
            line += (f"  (back on roll {(lv.reinstated_at or '')[:10]}"
                     f"{': ' + lv.reinstate_note if lv.reinstate_note else ''})")
        ttk.Label(box, text=line, foreground="#555", wraplength=900,
                  justify="left").pack(anchor="w", pady=(4, 0))


def _draw_teaching_groups(parent: ttk.Frame, pupil: P.Pupil) -> None:
    """This year's teaching groups (read-only; changed in Teaching Groups)."""
    if pupil.roll_status != "on_roll":
        return
    box = ttk.LabelFrame(parent, text="Teaching groups this year", padding=8)
    box.pack(fill="x", pady=(8, 0))
    try:
        from education_system.systems.secondary.modules.curriculum.domain import (
            teaching_groups as TG,
        )
        groups = TG.groups_for_pupil(pupil.pupil_id)
    except Exception:
        logger.exception("Teaching groups on profile failed")
        ttk.Label(box, text="Couldn't read teaching groups.", foreground="#a00").pack(anchor="w")
        return
    if not groups:
        ttk.Label(box, text="Not in any teaching group yet.", foreground="#888").pack(anchor="w")
        return
    ttk.Label(box, text="; ".join(
        f"{i.subject.name}: {i.group.code}" + (f" ({i.group.teacher_name})"
                                              if i.group.teacher_name else "")
        for i in groups), wraplength=1000, justify="left").pack(anchor="w")


def _draw_attendance(parent: ttk.Frame, pupil: P.Pupil) -> None:
    """This year's attendance figures (marks are changed in Registers & Attendance)."""
    box = ttk.LabelFrame(parent, text="Attendance this year", padding=8)
    box.pack(fill="x", pady=(8, 0))
    try:
        from education_system.systems.secondary.modules.attendance.domain import attendance as AT
        s = AT.pupil_summary(pupil.pupil_id)
    except Exception:
        logger.exception("Attendance on profile failed")
        ttk.Label(box, text="Couldn't read attendance.", foreground="#a00").pack(anchor="w")
        return
    if s.attendance_pct is None:
        ttk.Label(box, text="No marks this year.", foreground="#888").pack(anchor="w")
        return
    ttk.Label(box, text=(f"{s.attendance_pct}% of {s.possible} possible sessions · "
                         f"authorised absence {s.authorised} · unauthorised {s.unauthorised}"
                         f" · late {s.late}" + (f" · {s.band.upper()} ABSENCE" if s.band
                                                else "")),
              foreground="#a00" if s.band else "").pack(anchor="w")


def _draw_homework(parent: ttk.Frame, pupil: P.Pupil) -> None:
    """This year's homework (work is recorded in Homework)."""
    box = ttk.LabelFrame(parent, text="Homework this year", padding=8)
    box.pack(fill="x", pady=(8, 0))
    try:
        from education_system.systems.secondary.modules.curriculum.domain import homework as HW
        s = HW.pupil_summary(pupil.pupil_id)
    except Exception:
        logger.exception("Homework on profile failed")
        ttk.Label(box, text="Couldn't read homework.", foreground="#a00").pack(anchor="w")
        return
    if not s.set:
        ttk.Label(box, text="No homework due yet this year.", foreground="#888").pack(
            anchor="w")
        return
    ttk.Label(box, text=(f"{s.handed_in} of {s.set} handed in"
                         + (f" ({s.completion_pct}%)" if s.completion_pct is not None else "")
                         + f" · late {s.late} · missing {s.missing} · excused {s.excused}"
                         + (f" · average mark {s.average_pct}%" if s.average_pct is not None
                            else "")),
              foreground="#a00" if s.missing else "").pack(anchor="w")


def _draw_options(parent: ttk.Frame, pupil: P.Pupil) -> None:
    """Their Year 9 options, if they've chosen (managed in Year 9 Options)."""
    try:
        from education_system.systems.secondary.modules.curriculum.domain import options as OP
        rows = OP.for_pupil(pupil.pupil_id)
    except Exception:
        logger.exception("Options on profile failed")
        return
    if not rows:
        return
    box = ttk.LabelFrame(parent, text="Options", padding=8)
    box.pack(fill="x", pady=(8, 0))
    for r, x, alloc in rows[:2]:
        text = (f"{r.name} ({r.status}): "
                + (", ".join(f"block {a.block} {a.name}" + (" (reserve)" if a.from_reserve
                                                             else "") for a in alloc)
                   if alloc else f"chose {x.label}"))
        ttk.Label(box, text=text, wraplength=900, justify="left").pack(anchor="w")


def _draw_clubs(parent: ttk.Frame, pupil: P.Pupil) -> None:
    """Clubs they're in or waiting for (managed in Enrichment & Clubs)."""
    try:
        from education_system.systems.secondary.modules.curriculum.domain import enrichment as EN
        rows = [m for m in EN.for_pupil(pupil.pupil_id)
                if m.status in ("Active", "Waitlisted", "Suspended")]
    except Exception:
        logger.exception("Clubs on profile failed")
        return
    if not rows:
        return
    box = ttk.LabelFrame(parent, text="Clubs", padding=8)
    box.pack(fill="x", pady=(8, 0))
    ttk.Label(box, text="; ".join(m.club_name + ("" if m.status == "Active"
                                                 else f" ({m.status.lower()})")
                                  for m in rows), wraplength=900, justify="left").pack(
        anchor="w")


def _draw_library(parent: ttk.Frame, pupil: P.Pupil) -> None:
    """Library books out and reservations (managed in Library)."""
    try:
        from education_system.systems.secondary.modules.library.domain import library as LB
        info = LB.for_pupil(pupil.pupil_id)
    except Exception:
        logger.exception("Library on profile failed")
        return
    if not info["out"] and not info["holds"]:
        return
    box = ttk.LabelFrame(parent, text="Library", padding=8)
    box.pack(fill="x", pady=(8, 0))
    for x in info["out"]:
        ttk.Label(box, text=f"{x.book_title} ({x.barcode}) - "
                            + (f"OVERDUE by {x.days_overdue} day(s)" if x.days_overdue
                               else f"due {x.due_date}"),
                  foreground="#a00" if x.days_overdue else "").pack(anchor="w")
    for h in info["holds"]:
        ttk.Label(box, text=f"Reserved: {h.book_title}"
                            + (f" - ready to collect by {h.expires_on}" if h.status == "Ready"
                               else "")).pack(anchor="w")


def _draw_interventions(parent: ttk.Frame, pupil: P.Pupil, *, principal: Principal) -> None:
    """Open interventions and the last few closed ones (managed in Interventions)."""
    from education_system.systems.secondary.core.permissions.access import STAFF_ROLES
    if principal.role not in STAFF_ROLES:
        return
    try:
        from education_system.systems.secondary.modules.assessment.domain import interventions as IV
        rows = IV.for_pupil(pupil.pupil_id)
    except Exception:
        logger.exception("Interventions on profile failed")
        return
    if not rows:
        return
    shown = [r for r in rows if r.is_open] + [r for r in rows if not r.is_open][:3]
    box = ttk.LabelFrame(parent, text="Interventions", padding=8)
    box.pack(fill="x", pady=(8, 0))
    for r in shown:
        text = (f"{r.intervention_type}" + (f" in {r.subject_code}" if r.subject_code else "")
                + f" - {r.status}" + (f" ({r.outcome})" if r.outcome else "")
                + f", from {r.start_date}" + (f", led by {r.led_by}" if r.led_by else "")
                + (f" · {r.baseline_grade or '-'}→{r.current_grade or '-'}"
                   f" (target {r.target_grade or '-'})" if r.subject_id else ""))
        ttk.Label(box, text=text, foreground="" if r.is_open else "#777",
                  wraplength=900, justify="left").pack(anchor="w")


def _draw_reports(parent: ttk.Frame, pupil: P.Pupil, *, principal: Principal) -> None:
    """Reports to parents and where each has got to (managed in Reports to Parents)."""
    from education_system.systems.secondary.core.permissions.access import STAFF_ROLES
    if principal.role not in STAFF_ROLES:
        return
    try:
        from education_system.systems.secondary.modules.assessment.domain import (
            reports_to_parents as RP,
        )
        rows = RP.for_pupil(pupil.pupil_id)[:4]
    except Exception:
        logger.exception("Reports on profile failed")
        return
    if not rows:
        return
    box = ttk.LabelFrame(parent, text="Reports to parents", padding=8)
    box.pack(fill="x", pady=(8, 0))
    for x in rows:
        r = x["report"]
        text = f"{x['cycle'].title}: {r.status}"
        if r.status == "Issued":
            text += f" {(r.issued_at or '')[:10]}" + (
                f", seen {(r.first_viewed_at or '')[:10]}" if r.first_viewed_at
                else ", not opened yet") + (" (acknowledged)" if r.acknowledged_at else "")
        ttk.Label(box, text=text).pack(anchor="w")


def _draw_tutor_contacts(parent: ttk.Frame, pupil: P.Pupil, *, principal: Principal) -> None:
    """Their tutors this year and recent tutor meetings about them (Form Tutors).
    Meeting notes show only to those who may see that form's meetings."""
    from education_system.systems.secondary.core.permissions.access import STAFF_ROLES
    if principal.role not in STAFF_ROLES:
        return
    try:
        from education_system.systems.secondary.modules.curriculum.domain import form_tutors as FT
        info = FT.for_pupil(pupil.pupil_id)
        seen = {m.meeting_id for m in FT.list_meetings(actor=principal,
                                                       pupil_id=pupil.pupil_id)}
    except Exception:
        logger.exception("Tutor contacts on profile failed")
        return
    meetings = [m for m in info["meetings"] if m.meeting_id in seen][:5]
    if not info["tutors"] and not meetings:
        return
    box = ttk.LabelFrame(parent, text="Form tutor", padding=8)
    box.pack(fill="x", pady=(8, 0))
    if info["tutors"]:
        ttk.Label(box, text=" · ".join(f"{a.role}: {a.tutor_name}" for a in info["tutors"])
                  ).pack(anchor="w")
    for m in meetings:
        ttk.Label(box, text=f"{m.meeting_date} {m.meeting_type}"
                            + (f" - {m.agenda.splitlines()[0][:80]}" if m.agenda else ""),
                  foreground="#555").pack(anchor="w")


def _draw_behaviour(parent: ttk.Frame, pupil: P.Pupil, *, principal: Principal) -> None:
    """This year's behaviour points, house, rewards and latest entries
    (managed in Behaviour & Rewards)."""
    from education_system.systems.secondary.core.permissions.access import STAFF_ROLES
    if principal.role not in STAFF_ROLES:
        return
    try:
        from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
        s = BH.pupil_summary(pupil.pupil_id, academic_year=BH.current_year())
    except Exception:
        logger.exception("Behaviour on profile failed")
        return
    if not s["incidents"] and not s["house"]:
        return
    box = ttk.LabelFrame(parent, text="Behaviour & rewards", padding=8)
    box.pack(fill="x", pady=(8, 0))
    ttk.Label(box, text=f"{s['positive']} positive · {s['negative']} negative · net "
                        f"{s['total_points']:+d} points"
                        + (f" · {s['house'].name}" if s["house"] else "")
                        + (" · " + ", ".join(m["level"] for m in reversed(s["milestones"]))
                           if s["milestones"] else "")).pack(anchor="w")
    for e in [x for x in s["incidents"] if x.counts][:5]:
        ttk.Label(box, text=f"{e.entry_date} {e.incident_type} {e.points:+d} - "
                            f"{e.description[:70]}",
                  foreground="#2e7d32" if e.polarity == "positive" else "#a33").pack(
            anchor="w")


def _draw_detentions(parent: ttk.Frame, pupil: P.Pupil, *, principal: Principal) -> None:
    """This year's detentions: what's coming up and what was missed
    (managed in Detentions)."""
    from education_system.systems.secondary.core.permissions.access import STAFF_ROLES
    if principal.role not in STAFF_ROLES:
        return
    try:
        from education_system.systems.secondary.modules.behaviour.domain import detentions as DT
        s = DT.pupil_summary(pupil.pupil_id, academic_year=DT.current_year())
    except Exception:
        logger.exception("Detentions on profile failed")
        return
    if not s["total"]:
        return
    box = ttk.LabelFrame(parent, text="Detentions (this year)", padding=8)
    box.pack(fill="x", pady=(8, 0))
    ttk.Label(box, text=f"{s['total']} detention(s) · attended {s['attended']} · missed "
                        f"{s['missed']} · excused {s['excused']} · "
                        f"{s['minutes_served']} minutes served").pack(anchor="w")
    for d in s["upcoming"][:3]:
        ttk.Label(box, text=f"Coming up: {d.when} {d.detention_type} - {d.reason[:70]}").pack(
            anchor="w")
    for d in [x for x in s["detentions"] if x.status == "Missed"][:3]:
        ttk.Label(box, text=f"Missed: {d.when} {d.detention_type} - not yet rescheduled",
                  foreground="#a33").pack(anchor="w")


def _draw_exclusions(parent: ttk.Frame, pupil: P.Pupil, *, principal: Principal) -> None:
    """Suspensions and exclusions (managed in Suspensions & Exclusions)."""
    from education_system.systems.secondary.core.permissions.access import STAFF_ROLES
    if principal.role not in STAFF_ROLES:
        return
    try:
        from education_system.systems.secondary.modules.behaviour.domain import exclusions as EX
        s = EX.case_summary(pupil.pupil_id)
    except Exception:
        logger.exception("Exclusions on profile failed")
        return
    if not s["cases"]:
        return
    box = ttk.LabelFrame(parent, text="Suspensions & exclusions", padding=8)
    box.pack(fill="x", pady=(8, 0))
    ttk.Label(box, text=f"This year: {s['suspensions']} suspension(s), {s['suspension_days']} "
                        f"school day(s) - {s['days_left']} left of {EX.MAX_SUSPENSION_DAYS}"
              ).pack(anchor="w")
    if s["permanent"]:
        ttk.Label(box, text=f"Permanent exclusion from {s['permanent'].start_date} "
                            f"({s['permanent'].status})", foreground="#a33").pack(anchor="w")
    for c in s["open"][:3]:
        ttk.Label(box, text=f"Open: #{c.case_id} {c.case_type} {c.period} - {c.reason[:60]}"
                  ).pack(anchor="w")


def _draw_gradebook(parent: ttk.Frame, pupil: P.Pupil) -> None:
    """This year's marks by subject (managed in Gradebook)."""
    try:
        from education_system.systems.secondary.modules.assessment.domain import gradebook as GB
        rows = GB.pupil_overview(pupil.pupil_id)
    except Exception:
        logger.exception("Gradebook on profile failed")
        return
    if not rows:
        return
    box = ttk.LabelFrame(parent, text="Gradebook (this year)", padding=8)
    box.pack(fill="x", pady=(8, 0))
    for r in rows:
        last = r["latest"]
        ttk.Label(box, text=f"{r['subject_code']}: average "
                            + (f"{r['avg_pct']:g}%" if r["avg_pct"] is not None else "-")
                            + (f", latest grade {r['latest_grade']}" if r["latest_grade"]
                               else "")
                            + f" · {r['count']} mark(s), last: {last.assessment_name} "
                              f"({last.marks_label})",
                  foreground="#a00" if r["avg_pct"] is not None and r["avg_pct"] < 40
                  else "").pack(anchor="w")


def _draw_assessment_points(parent: ttk.Frame, pupil: P.Pupil) -> None:
    """The latest assessment point's grades (managed in Assessment Points)."""
    try:
        from education_system.systems.secondary.modules.assessment.domain import (
            assessment_points as AP,
        )
        found = AP.for_pupil(pupil.pupil_id)
    except Exception:
        logger.exception("Assessment points on profile failed")
        return
    if not found:
        return
    pt, rows = found
    box = ttk.LabelFrame(parent, text=f"Assessment point: {pt.name} ({pt.academic_year}, "
                                      f"{pt.status.lower()})", padding=8)
    box.pack(fill="x", pady=(8, 0))
    for x in rows:
        ttk.Label(box, text=f"{x.subject_code}: working at {x.working_at or '-'}"
                            + (f", predicted {x.predicted}" if x.predicted else "")
                            + (f", attitude {x.attitude} ({AP.ATTITUDE[x.attitude].lower()})"
                               if x.attitude else ""),
                  foreground="#a00" if x.attitude and x.attitude >= 3 else "").pack(anchor="w")


def _draw_targets(parent: ttk.Frame, pupil: P.Pupil) -> None:
    """Target grades and progress against them (managed in Target Grades)."""
    try:
        from education_system.systems.secondary.modules.assessment.domain import (
            target_grades as TGR,
        )
        rows = TGR.progress(pupil_id=pupil.pupil_id)
    except Exception:
        logger.exception("Target grades on profile failed")
        return
    if not rows:
        return
    box = ttk.LabelFrame(parent, text="Target grades", padding=8)
    box.pack(fill="x", pady=(8, 0))
    for r in rows:
        t = r["target"]
        ttk.Label(box, text=f"{t.subject_code}: target {t.target_grade}"
                            + (f" (min {t.minimum_grade}" if t.minimum_grade else "")
                            + (f", stretch {t.aspirational_grade}" if t.aspirational_grade
                               else "")
                            + (")" if t.minimum_grade else "")
                            + (f" · now {r['current']} - {r['status'].lower()}"
                               if r["current"] else ""),
                  foreground="#a00" if r["status"] in ("Below", "Well below") else ""
                  ).pack(anchor="w")


def _draw_mocks(parent: ttk.Frame, pupil: P.Pupil) -> None:
    """The latest mock series against target."""
    try:
        from education_system.systems.secondary.modules.examinations.gui import (
            mock_exams_views as MV,
        )
        MV.draw_profile_mocks(parent, pupil)
    except Exception:
        logger.exception("Mock exams section on profile failed")


def _draw_exam_entries(parent: ttk.Frame, pupil: P.Pupil) -> None:
    """Candidate number and live exam entries."""
    try:
        from education_system.systems.secondary.modules.examinations.gui import (
            exam_entries_views as EV,
        )
        EV.draw_profile_entries(parent, pupil)
    except Exception:
        logger.exception("Exam entries section on profile failed")


def _draw_exam_results(parent: ttk.Frame, pupil: P.Pupil, *, principal: Principal) -> None:
    """Exam results (embargoed series only for the exams officer)."""
    try:
        from education_system.systems.secondary.modules.examinations.gui import (
            exam_results_views as RV,
        )
        RV.draw_profile_results(parent, pupil, principal=principal)
    except Exception:
        logger.exception("Exam results section on profile failed")


def _draw_sixth_form(parent: ttk.Frame, pupil: P.Pupil, *, principal: Principal,
                     on_changed: Callable[[], None]) -> None:
    """SEN details and GCSE results (what moves on to the sixth form)."""
    try:
        from education_system.systems.secondary.modules.progression.gui import (
            sixth_form_progression_views as SFV,
        )
        SFV.draw_profile_sen(parent, pupil, principal=principal, on_changed=on_changed)
        SFV.draw_profile_gcses(parent, pupil, principal=principal, on_changed=on_changed)
    except Exception:
        logger.exception("SEN / GCSE sections on profile failed")


def draw_profile(parent: ttk.Frame, pupil_id: int, *, principal: Principal,
                 on_changed: Callable[[], None], on_deleted: Callable[[], None]) -> None:
    """One pupil's details and change history."""
    pupil = P.get_pupil(pupil_id)
    if pupil is None:
        activity_log.record("pupil.view", target=f"id:{pupil_id}", outcome="not_found")
        ttk.Label(parent, text="This pupil record no longer exists.",
                  foreground="#a00").pack(anchor="w")
        return
    activity_log.record("pupil.view", target=pupil.admission_no)

    head = ttk.Frame(parent)
    head.pack(fill="x", pady=(0, 8))
    ttk.Label(head, text=pupil.display_name, font=("", 16, "bold")).pack(side="left")
    ttk.Label(head, text=f"  {pupil.admission_no} · Year {pupil.year_group}"
                         f"{' · ' + pupil.form_group if pupil.form_group else ''}"
                         f" · {pupil.roll_status_label}",
              foreground="#555").pack(side="left", pady=(4, 0))
    if principal.can_edit_pupils:
        def edit() -> None:
            open_pupil_form(parent, principal=principal, pupil=P.get_pupil(pupil_id),
                            on_saved=lambda _p: on_changed())

        def delete() -> None:
            if confirm_delete(parent, principal=principal, pupil_id=pupil_id):
                on_deleted()

        ttk.Button(head, text="Delete", command=delete).pack(side="right")
        ttk.Button(head, text="Edit", command=edit).pack(side="right", padx=(0, 6))

    cols = ttk.Frame(parent)
    cols.pack(fill="x")
    cols.columnconfigure(0, weight=1, uniform="p")
    cols.columnconfigure(1, weight=1, uniform="p")

    def section(col: int, row: int, title: str, items: list[tuple[str, str]]) -> None:
        box = ttk.LabelFrame(cols, text=title, padding=10)
        box.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        for r, (k, v) in enumerate(items):
            ttk.Label(box, text=f"{k}:", foreground="#555").grid(
                row=r, column=0, sticky="nw", padx=(0, 10), pady=1)
            ttk.Label(box, text=v or "—", wraplength=320, justify="left").grid(
                row=r, column=1, sticky="w", pady=1)

    section(0, 0, "Identity", [
        ("Legal name", " ".join(x for x in (pupil.legal_first_name, pupil.middle_names,
                                             pupil.legal_last_name) if x)),
        ("Preferred name", pupil.preferred_name or ""),
        ("Date of birth", pupil.date_of_birth),
        ("Gender", pupil.gender),
        ("UPN", pupil.upn or "Not recorded"),
        ("Admission no.", pupil.admission_no),
    ])
    section(1, 0, "School", [
        ("Year group", f"Year {pupil.year_group}"),
        ("Form group", pupil.form_group or ""),
        ("Admission date", pupil.admission_date),
        ("Status", pupil.roll_status_label),
        ("Leaving date", pupil.leaving_date or ""),
        ("Leaving reason", pupil.leaving_reason or ""),
    ])
    section(0, 1, "Address", [
        ("Address", ", ".join(x for x in (pupil.address_line1, pupil.address_line2) if x)),
        ("Town", pupil.town or ""),
        ("Postcode", pupil.postcode or ""),
    ])
    section(1, 1, "Needs", [
        ("SEN", f"{pupil.sen_status} – {pupil.sen_label}"),
        ("Free school meals", "Eligible" if pupil.fsm_eligible else "Not eligible"),
        ("English as an additional language", "Yes" if pupil.eal else "No"),
        ("Notes", pupil.notes or ""),
    ])

    warning = P.year_group_warning(pupil.date_of_birth, pupil.year_group)
    if warning and pupil.roll_status == "on_roll":
        ttk.Label(parent, text=f"⚠ {warning}", foreground="#a60").pack(anchor="w", pady=(4, 0))
    from education_system.systems.secondary.modules.pupils.gui import profile_linked
    profile_linked.draw_safeguarding_flag(parent, pupil, principal=principal)

    _draw_teaching_groups(parent, pupil)
    _draw_attendance(parent, pupil)
    _draw_homework(parent, pupil)
    _draw_options(parent, pupil)
    _draw_clubs(parent, pupil)
    _draw_library(parent, pupil)
    _draw_gradebook(parent, pupil)
    _draw_assessment_points(parent, pupil)
    _draw_targets(parent, pupil)
    _draw_tutor_contacts(parent, pupil, principal=principal)
    _draw_behaviour(parent, pupil, principal=principal)
    _draw_detentions(parent, pupil, principal=principal)
    _draw_exclusions(parent, pupil, principal=principal)
    profile_linked.draw_linked(parent, pupil, principal=principal)
    _draw_interventions(parent, pupil, principal=principal)
    _draw_reports(parent, pupil, principal=principal)
    _draw_mocks(parent, pupil)
    _draw_exam_entries(parent, pupil)
    _draw_exam_results(parent, pupil, principal=principal)
    _draw_sixth_form(parent, pupil, principal=principal, on_changed=on_changed)

    from education_system.systems.secondary.modules.pupils.domain import pupil_accounts
    login = ttk.LabelFrame(parent, text="School login", padding=8)
    login.pack(fill="x", pady=(8, 0))
    account = pupil_accounts.get_for_pupil(pupil_id)
    if account is None:
        ttk.Label(login, text="No login or school e-mail yet.", foreground="#a60").pack(
            side="left")
        if principal.can_edit_pupils:
            ttk.Button(login, text="Create login", command=lambda: create_login(
                parent, principal=principal, pupil=pupil, on_done=on_changed)).pack(
                side="right")
    else:
        state = "" if account.status == "active" else "  (removed)"
        ttk.Label(login, text=f"Username: {account.username}    School e-mail: "
                              f"{account.school_email}    Created {account.created_at}"
                              f"{state}").pack(side="left")

    _draw_enrolment_section(parent, pupil, principal=principal, on_changed=on_changed)

    from education_system.systems.secondary.modules.communication.gui import contacts_views
    contacts_views.draw_contacts_section(parent, pupil, principal=principal,
                                         on_changed=on_changed).pack(fill="x", pady=(8, 0))

    hist =ttk.LabelFrame(parent, text="Change history", padding=8)
    hist.pack(fill="both", expand=True, pady=(8, 0))
    tree = ttk.Treeview(hist, columns=("at", "who", "what"), show="headings", height=6)
    for col, heading, width in (("at", "When", 150), ("who", "By", 110), ("what", "Change", 600)):
        tree.heading(col, text=heading)
        tree.column(col, width=width, anchor="w", stretch=col == "what")
    tree.pack(fill="both", expand=True)
    for h in P.history(pupil_id):
        tree.insert("", "end", values=(h["at"], h["actor"], _describe(h)))
    ttk.Label(parent, text=f"Created {pupil.created_at} by {pupil.created_by or '—'} · "
                           f"last changed {pupil.updated_at} by {pupil.updated_by or '—'}",
              foreground="#888").pack(anchor="w", pady=(4, 0))


def _describe(entry: dict) -> str:
    if entry["action"] == "create":
        return "Record created"
    try:
        detail = json.loads(entry["detail"] or "{}")
    except ValueError:
        detail = {}
    if entry["action"] == "delete":
        return f"Record deleted: {detail.get('reason', '')}"
    parts = []
    for field, change in sorted(detail.items()):
        if not isinstance(change, dict):
            continue
        name = field.replace("_", " ")
        parts.append(f"{name}: {change.get('from') or '—'} → {change.get('to') or '—'}")
    text = "; ".join(parts) or "Updated"
    if detail.get("_year_end_rollover"):
        text = f"Year-end rollover to {detail['_year_end_rollover']}: {text}"
    return text


def draw_pupil_picker(parent: ttk.Frame, *, on_pick: Callable[[int], None]) -> None:
    """Choose a pupil to open, when Pupil Profile is opened from the menu."""
    ttk.Label(parent, text="Pupil Profile", font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))
    ttk.Label(parent, text="Type part of a name, an admission number or a UPN, "
                           "then double-click the pupil.",
              foreground="#555").pack(anchor="w", pady=(0, 6))
    var = tk.StringVar()
    entry = ttk.Entry(parent, textvariable=var, width=40)
    entry.pack(anchor="w")
    box = tk.Listbox(parent, height=14, width=70)
    box.pack(anchor="w", pady=(6, 0), fill="x")
    ids: list[int] = []
    log_search = _debounced_logger(box)

    def refresh(*_a) -> None:
        box.delete(0, "end")
        ids.clear()
        if not var.get().strip():
            return
        found = P.list_pupils(search=var.get(), roll_status=None)
        log_search("pupil.search", status="All", results=len(found))
        for p in found[:200]:
            ids.append(p.pupil_id)
            box.insert("end", f"{p.display_name}  ·  {p.admission_no}  ·  Year {p.year_group}"
                              f"  ·  {p.roll_status_label}")

    def pick(_e=None) -> None:
        sel = box.curselection()
        if sel:
            on_pick(ids[sel[0]])

    var.trace_add("write", refresh)
    box.bind("<Double-1>", pick)
    box.bind("<Return>", pick)
    entry.focus_set()


# ── Add / edit form ──────────────────────────────────────────────────

def open_pupil_form(parent: tk.Misc, *, principal: Principal, pupil: P.Pupil | None,
                    on_saved: Callable[[P.Pupil], None]) -> tk.Toplevel | None:
    """Modal form to add a pupil (``pupil=None``) or edit one."""
    owner = parent.winfo_toplevel()
    if not principal.can_edit_pupils:
        activity_log.record("pupil.form.open", target=pupil.admission_no if pupil else "new",
                            outcome="denied")
        messagebox.showwarning("Pupils", "Your account can view pupils but not change them.",
                               parent=owner)
        return None
    editing = pupil is not None
    form_target = pupil.admission_no if editing else "new"
    activity_log.record("pupil.form.open", target=form_target,
                        mode="edit" if editing else "add")
    win = make_toplevel(owner)
    win.title(f"Edit {pupil.display_name}" if editing else "Add Pupil")
    window_sizing.fit(win, "900x720", (760, 600))
    win.transient(owner)

    from education_system.systems.secondary.ui.gui.layouts.scroll import scrolled_form
    body, footer = scrolled_form(win)
    body.columnconfigure(0, weight=1, uniform="f")
    body.columnconfigure(1, weight=1, uniform="f")

    vars_: dict[str, tk.Variable] = {}
    widgets: dict[str, object] = {}

    def value(name: str, default=""):
        return getattr(pupil, name) if editing else default

    def box(col: int, row: int, title: str) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(body, text=title, padding=10)
        frame.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        frame.columnconfigure(1, weight=1)
        return frame

    def entry(frame, r: int, label: str, name: str, *, required=False, width=28) -> None:
        ttk.Label(frame, text=label + (" *" if required else "")).grid(
            row=r, column=0, sticky="w", pady=2, padx=(0, 8))
        var = tk.StringVar(value=value(name) or "")
        ttk.Entry(frame, textvariable=var, width=width).grid(row=r, column=1, sticky="ew", pady=2)
        vars_[name] = var

    def combo(frame, r: int, label: str, name: str, values: list[str], current: str,
              *, required=False) -> ttk.Combobox:
        ttk.Label(frame, text=label + (" *" if required else "")).grid(
            row=r, column=0, sticky="w", pady=2, padx=(0, 8))
        cb = ttk.Combobox(frame, values=values, state="readonly", width=26)
        cb.set(current)
        cb.grid(row=r, column=1, sticky="w", pady=2)
        widgets[name] = cb
        return cb

    def date(frame, r: int, label: str, name: str, years, *, required=False) -> DatePicker:
        ttk.Label(frame, text=label + (" *" if required else "")).grid(
            row=r, column=0, sticky="w", pady=2, padx=(0, 8))
        dp = DatePicker(frame, value=value(name) or None, years=years)
        dp.grid(row=r, column=1, sticky="w", pady=2)
        widgets[name] = dp
        return dp

    import datetime as _dt
    this_year = _dt.date.today().year
    birth_years = [str(y) for y in range(this_year - 10, this_year - 19, -1)]

    ident = box(0, 0, "Identity")
    entry(ident, 0, "Legal first name", "legal_first_name", required=True)
    entry(ident, 1, "Middle names", "middle_names")
    entry(ident, 2, "Legal last name", "legal_last_name", required=True)
    entry(ident, 3, "Preferred name", "preferred_name")
    date(ident, 4, "Date of birth", "date_of_birth", birth_years, required=True)
    combo(ident, 5, "Gender", "gender", list(P.GENDERS), value("gender"), required=True)
    entry(ident, 6, "UPN", "upn")

    school = box(1, 0, "School")
    combo(school, 0, "Year group", "year_group", [str(y) for y in P.YEAR_GROUPS],
          str(value("year_group")) if editing else "", required=True)
    # Form: chosen from the forms set up for the year (Form Groups). A current form
    # that isn't set up stays in the list so editing doesn't drop it.
    from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
    year_cb = widgets["year_group"]
    current_form = (value("form_group") or "") if editing else ""
    form_row = ttk.Frame(school)
    ttk.Label(school, text="Form group").grid(row=1, column=0, sticky="w", pady=2, padx=(0, 8))
    form_row.grid(row=1, column=1, sticky="w", pady=2)
    form_cb = ttk.Combobox(form_row, state="readonly", width=12)
    form_cb.pack(side="left")
    form_hint = ttk.Label(form_row, foreground="#888")
    form_hint.pack(side="left", padx=(6, 0))
    widgets["form_group"] = form_cb

    def load_forms(_e=None) -> None:
        year = year_cb.get()  # type: ignore[union-attr]
        keep = current_form if editing and year == str(pupil.year_group) else ""
        try:
            names = FG.choices_for(year, keep)
            set_up = set(FG.names_for_year(int(year))) if year else set()
        except Exception:
            logger.exception("Loading form groups failed")
            names, set_up = ([keep] if keep else []), set()
        chosen = form_cb.get()
        form_cb.configure(values=[NO_FORM, *names])
        form_cb.set(chosen if chosen in names else keep if keep in names and keep else NO_FORM)
        if not year:
            form_hint.configure(text="choose the year group first")
        elif not set_up:
            form_hint.configure(text=f"no forms set up for Year {year} - see Form Groups")
        elif keep and keep not in set_up:
            form_hint.configure(text=f"{keep} isn't set up in Form Groups")
        else:
            form_hint.configure(text="")

    year_cb.bind("<<ComboboxSelected>>", load_forms)  # type: ignore[union-attr]
    load_forms()
    date(school, 2, "Admission date", "admission_date", recent_years(ahead=1, back=7))
    if not editing:
        widgets["admission_date"].set(_dt.date.today().isoformat())  # type: ignore[union-attr]
    status_cb = combo(school, 3, "Status", "roll_status",
                      [P.ROLL_STATUS_LABELS[s] for s in P.ROLL_STATUSES],
                      P.ROLL_STATUS_LABELS[value("roll_status", "on_roll")])
    leave_dp = date(school, 4, "Leaving date", "leaving_date", recent_years(ahead=1, back=7))
    reasons = list(P.LEAVING_REASONS)
    if editing and pupil.leaving_reason and pupil.leaving_reason not in reasons:
        reasons.append(pupil.leaving_reason)
    reason_cb = combo(school, 5, "Leaving reason", "leaving_reason", reasons,
                      value("leaving_reason") or "")

    def sync_leaving(*_a) -> None:
        left = status_cb.get() == P.ROLL_STATUS_LABELS["left"]
        state = "readonly" if left else "disabled"
        reason_cb.configure(state=state)
        for w in (leave_dp.cb_day, leave_dp.cb_month, leave_dp.cb_year):
            w.configure(state=state)

    status_cb.bind("<<ComboboxSelected>>", sync_leaving)
    sync_leaving()

    addr = box(0, 1, "Address")
    entry(addr, 0, "Address line 1", "address_line1")
    entry(addr, 1, "Address line 2", "address_line2")
    entry(addr, 2, "Town", "town")
    entry(addr, 3, "Postcode", "postcode", width=10)

    needs = box(1, 1, "Needs")
    sen_labels = [f"{k} – {v}" for k, v in P.SEN_STATUSES.items()]
    current_sen = value("sen_status", "N")
    combo(needs, 0, "SEN", "sen_status", sen_labels,
          f"{current_sen} – {P.SEN_STATUSES[current_sen]}")
    fsm = tk.BooleanVar(value=bool(value("fsm_eligible", False)))
    eal = tk.BooleanVar(value=bool(value("eal", False)))
    ttk.Checkbutton(needs, text="Eligible for free school meals",
                    variable=fsm).grid(row=1, column=0, columnspan=2, sticky="w", pady=2)
    ttk.Checkbutton(needs, text="English as an additional language",
                    variable=eal).grid(row=2, column=0, columnspan=2, sticky="w", pady=2)
    ttk.Label(needs, text="Notes").grid(row=3, column=0, sticky="nw", pady=(6, 0))
    notes = tk.Text(needs, height=4, width=30, wrap="word")
    notes.grid(row=3, column=1, sticky="ew", pady=(6, 0))
    notes.insert("1.0", value("notes") or "")

    # Parent / carer and medical / care notes: asked on Add Pupil (the same as
    # the primary school's). After that they live in the pupil's Contacts
    # section and on the Medical screen, so editing points there.
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    contact_vars: dict[str, tk.StringVar] = {}
    medical_text: tk.Text | None = None
    if not editing:
        family = box(0, 2, "Parent / carer")
        for r, (name, label) in enumerate((("full_name", "Name"),
                                           ("relationship", "Relationship"),
                                           ("phone", "Phone"), ("email", "E-mail"))):
            ttk.Label(family, text=label).grid(row=r, column=0, sticky="w", pady=2,
                                               padx=(0, 8))
            var = tk.StringVar()
            if name == "relationship":
                ttk.Combobox(family, textvariable=var, values=list(C.RELATIONSHIPS),
                             state="readonly", width=16).grid(row=r, column=1, sticky="w",
                                                              pady=2)
            else:
                ttk.Entry(family, textvariable=var, width=28).grid(
                    row=r, column=1, sticky="ew", pady=2)
            contact_vars[name] = var
        ttk.Label(family, text="Becomes the pupil's first contact (priority 1). "
                               "Give a phone number or an e-mail.",
                  foreground="#888", wraplength=360, justify="left").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(4, 0))
        medical = box(1, 2, "Medical")
        ttk.Label(medical, text="Medical / care notes").grid(row=0, column=0, sticky="nw",
                                                            pady=2, padx=(0, 8))
        medical_text = tk.Text(medical, height=4, width=30, wrap="word")
        medical_text.grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Label(medical, text="Added to the medical register; conditions, allergies "
                                "and medicines are then kept on the Medical screen.",
                  foreground="#888", wraplength=360, justify="left").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
    else:
        where = ttk.LabelFrame(body, text="Parent / carer and medical", padding=10)
        where.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
        ttk.Label(where, text="Parents / carers are edited in the Contacts section of "
                              "this pupil's profile; medical and care details on the "
                              "Medical screen.", foreground="#555", wraplength=820,
                  justify="left").pack(anchor="w")

    error_var = tk.StringVar()
    ttk.Label(footer, textvariable=error_var, foreground="#b00020", justify="left",
              wraplength=820).pack(side="top", anchor="w")

    def collect() -> dict:
        status_label = status_cb.get()
        status = next(k for k, v in P.ROLL_STATUS_LABELS.items() if v == status_label)
        data = {k: v.get() for k, v in vars_.items()}
        data.update({
            "date_of_birth": widgets["date_of_birth"].get(),  # type: ignore[union-attr]
            "gender": widgets["gender"].get(),  # type: ignore[union-attr]
            "year_group": widgets["year_group"].get(),  # type: ignore[union-attr]
            "form_group": "" if form_cb.get() in ("", NO_FORM) else form_cb.get(),
            "admission_date": widgets["admission_date"].get(),  # type: ignore[union-attr]
            "roll_status": status,
            "leaving_date": leave_dp.get() if status == "left" else "",
            "leaving_reason": reason_cb.get() if status == "left" else "",
            "sen_status": widgets["sen_status"].get()[:1],  # type: ignore[union-attr]
            "fsm_eligible": fsm.get(),
            "eal": eal.get(),
            "notes": notes.get("1.0", "end").strip(),
        })
        return data

    def save() -> None:
        data = collect()
        error_var.set("")
        warn = None
        if data["date_of_birth"] and data["year_group"]:
            warn = P.year_group_warning(data["date_of_birth"], int(data["year_group"]))
        changed_year = not editing or (str(pupil.year_group) != data["year_group"]
                                       or pupil.date_of_birth != data["date_of_birth"])
        if warn and changed_year and not messagebox.askyesno(
                "Check year group", f"{warn}\n\nSave anyway?", parent=win):
            activity_log.record("pupil.save", target=form_target,
                                outcome="cancelled_year_group_check")
            return
        try:
            FG.check_choice(data["year_group"], data["form_group"],
                            current_form if editing and data["year_group"] == str(
                                pupil.year_group) else None)
        except P.ValidationError as e:
            error_var.set("Please fix:\n• " + "\n• ".join(e.problems))
            return
        changed: list[str] = []
        extras_warnings: list[str] = []
        try:
            if editing:
                saved, changed = P.update_pupil_detailed(pupil.pupil_id, data,
                                                         actor=principal)
            else:
                contact = {k: v.get().strip() for k, v in contact_vars.items()}
                care = medical_text.get("1.0", "end").strip() if medical_text else ""
                try:
                    saved, extras_warnings = P.create_pupil_with_family(
                        data, actor=principal, contact=contact, medical_notes=care)
                except P.DuplicatePupil as dup:
                    if not messagebox.askyesno(
                            "Possible duplicate",
                            f"{dup}\n\nAdd this as a different pupil anyway?", parent=win):
                        activity_log.record("pupil.create", target=dup.existing.admission_no,
                                            outcome="cancelled_duplicate")
                        return
                    saved, extras_warnings = P.create_pupil_with_family(
                        data, actor=principal, contact=contact, medical_notes=care,
                        allow_duplicate=True)
        except P.ValidationError as e:
            error_var.set("Please fix:\n• " + "\n• ".join(e.problems))
            return
        except (P.PermissionDenied, P.NotFound) as e:
            messagebox.showerror("Pupils", str(e), parent=win)
            return
        except Exception as e:  # noqa: BLE001 - surface unexpected failures
            logger.exception("Saving pupil failed")
            messagebox.showerror("Pupils", f"Could not save the pupil:\n{e}", parent=win)
            return
        win.destroy()
        on_saved(saved)
        if extras_warnings:
            messagebox.showwarning("Pupil added", "\n\n".join(extras_warnings), parent=owner)
        if not editing:
            create_login(owner, principal=principal, pupil=saved,
                         intro=f"{saved.display_name} was added as {saved.admission_no}.",
                         on_done=lambda: on_saved(saved))
        elif changed:
            notify_updated(owner, principal=principal, pupil=saved, changed=changed)

    def cancel() -> None:
        activity_log.record("pupil.form.cancel", target=form_target)
        win.destroy()

    buttons = ttk.Frame(footer)
    buttons.pack(side="top", anchor="e", pady=(4, 0))
    ttk.Button(buttons, text="Cancel", command=cancel).pack(side="right")
    ttk.Button(buttons, text="Save" if editing else "Add pupil",
               command=save).pack(side="right", padx=(0, 6))
    win.bind("<Escape>", lambda _e: cancel())
    win.protocol("WM_DELETE_WINDOW", cancel)
    try:
        win.grab_set()
    except tk.TclError:
        pass
    return win


# ── Delete ───────────────────────────────────────────────────────────

def create_login(owner: tk.Misc, *, principal: Principal, pupil: P.Pupil, intro: str = "",
                 on_done: Callable[[], None] | None = None) -> None:
    """Create *pupil*'s login + school e-mail, deliver the welcome e-mail in the
    background, then show the sign-in details once."""
    from education_system.systems.secondary.modules.communication.gui import email_views
    from education_system.systems.secondary.modules.pupils.domain import pupil_accounts

    head = (intro + "\n\n") if intro else ""
    try:
        new = pupil_accounts.create_for_pupil(pupil.pupil_id, actor=principal)
    except Exception as e:  # noqa: BLE001
        logger.exception("Creating pupil login failed")
        messagebox.showerror("Pupil login", f"{head}The pupil's login could not be "
                                            f"created:\n{e}\n\nUse Create login on their "
                                            "profile to try again.", parent=owner)
        if on_done:
            on_done()
        return
    details = (f"{head}Login created:\n\n"
               f"    Username:      {new.account.username}\n"
               f"    Password:      {new.password}\n"
               f"    School e-mail: {new.account.school_email}\n\n"
               "Note the password now - it won't be shown again.")

    def finish(report, err) -> None:
        if new.welcome_error:
            mail = f"The welcome e-mail could not be prepared: {new.welcome_error}"
        elif err:
            mail = f"The welcome e-mail was saved but delivery failed: {err}"
        else:
            mail = "Welcome e-mail: " + email_views._report_text(report) + "."
        messagebox.showinfo("Pupil login", f"{details}\n\n{mail}", parent=owner)
        if on_done:
            on_done()

    if new.welcome_message_id is None:
        finish(None, None)
    else:
        email_views.deliver_in_background(owner, new.welcome_message_id, principal, finish)


def notify_updated(owner: tk.Misc, *, principal: Principal, pupil: P.Pupil,
                   changed: list[str]) -> None:
    """E-mail the pupil that their record changed (delivered in the background)."""
    from education_system.systems.secondary.modules.communication.gui import email_views
    from education_system.systems.secondary.modules.pupils.domain import pupil_accounts

    message_id, note = pupil_accounts.notify_record_updated(pupil.pupil_id, changed,
                                                            actor=principal)
    if message_id is None:
        if note.startswith("the e-mail could not"):
            messagebox.showerror("Pupils", f"Saved, but {note}", parent=owner)
        return

    def finish(report, err) -> None:
        if err:
            messagebox.showerror("Pupils", "Saved. The update e-mail to the pupil was saved "
                                           f"but delivery failed:\n{err}", parent=owner)
        else:
            messagebox.showinfo("Pupils", f"Saved. Update e-mail to {pupil.display_name}: "
                                          f"{email_views._report_text(report)}.", parent=owner)

    email_views.deliver_in_background(owner, message_id, principal, finish)


def confirm_delete(parent: tk.Misc, *, principal: Principal, pupil_id: int) -> bool:
    """Ask for confirmation and a reason, then delete. True if deleted."""
    owner = parent.winfo_toplevel()
    pupil = P.get_pupil(pupil_id)
    if pupil is None:
        return True
    if not principal.can_edit_pupils:
        activity_log.record("pupil.delete", target=pupil.admission_no, outcome="denied")
        messagebox.showwarning("Pupils", "Your account can view pupils but not change them.",
                               parent=owner)
        return False
    if not messagebox.askyesno(
            "Delete pupil record",
            f"Delete the record for {pupil.full_name} ({pupil.admission_no})?\n\n"
            "Delete is only for records created in error. If the pupil has left "
            "the school, edit the record and set the status to Left instead - "
            "that keeps their history.", icon="warning", parent=owner):
        activity_log.record("pupil.delete", target=pupil.admission_no, outcome="cancelled")
        return False
    reason = simpledialog.askstring(
        "Reason for deleting", "Why is this record being deleted?", parent=owner)
    if reason is None:
        activity_log.record("pupil.delete", target=pupil.admission_no, outcome="cancelled")
        return False
    try:
        P.delete_pupil(pupil_id, actor=principal, reason=reason)
    except P.ValidationError as e:
        messagebox.showwarning("Not deleted", str(e), parent=owner)
        return False
    except Exception as e:  # noqa: BLE001
        logger.exception("Deleting pupil failed")
        messagebox.showerror("Pupils", f"Could not delete the pupil:\n{e}", parent=owner)
        return False
    messagebox.showinfo("Deleted", f"The record for {pupil.full_name} was deleted.",
                        parent=owner)
    return True
