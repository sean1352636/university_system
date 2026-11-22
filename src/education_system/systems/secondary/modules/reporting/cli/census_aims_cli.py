"""Learner aims in the terminal - the old Census menu's 22-28: List all
aims, Active aims, Aims for return, Aims for learner, New aim, Edit aim,
Delete aim (and the aim lines of 30 Summary). Rules:
:mod:`modules.reporting.domain.census_aims`."""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.reporting.cli import report_prompts as RP
from education_system.systems.secondary.modules.reporting.domain import census_aims as CA
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt


def _show(rows: list[CA.Aim]) -> None:
    RP.table(["Id", "Learner", "Name", "Aim ref", "Title", "Funding model", "Start", "Status",
              "Hours", "Value", "Return"],
             [[a.aim_id, a.learner_ref, a.learner_name or "", a.aim_reference,
               a.aim_title or "", a.funding_model, a.start_date, a.status,
               a.planned_hours or 0, a.funding_band_value or "", a.return_id or ""]
              for a in rows], limit=None, width=24)
    print(f"\n  {len(rows)} aim(s).")


def list_all(principal: Principal) -> None:
    _show(CA.list_aims(actor=principal))


def list_active(principal: Principal) -> None:
    _show(CA.list_aims(actor=principal, active_only=True))


def for_return(principal: Principal) -> None:
    rid = prompts.ask_int("  Return id: ")
    if rid is not None:
        _show(CA.aims_for_return(rid, actor=principal))


def for_learner(principal: Principal) -> None:
    ref = _prompt("  Learner (admission no., UPN, ref or name): ")
    if ref:
        _show(CA.aims_for_learner(ref, actor=principal))


def _collect(a: CA.Aim | None) -> dict[str, Any]:
    """Each field with the current value in [brackets]; Enter keeps it, '-'
    clears it."""
    out: dict[str, Any] = {}

    def cur(key: str) -> str | None:
        v = getattr(a, key) if a is not None else None
        return None if v is None else str(v)

    for key, label, options in (
            ("return_id", "Return id (blank = none)", None),
            ("learner_ref", "Learner (admission no., UPN or ref)", None),
            ("learner_name", "Learner name", None), ("ukprn", "UKPRN", None),
            ("uln", "ULN", None), ("aim_type", "Aim type", CA.AIM_TYPES),
            ("aim_reference", "Aim reference", None), ("aim_title", "Aim title", None),
            ("funding_model", "Funding model", CA.FUNDING_MODELS),
            ("start_date", "Start date (YYYY-MM-DD)", None),
            ("planned_end_date", "Planned end date (YYYY-MM-DD)", None),
            ("actual_end_date", "Actual end date (YYYY-MM-DD)", None),
            ("completion_code", "Completion code (1/2/3/6/7/10)", None),
            ("outcome_code", "Outcome code", None), ("status", "Status", CA.STATUSES),
            ("planned_hours", "Planned hours", None), ("actual_hours", "Actual hours", None),
            ("funding_band_value", "Funding band value", None),
            ("delivery_location", "Delivery location", None),
            ("partner_ukprn", "Partner UKPRN", None), ("notes", "Notes", None)):
        if options:
            v = prompts.pick(label, options, cur(key))
        else:
            v = prompts.ask(label, cur(key),
                            required=key in ("learner_ref", "aim_reference", "start_date"))
        if v is not None:
            out[key] = v
    return out


def new(principal: Principal) -> None:
    a = CA.create_aim(_collect(None), actor=principal)
    print(f"\n  Created aim #{a.aim_id}" + (" (linked to the pupil record)" if a.pupil_id
                                            else ""))


def _pick(principal: Principal) -> CA.Aim | None:
    aid = prompts.ask_int("  Aim id: ")
    return CA.get_aim(aid, actor=principal) if aid is not None else None


def edit(principal: Principal) -> None:
    a = _pick(principal)
    if a is not None:
        CA.update_aim(a.aim_id, _collect(a), actor=principal)
        print(f"\n  Updated aim #{a.aim_id}")


def delete(principal: Principal) -> None:
    a = _pick(principal)
    if a is not None and prompts.yes(f"  Delete aim #{a.aim_id} ({a.aim_reference} for "
                                     f"{a.learner_ref})?"):
        CA.delete_aim(a.aim_id, actor=principal)
        print(f"\n  Deleted aim #{a.aim_id}")


def summary(principal: Principal) -> None:
    s = CA.summary(principal)
    print(f"\n  Total aims       {s['total']} ({s['learners']} learner(s))")
    for k in ("continuing", "completed", "achieved", "withdrawn"):
        print(f"  {k.capitalize():<16} {s[k]}")
    print("  By aim status:", ", ".join(f"{k} {v}" for k, v in s["by_status"].items()) or "-")


__all__ = ["delete", "edit", "for_learner", "for_return", "list_active", "list_all", "new",
           "summary"]
