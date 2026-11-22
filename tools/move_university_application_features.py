#!/usr/bin/env python3
"""Group the flat ``systems/university/application/`` modules by feature.

The package held 95 modules side by side, with the feature only in a filename
prefix (``alumni_*``, ``batch_*``, ``graduation_*``, ``integrity_*`` ...). This
moves each one into a feature subpackage and drops the prefix:

=================================================  ============================
from ``application/``                              to ``application/``
=================================================  ============================
``calendar_{access,dates,events,year}``            ``academic_calendar/``
``alumni_*``                                       ``alumni/``
``assessment_outcomes``, ``classification``,       ``assessment/``
``module_results``
``attendance_{engagement,registers}``              ``attendance/``
``batch_*``                                        ``batch/``
``chatbot_{care,knowledge}``                       ``chatbot/``
``{course,lecturer,module}_evaluation``,           ``evaluation/``
``lecturer_feedback``, ``teaching_history``
``exam_{marking,office,results,timetable}``        ``exams/``
``graduation_*``                                   ``graduation/``
``integrity_*``, ``ai_indicators``,                ``integrity/``
``plagiarism_{checks,text}``
``library_{circulation,services}``                 ``library/``
``email_{admin,outbox}``                           ``mail/``
``module_*`` (not results/evaluation)              ``modules/``
``programme_*``, ``course_lifecycle_service``,     ``programmes/``
``course_team``, ``prospectus``
``research_*``                                     ``research/``
``student_*``, ``sixth_form_feedback``             ``students/``
``timetable_occurrences``, ``office_hours``        ``teaching/``
=================================================  ============================

``ports``, ``persistence``, ``connectors``, ``lifecycle_consumers`` and
``case_management`` stay at the top: they are package-wide or have no group.

The modules stay in ``application/`` rather than going into
``domains/<domain>/application/``: they import each other across domains
(graduation -> alumni, student lifecycle -> library and timetable), which the
slice boundary tests forbid. Moving them into the slices needs ports first.

Old paths keep working: each moved module leaves an identity alias
(``sys.modules[__name__] = new``), so ``mock.patch``/``monkeypatch`` on the old
name still act on the real code, and dotted paths stored outside the code (an
Alembic migration, job records) still resolve. The aliases are marked
``# layout-shim:`` for ``tools/check_layout.py``.

Import statements, quoted module names and ``university/application/<name>``
mentions in ``src/`` and ``tests/`` are rewritten to the new paths. Generated
migrations are left alone. Behaviour is unchanged.

Usage::

    python tools/move_university_application_features.py            # dry run
    python tools/move_university_application_features.py --apply
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PKG = "education_system"
APP = SRC / PKG / "systems" / "university" / "application"
MIGRATIONS = SRC / PKG / "migrations"
DOTTED = f"{PKG}.systems.university.application"
MAP_FILE = ROOT / "var" / "backups" / "maintenance" / "university-application-path-map.json"
SHIM_MARKER = "# layout-shim:"

sys.path.insert(0, str(SRC))

#: group -> {old module name: new module name}
GROUPS: dict[str, dict[str, str]] = {
    "academic_calendar": {
        "calendar_access": "access", "calendar_dates": "dates",
        "calendar_events": "events", "calendar_year": "year",
    },
    "alumni": {
        "alumni_access": "access", "alumni_comms": "comms", "alumni_community": "community",
        "alumni_giving": "giving", "alumni_records": "records",
    },
    "assessment": {
        "assessment_outcomes": "outcomes", "classification": "classification",
        "module_results": "module_results",
    },
    "attendance": {"attendance_engagement": "engagement", "attendance_registers": "registers"},
    "batch": {
        "batch_admin": "admin", "batch_enrolments": "enrolments", "batch_exports": "exports",
        "batch_files": "files", "batch_imports": "imports", "batch_jobs": "jobs",
        "batch_reports": "reports", "batch_schedule": "schedule", "batch_window": "window",
    },
    "chatbot": {"chatbot_care": "care", "chatbot_knowledge": "knowledge"},
    "evaluation": {
        "course_evaluation": "course", "lecturer_evaluation": "lecturer",
        "lecturer_feedback": "lecturer_feedback", "module_evaluation": "module",
        "teaching_history": "teaching_history",
    },
    "exams": {
        "exam_marking": "marking", "exam_office": "office", "exam_results": "results",
        "exam_timetable": "timetable",
    },
    "graduation": {
        "graduation_access": "access", "graduation_ceremonies": "ceremonies",
        "graduation_conferral": "conferral", "graduation_eligibility": "eligibility",
        "graduation_transcripts": "transcripts",
    },
    "integrity": {
        "integrity_access": "access", "integrity_ai": "ai", "integrity_choices": "choices",
        "integrity_evidence": "evidence", "integrity_external": "external",
        "integrity_jobs": "jobs", "integrity_records": "records", "integrity_review": "review",
        "integrity_tools": "tools", "ai_indicators": "ai_indicators",
        "plagiarism_checks": "plagiarism_checks", "plagiarism_text": "plagiarism_text",
    },
    "library": {"library_circulation": "circulation", "library_services": "services"},
    "mail": {"email_admin": "admin", "email_outbox": "outbox"},
    "modules": {
        "module_catalogue": "catalogue", "module_delivery": "delivery",
        "module_enrolment": "enrolment", "module_registration": "registration",
        "module_registration_admin": "registration_admin",
        "module_registration_messages": "registration_messages",
        "module_specification": "specification",
    },
    "programmes": {
        "course_lifecycle_service": "lifecycle", "programme_record": "record",
        "programme_structure": "structure", "course_team": "course_team",
        "prospectus": "prospectus",
    },
    "research": {
        "research_access": "access", "research_ethics": "ethics", "research_grants": "grants",
        "research_integrity": "integrity", "research_ip": "ip", "research_outputs": "outputs",
        "research_projects": "projects", "research_ref": "ref",
        "research_reminders": "reminders",
    },
    "students": {
        "student_bulk_actions": "bulk_actions", "student_data_quality": "data_quality",
        "student_erasure": "erasure", "student_lifecycle_service": "lifecycle",
        "student_record_rules": "record_rules", "student_search": "search",
        "student_search_extras": "search_extras", "student_search_insights": "search_insights",
        "student_search_reports": "search_reports", "student_search_saved": "search_saved",
        "sixth_form_feedback": "sixth_form_feedback",
    },
    "teaching": {"timetable_occurrences": "occurrences", "office_hours": "office_hours"},
}

GROUP_DOCS = {
    "academic_calendar": "Academic years, terms, key dates and calendar events.",
    "alumni": "Alumni office: records, community, communications and giving.",
    "assessment": "Assessment outcomes, module results and degree classification.",
    "attendance": "Attendance registers and engagement monitoring.",
    "batch": "Batch operations: file imports, exports, jobs, schedules and reports.",
    "chatbot": "Chatbot care routing and the managed FAQ knowledge base.",
    "evaluation": "Module, course and lecturer evaluation surveys.",
    "exams": "Exam office: marking, results and the exam timetable.",
    "graduation": "Graduation: eligibility, conferral, ceremonies and transcripts.",
    "integrity": "Academic integrity cases, plagiarism checks and AI-use indicators.",
    "library": "Library circulation and services.",
    "mail": "The e-mail outbox and its administration.",
    "modules": "Module catalogue, specification, delivery, enrolment and registration.",
    "programmes": "Programme record, structure, lifecycle, course team and prospectus.",
    "research": "Research office: roles, ethics, grants, outputs, REF and IP.",
    "students": "Student records: rules, lifecycle, search, bulk actions and erasure.",
    "teaching": "Dated timetable occurrences and office hours.",
}

#: old module name -> (group, new module name)
MOVES = {old: (group, new) for group, names in GROUPS.items() for old, new in names.items()}


def new_dotted(old: str) -> str:
    group, new = MOVES[old]
    return f"{DOTTED}.{group}.{new}"


def module_shim(new_module: str) -> str:
    return (
        f'"""Moved to ``{new_module}``.\n'
        "\n"
        "The old name *is* the new module object, so ``mock.patch`` and\n"
        "``monkeypatch`` targets still act on the real code. Delete once nothing\n"
        "imports the old path.\n"
        '"""\n'
        f"{SHIM_MARKER} {new_module}\n"
        "import importlib as _importlib\n"
        "import sys as _sys\n"
        "\n"
        f'_sys.modules[__name__] = _importlib.import_module("{new_module}")\n'
    )


# --------------------------------------------------------------- rewriting

_QUOTED = re.compile(r"([\"'])" + re.escape(DOTTED) + r"\.(\w+)")
_DOC_PATH = re.compile(r"university/application/(\w+)(\*?)")


def _import_line(indent: str, module: str, names: list[tuple[str, str | None]]) -> list[str]:
    parts = [n if not a or a == n else f"{n} as {a}" for n, a in names]
    one = f"{indent}from {module} import {', '.join(parts)}"
    if len(one) <= 99:
        return [one]
    return [f"{indent}from {module} import ("] + [f"{indent}    {p}," for p in parts] + [f"{indent})"]


def _rewrite_import(node: ast.ImportFrom, lines: list[str]) -> list[str] | None:
    """New source lines for *node*, or ``None`` when it needs no change.

    Raises ``ValueError`` when the statement cannot be rewritten safely.
    """
    module = node.module or ""
    span = lines[node.lineno - 1:node.end_lineno]
    first, last = span[0], span[-1]
    indent = first[:node.col_offset]
    if indent.strip() or last[node.end_col_offset:].strip().split("#")[0].strip():
        raise ValueError("shares a line with other code")
    if module.startswith(DOTTED + "."):
        head = module[len(DOTTED) + 1:].split(".")[0]
        if head not in MOVES:
            return None
        rest = module[len(DOTTED) + 1 + len(head):]
        text = "\n".join(span).replace(f"from {module} ", f"from {new_dotted(head)}{rest} ", 1)
        if text == "\n".join(span):
            raise ValueError("module name not found verbatim")
        return text.split("\n")
    if module != DOTTED or not any(a.name in MOVES for a in node.names):
        return None
    body = "\n".join(span)
    comment = ""
    if "#" in body:
        if len(span) > 1:
            raise ValueError("comment inside a multi-line import")
        comment = "  #" + first.split("#", 1)[1]
    out: list[str] = []
    batch_module, batch = None, []
    for alias in node.names:
        if alias.name in MOVES:
            group, new = MOVES[alias.name]
            target, item = f"{DOTTED}.{group}", (new, alias.asname or alias.name)
        else:
            target, item = DOTTED, (alias.name, alias.asname)
        if target != batch_module and batch:
            out += _import_line(indent, batch_module, batch)
            batch = []
        batch_module = target
        batch.append(item)
    out += _import_line(indent, batch_module, batch)
    out[0] += comment
    return out


def _rewrite_text(text: str) -> tuple[str, int, list[str]]:
    """(new text, statements changed, problems)."""
    problems: list[str] = []
    changed = 0
    lines = text.split("\n")
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return text, 0, [f"syntax error, skipped: {exc}"]
    edits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and not node.level:
            try:
                new = _rewrite_import(node, lines)
            except ValueError as exc:
                problems.append(f"line {node.lineno}: {exc}")
                continue
            if new is not None:
                edits.append((node.lineno, node.end_lineno, new))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(DOTTED + ".") and \
                        alias.name[len(DOTTED) + 1:].split(".")[0] in MOVES:
                    problems.append(f"line {node.lineno}: plain 'import' of a moved module")
    for start, end, new in sorted(edits, reverse=True):
        lines[start - 1:end] = new
        changed += 1
    text = "\n".join(lines)

    def quoted(m: re.Match) -> str:
        return m.group(1) + new_dotted(m.group(2)) if m.group(2) in MOVES else m.group(0)

    text, n = _QUOTED.subn(quoted, text)
    changed += n

    def doc(m: re.Match) -> str:
        name, star = m.group(1), m.group(2)
        if name in MOVES and not star:
            group, new = MOVES[name]
            return f"university/application/{group}/{new}"
        if star:
            groups = {g for old, (g, _) in MOVES.items() if old.startswith(name)}
            if len(groups) == 1:
                return f"university/application/{groups.pop()}/"
        return m.group(0)

    text, n = _DOC_PATH.subn(doc, text)
    changed += n
    for i, line in enumerate(text.split("\n"), 1):
        if re.search(re.escape(DOTTED) + r"\.[\"'{]", line) or line.rstrip().endswith(DOTTED + '."'):
            problems.append(f"line {i}: split or formatted module name, fix by hand")
    return text, changed, problems


def candidates():
    for root in (SRC / PKG, ROOT / "tests"):
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts or MIGRATIONS in path.parents:
                continue
            if path.parent == APP and path.stem in MOVES:
                continue  # becomes a shim; its moved copy is handled below
            yield path


def rewrite(apply: bool, extra: list[Path]) -> tuple[int, int, list[str]]:
    files = statements = 0
    problems: list[str] = []
    for path in list(candidates()) + extra:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if SHIM_MARKER in text or ("university.application" not in text
                                   and "university/application" not in text):
            continue
        new, n, issues = _rewrite_text(text)
        problems += [f"{path.relative_to(ROOT)}: {p}" for p in issues]
        if new != text:
            files += 1
            statements += n
            if apply:
                path.write_text(new, encoding="utf-8")
    return files, statements, problems


# ---------------------------------------------------------------- main


def backup() -> Path:
    """Archive ``application/`` and every file the rewrite may touch.

    Most of the tree is uncommitted, so git alone cannot undo this.
    """
    from education_system import paths
    dest = paths.maintenance_backup_dir("university-application-features", create=True)
    archive = dest / "university_application_sources.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(APP, arcname=str(APP.relative_to(ROOT)),
                filter=lambda t: None if "__pycache__" in t.name else t)
        for path in candidates():
            text = path.read_text(encoding="utf-8", errors="replace")
            if "university.application" in text or "university/application" in text:
                tar.add(path, arcname=str(path.relative_to(ROOT)))
    return archive


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    present = {p.stem for p in APP.glob("*.py")} - {"__init__"}
    missing = sorted(set(MOVES) - present)
    unplanned = sorted(present - set(MOVES) - {
        "ports", "persistence", "connectors", "lifecycle_consumers", "case_management"})
    collisions = [g for g in GROUPS if (APP / g).exists() or (APP / f"{g}.py").exists()]
    print(f"modules to move: {len(MOVES)} into {len(GROUPS)} groups")
    if missing or unplanned or collisions:
        print("Refusing.", f"missing: {missing}", f"not in the plan: {unplanned}",
              f"group names taken: {collisions}", sep="\n  ")
        return 1
    files, statements, problems = rewrite(apply=False, extra=[])
    print(f"files to rewrite: {files} | statements/strings: {statements} | "
          f"to fix by hand: {len(problems)}")
    for line in problems:
        print("  hand:", line)
    if not args.apply:
        print("\nDry run. Re-run with --apply.")
        return 0

    print("backup:", backup())
    path_map = {}
    moved: list[Path] = []
    for group, names in GROUPS.items():
        pkg = APP / group
        pkg.mkdir()
        (pkg / "__init__.py").write_text(f'"""{GROUP_DOCS[group]}"""\n', encoding="utf-8")
        for old, new in names.items():
            src_path, dest = APP / f"{old}.py", pkg / f"{new}.py"
            shutil.move(str(src_path), str(dest))
            src_path.write_text(module_shim(new_dotted(old)), encoding="utf-8")
            moved.append(dest)
            path_map[src_path.relative_to(SRC / PKG).as_posix()] = \
                dest.relative_to(SRC / PKG).as_posix()
    files, statements, problems = rewrite(apply=True, extra=moved)
    MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    MAP_FILE.write_text(json.dumps(path_map, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"moved {len(moved)} modules into {len(GROUPS)} packages; rewrote "
          f"{statements} references in {files} files; {len(problems)} to fix by hand; "
          f"path map: {MAP_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
