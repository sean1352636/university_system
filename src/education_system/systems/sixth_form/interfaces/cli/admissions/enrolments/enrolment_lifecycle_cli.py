"""Enrolment CLI: lifecycle actions — reinstate a withdrawal, reopen a
completed year, Year 12 return intentions, rollover runs (history and
undo) and the enrolment audit trail."""

from __future__ import annotations

import logging

from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.interfaces.cli.admissions.enrolments._common import (
    _UserAbort,
    _default_academic_year,
    _input,
    _pause,
    _pick_from,
    _pick_student,
    _print_leaver_effects,
    _print_reinstate,
    _prompt_academic_year,
    _prompt_ids,
    _record_undo,
    _report_bulk,
    _resolve_enrolment,
    _student_names,
    _writes_ok,
)

logger = logging.getLogger(__name__)


# ── Reinstate / reopen ──────────────────────────────────────────────

def _pick_by_status(status: str, enrolment_id: int | None) -> data.Enrolment | None:
    """The given enrolment, or a pick from the ones with ``status``."""
    if enrolment_id is not None:
        return _resolve_enrolment(enrolment_id)
    rows = data.list_enrolments(status=status)
    if not rows:
        print(f"  (no {status.lower()} enrolments)")
        _pause()
        return None
    names = _student_names()
    print(f"\n  {status} enrolments:")
    for e in rows[:200]:
        when = (f"withdrawn {e.withdrawal_date or '?'} "
                f"({e.withdrawal_reason_label or 'no reason'})"
                if status == "Withdrawn" else f"completed {e.completed_at or '?'}")
        print(f"    #{e.enrolment_id:<5} {e.student_id:<10} "
              f"{names.get(e.student_id, '—')[:22]:<22} {e.academic_year} "
              f"Y{e.year_group}  {when}")
    if len(rows) > 200:
        print(f"    … {len(rows) - 200} more — type the id")
    return _resolve_enrolment(None)


def reinstate_withdrawn(enrolment_id: int | None = None) -> None:
    """Undo a withdrawal: back to Enrolled, the aims it ended reopened, and
    a student record marked Left put back on roll."""
    print("\n═══ Reinstate a Withdrawn Enrolment ═══")
    if not _writes_ok():
        return
    try:
        e = _pick_by_status("Withdrawn", enrolment_id)
        if e is None:
            return
        if e.status != "Withdrawn":
            print(f"  ✗ #{e.enrolment_id} is {e.status}, not withdrawn.")
            _pause()
            return
        st = student_data.get_student(e.student_id)
        print(f"  #{e.enrolment_id} {e.student_id} "
              f"({st.full_name if st else '—'}) {e.academic_year} Year "
              f"{e.year_group}: withdrawn {e.withdrawal_date or '?'} — "
              f"{e.withdrawal_reason_label or 'no reason'}")
        put_back = True
        if st is not None and st.status == "Left":
            put_back = _input("Their student record is marked Left — put them "
                              "back on roll too? (y/n)",
                              default="y").lower().startswith("y")
        reason = _input("Reason for reinstating (required)", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        res = data.reinstate_enrolment(e.enrolment_id, reason=reason,
                                       reinstate_student=put_back)
    except (ValueError, PermissionError) as exc:
        print(f"  ✗ {exc}")
        _pause()
        return
    _print_reinstate(res)
    _pause()


def reopen_completed(enrolment_id: int | None = None) -> None:
    """Put a Completed enrolment back to Enrolled (e.g. completed by a
    rollover by mistake). Aims are left as they are."""
    print("\n═══ Reopen a Completed Enrolment ═══")
    if not _writes_ok():
        return
    try:
        e = _pick_by_status("Completed", enrolment_id)
        if e is None:
            return
        if e.status != "Completed":
            print(f"  ✗ #{e.enrolment_id} is {e.status}, not Completed.")
            _pause()
            return
        reason = _input("Reason for reopening (required)", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        out = data.reopen_enrolment(e.enrolment_id, reason=reason)
    except (ValueError, PermissionError) as exc:
        print(f"  ✗ {exc}")
        _pause()
        return
    print(f"  ✓ #{out.enrolment_id} ({out.student_id}, {out.academic_year}) is "
          f"{out.status} again.")
    print("    Learning aims completed with it are unchanged — reopen those "
          "under Learning aims if needed.")
    _record_undo(f"reopen of #{out.enrolment_id}",
                 lambda: data.complete_enrolment(out.enrolment_id,
                                                 completed_on=e.completed_at,
                                                 complete_aims=False))
    _pause()


# ── Year 12 return intentions ───────────────────────────────────────

def _intention_choice() -> tuple[str | None, str | None]:
    options = [*data.RETURN_INTENTIONS, "Clear (no answer)"]
    pick = _pick_from("Return intention for Year 13", options, default="Returning")
    note = _input("Note (optional)") or None
    return (None if pick.startswith("Clear") else pick), note


def record_return_intention() -> None:
    """Record one Year 12 learner's answer to "coming back for Year 13?"."""
    print("\n═══ Record Year 12 Return Intention ═══")
    if not _writes_ok():
        return
    try:
        sid = _pick_student()
        year = _default_academic_year()
        rows = [e for e in data.list_for_student(sid)
                if e.year_group == 12 and e.status == "Enrolled"]
        if not rows:
            print(f"  ✗ {sid} has no Enrolled Year 12 enrolment.")
            _pause()
            return
        e = next((r for r in rows if r.academic_year == year), rows[0])
        print(f"  #{e.enrolment_id} {e.academic_year} Year 12 — currently "
              f"{e.return_intention or 'no answer'}"
              + (f" ({e.return_intention_note})" if e.return_intention_note else ""))
        intention, note = _intention_choice()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        out = data.set_return_intention(e.enrolment_id, intention, note=note)
    except (ValueError, PermissionError) as exc:
        print(f"  ✗ {exc}")
        _pause()
        return
    print(f"  ✓ {sid}: {out.return_intention or 'cleared'}")
    _pause()


def bulk_return_intention() -> None:
    """Record one return intention on many Year 12 enrolments by ID."""
    print("\n═══ Bulk Year 12 Return Intention ═══")
    if not _writes_ok():
        return
    try:
        year = _prompt_academic_year(_default_academic_year())
        names = _student_names()
        rows = [e for e in data.list_enrolments(academic_year=year, year_group=12)
                if e.status == "Enrolled"]
        if not rows:
            print(f"  (no Enrolled Year 12 enrolments in {year})")
            _pause()
            return
        for e in rows:
            print(f"    #{e.enrolment_id:<5} {e.student_id:<10} "
                  f"{names.get(e.student_id, '—')[:24]:<24} "
                  f"{e.return_intention or '—'}")
        raw = _input("Enrolment IDs (comma/space separated, or 'all')",
                     allow_empty=False)
        ids = ([e.enrolment_id for e in rows] if raw.lower() == "all" else
               [int(t) for t in raw.replace(",", " ").split() if t.isdigit()])
        if not ids:
            print("  No IDs given.")
            _pause()
            return
        intention, note = _intention_choice()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok: list[str] = []
    fail: list[str] = []
    for eid in ids:
        try:
            data.set_return_intention(eid, intention, note=note)
            ok.append(f"#{eid}")
        except Exception as exc:  # ValidationError / AccessDenied per row
            fail.append(f"#{eid}: {exc}")
    _print_summary(year)
    _report_bulk("Return intentions", ok, fail)


def _print_summary(year: str) -> None:
    try:
        summary = data.reintention_summary(year)
    except Exception as exc:  # noqa: BLE001 — shown
        print(f"  ✗ {exc}")
        return
    total = sum(summary.values())
    print(f"\n  Year 12 return intentions, {year} ({total} enrolled):")
    for k, v in summary.items():
        print(f"    {k:<14} {v}")


def return_intention_summary() -> None:
    print("\n═══ Year 12 Return Intentions ═══")
    try:
        year = _prompt_academic_year(_default_academic_year())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_summary(year)
    _pause()


# ── Rollover runs ───────────────────────────────────────────────────

def _print_runs(runs: list[dict]) -> None:
    for r in runs:
        counts = ", ".join(f"{k} {v}" for k, v in r.items()
                           if isinstance(v, int) and k != "run_id")
        undone = (f"  UNDONE {r['undone_at']} by {r.get('undone_by') or '—'}"
                  if r.get("undone_at") else "")
        print(f"    #{r['run_id']:<4} {r['from_year']} → {r['to_year']}  "
              f"{(r.get('run_at') or '')[:16]} by {r.get('run_by') or '—'}"
              f"  [{counts}]{undone}")


def rollover_history() -> None:
    print("\n═══ Rollover History ═══")
    runs = data.list_rollovers()
    if not runs:
        print("  (no rollover has been run)")
    _print_runs(runs)
    _pause()


def undo_rollover_flow() -> None:
    """Put a rollover run back (latest first): rows it created are archived,
    rows it completed go back to Enrolled and their aims reopen."""
    print("\n═══ Undo Rollover ═══")
    if not _writes_ok():
        return
    runs = [r for r in data.list_rollovers() if not r.get("undone_at")]
    if not runs:
        print("  (no rollover run to undo)")
        _pause()
        return
    _print_runs(runs)
    try:
        raw = _input("Run # to undo", default=str(runs[0]["run_id"]))
        run_id = int(raw.lstrip("#"))
        if _input(f"Undo rollover run #{run_id}? Type 'yes' to confirm",
                  default="no").lower() != "yes":
            print("\n  Cancelled.")
            return
    except ValueError:
        print("  ✗ Run # must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        res = data.undo_rollover(run_id)
    except (ValueError, PermissionError) as exc:
        print(f"  ✗ {exc}")
        _pause()
        return
    print(f"  ✓ Rollover run #{res.run_id} undone: {res.reverted} enrolment(s) "
          "put back.")
    for k in res.kept:
        print(f"    • left alone: {k}")
    for p in res.aim_problems:
        print(f"    ✗ aim: {p}")
    _pause()


# ── Audit trail ─────────────────────────────────────────────────────

def enrolment_audit_history() -> None:
    """The persistent change history for one enrolment or one learner."""
    print("\n═══ Enrolment Change History ═══")
    try:
        by = _pick_from("History for", ["One enrolment", "One learner"],
                        default="One learner")
        if by == "One enrolment":
            ids = _prompt_ids("Enrolment ID")
            if not ids:
                return
            rows = data.enrolment_history(enrolment_id=ids[0])
            title = f"enrolment #{ids[0]}"
        else:
            sid = _pick_student(include_leavers=True)
            rows = data.enrolment_history(student_id=sid)
            title = sid
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  Change history — {title} (newest first)")
    for h in rows:
        print(f"    {(h.get('changed_at') or '')[:16]}  #{h['enrolment_id']:<5} "
              f"{h['action']:<16} {h.get('changed_by') or '—':<10} "
              f"{h.get('detail') or ''}")
    if not rows:
        print("    (no changes recorded)")
    if by != "One enrolment":
        print()
        _print_leaver_effects(sid)
    _pause()
