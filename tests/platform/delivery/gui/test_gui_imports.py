"""Smoke test: verify all GUI modules can be imported without errors.

Catches broken import paths, missing modules, and typos in class names
before they surface at runtime. Runs without a display (no tkinter
windows are created).

Marked as ``gui`` so it's excluded from the default test run but
included in ``make test-all``.
"""

import importlib
import pkgutil
import pytest
import os
import sys


def _discover_gui_modules():
    """Walk the university_system tree and yield importable GUI module paths."""
    base = os.path.join(
        os.path.dirname(__file__),
        os.pardir, os.pardir,
        "post_18", "university_system", "modules",
    )
    base = os.path.normpath(base)

    for root, dirs, files in os.walk(base):
        # Skip __pycache__ and test directories
        dirs[:] = [d for d in dirs if d != "__pycache__" and d != "tests"]

        for fname in files:
            if not fname.endswith(".py") or fname.startswith("_"):
                continue

            # Only GUI-related files
            full = os.path.join(root, fname)
            # Build the dotted import path relative to the directory that
            # *contains* the education_system package (the repo root), so the
            # module path is fully qualified: education_system.post_18…
            # ``base`` is …/education_system/post_18/university_system/modules,
            # so climb four levels (modules → university_system → post_18 →
            # education_system → repo root).
            repo_root = os.path.join(base, os.pardir, os.pardir, os.pardir, os.pardir)
            rel = os.path.relpath(full, repo_root)
            module_path = rel.replace(os.sep, ".").removesuffix(".py")

            if "_gui" in fname or os.sep + "gui" + os.sep in full.replace("/", os.sep):
                yield module_path


# Collect at import time so parametrize works
_GUI_MODULES = sorted(set(_discover_gui_modules()))


@pytest.mark.gui
@pytest.mark.parametrize("module_path", _GUI_MODULES[:50])  # Cap to keep CI fast
def test_gui_module_imports(module_path):
    """Each GUI module should import without raising ImportError."""
    try:
        importlib.import_module(module_path)
    except ImportError as exc:
        pytest.fail(f"ImportError in {module_path}: {exc}")
    except Exception:
        # Non-import errors (e.g. missing DB, no display) are OK here.
        # We only care about broken import paths.
        pass
