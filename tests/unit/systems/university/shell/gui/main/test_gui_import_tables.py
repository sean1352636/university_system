"""The GUI launcher's lazy-import tables must point at modules that exist.

``gui_imports`` resolves feature GUIs on first attribute access instead of at
startup, which took ~20s off launch. The cost is that a wrong target is not
discovered until a user opens that feature -- and the availability flags are
optimistically ``True``, so a broken entry does not even hide the menu item.

That is exactly how these rotted: ``_LAZY_GUI`` used to build its paths from a
shared ``_GUI`` prefix, so the complete dotted path never appeared in the source
and the sweeps that repointed every other reference during the eleven
vertical-slice migrations could not see them. All 33 entries silently kept
pointing at ``interfaces/gui/<domain>/`` long after the code had moved to
``domains/<domain>/interfaces/gui/``. ``_LAUNCHER_MAP``, directly above it in
the same file, spells each target out in full and came through untouched.

The check is deliberately static: it resolves modules on disk and looks for the
symbol in the AST rather than importing anything. Importing these targets would
pull in Tkinter and the heavy optional dependencies the lazy table exists to
avoid.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.find_spec("education_system")
assert _SPEC is not None and _SPEC.origin is not None
PACKAGE = Path(_SPEC.origin).parent
UNIVERSITY = PACKAGE / "systems" / "university"
TABLE_FILE = UNIVERSITY / "shell" / "gui" / "main" / "imports" / "gui_imports.py"

#: Guards against a refactor that empties a table and passes vacuously.
MINIMUM_ENTRIES = {"_LAZY_GUI": 30, "_LAUNCHER_MAP": 15}


def _tables() -> dict[str, list[tuple[str, str, str | None]]]:
    """name -> [(key, module, symbol or None)] for each import table."""
    tree = ast.parse(TABLE_FILE.read_text(encoding="utf-8"))
    found: dict[str, list[tuple[str, str, str | None]]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)):
            continue
        name = node.targets[0].id
        if name not in MINIMUM_ENTRIES or not isinstance(node.value, ast.Dict):
            continue
        entries: list[tuple[str, str, str | None]] = []
        for key, value in zip(node.value.keys, node.value.values):
            assert isinstance(key, ast.Constant), f"{name}: non-literal key"
            if isinstance(value, ast.Tuple):  # (module, attribute)
                module, symbol = value.elts[0], value.elts[1]
                assert isinstance(module, ast.Constant) and isinstance(symbol, ast.Constant), (
                    f"{name}[{key.value!r}]: target is assembled at runtime rather than "
                    "written as a literal, which is what let these rot before"
                )
                entries.append((key.value, module.value, symbol.value))
            else:  # bare module path
                assert isinstance(value, ast.Constant), (
                    f"{name}[{key.value!r}]: target is not a literal string"
                )
                entries.append((key.value, value.value, None))
        found[name] = entries
    return found


def _module_file(dotted: str) -> Path | None:
    path = PACKAGE.parent / Path(*dotted.split("."))
    for candidate in (path.with_suffix(".py"), path / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _defines(path: Path, symbol: str) -> bool:
    """Is ``symbol`` defined, assigned or re-exported at module level?"""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return True  # not this test's business
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol:
                return True
        elif isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == symbol for t in node.targets):
                return True
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if any((a.asname or a.name.split(".")[0]) == symbol for a in node.names):
                return True
    return False


ALL_ENTRIES = [
    pytest.param(table, key, module, symbol, id=f"{table}-{key}")
    for table, entries in _tables().items()
    for key, module, symbol in entries
]


def test_tables_were_found() -> None:
    """Both tables parsed, and neither has been quietly emptied."""
    tables = _tables()
    assert set(tables) == set(MINIMUM_ENTRIES), f"missing table(s) in {TABLE_FILE.name}"
    for name, minimum in MINIMUM_ENTRIES.items():
        assert len(tables[name]) >= minimum, f"{name} shrank to {len(tables[name])} entries"


@pytest.mark.parametrize(("table", "key", "module", "symbol"), ALL_ENTRIES)
def test_lazy_target_resolves(table: str, key: str, module: str, symbol: str | None) -> None:
    """Every lazy target names a real module, and a symbol that module defines."""
    path = _module_file(module)
    assert path is not None, (
        f"{table}[{key!r}] points at {module!r}, which does not exist. If the code moved, "
        "repoint the table -- a lazy import only fails when a user opens the feature."
    )
    if symbol is not None:
        assert _defines(path, symbol), (
            f"{table}[{key!r}] wants {symbol!r} from {module!r}, "
            f"but {path.name} does not define or re-export it."
        )
