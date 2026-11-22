"""Admissions CLI: browsing and searching — saved views, columns, age filter, duplicates, activity."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
    SOURCES,
    STATUSES,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    VIEWS_FILE,
    _UserAbort,
    _age,
    _days_in_stage,
    _input,
    _load_json,
    _pause,
    _pick_from,
    _print_applicants,
    _store_json,
)



def duplicate_report_flow() -> None:
    """Item 7 — list applicants sharing an email or phone."""
    print("\n═══ Duplicate Report ═══")
    from collections import defaultdict
    by_key: dict[tuple[str, str], list[Applicant]] = defaultdict(list)
    for a in data.list_applicants():
        if a.email and a.email.strip():
            by_key[("email", a.email.strip().lower())].append(a)
        if a.phone and a.phone.strip():
            by_key[("phone", a.phone.strip())].append(a)
    groups = [(k, v) for k, v in by_key.items() if len(v) > 1]
    if not groups:
        print("  No shared email/phone found.")
        _pause()
        return
    for (kind, val), members in groups:
        print(f"\n  Shared {kind}: {val}")
        for a in members:
            print(f"      {a.applicant_id}  {a.full_name[:24]:<24}  "
                  f"[{a.status}]")
    _pause()


def saved_views_flow() -> None:
    """Item 8 — save/apply/delete named filter presets."""
    while True:
        views = _load_json(VIEWS_FILE, {})
        print("\n═══ Saved Views ═══")
        names = sorted(views)
        for i, name in enumerate(names, 1):
            v = views[name]
            print(f"    {i:>2}) {name}  "
                  f"(status={v.get('status') or 'any'}, "
                  f"source={v.get('source') or 'any'}, "
                  f"sort={v.get('sort') or '—'})")
        if not names:
            print("    (no saved views)")
        print("\n    (a)pply <n>, (s)ave new, (d)elete <n>, Enter) back")
        raw = _input("  Action", default="")
        if not raw:
            return
        parts = raw.split()
        cmd = parts[0].lower()
        idx = int(parts[1]) - 1 if len(parts) > 1 and parts[1].isdigit() \
            else None
        if cmd == "s":
            try:
                name = _input("View name", allow_empty=False)
                status = _pick_from("Status", ["(any)"] + list(STATUSES))
                source = _pick_from("Source", ["(any)"] + list(SOURCES))
                sort = _pick_from("Sort by",
                                  ["(none)", "name", "age", "submitted",
                                   "days", "status"])
            except _UserAbort:
                continue
            views[name] = {
                "status": "" if status == "(any)" else status,
                "source": "" if source == "(any)" else source,
                "sort": "" if sort == "(none)" else sort}
            _store_json(VIEWS_FILE, views)
        elif cmd == "a" and idx is not None and 0 <= idx < len(names):
            v = views[names[idx]]
            rows = data.list_applicants(status=v.get("status") or None,
                                        source=v.get("source") or None)
            _print_applicants(rows, sort_by=v.get("sort") or "")
            _pause()
        elif cmd == "d" and idx is not None and 0 <= idx < len(names):
            views.pop(names[idx], None)
            _store_json(VIEWS_FILE, views)
        else:
            print("  ✗ Unrecognised action.")


def column_chooser_flow() -> None:
    """Item 9 — choose which columns to show, then list applicants."""
    print("\n═══ Choose Columns ═══")
    all_cols = [("id", "ID"), ("name", "Name"), ("age", "Age"),
                ("submitted", "Submitted"), ("days", "Days"),
                ("status", "Status"), ("offer", "Offer"),
                ("source", "Source"), ("subjects", "Subjects")]
    for i, (_, label) in enumerate(all_cols, 1):
        print(f"    {i:>2}) {label}")
    raw = _input("  Columns to show (comma-separated numbers, blank=all)",
                 default="")
    if raw.strip():
        picks = [all_cols[int(t) - 1][0] for t in raw.replace(" ", "").split(",")
                 if t.isdigit() and 1 <= int(t) <= len(all_cols)]
    else:
        picks = [c for c, _ in all_cols]
    if not picks:
        print("  ✗ No valid columns.")
        _pause()
        return
    rows = data.list_applicants()

    def cell(a: Applicant, col: str) -> str:
        age = _age(a.dob)
        days = _days_in_stage(a)
        return {
            "id": a.applicant_id, "name": a.full_name[:22],
            "age": str(age) if age is not None else "—",
            "submitted": a.submitted_at or "—",
            "days": str(days) if days is not None else "—",
            "status": a.status, "offer": a.offer_type or "—",
            "source": a.application_source,
            "subjects": ", ".join(a.subjects)[:28]}.get(col, "")

    header = {"id": "ID", "name": "Name", "age": "Age",
              "submitted": "Submitted", "days": "Days", "status": "Status",
              "offer": "Offer", "source": "Source", "subjects": "Subjects"}
    print()
    print("  " + "  ".join(f"{header[c]:<14}" for c in picks))
    print("  " + "-" * (16 * len(picks)))
    for a in rows:
        print("  " + "  ".join(f"{cell(a, c):<14}" for c in picks))
    print(f"\n  {len(rows)} shown.")
    _pause()


def quick_search_flow() -> None:
    """Item 10 — search applicants by id / name / email."""
    print("\n═══ Quick Search ═══")
    try:
        q = _input("Search (id / name / email)", allow_empty=False).lower()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = [a for a in data.list_applicants()
            if q in a.applicant_id.lower() or q in a.full_name.lower()
            or (a.email and q in a.email.lower())]
    _print_applicants(rows)
    _pause()


def age_filter_flow() -> None:
    """Item 15 — filter applicants by an age range."""
    print("\n═══ Filter by Age ═══")
    try:
        lo_s = _input("Min age (blank = none)")
        hi_s = _input("Max age (blank = none)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    lo = int(lo_s) if lo_s.isdigit() else None
    hi = int(hi_s) if hi_s.isdigit() else None
    rows = []
    for a in data.list_applicants():
        age = _age(a.dob)
        if age is None:
            continue
        if lo is not None and age < lo:
            continue
        if hi is not None and age > hi:
            continue
        rows.append(a)
    _print_applicants(rows, sort_by="age")
    _pause()


def activity_feed_flow(limit: int = 100) -> None:
    """Item 50 — global recent-events stream across all applicants."""
    print("\n═══ Activity Feed ═══")
    events = []
    for a in data.list_applicants():
        for e in data.list_events(a.applicant_id):
            events.append((e.at, a.applicant_id, e.kind, e.detail))
    events.sort(key=lambda t: t[0], reverse=True)
    if not events:
        print("  (no activity recorded)")
    for at, aid, kind, detail in events[:limit]:
        print(f"    {at}  {aid:<8} [{kind}]  {detail}")
    _pause()
