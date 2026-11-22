"""CLI for behaviour escalation, the learner agreement and dress code /
ID badge breaches."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.pastoral._records import Col
from education_system.systems.sixth_form.domain.pastoral.behaviour import behaviour as data
from education_system.systems.sixth_form.interfaces.cli.pastoral import _records_cli as ui


# ── Escalation ───────────────────────────────────────────────────

def open_escalations() -> None:
    ui.print_rows(data.list_escalations(status="Open"),
                  ui.spec_columns(data.ESCALATION_SPEC),
                  empty="(no open escalations)")
    ui.pause()


def action_escalation() -> None:
    rows = data.list_escalations(status="Open")
    ui.print_rows(rows, ui.spec_columns(data.ESCALATION_SPEC))
    e = ui.pick_row(rows, lambda x: x.escalation_id, "escalation")
    v = ui.prompt_fields((Col("outcome", "What was done / agreed",
                              "multiline", required=True),
                          Col("close", "Close the escalation", "bool")))
    data.action_escalation(e.escalation_id, outcome=v["outcome"],
                           close=v["close"])
    print("\n  ✓ Saved.")
    ui.pause()


def check_now() -> None:
    made = data.run_escalation_check()
    ui.print_rows(made, ui.spec_columns(data.ESCALATION_SPEC),
                  empty="(no new escalations)")
    ui.pause()


def points_for_student() -> None:
    sid = ui.pick_student()
    for r in data.list_rules(active_only=True):
        pts, start = data.negative_points(sid, window_days=r.window_days)
        mark = "  ← reached" if pts >= r.points_threshold else ""
        print(f"  {r.stage:<24} {pts:>4} / {r.points_threshold:<4} "
              f"since {start}{mark}")
    if not data.list_rules(active_only=True):
        print("\n  (no thresholds configured)")
    ui.pause()


def suggested() -> None:
    if ui.yes_no("Add the suggested thresholds for stages without one?"):
        ui.print_rows(data.install_suggested_rules(),
                      ui.spec_columns(data.RULE_SPEC))
    ui.pause()


def escalation_menu() -> None:
    ui.run_menu("Behaviour Escalation", [
        ("Open escalations", open_escalations),
        ("Action / close an escalation", action_escalation),
        *ui.crud_items("escalation", data.ESCALATION_SPEC,
                       load=data.list_escalations,
                       update=data.update_escalation,
                       delete=data.delete_escalation),
        ("Check all students now", check_now),
        ("A student's points against each threshold", points_for_student),
        ("── Thresholds ──", None),
        *ui.crud_items("threshold", data.RULE_SPEC, load=data.list_rules,
                       create=data.create_rule, update=data.update_rule,
                       delete=data.delete_rule),
        ("Add suggested thresholds", suggested),
    ])


# ── Learner agreement ────────────────────────────────────────────

def make_current() -> None:
    rows = data.list_agreement_versions()
    ui.print_rows(rows, ui.spec_columns(data.VERSION_SPEC))
    v = ui.pick_row(rows, lambda x: x.version_id, "version")
    data.set_current_agreement_version(v.version_id)
    print(f"\n  ✓ {v.version_label} is now the current version.")
    ui.pause()


def outstanding() -> None:
    ui.print_rows(data.outstanding_agreements(), (
        ("Student", lambda o: o.student_id, 9),
        ("Name", lambda o: o.student_name, 22),
        ("Student ok", lambda o: o.student_signed, 10),
        ("Parent needed", lambda o: o.parent_needed, 13),
        ("Parent ok", lambda o: o.parent_signed, 9)),
        empty="(everyone has accepted the current version)")
    ui.pause()


def _accept_initial() -> dict:
    cur = data.current_agreement_version()
    if cur is None:
        raise data.ValidationError("Add a learner agreement version first")
    return {"version_id": cur.version_id}


def agreement_menu() -> None:
    ui.run_menu("Learner Agreement", [
        *ui.crud_items("version", data.VERSION_SPEC,
                       load=data.list_agreement_versions,
                       create=data.create_agreement_version,
                       update=data.update_agreement_version,
                       delete=data.delete_agreement_version),
        ("Make a version current", make_current),
        ("── Acceptances ──", None),
        *ui.crud_items("acceptance", data.SIGNATURE_SPEC,
                       load=data.list_agreement_acceptances,
                       create=data.record_agreement_acceptance,
                       update=data.update_agreement_acceptance,
                       delete=data.delete_agreement_acceptance,
                       new_initial=_accept_initial),
        ("Outstanding (current version)", outstanding),
    ])


# ── Dress code ───────────────────────────────────────────────────

def points_table() -> None:
    pts = data.breach_points()
    for t in data.BREACH_TYPES:
        print(f"  {t:<22} {pts[t]:>4}")
    if ui.yes_no("Change one?"):
        t = ui.pick_from("Breach", data.BREACH_TYPES)
        n = ui.ask("Points (entered as positive, stored negative)",
                   required=True)
        data.set_breach_points(t, int(n))
        print("\n  ✓ Saved.")
    ui.pause()


def breaches_menu() -> None:
    ui.run_menu("Dress Code / ID Badge Breaches", [
        *ui.crud_items("breach", data.BREACH_SPEC, load=data.list_breaches,
                       create=data.record_breach, update=data.update_breach,
                       delete=data.delete_breach),
        ("Points per breach type", points_table),
    ])
