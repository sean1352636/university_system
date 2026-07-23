"""Unit tests for the chatbot tool surface (``modules.services.chatbot_tools``).

Almost every tool is a thin wrapper: it lazily ``from ... import <fn>`` a
canonical service function, calls it, and wraps the result in a
``{"ok": True, ...}`` dict (or ``{"ok": False, "error": ...}`` on any
exception). Because the imports happen *inside* the function at call time,
each seam can be controlled by injecting a fake module into ``sys.modules``
before the call — the ``from`` statement then resolves the fake.

Tests assert two behaviours per tool:
* **pass-through** — the tool forwards its args to the delegate and shapes
  the delegate's return into the documented reply dict.
* **error swallowing** — a raising delegate degrades to
  ``{"ok": False, "error": <str>}`` instead of propagating.
"""

from __future__ import annotations

import sys
import sqlite3
import types

import pytest

from education_system.post_18.university_system.modules.services import chatbot_tools


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def inject(monkeypatch, dotted: str, **attrs) -> types.ModuleType:
    """Install a fake module at ``dotted`` in sys.modules for the test's life."""
    mod = types.ModuleType(dotted)
    for name, val in attrs.items():
        setattr(mod, name, val)
    monkeypatch.setitem(sys.modules, dotted, mod)
    return mod


SERVICES = "education_system.post_18.university_system.modules.services"
XSVC = "education_system.post_18.university_system.modules.domain.academics.gui._cross_services"


def raiser(*a, **k):
    raise RuntimeError("boom")


# ---------------------------------------------------------------------------
# Finance tools
# ---------------------------------------------------------------------------

class TestFinanceTools:
    def test_balance_passthrough(self, monkeypatch):
        inject(monkeypatch, f"{SERVICES}.finance_bus",
               student_balance=lambda sid: 123.45)
        out = chatbot_tools.tool_balance("S1")
        assert out == {"ok": True, "balance": 123.45, "currency": "GBP"}

    def test_balance_error_swallowed(self, monkeypatch):
        inject(monkeypatch, f"{SERVICES}.finance_bus", student_balance=raiser)
        out = chatbot_tools.tool_balance("S1")
        assert out["ok"] is False
        assert "boom" in out["error"]

    def test_active_holds_passthrough(self, monkeypatch):
        holds = [{"hold_id": 1}]
        inject(monkeypatch, f"{SERVICES}.finance_bus",
               list_active_holds=lambda sid: holds)
        assert chatbot_tools.tool_active_holds("S1") == {"ok": True, "holds": holds}


# ---------------------------------------------------------------------------
# Academic tools (delegate to _cross_services)
# ---------------------------------------------------------------------------

class TestAcademicTools:
    def test_module_grade(self, monkeypatch):
        inject(monkeypatch, XSVC,
               compute_module_grade=lambda sid, mc: {"grade": 72})
        out = chatbot_tools.tool_module_grade("S1", "CS101")
        assert out == {"ok": True, "result": {"grade": 72}}

    def test_module_timeline(self, monkeypatch):
        inject(monkeypatch, XSVC, module_timeline=lambda mc: ["ev1", "ev2"])
        assert chatbot_tools.tool_module_timeline("CS101") == {
            "ok": True, "events": ["ev1", "ev2"]}

    def test_current_period_echoes_kind(self, monkeypatch):
        inject(monkeypatch, XSVC, current_period=lambda kind: "Autumn 2025")
        out = chatbot_tools.tool_current_period("term")
        assert out == {"ok": True, "kind": "term", "period": "Autumn 2025"}

    def test_find_free_rooms_forwards_kwargs(self, monkeypatch):
        seen = {}

        def _find(*, day_of_week, start_time, end_time, min_capacity):
            seen.update(dict(day_of_week=day_of_week, start_time=start_time,
                             end_time=end_time, min_capacity=min_capacity))
            return [{"room": "R1"}]

        inject(monkeypatch, XSVC, find_free_rooms=_find)
        out = chatbot_tools.tool_find_free_rooms("Mon", "09:00", "10:00", 30)
        assert out == {"ok": True, "rooms": [{"room": "R1"}]}
        assert seen == {"day_of_week": "Mon", "start_time": "09:00",
                        "end_time": "10:00", "min_capacity": 30}

    def test_instructor_workload_coerces_int(self, monkeypatch):
        seen = {}

        def _wl(*, instructor_id):
            seen["id"] = instructor_id
            return {"modules": 3}

        inject(monkeypatch, XSVC, instructor_workload=_wl)
        out = chatbot_tools.tool_instructor_workload("42")
        assert out == {"ok": True, "workload": {"modules": 3}}
        assert seen["id"] == 42 and isinstance(seen["id"], int)

    def test_academic_error_swallowed(self, monkeypatch):
        inject(monkeypatch, XSVC, module_timeline=raiser)
        assert chatbot_tools.tool_module_timeline("CS101")["ok"] is False


# ---------------------------------------------------------------------------
# HR / certs / documents / inbox
# ---------------------------------------------------------------------------

class TestMiscReadTools:
    def test_qualified_for(self, monkeypatch):
        inject(monkeypatch, f"{SERVICES}.staff_hr_bus",
               is_qualified_for=lambda iid, mc: True)
        assert chatbot_tools.tool_qualified_for(7, "CS101") == {
            "ok": True, "qualified": True}

    def test_certs_expiring_forwards_args(self, monkeypatch):
        seen = {}

        def _exp(within_days, kind=None):
            seen.update(dict(within_days=within_days, kind=kind))
            return [{"kind": "First Aid"}]

        inject(monkeypatch, f"{SERVICES}.cert_bus", expiring_certifications=_exp)
        out = chatbot_tools.tool_certs_expiring(45, kind="First Aid")
        assert out == {"ok": True, "certs": [{"kind": "First Aid"}]}
        assert seen == {"within_days": 45, "kind": "First Aid"}

    def test_documents_for(self, monkeypatch):
        inject(monkeypatch, f"{SERVICES}.document_bus",
               get_documents_for=lambda domain, ref: [{"id": 1}])
        assert chatbot_tools.tool_documents_for("housing", 9) == {
            "ok": True, "documents": [{"id": 1}]}

    def test_pending_messages(self, monkeypatch):
        inject(monkeypatch, f"{SERVICES}.chatbot_inbox",
               pop_messages_for=lambda uid: ["m1"])
        assert chatbot_tools.tool_pending_messages("S1") == {
            "ok": True, "messages": ["m1"]}


# ---------------------------------------------------------------------------
# Mutation-style wrappers
# ---------------------------------------------------------------------------

class TestMutationTools:
    def test_move_slot_forwards_all_kwargs(self, monkeypatch):
        seen = {}

        def _move(schedule_id, *, new_day, new_start_time, new_end_time,
                  new_room_id, moved_by):
            seen.update(locals())
            return {"moved": True}

        inject(
            monkeypatch,
            "education_system.post_18.university_system.modules.domain.academics."
            "services.module_scheduling.slot_writer",
            move_slot=_move,
        )
        out = chatbot_tools.tool_move_slot(5, new_day="Tue", new_start_time="11:00")
        assert out == {"ok": True, "result": {"moved": True}}
        assert seen["schedule_id"] == 5
        assert seen["new_day"] == "Tue"
        assert seen["moved_by"] == "chatbot"      # default

    def test_book_room_trims_to_top_five(self, monkeypatch):
        rooms = [{"room": f"R{i}"} for i in range(9)]
        inject(monkeypatch, XSVC, find_free_rooms=lambda **k: rooms)
        out = chatbot_tools.tool_book_room(
            day_of_week="Mon", start_time="09:00", end_time="10:00")
        assert out["ok"] is True
        assert len(out["rooms"]) == 5
        assert out["total"] == 9

    def test_schedule_exam_requires_core_fields(self):
        out = chatbot_tools.tool_schedule_exam(
            module_code="", date="2026-01-01", start_time="09:00", end_time="11:00")
        assert out == {"ok": False, "error":
                       "module_code/date/start_time/end_time required"}

    def test_queue_message_ok_flag_reflects_id(self, monkeypatch):
        inject(monkeypatch, f"{SERVICES}.chatbot_inbox",
               queue_message_for=lambda uid, msg, source="chatbot": 99)
        out = chatbot_tools.tool_queue_message("S1", "hi")
        assert out == {"ok": True, "msg_id": 99}

    def test_queue_message_falsy_id_is_not_ok(self, monkeypatch):
        inject(monkeypatch, f"{SERVICES}.chatbot_inbox",
               queue_message_for=lambda uid, msg, source="chatbot": 0)
        out = chatbot_tools.tool_queue_message("S1", "hi")
        assert out == {"ok": False, "msg_id": 0}

    def test_set_email_pref_returns_raw_bool(self, monkeypatch):
        inject(monkeypatch, f"{SERVICES}.email_bus",
               set_pref=lambda uid, kind, enabled: True)
        assert chatbot_tools.tool_set_email_pref("S1", "grades", True) == {"ok": True}


# ---------------------------------------------------------------------------
# Student-services wrappers
# ---------------------------------------------------------------------------

class TestStudentServiceTools:
    def test_my_open_cases(self, monkeypatch):
        inject(monkeypatch, f"{SERVICES}.cases_bus",
               list_open=lambda uid: [{"case_id": 1}])
        assert chatbot_tools.tool_my_open_cases("S1") == {
            "ok": True, "cases": [{"case_id": 1}]}

    def test_my_clubs(self, monkeypatch):
        inject(monkeypatch, f"{SERVICES}.student_union_bus",
               list_clubs_for=lambda uid: ["Chess"])
        assert chatbot_tools.tool_my_clubs("S1") == {"ok": True, "clubs": ["Chess"]}

    def test_request_su_advocacy_forwards_kind(self, monkeypatch):
        seen = {}

        def _req(uid, cid, *, case_kind):
            seen.update(dict(uid=uid, cid=cid, case_kind=case_kind))
            return 5

        inject(monkeypatch, f"{SERVICES}.student_union_bus", request_advocacy=_req)
        out = chatbot_tools.tool_request_su_advocacy("S1", 8, kind="misconduct")
        assert out == {"ok": True, "request_id": 5}
        assert seen == {"uid": "S1", "cid": 8, "case_kind": "misconduct"}

    def test_my_parking_merges_two_calls(self, monkeypatch):
        inject(monkeypatch, f"{SERVICES}.parking_bus",
               list_permits_for=lambda uid: ["P1"],
               outstanding_parking_charges=lambda uid: [{"fine": 40}])
        out = chatbot_tools.tool_my_parking("S1")
        assert out == {"ok": True, "permits": ["P1"], "fines": [{"fine": 40}]}

    def test_todays_menu(self, monkeypatch):
        inject(monkeypatch, f"{SERVICES}.restaurant_bus",
               menu_for=lambda: [{"dish": "Curry"}])
        assert chatbot_tools.tool_todays_menu() == {
            "ok": True, "menus": [{"dish": "Curry"}]}

    def test_upcoming_trips_defaults_floor_to_today(self, monkeypatch):
        seen = {}
        inject(monkeypatch, f"{SERVICES}.trip_bus",
               list_trips=lambda since=None: seen.setdefault("since", since) or [])
        out = chatbot_tools.tool_upcoming_trips()
        assert out["ok"] is True
        # Defaults to an ISO date (today) rather than None.
        assert seen["since"] and "-" in seen["since"]


# ---------------------------------------------------------------------------
# Aggregator: tool_summarise_module (uses _cross_services + real get_connection)
# ---------------------------------------------------------------------------

class TestSummariseModule:
    def test_empty_module_code_errors(self):
        out = chatbot_tools.tool_summarise_module("")
        assert out == {"ok": False, "error": "module_code required"}

    def test_aggregates_sections(self, tmp_path, monkeypatch):
        # Real DB for the instructor lookup branch.
        db_path = str(tmp_path / "summ.db")
        monkeypatch.setattr(
            "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH",
            db_path,
        )
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE module_schedule (module_code TEXT, instructor_id INTEGER)")
        conn.execute("INSERT INTO module_schedule VALUES ('CS101', 7)")
        conn.commit()
        conn.close()

        inject(
            monkeypatch, XSVC,
            module_timeline=lambda mc: ["lecture"],
            find_conflicts_for_module=lambda mc: [],
            compute_module_grade=lambda sid, mc: {"grade": 65},
            instructor_workload=lambda *, instructor_id: {"id": instructor_id},
        )
        out = chatbot_tools.tool_summarise_module("CS101", student_id="S1")
        assert out["ok"] is True
        assert out["module_code"] == "CS101"
        assert out["timeline"] == ["lecture"]
        assert out["conflicts"] == []
        assert out["grade"] == {"grade": 65}
        assert out["instructor"] == {"id": 7}

    def test_section_failures_are_isolated(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "summ2.db")
        monkeypatch.setattr(
            "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH",
            db_path,
        )
        # No module_schedule table → instructor branch swallowed silently.
        inject(
            monkeypatch, XSVC,
            module_timeline=raiser,               # timeline branch fails → []
            find_conflicts_for_module=lambda mc: [{"c": 1}],
            compute_module_grade=raiser,
            instructor_workload=lambda **k: {},
        )
        out = chatbot_tools.tool_summarise_module("CS101", student_id="S1")
        assert out["ok"] is True
        assert out["timeline"] == []              # failure degraded to []
        assert out["conflicts"] == [{"c": 1}]
        assert out["grade"] is None               # failure degraded to None
        assert "instructor" not in out            # no schedule row


# ---------------------------------------------------------------------------
# Registry + dispatch
# ---------------------------------------------------------------------------

class TestRegistryAndDispatch:
    def test_every_registry_value_is_callable(self):
        assert chatbot_tools.TOOLS
        assert all(callable(fn) for fn in chatbot_tools.TOOLS.values())

    def test_registry_points_at_module_functions(self):
        assert chatbot_tools.TOOLS["balance"] is chatbot_tools.tool_balance
        assert chatbot_tools.TOOLS["summarise_module"] is chatbot_tools.tool_summarise_module

    def test_call_tool_dispatches(self, monkeypatch):
        inject(monkeypatch, f"{SERVICES}.finance_bus",
               student_balance=lambda sid: 10.0)
        out = chatbot_tools.call_tool("balance", student_id="S1")
        assert out == {"ok": True, "balance": 10.0, "currency": "GBP"}

    def test_call_tool_unknown_name(self):
        assert chatbot_tools.call_tool("nope") == {
            "ok": False, "error": "unknown tool: nope"}

    def test_call_tool_bad_arguments(self):
        # tool_balance requires student_id; wrong kwarg → TypeError → shaped error.
        out = chatbot_tools.call_tool("balance", wrong_kw=1)
        assert out["ok"] is False
        assert "bad arguments" in out["error"]
