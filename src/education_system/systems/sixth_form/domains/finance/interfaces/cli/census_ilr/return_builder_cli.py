"""CLI flows for the generated census / ILR return, attendance extract,
funding summary and 16-18 measures (added to the Census / ILR submenu).
"""

from __future__ import annotations

import datetime as _dt
import logging

from education_system.systems.sixth_form.domains.finance.domain.census_ilr import (
    census_ilr as core,
    funding_summary as funding,
    return_builder as builder,
    return_export as export,
    return_validation as validation,
)
from education_system.systems.sixth_form.domains.finance.interfaces.cli.census_ilr.census_ilr_cli import (
    _UserAbort,
    _input,
    _pause,
    _pick_from,
    _pick_return,
)

logger = logging.getLogger(__name__)

_ERRORS = (core.ValidationError, ValueError, PermissionError)


def _show_error(e: Exception) -> None:
    print(f"\n  ✗ {e}")
    _pause()


def settings_flow() -> None:
    s = builder.get_settings()
    print("\n  A sixth form in a school files the school census; a "
          "sixth-form college files the ILR.")
    route = _pick_from("Route", list(builder.ROUTES),
                       default=s["route"] or builder.DEFAULT_ROUTE)
    try:
        builder.set_route(route)
        for key, label in (("ukprn", "UKPRN"),
                           ("provider_name", "Provider name"),
                           ("laestab", "LAESTAB (school census)"),
                           ("urn", "URN")):
            builder.set_setting(key, _input(label, default=s.get(key) or ""))
    except _ERRORS as e:
        _show_error(e)
        return
    print("\n  ✓ Settings saved.")
    _pause()


def generate_flow() -> None:
    r = _pick_return()
    print("\n  Generating (attendance extract can take a while)…")
    try:
        res = builder.generate_return(r.return_id)
    except _ERRORS as e:
        _show_error(e)
        return
    print(f"\n  ✓ {res.summary}")
    if res.attendance_summary:
        print(f"    Attendance: {res.attendance_summary}")
    for m in res.messages[:10]:
        print(f"    ! {m}")
    _pause()


def validate_rules_flow() -> None:
    r = _pick_return()
    try:
        updated = core.validate_return(r.return_id)
    except _ERRORS as e:
        _show_error(e)
        return
    print()
    print(validation.report(validation.list_findings(r.return_id)))
    print(f"\n  Return #{updated.return_id} is now {updated.status}.")
    _pause()


def findings_flow() -> None:
    r = _pick_return()
    found = validation.list_findings(r.return_id)
    print()
    print(validation.report(found) if found
          else "  No stored findings — run validation first.")
    _pause()


def learners_flow() -> None:
    r = _pick_return()
    rows = builder.list_learners(r.return_id)
    if not rows:
        print("\n  No learners — generate the return first.")
        _pause()
        return
    print(f"\n  {'#':>5}  {'Ref':<12} {'Name':<24} {'ULN':<11} {'Age':>3} "
          f"{'Hours':>6} {'Band':<8} {'CoF':<4} Overrides")
    for ln in rows:
        print(f"  {ln.learner_id:>5}  {ln.learner_ref:<12} {ln.name[:24]:<24} "
              f"{(ln.uln or '—'):<11} "
              f"{'' if ln.age_31_aug is None else ln.age_31_aug:>3} "
              f"{'' if ln.planned_hours is None else f'{ln.planned_hours:g}':>6} "
              f"{(ln.funding_band or '—'):<8} "
              f"{({1: 'Yes', 0: 'No'}.get(ln.cof_compliant, '—')):<4} "
              f"{', '.join(ln.overrides)}")
    _pause()


def edit_learner_flow() -> None:
    r = _pick_return()
    raw = _input("Learner # (from the learners list)", allow_empty=False)
    if not raw.isdigit():
        print("    Enter a number.")
        return
    ln = builder.get_learner(int(raw))
    if ln is None or ln.return_id != r.return_id:
        print("    No such learner on this return.")
        _pause()
        return
    print("  Edited fields are kept as overrides when the return is "
          "regenerated. ENTER keeps a value.")
    payload: dict = {}
    for key in builder.OVERRIDABLE_LEARNER_FIELDS:
        cur = getattr(ln, key)
        new = _input(key, default="" if cur is None else str(cur))
        if new != ("" if cur is None else str(cur)):
            payload[key] = new
    try:
        builder.update_learner(ln.learner_id, payload)
    except _ERRORS as e:
        _show_error(e)
        return
    print("\n  ✓ Saved.")
    _pause()


def clear_overrides_flow() -> None:
    raw = _input("Learner # to clear overrides for", allow_empty=False)
    if not raw.isdigit():
        return
    try:
        builder.clear_learner_overrides(int(raw))
    except _ERRORS as e:
        _show_error(e)
        return
    print("\n  ✓ Overrides cleared; the next generate refreshes the learner.")
    _pause()


def _export(kind: str) -> None:
    r = _pick_return()
    ext = "xml" if kind == "xml" else "csv"
    stem = {"csv": "return", "census_aims": "census_learning_aims",
            "xml": "ilr"}[kind]
    path = _input("Path", default=f"{stem}_{r.return_id}_"
                                  f"{_dt.date.today():%Y%m%d}.{ext}")
    try:
        saved = export.save(r.return_id, path, kind=kind)
    except core.ValidationError as e:
        print(f"\n  ✗ {e}")
        if _input("Export anyway as a DRAFT (not for submission)? y/N",
                  default="n").lower() != "y":
            return
        try:
            saved = export.save(r.return_id, path, kind=kind,
                                allow_errors=True)
        except _ERRORS as e2:
            _show_error(e2)
            return
    except PermissionError as e:
        _show_error(e)
        return
    print(f"\n  ✓ Written to {saved}")
    print(f"    {export.SPEC_NOTICE}")
    _pause()


def export_csv_flow() -> None:
    _export("csv")


def export_census_aims_flow() -> None:
    _export("census_aims")


def export_xml_flow() -> None:
    _export("xml")


def export_ilr_year_flow() -> None:
    """The year's ILR file — the same file as Enrolments → ILR Export."""
    year = _input("Academic year", default=builder.current_year())
    path = _input("Write to (path; blank = check only, no file)",
                  default="") or None
    try:
        res = export.export_ilr_csv(year, path=path)
    except _ERRORS as e:
        _show_error(e)
        return
    print(f"\n  {res.academic_year}: {res.learners} learner(s), "
          f"{res.deliveries} learning deliver(y/ies)"
          + (f" — written to {res.path}" if res.path else " — no file written"))
    for p in res.problems[:200]:
        aim = f" aim #{p.aim_id}" if p.aim_id else ""
        print(f"    {p.severity}: {p.student_id}{aim} {p.field}: {p.message}")
    if len(res.problems) > 200:
        print(f"    … {len(res.problems) - 200} more")
    if not res.problems:
        print("  ✓ No problems found")
    print(f"    {export.SPEC_NOTICE}")
    _pause()


def attendance_census_flow() -> None:
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_census,
    )
    start, _end = builder.year_bounds(builder.current_year())
    kind = _pick_from("Kind", ["census", "ilr"],
                      default=builder.route_attendance_kind(builder.get_route()))
    d_from = _input("From", default=start)
    d_to = _input("To", default=_dt.date.today().isoformat())
    print("\n  Building…")
    try:
        ret = builder.attendance_extract(kind, d_from, d_to, fresh=True)
    except _ERRORS as e:
        _show_error(e)
        return
    print(f"\n  {ret.summary}\n")
    print(attendance_census.validation_report(ret))
    if ret.submittable and _input("Save CSV? y/N", default="n").lower() == "y":
        path = _input("Path", default=f"attendance_{kind}.csv")
        try:
            print(f"\n  ✓ Written to {attendance_census.save(ret, path)}")
        except _ERRORS as e:
            print(f"\n  ✗ {e}")
    _pause()


def funding_summary_flow() -> None:
    year = _input("Academic year", default=builder.current_year())
    as_of = _input("As of", default=_dt.date.today().isoformat())
    try:
        s = funding.funding_summary(year, as_of=as_of)
    except _ERRORS as e:
        _show_error(e)
        return
    print()
    print(s.text())
    _pause()


def measures_flow() -> None:
    from education_system.systems.sixth_form.interfaces.cli.governance.compliance.measures import (
        measures_cli,
    )
    measures_cli.show_measures()


MENU_ITEMS = [
    ("Return settings (route/UKPRN)", settings_flow),
    ("Generate return from records", generate_flow),
    ("Validate return (rules)", validate_rules_flow),
    ("Show validation findings", findings_flow),
    ("Return learners", learners_flow),
    ("Edit return learner", edit_learner_flow),
    ("Clear learner overrides", clear_overrides_flow),
    ("Export return CSV", export_csv_flow),
    ("Export census aims CSV", export_census_aims_flow),
    ("Export ILR XML", export_xml_flow),
    ("Attendance census extract", attendance_census_flow),
    ("Funding summary", funding_summary_flow),
    ("16-18 measures", measures_flow),
    ("ILR export (year CSV)", export_ilr_year_flow),
]

__all__ = ["MENU_ITEMS"]
