#!/usr/bin/env python3
"""Give the university's analytics and communication code one home each.

Analytics engines were spread over ``services/analytics``,
``services/business_intelligence`` and ``services/dashboard`` (with two Tk
windows inside them), their windows over ``shell/gui/student_analytics`` and
``shell/gui/enhanced_reporting``; ``infrastructure/analytics`` was imported by
nothing. Communication channels were split between ``infrastructure/communication``
and ``services/communication``. This moves:

====================================================  ==========================================
from (under ``systems/university/``)                  to
====================================================  ==========================================
``services/analytics/``                               ``shared/analytics/``
``services/analytics/predictive_analytics_gui.py``    ``shell/gui/analytics/predictive_analytics_gui.py``
``services/business_intelligence/``                   ``shared/analytics/business_intelligence/``
``services/business_intelligence/business_intelligence_gui.py``
                                                      ``shell/gui/analytics/business_intelligence_gui.py``
``services/dashboard/``                               ``shared/analytics/dashboard/``
``shell/gui/student_analytics/``                      ``shell/gui/analytics/student_analytics/``
``shell/gui/enhanced_reporting/``                     ``shell/gui/analytics/enhanced_reporting/``
``services/communication/communication_manager.py``   ``infrastructure/communication/communication_manager.py``
``services/communication/schema.py``                  ``infrastructure/communication/communication_schema.py``
``infrastructure/analytics/`` (dead)                  ``remove/`` at the repo root
====================================================  ==========================================

``infrastructure/email`` stays where it is: 566 files import it, and moving it
would only rename it.

Old paths keep working through the same module aliases and package mirrors as
``tools/move_university_ai.py`` (whose helpers this reuses); the dead package
leaves nothing behind. Imports, quoted and written module names, and
``university/<path>`` mentions in ``src/`` and ``tests/`` are rewritten.

Usage::

    python tools/move_university_analytics_comms.py            # dry run
    python tools/move_university_analytics_comms.py --apply
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import move_university_ai as base  # noqa: E402

ROOT, SRC, U = base.ROOT, base.SRC, base.U
CLASSIFICATION = base.CLASSIFICATION
MAP_FILE = ROOT / "var" / "backups" / "maintenance" / "university-analytics-comms-path-map.json"

DIR_MOVES = [
    (U / "services/analytics", U / "shared/analytics"),
    (U / "services/business_intelligence", U / "shared/analytics/business_intelligence"),
    (U / "services/dashboard", U / "shared/analytics/dashboard"),
    (U / "shell/gui/student_analytics", U / "shell/gui/analytics/student_analytics"),
    (U / "shell/gui/enhanced_reporting", U / "shell/gui/analytics/enhanced_reporting"),
]
FILE_MOVES = [
    (U / "services/analytics/predictive_analytics_gui.py",
     U / "shell/gui/analytics/predictive_analytics_gui.py"),
    (U / "services/business_intelligence/business_intelligence_gui.py",
     U / "shell/gui/analytics/business_intelligence_gui.py"),
    (U / "services/communication/communication_manager.py",
     U / "infrastructure/communication/communication_manager.py"),
    (U / "services/communication/schema.py",
     U / "infrastructure/communication/communication_schema.py"),
]
#: Packages folded into an existing package: the old ``__init__`` becomes a mirror.
PACKAGE_FOLDS = [(U / "services/communication", U / "infrastructure/communication")]
DEAD = [U / "infrastructure/analytics"]
NEW_PACKAGES = {
    U / "shell/gui/analytics": "Analytics and reporting windows: student analytics, enhanced\n"
                               "reporting, predictive analytics and business intelligence.\n"
                               "Their engines are in ``shared/analytics``.",
}
#: What ``infrastructure/communication`` must now export for the folded package.
FOLD_EXPORTS = (
    "\n# Communication hub (folded in from services/communication)\n"
    "from education_system.systems.university.infrastructure.communication.communication_manager import (\n"
    "    CommunicationManager,\n"
    ")\n"
    "from education_system.systems.university.infrastructure.communication.communication_schema import (\n"
    "    create_communication_tables,\n"
    ")\n"
)
CLASSIFICATION_RENAMES = {"infrastructure/analytics/**": "shared/analytics/**"}


def plan():
    """(python moves, data-file moves, old->new dotted prefixes)."""
    singles = {old for old, _ in FILE_MOVES}
    moves: list[tuple[Path, Path]] = []
    data: list[tuple[Path, Path]] = []
    prefixes: dict[str, str] = {}
    for old_dir, new_dir in DIR_MOVES:
        prefixes[base.dotted(old_dir / "__init__.py")] = base.dotted(new_dir / "__init__.py")
        for path in sorted(old_dir.rglob("*")):
            if "__pycache__" in path.parts or path.is_dir() or path in singles:
                continue
            dest = new_dir / path.relative_to(old_dir)
            (moves if path.suffix == ".py" else data).append((path, dest))
    for old, new in FILE_MOVES:
        moves.append((old, new))
        prefixes[base.dotted(old)] = base.dotted(new)
    for old_pkg, new_pkg in PACKAGE_FOLDS:
        prefixes[base.dotted(old_pkg / "__init__.py")] = base.dotted(new_pkg / "__init__.py")
    return moves, data, prefixes


def backup(moves, data, paths) -> Path:
    """Archive everything moved or rewritten; most of the tree is uncommitted."""
    from education_system import paths as edu_paths
    dest = edu_paths.maintenance_backup_dir("university-analytics-comms", create=True)
    archive = dest / "university_analytics_comms_sources.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for src_path, _ in moves + data:
            tar.add(src_path, arcname=str(src_path.relative_to(ROOT)))
        for old_pkg, new_pkg in PACKAGE_FOLDS:
            for init in (old_pkg / "__init__.py", new_pkg / "__init__.py"):
                tar.add(init, arcname=str(init.relative_to(ROOT)))
        for dead in DEAD:
            tar.add(dead, arcname=str(dead.relative_to(ROOT)),
                    filter=lambda t: None if "__pycache__" in t.name else t)
        for path in paths:
            tar.add(path, arcname=str(path.relative_to(ROOT)))
        tar.add(CLASSIFICATION, arcname=str(CLASSIFICATION.relative_to(ROOT)))
    return archive


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    moves, data, prefixes = plan()
    missing = [str(s) for s, _ in moves if not s.exists()] + \
        [str(d) for d in DEAD if not d.exists()]
    collisions = [str(d) for _, d in moves + data if d.exists()] + \
        [str(ROOT / "remove" / d.relative_to(ROOT)) for d in DEAD
         if (ROOT / "remove" / d.relative_to(ROOT)).exists()]
    print(f"python modules to move: {len(moves)} | data files: {len(data)} | "
          f"prefixes: {len(prefixes)} | dead packages: {len(DEAD)}")
    if missing or collisions:
        print("Refusing:", *(missing + collisions)[:10], sep="\n  ")
        return 1
    sources = {s for s, _ in moves}
    paths = [p for p in base.candidates(sources) if not any(d in p.parents for d in DEAD)]
    files, statements, problems = base.rewrite(prefixes, apply=False, paths=paths + sorted(sources))
    print(f"files to rewrite: {files} | references: {statements} | to fix by hand: {len(problems)}")
    for line in problems:
        print("  hand:", line)
    if not args.apply:
        print("\nDry run. Re-run with --apply.")
        return 0

    needles = list(prefixes) + [o for o, _ in base._slash_prefixes(prefixes)]
    touched = [p for p in paths if p.exists() and any(
        n in p.read_text(encoding="utf-8", errors="replace") for n in needles)]
    print("backup:", backup(moves, data, touched))
    for pkg, doc in NEW_PACKAGES.items():
        pkg.mkdir(parents=True, exist_ok=True)
        init = pkg / "__init__.py"
        if not init.exists():
            init.write_text(f'"""{doc}"""\n', encoding="utf-8")
    path_map = {}
    for src_path, dest in moves:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dest))
        shim = base.package_shim if src_path.name == "__init__.py" else base.module_shim
        src_path.write_text(shim(base.dotted(dest)), encoding="utf-8")
        path_map[src_path.relative_to(SRC / base.PKG).as_posix()] = \
            dest.relative_to(SRC / base.PKG).as_posix()
    for src_path, dest in data:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dest))
    for old_pkg, new_pkg in PACKAGE_FOLDS:
        new_init = new_pkg / "__init__.py"
        text = new_init.read_text(encoding="utf-8")
        head, sep, tail = text.partition("\n__all__ = [")
        new_init.write_text(
            head.rstrip() + "\n" + FOLD_EXPORTS + "\n__all__ = [" + tail.replace(
                "\n]", "\n    # Communication hub\n    'CommunicationManager',\n"
                       "    'create_communication_tables',\n]", 1),
            encoding="utf-8")
        (old_pkg / "__init__.py").write_text(
            base.package_shim(base.dotted(new_init)), encoding="utf-8")
    for dead in DEAD:
        target = ROOT / "remove" / dead.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dead), str(target))
    catalogue = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
    for rule in catalogue["rules"]:
        rule["glob"] = CLASSIFICATION_RENAMES.get(rule["glob"], rule["glob"])
    CLASSIFICATION.write_text(json.dumps(catalogue, indent=2) + "\n", encoding="utf-8")
    files, statements, problems = base.rewrite(prefixes, apply=True,
                                               paths=paths + [d for _, d in moves])
    MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    MAP_FILE.write_text(json.dumps(path_map, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"moved {len(moves)} modules and {len(data)} data files; {len(DEAD)} dead package(s) "
          f"to remove/; rewrote {statements} references in {files} files; "
          f"{len(problems)} to fix by hand; path map: {MAP_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
