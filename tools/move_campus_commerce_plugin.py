#!/usr/bin/env python3
"""Move campus commerce code into the ``campus_commerce`` university plugin.

Until now the plugin was a ``plugin.json`` and nothing else; its code was spread
over the Operations slice, the shell, services, schemas and the API. This moves
it into one package, ``systems/university/plugins/campus_commerce/``:

=====================================================  ==============================
from                                                   to (under the plugin package)
=====================================================  ==============================
``domains/operations/domain/commerce/``                ``domain/``
``domains/operations/interfaces/gui/commerce/``        ``interfaces/gui/``
``domains/operations/interfaces/cli/commerce/``        ``interfaces/cli/``
17 commerce CLIs in ``shell/cli/services/``            ``interfaces/cli/services/``
``shell/gui/services/charity_shop_gui/``               ``interfaces/gui/charity_shop_gui/``
``shell/gui/main/features/commerce_facilities_gui.py`` ``interfaces/gui/``
``shell/cli/menus/commerce.py``                        ``interfaces/cli/commerce_menu.py``
``services/bus/{commerce,restaurant}_bus.py``          ``services/``
``.../admin_support_schemas_parts/init_commerce_tables.py`` ``infrastructure/``
14 commerce route modules in ``api/university/operations/`` ``api/``
``plugins/campus-commerce/plugin.json``                ``plugin.json``
=====================================================  ==============================

Old paths keep working:

* a moved **module** leaves an identity alias (``sys.modules[__name__] = new``),
  so ``mock.patch``/``monkeypatch`` on the old name still act on the real code;
* a moved **package** ``__init__`` leaves a *mirror* that copies the new
  package's names. It cannot be an alias: Python would then resolve the old
  package's submodules through the new ``__path__`` and load each one twice.

Both are marked ``# layout-shim:`` for ``tools/check_layout.py``.

Import lines and quoted module names in ``src/`` and ``tests/`` are rewritten to
the new paths. The university ``test_*_boundaries.py`` allow-lists are left for
a follow-up recomputation. Behaviour is unchanged: nothing is gated behind
``EDUCATION_UNIVERSITY_PLUGINS``.

Usage::

    python tools/move_campus_commerce_plugin.py            # dry run
    python tools/move_campus_commerce_plugin.py --apply
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PKG = "education_system"
U = SRC / PKG / "systems" / "university"
API_OPS = SRC / PKG / "api" / "university" / "operations"
PLUGIN = U / "plugins" / "campus_commerce"
OLD_MANIFEST_DIR = U / "plugins" / "campus-commerce"
SCAFFOLDS = API_OPS / "routes" / "commerce"
CLASSIFICATION = ROOT / "docs" / "university" / "MODULE_CLASSIFICATION.json"
MAP_FILE = ROOT / "var" / "backups" / "maintenance" / "campus-commerce-plugin-path-map.json"
SHIM_MARKER = "# layout-shim:"

sys.path.insert(0, str(SRC))

SHELL_CLI = U / "shell" / "cli" / "services"
DIR_MOVES = [
    (U / "domains/operations/domain/commerce", PLUGIN / "domain"),
    (U / "domains/operations/interfaces/gui/commerce", PLUGIN / "interfaces/gui"),
    (U / "domains/operations/interfaces/cli/commerce", PLUGIN / "interfaces/cli"),
    *[(SHELL_CLI / name, PLUGIN / "interfaces/cli/services" / name) for name in (
        "barber_cli_parts", "betting_shop_cli", "butcher_cli_parts", "cafe",
        "charity_shop_cli", "cinema_cli", "nailbar_cli")],
    (U / "shell/gui/services/charity_shop_gui", PLUGIN / "interfaces/gui/charity_shop_gui"),
]
FILE_MOVES = [
    *[(SHELL_CLI / name, PLUGIN / "interfaces/cli/services" / name) for name in (
        "barber_cli.py", "barber_cli_shared.py", "bar_cli.py", "butcher_cli.py",
        "butcher_cli_shared.py", "cafe_system_cli.py", "carrental_cli.py", "gym_cli.py",
        "music_shop_cli.py", "phone_shop_cli.py")],
    (U / "shell/gui/main/features/commerce_facilities_gui.py",
     PLUGIN / "interfaces/gui/commerce_facilities_gui.py"),
    (U / "shell/cli/menus/commerce.py", PLUGIN / "interfaces/cli/commerce_menu.py"),
    (U / "services/bus/commerce_bus.py", PLUGIN / "services/commerce_bus.py"),
    (U / "services/bus/restaurant_bus.py", PLUGIN / "services/restaurant_bus.py"),
    (U / "infrastructure/database/schemas/admin_support_schemas_parts/init_commerce_tables.py",
     PLUGIN / "infrastructure/init_commerce_tables.py"),
    *[(API_OPS / f"{name}_routes.py", PLUGIN / "api" / f"{name}_routes.py") for name in (
        "barber", "betting", "butcher", "carrental", "cinema", "commerce", "dining", "gym",
        "marketplace", "musicshop", "nailbar", "phoneshop", "printing", "textbooks")],
]

#: Folder-climbing paths in moved code that were already wrong and would move
#: further off target. Applied to the file at its *new* location.
PATH_FIXES = {
    "interfaces/gui/cinema/cinema_gui/database.py": [(
        'LOGS_DIR = os.path.join(os.path.dirname(__file__), "../../../../../logs")',
        "from education_system.paths import UNIVERSITY_LOG_DIR as _UNIVERSITY_LOG_DIR\n"
        "LOGS_DIR = str(_UNIVERSITY_LOG_DIR)",
    )],
    "interfaces/gui/cinema/cinema_gui/reports/audit_log.py": [(
        "logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', '..', '..', 'logs')",
        "from education_system.paths import UNIVERSITY_LOG_DIR\n"
        "    logs_dir = str(UNIVERSITY_LOG_DIR)",
    )],
    "interfaces/gui/charity_shop_gui/_imports.py": [(
        'EMAIL_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent.parent / "templates" / "email"',
        "from education_system.paths import UNIVERSITY_EMAIL_TEMPLATES_DIR as EMAIL_TEMPLATES_DIR",
    )],
    "interfaces/gui/shop_management_gui/main_gui.py": [(
        "                    project_root = current_file\n"
        "                    for _ in range(8):\n"
        "                        project_root = os.path.dirname(project_root)\n",
        "                    from education_system.paths import SRC_ROOT\n"
        "                    project_root = str(SRC_ROOT)\n",
    )],
    "infrastructure/init_commerce_tables.py": [(
        "from .. import admin_support_schemas_shared",
        "from education_system.systems.university.infrastructure.database.schemas "
        "import admin_support_schemas_shared",
    )],
}


def dotted(path: Path) -> str:
    parts = list(path.with_suffix("").relative_to(SRC).parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def plan():
    """(file moves, prefix map old->new dotted, non-python files)."""
    moves: list[tuple[Path, Path]] = []
    data_files: list[tuple[Path, Path]] = []
    prefixes: dict[str, str] = {}
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
        f'"""Moved to ``{new_module}`` (campus commerce plugin).\n'
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
        f'"""Moved to ``{new_package}`` (campus commerce plugin).\n'
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


_TOKEN = re.compile(r"\beducation_system(?:\.\w+)+")
_FROM = re.compile(r"^(\s*)from\s+([\w.]+)\s+import\s+(.+?)\s*(#.*)?$")


def _map_name(name: str, prefixes: dict[str, str]) -> str | None:
    best = None
    for old in prefixes:
        if name == old or name.startswith(old + "."):
            if best is None or len(old) > len(best):
                best = old
    return None if best is None else prefixes[best] + name[len(best):]


def rewrite(prefixes: dict[str, str], apply: bool) -> tuple[int, list[str]]:
    changed = 0
    left: list[str] = []
    roots = [SRC / PKG, ROOT / "tests"]
    needle = re.compile("|".join(re.escape(k) for k in sorted(prefixes, key=len, reverse=True)))
    parents = {k.rsplit(".", 1)[0] for k in prefixes}
    parent_needle = re.compile(r"from\s+(" + "|".join(re.escape(p) for p in parents) + r")\s+import\b")
    for root in roots:
        for path in sorted(root.rglob("*.py")):
            if path.name.endswith("_boundaries.py"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if SHIM_MARKER in text or not (needle.search(text) or parent_needle.search(text)):
                continue
            lines = text.split("\n")
            dirty = False
            for i, line in enumerate(lines):
                stripped = line.lstrip()
                is_import = stripped.startswith(("from ", "import "))
                m = _FROM.match(line)
                if m and not needle.search(m.group(2)) and parent_needle.search(line):
                    mod, names = m.group(2), m.group(3)
                    if names.strip().startswith("("):
                        continue
                    bare = [n.split(" as ")[0].strip() for n in names.split(",")]
                    mapped = [_map_name(f"{mod}.{n}", prefixes) for n in bare]
                    if any(mapped):
                        targets = {x.rsplit(".", 1)[0] for x in mapped if x}
                        new_names = [x.rsplit(".", 1)[1] if x else None for x in mapped]
                        renamed = any(x and x.rsplit(".", 1)[1] != n for x, n in zip(mapped, bare))
                        if all(mapped) and len(targets) == 1 and not renamed:
                            lines[i] = line.replace(f"from {mod} import", f"from {targets.pop()} import", 1)
                            changed += 1
                            dirty = True
                        else:
                            left.append(f"{path.relative_to(ROOT)}:{i + 1}: {stripped}")
                    continue
                if is_import and stripped.startswith("import ") and " as " not in stripped \
                        and needle.search(stripped):
                    left.append(f"{path.relative_to(ROOT)}:{i + 1}: {stripped}")
                    continue
                if not needle.search(line):
                    continue
                if not is_import and not re.search(r"[\"']education_system\.", line):
                    continue
                def swap(match):
                    return _map_name(match.group(0), prefixes) or match.group(0)
                if is_import:
                    new_line = _TOKEN.sub(swap, line)
                else:
                    new_line = re.sub(r"([\"'])(education_system(?:\.\w+)+)", lambda mm: mm.group(1) + (_map_name(mm.group(2), prefixes) or mm.group(2)), line)
                if new_line != line:
                    lines[i] = new_line
                    changed += 1
                    dirty = True
            if dirty and apply:
                path.write_text("\n".join(lines), encoding="utf-8")
    return changed, left


def backup() -> Path:
    from education_system import paths
    dest = paths.maintenance_backup_dir("campus-commerce-plugin", create=True)
    archive = dest / "campus_commerce_sources.tar.gz"
    moves, _, data = plan()
    extra = [OLD_MANIFEST_DIR / "plugin.json", CLASSIFICATION, SCAFFOLDS]
    with tarfile.open(archive, "w:gz") as tar:
        for src_path, _ in moves + data:
            tar.add(src_path, arcname=str(src_path.relative_to(ROOT)))
        for p in extra:
            if p.exists():
                tar.add(p, arcname=str(p.relative_to(ROOT)))
    return archive


def write_manifest() -> None:
    manifest = json.loads((OLD_MANIFEST_DIR / "plugin.json").read_text(encoding="utf-8"))
    api = f"{PKG}.systems.university.plugins.campus_commerce.api"
    manifest["capabilities"] = [
        "campus.bakery", "campus.bar", "campus.barber", "campus.betting", "campus.butcher",
        "campus.cafe", "campus.car-rental", "campus.charity-shop", "campus.cinema",
        "campus.dining", "campus.grocery", "campus.gym", "campus.marketplace",
        "campus.music-shop", "campus.nailbar", "campus.phone-shop", "campus.printing",
        "campus.restaurant", "campus.shop", "campus.takeaway", "campus.textbooks",
    ]
    manifest["routes"] = [f"{api}.{name}_routes:{name}_bp" for name in (
        "barber", "betting", "butcher", "carrental", "cinema", "commerce", "dining", "gym",
        "marketplace", "musicshop", "nailbar", "phoneshop", "printing", "textbooks")]
    (PLUGIN / "plugin.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (OLD_MANIFEST_DIR / "plugin.json").unlink()
    OLD_MANIFEST_DIR.rmdir()


def add_classification_rule() -> None:
    data = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
    rules = data["rules"]
    if not any(r["glob"] == "plugins/campus_commerce/**" for r in rules):
        catch_all = next((i for i, r in enumerate(rules) if r["glob"] == "**"), len(rules))
        rules.insert(catch_all, {"glob": "plugins/campus_commerce/**", "classification": "demo"})
    CLASSIFICATION.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def ensure_package(directory: Path, created: list[Path]) -> None:
    stop = U / "plugins"
    d = directory
    while d != stop and stop in d.parents:
        init = d / "__init__.py"
        if not init.exists():
            init.parent.mkdir(parents=True, exist_ok=True)
            init.write_text("", encoding="utf-8")
            created.append(init)
        d = d.parent


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    moves, prefixes, data_files = plan()
    missing = [str(s) for s, _ in moves if not s.exists()]
    collisions = [str(d) for _, d in moves + data_files if d.exists()]
    fix_targets = [PLUGIN / rel for rel in PATH_FIXES]
    print(f"python modules to move: {len(moves)} | data files: {len(data_files)} | "
          f"package prefixes: {len(prefixes)}")
    if missing or collisions:
        print("Refusing:", *(missing + collisions)[:10], sep="\n  ")
        return 1
    new_by_old = {s: d for s, d in moves}
    unfound_fixes = []
    for rel, fixes in PATH_FIXES.items():
        source = next((s for s, d in moves if d == PLUGIN / rel), None)
        text = source.read_text(encoding="utf-8") if source else ""
        for old, _ in fixes:
            if old not in text:
                unfound_fixes.append(f"{rel}: {old[:60]}")
    if unfound_fixes:
        print("Refusing: path fixes no longer match:", *unfound_fixes, sep="\n  ")
        return 1
    changed, left = rewrite(prefixes, apply=False)
    print(f"references to rewrite: {changed} | left to aliases: {len(left)}")
    for line in left[:25]:
        print("  alias:", line)
    if not args.apply:
        print("\nDry run. Re-run with --apply.")
        return 0

    print("backup:", backup())
    created: list[Path] = []
    path_map = {}
    for src_path, dest in moves:
        ensure_package(dest.parent, created)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dest))
        if src_path.name == "__init__.py":
            src_path.write_text(package_shim(dotted(dest)), encoding="utf-8")
        else:
            src_path.write_text(module_shim(dotted(dest)), encoding="utf-8")
        path_map[src_path.relative_to(SRC / PKG).as_posix()] = dest.relative_to(SRC / PKG).as_posix()
    for src_path, dest in data_files:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dest))
    for rel, fixes in PATH_FIXES.items():
        target = PLUGIN / rel
        text = target.read_text(encoding="utf-8")
        for old, new in fixes:
            text = text.replace(old, new, 1)
        target.write_text(text, encoding="utf-8")
    ensure_package(PLUGIN / "api", created)
    for sub in ("services", "infrastructure", "api", "interfaces", "interfaces/cli/services"):
        ensure_package(PLUGIN / sub / "x", created)
    init = PLUGIN / "__init__.py"
    init.write_text(
        '"""Campus commerce — an optional university plugin.\n'
        "\n"
        "Retail and hospitality services that run on campus but are not part of the\n"
        "education core: bakery, bar, barber, betting, butcher, cafe, car rental,\n"
        "charity shop, cinema, dining, grocery, gym, marketplace, music shop, nail\n"
        "bar, phone shop, printing, restaurant, shop, takeaway and textbooks.\n"
        "\n"
        "``plugin.json`` declares its capabilities, routes and data handling for\n"
        "``systems/university/plugins/registry.py``. Layout: ``domain/``,\n"
        "``interfaces/{gui,cli}``, ``services/``, ``infrastructure/``, ``api/``.\n"
        '"""\n', encoding="utf-8")
    write_manifest()
    add_classification_rule()
    if SCAFFOLDS.exists():
        target = ROOT / "remove" / SCAFFOLDS.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(SCAFFOLDS), str(target))
    changed, left = rewrite(prefixes, apply=True)
    MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    MAP_FILE.write_text(json.dumps(path_map, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"moved {len(moves)} modules and {len(data_files)} data files; created "
          f"{len(created)} __init__.py; rewrote {changed} references; "
          f"{len(left)} left to aliases; path map: {MAP_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
