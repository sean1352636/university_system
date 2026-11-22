"""Incoming Year 6 -> Year 7 transfers from primary, in the terminal.

1 Queue, 2 Handover, 3 Acknowledge, 4 Reject, 5 Match to a pupil or
application, 6 Create pupil from handover, 7 Checklist, 8 Tick / untick, 9 SEN
passed to SENCO, 10 Safeguarding file received, 11 Import KS2, 12 Complete
(admit), 13 Unmatch, 14 Step log, 15 Refresh matches, 16 Export CSV. Rules
live in :mod:`modules.progression.domain.incoming_primary`.
"""

from __future__ import annotations

from education_system.systems.secondary.modules.progression.domain import incoming_primary as IP
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (IP.ValidationError, IP.PermissionDenied, IP.NotFound)
_problem = prompts.problem


def _list(principal: Principal, include_closed: bool = False) -> list[IP.Incoming]:
    rows = IP.queue(actor=principal, include_closed=include_closed)
    if not rows:
        print("  No transfers from primary.")
    for n, i in enumerate(rows, 1):
        name = i.name + i.tag.replace("from ", "")
        print(f"  {n:>2}) {name:<28} {i.date_of_birth or '':<11} {i.status_label:<15} "
              f"{'ack' if i.acknowledged_at else '   '} "
              f"{'pupil #' + str(i.pupil_id) if i.pupil_id else ''}")
    return rows


def _choose(principal: Principal) -> IP.Incoming | None:
    rows = _list(principal, include_closed=True)
    n = prompts.ask_int("  Transfer number: ") if rows else None
    return rows[n - 1] if n and 1 <= n <= len(rows) else None


def _queue(principal: Principal) -> None:
    c = IP.counts(actor=principal)
    print("  " + ", ".join(f"{k}: {v}" for k, v in c.items()))
    _list(principal, include_closed=_yes("  Include completed / rejected?"))


def _handover(principal: Principal) -> None:
    i = _choose(principal)
    if i:
        print("\n" + IP.handover_text(IP.handover(i.transition_id, actor=principal)))


def _ack(principal: Principal) -> None:
    i = _choose(principal)
    if i:
        IP.acknowledge(i.transition_id, actor=principal,
                       note=_prompt("  Note (optional): ") or None)
        print("  Acknowledged.")


def _reject(principal: Principal) -> None:
    i = _choose(principal)
    if i:
        reason = _prompt("  Reason (sent back to the primary school): ")
        if _yes(f"  Reject the transfer for {i.name}?"):
            IP.reject(i.transition_id, actor=principal, reason=reason)
            print("  Rejected.")


def _show_outcome(out: IP.Outcome) -> None:
    for note in out.notes:
        print(f"  - {note}")


def _match(principal: Principal) -> None:
    i = _choose(principal)
    if not i:
        return
    cands = IP.match_candidates(i.transition_id, actor=principal)
    if not cands:
        print("  No matching applications or pupil records - create the pupil instead.")
        return
    for n, c in enumerate(cands, 1):
        print(f"  {n:>2}) {c['kind']:<12} {c['label']:<40} {c['reason']}")
    n = prompts.ask_int("  Match to number: ")
    if n and 1 <= n <= len(cands):
        c = cands[n - 1]
        fn = IP.match_pupil if c["kind"] == "pupil" else IP.match_application
        _show_outcome(fn(i.transition_id, c["id"], actor=principal))


def _create(principal: Principal) -> None:
    i = _choose(principal)
    if not i:
        return
    d = IP.new_pupil_defaults(i.transition_id, actor=principal)
    print("  Enter keeps the value from the handover; '-' clears.")
    data = {}
    for key, value in d.items():
        v = prompts.ask(key.replace("_", " ").capitalize(), str(value) if value != "" else None)
        data[key] = value if v is None else v
    try:
        out = IP.create_pupil(i.transition_id, data, actor=principal)
    except P.DuplicatePupil as e:
        print(f"  {e}")
        if not _yes("  Create a separate record anyway?"):
            return
        out = IP.create_pupil(i.transition_id, data, actor=principal, allow_duplicate=True)
    _show_outcome(out)


def _checklist_rows(principal: Principal, i: IP.Incoming) -> list[dict]:
    rows = IP.checklist(i.transition_id, actor=principal)
    for n, r in enumerate(rows, 1):
        mark = "x" if r["done"] else " "
        by = f" - {r['done_by']} {r['done_at']}" if r["done"] else ""
        print(f"  {n:>2}) [{mark}] {r['label']:<48} ({r['owner']}){by}")
    return rows


def _checklist(principal: Principal) -> None:
    i = _choose(principal)
    if i:
        _checklist_rows(principal, i)


def _tick(principal: Principal) -> None:
    i = _choose(principal)
    if not i:
        return
    rows = _checklist_rows(principal, i)
    n = prompts.ask_int("  Item number: ")
    if n and 1 <= n <= len(rows):
        r = rows[n - 1]
        IP.tick(i.transition_id, r["key"], actor=principal, done=not r["done"],
                note=_prompt("  Note (optional): ") or None)
        print("  Unticked." if r["done"] else "  Ticked.")


def _sen(principal: Principal) -> None:
    i = _choose(principal)
    if i:
        IP.pass_sen_to_senco(i.transition_id, to=_prompt("  Passed to (SENCO's name): "),
                             actor=principal)
        print("  Recorded.")


def _safeguarding(principal: Principal) -> None:
    i = _choose(principal)
    if i:
        IP.record_safeguarding_file(i.transition_id, actor=principal)
        print("  Recorded.")


def _ks2(principal: Principal) -> None:
    i = _choose(principal)
    if not i:
        return
    s = IP.ks2_scores(IP.handover(i.transition_id, actor=principal))
    print(f"  Reading {s['reading_scaled']}, maths {s['maths_scaled']}")
    if _yes("  Import into prior attainment?"):
        IP.import_ks2(i.transition_id, actor=principal)
        print("  Imported.")


def _complete(principal: Principal) -> None:
    i = _choose(principal)
    if i:
        start = _prompt(f"  Start date [{i.effective_date or 'today'}]: ") or None
        IP.complete(i.transition_id, actor=principal, start_date=start)
        print("  Completed.")


def _unmatch(principal: Principal) -> None:
    i = _choose(principal)
    if i:
        IP.unmatch(i.transition_id, actor=principal, reason=_prompt("  Reason: "))
        print("  Unmatched.")


def _log(principal: Principal) -> None:
    i = _choose(principal)
    if i:
        for r in IP.step_log(i.transition_id, actor=principal):
            print(f"  {r['at']:<20} {r['source']:<9} {r['who'] or '':<12} {r['step']:<22} "
                  f"{r['note']}")


def _refresh(principal: Principal) -> None:
    notes = IP.refresh_matches(actor=principal)
    print("\n".join(f"  - {n}" for n in notes) or "  Nothing new to match.")


def _export(principal: Principal) -> None:
    path = _prompt("  Save CSV to (e.g. incoming_primary.csv): ")
    if path:
        print(f"  Exported {IP.export_csv(path, actor=principal)} transfer(s).")


_OPTIONS = {"1": _queue, "2": _handover, "3": _ack, "4": _reject, "5": _match, "6": _create,
            "7": _checklist, "8": _tick, "9": _sen, "10": _safeguarding, "11": _ks2,
            "12": _complete, "13": _unmatch, "14": _log, "15": _refresh, "16": _export}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("incoming.open")
        print("\n  ── Incoming from Primary ──")
        print("    1) Queue\n    2) Handover\n    3) Acknowledge\n    4) Reject\n    5) Match "
              "to a pupil or application\n    6) Create pupil from handover\n    7) Checklist"
              "\n    8) Tick / untick an item\n    9) SEN passed to SENCO")
        if IP.is_safeguarding_lead(principal):
            print("   10) Safeguarding file received")
        print("   11) Import KS2\n   12) Complete (admit)\n   13) Unmatch\n   14) Step log"
              "\n   15) Refresh matches\n   16) Export CSV\n    0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        fn = _OPTIONS.get(choice)
        if fn is None:
            print("  Invalid selection.")
            continue
        try:
            fn(principal)
        except (*_ERRORS, OSError) as e:
            _problem(e)
        _pause()
