"""A pupil's journey across the linked platform, in the terminal.

1 Show journey, 2 Learner 360, 3 Transfers in / out, 4 Transfer events,
5 Possible duplicates, 6 Merge two journeys, 7 Not the same person, 8 Link
to an existing journey, 9 Register on the platform, 10 History. Duplicates,
merge and linking are for data managers only. Rules live in
:mod:`modules.progression.domain.student_journey`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.progression.domain import student_journey as SJ
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (SJ.ValidationError, SJ.PermissionDenied, SJ.NotFound)
_problem = prompts.problem


def _pupil(msg: str = "  Pupil (admission number, UPN, ID or name): ") -> P.Pupil | None:
    """A pupil by admission number, UPN, ID or (part of) a name; leavers too."""
    ref = _prompt(msg)
    if not ref:
        return None
    try:
        return SJ._pupil(ref)
    except SJ.NotFound:
        found = P.list_pupils(search=ref, roll_status=None)
    if not found:
        raise SJ.NotFound(f"No pupil matching {ref}")
    if len(found) == 1:
        return found[0]
    for n, p in enumerate(found[:20], 1):
        print(f"  {n:>2}) {p.admission_no:<10} {p.display_name:<30} {p.date_of_birth or ''}")
    n = prompts.ask_int("  Which pupil: ")
    return found[n - 1] if n and 1 <= n <= min(len(found), 20) else None


def _who(d: dict[str, Any]) -> str:
    return (f"{d.get('legal_first_name') or ''} {d.get('legal_last_name') or ''} "
            f"{d.get('date_of_birth') or ''}").strip()


def _show(principal: Principal) -> None:
    p = _pupil()
    if p:
        print("\n" + SJ.journey_text(SJ.journey(p, actor=principal)))


def _l360(principal: Principal) -> None:
    p = _pupil()
    if p:
        print("\n" + SJ.learner_text(SJ.learner_view(p, actor=principal)))


def _transfers(principal: Principal) -> list[SJ.Transfer]:
    p = _pupil()
    if not p:
        return []
    rows = SJ.transfers(p, actor=principal)
    if not rows:
        print("  No transfers in or out.")
    for n, t in enumerate(rows, 1):
        print(f"  {n:>2}) {t.direction:<5} {t.label:<36} {t.status:<18} "
              f"{t.effective_date or '':<11} {t.reason or ''}")
    return rows


def _events(principal: Principal) -> None:
    rows = _transfers(principal)
    n = prompts.ask_int("  Transfer number: ") if rows else None
    if not n or not 1 <= n <= len(rows):
        return
    for e in SJ.transfer_events(rows[n - 1].transition_id, actor=principal):
        print(f"  {e.get('at') or '':<20} {e.get('step') or '':<22} {e.get('actor') or '':<12} "
              f"{e.get('note') or ''}")


def _dups(principal: Principal) -> list[dict[str, Any]]:
    ref = _prompt("  Pupil (blank = the whole register): ")
    rows = SJ.duplicates(ref or None, actor=principal)
    if not rows:
        print("  No possible duplicates.")
    for n, r in enumerate(rows, 1):
        print(f"  {n:>2}) score {r['score']:>3}  {_who(r['journey'])}  <->  "
              f"{_who(r['duplicate'])}\n       {'; '.join(r['reasons'])}")
    return rows


def _choose_dup(principal: Principal) -> dict[str, Any] | None:
    rows = _dups(principal)
    n = prompts.ask_int("  Pair number: ") if rows else None
    return rows[n - 1] if n and 1 <= n <= len(rows) else None


def _merge(principal: Principal) -> None:
    r = _choose_dup(principal)
    if not r:
        return
    print(f"  {r['duplicate_id']} folds into {r['journey_id']}.")
    reason = _prompt("  Why are these the same person? ")
    force = _yes("  Merge even if the platform sees a conflict?")
    if _yes("  Merge now?"):
        SJ.merge(r["journey_id"], r["duplicate_id"], actor=principal, reason=reason,
                 force=force)
        print("  Merged.")


def _not_dup(principal: Principal) -> None:
    r = _choose_dup(principal)
    if r:
        SJ.not_duplicate(r["journey_id"], r["duplicate_id"], actor=principal,
                         reason=_prompt("  Reason (optional): "))
        print("  Marked as different people.")


def _link(principal: Principal) -> None:
    p = _pupil()
    if not p:
        return
    j = SJ.journey(p, actor=principal)
    if j.linked:
        print(f"  Already linked to {j.journey_id}.")
        return
    if not j.candidates:
        print("  No possible journeys - use Register instead.")
        return
    for n, c in enumerate(j.candidates, 1):
        print(f"  {n:>2}) {c['journey_id']}  {_who(c)}  ({c['_reason']})")
    n = prompts.ask_int("  Journey number: ")
    if n and 1 <= n <= len(j.candidates):
        SJ.link(p, j.candidates[n - 1]["journey_id"], actor=principal)
        print("  Linked.")


def _register(principal: Principal) -> None:
    p = _pupil()
    if p and _yes(f"  Register {p.display_name} on the linked platform?"):
        print(f"  Journey {SJ.register(p, actor=principal)}.")


def _history(_principal: Principal) -> None:
    p = _pupil("  Pupil (blank = everyone): ")
    pid = p.pupil_id if p else None
    for h in SJ.history(pid, limit=50):
        print(f"  {h['at']}  {h['actor'] or '':<12} {h['action']:<14} {h['journey_id'] or '':<38}"
              + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


_OPTIONS = {"1": _show, "2": _l360, "3": _transfers, "4": _events, "5": _dups, "6": _merge,
            "7": _not_dup, "8": _link, "9": _register, "10": _history}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("journey.open")
        print("\n  ── Student Journey ──")
        print("    1) Show journey\n    2) Learner 360\n    3) Transfers in / out\n    4) Transfer "
              "events")
        if SJ.is_data_manager(principal):
            print("    5) Possible duplicates\n    6) Merge two journeys\n    7) Not the same "
                  "person\n    8) Link to an existing journey\n    9) Register on the platform")
        print("   10) History\n    0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        fn = _OPTIONS.get(choice)
        if fn is None:
            print("  Invalid selection.")
            continue
        try:
            fn(principal)
        except _ERRORS as e:
            _problem(e)
        _pause()
