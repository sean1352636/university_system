"""Attainment 8 & Progress 8 in the terminal.

The old two menus are kept as options 1 and 2 with their options in place:
Attainment 8 1-5 (set / update, list, view, cohort summary, delete) and
Progress 8 1-6 (set / update, list, view, refresh A8, cohort summary,
delete); each gains a Calculate option and A8 gains export. Options 3-5
(headline measures, KS2 prior attainment, P8 estimates) are new. Rules live
in :mod:`modules.assessment.domain.headline_measures`.
"""

from __future__ import annotations

from education_system.systems.secondary.modules.assessment.domain import headline_measures as HM
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (HM.ValidationError, HM.PermissionDenied, HM.NotFound)


_problem = prompts.problem


def _run(fn) -> None:
    try:
        fn()
    except _ERRORS as e:
        _problem(e)


def _num(v, signed: bool = False) -> str:
    if v is None:
        return "-"
    return f"{v:+.2f}" if signed else f"{v:g}"


def _pupil() -> P.Pupil | None:
    ref = _prompt("  Pupil (admission number or UPN): ")
    if not ref:
        return None
    p = P.find_by_reference(ref)
    if p is None:
        print("  No pupil with that admission number.")
    return p


def _year(default: str | None = None) -> int | None:
    y = _prompt(f"  Year (7-11{', blank = ' + default if default else ', blank = all'}): ")
    return int(y) if y.isdigit() else (int(default) if default else None)


def _ay() -> str:
    return _prompt(f"  Academic year [{HM.current_year()}]: ") or HM.current_year()


def _source(blank: str = "all") -> str | None:
    s = _prompt(f"  Source ({' / '.join(HM.SOURCES)}, blank = {blank}): ").title()
    return s or None


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("headline.view")
        print("\n── Attainment 8 & Progress 8 ──")
        print("   1) Attainment 8\n   2) Progress 8\n   3) Headline measures"
              "\n   4) KS2 prior attainment\n   5) Progress 8 estimates\n   0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        fn = {"1": _a8_menu, "2": _p8_menu, "3": _headline, "4": _ks2_menu,
              "5": _estimates_menu}.get(choice)
        if fn:
            fn(principal)


# ── Attainment 8 (old menu 1-5) ──────────────────────────────────────

def _a8_table(rows: list[HM.A8Record]) -> None:
    if not rows:
        print("  (no records)")
        return
    print(f"  {'ID':<5} {'Pupil':<10} {'Name':<20} {'Yr':<3} {'Academic yr':<11} "
          f"{'Source':<9} {'Eng':<5} {'Mth':<4} {'EBacc':<11} {'Open':<11} {'Total':<6} "
          f"{'A8':<5} Method")
    for r in rows:
        eb = "/".join(r.grade(f"ebacc{i}_grade") or "-" for i in (1, 2, 3))
        op = "/".join(r.grade(f"open{i}_grade") or "-" for i in (1, 2, 3))
        print(f"  {r.record_id:<5} {r.admission_no:<10} {r.pupil_name[:20]:<20} "
              f"{r.year_group:<3} {r.academic_year:<11} {r.record_source:<9} "
              f"{(r.english_grade or '-'):<5} {(r.maths_grade or '-'):<4} {eb:<11} {op:<11} "
              f"{r.total_points:<6g} {r.average_grade:<5g} {r.method}")


def _a8_menu(principal: Principal) -> None:
    while True:
        print("\n── Attainment 8 ──")
        print("   1) Set / update a pupil's record\n   2) List records"
              "\n   3) View pupil record\n   4) Cohort summary\n   5) Delete record"
              "\n   6) Calculate for a year group\n   7) Export CSV\n   0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        fn = {"1": _a8_upsert, "2": _a8_list, "3": _a8_view, "4": _a8_summary,
              "5": _a8_delete, "6": _a8_calculate, "7": _a8_export}.get(choice)
        if fn:
            _run(lambda: fn(principal))
            _pause()


def _a8_upsert(principal: Principal) -> None:
    p = _pupil()
    if p is None:
        return
    ay, src = _ay(), _source(HM.DEFAULT_SOURCE) or HM.DEFAULT_SOURCE
    old = HM.get_for(p.pupil_id, ay, src)
    print("  Slots (1-9 or U; combined like 6-5; BTEC D*, D, M, P). Enter keeps, '-' clears.")
    data = {"pupil_id": p.pupil_id, "academic_year": ay, "record_source": src}
    for slot in HM.SLOTS:
        cur = old.grade(slot) if old else None
        raw = _prompt(f"  {HM.SLOT_LABELS[slot]}" + (f" [{cur}]" if cur else "") + ": ")
        data[slot] = None if raw == "-" else (raw or cur)
    data["english_double"] = not _yes("  Only one of English language / literature taken?")
    data["notes"] = _prompt("  Notes: ") or (old.notes if old else None)
    r = HM.upsert(data, actor=principal)
    print(f"  ✓ Saved: A8 {r.total_points:g} (average grade {r.average_grade:g})")


def _a8_list(principal: Principal) -> None:
    rows = HM.list_records(year_group=_year(), academic_year=_prompt(
        "  Academic year (blank = all): ") or None, record_source=_source())
    _a8_table(rows)
    activity_log.record("headline.a8_list", results=len(rows))


def _a8_view(principal: Principal) -> None:
    p = _pupil()
    if p is None:
        return
    rows = HM.list_records(pupil_id=p.pupil_id)
    if not rows:
        print("  No Attainment 8 records.")
        return
    for r in rows:
        print(f"\n  {r.record_source} {r.academic_year} - {r.method}"
              + (f" from {r.based_on}" if r.based_on else ""))
        for d in r.slot_detail:
            pts = f"{d['points']:g}" + (" (x2)" if d.get("weight") == 2 else "")
            print(f"    {d['slot']:<12} {(d.get('subject') or '-'):<26} "
                  f"{(d.get('grade') or '-'):<5} {pts}"
                  + (f"  {d['note']}" if d.get("note") else ""))
        print(f"    A8 {r.total_points:g} · average grade {r.average_grade:g} · EBacc "
              "entered " + ("-" if r.ebacc_entered is None else
                            "yes" if r.ebacc_entered else "no"))


def _a8_summary(principal: Principal) -> None:
    s = HM.cohort_summary(year_group=_year(), academic_year=_prompt(
        "  Academic year (blank = all): ") or None, record_source=_source())
    if not s["records"]:
        print("  No records match.")
        return
    print(f"  Records: {s['records']} · average A8 {s['average_a8']} (average grade "
          f"{s['average_grade']}) · highest {s['highest']:g} · lowest {s['lowest']:g}")
    print("  By source: " + ", ".join(f"{k} {v}" for k, v in s["by_source"].items()))
    for b, n in s["bands"].items():
        print(f"    {b:<9} {n}")


def _a8_delete(principal: Principal) -> None:
    rid = _prompt("  Record ID: ")
    if rid.isdigit():
        r = HM.get(int(rid))
        if _yes(f"  Delete the {r.record_source} record for {r.pupil_name} "
                f"({r.academic_year})?"):
            HM.delete(r.record_id, actor=principal)
            print("  ✓ Deleted")


def _a8_calculate(principal: Principal) -> None:
    year = _year("11")
    src = _source("Actual") or "Actual"
    point = None
    if src == "Predicted":
        from education_system.systems.secondary.modules.assessment.domain import (
            assessment_points as AP,
        )
        pts = [pt for pt in AP.list_points(status="Published") if year in pt.years]
        for i, pt in enumerate(pts, 1):
            print(f"   {i}) {pt.name} ({pt.academic_year})")
        raw = _prompt("  Assessment point (blank = newest): ")
        point = pts[int(raw) - 1].point_id if raw.isdigit() and 0 < int(raw) <= len(pts) \
            else None
    out = HM.calculate(year, src, actor=principal, academic_year=_ay(), point_id=point,  # type: ignore[arg-type]
                       overwrite_entered=_yes("  Also replace records entered by hand?"))
    print(f"  ✓ Saved {len(out['saved'])} from {out['based_on']}")
    if out["kept"]:
        print(f"  Kept {len(out['kept'])} entered by hand")
    if out["no_data"]:
        print(f"  No grades for {len(out['no_data'])}: " + ", ".join(out["no_data"][:15]))


def _a8_export(principal: Principal) -> None:
    path = _prompt("  Save to (path .csv): ")
    if path:
        n = HM.export_csv(path, actor=principal, year_group=_year(),
                          academic_year=_prompt("  Academic year (blank = all): ") or None,
                          record_source=_source())
        print(f"  ✓ Exported {n} record(s)")


# ── Progress 8 (old menu 1-6) ────────────────────────────────────────

def _p8_table(rows: list[HM.P8Record]) -> None:
    if not rows:
        print("  (no records)")
        return
    print(f"  {'ID':<5} {'Pupil':<10} {'Name':<20} {'Yr':<3} {'Academic yr':<11} {'KS2':<6} "
          f"{'Exp A8':<7} {'A8':<6} {'P8':<7} {'A8 source':<10} Eng/Mth/EBacc/Open")
    for r in rows:
        el = "/".join(_num(getattr(r, f"p8_{e}"), True) for e in HM.ELEMENTS)
        print(f"  {r.record_id:<5} {r.admission_no:<10} {r.pupil_name[:20]:<20} "
              f"{r.year_group:<3} {r.academic_year:<11} {r.ks2_prior:<6g} "
              f"{r.expected_a8:<7g} {_num(r.attainment_8):<6} {_num(r.progress_8, True):<7} "
              f"{(r.a8_source or '-'):<10} {el}")


def _p8_menu(principal: Principal) -> None:
    while True:
        print("\n── Progress 8 ──")
        print("   1) Set / update a pupil's record\n   2) List records\n   3) View pupil record"
              "\n   4) Refresh attainment_8 (re-pull from A8 table)\n   5) Cohort summary"
              "\n   6) Delete record\n   7) Calculate for a year group\n   0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        fn = {"1": _p8_upsert, "2": _p8_list, "3": _p8_view, "4": _p8_refresh,
              "5": _p8_summary, "6": _p8_delete, "7": _p8_calculate}.get(choice)
        if fn:
            _run(lambda: fn(principal))
            _pause()


def _p8_upsert(principal: Principal) -> None:
    p = _pupil()
    if p is None:
        return
    print("  Blank KS2 = the pupil's KS2 record; blank expected A8 = the year's estimates; "
          "blank A8 = their A8 record (Actual first).")
    r = HM.upsert_p8({"pupil_id": p.pupil_id, "academic_year": _ay(),
                      "ks2_prior": _prompt("  KS2 prior attainment (80-120): ") or None,
                      "expected_a8": _prompt("  Expected A8 (0-90): ") or None,
                      "attainment_8": _prompt("  A8 (0-90): ") or None,
                      "notes": _prompt("  Notes: ") or None}, actor=principal)
    print(f"  ✓ Saved: P8 {_num(r.progress_8, True)} (A8 {_num(r.attainment_8)}, expected "
          f"{r.expected_a8:g})")


def _p8_list(principal: Principal) -> None:
    rows = HM.list_p8(year_group=_year(),
                      academic_year=_prompt("  Academic year (blank = all): ") or None)
    _p8_table(rows)
    activity_log.record("headline.p8_list", results=len(rows))


def _p8_view(principal: Principal) -> None:
    p = _pupil()
    if p is not None:
        _p8_table(HM.list_p8(pupil_id=p.pupil_id))
        k = HM.get_ks2(p.pupil_id)
        print(f"  KS2: reading {k.reading_scaled or '-'}, maths {k.maths_scaled or '-'} "
              f"(prior {k.prior})" if k else "  No KS2 data.")


def _p8_refresh(principal: Principal) -> None:
    rid = _prompt("  Record ID: ")
    if rid.isdigit():
        r = HM.refresh_a8(int(rid), actor=principal)
        print(f"  ✓ A8 {_num(r.attainment_8)} ({r.a8_source}) · P8 {_num(r.progress_8, True)}")


def _p8_summary(principal: Principal) -> None:
    s = HM.p8_summary(year_group=_year(),
                      academic_year=_prompt("  Academic year (blank = all): ") or None)
    if not s["records"]:
        print("  No Progress 8 scores match.")
        return
    print(f"  Pupils {s['records']} · average P8 {s['average_p8']:+.2f} · above zero "
          f"{s['above_zero']} · below -0.5 {s['below_minus_half']} · highest "
          f"{s['highest']:+.2f} · lowest {s['lowest']:+.2f}")


def _p8_delete(principal: Principal) -> None:
    rid = _prompt("  Record ID: ")
    if rid.isdigit():
        r = HM.get_p8(int(rid))
        if _yes(f"  Delete the Progress 8 record for {r.pupil_name} ({r.academic_year})?"):
            HM.delete_p8(r.record_id, actor=principal)
            print("  ✓ Deleted")


def _p8_calculate(principal: Principal) -> None:
    out = HM.calculate_p8(_year("11"), actor=principal, academic_year=_ay(),  # type: ignore[arg-type]
                          prefer=_source("Actual first"),
                          overwrite_entered=_yes("  Also replace records entered by hand?"))
    print(f"  ✓ Saved {len(out['saved'])} Progress 8 score(s)")
    for key, label in (("no_ks2", "no KS2 data"), ("no_a8", "no A8 record"),
                       ("kept", "entered by hand, kept")):
        if out[key]:
            print(f"  {len(out[key])} {label}: " + ", ".join(out[key][:12]))


# ── Headline measures ────────────────────────────────────────────────

def _headline(principal: Principal) -> None:
    h = HM.headline(year_group=_year("11") or 11, academic_year=_ay(),
                    record_source=_source("Actual") or "Actual")
    print(f"\n  Year {h['year_group']} · {h['academic_year']} · {h['source']}")
    print(f"  {'Group':<22} {'Pupils':<7} {'A8 n':<5} {'Avg A8':<7} {'Avg P8':<7} {'P8 n':<5} "
          f"{'E&M 4+':<7} {'E&M 5+':<7} EBacc")
    pct = lambda v: "-" if v is None else f"{v:g}%"  # noqa: E731
    for g in h["groups"]:
        print(f"  {g['group']:<22} {g['pupils']:<7} {g['with_a8']:<5} "
              f"{_num(g['average_a8']):<7} {_num(g['average_p8'], True):<7} "
              f"{g['with_p8']:<5} {pct(g['eng_maths_4']):<7} {pct(g['eng_maths_5']):<7} "
              f"{pct(g['ebacc_entry'])}")
    gap = h["disadvantaged_gap"]
    print(f"\n  Disadvantaged gap: A8 {_num(gap['average_a8'])}, P8 "
          f"{_num(gap['average_p8'], True)}, Eng & maths 4+ {_num(gap['eng_maths_4'])} pts")
    print(f"  {len(h['missing_a8'])} with no {h['source']} A8 record; "
          f"{len(h['missing_ks2'])} with no KS2 data")
    activity_log.record("headline.measures", source=h["source"])
    _pause()


# ── KS2 prior attainment ─────────────────────────────────────────────

def _ks2_menu(principal: Principal) -> None:
    while True:
        print("\n── KS2 prior attainment ──")
        print("   1) List\n   2) Pupils with no KS2 data\n   3) Set a pupil's KS2"
              "\n   4) Clear a pupil's KS2\n   5) Import CSV (admission_no, reading, maths)"
              "\n   0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        if choice in ("1", "2"):
            rows = HM.ks2_list(year_group=_year("11"), missing_only=choice == "2")
            for p, k in rows:
                print(f"  {p.admission_no:<10} {p.display_name[:24]:<24} Y{p.year_group:<3} "
                      + (f"reading {k.reading_scaled or '-':<4} maths {k.maths_scaled or '-':<4}"
                         f" prior {k.prior}  ({k.source})" if k else "no KS2 data"))
            print(f"  {len(rows)} pupil(s)")
        elif choice == "3":
            def go() -> None:
                p = _pupil()
                if p is None:
                    return
                k = HM.set_ks2(p.pupil_id, {
                    "reading_scaled": _prompt("  Reading scaled score (80-120): ") or None,
                    "maths_scaled": _prompt("  Maths scaled score (80-120): ") or None,
                    "source": _prompt(f"  Source ({', '.join(HM.KS2_SOURCES)}) [Entered]: ")
                    or "Entered"}, actor=principal)
                print(f"  ✓ Saved: prior attainment {k.prior}")
            _run(go)
        elif choice == "4":
            def go() -> None:
                p = _pupil()
                if p is not None and _yes(f"  Clear {p.display_name}'s KS2 data?"):
                    print("  ✓ Cleared" if HM.clear_ks2(p.pupil_id, actor=principal)
                          else "  Nothing to clear")
            _run(go)
        elif choice == "5":
            def go() -> None:
                path = _prompt("  CSV path: ")
                if path:
                    print(f"  ✓ Imported {HM.import_ks2(path, actor=principal)['imported']}")
            _run(go)
        _pause()


# ── P8 estimates ─────────────────────────────────────────────────────

def _estimates_menu(principal: Principal) -> None:
    while True:
        print("\n── Progress 8 estimates ──")
        print("   1) Show a year\n   2) Add / change a row\n   3) Delete a row"
              "\n   4) Import CSV (ks2_from, expected_a8, …)\n   5) Copy from another year"
              "\n   0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        ay = _ay()
        if choice == "1":
            rows = HM.estimates(ay)
            print(f"  {'KS2 from':<9} {'Exp A8':<7} Eng / Mth / EBacc / Open")
            for e in rows:
                print(f"  {e.ks2_from:<9g} {e.expected_a8:<7g} " + " / ".join(
                    _num(getattr(e, f"expected_{el}")) for el in HM.ELEMENTS))
            print(f"  {len(rows)} row(s)" + ("" if rows else
                                             f" - years with estimates: "
                                             f"{', '.join(HM.estimate_years()) or 'none'}"))
        elif choice == "2":
            _run(lambda: HM.set_estimate(ay, {
                "ks2_from": _prompt("  KS2 from: "),
                "expected_a8": _prompt("  Expected A8 (0-90): "),
                **{f"expected_{el}": _prompt(f"  Expected {el} (optional): ") or None
                   for el in HM.ELEMENTS}}, actor=principal) and print("  ✓ Saved"))
        elif choice == "3":
            raw = _prompt("  KS2 from: ")
            try:
                ks2 = float(raw)
            except ValueError:
                print("  Give the row's KS2 value (a number).")
            else:
                _run(lambda: print("  ✓ Deleted" if HM.delete_estimate(
                    ay, ks2, actor=principal) else "  No such row"))
        elif choice == "4":
            path = _prompt("  CSV path: ")
            if path and _yes(f"  Replace the {ay} estimates with this file?"):
                _run(lambda: print(f"  ✓ Imported "
                                   f"{HM.import_estimates(ay, path, actor=principal)['imported']}"))
        elif choice == "5":
            src = _prompt("  Copy from academic year: ")
            _run(lambda: print(f"  ✓ Copied {HM.copy_estimates(src, ay, actor=principal)} "
                               "row(s)"))
        _pause()
