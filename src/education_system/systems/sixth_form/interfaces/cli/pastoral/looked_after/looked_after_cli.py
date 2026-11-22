"""CLI: Looked-After Children & Care Leavers register."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.pastoral._records import Col, today
from education_system.systems.sixth_form.domain.pastoral.looked_after import (
    looked_after as data,
)
from education_system.systems.sixth_form.domain.pastoral.wellbeing import (
    wellbeing as _wb,
)
from education_system.systems.sixth_form.interfaces.cli.pastoral import _records_cli as ui

_CARE_COLS = [c for c in _wb.CARE_SPEC.cols if c.name != "designated_teacher"]
_CARE_COLS.append(Col("designated_teacher_id",
                      "Designated teacher staff id (blank = current)"))


def _pick_record(**filters):
    rows = data.list_care_records(**filters)
    ui.print_rows(rows, ui.spec_columns(_wb.CARE_SPEC))
    return ui.pick_row(rows, lambda r: r.record_id, "care record")


def list_records() -> None:
    ui.print_rows(data.list_care_records(active_only=ui.yes_no(
        "Current only?", True)), ui.spec_columns(_wb.CARE_SPEC))
    ui.pause()


def new_record() -> None:
    rec = data.create_care_record(ui.prompt_fields(_CARE_COLS))
    print(f"\n  ✓ Saved care record #{rec.record_id}.")
    ui.pause()


def edit_record() -> None:
    rec = _pick_record()
    data.update_care_record(rec.record_id,
                            ui.prompt_fields(_CARE_COLS, existing=rec))
    print("\n  ✓ Updated.")
    ui.pause()


def delete_record() -> None:
    rec = _pick_record()
    if ui.yes_no(f"Delete care record #{rec.record_id}?"):
        data.delete_care_record(rec.record_id)
        print("\n  ✓ Deleted.")
    ui.pause()


def care_file() -> None:
    rec = _pick_record()
    print()
    print(data.care_file_text(rec.record_id))
    ui.pause()


def record_pep() -> None:
    rec = _pick_record(active_only=True)
    v = ui.prompt_fields(_wb.PEP_SPEC.cols,
                         initial={"record_id": rec.record_id})
    actions = []
    while ui.yes_no("Add an agreed action?", not actions):
        actions.append(ui.prompt_fields(
            [c for c in data.PEP_ACTION_SPEC.cols
             if c.name in ("action", "area", "owner", "due_date")]))
    r = data.record_pep_review({**v, "record_id": rec.record_id},
                               actions=actions)
    print(f"\n  ✓ PEP review #{r.review_id} saved with "
          f"{len(actions)} action(s).")
    ui.pause()


def pep_reviews() -> None:
    rec = _pick_record()
    ui.run_menu(f"PEP reviews — care record #{rec.record_id}", ui.crud_items(
        "PEP review", _wb.PEP_SPEC,
        load=lambda: _wb.list_pep_reviews(rec.record_id),
        create=data.record_pep_review, update=_wb.update_pep_review,
        delete=_wb.delete_pep_review,
        new_initial=lambda: {"record_id": rec.record_id}))


def pep_actions() -> None:
    ui.run_menu("PEP actions", [
        *ui.crud_items("PEP action", data.PEP_ACTION_SPEC,
                       load=lambda: data.list_pep_actions(open_only=True),
                       create=data.add_pep_action,
                       update=data.update_pep_action,
                       delete=data.delete_pep_action),
        ("Close an action", close_action),
        ("Overdue actions", overdue_actions),
    ])


def close_action() -> None:
    rows = data.list_pep_actions(open_only=True)
    ui.print_rows(rows, ui.spec_columns(data.PEP_ACTION_SPEC))
    a = ui.pick_row(rows, lambda r: r.action_id, "action")
    status = ui.pick_from("Outcome", [s for s in data.PEP_ACTION_STATUSES
                                      if s != data.OPEN],
                          default="Completed")
    data.complete_pep_action(a.action_id, status=status,
                             outcome=ui.ask_multiline("Notes"))
    print("\n  ✓ Closed.")
    ui.pause()


def overdue_actions() -> None:
    ui.print_rows(data.list_pep_actions(overdue_only=True),
                  ui.spec_columns(data.PEP_ACTION_SPEC),
                  empty="(no PEP actions overdue)")
    ui.pause()


def pep_due() -> None:
    days = ui.ask("Due within how many days",
                  default=str(data.DEFAULT_DUE_SOON_DAYS))
    rows = data.pep_due_list(within_days=int(days) if days.isdigit()
                             else data.DEFAULT_DUE_SOON_DAYS)
    ui.print_rows(rows, (
        ("Care#", lambda r: r.record_id, 5),
        ("Student", lambda r: r.student_id, 9),
        ("Name", lambda r: r.student_name, 20),
        ("State", lambda r: r.state, 15),
        ("Days", lambda r: r.days, 5),
        ("Next PEP", lambda r: r.next_pep_due, 10),
        ("LA", lambda r: r.local_authority, 12),
        ("Virtual school", lambda r: r.virtual_school_contact, 16),
        ("Late acts", lambda r: r.overdue_actions, 9),
    ), empty="(no PEP reviews due)")
    ui.pause()


def leaver_plans() -> None:
    ui.run_menu("Care-leaver support plans", ui.crud_items(
        "leaver plan", data.LEAVER_PLAN_SPEC,
        load=lambda: data.list_leaver_plans(active_only=True),
        create=data.create_leaver_plan, update=data.update_leaver_plan,
        delete=data.delete_leaver_plan))


def bursary_gaps() -> None:
    ui.print_rows(data.bursary_gaps(), (
        ("Student", lambda r: r.student_id, 9),
        ("Name", lambda r: r.student_name, 20),
        ("Care status", lambda r: r.care_status, 26),
        ("Bursary category", lambda r: r.expected_category, 28),
        ("Note", lambda r: r.note, 40),
    ), empty="(every current LAC / care leaver has a bursary application)")
    ui.pause()


def designated_teacher() -> None:
    appt = data.current_designated_teacher()
    print(f"\n  Current designated teacher: "
          f"{appt.staff_id if appt else '(none)'}")
    ui.print_rows(data.list_appointments(),
                  ui.spec_columns(data.APPOINTMENT_SPEC))
    if ui.yes_no("Appoint a new designated teacher?"):
        a = data.appoint_designated_teacher(
            ui.ask("Staff id", required=True),
            start_date=ui.ask("From (YYYY-MM-DD)", default=today()),
            notes=ui.ask("Notes"))
        print(f"\n  ✓ Appointed {a.staff_id} from {a.start_date}.")
    ui.pause()


def summary() -> None:
    s = data.summary()
    print("\n═══ Looked-after children & care leavers ═══")
    print(f"  Designated teacher:       {s.designated_teacher or '(none)'}")
    for k, n in s.by_status.items():
        print(f"    {k:<32} {n}")
    print(f"  PEP reviews overdue:      {s.peps_overdue}")
    print(f"  LAC with no PEP:          {s.no_pep}")
    print(f"  PEP actions open/overdue: {s.actions_open}/{s.actions_overdue}")
    print(f"  Leaver plans active:      {s.leaver_plans_active} "
          f"({s.leaver_reviews_overdue} review overdue)")
    print(f"  No vulnerable bursary:    {s.bursary_gaps}")
    ui.pause()


def run() -> None:
    ui.run_menu("Looked-After Children & Care Leavers", [
        ("── Register ──", None),
        ("List care records", list_records),
        ("Care file (one learner)", care_file),
        ("New care record", new_record),
        ("Edit care record", edit_record),
        ("Delete care record", delete_record),
        ("── PEPs ──", None),
        ("PEP reviews due / overdue", pep_due),
        ("Record PEP review (+ actions)", record_pep),
        ("PEP reviews for a record", pep_reviews),
        ("PEP actions", pep_actions),
        ("── Care leavers ──", None),
        ("Care-leaver support plans", leaver_plans),
        ("No vulnerable bursary application", bursary_gaps),
        ("── Other ──", None),
        ("Designated teacher", designated_teacher),
        ("Summary", summary),
    ])


def looked_after_menu() -> None:
    """Entry point for the main CLI menu."""
    run()
