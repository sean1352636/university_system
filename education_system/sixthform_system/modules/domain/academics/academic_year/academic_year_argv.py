"""Non-interactive argparse front-end for the Academic Year module.

Covers suggestion items 32-38:
  --json output mode, --dry-run, --no-color, --no-pause,
  doctor flow, fixtures preset loader, plus a static bash completion
  file under share/.

Examples:

    python -m education_system.sixthform_system.modules.domain.academics.academic_year.academic_year_argv \\
        list-years --json
    ... set-current --id 3 --dry-run
    ... doctor
    ... fixtures load demo
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import sys
from typing import Any
from education_system.sixthform_system.modules.domain.academics.academic_year import (
    academic_year as data,
    academic_year_analytics as analytics,
    academic_year_views as views,
    academic_year_cli as interactive,
)
from education_system.sixthform_system.modules.domain.academics.academic_year.academic_year import (
    BREAK_TYPES, DEFAULT_BREAK_TYPE, ValidationError, YEAR_STATUSES,
)

logger = logging.getLogger(__name__)


# ── small helpers ─────────────────────────────────────────────────

def _emit(obj: Any, *, json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(obj, default=str, indent=2))
    elif isinstance(obj, list):
        for row in obj:
            print(row)
    else:
        print(obj)


def _year_to_row(y) -> dict:
    return {
        "year_id": y.year_id, "name": y.name,
        "start_date": y.start_date, "end_date": y.end_date,
        "status": y.status, "is_current": y.is_current,
        "campus_id": y.campus_id,
        "approved_at": y.approved_at, "approved_by": y.approved_by,
    }


def _term_to_row(t) -> dict:
    return {
        "term_id": t.term_id, "year_id": t.year_id,
        "name": t.name, "kind": t.kind,
        "start_date": t.start_date, "end_date": t.end_date,
    }


def _break_to_row(b) -> dict:
    return {
        "break_id": b.break_id, "year_id": b.year_id,
        "name": b.name, "type": b.type, "am_pm": b.am_pm,
        "start_date": b.start_date, "end_date": b.end_date,
    }


# ── command implementations ───────────────────────────────────────

def cmd_list_years(args: argparse.Namespace) -> int:
    rows = data.list_years(status=args.status, campus_id=args.campus)
    if args.json:
        _emit([_year_to_row(r) for r in rows], json_mode=True)
    else:
        for y in rows:
            print(f"#{y.year_id:>3}  {y.name:<12}  "
                   f"{y.start_date}..{y.end_date}  "
                   f"{y.status:<10}  "
                   f"{'current' if y.is_current else '       '}")
    return 0


def cmd_show_current(args: argparse.Namespace) -> int:
    y = data.current_year(campus_id=args.campus)
    if y is None:
        _emit({"current": None}, json_mode=args.json)
        return 0
    if args.json:
        s = data.year_summary(y.year_id)
        _emit({
            "year": _year_to_row(y),
            "teaching_days": s.teaching_days,
            "non_teaching_days": s.non_teaching_days,
            "weekend_days": s.weekend_days,
            "terms": len(s.terms),
            "breaks": len(s.breaks),
        }, json_mode=True)
    else:
        print(f"Current: #{y.year_id} {y.name} "
               f"({y.start_date}..{y.end_date}, {y.status})")
    return 0


def _resolve_year_id(args) -> int:
    if args.id is not None:
        return int(args.id)
    if args.name:
        y = data.get_year_by_name(args.name)
        if y is None:
            raise SystemExit(f"No year named {args.name!r}")
        return y.year_id
    raise SystemExit("--id or --name required")


def cmd_set_current(args: argparse.Namespace) -> int:
    yid = _resolve_year_id(args)
    y = data.get_year(yid)
    if y is None:
        raise SystemExit(f"No year #{yid}")
    if args.dry_run:
        print(f"DRY-RUN: would set #{yid} {y.name!r} as current")
        return 0
    data.set_current(yid)
    _emit({"set_current": yid}, json_mode=args.json)
    return 0


def cmd_create_year(args: argparse.Namespace) -> int:
    payload = {
        "name": args.name, "start_date": args.start,
        "end_date": args.end,
        "status": args.status or "Planning",
        "is_current": args.current,
        "notes": args.notes,
        "campus_id": args.campus,
    }
    if args.dry_run:
        print(f"DRY-RUN: would create year {payload}")
        return 0
    try:
        y = data.create_year(payload)
    except ValidationError as e:
        raise SystemExit(f"✗ {e}")
    _emit(_year_to_row(y), json_mode=args.json)
    return 0


def cmd_delete_year(args: argparse.Namespace) -> int:
    yid = _resolve_year_id(args)
    y = data.get_year(yid, include_deleted=True)
    if y is None:
        raise SystemExit(f"No year #{yid}")
    mode = "hard-delete" if args.hard else "soft-delete"
    if args.dry_run:
        print(f"DRY-RUN: would {mode} year #{yid} {y.name!r}")
        return 0
    ok = data.delete_year(yid, hard=args.hard)
    _emit({"deleted": yid, "hard": args.hard, "ok": ok},
            json_mode=args.json)
    return 0 if ok else 1


def cmd_duplicate_year(args: argparse.Namespace) -> int:
    yid = _resolve_year_id(args)
    src = data.get_year(yid)
    if src is None:
        raise SystemExit(f"No year #{yid}")
    new_name = views._bump_year_name(src.name)
    new_start = views._shift_iso(src.start_date, 365)
    new_end = views._shift_iso(src.end_date, 365)
    plan = {"new_name": new_name, "new_start": new_start,
              "new_end": new_end}
    if args.dry_run:
        print(f"DRY-RUN: would duplicate #{yid} → {plan}")
        return 0
    new_year = data.create_year({
        "name": new_name, "start_date": new_start, "end_date": new_end,
        "status": "Planning", "is_current": False, "notes": src.notes,
    })
    for t in data.list_terms(year_id=src.year_id):
        try:
            data.create_term({
                "year_id": new_year.year_id, "name": t.name,
                "kind": t.kind,
                "start_date": views._shift_iso(t.start_date, 365),
                "end_date":   views._shift_iso(t.end_date, 365),
                "notes": t.notes,
            })
        except ValidationError:
            pass
    for b in data.list_breaks(year_id=src.year_id):
        try:
            data.create_break({
                "year_id": new_year.year_id, "name": b.name,
                "type": b.type, "am_pm": b.am_pm,
                "start_date": views._shift_iso(b.start_date, 365),
                "end_date":   views._shift_iso(b.end_date, 365),
                "notes": b.notes,
            })
        except ValidationError:
            pass
    _emit(_year_to_row(new_year), json_mode=args.json)
    return 0


def cmd_import_bank_holidays(args: argparse.Namespace) -> int:
    yid = _resolve_year_id(args)
    y = data.get_year(yid)
    if y is None:
        raise SystemExit(f"No year #{yid}")
    ys = _dt.date.fromisoformat(y.start_date)
    ye = _dt.date.fromisoformat(y.end_date)
    candidates = views._uk_bank_holidays(ys, ye)
    existing = {(b.name, b.start_date)
                 for b in data.list_breaks(year_id=yid)}
    new = [(n, d) for n, d in candidates if (n, d) not in existing]
    if args.dry_run:
        print(f"DRY-RUN: would import {len(new)} bank holiday(s)")
        for n, d in new:
            print(f"  • {n}  {d}")
        return 0
    added = 0
    for n, d in new:
        try:
            data.create_break({
                "year_id": yid, "name": n, "type": "Bank Holiday",
                "start_date": d, "end_date": d, "notes": None,
            })
            added += 1
        except ValidationError as e:
            print(f"  ⚠ {n}: {e}", file=sys.stderr)
    _emit({"added": added}, json_mode=args.json)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Walk every year, classify terms, check breaks-outside-terms."""
    findings: list[dict[str, Any]] = []
    for y in data.list_years():
        terms = data.list_terms(year_id=y.year_id)
        statuses = views._classify_terms(y, terms)
        for tid, st in statuses.items():
            if st != "ok":
                findings.append({"year": y.name, "kind": "term",
                                    "id": tid, "issue": st})
        ranges = [(t.start_date, t.end_date) for t in terms]
        for b in data.list_breaks(year_id=y.year_id):
            if not any(not (b.end_date < s or b.start_date > e)
                          for s, e in ranges):
                findings.append({"year": y.name, "kind": "break",
                                    "id": b.break_id,
                                    "issue": "outside-term"})
        var = analytics.term_length_variance(y.year_id)
        for v in var:
            if v["flagged"]:
                findings.append({
                    "year": y.name, "kind": "term-variance",
                    "id": v["term_id"],
                    "issue": f"{v['name']} differs by "
                              f"{v['diff_days']:+.0f}d"})
    if args.json:
        _emit({"findings": findings, "count": len(findings)},
                json_mode=True)
    else:
        if not findings:
            print("✓ No issues found.")
        else:
            print(f"⚠ {len(findings)} finding(s):")
            for f in findings:
                print(f"  [{f['year']}] {f['kind']} #{f['id']}: "
                       f"{f['issue']}")
    return 0 if not findings else 2


_FIXTURES: dict[str, dict[str, Any]] = {
    "demo": {
        "year": {"name": "2025/26-demo",
                  "start_date": "2025-09-01",
                  "end_date":   "2026-07-20",
                  "status": "Planning"},
        "terms": [
            {"name": "Autumn", "start_date": "2025-09-01",
              "end_date":   "2025-12-19"},
            {"name": "Spring", "start_date": "2026-01-05",
              "end_date":   "2026-03-27"},
            {"name": "Summer", "start_date": "2026-04-13",
              "end_date":   "2026-07-20"},
        ],
        "breaks": [
            {"name": "Christmas", "type": "Holiday",
              "start_date": "2025-12-22",
              "end_date":   "2026-01-02"},
            {"name": "Easter", "type": "Holiday",
              "start_date": "2026-03-30",
              "end_date":   "2026-04-10"},
        ],
    },
    "minimal": {
        "year": {"name": "2025/26-min",
                  "start_date": "2025-09-01",
                  "end_date":   "2026-07-20",
                  "status": "Planning"},
        "terms": [], "breaks": [],
    },
}


def cmd_fixtures(args: argparse.Namespace) -> int:
    if args.fix_action != "load":
        raise SystemExit("only 'load' is supported")
    name = args.preset
    if name not in _FIXTURES:
        raise SystemExit(
            f"unknown preset {name!r}. "
            f"choices: {sorted(_FIXTURES)}")
    spec = _FIXTURES[name]
    yp = spec["year"]
    if data.get_year_by_name(yp["name"]):
        raise SystemExit(f"preset already loaded: {yp['name']!r}")
    if args.dry_run:
        print(f"DRY-RUN: would load preset {name!r}: "
               f"1 year, {len(spec['terms'])} term(s), "
               f"{len(spec['breaks'])} break(s)")
        return 0
    y = data.create_year(yp)
    for t in spec["terms"]:
        data.create_term({**t, "year_id": y.year_id})
    for b in spec["breaks"]:
        data.create_break({**b, "year_id": y.year_id})
    _emit({"loaded": name, "year_id": y.year_id},
            json_mode=args.json)
    return 0


def cmd_export_year(args: argparse.Namespace) -> int:
    yid = _resolve_year_id(args)
    y = data.get_year(yid)
    if y is None:
        raise SystemExit(f"No year #{yid}")
    payload = {
        "schema": "sixthform.academic_year/v1",
        "year": {"name": y.name, "start_date": y.start_date,
                   "end_date": y.end_date, "status": y.status,
                   "is_current": y.is_current, "notes": y.notes,
                   "campus_id": y.campus_id},
        "terms": [_term_to_row(t) for t in data.list_terms(year_id=yid)],
        "breaks": [_break_to_row(b) for b in data.list_breaks(year_id=yid)],
    }
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)
    _emit({"output": args.output}, json_mode=args.json)
    return 0


def cmd_import_year(args: argparse.Namespace) -> int:
    with open(args.input, encoding="utf-8") as fh:
        payload = json.load(fh)
    if args.dry_run:
        n = (1, len(payload.get("terms", [])),
              len(payload.get("breaks", [])))
        print(f"DRY-RUN: would create 1 year, "
               f"{n[1]} term(s), {n[2]} break(s)")
        return 0
    yp = payload["year"]
    name = yp["name"]
    if data.get_year_by_name(name):
        i = 2
        while data.get_year_by_name(f"{name} ({i})"):
            i += 1
        name = f"{name} ({i})"
    y = data.create_year({**yp, "name": name, "is_current": False,
                              "status": "Planning"})
    for t in payload.get("terms", []):
        try:
            data.create_term({**t, "year_id": y.year_id})
        except ValidationError as e:
            print(f"  ⚠ term {t.get('name')!r}: {e}", file=sys.stderr)
    for b in payload.get("breaks", []):
        try:
            data.create_break({**b, "year_id": y.year_id})
        except ValidationError as e:
            print(f"  ⚠ break {b.get('name')!r}: {e}", file=sys.stderr)
    _emit(_year_to_row(y), json_mode=args.json)
    return 0


def cmd_lookup(args: argparse.Namespace) -> int:
    date = args.date or _dt.date.today().isoformat()
    if args.id is not None:
        yid = int(args.id)
    else:
        cur = data.current_year()
        if cur is None:
            raise SystemExit("No current year and --id not given")
        yid = cur.year_id
    try:
        term = data.find_term_on(yid, date)
        brk = data.is_break(yid, date)
    except ValidationError as e:
        raise SystemExit(str(e))
    out = {
        "date": date,
        "year_id": yid,
        "term": term.name if term else None,
        "break": ({"name": brk.name, "type": brk.type}
                    if brk else None),
    }
    _emit(out, json_mode=args.json)
    return 0


def cmd_completion(args: argparse.Namespace) -> int:
    """Print a bash completion script to stdout."""
    print(_BASH_COMPLETION)
    return 0


_BASH_COMPLETION = r"""
# Bash completion for the Academic Year CLI. Source this from your
# shell rc, or save under /etc/bash_completion.d/.
_academic_year_complete() {
    local cur prev cmds
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    cmds="list-years show-current set-current create-year delete-year \
          duplicate-year import-bank-holidays doctor fixtures \
          export-year import-year lookup completion"
    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "${cmds}" -- ${cur}) )
        return 0
    fi
    case "${prev}" in
        --status) COMPREPLY=( $(compgen -W "Planning Active Archived" -- ${cur}) ) ;;
        --json|--dry-run|--current|--hard) COMPREPLY=() ;;
        *) COMPREPLY=( $(compgen -W "--id --name --json --dry-run --status \
            --campus --start --end --current --notes --output --input \
            --hard --date" -- ${cur}) ) ;;
    esac
}
complete -F _academic_year_complete academic-year
"""


# ── argparse wiring ───────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="academic-year",
        description="Sixth-Form Academic Year non-interactive CLI")
    p.add_argument("--json", action="store_true",
                     help="Emit JSON instead of human-readable output")
    p.add_argument("--dry-run", action="store_true",
                     help="Describe what would happen, but don't write")
    p.add_argument("--no-color", action="store_true",
                     help="Disable ANSI colour codes")
    p.add_argument("--no-pause", action="store_true",
                     help="Don't prompt 'press enter' in interactive flows")

    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list-years")
    sp.add_argument("--status", choices=YEAR_STATUSES)
    sp.add_argument("--campus")
    sp.set_defaults(fn=cmd_list_years)

    sp = sub.add_parser("show-current")
    sp.add_argument("--campus")
    sp.set_defaults(fn=cmd_show_current)

    sp = sub.add_parser("set-current")
    sp.add_argument("--id", type=int)
    sp.add_argument("--name")
    sp.set_defaults(fn=cmd_set_current)

    sp = sub.add_parser("create-year")
    sp.add_argument("--name", required=True)
    sp.add_argument("--start", required=True)
    sp.add_argument("--end", required=True)
    sp.add_argument("--status", choices=YEAR_STATUSES,
                      default="Planning")
    sp.add_argument("--current", action="store_true")
    sp.add_argument("--campus")
    sp.add_argument("--notes")
    sp.set_defaults(fn=cmd_create_year)

    sp = sub.add_parser("delete-year")
    sp.add_argument("--id", type=int)
    sp.add_argument("--name")
    sp.add_argument("--hard", action="store_true",
                      help="Physically delete instead of soft-delete")
    sp.set_defaults(fn=cmd_delete_year)

    sp = sub.add_parser("duplicate-year")
    sp.add_argument("--id", type=int)
    sp.add_argument("--name")
    sp.set_defaults(fn=cmd_duplicate_year)

    sp = sub.add_parser("import-bank-holidays")
    sp.add_argument("--id", type=int)
    sp.add_argument("--name")
    sp.set_defaults(fn=cmd_import_bank_holidays)

    sp = sub.add_parser("doctor")
    sp.set_defaults(fn=cmd_doctor)

    sp = sub.add_parser("fixtures")
    sp.add_argument("fix_action", choices=["load"])
    sp.add_argument("preset")
    sp.set_defaults(fn=cmd_fixtures)

    sp = sub.add_parser("export-year")
    sp.add_argument("--id", type=int)
    sp.add_argument("--name")
    sp.add_argument("--output", required=True)
    sp.set_defaults(fn=cmd_export_year)

    sp = sub.add_parser("import-year")
    sp.add_argument("--input", required=True)
    sp.set_defaults(fn=cmd_import_year)

    sp = sub.add_parser("lookup")
    sp.add_argument("--id", type=int)
    sp.add_argument("--date")
    sp.set_defaults(fn=cmd_lookup)

    sp = sub.add_parser("approve-year",
                          help="Sign-off the year")
    sp.add_argument("--id", type=int)
    sp.add_argument("--name")
    sp.add_argument("--approver", required=True)
    sp.set_defaults(fn=cmd_approve_year)

    sp = sub.add_parser("unapprove-year",
                          help="Remove an approval")
    sp.add_argument("--id", type=int)
    sp.add_argument("--name")
    sp.set_defaults(fn=cmd_unapprove_year)

    sp = sub.add_parser("set-campus",
                          help="Tag a year with a campus_id")
    sp.add_argument("--id", type=int)
    sp.add_argument("--name")
    sp.add_argument("--campus", required=True)
    sp.set_defaults(fn=cmd_set_campus)

    sp = sub.add_parser("completion",
                          help="Print bash completion script")
    sp.set_defaults(fn=cmd_completion)

    return p


def cmd_approve_year(args: argparse.Namespace) -> int:
    yid = _resolve_year_id(args)
    if args.dry_run:
        print(f"DRY-RUN: would approve year #{yid} by {args.approver!r}")
        return 0
    y = data.approve_year(yid, approver=args.approver)
    _emit({"approved": yid, "by": y.approved_by,
             "at": y.approved_at}, json_mode=args.json)
    return 0


def cmd_unapprove_year(args: argparse.Namespace) -> int:
    yid = _resolve_year_id(args)
    if args.dry_run:
        print(f"DRY-RUN: would unapprove year #{yid}")
        return 0
    y = data.unapprove_year(yid)
    _emit({"unapproved": yid, "name": y.name}, json_mode=args.json)
    return 0


def cmd_set_campus(args: argparse.Namespace) -> int:
    yid = _resolve_year_id(args)
    if args.dry_run:
        print(f"DRY-RUN: would set campus_id={args.campus!r} "
               f"on year #{yid}")
        return 0
    y = data.update_year(yid, {"campus_id": args.campus})
    _emit({"year_id": yid, "campus_id": y.campus_id},
            json_mode=args.json)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    interactive.NO_PAUSE = bool(args.no_pause)
    interactive.NO_COLOR = bool(args.no_color)
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
