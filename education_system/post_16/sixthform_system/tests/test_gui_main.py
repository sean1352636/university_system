"""Tests for the sixth-form Tk GUI entry points.

Covers the shim ``sixthform_system/gui_main.py`` plus the underlying
``modules.shared.gui.gui_main``: module-level constants, ``run``
preconditions, and ``SixthFormMainGUI`` lifecycle/helpers.
"""

from __future__ import annotations

import os
import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest


_NO_DISPLAY = not os.environ.get("DISPLAY")


@pytest.fixture
def fake_auth():
    auth = MagicMock()
    auth.current_user = {"username": "tester", "role": "staff"}
    return auth


@pytest.fixture
def gui_inner():
    from education_system.post_16.sixthform_system.modules.shared.gui import gui_main
    return gui_main


# ── shim ─────────────────────────────────────────────────────────────

def test_shim_reexports_run():
    from education_system.post_16.sixthform_system import gui_main as shim
    from education_system.post_16.sixthform_system.modules.shared.gui import (
        gui_main as inner,
    )
    assert shim.run is inner.run
    assert shim.SixthFormMainGUI is inner.SixthFormMainGUI


# ── module shape ─────────────────────────────────────────────────────

def test_nav_categories_match_expected_groups(gui_inner):
    cats = {c for c, _ in gui_inner.NAV_CATEGORIES}
    assert {
        "Student Management", "Academic Management", "Assessment & Grades",
        "UCAS & Careers", "Pastoral & Wellbeing", "Staff & Communication",
        "Finance & Bursaries", "Reports & Analytics", "System",
    } == cats
    for _grp, items in gui_inner.NAV_CATEGORIES:
        assert items
        for label, handler in items:
            assert isinstance(label, str) and isinstance(handler, str)


def test_module_constants(gui_inner):
    assert gui_inner.FOOTER_LABEL == "Sixth Form"
    assert isinstance(gui_inner.VERSION, str) and gui_inner.VERSION


# ── run() preconditions ──────────────────────────────────────────────

def test_run_raises_without_shared_auth(gui_inner):
    with pytest.raises(RuntimeError):
        gui_inner.run(shared_auth=None)


def test_run_raises_when_shared_auth_has_no_current_user(gui_inner):
    auth = MagicMock()
    auth.current_user = None
    with pytest.raises(RuntimeError):
        gui_inner.run(shared_auth=auth)


def test_run_main_module_guard():
    import runpy
    with pytest.raises(SystemExit) as exc:
        runpy.run_module(
            "education_system.post_16.sixthform_system.modules.shared.gui.gui_main",
            run_name="__main__",
        )
    assert exc.value.code == 2


# ── SixthFormMainGUI — head-only construction ────────────────────────

@pytest.mark.skipif(_NO_DISPLAY, reason="needs a display")
@pytest.mark.gui
class TestSixthFormMainGUI:
    """Construct a real Tk window and exercise the in-memory helpers.

    The constructor brings up a window and renders the welcome screen; we
    immediately destroy the root in teardown so no event loop is run.
    """

    @pytest.fixture
    def app(self, fake_auth, gui_inner, monkeypatch):
        # Force the idle watcher to be a no-op so tests don't schedule
        # background ``after`` callbacks against a destroyed root.
        from education_system.post_16.sixthform_system.modules.shared.gui import (
            idle_timeout as it,
        )
        monkeypatch.setattr(
            it, "IdleTimeoutWatcher",
            lambda *a, **kw: MagicMock(start=MagicMock(), stop=MagicMock()),
        )
        instance = gui_inner.SixthFormMainGUI(fake_auth)
        yield instance
        try:
            instance.root.destroy()
        except tk.TclError:
            pass

    def test_construction_sets_window_basics(self, app):
        assert app.root.title() == "Sixth Form System"
        assert app.current_user_var.get() == "tester"
        assert app.status_var.get() == "Ready"
        assert app.content_frame is not None

    def test_handler_returns_callable_for_known_method(self, app):
        cb = app._handler("open_add_student", "Add Student")
        assert callable(cb)
        # Bound method — same identity.
        assert cb == app.open_add_student

    def test_handler_falls_back_to_stub_for_unknown(self, app):
        cb = app._handler("nope_does_not_exist", "Mystery Feature")
        cb()
        # Stub flips the status bar.
        assert app.status_var.get() == "Opened: Mystery Feature"

    def test_show_stub_renders_label(self, app):
        app._show_stub("Some Label")
        children = app.content_frame.winfo_children()
        assert any(
            isinstance(w, type(children[0])) and "Some Label" in str(w.cget("text"))
            for w in children if hasattr(w, "cget")
        )

    def test_clear_content_empties_frame(self, app):
        app._show_stub("X")
        assert app.content_frame.winfo_children()
        app._clear_content()
        assert app.content_frame.winfo_children() == []

    def test_safe_count_handles_missing_module(self, app):
        assert app._safe_count(
            "no.such.module.exists.anywhere", "list_x") is None

    def test_safe_count_handles_missing_function(self, app):
        # Use a real importable module that lacks the requested attr.
        assert app._safe_count("logging", "definitely_not_a_function") is None

    def test_safe_count_returns_length(self, app):
        with patch("importlib.import_module") as m:
            fake_mod = MagicMock()
            fake_mod.list_things.return_value = [1, 2, 3]
            m.return_value = fake_mod
            assert app._safe_count("anything", "list_things") == 3

    def test_safe_count_none_rows_treated_as_zero(self, app):
        with patch("importlib.import_module") as m:
            fake_mod = MagicMock()
            fake_mod.list_things.return_value = None
            m.return_value = fake_mod
            assert app._safe_count("x", "list_things") == 0

    def test_today_attendance_pct_no_rows(self, app):
        with patch(
            "education_system.post_16.sixthform_system.modules.domain."
            "academics.attendance.attendance.list_records",
            return_value=[],
        ):
            pct, hint = app._today_attendance_pct("2026-05-18")
        assert pct == "—"
        assert "No marks" in hint

    def test_today_attendance_pct_with_rows(self, app):
        rows = [
            MagicMock(status="Present"),
            MagicMock(status="Late"),
            MagicMock(status="Absent"),
            MagicMock(status="Absent"),
        ]
        with patch(
            "education_system.post_16.sixthform_system.modules.domain."
            "academics.attendance.attendance.list_records",
            return_value=rows,
        ):
            pct, hint = app._today_attendance_pct("2026-05-18")
        assert pct == "50%"
        assert "2/4" in hint

    def test_today_attendance_pct_swallows_errors(self, app):
        with patch(
            "education_system.post_16.sixthform_system.modules.domain."
            "academics.attendance.attendance.list_records",
            side_effect=RuntimeError("boom"),
        ):
            pct, hint = app._today_attendance_pct("2026-05-18")
        assert pct == "—"
        assert "not available" in hint.lower()

    def test_gather_kpis_returns_four_tiles(self, app):
        with patch.object(app, "_safe_count", return_value=7), \
             patch.object(app, "_today_attendance_pct",
                          return_value=("80%", "x/y")):
            kpis = app._gather_kpis()
        assert len(kpis) == 4
        labels = [k[0] for k in kpis]
        assert labels == ["Students", "Staff", "Courses",
                          "Today's Attendance"]

    def test_show_welcome_resets_status(self, app):
        app.status_var.set("Doing something")
        app._show_welcome()
        assert app.status_var.get() == "Ready"

    def test_stop_idle_watcher_safe_when_none(self, app):
        app._idle_watcher = None
        app._stop_idle_watcher()  # must not raise

    def test_stop_idle_watcher_calls_stop(self, app):
        watcher = MagicMock()
        app._idle_watcher = watcher
        app._stop_idle_watcher()
        watcher.stop.assert_called_once()

    def test_logout_invokes_request_logout(self, app, monkeypatch):
        from education_system import switch
        captured = {}
        monkeypatch.setattr(
            switch, "request_logout",
            lambda iface: captured.setdefault("iface", iface))
        app._logout()
        assert captured["iface"] == "gui"
        app.auth.logout.assert_called_once()

    def test_idle_logout_signals_logout(self, app, monkeypatch):
        from education_system import switch
        called = {}
        monkeypatch.setattr(
            switch, "request_logout",
            lambda iface: called.setdefault("iface", iface))
        # Suppress the messagebox so the test doesn't open a dialog.
        monkeypatch.setattr(
            "tkinter.messagebox.showinfo", lambda *a, **kw: None)
        app._idle_logout()
        assert called["iface"] == "gui"
        app.auth.logout.assert_called_once()

    def test_switch_to_cli_cancelled(self, app, monkeypatch):
        from education_system import switch
        monkeypatch.setattr(
            "tkinter.messagebox.askyesno", lambda *a, **kw: False)
        called = {"hit": False}
        monkeypatch.setattr(
            switch, "request_switch",
            lambda *a, **kw: called.__setitem__("hit", True))
        app._switch_to_cli()
        assert called["hit"] is False

    def test_switch_to_cli_confirmed(self, app, monkeypatch):
        from education_system import switch
        monkeypatch.setattr(
            "tkinter.messagebox.askyesno", lambda *a, **kw: True)
        captured = {}
        monkeypatch.setattr(
            switch, "request_switch",
            lambda sys, iface: captured.update(system=sys, iface=iface))
        app._switch_to_cli()
        assert captured == {"system": "college", "iface": "cli"}

    def test_on_close_logs_out(self, app):
        app._on_close()
        app.auth.logout.assert_called_once()

    @pytest.mark.parametrize(
        "method_name",
        [
            # Spot-check a sampling of the ``open_*`` handlers exist and
            # are bound methods. Mounting each window would require deep
            # mocking of every domain — we settle for verifying the
            # surface area instead.
            "open_student_directory", "open_add_student",
            "open_search_students", "open_student_profile",
            "open_courses", "open_subjects", "open_class_groups",
            "open_timetable", "open_attendance", "open_homework",
            "open_gradebook", "open_predicted_grades",
            "open_mock_exams", "open_exam_entries", "open_results_day",
            "open_ucas", "open_personal_statements", "open_references",
            "open_offers", "open_apprenticeships",
            "open_university_visits", "open_careers", "open_destinations",
            "open_epq", "open_work_experience", "open_room_booking",
            "open_medical_records", "open_tutor_groups",
            "open_behaviour", "open_safeguarding", "open_wellbeing",
            "open_student_wellbeing", "open_prevent_duty",
            "open_attendance_concerns", "open_staff", "open_parents",
            "open_parents_evenings", "open_notices", "open_messaging",
            "open_fees", "open_bursaries", "open_trips_payments",
            "open_receipts", "open_report_attendance",
            "open_report_grades", "open_progress", "open_kpi_dashboard",
            "open_data_dashboard", "open_progress_dashboard",
            "open_mobile_dashboard", "open_export", "open_audit_reports",
            "open_data_export", "open_gdpr", "open_risk_management",
            "open_change_password", "open_mfa", "open_user_accounts",
            "open_settings", "open_user_management", "open_compliance",
            "open_governance", "open_policies", "open_absence_requests",
            "open_academic_year", "open_accessibility",
            "open_activity_feed", "open_advanced_search",
            "open_admissions", "open_onboarding", "open_bulk_operations",
            "open_alumni", "open_calendar", "open_lesson_plans",
            "open_cover", "open_cover_agency", "open_assignments",
            "open_enrichment", "open_library", "open_study_planner",
            "open_baseline_assessment", "open_target_setting", "open_ilp",
            "open_intervention_tracking", "open_value_added",
            "open_early_warning", "open_observations",
            "open_self_assessment", "open_quality_assurance",
            "open_sef_builder", "open_send", "open_disciplinary",
            "open_student_support", "open_peer_mentoring",
            "open_first_aid", "open_emergency", "open_health_safety",
            "open_assets", "open_equality_diversity", "open_complaints",
            "open_feedback", "open_surveys", "open_student_council",
            "open_transport", "open_staff_hr", "open_departments",
            "open_staff_absence", "open_staff_wellbeing",
            "open_recruitment", "open_appraisals", "open_cpd",
            "open_dbs_checks", "open_visitors", "open_announcements",
            "open_notifications", "open_letter_templates",
            "open_document_hub", "open_attachments", "open_census_ilr",
            "open_expense_claims", "open_funding", "open_about",
            "open_multi_language", "open_todo",
        ],
    )
    def test_open_handlers_exist(self, app, method_name):
        assert callable(getattr(app, method_name))
