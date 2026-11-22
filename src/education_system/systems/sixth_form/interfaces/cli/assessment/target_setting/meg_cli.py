"""CLI flow for minimum expected grades (offered from the Value Added
submenu; Target Setting's own submenu is unchanged)."""

from __future__ import annotations

import logging

from education_system.systems.sixth_form.domain.assessment.target_setting import (
    meg as data,
)

logger = logging.getLogger(__name__)


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


def meg_flow() -> None:
    subject = _input("Subject (blank = all)")
    print("\n  Calculating…")
    rows = data.meg_report(subject=subject or None)
    if any(r.placeholder for r in rows):
        print("  !! MEGs come from the PLACEHOLDER benchmark table - replace it "
              "(Value Added > Benchmark bands).")
    print(f"\n  {'Student':<10} {'Name':<20} {'Subject':<18} {'APS':<5} "
          f"{'MEG':<4} {'MTE':<4} Action")
    for r in rows:
        aps = "" if r.aps is None else f"{r.aps:.2f}"
        print(f"  {r.student_id:<10} {r.student_name[:20]:<20} "
              f"{r.subject[:18]:<18} {aps:<5} {r.meg_grade or '—':<4} "
              f"{r.current_mte or '—':<4} {r.action} {r.note}")
    if rows and _input("\n  Write MEGs into Target Setting? y/N",
                       "n").lower() == "y":
        overwrite = _input("Replace a different hand-set MTE? y/N",
                           "n").lower() == "y"
        res = data.apply_megs(rows, overwrite=overwrite)
        print(f"\n  ✓ {res.summary}")
        for sid, sub, why in res.skipped[:15]:
            print(f"    skipped {sid} {sub}: {why}")
    _pause()


MENU_ITEMS = [("Minimum expected grades (MEG)", meg_flow)]

__all__ = ["meg_flow", "MENU_ITEMS"]
