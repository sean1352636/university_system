"""Unit tests for the risks panel widget (``modules.services.risks_panel``).

``risks_panel`` is a pure read-side Tk widget over ``risk_bus.list_risks_for``. It
owns no DB and no display can be assumed under CI, so the test replaces the module's
``tk`` / ``ttk`` / ``messagebox`` globals with lightweight fakes that record what the
function builds, and stubs the one data seam (``risk_bus.list_risks_for``).

What is asserted is the widget's real branching behaviour: the missing-reference and
``risk_bus``-unavailable guard rails, the empty-state (no Treeview), and — for the
populated case — that exactly one Treeview row is inserted per risk with the derived
``L×I`` score and the ``—`` fallbacks the code applies.
"""

import importlib
import sys
import types

import pytest

from education_system.post_18.university_system.modules.services import risks_panel, risk_bus

_SERVICES = "education_system.post_18.university_system.modules.services"
_RISK_BUS = _SERVICES + ".risk_bus"


# ---------------------------------------------------------------------------
# Fake Tk toolkit
# ---------------------------------------------------------------------------

class _FakeWidget:
    def __init__(self, *a, **k):
        self.args = a
        self.kwargs = k
    def pack(self, *a, **k):
        return self
    def heading(self, *a, **k):
        pass
    def column(self, *a, **k):
        pass
    def tag_configure(self, *a, **k):
        pass


class _FakeTreeview(_FakeWidget):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.rows = []
    def insert(self, parent, index, *, values=(), tags=()):
        self.rows.append({"values": values, "tags": tags})


class _FakeToplevel(_FakeWidget):
    def title(self, *a, **k):
        pass
    def geometry(self, *a, **k):
        pass
    def transient(self, *a, **k):
        pass
    def destroy(self):
        pass
    def winfo_toplevel(self):
        return self


@pytest.fixture()
def fake_tk(monkeypatch):
    """Swap risks_panel's tk/ttk/messagebox for recording fakes.

    Returns a small state object exposing the warnings/errors captured and the
    Treeview/Toplevel instances created so tests can inspect what was built.
    """
    state = types.SimpleNamespace(
        warnings=[], errors=[], treeviews=[], toplevels=[],
    )

    def _make_tree(*a, **k):
        tv = _FakeTreeview(*a, **k)
        state.treeviews.append(tv)
        return tv

    def _make_top(*a, **k):
        top = _FakeToplevel(*a, **k)
        state.toplevels.append(top)
        return top

    fake_tk_mod = types.SimpleNamespace(Toplevel=_make_top, Misc=object)
    fake_ttk = types.SimpleNamespace(
        Frame=_FakeWidget, Label=_FakeWidget,
        Button=_FakeWidget, Treeview=_make_tree,
    )
    fake_mb = types.SimpleNamespace(
        showwarning=lambda *a, **k: state.warnings.append(a),
        showerror=lambda *a, **k: state.errors.append(a),
    )
    monkeypatch.setattr(risks_panel, "tk", fake_tk_mod)
    monkeypatch.setattr(risks_panel, "ttk", fake_ttk)
    monkeypatch.setattr(risks_panel, "messagebox", fake_mb)
    return state


def _stub_risk_bus(monkeypatch, rows):
    """Patch the real risk_bus seam. Patching the attribute (rather than swapping
    the module in sys.modules) is robust to the module already being imported by
    other tests in the same session."""
    monkeypatch.setattr(risk_bus, "list_risks_for", lambda ref: rows)


# ---------------------------------------------------------------------------
# Guard rails
# ---------------------------------------------------------------------------

class TestGuardRails:
    def test_missing_reference_warns_and_returns(self, fake_tk):
        risks_panel.show_risks_for(_FakeToplevel(), reference_id="")
        assert len(fake_tk.warnings) == 1
        # No window is created when the reference id is missing.
        assert fake_tk.toplevels == []

    def test_risk_bus_unavailable_shows_error(self, fake_tk, monkeypatch):
        # Poison the import so `from ... import risk_bus` raises ImportError:
        # drop the cached attribute on the services package AND null the module
        # entry so the import machinery re-runs and fails.
        services_pkg = importlib.import_module(_SERVICES)
        monkeypatch.delattr(services_pkg, "risk_bus", raising=False)
        monkeypatch.setitem(sys.modules, _RISK_BUS, None)
        risks_panel.show_risks_for(_FakeToplevel(), reference_id="module:CS101")
        assert len(fake_tk.errors) == 1
        assert fake_tk.toplevels == []


# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------

class TestEmptyState:
    def test_no_rows_builds_window_without_treeview(self, fake_tk, monkeypatch):
        _stub_risk_bus(monkeypatch, [])
        risks_panel.show_risks_for(_FakeToplevel(), reference_id="trip:42")
        # Window is created, but the empty-state path never builds a Treeview.
        assert len(fake_tk.toplevels) == 1
        assert fake_tk.treeviews == []

    def test_passes_reference_id_through(self, fake_tk, monkeypatch):
        seen = []
        monkeypatch.setattr(risk_bus, "list_risks_for",
                            lambda ref: seen.append(ref) or [])
        risks_panel.show_risks_for(_FakeToplevel(), reference_id="course:CS-BSC")
        assert seen == ["course:CS-BSC"]


# ---------------------------------------------------------------------------
# Populated table
# ---------------------------------------------------------------------------

class TestPopulated:
    def test_one_row_per_risk_with_score_and_fallbacks(self, fake_tk, monkeypatch):
        rows = [
            {"id": 1, "title": "Coach breakdown", "category": "Safety",
             "status": "Open", "likelihood": 3, "impact": 4,
             "owner": "S001", "next_review_date": "2026-08-01",
             "expires_at": "2026-09-01"},
            {"id": 2, "title": "Budget overrun", "category": "Finance",
             "status": "review", "likelihood": 2, "impact": 5,
             "owner": None, "next_review_date": None, "expires_at": None},
        ]
        _stub_risk_bus(monkeypatch, rows)
        risks_panel.show_risks_for(_FakeToplevel(), reference_id="trip:42",
                                   title="Risks for trip 42")

        assert len(fake_tk.treeviews) == 1
        tv = fake_tk.treeviews[0]
        assert len(tv.rows) == 2

        first = tv.rows[0]["values"]
        # values = (id, title, category, status, score, owner, review, expires)
        assert first[0] == 1
        assert first[4] == 12                 # 3 * 4
        assert first[5] == "S001"
        assert fake_tk.treeviews[0].rows[0]["tags"] == ("open",)

        second = tv.rows[1]["values"]
        assert second[4] == 10                # 2 * 5
        assert second[5] == "—"               # owner None fallback
        assert second[6] == "—"               # next_review_date None fallback
        assert second[7] == "—"               # expires_at None fallback

    def test_missing_score_fields_default_to_zero(self, fake_tk, monkeypatch):
        _stub_risk_bus(monkeypatch, [{"id": 9, "title": "T", "status": "closed"}])
        risks_panel.show_risks_for(_FakeToplevel(), reference_id="module:X")
        tv = fake_tk.treeviews[0]
        assert tv.rows[0]["values"][4] == 0   # likelihood/impact absent -> 0
        assert tv.rows[0]["tags"] == ("closed",)
