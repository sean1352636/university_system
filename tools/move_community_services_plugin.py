#!/usr/bin/env python3
"""Move church management into the ``community_services`` university plugin.

Like campus commerce, the community-services plugin was a ``plugin.json`` and
nothing else. Its code is the church management app:

=========================================================  =============================
from                                                       to (under the plugin package)
=========================================================  =============================
``domains/operations/interfaces/gui/campus/community/``   ``interfaces/gui/``
``shell/cli/services/church_cli.py``                       ``interfaces/cli/church_cli.py``
``plugins/community-services/plugin.json``                 ``plugin.json``
=========================================================  =============================

Old paths keep working exactly as in ``move_campus_commerce_plugin.py`` (whose
rewrite and packaging helpers this reuses): modules leave identity aliases,
package ``__init__`` files leave name mirrors, both marked ``# layout-shim:``.
Imports and quoted module names in ``src/`` and ``tests/`` are rewritten.

The ``api/university/pastoral/routes/community/`` scaffolds are *not* moved:
they are placeholders for student-life routes (clubs, elections, social
matching), not community services.

Usage::

    python tools/move_community_services_plugin.py            # dry run
    python tools/move_community_services_plugin.py --apply
"""

from __future__ import annotations

import argparse
import fnmatch
import importlib.util
import json
import shutil
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "move_campus_commerce_plugin", ROOT / "tools" / "move_campus_commerce_plugin.py")
_commerce = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_commerce)

SRC = _commerce.SRC
PKG = _commerce.PKG
U = _commerce.U
SHIM_MARKER = _commerce.SHIM_MARKER
dotted = _commerce.dotted
rewrite = _commerce.rewrite
ensure_package = _commerce.ensure_package

PLUGIN = U / "plugins" / "community_services"
OLD_MANIFEST_DIR = U / "plugins" / "community-services"
CLASSIFICATION = _commerce.CLASSIFICATION
MAP_FILE = ROOT / "var" / "backups" / "maintenance" / "community-services-plugin-path-map.json"

DIR_MOVES = [
    (U / "domains/operations/interfaces/gui/campus/community", PLUGIN / "interfaces/gui"),
]
FILE_MOVES = [
    (U / "shell/cli/services/church_cli.py", PLUGIN / "interfaces/cli/church_cli.py"),
]


def plan():
    moves, data_files, prefixes = [], [], {}
    for old_dir, new_dir in DIR_MOVES:
        prefixes[dotted(old_dir / "__init__.py")] = dotted(new_dir / "__init__.py")
        for path in sorted(old_dir.rglob("*")):
            if "__pycache__" in path.parts or path.is_dir():
                continue
            dest = new_dir / path.relative_to(old_dir)
            (moves if path.suffix == ".py" else data_files).append((path, dest))
    for old, new in FILE_MOVES:
        moves.append((old, new))
        prefixes[dotted(old)] = dotted(new)
    return moves, prefixes, data_files


def module_shim(new_module: str) -> str:
    return (
        f'"""Moved to ``{new_module}`` (community services plugin).\n'
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


def package_shim(new_package: str) -> str:
    return (
        f'"""Moved to ``{new_package}`` (community services plugin).\n'
        "\n"
        "A mirror, not an alias: an aliased package would resolve this package's\n"
        "submodules through the new ``__path__`` and load each one a second time.\n"
        "Submodules are aliased individually; this copies the package's names.\n"
        '"""\n'
        f"{SHIM_MARKER} {new_package}\n"
        "import importlib as _importlib\n"
        "\n"
        f'_new = _importlib.import_module("{new_package}")\n'
        "globals().update({k: v for k, v in vars(_new).items()\n"
        '                  if not (k.startswith("__") and k.endswith("__"))})\n'
        "del _importlib, _new\n"
    )


def add_classification_rule(sample_old_rel: str) -> str:
    data = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
    rules = data["rules"]
    current = next((r["classification"] for r in rules
                    if fnmatch.fnmatch(sample_old_rel, r["glob"])), "demo")
    if not any(r["glob"] == "plugins/community_services/**" for r in rules):
        catch_all = next((i for i, r in enumerate(rules) if r["glob"] == "**"), len(rules))
        rules.insert(catch_all, {"glob": "plugins/community_services/**",
                                 "classification": current})
    CLASSIFICATION.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return current


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    moves, prefixes, data_files = plan()
    missing = [str(s) for s, _ in moves if not s.exists()]
    collisions = [str(d) for _, d in moves + data_files if d.exists()]
    print(f"python modules to move: {len(moves)} | data files: {len(data_files)} | "
          f"package prefixes: {len(prefixes)}")
    if missing or collisions or not (OLD_MANIFEST_DIR / "plugin.json").exists():
        print("Refusing:", *(missing + collisions)[:10], sep="\n  ")
        return 1
    changed, left = rewrite(prefixes, apply=False)
    print(f"references to rewrite: {changed} | left to aliases: {len(left)}")
    for line in left[:20]:
        print("  alias:", line)
    if not args.apply:
        print("\nDry run. Re-run with --apply.")
        return 0

    from education_system import paths
    dest = paths.maintenance_backup_dir("community-services-plugin", create=True)
    archive = dest / "community_services_sources.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for src_path, _ in moves + data_files:
            tar.add(src_path, arcname=str(src_path.relative_to(ROOT)))
        for p in (OLD_MANIFEST_DIR / "plugin.json", CLASSIFICATION):
            tar.add(p, arcname=str(p.relative_to(ROOT)))
    print("backup:", archive)

    sample = moves[0][0].relative_to(U).as_posix()
    created: list[Path] = []
    path_map = {}
    for src_path, dest_path in moves:
        ensure_package(dest_path.parent, created)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dest_path))
        shim = package_shim if src_path.name == "__init__.py" else module_shim
        src_path.write_text(shim(dotted(dest_path)), encoding="utf-8")
        path_map[src_path.relative_to(SRC / PKG).as_posix()] = dest_path.relative_to(SRC / PKG).as_posix()
    for src_path, dest_path in data_files:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dest_path))
    for sub in (PLUGIN / "interfaces", PLUGIN / "interfaces" / "cli"):
        ensure_package(sub, created)
    (PLUGIN / "__init__.py").write_text(
        '"""Community services — an optional university plugin.\n'
        "\n"
        "Faith and community services run on campus but outside the education core.\n"
        "Today that is church management: members, donations, prayer requests,\n"
        "sermons, announcements, volunteers, attendance, small groups and expenses\n"
        "(``interfaces/gui/church_management``), plus its terminal app\n"
        "(``interfaces/cli/church_cli.py``).\n"
        "\n"
        "``plugin.json`` declares capabilities and data handling for\n"
        "``systems/university/plugins/registry.py``. The ``campus.community-events``\n"
        "capability it lists has no implementation yet.\n"
        '"""\n', encoding="utf-8")
    shutil.move(str(OLD_MANIFEST_DIR / "plugin.json"), str(PLUGIN / "plugin.json"))
    OLD_MANIFEST_DIR.rmdir()
    classification = add_classification_rule(sample)
    changed, left = rewrite(prefixes, apply=True)
    MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    MAP_FILE.write_text(json.dumps(path_map, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"moved {len(moves)} modules; created {len(created)} __init__.py; rewrote {changed} "
          f"references; {len(left)} left to aliases; classification '{classification}'; "
          f"path map: {MAP_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
