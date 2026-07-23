"""Unit tests for shared academic state (``modules.services.academic_state``).

Not DB-backed: the module holds two pieces of process-wide, in-memory state
(current term, current selection) behind a lock, and broadcasts changes via
``_publish_term`` / ``_publish_selection`` (which fan out to the academics
GUI event bus). Tests:

* reset the module-level state between cases (a fixture) so there's no bleed;
* stub the two publish seams to capture what was broadcast without touching
  the real event bus;
* assert getters/setters, coercion, payload filtering and state transitions.
"""

from __future__ import annotations

import pytest

from education_system.post_18.university_system.modules.services import academic_state
from education_system.post_18.university_system.modules.services.academic_state import (
    Selection,
    Term,
)


@pytest.fixture()
def state(monkeypatch):
    """Reset in-memory state and capture broadcasts.

    Returns a dict with ``terms`` / ``selections`` lists recording every
    publish so tests can assert what was broadcast.
    """
    academic_state._current_term = None
    academic_state._current_selection = None

    published: dict[str, list] = {"terms": [], "selections": []}
    monkeypatch.setattr(academic_state, "_publish_term",
                        lambda term: published["terms"].append(term))
    monkeypatch.setattr(academic_state, "_publish_selection",
                        lambda sel: published["selections"].append(sel))
    yield published

    academic_state._current_term = None
    academic_state._current_selection = None


# ---------------------------------------------------------------------------
# Term dataclass
# ---------------------------------------------------------------------------

class TestTerm:
    def test_label(self):
        assert Term(2025, "Autumn").label() == "Autumn 2025"

    def test_frozen(self):
        with pytest.raises(Exception):
            Term(2025, "Autumn").year = 2026  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Current term
# ---------------------------------------------------------------------------

class TestCurrentTerm:
    def test_starts_none(self, state):
        assert academic_state.get_current_term() is None

    def test_set_stores_coerces_and_broadcasts(self, state):
        term = academic_state.set_current_term("2025", "  Autumn  ")
        assert term == Term(2025, "Autumn")       # year int-coerced, semester stripped
        assert academic_state.get_current_term() == term
        assert state["terms"] == [term]           # broadcast exactly once

    def test_overwrite_replaces_single_source(self, state):
        academic_state.set_current_term(2025, "Autumn")
        second = academic_state.set_current_term(2026, "Spring")
        assert academic_state.get_current_term() == second
        assert state["terms"][-1] == Term(2026, "Spring")
        assert len(state["terms"]) == 2


# ---------------------------------------------------------------------------
# Selection dataclass
# ---------------------------------------------------------------------------

class TestSelectionPayload:
    def test_to_payload_drops_none_and_empty(self):
        sel = Selection(module_code="CS101", course_code=None,
                        student_id="", source="module_gui")
        assert sel.to_payload() == {"module_code": "CS101", "source": "module_gui"}

    def test_empty_selection_payload_is_empty(self):
        assert Selection().to_payload() == {}


# ---------------------------------------------------------------------------
# Current selection
# ---------------------------------------------------------------------------

class TestCurrentSelection:
    def test_starts_none(self, state):
        assert academic_state.get_current_selection() is None

    def test_set_keeps_only_valid_keys(self, state):
        sel = academic_state.set_current_selection(
            module_code="CS101", exam_id=5, bogus="ignored")
        assert sel.module_code == "CS101"
        assert sel.exam_id == 5
        assert not hasattr(sel, "bogus")
        assert academic_state.get_current_selection() == sel
        assert state["selections"] == [sel]

    def test_unset_fields_default_none(self, state):
        sel = academic_state.set_current_selection(student_id="S1")
        assert sel.student_id == "S1"
        assert sel.module_code is None
        assert sel.course_code is None
        assert sel.instructor_id is None

    def test_set_replaces_previous_selection(self, state):
        academic_state.set_current_selection(module_code="CS101")
        second = academic_state.set_current_selection(course_code="C200")
        # New selection does not retain the old module_code (fresh dataclass).
        assert second.module_code is None
        assert second.course_code == "C200"
        assert academic_state.get_current_selection() == second

    def test_clear_resets_and_broadcasts_empty(self, state):
        academic_state.set_current_selection(module_code="CS101")
        academic_state.clear_selection()
        assert academic_state.get_current_selection() is None
        # Last broadcast is an empty Selection.
        assert state["selections"][-1] == Selection()

    def test_empty_kwargs_yields_empty_selection(self, state):
        sel = academic_state.set_current_selection()
        assert sel == Selection()
        assert sel.to_payload() == {}
