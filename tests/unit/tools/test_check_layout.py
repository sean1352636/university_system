"""Tests for tools/check_layout.py — the repository layout ratchet.

``test_repository_matches_baseline`` is the gate itself: it fails when the tree
gains a layout problem, or when a recorded one is fixed but still listed. The
rest pin each rule's behaviour against a small synthetic tree.
"""

from pathlib import Path

import pytest

from tools import check_layout as layout


def test_repository_matches_baseline():
    found = layout.collect()
    new, stale = layout.compare(found, layout.load_baseline())
    assert not new, "New layout violations:\n" + "\n".join(
        f"[{rule}] {entry}" for rule, entries in new.items() for entry in entries)
    assert not stale, (
        "Fixed but still baselined — run `python tools/check_layout.py --prune`:\n"
        + "\n".join(f"[{rule}] {entry}" for rule, entries in stale.items()
                    for entry in entries))


# ---------------------------------------------------------------------------
# synthetic tree
# ---------------------------------------------------------------------------

def _write(root: Path, rel: str, text: str = "") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def src(tmp_path):
    root = tmp_path / "education_system"
    _write(root, "systems/demo/domain/clean.py", "import json\n")
    return root


def test_clean_tree_has_no_findings(src):
    found = layout.collect(src)
    assert all(not found[rule] for rule in layout.RULES)


def test_forbidden_imports_in_domain_are_found_even_inside_functions(src):
    _write(src, "systems/demo/domain/screen.py",
           "def show():\n    import tkinter as tk\n    from sqlite3 import connect\n")
    assert layout.collect(src)["domain-forbidden-import"] == {
        "systems/demo/domain/screen.py -> tkinter",
        "systems/demo/domain/screen.py -> sqlite3",
    }


def test_adapter_imports_in_domain(src):
    _write(src, "systems/demo/domain/rules.py",
           "from education_system.systems.demo.interfaces.gui import app\n"
           "import education_system.platform.delivery.gui.window_sizing\n"
           "from . import sibling\n")
    assert layout.collect(src)["domain-adapter-import"] == {
        "systems/demo/domain/rules.py -> education_system.systems.demo.interfaces.gui",
        "systems/demo/domain/rules.py -> education_system.platform.delivery.gui.window_sizing",
    }


def test_views_and_cli_modules_in_domain(src):
    _write(src, "systems/demo/domain/fees/fees_views.py")
    _write(src, "systems/demo/domain/fees/fees_cli.py")
    _write(src, "systems/demo/interfaces/gui/fees_views.py")
    assert layout.collect(src)["delivery-module-in-domain"] == {
        "systems/demo/domain/fees/fees_views.py",
        "systems/demo/domain/fees/fees_cli.py",
    }


def test_university_domain_layers_are_left_to_the_slice_tests(src):
    _write(src, "systems/university/domain/legacy.py", "import tkinter\n")
    _write(src, "systems/university/domains/finance/domain/x_views.py", "import tkinter\n")
    found = layout.collect(src)
    assert not found["domain-forbidden-import"]
    assert not found["delivery-module-in-domain"]


def test_tree_wide_rules(src):
    _write(src, "platform/big.py", "x = 1\n" * (layout.MAX_LINES + 5))
    _write(src, "migrations/versions/abc_baseline.py", "x = 1\n" * (layout.MAX_LINES + 5))
    _write(src, "systems/demo/interfaces/gui/report_parts/a.py")
    _write(src, "platform/misc.py")
    _write(src, "platform/_imports.py")
    deep = "/".join(f"d{i}" for i in range(layout.MAX_DEPTH)) + "/leaf.py"
    _write(src, deep)
    found = layout.collect(src)
    assert set(found["oversize"]) == {"platform/big.py"}
    assert found["parts-dir"] == {"systems/demo/interfaces/gui/report_parts"}
    assert found["grab-bag-module"] == {"platform/misc.py", "platform/_imports.py"}
    assert found["too-deep"] == {deep}


SHIM = ('"""Moved."""\n# layout-shim: education_system.systems.demo.interfaces.gui.fees_views\n'
        "import importlib as _importlib\nimport sys as _sys\n")


def test_shims_are_exempt_from_other_rules_and_recorded(src):
    _write(src, "systems/demo/domain/fees/fees_views.py", SHIM)
    _write(src, "platform/misc.py", SHIM)
    found = layout.collect(src)
    assert not found["delivery-module-in-domain"]
    assert not found["domain-forbidden-import"]
    assert not found["grab-bag-module"]
    assert found["layout-shim"] == {"systems/demo/domain/fees/fees_views.py", "platform/misc.py"}


def test_parts_dir_holding_only_shims_is_not_counted(src):
    _write(src, "systems/demo/interfaces/gui/old_parts/__init__.py", SHIM)
    _write(src, "systems/demo/interfaces/gui/old_parts/a.py", SHIM)
    _write(src, "systems/demo/interfaces/gui/live_parts/a.py", "x = 1\n")
    assert layout.collect(src)["parts-dir"] == {"systems/demo/interfaces/gui/live_parts"}


def test_accept_shims_records_only_shims(tmp_path, src):
    baseline = tmp_path / "baseline.json"
    assert layout.main(["--src", str(src), "--baseline", str(baseline), "--init"]) == 0
    _write(src, "systems/demo/domain/fees/fees_views.py", SHIM)
    assert layout.main(["--src", str(src), "--baseline", str(baseline)]) == 1
    assert layout.main(["--src", str(src), "--baseline", str(baseline), "--accept-shims"]) == 0
    assert layout.main(["--src", str(src), "--baseline", str(baseline)]) == 0
    _write(src, "platform/misc.py")                         # a real new violation
    assert layout.main(["--src", str(src), "--baseline", str(baseline), "--accept-shims"]) == 1
    assert "platform/misc.py" not in layout.load_baseline(baseline)["grab-bag-module"]


# ---------------------------------------------------------------------------
# ratchet semantics
# ---------------------------------------------------------------------------

def _empty():
    base = {rule: set() for rule in layout.SET_RULES}
    base["oversize"] = {}
    return base


def test_new_entries_fail_and_fixed_entries_are_stale():
    baseline = _empty()
    baseline["parts-dir"] = {"old_parts"}
    found = _empty()
    found["parts-dir"] = {"new_parts"}
    new, stale = layout.compare(found, baseline)
    assert new == {"parts-dir": ["new_parts"]}
    assert stale == {"parts-dir": ["old_parts"]}


def test_oversize_growth_within_headroom_is_allowed():
    baseline = _empty()
    baseline["oversize"] = {"big.py": 3000}
    found = _empty()
    found["oversize"] = {"big.py": 3000 + layout.SIZE_HEADROOM}
    assert layout.compare(found, baseline) == ({}, {})
    found["oversize"]["big.py"] += 1
    new, _ = layout.compare(found, baseline)
    assert list(new) == ["oversize"]


def test_a_file_split_below_the_cap_is_stale():
    baseline = _empty()
    baseline["oversize"] = {"big.py": 3000}
    _, stale = layout.compare(_empty(), baseline)
    assert list(stale) == ["oversize"]


def test_prune_only_ever_shrinks():
    baseline = _empty()
    baseline["grab-bag-module"] = {"a/misc.py", "b/misc.py"}
    baseline["oversize"] = {"big.py": 3000, "gone.py": 2500}
    found = _empty()
    found["grab-bag-module"] = {"a/misc.py", "c/misc.py"}      # c is new
    found["oversize"] = {"big.py": 2600, "new_big.py": 4000}
    result = layout.pruned(found, baseline)
    assert result["grab-bag-module"] == {"a/misc.py"}
    assert result["oversize"] == {"big.py": 2600}


def test_init_refuses_to_overwrite(tmp_path, src):
    baseline = tmp_path / "baseline.json"
    assert layout.main(["--src", str(src), "--baseline", str(baseline), "--init"]) == 0
    assert layout.main(["--src", str(src), "--baseline", str(baseline), "--init"]) == 1
    assert layout.main(["--src", str(src), "--baseline", str(baseline)]) == 0
    _write(src, "platform/misc.py")
    assert layout.main(["--src", str(src), "--baseline", str(baseline)]) == 1
