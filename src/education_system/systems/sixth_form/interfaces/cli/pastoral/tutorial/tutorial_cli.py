"""CLI: Tutorial & PSHE programme and personal-tutor 1:1s."""

from __future__ import annotations

import datetime as _dt

from education_system.systems.sixth_form.domain.pastoral._records import today
from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
    tutor_groups as _tg,
)
from education_system.systems.sixth_form.domain.pastoral.tutorial import (
    tutorial as data,
)
from education_system.systems.sixth_form.interfaces.cli.pastoral import _records_cli as ui


def _year() -> str:
    return ui.ask("Academic year", default=data.current_academic_year())


def _pick_topic():
    rows = data.list_topics(academic_year=_year())
    ui.print_rows(rows, ui.spec_columns(data.TOPIC_SPEC))
    return ui.pick_row(rows, lambda r: r.topic_id, "topic")


def _pick_group(allow_blank: bool = True) -> int | None:
    groups = _tg.list_groups()
    if not groups:
        print("    No tutor groups.")
        return None
    labels = [f"{g.tutor_group_id} — {g.name}" for g in groups]
    pick = ui.pick_from("Tutor group", labels, allow_blank=allow_blank)
    return int(pick.split(" — ")[0]) if pick else None


def _session_cols():
    return (("#", lambda d: d.delivery_id, 5),
            ("Group", lambda d: d.group_name, 8),
            ("Topic", lambda d: d.topic_title, 30),
            ("Status", lambda d: d.status, 9),
            ("Planned", lambda d: d.planned_date, 10),
            ("Delivered", lambda d: d.delivered_on, 10),
            ("Present", lambda d: f"{d.present}/{d.marked}"
             if d.marked else "", 7))


def plan_groups() -> None:
    t = _pick_topic()
    made = data.plan_for_groups(
        t.topic_id, planned_date=ui.ask("Planned for (blank = week "
                                        "commencing)") or None)
    print(f"\n  ✓ Planned for {len(made)} group(s).")
    ui.pause()


def copy_year() -> None:
    n = data.copy_programme(ui.ask("From year", required=True),
                            ui.ask("To year", required=True))
    print(f"\n  ✓ Copied {n} topic(s).")
    ui.pause()


def sessions() -> None:
    rows = data.list_deliveries(academic_year=_year(),
                                tutor_group_id=_pick_group())
    ui.print_rows(rows, _session_cols())
    ui.pause()


def take_register() -> None:
    rows = data.list_deliveries(tutor_group_id=_pick_group(False),
                                academic_year=_year())
    ui.print_rows(rows, _session_cols())
    d = ui.pick_row(rows, lambda r: r.delivery_id, "session")
    lines = data.register_for(d.delivery_id)
    if not lines:
        print("\n  Nobody in this group.")
        ui.pause()
        return
    print("\n  Marks: P = Present, L = Late, A = Absent, E = Excused "
          "(Enter = keep / Present)")
    code = {"p": "Present", "l": "Late", "a": "Absent", "e": "Excused"}
    marks = {}
    for ln in lines:
        cur = ln.mark or "Present"
        raw = ui.ask(f"{ln.student_id} {ln.student_name}", default=cur[0])
        marks[ln.student_id] = code.get(raw.lower()[:1], cur)
    out = data.save_register(d.delivery_id, marks,
                             delivered_on=ui.ask("Delivered on",
                                                 default=today()),
                             delivered_by=ui.ask("Delivered by") or None)
    print(f"\n  ✓ Register saved: {out.present}/{out.marked} present.")
    ui.pause()


def edit_session() -> None:
    rows = data.list_deliveries(academic_year=_year())
    ui.print_rows(rows, _session_cols())
    d = ui.pick_row(rows, lambda r: r.delivery_id, "session")
    data.update_delivery(d.delivery_id,
                         ui.prompt_fields(data.DELIVERY_SPEC.cols,
                                          existing=d))
    print("\n  ✓ Updated.")
    ui.pause()


def coverage() -> None:
    yr = _year()
    groups, rows = data.coverage(yr)
    abbr = {"Delivered": "D", "Planned": "P", "Cancelled": "C", "—": "-",
            "n/a": ""}
    print(f"\n  Coverage {yr} (D delivered, P planned, C cancelled, "
          "- not planned)")
    print("  " + f"{'Topic':<36}" + "".join(f"{g[:6]:<7}" for g in groups))
    for r in rows:
        print("  " + f"{r.topic.title[:35]:<36}" + "".join(
            f"{abbr.get(r.by_group[g], '?'):<7}" for g in groups))
    ui.pause()


def overdue_sessions() -> None:
    ui.print_rows(data.overdue_sessions(_year()), (
        ("Group", lambda r: r.group_name, 8),
        ("W/c", lambda r: r.topic.week_commencing, 10),
        ("Topic", lambda r: r.topic.title, 32),
        ("Req", lambda r: r.topic.required, 4),
        ("State", lambda r: r.status, 11),
    ), empty="(nothing overdue)")
    ui.pause()


def catch_up() -> None:
    ui.print_rows(data.catch_up_list(_year()), (
        ("Student", lambda r: r.student_id, 9),
        ("Name", lambda r: r.student_name, 20),
        ("Topic", lambda r: r.topic_title, 30),
        ("Group", lambda r: r.group_name, 8),
        ("Mark", lambda r: r.mark, 8),
    ), empty="(no catch-up needed)")
    ui.pause()


def meetings() -> None:
    ui.run_menu("Personal tutor 1:1s", [
        *ui.crud_items("1:1 meeting", data.MEETING_SPEC,
                       load=lambda: data.list_meetings(),
                       create=data.create_meeting,
                       update=data.update_meeting,
                       delete=data.delete_meeting),
        ("Add agreed action to a meeting", add_action),
        ("Follow-up done", follow_up_done),
        ("Follow-ups due", follow_ups_due),
    ])


def _pick_meeting(**kw):
    rows = data.list_meetings(**kw)
    ui.print_rows(rows, ui.spec_columns(data.MEETING_SPEC))
    return ui.pick_row(rows, lambda r: r.meeting_id, "meeting")


def add_action() -> None:
    m = _pick_meeting()
    v = ui.prompt_fields(data.ACTION_SPEC.cols,
                         initial={"meeting_id": m.meeting_id})
    a = data.add_action({**v, "meeting_id": m.meeting_id})
    print(f"\n  ✓ Action #{a.action_id} added.")
    ui.pause()


def follow_up_done() -> None:
    m = _pick_meeting(follow_up_due_only=True)
    data.complete_follow_up(m.meeting_id, on=ui.ask("On", default=today()),
                            notes=ui.ask_multiline("Notes"))
    print("\n  ✓ Follow-up recorded.")
    ui.pause()


def follow_ups_due() -> None:
    ui.print_rows(data.list_meetings(follow_up_due_only=True),
                  ui.spec_columns(data.MEETING_SPEC),
                  empty="(no follow-ups due)")
    ui.pause()


def actions_menu() -> None:
    ui.run_menu("Agreed actions", [
        *ui.crud_items("agreed action", data.ACTION_SPEC,
                       load=lambda: data.list_actions(open_only=True),
                       update=data.update_action,
                       delete=data.delete_action),
        ("Close an action", close_action),
        ("Overdue actions", lambda: (ui.print_rows(
            data.list_actions(overdue_only=True),
            ui.spec_columns(data.ACTION_SPEC), empty="(none overdue)"),
            ui.pause())),
    ])


def close_action() -> None:
    rows = data.list_actions(open_only=True)
    ui.print_rows(rows, ui.spec_columns(data.ACTION_SPEC))
    a = ui.pick_row(rows, lambda r: r.action_id, "action")
    status = ui.pick_from("Outcome", [s for s in data.ACTION_STATUSES
                                      if s != data.ACTION_OPEN],
                          default="Done")
    data.complete_action(a.action_id, status=status,
                         notes=ui.ask("Notes") or None)
    print("\n  ✓ Closed.")
    ui.pause()


def not_seen() -> None:
    since = ui.ask("No 1:1 since", default=(
        _dt.date.today() - _dt.timedelta(days=42)).isoformat())
    ui.print_rows(data.students_not_seen(since=since,
                                         tutor_group_id=_pick_group()), (
        ("Student", lambda r: r.student_id, 9),
        ("Name", lambda r: r.student_name, 22),
        ("Group", lambda r: r.group_name, 8),
        ("Tutor", lambda r: r.tutor, 16),
        ("Last 1:1", lambda r: r.last_meeting or "never", 10),
    ), empty="(everyone has been seen)")
    ui.pause()


def run() -> None:
    ui.run_menu("Tutorial & PSHE Programme", [
        ("── Programme ──", None),
        *ui.crud_items("topic", data.TOPIC_SPEC,
                       load=lambda: data.list_topics(
                           academic_year=data.current_academic_year()),
                       create=data.create_topic, update=data.update_topic,
                       delete=data.delete_topic,
                       new_initial=lambda: {
                           "academic_year": data.current_academic_year()}),
        ("Plan a topic for tutor groups", plan_groups),
        ("Copy programme to another year", copy_year),
        ("── Sessions ──", None),
        ("List sessions", sessions),
        ("Take register", take_register),
        ("Edit / cancel a session", edit_session),
        ("Coverage grid", coverage),
        ("Overdue sessions", overdue_sessions),
        ("Catch-up list (missed required topics)", catch_up),
        ("── 1:1s ──", None),
        ("1:1 meetings", meetings),
        ("Agreed actions", actions_menu),
        ("Learners not seen", not_seen),
    ])


def tutorial_menu() -> None:
    """Entry point for the main CLI menu."""
    run()
