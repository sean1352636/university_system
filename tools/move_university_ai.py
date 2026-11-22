#!/usr/bin/env python3
"""Give the university's AI code one home per layer.

AI engine code was spread over ``infrastructure/ai``, ``infrastructure/ml`` and
``services/ai_features``; its menus and windows over ``shell/gui/ai``,
``shell/gui/ai_features``, ``shell/cli/ai`` and three loose ``shell/cli``
modules. This moves:

==============================================  ====================================
from (under ``systems/university/``)            to
==============================================  ====================================
``infrastructure/ai/ai_detector/``              ``shared/ai/ai_detector/``
``infrastructure/ai/university_chatbot/``       ``shared/ai/chatbot/``
``infrastructure/ai/voice_interface.py``        ``shared/ai/voice_interface.py``
``infrastructure/ml/``                          ``shared/ai/ml/``
``services/ai_features/``                       ``shared/ai/features/``
``shell/gui/ai_features/ai_features_gui.py``    ``shell/gui/ai/ai_features_gui.py``
``shell/cli/ai_tools_integration.py``           ``shell/cli/ai/tools_integration.py``
``shell/cli/chatbot_integration.py``            ``shell/cli/ai/chatbot_integration.py``
``shell/cli/chatbot_care_menu.py``              ``shell/cli/ai/chatbot_care_menu.py``
==============================================  ====================================

``shared/`` holds features several areas use, with no screens in it: screens and
menus stay in ``shell/``. AI that belongs to one feature stays with it: the
integrity detector window, Study Hub, AI grading and the assignment assistant.

Old paths keep working:

* a moved **module** leaves an identity alias (``sys.modules[__name__] = new``),
  so ``mock.patch``/``monkeypatch`` on the old name still act on the real code;
* a moved **package** ``__init__`` leaves a *mirror* that copies the new
  package's names and forwards lazy ones. It cannot be an alias: Python would
  then resolve the old package's submodules through the new ``__path__`` and
  load each one twice.

Both are marked ``# layout-shim:`` for ``tools/check_layout.py``. Imports, quoted
and written module names, and ``university/<path>`` mentions in ``src/`` and
``tests/`` are rewritten. Generated migrations are left alone.

Usage::

    python tools/move_university_ai.py            # dry run
    python tools/move_university_ai.py --apply
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
U = SRC / PKG / "systems" / "university"
MIGRATIONS = SRC / PKG / "migrations"
CLASSIFICATION = ROOT / "docs" / "university" / "MODULE_CLASSIFICATION.json"
MAP_FILE = ROOT / "var" / "backups" / "maintenance" / "university-ai-path-map.json"
SHIM_MARKER = "# layout-shim:"

sys.path.insert(0, str(SRC))

DIR_MOVES = [
    (U / "infrastructure/ai/ai_detector", U / "shared/ai/ai_detector"),
    (U / "infrastructure/ai/university_chatbot", U / "shared/ai/chatbot"),
    (U / "infrastructure/ml", U / "shared/ai/ml"),
    (U / "services/ai_features", U / "shared/ai/features"),
]
FILE_MOVES = [
    (U / "infrastructure/ai/voice_interface.py", U / "shared/ai/voice_interface.py"),
    (U / "shell/gui/ai_features/ai_features_gui.py", U / "shell/gui/ai/ai_features_gui.py"),
    (U / "shell/cli/ai_tools_integration.py", U / "shell/cli/ai/tools_integration.py"),
    (U / "shell/cli/chatbot_integration.py", U / "shell/cli/ai/chatbot_integration.py"),
    (U / "shell/cli/chatbot_care_menu.py", U / "shell/cli/ai/chatbot_care_menu.py"),
]
NEW_PACKAGES = {
    U / "shared": "Features several university areas use. No screens or menus: those\n"
                  "stay in ``shell/``; a feature's own UI stays with the feature.",
    U / "shared/ai": "University AI engines: the AI content detector, the chatbot, voice,\n"
                     "ML models and the AI-features managers. Screens and menus are in\n"
                     "``shell/gui/ai`` and ``shell/cli/ai``.",
    U / "shell/cli/ai": "AI menus for the university console: detector, chatbot, chatbot care.",
}


def dotted(path: Path) -> str:
    parts = list(path.with_suffix("").relative_to(SRC).parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def plan():
    """(python moves, data-file moves, old->new dotted prefixes)."""
    moves: list[tuple[Path, Path]] = []
    data: list[tuple[Path, Path]] = []
    prefixes: dict[str, str] = {}
    for old_dir, new_dir in DIR_MOVES:
        prefixes[dotted(old_dir / "__init__.py")] = dotted(new_dir / "__init__.py")
        for path in sorted(old_dir.rglob("*")):
            if "__pycache__" in path.parts or path.is_dir():
                continue
            dest = new_dir / path.relative_to(old_dir)
            (moves if path.suffix == ".py" else data).append((path, dest))
    for old, new in FILE_MOVES:
        moves.append((old, new))
        prefixes[dotted(old)] = dotted(new)
    return moves, data, prefixes


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


def package_shim(new_package: str) -> str:
    return (
        f'"""Moved to ``{new_package}``.\n'
        "\n"
        "A mirror, not an alias: an aliased package would resolve this package's\n"
        "submodules through the new ``__path__`` and load each one a second time.\n"
        "Submodules are aliased individually; this copies the package's names and\n"
        "forwards the ones it loads lazily.\n"
        '"""\n'
        f"{SHIM_MARKER} {new_package}\n"
        "import importlib as _importlib\n"
        "\n"
        f'_new = _importlib.import_module("{new_package}")\n'
        "globals().update({k: v for k, v in vars(_new).items()\n"
        '                  if not (k.startswith("__") and k.endswith("__"))})\n'
        'if hasattr(_new, "__all__"):\n'
        "    __all__ = list(_new.__all__)\n"
        "\n"
        "\n"
        "def __getattr__(name):\n"
        "    return getattr(_new, name)\n"
        "\n"
        "\n"
        "del _importlib\n"
    )


# --------------------------------------------------------------- rewriting

_TOKEN = re.compile(r"\beducation_system(?:\.\w+)+")
_UNI = f"{PKG}.systems.university."


def _map_name(name: str, prefixes: dict[str, str]) -> str | None:
    best = None
    for old in prefixes:
        if (name == old or name.startswith(old + ".")) and (best is None or len(old) > len(best)):
            best = old
    return None if best is None else prefixes[best] + name[len(best):]


def _import_lines(indent: str, module: str, names: list[tuple[str, str | None]]) -> list[str]:
    parts = [n if not a or a == n else f"{n} as {a}" for n, a in names]
    one = f"{indent}from {module} import {', '.join(parts)}"
    if len(one) <= 99:
        return [one]
    return [f"{indent}from {module} import ("] + [f"{indent}    {p}," for p in parts] + [f"{indent})"]


def _split_parent_import(node: ast.ImportFrom, lines: list[str], prefixes) -> list[str] | None:
    """``from parent import child`` where *child* itself moved."""
    module = node.module or ""
    if _map_name(module, prefixes):
        return None  # the token pass rewrites the module name in place
    if not any(f"{module}.{a.name}" in prefixes for a in node.names):
        return None
    span = lines[node.lineno - 1:node.end_lineno]
    indent = span[0][:node.col_offset]
    if indent.strip() or span[-1][node.end_col_offset:].strip().split("#")[0].strip():
        raise ValueError("shares a line with other code")
    comment = ""
    if "#" in "\n".join(span):
        if len(span) > 1:
            raise ValueError("comment inside a multi-line import")
        comment = "  #" + span[0].split("#", 1)[1]
    out: list[str] = []
    batch_module, batch = None, []
    for alias in node.names:
        new = prefixes.get(f"{module}.{alias.name}")
        if new:
            target, item = new.rsplit(".", 1)[0], (new.rsplit(".", 1)[1], alias.asname or alias.name)
        else:
            target, item = module, (alias.name, alias.asname)
        if target != batch_module and batch:
            out += _import_lines(indent, batch_module, batch)
            batch = []
        batch_module = target
        batch.append(item)
    out += _import_lines(indent, batch_module, batch)
    out[0] += comment
    return out


def _rewrite_text(text: str, prefixes, slash_prefixes) -> tuple[str, int, list[str]]:
    problems: list[str] = []
    lines = text.split("\n")
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return text, 0, [f"syntax error, skipped: {exc}"]
    edits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and not node.level:
            try:
                new = _split_parent_import(node, lines, prefixes)
            except ValueError as exc:
                problems.append(f"line {node.lineno}: {exc}")
                continue
            if new is not None:
                edits.append((node.lineno, node.end_lineno, new))
    for start, end, new in sorted(edits, reverse=True):
        lines[start - 1:end] = new
    changed = len(edits)
    text = "\n".join(lines)
    text, n = _TOKEN.subn(lambda m: _map_name(m.group(0), prefixes) or m.group(0), text)
    changed += n
    for old, new in slash_prefixes:
        pattern = re.compile(re.escape(old) + r"(?![\w])")
        text, n = pattern.subn(new, text)
        changed += n
    for i, line in enumerate(text.split("\n"), 1):
        for old in prefixes:
            tail = old.rsplit(".", 1)[0] + "."
            if line.rstrip().endswith((tail + '"', tail + "'")) or (old + ".{") in line:
                problems.append(f"line {i}: split or formatted module name, fix by hand")
    return text, changed, problems


def _slash_prefixes(prefixes: dict[str, str]) -> list[tuple[str, str]]:
    pairs = []
    for old, new in prefixes.items():
        if old.startswith(_UNI) and new.startswith(_UNI):
            pairs.append(("university/" + old[len(_UNI):].replace(".", "/"),
                          "university/" + new[len(_UNI):].replace(".", "/")))
    return sorted(pairs, key=lambda p: len(p[0]), reverse=True)


def candidates(moved_sources: set[Path]):
    for root in (SRC / PKG, ROOT / "tests"):
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts or MIGRATIONS in path.parents or path in moved_sources:
                continue
            yield path


def rewrite(prefixes, apply: bool, paths) -> tuple[int, int, list[str]]:
    slash = _slash_prefixes(prefixes)
    needles = list(prefixes) + [o for o, _ in slash] + \
        sorted({k.rsplit(".", 1)[0] for k in prefixes})
    files = statements = 0
    problems: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if SHIM_MARKER in text or not any(n in text for n in needles):
            continue
        new, n, issues = _rewrite_text(text, prefixes, slash)
        problems += [f"{path.relative_to(ROOT)}: {p}" for p in issues]
        if new != text:
            files += 1
            statements += n
            if apply:
                path.write_text(new, encoding="utf-8")
    return files, statements, problems


# ---------------------------------------------------------------- main


def backup(moves, data, paths) -> Path:
    """Archive the moved code and every file the rewrite may touch.

    Most of the tree is uncommitted, so git alone cannot undo this.
    """
    from education_system import paths as edu_paths
    dest = edu_paths.maintenance_backup_dir("university-ai", create=True)
    archive = dest / "university_ai_sources.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for src_path, _ in moves + data:
            tar.add(src_path, arcname=str(src_path.relative_to(ROOT)))
        for path in paths:
            tar.add(path, arcname=str(path.relative_to(ROOT)))
        tar.add(CLASSIFICATION, arcname=str(CLASSIFICATION.relative_to(ROOT)))
    return archive


def add_classification_rule() -> None:
    data = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
    rules = data["rules"]
    if not any(r["glob"] == "shared/ai/**" for r in rules):
        at = next(i for i, r in enumerate(rules) if r["glob"] == "infrastructure/ai/**")
        rules.insert(at, {"glob": "shared/ai/**", "classification": rules[at]["classification"]})
    CLASSIFICATION.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    moves, data, prefixes = plan()
    missing = [str(s) for s, _ in moves if not s.exists()]
    collisions = [str(d) for _, d in moves + data if d.exists()]
    print(f"python modules to move: {len(moves)} | data files: {len(data)} | "
          f"prefixes: {len(prefixes)}")
    if missing or collisions:
        print("Refusing:", *(missing + collisions)[:10], sep="\n  ")
        return 1
    sources = {s for s, _ in moves}
    paths = list(candidates(sources))
    files, statements, problems = rewrite(prefixes, apply=False, paths=paths + sorted(sources))
    print(f"files to rewrite: {files} | references: {statements} | to fix by hand: {len(problems)}")
    for line in problems:
        print("  hand:", line)
    if not args.apply:
        print("\nDry run. Re-run with --apply.")
        return 0

    touched = [p for p in paths if p.exists() and any(
        n in p.read_text(encoding="utf-8", errors="replace")
        for n in list(prefixes) + [o for o, _ in _slash_prefixes(prefixes)])]
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
        shim = package_shim if src_path.name == "__init__.py" else module_shim
        src_path.write_text(shim(dotted(dest)), encoding="utf-8")
        path_map[src_path.relative_to(SRC / PKG).as_posix()] = dest.relative_to(SRC / PKG).as_posix()
    for src_path, dest in data:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dest))
    add_classification_rule()
    files, statements, problems = rewrite(prefixes, apply=True,
                                          paths=paths + [d for _, d in moves])
    MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    MAP_FILE.write_text(json.dumps(path_map, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"moved {len(moves)} modules and {len(data)} data files; rewrote {statements} "
          f"references in {files} files; {len(problems)} to fix by hand; path map: {MAP_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
