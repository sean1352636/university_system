"""Additively reconcile the 60 'conflicting' tables in student_records.db
with their canonical production CREATE TABLE definition.

For each of the 60 tables flagged in `schema_audit_report.txt`, pick the most
canonical, most-complete production variant; parse its real column list (not
CHECK enum values); compare against `PRAGMA table_info`; and emit
`ALTER TABLE ... ADD COLUMN` statements for any columns missing in live.

Never drops or renames existing columns. NOT NULL / PRIMARY KEY / UNIQUE /
REFERENCES are stripped from the ALTER form because SQLite cannot apply them
to an existing populated table.

Run:
    python -m education_system.university_system.scripts.reconcile_conflicting_tables --dry-run
    python -m education_system.university_system.scripts.reconcile_conflicting_tables --apply
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path("/home/seancatchpole989/education_system")
DEFAULT_DB = REPO_ROOT / "university_system/data/db_files/student_records.db"
DEFAULT_AUDIT = Path("/home/seancatchpole989/schema_audit_report.txt")
DEFAULT_PLAN = Path("/tmp/reconcile_plan.txt")

CREATE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`\[]?(\w+)[\"`\]]?\s*\(",
    re.IGNORECASE,
)

# Variant entry inside the conflicting line: `[Ncols]@path:line` (optionally
# followed by `(+M)` indicating M extra equivalent locations we ignore).
VARIANT_RE = re.compile(r"\[(\d+)cols\]@([^:]+):(\d+)(?:\(\+\d+\))?")
HEADER_RE = re.compile(r"^([A-Za-z0-9_]+)\s+—\s+live=(\d+)cols")


# ---------------------------------------------------------------------------
# Audit parsing
# ---------------------------------------------------------------------------


@dataclass
class Variant:
    cols: int
    path: str
    line: int


@dataclass
class TableEntry:
    table: str
    live_cols: int
    variants: list[Variant] = field(default_factory=list)


def parse_audit_report(audit_path: Path) -> list[TableEntry]:
    text = audit_path.read_text(encoding="utf-8", errors="replace")
    # Slice between "=== Conflicting CREATE definitions" and the next "===" header.
    start = text.find("=== Conflicting CREATE definitions")
    if start < 0:
        raise RuntimeError("Conflicting section not found in audit report")
    body_start = text.find("\n", start) + 1
    next_section = text.find("\n=== ", body_start)
    body = text[body_start:next_section] if next_section > 0 else text[body_start:]

    entries: list[TableEntry] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = HEADER_RE.match(line)
        if not m:
            continue
        entry = TableEntry(table=m.group(1), live_cols=int(m.group(2)))
        for vm in VARIANT_RE.finditer(line):
            entry.variants.append(
                Variant(cols=int(vm.group(1)), path=vm.group(2), line=int(vm.group(3)))
            )
        entries.append(entry)
    return entries


# ---------------------------------------------------------------------------
# Canonical-variant selection
# ---------------------------------------------------------------------------


def _is_test_path(path: str) -> bool:
    if "/tests/" in path:
        return True
    name = path.rsplit("/", 1)[-1]
    return "test" in name and name.endswith(".py")


def _is_excluded_path(path: str) -> bool:
    return path.endswith("shared/migrations/runner.py")


def _priority(path: str) -> int:
    """Lower number = higher priority. Used to rank non-test variants."""
    if "infrastructure/database/schemas/" in path:
        return 0
    if "infrastructure/database/migrations/" in path:
        return 1
    if "modules/domain/" in path and "/services/" in path and (
        path.endswith("/database.py") or path.endswith("/db.py") or path.endswith("/schema.py")
    ):
        return 2
    if "modules/domain/" in path and "/core/" in path and path.endswith("database.py"):
        return 3
    return 4


def pick_canonical(entry: TableEntry) -> Variant | None:
    candidates: list[Variant] = []
    for v in entry.variants:
        if v.cols == 0:
            continue
        if _is_test_path(v.path) or _is_excluded_path(v.path):
            continue
        candidates.append(v)
    if not candidates:
        return None
    # Sort by (priority asc, cols desc) and take the first.
    candidates.sort(key=lambda v: (_priority(v.path), -v.cols))
    return candidates[0]


# ---------------------------------------------------------------------------
# CREATE-block extraction (paren matching, identical strategy to
# create_missing_tables.py)
# ---------------------------------------------------------------------------


def _extract_create_sql(file_path: Path, line_no: int, expected_table: str) -> str | None:
    text = file_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for ln in lines:
        offsets.append(offsets[-1] + len(ln))
    if line_no < 1 or line_no > len(lines):
        return None
    start_line = max(1, line_no - 2)
    start = offsets[start_line - 1]
    snippet = text[start : start + 12000]
    m = CREATE_RE.search(snippet)
    if not m:
        return None
    found = m.group(1)
    if found.lower() != expected_table.lower():
        return None
    open_idx = snippet.index("(", m.end() - 1)
    depth = 0
    i = open_idx
    in_str: str | None = None
    while i < len(snippet):
        ch = snippet[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
        else:
            if ch in ("'", '"'):
                in_str = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return snippet[m.start() : i + 1]
        i += 1
    return None


# ---------------------------------------------------------------------------
# Column parsing
# ---------------------------------------------------------------------------


_TABLE_CONSTRAINT_KEYWORDS = (
    "PRIMARY KEY",
    "FOREIGN KEY",
    "UNIQUE",
    "CHECK",
    "CONSTRAINT",
    "INDEX",
)


def _split_top_level_commas(body: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    cur: list[str] = []
    in_str: str | None = None
    i = 0
    while i < len(body):
        ch = body[i]
        if in_str:
            cur.append(ch)
            if ch == "\\" and i + 1 < len(body):
                cur.append(body[i + 1])
                i += 2
                continue
            if ch == in_str:
                in_str = None
        else:
            if ch in ("'", '"'):
                in_str = ch
                cur.append(ch)
            elif ch == "(":
                depth += 1
                cur.append(ch)
            elif ch == ")":
                depth -= 1
                cur.append(ch)
            elif ch == "," and depth == 0:
                parts.append("".join(cur).strip())
                cur = []
            else:
                cur.append(ch)
        i += 1
    tail = "".join(cur).strip()
    if tail:
        parts.append(tail)
    return parts


def _is_table_constraint(part: str) -> bool:
    upper = part.lstrip().upper()
    return any(upper.startswith(kw) for kw in _TABLE_CONSTRAINT_KEYWORDS)


_IDENT_RE = re.compile(r'^\s*[\"`\[]?([A-Za-z_][A-Za-z0-9_]*)[\"`\]]?\s*(.*)$', re.DOTALL)


def _strip_sql_line_comments(text: str) -> str:
    """Remove `-- ...` to end-of-line, but not inside string literals."""
    out: list[str] = []
    i = 0
    in_str: str | None = None
    while i < len(text):
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < len(text):
                out.append(text[i + 1])
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in ("'", '"'):
            in_str = ch
            out.append(ch)
            i += 1
            continue
        if ch == "-" and i + 1 < len(text) and text[i + 1] == "-":
            # skip to end of line (don't consume the newline)
            j = text.find("\n", i)
            if j < 0:
                break
            i = j
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def parse_columns(create_sql: str) -> list[tuple[str, str]]:
    """Return list of (column_name, raw_definition_after_name) tuples."""
    create_sql = _strip_sql_line_comments(create_sql)
    open_idx = create_sql.find("(")
    close_idx = create_sql.rfind(")")
    if open_idx < 0 or close_idx <= open_idx:
        return []
    body = create_sql[open_idx + 1 : close_idx]
    cols: list[tuple[str, str]] = []
    for part in _split_top_level_commas(body):
        if not part or _is_table_constraint(part):
            continue
        m = _IDENT_RE.match(part)
        if not m:
            continue
        name = m.group(1)
        rest = m.group(2).strip().rstrip(",").strip()
        cols.append((name, rest))
    return cols


# ---------------------------------------------------------------------------
# ALTER-clause sanitization
# ---------------------------------------------------------------------------


_REFERENCES_RE = re.compile(
    r"\bREFERENCES\b\s+[\"`\[]?\w+[\"`\]]?\s*(?:\([^)]*\))?"
    r"(?:\s+ON\s+(?:DELETE|UPDATE)\s+(?:CASCADE|RESTRICT|SET\s+NULL|SET\s+DEFAULT|NO\s+ACTION))*"
    r"(?:\s+(?:DEFERRABLE|NOT\s+DEFERRABLE)(?:\s+INITIALLY\s+(?:DEFERRED|IMMEDIATE))?)?",
    re.IGNORECASE,
)
_NOT_NULL_RE = re.compile(r"\bNOT\s+NULL\b", re.IGNORECASE)
_PRIMARY_KEY_RE = re.compile(r"\bPRIMARY\s+KEY(?:\s+AUTOINCREMENT)?\b", re.IGNORECASE)
_UNIQUE_RE = re.compile(r"\bUNIQUE\b", re.IGNORECASE)


def sanitize_for_alter(definition: str) -> str:
    out = definition
    out = _REFERENCES_RE.sub("", out)
    out = _NOT_NULL_RE.sub("", out)
    out = _PRIMARY_KEY_RE.sub("", out)
    out = _UNIQUE_RE.sub("", out)
    out = re.sub(r"\s+", " ", out).strip().rstrip(",").strip()
    if not out:
        out = "TEXT"
    return out


# ---------------------------------------------------------------------------
# Main reconciliation
# ---------------------------------------------------------------------------


@dataclass
class ReconcileResult:
    added: dict[str, list[str]] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)
    failed: list[tuple[str, str, str]] = field(default_factory=list)
    plan: list[str] = field(default_factory=list)


def reconcile_conflicting_tables(
    db_path: Path = DEFAULT_DB,
    dry_run: bool = True,
    audit_path: Path = DEFAULT_AUDIT,
) -> ReconcileResult:
    result = ReconcileResult()
    entries = parse_audit_report(audit_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        for entry in entries:
            variant = pick_canonical(entry)
            if variant is None:
                result.skipped[entry.table] = "no canonical (non-test) source"
                continue
            file_path = REPO_ROOT / variant.path
            if not file_path.exists():
                result.skipped[entry.table] = f"source not found: {variant.path}"
                continue
            create_sql = _extract_create_sql(file_path, variant.line, entry.table)
            if create_sql is None:
                result.skipped[entry.table] = (
                    f"could not extract CREATE at {variant.path}:{variant.line}"
                )
                continue
            canon_cols = parse_columns(create_sql)
            if not canon_cols:
                result.skipped[entry.table] = "no columns parsed from canonical SQL"
                continue
            try:
                live_info = list(conn.execute(f'PRAGMA table_info("{entry.table}")'))
            except sqlite3.Error as exc:
                result.skipped[entry.table] = f"PRAGMA failed: {exc}"
                continue
            if not live_info:
                result.skipped[entry.table] = "table missing in live DB"
                continue
            live_names = {row[1].lower() for row in live_info}
            to_add: list[tuple[str, str]] = []
            for name, raw_def in canon_cols:
                if name.lower() in live_names:
                    continue
                clean = sanitize_for_alter(raw_def)
                to_add.append((name, clean))
            if not to_add:
                continue
            added_for_table: list[str] = []
            for name, clean_def in to_add:
                stmt = f'ALTER TABLE "{entry.table}" ADD COLUMN "{name}" {clean_def}'
                result.plan.append(stmt)
                if dry_run:
                    added_for_table.append(name)
                    continue
                try:
                    conn.execute(stmt)
                    conn.commit()
                    added_for_table.append(name)
                except sqlite3.Error as exc:
                    result.failed.append((entry.table, name, f"{type(exc).__name__}: {exc}"))
            if added_for_table:
                result.added[entry.table] = added_for_table
    finally:
        conn.close()
    return result


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify(db_path: Path, added: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Return list of (table, column) pairs that the script reported adding
    but which are NOT present in the live DB after applying."""
    missing: list[tuple[str, str]] = []
    conn = sqlite3.connect(str(db_path))
    try:
        for table, cols in added.items():
            live = {
                row[1].lower()
                for row in conn.execute(f'PRAGMA table_info("{table}")')
            }
            for c in cols:
                if c.lower() not in live:
                    missing.append((table, c))
    finally:
        conn.close()
    return missing


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_report(r: ReconcileResult, dry_run: bool, verify_missing: list[tuple[str, str]]) -> None:
    verb = "would add" if dry_run else "added"
    total_cols = sum(len(v) for v in r.added.values())
    print(f"=== {verb}: {len(r.added)} tables / {total_cols} columns ===")
    for t, cols in r.added.items():
        print(f"  + {t}: {', '.join(cols)}")
    if r.skipped:
        print(f"\n=== skipped: {len(r.skipped)} ===")
        for t, reason in r.skipped.items():
            print(f"  ? {t}: {reason}")
    if r.failed:
        print(f"\n=== failed: {len(r.failed)} ===")
        for t, c, err in r.failed:
            print(f"  ! {t}.{c}: {err}")
    if not dry_run:
        if verify_missing:
            print(f"\n=== verify: MISSING {len(verify_missing)} ===")
            for t, c in verify_missing:
                print(f"  - {t}.{c}")
        else:
            print("\n=== verify: OK ===")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    p.add_argument("--plan-out", type=Path, default=DEFAULT_PLAN)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True)
    g.add_argument("--apply", action="store_true")
    args = p.parse_args()
    dry_run = not args.apply
    r = reconcile_conflicting_tables(db_path=args.db, dry_run=dry_run, audit_path=args.audit)
    args.plan_out.write_text("\n".join(r.plan) + "\n", encoding="utf-8")
    verify_missing: list[tuple[str, str]] = []
    if not dry_run:
        verify_missing = verify(args.db, r.added)
    _print_report(r, dry_run=dry_run, verify_missing=verify_missing)


if __name__ == "__main__":
    main()
