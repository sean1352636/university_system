"""Submitting a UCAS application: the derived status and the email.

The GUI no longer offers a status dropdown next to a submission-date
field, because keeping the two consistent by hand is how a Draft ends up
dated last Tuesday. The status is now a function of the date, and the
transition into Submitted is what tells the student.
"""

from __future__ import annotations

import importlib
import sqlite3

import pytest

#: Sixth-form data modules whose ``DB_PATH`` must point at the temp file.
_SF_MODULES = (
    "education_system.systems.sixth_form.domain.learners.students.students",
    "education_system.systems.sixth_form.domain.progression.university.ucas",
)


@pytest.fixture
def sf(tmp_path, monkeypatch):
    """One student with a draft application, on a throwaway database."""
    db = str(tmp_path / "sixthform.db")
    loaded = {}
    for dotted in _SF_MODULES:
        module = importlib.import_module(dotted)
        monkeypatch.setattr(module, "DB_PATH", db, raising=False)
        if hasattr(module, "_DB_READY"):
            monkeypatch.setattr(module, "_DB_READY", False, raising=False)
        loaded[dotted.rsplit(".", 1)[-1]] = module
    students, ucas = loaded["students"], loaded["ucas"]
    students.init_db()
    ucas.init_db()

    # Inserted directly: ``create_student`` provisions a login in the
    # shared auth database and registers a cross-system journey, neither
    # of which is under test and both of which would be written for real.
    conn = sqlite3.connect(db)
    conn.execute(
        """INSERT INTO students (student_id, first_name, last_name, email,
                                 date_of_birth, subject_1, subject_2,
                                 subject_3, status)
           VALUES ('SF001', 'Robin', 'Fielding',
                   'robin.fielding@example.test', '2007-03-14',
                   'Mathematics', 'Physics', 'Chemistry', 'Active')""")
    conn.commit()
    conn.close()
    return ucas


class TestDeriveStatus:
    def test_no_date_is_a_draft(self, sf):
        assert sf.derive_status(None, "") == "Draft"
        assert sf.derive_status("Draft", None) == "Draft"

    def test_a_date_means_submitted(self, sf):
        assert sf.derive_status(None, "2026-01-15") == "Submitted"
        assert sf.derive_status("Draft", "2026-01-15") == "Submitted"

    def test_removing_the_date_returns_it_to_draft(self, sf):
        assert sf.derive_status("Submitted", "") == "Draft"

    @pytest.mark.parametrize("later", ["Replied", "Confirmed", "Clearing"])
    def test_later_statuses_are_left_alone(self, sf, later):
        """Deriving these would be a downgrade.

        An application the universities have already replied to still has
        a submission date on it. Re-deriving on every save would walk
        'Replied' back to 'Submitted' each time somebody edited the notes.
        """
        assert sf.derive_status(later, "2026-01-15") == later
        assert sf.derive_status(later, "") == later


class TestSubmissionEmail:
    def _application(self, sf, **over):
        payload = {"student_id": "SF001", "cycle_year": 2027,
                   "ucas_id": "1234567890"}
        payload.update(over)
        return sf.create_application(payload)

    def test_sent_on_submission_with_the_choices_listed(
            self, sf, monkeypatch):
        from education_system.systems.sixth_form.domain.progression.university import submission_notice
        captured: list[dict] = []

        def _capture(name, context, **kwargs):
            captured.append({"name": name, **context, **kwargs})
            return type("M", (), {"message_id": 7})()

        import education_system.systems.sixth_form.domain.operations.communications.messages.email_templates as tpl
        monkeypatch.setattr(tpl, "send_from_template", _capture)

        app = self._application(sf)
        sf.create_choice(app.application_id, {
            "choice_order": 1, "university": "Elsewhere University",
            "course_code": "ENG1", "course_name": "Mechanical Engineering",
            "entry_year": 2027})
        app = sf.update_application(app.application_id, {
            "status": sf.derive_status(app.status, "2026-10-15"),
            "submitted_at": "2026-10-15"})
        assert app.status == "Submitted"

        msg = submission_notice.send_submission_email(app)
        assert msg is not None
        assert len(captured) == 1
        ctx = captured[0]
        assert ctx["name"] == "ucas_application_submitted"
        assert ctx["to_address"] == "robin.fielding@example.test"
        assert ctx["submitted_at"] == "2026-10-15"
        assert ctx["ucas_id"] == "1234567890"
        assert ctx["n_choices"] == "1"
        assert "Elsewhere University" in ctx["choices_block"]
        # The student is checking that the slots they left empty really
        # are empty, so the count of them is part of the confirmation.
        assert "4 of your 5 choice slots" in ctx["choices_block"]

    def test_an_application_with_no_choices_says_so(self, sf, monkeypatch):
        from education_system.systems.sixth_form.domain.progression.university import submission_notice
        captured: list[dict] = []
        import education_system.systems.sixth_form.domain.operations.communications.messages.email_templates as tpl
        monkeypatch.setattr(
            tpl, "send_from_template",
            lambda name, context, **kw: (
                captured.append(context),
                type("M", (), {"message_id": 7})())[1])

        app = self._application(sf, submitted_at="2026-10-15",
                                status="Submitted")
        submission_notice.send_submission_email(app)
        assert "No choices were listed" in captured[0]["choices_block"]

    def test_a_failing_send_returns_none_rather_than_raising(
            self, sf, monkeypatch):
        """The submission is already saved by the time this runs."""
        from education_system.systems.sixth_form.domain.progression.university import submission_notice
        import education_system.systems.sixth_form.domain.operations.communications.messages.email_templates as tpl

        def _boom(*_a, **_k):
            raise RuntimeError("mail server down")

        monkeypatch.setattr(tpl, "send_from_template", _boom)
        app = self._application(sf, submitted_at="2026-10-15",
                                status="Submitted")
        assert submission_notice.send_submission_email(app) is None

    def test_a_student_with_no_address_is_skipped(self, sf, monkeypatch):
        from education_system.systems.sixth_form.domain.progression.university import submission_notice
        conn = sqlite3.connect(str(sf.DB_PATH))
        conn.execute("UPDATE students SET email = '' WHERE student_id='SF001'")
        conn.commit()
        conn.close()
        app = self._application(sf, submitted_at="2026-10-15",
                                status="Submitted")
        assert submission_notice.send_submission_email(app) is None
