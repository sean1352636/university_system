#!/usr/bin/env python3
"""Ratchet the program's file and directory layout so it can only improve.

Every rule below describes a layout problem the codebase already has. Today's
instances are recorded in ``tools/layout_baseline.json``; the check fails when

* a **new** instance appears (a new file, import, directory or oversized file),
  or
* a baselined instance has been **fixed** but is still listed — run
  ``--prune`` so the baseline shrinks with the code and cannot be re-used.

Rules
-----
Domain layers of every system except the university (whose slices are already
ratcheted per domain by ``tests/unit/systems/university/domains/``):

``domain-forbidden-import``
    ``domain/`` imports tkinter, flask or sqlite3.
``domain-adapter-import``
    ``domain/`` imports an inbound adapter: ``interfaces``, ``shell``, the API
    package or ``platform.delivery``.
``delivery-module-in-domain``
    a ``*_views.py`` or ``*_cli.py`` module lives under ``domain/``.

Everything under ``src/education_system`` (generated migrations excepted):

``oversize``
    more than ``MAX_LINES`` lines. A baselined file may grow by at most
    ``SIZE_HEADROOM`` lines over its recorded size.
``parts-dir``
    a ``*_parts`` directory (leftover of automatic file splitting).
``grab-bag-module``
    a ``misc.py`` or ``_imports.py`` module.
``too-deep``
    a module more than ``MAX_DEPTH`` path components below ``src/education_system``.
``layout-shim``
    an alias module left at an old path by a layout move (marked
    ``# layout-shim:``). Shims are exempt from the other rules — they only
    forward to the real module — and are recorded so they can only disappear.

Usage::

    python tools/check_layout.py            # check (CI)
    python tools/check_layout.py --prune    # drop fixed entries, lower size ceilings
    python tools/check_layout.py --init     # write the first baseline (refuses to overwrite)
    python tools/check_layout.py --accept-shims   # after a planned move: record its new
                                                  # aliases (no other rule ever grows)
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "education_system"
BASELINE = ROOT / "tools" / "layout_baseline.json"

MAX_LINES = 2000
SIZE_HEADROOM = 50
MAX_DEPTH = 12
FORBIDDEN_IN_DOMAIN = ("tkinter", "flask", "sqlite3")
GRAB_BAG_NAMES = ("misc.py", "_imports.py")
SHIM_MARKER = "# layout-shim:"
DOMAIN_RULE_EXCLUDED_SYSTEMS = ("university",)

SET_RULES = (
    "domain-forbidden-import",
    "domain-adapter-import",
    "delivery-module-in-domain",
    "parts-dir",
    "grab-bag-module",
    "too-deep",
    "layout-shim",
)
RULES = SET_RULES + ("oversize",)

RULE_HELP = {
    "domain-forbidden-import":
        "domain/ must not import tkinter, flask or sqlite3 — screens belong in "
        "interfaces/gui, SQL in infrastructure/.",
    "domain-adapter-import":
        "domain/ must not import interfaces/, shell/, the API or platform.delivery "
        "— dependencies point inward.",
    "delivery-module-in-domain":
        "*_views.py and *_cli.py are delivery code — put them under "
        "interfaces/gui/ or interfaces/cli/.",
    "oversize":
        f"files over {MAX_LINES} lines — split before adding more "
        f"(a baselined file may grow by at most {SIZE_HEADROOM} lines).",
    "parts-dir":
        "*_parts directories are auto-split leftovers — give the pieces real "
        "module names in a real package.",
    "grab-bag-module":
        "misc.py / _imports.py collect unrelated code — name modules for what "
        "they hold.",
    "too-deep":
        f"modules more than {MAX_DEPTH} levels below src/education_system — flatten.",
    "layout-shim":
        "alias modules left at old paths by a layout move — new ones are recorded "
        "with --accept-shims; delete them once nothing imports the old path.",
}


# ---------------------------------------------------------------------------
# collection
# ---------------------------------------------------------------------------

def _imports(path: Path) -> list[str]:
    """Every module *path* imports, including inside functions."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"),
                         filename=str(path))
    except SyntaxError:
        return []
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            found.append(node.module)
    return found


def _is_adapter(module: str) -> bool:
    return (
        ".interfaces." in module
        or module.endswith(".interfaces")
        or ".shell." in module
        or module.startswith("education_system.api")
        or module.startswith("education_system.platform.delivery")
    )


def _is_shim(path: Path) -> bool:
    try:
        return SHIM_MARKER in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def _domain_roots(src: Path):
    systems = src / "systems"
    if not systems.is_dir():
        return
    for system in sorted(systems.iterdir()):
        if (not system.is_dir() or system.name.startswith(("_", "."))
                or system.name in DOMAIN_RULE_EXCLUDED_SYSTEMS):
            continue
        domain = system / "domain"
        if domain.is_dir():
            yield domain
        # Areas already moved into vertical slices keep their rules
        # under domains/<area>/domain/.
        slices = system / "domains"
        if slices.is_dir():
            for area in sorted(slices.iterdir()):
                if (area / "domain").is_dir():
                    yield area / "domain"


def collect(src: Path = SRC) -> dict:
    """Every current instance of every rule, keyed by rule name."""
    found: dict = {rule: set() for rule in SET_RULES}
    found["oversize"] = {}

    for domain in _domain_roots(src):
        for path in domain.rglob("*.py"):
            if _is_shim(path):
                continue
            rel = path.relative_to(src).as_posix()
            if path.name.endswith(("_views.py", "_cli.py")):
                found["delivery-module-in-domain"].add(rel)
            for module in _imports(path):
                top = module.split(".")[0]
                if top in FORBIDDEN_IN_DOMAIN:
                    found["domain-forbidden-import"].add(f"{rel} -> {top}")
                if _is_adapter(module):
                    found["domain-adapter-import"].add(f"{rel} -> {module}")

    for path in src.rglob("*.py"):
        rel = path.relative_to(src).as_posix()
        if rel.startswith("migrations/versions/"):
            continue  # generated by Alembic
        if _is_shim(path):
            found["layout-shim"].add(rel)
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").count("\n") + 1
        if lines > MAX_LINES:
            found["oversize"][rel] = lines
        if path.name in GRAB_BAG_NAMES:
            found["grab-bag-module"].add(rel)
        if len(path.relative_to(src).parts) > MAX_DEPTH:
            found["too-deep"].add(rel)

    for path in src.rglob("*_parts"):
        if not path.is_dir():
            continue
        modules = [m for m in path.rglob("*.py")]
        if modules and all(_is_shim(m) for m in modules):
            continue  # left behind by a move; its aliases are recorded as layout-shim
        found["parts-dir"].add(path.relative_to(src).as_posix())
    return found


# ---------------------------------------------------------------------------
# baseline
# ---------------------------------------------------------------------------

def load_baseline(path: Path = BASELINE) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))["rules"]
    baseline = {rule: set(data.get(rule, [])) for rule in SET_RULES}
    baseline["oversize"] = dict(data.get("oversize", {}))
    return baseline


def write_baseline(found: dict, path: Path = BASELINE) -> None:
    rules = {rule: sorted(found[rule]) for rule in SET_RULES}
    rules["oversize"] = dict(sorted(found["oversize"].items()))
    payload = {
        "_about": ("Known layout problems, recorded so they cannot grow. "
                   "See tools/check_layout.py. Only ever shrink this file: "
                   "run `python tools/check_layout.py --prune` after fixing one."),
        "limits": {"max_lines": MAX_LINES, "size_headroom": SIZE_HEADROOM,
                   "max_depth": MAX_DEPTH},
        "rules": rules,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def compare(found: dict, baseline: dict) -> tuple[dict, dict]:
    """``(new, stale)``: each maps rule -> sorted list of human-readable entries."""
    new: dict = {}
    stale: dict = {}
    for rule in SET_RULES:
        added = sorted(found[rule] - baseline[rule])
        fixed = sorted(baseline[rule] - found[rule])
        if added:
            new[rule] = added
        if fixed:
            stale[rule] = fixed

    grew = []
    for rel, lines in sorted(found["oversize"].items()):
        ceiling = baseline["oversize"].get(rel)
        if ceiling is None:
            grew.append(f"{rel} ({lines} lines)")
        elif lines > ceiling + SIZE_HEADROOM:
            grew.append(f"{rel} ({lines} lines, recorded {ceiling})")
    if grew:
        new["oversize"] = grew

    shrunk = sorted(f"{rel} (now under {MAX_LINES} lines)"
                    for rel in baseline["oversize"] if rel not in found["oversize"])
    if shrunk:
        stale["oversize"] = shrunk
    return new, stale


def pruned(found: dict, baseline: dict) -> dict:
    """The baseline minus fixed entries, with size ceilings lowered. Never adds."""
    result = {rule: baseline[rule] & found[rule] for rule in SET_RULES}
    result["oversize"] = {
        rel: min(ceiling, found["oversize"][rel])
        for rel, ceiling in baseline["oversize"].items() if rel in found["oversize"]
    }
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _report(title: str, entries: dict, stream) -> None:
    print(title, file=stream)
    for rule in RULES:
        if rule not in entries:
            continue
        print(f"\n  [{rule}] {RULE_HELP[rule]}", file=stream)
        for entry in entries[rule][:50]:
            print(f"    - {entry}", file=stream)
        if len(entries[rule]) > 50:
            print(f"    … and {len(entries[rule]) - 50} more", file=stream)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--init", action="store_true",
                       help="write the first baseline (refuses to overwrite)")
    group.add_argument("--prune", action="store_true",
                       help="remove fixed entries and lower size ceilings")
    group.add_argument("--accept-shims", action="store_true",
                       help="prune, then record new layout-shim aliases only")
    parser.add_argument("--src", type=Path, default=SRC)
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    args = parser.parse_args(argv)

    found = collect(args.src)

    if args.init:
        if args.baseline.exists():
            print(f"{args.baseline} already exists; use --prune to shrink it.",
                  file=sys.stderr)
            return 1
        write_baseline(found, args.baseline)
        counts = ", ".join(f"{r}={len(found[r])}" for r in RULES)
        print(f"Wrote {args.baseline} ({counts})")
        return 0

    baseline = load_baseline(args.baseline)
    new, stale = compare(found, baseline)

    if args.accept_shims:
        result = pruned(found, baseline)
        added = found["layout-shim"] - baseline["layout-shim"]
        result["layout-shim"] = found["layout-shim"]
        write_baseline(result, args.baseline)
        removed = sum(len(v) for v in stale.values())
        print(f"Recorded {len(added)} new shim(s); pruned {removed} fixed entr"
              f"{'y' if removed == 1 else 'ies'} from {args.baseline}.")
        new.pop("layout-shim", None)
        if new:
            _report("New layout violations (not added to the baseline):", new, sys.stderr)
            return 1
        return 0

    if args.prune:
        write_baseline(pruned(found, baseline), args.baseline)
        removed = sum(len(v) for v in stale.values())
        print(f"Pruned {removed} fixed entr{'y' if removed == 1 else 'ies'} "
              f"from {args.baseline}.")
        if new:
            _report("New layout violations (not added to the baseline):", new, sys.stderr)
            return 1
        return 0

    if new:
        _report("Layout check failed — new violations:", new, sys.stderr)
    if stale:
        _report("Layout check failed — fixed but still in the baseline "
                "(run `python tools/check_layout.py --prune`):", stale, sys.stderr)
    if new or stale:
        return 1
    total = sum(len(baseline[r]) for r in RULES)
    print(f"Layout check passed ({total} known issues, none new).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
