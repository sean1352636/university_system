"""Enrolment CLI: reports, analytics, import/export and the academic-year list."""

from __future__ import annotations

import logging
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.admissions.enrolments.enrolments import (
    DEFAULT_STATUS,
    STATUSES,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.enrolments._common import (
    _UserAbort,
    _compute_capacity_utilisation,
    _default_academic_year,
    _input,
    _load_academic_years,
    _next_academic_year,
    _pause,
    _prompt_academic_year,
    _render_status_bar_chart,
    _report_bulk,
    _resolve_enrolment,
    _status_counts,
    _student_names,
    _write_simple_pdf,
)

logger = logging.getLogger(__name__)



# ════════════════════════════════════════════════════════════════════
# Reports & analytics (features 21–28)
# ════════════════════════════════════════════════════════════════════

def enrolment_dashboard() -> None:
    """Feature #21 — headline totals, a status bar chart, and breakdowns."""
    print("\n═══ Enrolment Dashboard ═══")
    rows = data.list_enrolments()
    counts = _status_counts(rows)
    by_year: dict[str, int] = {}
    by_yg: dict[int, int] = {}
    for e in rows:
        by_year[e.academic_year] = by_year.get(e.academic_year, 0) + 1
        by_yg[e.year_group] = by_yg.get(e.year_group, 0) + 1
    print(f"\n  Total enrolments: {len(rows)}")
    print("\n  By status:")
    _render_status_bar_chart(counts)  # feature #25
    print("\n  By year group:  " +
          "   ".join(f"Year {yg}: {n}" for yg, n in sorted(by_yg.items())))
    print("  By academic year:  " +
          "   ".join(f"{y}: {n}" for y, n in sorted(by_year.items(), reverse=True)))
    _pause()


def cohort_report(academic_year: str | None = None) -> None:
    """Feature #22 — headcount breakdown for a single academic year."""
    print("\n═══ Cohort Report ═══")
    if academic_year is None:
        try:
            academic_year = _prompt_academic_year(_default_academic_year())
        except _UserAbort:
            print("\n  Cancelled.")
            return
    rows = data.list_enrolments(academic_year=academic_year)
    by_yg: dict[int, dict[str, int]] = {}
    for e in rows:
        by_yg.setdefault(e.year_group, {s: 0 for s in STATUSES})[e.status] += 1
    print(f"\n  {academic_year} — {len(rows)} enrolment(s)\n")
    header = f"  {'Year':<8}" + "".join(f"{s:<11}" for s in STATUSES) + "Total"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for yg in sorted(by_yg):
        c = by_yg[yg]
        print(f"  Year {yg:<3}" + "".join(f"{c.get(s, 0):<11}" for s in STATUSES)
              + str(sum(c.values())))
    total = _status_counts(rows)
    print(f"  {'All':<8}" + "".join(f"{total.get(s, 0):<11}" for s in STATUSES)
          + str(len(rows)))
    _pause()


def retention_report() -> None:
    """Feature #23 — Year 12 → 13 progression rate per academic year."""
    print("\n═══ Retention (Year 12 → 13) ═══")
    rows = data.list_enrolments()
    by_student: dict[str, set[tuple[str, int]]] = {}
    y12_years: set[str] = set()
    for e in rows:
        by_student.setdefault(e.student_id, set()).add((e.academic_year, e.year_group))
        if e.year_group == 12:
            y12_years.add(e.academic_year)
    print(f"\n  {'Y12 year':<12}{'Y12':<8}{'→ Y13':<8}{'Rate':<8}")
    print("  " + "-" * 34)
    for y12_year in sorted(y12_years, reverse=True):
        nxt = _next_academic_year(y12_year)
        cohort = [sid for sid, pairs in by_student.items() if (y12_year, 12) in pairs]
        prog = [sid for sid in cohort if (nxt, 13) in by_student.get(sid, set())]
        rate = (100 * len(prog) / len(cohort)) if cohort else 0
        print(f"  {y12_year:<12}{len(cohort):<8}{len(prog):<8}{rate:.0f}%")
    _pause()


def tutor_group_roster(tutor_group: str | None = None) -> None:
    """Feature #24 — class list for one tutor group (offers PDF export)."""
    print("\n═══ Tutor Group Roster ═══")
    try:
        tg = tutor_group or _input("Tutor group", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    names = _student_names()
    rows = sorted(
        (e for e in data.list_enrolments()
         if (e.tutor_group or "").lower() == tg.lower()),
        key=lambda r: names.get(r.student_id, ""))
    print(f"\n  {tg} — {len(rows)} student(s)\n")
    for i, e in enumerate(rows, 1):
        print(f"    {i:>2}. {e.student_id:<10} {names.get(e.student_id, '—'):<26} "
              f"{e.academic_year}  {e.status}")
    if rows and _input("\n  Export PDF? Type 'yes' to confirm",
                      default="no").lower() == "yes":
        export_tutor_group_pdf(tg)
    else:
        _pause()


def withdrawal_analysis() -> None:
    """Feature #26 — all withdrawn enrolments with their captured reasons."""
    print("\n═══ Withdrawal Analysis ═══")
    names = _student_names()
    rows = data.list_enrolments(status="Withdrawn")
    print(f"\n  {len(rows)} withdrawn enrolment(s):\n")
    for e in rows:
        reason = (e.notes or "—").replace("\n", " ⏎ ")
        print(f"    {e.student_id:<10} {names.get(e.student_id, '—')[:20]:<20} "
              f"{e.academic_year}  {reason[:50]}")
    _pause()


def year_on_year_comparison() -> None:
    """Feature #27 — headcounts side by side across academic years."""
    print("\n═══ Year-on-Year Comparison ═══")
    per_year: dict[str, dict[str, int]] = {}
    for e in data.list_enrolments():
        per_year.setdefault(e.academic_year, {s: 0 for s in STATUSES})[e.status] += 1
    header = f"  {'Year':<10}" + "".join(f"{s:<11}" for s in STATUSES) + "Total"
    print("\n" + header)
    print("  " + "-" * (len(header) - 2))
    for year in sorted(per_year, reverse=True):
        c = per_year[year]
        print(f"  {year:<10}" + "".join(f"{c.get(s, 0):<11}" for s in STATUSES)
              + str(sum(c.values())))
    _pause()


def capacity_utilisation() -> None:
    """Feature #28 — active headcount vs a configured cohort capacity."""
    print("\n═══ Capacity Utilisation ═══")
    try:
        cap_raw = _input("Cohort capacity (number)", allow_empty=False)
        capacity = int(cap_raw)
    except ValueError:
        print("  ✗ Capacity must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    stats = _compute_capacity_utilisation(data.list_enrolments(), capacity)
    print(f"\n  Active (Enrolled + Pending): {stats['active']}")
    print(f"  Capacity                   : {stats['capacity']}")
    print(f"  Free places                : {stats['free']}")
    print(f"  Utilisation                : {stats['utilisation_pct']}%")
    if stats["over_capacity"]:
        print("  ⚠  Over capacity!")
    _pause()


# ════════════════════════════════════════════════════════════════════
# Import / export / print (features 29–35)
# ════════════════════════════════════════════════════════════════════

_CSV_HEADERS = ("enrolment_id", "student_id", "name", "academic_year",
                "year_group", "tutor_group", "start_date", "status", "notes")


def export_directory_csv() -> None:
    """Feature #29 — export all enrolments to a CSV file."""
    import csv
    print("\n═══ Export Enrolments (CSV) ═══")
    try:
        path = _input("Output path", default="enrolments.csv", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_enrolments()
    names = _student_names()
    try:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(_CSV_HEADERS)
            for e in rows:
                w.writerow([
                    e.enrolment_id, e.student_id, names.get(e.student_id, ""),
                    e.academic_year, e.year_group, e.tutor_group or "",
                    e.start_date or "", e.status, (e.notes or "").replace("\n", " ")])
    except Exception as exc:
        logger.exception("CLI CSV export failed")
        print(f"  ✗ {exc}")
        _pause()
        return
    print(f"  ✓ Wrote {len(rows)} row(s) to {path}")
    _pause()


def export_progression_list() -> None:
    """Feature #35 — CSV of who is progressing vs leaving this year."""
    import csv
    print("\n═══ Export Progression List (CSV) ═══")
    year = _default_academic_year()
    try:
        path = _input("Output path",
                      default=f"progression_{year.replace('/', '-')}.csv",
                      allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_enrolments(academic_year=year, status="Enrolled")
    names = _student_names()
    try:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(("student_id", "name", "year_group", "outcome"))
            for e in rows:
                outcome = ("Progressing to Y13" if e.year_group == 12 else
                           "Leaving (Y13)" if e.year_group == 13 else "—")
                w.writerow((e.student_id, names.get(e.student_id, ""),
                            e.year_group, outcome))
    except Exception as exc:
        logger.exception("CLI progression export failed")
        print(f"  ✗ {exc}")
        _pause()
        return
    print(f"  ✓ Wrote {len(rows)} row(s) to {path}")
    _pause()


def export_enrolment_pdf(enrolment_id: int | None = None) -> None:
    """Feature #30 — printable one-enrolment PDF summary."""
    print("\n═══ Export Enrolment PDF ═══")
    e = _resolve_enrolment(enrolment_id)
    if e is None:
        return
    try:
        path = _input("Output path",
                      default=f"enrolment_{e.enrolment_id}.pdf", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(e.student_id)
    lines = [
        f"Enrolment #{e.enrolment_id}", "",
        f"Student        : {e.student_id} — {student.full_name if student else '(deleted)'}",
        f"Academic year  : {e.academic_year}",
        f"Year group     : Year {e.year_group}",
        f"Tutor group    : {e.tutor_group or '-'}",
        f"Start date     : {e.start_date or '-'}",
        f"Status         : {e.status}",
        f"Created        : {e.created_at}",
        "", "Notes:", *(e.notes or "-").splitlines(),
    ]
    try:
        _write_simple_pdf(path, "Sixth Form Enrolment", lines)
    except Exception as exc:
        logger.exception("CLI PDF export failed")
        print(f"  ✗ {exc}")
        _pause()
        return
    print(f"  ✓ Saved PDF to {path}")
    _pause()


def export_tutor_group_pdf(tutor_group: str | None = None) -> None:
    """Feature #33 — printable tutor-group roster PDF."""
    print("\n═══ Export Roster PDF ═══")
    try:
        tg = tutor_group or _input("Tutor group", allow_empty=False)
        path = _input("Output path", default=f"roster_{tutor_group or 'group'}.pdf",
                      allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    names = _student_names()
    rows = sorted(
        (e for e in data.list_enrolments()
         if (e.tutor_group or "").lower() == tg.lower()),
        key=lambda r: names.get(r.student_id, ""))
    lines = [f"Tutor group: {tg}    ({len(rows)} students)", ""]
    lines += [f"{i + 1:>2}. {e.student_id:<10} {names.get(e.student_id, '-'):<28} "
              f"{e.academic_year}  {e.status}" for i, e in enumerate(rows)]
    try:
        _write_simple_pdf(path, "Tutor Group Roster", lines)
    except Exception as exc:
        logger.exception("CLI roster PDF export failed")
        print(f"  ✗ {exc}")
        _pause()
        return
    print(f"  ✓ Saved roster to {path}")
    _pause()


def copy_enrolment_details(enrolment_id: int | None = None) -> None:
    """Feature #34 — print a formatted, copy-ready enrolment summary.

    (A terminal has no reliable clipboard, so the CLI analogue is to render
    the block for the user to copy.)"""
    print("\n═══ Copy Enrolment Details ═══")
    e = _resolve_enrolment(enrolment_id)
    if e is None:
        return
    student = student_data.get_student(e.student_id)
    print("\n  ----- copy below -----")
    print(f"  Enrolment #{e.enrolment_id}")
    print(f"  Student: {e.student_id} — {student.full_name if student else '(deleted)'}")
    print(f"  Year: {e.academic_year} · Year {e.year_group}")
    print(f"  Tutor: {e.tutor_group or '—'} · Start: {e.start_date or '—'}")
    print(f"  Status: {e.status}")
    print("  ----------------------")
    _pause()


def _preview_import_diff(records: list[dict[str, str]]) -> list[dict[str, str]]:
    """Feature #32 — classify parsed CSV rows as new / duplicate / invalid,
    print the verdicts, and return the importable (new) subset."""
    existing = {(e.student_id, e.academic_year) for e in data.list_enrolments()}
    valid_students = {s.student_id for s in student_data.list_students()}
    importable: list[dict[str, str]] = []
    print(f"\n  {'Student':<12}{'Year':<10}{'YG':<5}Verdict")
    print("  " + "-" * 56)
    for rec in records:
        sid = (rec.get("student_id") or "").strip()
        year = (rec.get("academic_year") or "").strip()
        yg = (rec.get("year_group") or "").strip()
        if sid not in valid_students:
            verdict = "unknown student — skipped"
        elif not enrolments._ACADEMIC_YEAR_RE.match(year):
            verdict = "bad academic year — skipped"
        elif (sid, year) in existing:
            verdict = "duplicate — skipped"
        elif (rec.get("status") or DEFAULT_STATUS).strip() not in enrolments.CREATE_STATUSES:
            verdict = ("status can't be imported — skipped (import as "
                       "Enrolled, then use Withdraw for the ILR reason)")
        else:
            verdict = "new — will import"
            importable.append(rec)
        print(f"  {sid:<12}{year:<10}{yg:<5}{verdict}")
    return importable


def import_enrolments_csv() -> None:
    """Feature #31 — bulk-import enrolments from CSV with a validated preview."""
    import csv
    print("\n═══ Import Enrolments (CSV) ═══")
    try:
        path = _input("Input CSV path", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            records = list(csv.DictReader(fh))
    except Exception as exc:
        logger.exception("CLI CSV import read failed")
        print(f"  ✗ Could not read file: {exc}")
        _pause()
        return
    print(f"\n  {len(records)} row(s) read.")
    importable = _preview_import_diff(records)
    if not importable:
        print("\n  Nothing importable.")
        _pause()
        return
    if _input(f"\n  Import {len(importable)} new row(s)? Type 'yes' to confirm",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    ok: list[str] = []
    fail: list[str] = []
    for rec in importable:
        try:
            data.create_enrolment({
                "student_id": rec.get("student_id", "").strip(),
                "academic_year": rec.get("academic_year", "").strip(),
                "year_group": rec.get("year_group", "").strip(),
                "tutor_group": (rec.get("tutor_group") or "").strip() or None,
                "start_date": (rec.get("start_date") or "").strip() or None,
                "status": (rec.get("status") or DEFAULT_STATUS).strip(),
                "notes": (rec.get("notes") or "").strip() or None,
            })
            ok.append(rec.get("student_id", "?"))
        except Exception as exc:
            fail.append(f"{rec.get('student_id', '?')}: {exc}")
    _report_bulk("CSV import", ok, fail)


# ════════════════════════════════════════════════════════════════════
# Academic-year list manager (feature 50)
# ════════════════════════════════════════════════════════════════════

def academic_year_manager() -> None:
    """Feature #50 — the academic years enrolments can use. The years come
    from the Academic Year & Calendar register (the source of truth);
    names in the old ``enrolment_academic_years.json`` list that are not
    in the register are shown as "listed only" (the file is no longer
    written). Adding a year creates it in the register."""
    from education_system.systems.sixth_form.domain.academics.academic_year import (
        academic_year as ay,
    )
    while True:
        years = {y.name: y for y in ay.list_years()}
        legacy = [y for y in _load_academic_years() if y not in years]
        counts: dict[str, int] = {}
        for e in data.list_enrolments():
            counts[e.academic_year] = counts.get(e.academic_year, 0) + 1
        print("\n═══ Academic Years ═══")
        for y in years.values():
            print(f"  {y.name:<10} {y.start_date} → {y.end_date}  [{y.status}]"
                  f"{'  CURRENT' if y.is_current else ''}  "
                  f"{counts.get(y.name, 0)} enrolment(s)")
        for name in sorted(legacy, reverse=True):
            print(f"  {name:<10} (listed only — not in the academic-year "
                  f"register)  {counts.get(name, 0)} enrolment(s)")
        if not years and not legacy:
            print("  (none)")
        print("\n  A) Add to the register   (Enter to go back)")
        print("  Change or remove years under Academic Year & Calendar.")
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice != "a":
            print("  ✗ Unrecognised action.")
            continue
        try:
            val = _input("New academic year (YYYY/YY)",
                         default=(sorted(legacy)[-1] if legacy else ""),
                         allow_empty=False)
            if not enrolments._ACADEMIC_YEAR_RE.match(val):
                print("  ✗ Must look like '2025/26'.")
                continue
            start_y = int(val[:4])
            start = _input("Start date", default=f"{start_y}-09-01")
            end = _input("End date", default=f"{start_y + 1}-07-31")
        except _UserAbort:
            continue
        try:
            y = ay.create_year({"name": val, "start_date": start,
                                "end_date": end})
            print(f"  ✓ Added {y.name} ({y.start_date} → {y.end_date}) "
                  f"[{y.status}]")
        except Exception as exc:  # noqa: BLE001 — register refusals shown
            print(f"  ✗ {exc}")
