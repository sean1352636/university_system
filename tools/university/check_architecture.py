#!/usr/bin/env python3
"""Enforce boundaries for the modernised university core."""

from __future__ import annotations

import ast
import fnmatch
import json
import sys
from pathlib import Path

# check_architecture.py -> university -> tools -> <repo root>
ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src/education_system/systems/university"
MAX_LINES = 800
MAX_COMPLEXITY = 15
MODERNISED = (
    PACKAGE / "domains/admissions/domain/services/admissions_lifecycle.py",
    PACKAGE / "domains/learners/domain/student_lifecycle.py",
    PACKAGE / "domains/assessment/domain/boards",
    PACKAGE / "domains/academics/domain/programme_governance",
    PACKAGE / "domains/academics/domain/research/pgr",
    PACKAGE / "services/events",
    PACKAGE / "services/operations.py",
    PACKAGE / "application/ports.py",
    PACKAGE / "application/persistence.py",
    PACKAGE / "domains/governance/application/data_lifecycle.py",
    PACKAGE / "application/lifecycle_consumers.py",
    PACKAGE / "application/case_management.py",
    PACKAGE / "domains/learners/application/identity_management.py",
    PACKAGE / "domains/academics/application/timetabling.py",
    PACKAGE / "application/connectors.py",
    PACKAGE / "domains/learners/application/alumni_transition.py",
    PACKAGE / "infrastructure/events.py",
    PACKAGE / "infrastructure/unit_of_work.py",
)

#: Application layers are gated as a whole, so a new use-case module meets the
#: rules above from its first commit instead of waiting to be pinned by hand.
APPLICATION_LAYERS = ("application", "domains/*/application")

#: Application modules that break a rule today. A ratchet: fixing one fails the
#: check until its entry is deleted, so the list can only shrink.
APPLICATION_EXCEPTIONS = {
    # imports a chat-rooms module from the student CRUD GUI
    "application/student_lifecycle_service.py",
    # tkinter file dialogs for evidence uploads
    "domains/safeguarding/application/services/media.py",
    # save_submission complexity above MAX_COMPLEXITY
    "domains/safeguarding/application/services/submissions.py",
}


def python_files(path: Path):
    if path.is_file():
        yield path
    elif path.exists():
        yield from path.rglob("*.py")


def imported_modules(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def function_complexity(node: ast.AST) -> int:
    branches = (
        ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.IfExp,
        ast.Match, ast.comprehension,
    )
    return 1 + sum(isinstance(child, branches) for child in ast.walk(node))


def application_files():
    """Every module in an application layer, minus the recorded exceptions."""
    found = set()
    for pattern in APPLICATION_LAYERS:
        for layer in PACKAGE.glob(pattern):
            found.update(python_files(layer))
    return found


def file_errors(file: Path) -> list[str]:
    """Rule breaches in one module."""
    errors: list[str] = []
    source = file.read_text(encoding="utf-8")
    relative = file.relative_to(ROOT)
    lines = source.count("\n") + 1
    if lines > MAX_LINES:
        errors.append(f"{relative}: {lines} lines exceeds {MAX_LINES}")
    try:
        tree = ast.parse(source, filename=str(relative))
    except SyntaxError as exc:
        errors.append(f"{relative}:{exc.lineno}: invalid syntax: {exc.msg}")
        return errors
    for module in imported_modules(tree):
        # GUI adapters live in two places: a slice's own ``interfaces/gui/`` and
        # the system-wide ``shell/gui/``. Matching only the former would let the
        # shell back in through the side door.
        if (
            ".interfaces.gui" in module
            or ".shell.gui" in module
            or module.startswith("tkinter")
        ):
            errors.append(f"{relative}: forbidden domain dependency on {module}")
        if module == "sqlite3" and "/infrastructure/" not in str(relative):
            errors.append(
                f"{relative}: direct sqlite3 import; use a repository/unit-of-work"
            )
    if "CREATE TABLE" in source.upper() or "ALTER TABLE" in source.upper():
        if "/migrations/" not in str(relative):
            errors.append(f"{relative}: runtime schema DDL is forbidden")
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            complexity = function_complexity(node)
            if complexity > MAX_COMPLEXITY:
                errors.append(
                    f"{relative}:{node.lineno}: {node.name} complexity "
                    f"{complexity} exceeds {MAX_COMPLEXITY}"
                )
    return errors


def main() -> int:
    errors: list[str] = []
    # A pin that no longer exists yields no files, so the gate would keep passing
    # while quietly checking less than it claims. Fail instead.
    for path in MODERNISED:
        if not path.exists():
            errors.append(
                f"{path.relative_to(ROOT)}: MODERNISED path does not exist "
                f"(moved? the gate silently stops checking it)"
            )

    exceptions = {PACKAGE / rel for rel in APPLICATION_EXCEPTIONS}
    for path in sorted(exceptions):
        if not path.exists():
            errors.append(
                f"{path.relative_to(ROOT)}: APPLICATION_EXCEPTIONS entry does not "
                f"exist; delete it"
            )
        elif not file_errors(path):
            errors.append(
                f"{path.relative_to(ROOT)}: now passes every rule; delete it from "
                f"APPLICATION_EXCEPTIONS"
            )

    pinned = {file for path in MODERNISED for file in python_files(path)}
    files = sorted(pinned | (application_files() - exceptions))
    for file in files:
        errors.extend(file_errors(file))

    classification_path = (
        ROOT / "docs/university/MODULE_CLASSIFICATION.json"
    )
    catalogue = json.loads(classification_path.read_text(encoding="utf-8"))
    rules = catalogue["rules"]
    university_files = [p.relative_to(PACKAGE).as_posix() for p in PACKAGE.rglob("*.py")]
    for relative in university_files:
        if not any(fnmatch.fnmatch(relative, rule["glob"]) for rule in rules):
            errors.append(f"{relative}: missing module classification")

    # Every rule must still describe real code. Without this, a rule whose area has
    # been moved or renamed simply stops matching and the trailing "**" catch-all
    # reclassifies those modules silently -- the check above cannot see the
    # difference, because a file matched by "**" is still matched.
    for rule in rules:
        if rule["glob"] == "**":
            continue
        if not any(fnmatch.fnmatch(f, rule["glob"]) for f in university_files):
            errors.append(
                f"{rule['glob']}: classification rule matches no module "
                f"(stale path? it is now silently absorbed by the '**' catch-all)"
            )

    if errors:
        print("University architecture check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"University architecture check passed ({len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
