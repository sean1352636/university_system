#!/usr/bin/env python3
"""Move K-12 delivery modules out of ``domain/`` into ``interfaces/``.

For nursery, primary, secondary and sixth_form:

* ``domain/<path>/<name>_views.py`` -> ``interfaces/gui/<path>/<name>_views.py``
* ``domain/<path>/<name>_cli.py``   -> ``interfaces/cli/<path>/<name>_cli.py``

Each old path keeps a ``sys.modules`` alias, so the old dotted name *is* the new
module object: ``import``, ``importlib.import_module``, ``mock.patch`` and
``monkeypatch.setattr`` on the old name all keep acting on the real module.
A plain ``from new import *`` re-export would break the last two.

Import statements in ``src/`` that name a moved module are rewritten to the
new path. Lines that mix moved and unmoved names are left alone (the alias
serves them) and listed in the report.

Usage::

    python tools/move_k12_delivery_modules.py            # dry run
    python tools/move_k12_delivery_modules.py --apply
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_PARENT = ROOT / "src"
SYSTEMS = ROOT / "src" / "education_system" / "systems"
TARGET_SYSTEMS = ("nursery", "primary", "secondary", "sixth_form")
SHIM_MARKER = "# layout-shim:"

sys.path.insert(0, str(SRC_PARENT))


def _dotted(path: Path) -> str:
    return ".".join(path.with_suffix("").relative_to(SRC_PARENT).parts)


def plan() -> list[tuple[Path, Path]]:
    moves = []
    for system in TARGET_SYSTEMS:
        domain = SYSTEMS / system / "domain"
        for path in sorted(domain.rglob("*.py")):
            if path.read_text(encoding="utf-8", errors="replace").find(SHIM_MARKER) != -1:
                continue  # already an alias from an earlier run
            if path.name.endswith("_views.py"):
                kind = "gui"
            elif path.name.endswith("_cli.py"):
                kind = "cli"
            else:
                continue
            dest = SYSTEMS / system / "interfaces" / kind / path.relative_to(domain)
            moves.append((path, dest))
    return moves


def shim_text(new_module: str) -> str:
    return (
        f'"""Moved to ``{new_module}``.\n'
        "\n"
        "Delivery code (screens and terminal menus) lives under ``interfaces/``.\n"
        "This alias keeps the old import path working: the old name *is* the new\n"
        "module object, so ``mock.patch`` and ``monkeypatch`` targets still act on\n"
        "the real module. Delete it once nothing imports the old path.\n"
        '"""\n'
        f"{SHIM_MARKER} {new_module}\n"
        "import importlib as _importlib\n"
        "import sys as _sys\n"
        "\n"
        f'_sys.modules[__name__] = _importlib.import_module("{new_module}")\n'
    )


_FROM = re.compile(r"^(?P<indent>\s*)from\s+(?P<mod>[\w.]+)\s+import\s+(?P<names>.+?)\s*(?P<comment>#.*)?$")
_SYSTEMS_ALT = "|".join(TARGET_SYSTEMS)
_MENTIONS = re.compile(rf"education_system\.systems\.(?:{_SYSTEMS_ALT})\.domain\.")
_QUOTED = re.compile(rf"""(["'])(education_system\.systems\.(?:{_SYSTEMS_ALT})\.domain\.[\w.]+)\1""")
_IMPORT = re.compile(r"^(?P<indent>\s*)import\s+(?P<mod>[\w.]+)(?P<rest>(\s+as\s+\w+)?\s*(#.*)?)$")


def rewrite_imports(mapping: dict[str, str], apply: bool) -> tuple[int, list[str]]:
    """Rewrite single-line import statements naming moved modules."""
    changed_lines = 0
    left_for_alias: list[str] = []
    for path in sorted((SRC_PARENT / "education_system").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if SHIM_MARKER in text or not _MENTIONS.search(text):
            continue
        lines = text.split("\n")
        dirty = False
        for i, line in enumerate(lines):
            m = _FROM.match(line)
            if m:
                mod = m.group("mod")
                names_part = m.group("names")
                if mod in mapping:
                    lines[i] = line.replace(f"from {mod} import", f"from {mapping[mod]} import", 1)
                    changed_lines += 1
                    dirty = True
                    continue
                if names_part.strip().startswith("("):
                    continue  # multi-line; alias covers it
                names = [n.strip() for n in names_part.split(",")]
                bare = [n.split(" as ")[0].strip() for n in names]
                moved = [f"{mod}.{n}" in mapping for n in bare]
                if any(moved):
                    targets = {mapping[f"{mod}.{n}"].rsplit(".", 1)[0]
                               for n, hit in zip(bare, moved) if hit}
                    if all(moved) and len(targets) == 1:
                        lines[i] = line.replace(f"from {mod} import", f"from {targets.pop()} import", 1)
                        changed_lines += 1
                        dirty = True
                    else:
                        left_for_alias.append(f"{path.relative_to(ROOT)}:{i + 1}: {line.strip()}")
                continue
            m = _IMPORT.match(line)
            if m and m.group("mod") in mapping:
                mod = m.group("mod")
                if not m.group("rest").strip().startswith("as"):
                    # `import a.b.c` binds `a` and is used as a.b.c.x: rewriting
                    # would change every use site. The alias serves it.
                    left_for_alias.append(f"{path.relative_to(ROOT)}:{i + 1}: {line.strip()}")
                    continue
                lines[i] = line.replace(f"import {mod}", f"import {mapping[mod]}", 1)
                changed_lines += 1
                dirty = True
        for i, line in enumerate(lines):
            if line.lstrip().startswith(("from ", "import ")):
                continue

            def _swap(match):
                return f"{match.group(1)}{mapping[match.group(2)]}{match.group(1)}"

            updated, count = _QUOTED.subn(
                lambda m: _swap(m) if m.group(2) in mapping else m.group(0), line)
            if count and updated != line:
                lines[i] = updated
                changed_lines += 1
                dirty = True
        if dirty and apply:
            path.write_text("\n".join(lines), encoding="utf-8")
    return changed_lines, left_for_alias


def backup(label: str) -> Path:
    from education_system import paths
    dest = paths.maintenance_backup_dir(label, create=True)
    archive = dest / "k12_domain_and_interfaces.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for system in TARGET_SYSTEMS:
            for part in ("domain", "interfaces", "cli_main.py", "gui_main.py", "menu.py"):
                p = SYSTEMS / system / part
                if p.exists():
                    tar.add(p, arcname=str(p.relative_to(ROOT)))
    return archive


def ensure_packages(dest: Path, system: str) -> list[Path]:
    created = []
    stop = SYSTEMS / system / "interfaces"
    d = dest.parent
    while d != stop and stop in d.parents:
        init = d / "__init__.py"
        if not init.exists():
            init.parent.mkdir(parents=True, exist_ok=True)
            init.write_text("", encoding="utf-8")
            created.append(init)
        d = d.parent
    return created


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--apply", action="store_true")
    args = p.parse_args(argv)

    moves = plan()
    collisions = [d for _, d in moves if d.exists()]
    mapping = {_dotted(src): _dotted(dst) for src, dst in moves}
    by_system = {}
    for src, dst in moves:
        key = (src.relative_to(SYSTEMS).parts[0], "gui" if "/gui/" in dst.as_posix() else "cli")
        by_system[key] = by_system.get(key, 0) + 1
    print(f"{len(moves)} module(s) to move:")
    for (system, kind), n in sorted(by_system.items()):
        print(f"  {system:11} {kind}: {n}")
    if collisions:
        print("Refusing: destinations already exist:", *collisions[:10], sep="\n  ")
        return 1

    changed, left = rewrite_imports(mapping, apply=False)
    print(f"import/string references to rewrite: {changed}; left to aliases: {len(left)}")
    if not args.apply:
        for line in left[:20]:
            print("  alias:", line)
        print("\nDry run. Re-run with --apply.")
        return 0

    archive = backup("k12-delivery-modules-to-interfaces")
    print(f"backup: {archive}")
    created = []
    for src, dst in moves:
        system = src.relative_to(SYSTEMS).parts[0]
        created += ensure_packages(dst, system)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        src.write_text(shim_text(_dotted(dst)), encoding="utf-8")
    changed, left = rewrite_imports(mapping, apply=True)
    print(f"moved {len(moves)}; created {len(created)} __init__.py; "
          f"rewrote {changed} reference(s); {len(left)} left to aliases")
    for line in left:
        print("  alias:", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
