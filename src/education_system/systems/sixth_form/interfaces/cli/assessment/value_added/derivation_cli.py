"""CLI flows for the VA benchmark table and derived value added
(added to the Value Added submenu)."""

from __future__ import annotations

import logging

from education_system.systems.sixth_form.domain.academics.qualifications import (
    grade_scales,
)
from education_system.systems.sixth_form.domain.assessment.value_added import (
    derivation as data,
)

logger = logging.getLogger(__name__)

PLACEHOLDER_WARNING = ("  !! PLACEHOLDER benchmarks in use (linear, one grade "
                       "per GCSE point) - NOT ALPS/DfE data.\n"
                       "     Replace them with your ALPS / L3VA benchmarks.")


def _input(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return raw or default


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _warn_placeholder() -> None:
    if data.placeholder_in_use():
        print(PLACEHOLDER_WARNING)


def list_bands_flow() -> None:
    _warn_placeholder()
    print(f"\n  {'#':>4}  {'Type':<22} {'Subject':<18} {'Avg GCSE':<14} "
          f"{'Exp':<5} {'MEG':<5} Source")
    for b in data.list_bands():
        print(f"  {b.band_id:>4}  {b.qualification_type:<22} "
              f"{(b.subject or '(all)')[:18]:<18} {b.range_label:<14} "
              f"{b.expected_grade:<5} {b.minimum_grade:<5} "
              f"{'[PLACEHOLDER] ' if b.is_placeholder else ''}{b.source[:50]}")
    _pause()


def _collect(band: data.Band | None) -> dict:
    types = list(grade_scales.QUALIFICATION_TYPES)
    print("  Types: " + ", ".join(types))
    g = (lambda k, d="": _input(k, d))
    return {
        "qualification_type": g("Qualification type",
                                band.qualification_type if band else "A Level"),
        "subject": g("Subject (blank = all)", (band.subject or "") if band else ""),
        "min_aps": g("Average GCSE from", str(band.min_aps) if band else ""),
        "max_aps": g("Average GCSE below (blank = no limit)",
                     "" if not band or band.max_aps is None else str(band.max_aps)),
        "expected_grade": g("Expected grade", band.expected_grade if band else ""),
        "meg_grade": g("MEG (blank = expected)",
                       (band.meg_grade or "") if band else ""),
        "source": g("Source (e.g. ALPS 2025)",
                    "" if not band or band.is_placeholder else band.source),
        "notes": g("Notes", (band.notes or "") if band else ""),
    }


def add_band_flow() -> None:
    try:
        b = data.add_band(_collect(None))
    except (data.ValidationError, ValueError) as e:
        print(f"\n  ✗ {e}")
    else:
        print(f"\n  ✓ Band #{b.band_id} added.")
    _pause()


def edit_band_flow() -> None:
    raw = _input("Band #")
    if not raw.isdigit() or data.get_band(int(raw)) is None:
        print("    No such band.")
        _pause()
        return
    band = data.get_band(int(raw))
    try:
        data.update_band(band.band_id, _collect(band))
    except (data.ValidationError, ValueError) as e:
        print(f"\n  ✗ {e}")
    else:
        print("\n  ✓ Saved.")
    _pause()


def delete_band_flow() -> None:
    raw = _input("Band # to delete")
    if raw.isdigit() and _input("Really delete? y/N", "n").lower() == "y":
        print("  ✓ Deleted." if data.delete_band(int(raw)) else "  No such band.")
    _pause()


def restore_placeholder_flow() -> None:
    if _input("Re-seed the linear placeholder (your own bands are kept)? y/N",
              "n").lower() == "y":
        print(f"  ✓ {data.restore_placeholder()} placeholder band(s) seeded.")
    _pause()


def derived_va_flow() -> None:
    year = _input("Academic year (blank = all)")
    ry = _input("Result year (blank = any)")
    subject = _input("Subject (blank = all)")
    print("\n  Calculating…")
    c = data.derive_cohort(academic_year=year or None, subject=subject or None,
                           results_year=int(ry) if ry.isdigit() else None)
    if c.placeholder_in_use:
        print(PLACEHOLDER_WARNING)
    mean = "—" if c.mean_va is None else f"{c.mean_va:+.2f}"
    print(f"\n  Cohort VA: {mean} grades over {c.with_results} result(s)")
    print("\n  By subject:")
    for s in c.by_subject:
        va = "—" if s.mean_va is None else f"{s.mean_va:+.2f}"
        print(f"    {s.subject[:24]:<24} learners {s.learners:>3}  "
              f"results {s.with_results:>3}  mean VA {va}")
    if _input("\n  Show learner rows? y/N", "n").lower() == "y":
        for r in c.rows:
            va = "" if r.va is None else f"{r.va:+.0f}"
            aps = "" if r.aps is None else f"{r.aps:.2f}"
            print(f"    {r.student_id:<10} {r.student_name[:20]:<20} "
                  f"{r.subject[:18]:<18} APS {aps:<5} exp "
                  f"{r.expected_grade or '—':<4} act {r.actual_grade or '—':<4} "
                  f"VA {va:<3} {r.note}")
    if _input("\n  Write these into VA records? y/N", "n").lower() == "y":
        session = _input("Exam session (e.g. 'Summer 2026')")
        overwrite = _input("Replace expected grades already typed in? y/N",
                           "n").lower() == "y"
        res = data.apply_to_records(session, rows=c.rows,
                                    overwrite_expected=overwrite)
        print(f"\n  ✓ {res.summary}")
        for sid, sub, why in res.skipped[:15]:
            print(f"    skipped {sid} {sub}: {why}")
    _pause()


MENU_ITEMS = [
    ("Benchmark bands",          list_bands_flow),
    ("Add benchmark band",       add_band_flow),
    ("Edit benchmark band",      edit_band_flow),
    ("Delete benchmark band",    delete_band_flow),
    ("Restore placeholder bands", restore_placeholder_flow),
    ("Derived VA (from GCSEs)",  derived_va_flow),
]

__all__ = ["MENU_ITEMS"]
