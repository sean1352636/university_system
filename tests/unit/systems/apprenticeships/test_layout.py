"""Layout guards: every module in the package holds code.

About 110 re-export shims and one-line docstring stubs were cleared out
of this package in September 2026. Each looked like a feature in the
file tree and did nothing, which made the tree hard to navigate. These
tests stop either kind coming back.
"""

from __future__ import annotations

import ast
from pathlib import Path

import education_system.systems.apprenticeships as package

_ROOT = Path(package.__file__).parent


def _modules() -> list[Path]:
    return sorted(p for p in _ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def _is_docstring(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def test_no_star_reexports():
    """Import names from the module that defines them, not via a shim."""
    offenders = []
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
                offenders.append(f"{path.relative_to(_ROOT)} -> {node.module}")
    assert not offenders, offenders


def test_no_docstring_only_modules():
    """A planned module belongs in the docs until it has code in it."""
    offenders = [
        str(path.relative_to(_ROOT))
        for path in _modules()
        if path.name != "__init__.py"
        and all(_is_docstring(node) for node in ast.parse(path.read_text(encoding="utf-8")).body)
    ]
    assert not offenders, offenders
