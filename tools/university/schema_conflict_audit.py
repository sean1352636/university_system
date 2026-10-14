#!/usr/bin/env python3
"""Find tables whose ``CREATE TABLE`` definitions disagree with each other.

The tree carries several thousand ``CREATE TABLE IF NOT EXISTS`` statements.
Most are harmless: the same module bootstrapping its own tables from two
entry points, byte-identical, idempotent. The dangerous ones are the tables
defined more than once **with different columns on the same database** —
there, whichever code path runs first on a fresh database wins, and every
query written against the other definition fails with ``no such column``.

Two refinements make the output usable rather than alarming:

1. **Partition by database, not by table name.** All five systems have a
   ``students`` table; they are different tables in different files and are
   not in conflict. Attribution is best-effort, in priority order: an
   explicit ``<name>.db`` literal, a ``paths.py`` constant, an import of a
   system's shared database module, then the owning package as a fallback.

2. **Rank by blast radius**, not by how badly the definitions disagree. A
   table with three conflicting definitions that nothing reads matters less
   than one with two definitions that four hundred modules query.

Usage::

    python tools/university/schema_conflict_audit.py            # ranked report
    python tools/university/schema_conflict_audit.py --table students
    python tools/university/schema_conflict_audit.py --json /tmp/audit.json
    python tools/university/schema_conflict_audit.py --check    # CI ratchet

``--check`` exits non-zero if the conflict count exceeds ``--max-conflicts``,
so the number can be ratcheted down rather than left to grow.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"

CREATE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"[\"'`\[]?([A-Za-z_][A-Za-z0-9_]*)[\"'`\]]?\s*\(",
    re.IGNORECASE,
)

CONSTRAINT_RE = re.compile(
    r"^\s*(PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CHECK|CONSTRAINT)\b",
    re.IGNORECASE,
)

# An identifier sitting where SQL expects a table name.
TABLE_POSITION_RE = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+[\"'`\[]?"
    r"([A-Za-z_][A-Za-z0-9_]*)[\"'`\]]?\b",
    re.IGNORECASE,
)

DB_LITERAL_RE = re.compile(r"[\"']([A-Za-z0-9_\-/]*?([A-Za-z0-9_\-]+)\.db)[\"']")
PATHS_CONST_RE = re.compile(
    r"\b((?:UNIVERSITY|SIXTH_FORM|SECONDARY|PRIMARY|NURSERY|PLATFORM)"
    r"_[A-Z0-9_]*DB[A-Z0-9_]*)\b"
)
SHARED_DB_IMPORT_RE = re.compile(
    r"education_system\.systems\.([a-z_]+)\.infrastructure\.database"
)
PLATFORM_DB_IMPORT_RE = re.compile(
    r"education_system\.platform\.(?:kernel\.database|identity\.auth)"
)

# The university's shared database module *is* student_records.db. Treating
# the two as separate targets would hide most of the conflicts we want.
SHARED_ALIASES = {"university": "student_records.db"}

# Databases named in the source that are not separate databases at runtime.
#
# ``student_grading_system.db`` is the notable one: the grade-tracking
# package's ``analytics_manager/constants.py`` reassigns ``sqlite3.connect``
# on the shared module object, redirecting any connection to that filename
# onto the university default database. The redirect is process-global once
# that module is imported, and the file exists nowhere on disk — so every
# definition "targeting" it actually lands on student_records.db, and
# partitioning them apart hides real conflicts.
DB_FILE_ALIASES = {"student_grading_system.db": "student_records.db"}

_PATHS_TO_FILE: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _load_paths_constants() -> None:
    """Map ``paths.py`` DB constants to their filenames, from the real module
    so this cannot drift from the source of truth."""
    try:
        sys.path.insert(0, str(SRC_ROOT))
        from education_system import paths as p  # noqa: PLC0415
    except Exception:
        return
    for name in dir(p):
        if not re.fullmatch(r"[A-Z0-9_]+", name) or "DB" not in name:
            continue
        value = getattr(p, name)
        if isinstance(value, (str, Path)) and str(value).endswith(".db"):
            _PATHS_TO_FILE[name] = Path(str(value)).name


def _balanced_body(text: str, open_idx: int) -> str | None:
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1:i]
    return None


def _split_top_level(body: str) -> list[str]:
    parts, depth, current = [], 0, []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def _normalise(defn: str) -> str:
    defn = re.sub(r"--[^\n]*", " ", defn)
    return re.sub(r"\s+", " ", defn).strip().rstrip(",").strip()


def _parse_columns(body: str) -> dict[str, str]:
    columns: dict[str, str] = {}
    for part in _split_top_level(body):
        clean = _normalise(part)
        if not clean or CONSTRAINT_RE.match(clean):
            continue
        name = clean.split()[0].strip("\"`[]'")
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            columns[name.lower()] = clean
    return columns


def _owner_of(path: Path) -> str:
    posix = path.as_posix()
    m = re.search(r"/education_system/systems/([a-z_]+)/", posix)
    if m:
        return f"systems/{m.group(1)}"
    if "/education_system/platform/" in posix:
        return "platform"
    if "/education_system/migrations/" in posix:
        return "migrations"
    return "other"


def _db_target(text: str, path: Path) -> str:
    literals = {DB_FILE_ALIASES.get(m.group(2) + ".db", m.group(2) + ".db")
                for m in DB_LITERAL_RE.finditer(text)}
    literals.discard("test.db")
    if len(literals) == 1:
        return next(iter(literals))
    if len(literals) > 1:
        return "|".join(sorted(literals))

    consts = {m.group(1) for m in PATHS_CONST_RE.finditer(text)}
    files = {_PATHS_TO_FILE[c] for c in consts if c in _PATHS_TO_FILE}
    if len(files) == 1:
        return next(iter(files))
    if len(files) > 1:
        return "|".join(sorted(files))

    m = SHARED_DB_IMPORT_RE.search(text)
    if m:
        system = m.group(1)
        return SHARED_ALIASES.get(system, f"shared:{system}")
    if PLATFORM_DB_IMPORT_RE.search(text):
        return "shared:platform"

    return f"unknown:{_owner_of(path)}"


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def scan(root: Path) -> tuple[dict, dict[str, int]]:
    """Return ({(target, table): [definitions]}, {table: referencing files})."""
    by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    texts: dict[Path, str] = {}

    for path in root.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        texts[path] = text
        if "CREATE TABLE" not in text.upper():
            continue
        target = _db_target(text, path)
        owner = _owner_of(path)
        for match in CREATE_RE.finditer(text):
            body = _balanced_body(text, match.end() - 1)
            if body is None:
                continue
            columns = _parse_columns(body)
            if not columns:
                continue
            by_key[(target, match.group(1).lower())].append({
                "file": str(path.relative_to(REPO_ROOT)),
                "owner": owner,
                "line": text.count("\n", 0, match.start()) + 1,
                "columns": columns,
            })

    # Blast radius: how many files mention the table in a SQL-ish context.
    # One pass per file extracting every table-position identifier, rather
    # than one regex per known table per file — the latter is quadratic and
    # takes minutes on a tree this size.
    tables = {table for _target, table in by_key}
    references: dict[str, int] = defaultdict(int)
    for text in texts.values():
        mentioned = {
            m.group(1).lower()
            for m in TABLE_POSITION_RE.finditer(text)
        }
        for table in mentioned & tables:
            references[table] += 1
    return by_key, references


def classify(by_key: dict, references: dict[str, int]) -> dict:
    conflicts, repeats = [], []
    for (target, table), defs in by_key.items():
        files = sorted({d["file"] for d in defs})
        if len(files) < 2:
            continue
        union: set[str] = set()
        for d in defs:
            union |= set(d["columns"])
        divergent = sorted(c for c in union
                           if any(c not in d["columns"] for d in defs))
        type_diffs = {
            col: sorted({d["columns"][col] for d in defs if col in d["columns"]})
            for col in sorted(union)
            if len({d["columns"][col] for d in defs if col in d["columns"]}) > 1
        }
        entry = {
            "target": target,
            "table": table,
            "referencing_files": references.get(table, 0),
            "files": files,
            "owners": sorted({d["owner"] for d in defs}),
            "definition_count": len(defs),
            "union_columns": sorted(union),
            "divergent_columns": divergent,
            "type_diffs": type_diffs,
            "variants": sorted(
                ({"file": d["file"], "line": d["line"],
                  "column_count": len(d["columns"]),
                  "missing": sorted(union - set(d["columns"]))}
                 for d in defs),
                key=lambda v: -v["column_count"],
            ),
        }
        (conflicts if (divergent or type_diffs) else repeats).append(entry)

    conflicts.sort(key=lambda c: (-c["referencing_files"],
                                  -len(c["divergent_columns"]),
                                  -len(c["files"])))
    return {"conflicts": conflicts, "repeats": repeats}


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def report(result: dict, limit: int) -> None:
    conflicts = result["conflicts"]
    print(f"tables with identical repeat definitions : {len(result['repeats'])}")
    print(f"tables with CONFLICTING definitions      : {len(conflicts)}")

    by_target: dict[str, int] = defaultdict(int)
    for c in conflicts:
        by_target[c["target"]] += 1
    print("\nConflicts by database:")
    for target, n in sorted(by_target.items(), key=lambda kv: -kv[1]):
        print(f"  {target:<34} {n}")

    print(f"\nRanked by blast radius (top {limit}):")
    print(f"  {'table':<34} {'reads':>6} {'defs':>5} {'files':>6} "
          f"{'divergent':>10}  database")
    for c in conflicts[:limit]:
        print(f"  {c['table']:<34} {c['referencing_files']:>6} "
              f"{c['definition_count']:>5} {len(c['files']):>6} "
              f"{len(c['divergent_columns']):>10}  {c['target']}")


def report_table(result: dict, table: str) -> int:
    matches = [c for c in result["conflicts"] if c["table"] == table]
    if not matches:
        print(f"No conflicting definitions for {table!r}.")
        return 1
    for c in matches:
        print(f"\n=== {c['table']} on {c['target']} ===")
        print(f"referencing files : {c['referencing_files']}")
        print(f"definitions       : {c['definition_count']} "
              f"across {len(c['files'])} files")
        print(f"union of columns  : {len(c['union_columns'])}")
        print(f"divergent columns : {', '.join(c['divergent_columns'])}")
        if c["type_diffs"]:
            print("\nsame column, different declaration:")
            for col, spellings in c["type_diffs"].items():
                print(f"  {col}:")
                for s in spellings:
                    print(f"      {s}")
        print("\ndefinitions (columns / missing vs union / file:line):")
        for v in c["variants"]:
            print(f"  {v['column_count']:>3}  -{len(v['missing']):<3} "
                  f"{v['file']}:{v['line']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=SRC_ROOT)
    ap.add_argument("--table", help="show every definition of one table")
    ap.add_argument("--json", type=Path, help="write the full result as JSON")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if conflicts exceed --max-conflicts")
    # Lower this as conflicts are fixed; never raise it. 301 when the audit
    # was first run; 299 after students and the local users table; 296 after
    # modules and student_modules — that pass also folded the phantom
    # student_grading_system.db target into student_records.db (see
    # DB_FILE_ALIASES), which surfaced conflicts the old partition hid, so
    # the number fell less than the work done would suggest.
    ap.add_argument("--max-conflicts", type=int, default=296,
                    help="ratchet ceiling; lower it as conflicts are fixed")
    args = ap.parse_args()

    _load_paths_constants()
    by_key, references = scan(args.root)
    result = classify(by_key, references)

    if args.json:
        args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")

    if args.table:
        return report_table(result, args.table.lower())

    report(result, args.limit)

    if args.check:
        n = len(result["conflicts"])
        if n > args.max_conflicts:
            print(f"\nFAIL: {n} conflicting tables exceeds the "
                  f"ceiling of {args.max_conflicts}.")
            return 1
        print(f"\nOK: {n} conflicting tables, ceiling {args.max_conflicts}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
