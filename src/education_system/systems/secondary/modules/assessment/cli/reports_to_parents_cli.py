"""Reports to Parents in the terminal.

New (there was no old menu): cycles 1-4, comments 5-7, checking and issuing
8-13, reports 14-17. Rules live in :mod:`modules.assessment.domain.reports_to_parents`.
"""

from __future__ import annotations

from education_system.systems.secondary.modules.assessment.domain import reports_to_parents as RP
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (RP.ValidationError, RP.PermissionDenied, RP.NotFound)


_problem = prompts.problem


def _cycles() -> list[RP.Cycle]:
    rows = RP.list_cycles()
    if not rows:
        print("  (no report cycles)")
    for c in rows:
        print(f"  {c.cycle_id:<4} {c.title[:34]:<34} {c.report_type:<11} Y{c.years_label:<12} "
              f"{c.status:<9} {c.point_name} ({c.point_status})")
    return rows


def _cycle() -> RP.Cycle | None:
    rows = _cycles()
    if not rows:
        return None
    v = _prompt(f"  Cycle ID [{rows[0].cycle_id}]: ") or str(rows[0].cycle_id)
    if not v.isdigit():
        return None
    try:
        return RP.get_cycle(int(v))
    except RP.NotFound as e:
        print(f"  {e}")
        return None


def _pupil() -> P.Pupil | None:
    ref = _prompt("  Pupil (admission number or UPN): ")
    p = P.find_by_reference(ref) if ref else None
    if ref and p is None:
        print("  No pupil with that admission number.")
    return p


def _pupils() -> list[int]:
    refs = _prompt("  Pupils (admission numbers, blank = everyone): ")
    out = []
    for ref in refs.replace(",", " ").split():
        p = P.find_by_reference(ref)
        if p is None:
            print(f"  Not found: {ref}")
            return [-1]
        out.append(p.pupil_id)
    return out


# ── Cycles ───────────────────────────────────────────────────────────

def _list(_p: Principal) -> None:
    _cycles()


def _cycle_details(c: RP.Cycle | None) -> dict:
    from education_system.systems.secondary.modules.assessment.domain import assessment_points as AP
    data: dict = {}
    g = (lambda k: getattr(c, k) if c else None)

    def ask(key, label):
        cur = g(key)
        v = _prompt(f"  {label}" + (f" [{cur}]" if cur not in (None, "") else "") + ": ")
        if v:
            data[key] = "" if v == "-" else v
    if c is None:
        print("  (Enter keeps the default, '-' clears.)")
    ask("name", "Name")
    ask("report_type", f"Type ({'/'.join(RP.REPORT_TYPES)})")
    for pt in AP.list_points():
        print(f"    {pt.point_id:<4} {pt.name} {pt.academic_year} Y{pt.years_label} "
              f"({pt.status})")
    ask("point_id", "Assessment point ID")
    ask("year_groups", "Year groups (blank = the point's)")
    for k, label in RP.INCLUDES.items():
        cur = g(k)
        v = _prompt(f"  Include {label.lower()}? (y/n)"
                    + (f" [{'y' if cur else 'n'}]" if cur is not None else "") + ": ").lower()
        if v in ("y", "n"):
            data[k] = v == "y"
    ask("comments_due", "Comments due (YYYY-MM-DD)")
    ask("issue_date", "Issue date (YYYY-MM-DD)")
    ask("intro", "Introduction for families")
    return data


def _new(principal: Principal) -> None:
    c = RP.create_cycle(_cycle_details(None), actor=principal)
    print(f"\n  Created {c.title} (#{c.cycle_id}). Move it to Writing when tutors should "
          "write comments.")


def _edit(principal: Principal) -> None:
    c = _cycle()
    if c:
        RP.update_cycle(c.cycle_id, _cycle_details(c), actor=principal)
        print("\n  Saved.")


def _status(principal: Principal) -> None:
    c = _cycle()
    if c is None:
        return
    moves = [b for a, b in sorted(RP._CYCLE_MOVES) if a == c.status]
    print(f"  Currently {c.status}; can move to: {', '.join(moves)}")
    st = _prompt("  New status: ")
    if st:
        print(f"\n  Now {RP.set_cycle_status(c.cycle_id, st, actor=principal).status}.")


# ── Comments ─────────────────────────────────────────────────────────

def _kind() -> str:
    v = _prompt("  Comment: 1) form tutor  2) head of year [1]: ")
    return "hoy" if v == "2" else "tutor"


def _write(principal: Principal) -> None:
    """Go through my pupils (or a form) writing comments."""
    c = _cycle()
    if c is None:
        return
    kind = _kind()
    form = _prompt("  Form (blank = all mine): ").upper()
    pupils = RP.pupils_in(c, form_group=form) if form else RP.my_pupils(c.cycle_id, principal,
                                                                        kind)
    if not pupils:
        print("  No pupils to write for.")
        return
    cm = RP.comments(c.cycle_id)
    todo = [p for p in pupils if (p.pupil_id, kind) not in cm] if _yes(
        "  Only pupils without a comment yet?") else pupils
    bank = RP.bank(kind)
    for p in todo:
        cur = (cm.get((p.pupil_id, kind)) or {}).get("comment")
        print(f"\n  {p.admission_no} {p.display_name} (form {p.form_group or '-'})")
        if cur:
            print(f"    now: {cur}")
        if bank:
            print("    bank: " + "  ".join(f"[{i}] {b.text[:40]}…" for i, b in
                                           enumerate(bank[:5], 1)))
        v = _prompt("    Comment (Enter = skip, b<n> = bank, q = stop): ")
        if v.lower() == "q":
            return
        if not v:
            continue
        if v.lower().startswith("b") and v[1:].isdigit() and 1 <= int(v[1:]) <= len(bank):
            v = bank[int(v[1:]) - 1].text
        try:
            print("    saved: " + (RP.set_comment(c.cycle_id, p.pupil_id, kind, v,
                                                  actor=principal) or "-"))
        except _ERRORS as e:
            _problem(e)


def _one_comment(principal: Principal) -> None:
    c = _cycle()
    p = _pupil() if c else None
    if p is None:
        return
    kind = _kind()
    cur = (RP.comments(c.cycle_id, p.pupil_id).get((p.pupil_id, kind)) or {}).get("comment")
    if cur:
        print(f"  Now: {cur}")
    v = _prompt("  New comment ('-' removes it): ")
    if v:
        RP.set_comment(c.cycle_id, p.pupil_id, kind, "" if v == "-" else v, actor=principal)
        print("  Saved.")


def _bank(principal: Principal) -> None:
    for b in RP.bank():
        print(f"  {b.bank_id:<4} {b.kind:<6} {b.category[:14]:<14} {b.text}")
    v = _prompt("  a = add, d<ID> = delete, Enter = back: ").lower()
    if v == "a":
        text = _prompt("  Comment ({first_name} / {name} for the pupil): ")
        kind = _prompt("  For tutor / hoy / any [any]: ").lower() or "any"
        RP.add_bank(text, actor=principal, kind=kind,
                    category=_prompt("  Category [General]: ") or "General")
        print("  Added.")
    elif v.startswith("d") and v[1:].isdigit():
        RP.delete_bank(int(v[1:]), actor=principal)
        print("  Removed.")


# ── Checking and issuing ─────────────────────────────────────────────

def _check(_p: Principal) -> None:
    c = _cycle()
    if c is None:
        return
    y = _prompt("  Year (blank = all): ")
    for p, r in RP.list_reports(c.cycle_id, year_group=int(y) if y.isdigit() else None):
        st = r.status if r else "Draft"
        missing = "" if st in ("Issued", "Withheld") else "; ".join(
            RP.problems(c.cycle_id, p.pupil_id))
        print(f"  {p.admission_no:<10} {p.display_name[:22]:<22} {p.form_group or '-':<6} "
              f"{st:<9} {missing or (r.withheld_reason if r and st == 'Withheld' else '')}")


def _preview(_p: Principal) -> None:
    c = _cycle()
    p = _pupil() if c else None
    if p:
        print("\n" + "\n".join("  " + line for line in RP.render_text(
            RP.view(c.cycle_id, p.pupil_id)).splitlines()))


def _ready(principal: Principal) -> None:
    c = _cycle()
    if c is None:
        return
    ids = _pupils()
    if ids == [-1]:
        return
    ids = ids or [p.pupil_id for p, _r in RP.list_reports(c.cycle_id)]
    res = RP.mark_ready(c.cycle_id, ids, actor=principal)
    print(f"\n  {res['ready']} report(s) marked ready.")
    for k, why in list(res["skipped"].items())[:30]:
        print(f"   not ready {k}: {'; '.join(why)}")
    if res["skipped"] and _yes("  Mark the ones with gaps ready anyway?"):
        n = RP.mark_ready(c.cycle_id, ids, actor=principal, force=True)["ready"]
        print(f"  {n} more marked ready.")


def _withhold(principal: Principal) -> None:
    c = _cycle()
    p = _pupil() if c else None
    if p is None:
        return
    if _yes("  Reset a withheld / ready report back to draft instead?"):
        RP.reset(c.cycle_id, p.pupil_id, actor=principal)
        print("  Reset.")
        return
    RP.withhold(c.cycle_id, p.pupil_id, _prompt("  Reason: "), actor=principal)
    print("  Withheld.")


def _issue(principal: Principal) -> None:
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    c = _cycle()
    if c is None:
        return
    ids = _pupils()
    if ids == [-1]:
        return
    email = _yes("  E-mail parents with parental responsibility as well?")
    if not _yes(f"  Issue {'those' if ids else 'every Ready'} report(s) for {c.title}?"):
        return
    res = RP.issue(c.cycle_id, ids or None, actor=principal, email=email)
    print(f"\n  Issued {len(res['issued'])} report(s).")
    for k, why in res["skipped"].items():
        print(f"   skipped {k}: {why}")
    if email and res["no_email"]:
        print("  No parent e-mail for: " + ", ".join(p.display_name for p in res["no_email"]))
    if res["message_id"]:
        try:
            E.deliver(res["message_id"], principal=principal)
            print(f"  {res['emails']} e-mail(s) sent.")
        except Exception as e:  # noqa: BLE001 - the e-mails stay queued
            print(f"  Saved {res['emails']} e-mail(s) but delivery failed: {e}")


def _withdraw(principal: Principal) -> None:
    c = _cycle()
    p = _pupil() if c else None
    if p is None:
        return
    r = RP.report_for(c.cycle_id, p.pupil_id)
    if r is None or r.status != "Issued":
        print("  That pupil's report hasn't been issued.")
        return
    RP.withdraw(r.report_id, _prompt("  Reason: "), actor=principal)
    print("  Withdrawn - correct it, mark it ready and issue it again.")


# ── Reports ──────────────────────────────────────────────────────────

def _progress(_p: Principal) -> None:
    c = _cycle()
    if c is None:
        return
    print(f"\n  {'Yr':<3} {'Form':<7} {'Tutor':<18} {'Pupils':>6} {'Tutor':>6} {'HoY':>5} "
          f"{'Draft':>6} {'Ready':>6} {'Issued':>7} {'Held':>5} {'Viewed':>7}")
    for g in RP.progress(c.cycle_id):
        print(f"  {g['year_group']:<3} {g['form_group'][:7]:<7} {g['tutor'][:18]:<18} "
              f"{g['pupils']:>6} {g['tutor_done']:>6} {g['hoy_done']:>5} {g['Draft']:>6} "
              f"{g['Ready']:>6} {g['Issued']:>7} {g['Withheld']:>5} {g['viewed']:>7}")


def _export_html(principal: Principal) -> None:
    c = _cycle()
    folder = _prompt("  Folder to save to: ") if c else ""
    if folder:
        try:
            print(f"  Saved {RP.export_html(c.cycle_id, folder, actor=principal)} report(s).")
        except OSError as e:
            print(f"  Couldn't write there: {e.strerror or e}")


def _export_csv(principal: Principal) -> None:
    c = _cycle()
    path = _prompt("  Save to (path, .csv): ") if c else ""
    if path:
        try:
            print(f"  Exported {RP.export_csv(c.cycle_id, path, actor=principal)} row(s).")
        except OSError as e:
            print(f"  Couldn't write the file: {e.strerror or e}")


def _history(_p: Principal) -> None:
    c = _cycle()
    if c:
        for h in RP.history(c.cycle_id):
            print(f"  {h['at']}  {h['actor']:<14} {h['action']:<14} "
                  + (f"pupil {h['pupil_id']} " if h["pupil_id"] else "")
                  + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


_OPTIONS = {"1": _list, "2": _new, "3": _edit, "4": _status, "5": _write, "6": _one_comment,
            "7": _bank, "8": _check, "9": _preview, "10": _ready, "11": _withhold,
            "12": _issue, "13": _withdraw, "14": _progress, "15": _export_html,
            "16": _export_csv, "17": _history}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("reports.view")
        print("\n── Reports to Parents ──")
        print("  Cycles\n   1) List\n   2) New\n   3) Edit\n   4) Status")
        print("  Comments\n   5) Write comments for my pupils\n   6) One pupil's comment"
              "\n   7) Comment bank")
        print("  Check & issue\n   8) Check reports\n   9) Preview a report\n  10) Mark ready"
              "\n  11) Withhold / reset\n  12) Issue\n  13) Withdraw an issued report")
        print("  Reports\n  14) Progress by form\n  15) Export HTML (to print)"
              "\n  16) Export CSV\n  17) History\n   0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        fn = _OPTIONS.get(choice)
        if fn is None:
            continue
        try:
            fn(principal)
        except _ERRORS as e:
            _problem(e)
        _pause()
