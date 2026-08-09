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
    PACKAGE / "domain/academics/programme_governance",
    PACKAGE / "domain/academics/research/pgr",
    PACKAGE / "services/events",
    PACKAGE / "services/operations.py",
    PACKAGE / "application/ports.py",
    PACKAGE / "application/persistence.py",
    PACKAGE / "application/data_lifecycle.py",
    PACKAGE / "application/lifecycle_consumers.py",
    PACKAGE / "application/case_management.py",
    PACKAGE / "domains/learners/application/identity_management.py",
    PACKAGE / "application/timetabling.py",
    PACKAGE / "application/connectors.py",
    PACKAGE / "domains/learners/application/alumni_transition.py",
    PACKAGE / "infrastructure/events.py",
    PACKAGE / "infrastructure/unit_of_work.py",
)


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


def main() -> int:
    errors: list[str] = []
    files = sorted({file for path in MODERNISED for file in python_files(path)})
    for file in files:
        source = file.read_text(encoding="utf-8")
        relative = file.relative_to(ROOT)
        lines = source.count("\n") + 1
        if lines > MAX_LINES:
            errors.append(f"{relative}: {lines} lines exceeds {MAX_LINES}")
        try:
            tree = ast.parse(source, filename=str(relative))
        except SyntaxError as exc:
            errors.append(f"{relative}:{exc.lineno}: invalid syntax: {exc.msg}")
            continue
        for module in imported_modules(tree):
            if ".interfaces.gui" in module or module.startswith("tkinter"):
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

    classification_path = (
        ROOT / "docs/university/MODULE_CLASSIFICATION.json"
    )
    catalogue = json.loads(classification_path.read_text(encoding="utf-8"))
    rules = catalogue["rules"]
    university_files = PACKAGE.rglob("*.py")
    for file in university_files:
        relative = file.relative_to(PACKAGE).as_posix()
        if not any(fnmatch.fnmatch(relative, rule["glob"]) for rule in rules):
            errors.append(f"{relative}: missing module classification")

    if errors:
        print("University architecture check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"University architecture check passed ({len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
