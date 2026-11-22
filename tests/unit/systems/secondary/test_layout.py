"""The Secondary School layout rules (one package per feature module, rules
never reach up into screens, core never reaches into the modules).

    secondary/
    ├── app/                  cli_main, gui_main, routing (the menu catalogue)
    ├── core/                 exceptions/, permissions/, academic_calendar/, utilities/
    ├── infrastructure/       database/, authentication/, logging/, integrations/
    ├── ui/{gui,cli}/         shared widgets, layouts, page/menu registries, prompts
    ├── resources/            shared assets (e-mail templates)
    └── modules/<module>/
        ├── domain/           the module's rules
        ├── gui/              its screens
        └── cli/              its menus

Rules code (``core/`` and every ``modules/*/domain/``) may import ``core``,
``infrastructure`` and other modules' ``domain`` - never a screen, a menu,
``ui``, ``app``, tkinter, sqlite3 (SQL belongs in ``infrastructure``) or the
platform's delivery layer. ``core`` imports no feature module at all.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import education_system.systems.secondary as secondary

ROOT = Path(secondary.__file__).resolve().parent
PKG = "education_system.systems.secondary"
FORBIDDEN_MODULES = ("tkinter", "sqlite3")
FORBIDDEN_PREFIXES = (f"{PKG}.ui", f"{PKG}.app", "education_system.platform.delivery")
CORE_FORBIDDEN = (f"{PKG}.modules", f"{PKG}.infrastructure.integrations")


def _rules_files() -> list[Path]:
    files = sorted((ROOT / "core").rglob("*.py"))
    for module in sorted((ROOT / "modules").iterdir()):
        files += sorted((module / "domain").glob("*.py")) if module.is_dir() else []
    return files


def _imports(path: Path) -> list[tuple[int, str]]:
    """Every module imported anywhere in the file, lazy imports included."""
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out += [(node.lineno, a.name) for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            out.append((node.lineno, node.module))
            out += [(node.lineno, f"{node.module}.{a.name}") for a in node.names]
    return out


def _is_screen(module: str) -> bool:
    parts = module.split(".")
    return (module.startswith(f"{PKG}.modules.") and len(parts) > 5
            and parts[5] in ("gui", "cli"))


@pytest.mark.parametrize("path", _rules_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_rules_never_import_screens(path: Path) -> None:
    bad = [f"line {n}: {m}" for n, m in _imports(path)
           if m.split(".")[0] in FORBIDDEN_MODULES
           or m.startswith(FORBIDDEN_PREFIXES) or _is_screen(m)]
    assert not bad, f"{path.relative_to(ROOT)} imports " + "; ".join(bad)


@pytest.mark.parametrize("path", sorted((ROOT / "core").rglob("*.py")),
                         ids=lambda p: str(p.relative_to(ROOT)))
def test_core_never_imports_feature_modules(path: Path) -> None:
    bad = [f"line {n}: {m}" for n, m in _imports(path) if m.startswith(CORE_FORBIDDEN)]
    assert not bad, f"{path.relative_to(ROOT)} imports " + "; ".join(bad)


def test_every_module_has_the_same_shape() -> None:
    for module in sorted(p for p in (ROOT / "modules").iterdir() if p.is_dir()
                         and p.name != "__pycache__"):
        for sub in ("domain", "gui", "cli"):
            assert (module / sub / "__init__.py").is_file(), \
                f"modules/{module.name}/{sub}/ missing"
        stray = sorted(p.name for p in module.glob("*.py") if p.name != "__init__.py")
        assert not stray, f"modules/{module.name}/ has loose modules {stray}"


def test_old_folders_do_not_come_back() -> None:
    for old in ("areas", "domain", "interfaces", "cli_main.py", "gui_main.py"):
        assert not (ROOT / old).exists(), \
            f"{old} is back - features go in modules/<module>/, entry points in app/"
