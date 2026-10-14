"""Statements that live on a UCAS application, and reviewer feedback.

A personal statement can be in one of two places: a draft in the
``personal_statements`` table, or the single column on the student's
UCAS application. ``push_to_ucas`` has always gone one way; these cover
the way back, and the feedback email that closes the review loop.
"""

from __future__ import annotations

import importlib
import sqlite3

import pytest

_SF_MODULES = (
    "education_system.systems.sixth_form.domain.learners.students.students",
    "education_system.systems.sixth_form.domain.progression.university.ucas",
    "education_system.systems.sixth_form.domain.progression."
    "personal_statements.personal_statements",
)


@pytest.fixture
def sf(tmp_path, monkeypatch):
    """One student, on a throwaway database. Returns (ucas, statements)."""
    db = str(tmp_path / "sixthform.db")
    loaded = {}
    for dotted in _SF_MODULES:
        module = importlib.import_module(dotted)
        monkeypatch.setattr(module, "DB_PATH", db, raising=False)
        if hasattr(module, "_DB_READY"):
            monkeypatch.setattr(module, "_DB_READY", False, raising=False)
        loaded[dotted.rsplit(".", 1)[-1]] = module
    loaded["students"].init_db()
    loaded["ucas"].init_db()
    loaded["personal_statements"].init_db()

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
    return loaded["ucas"], loaded["personal_statements"]


BODY = "I have wanted to study engineering since I took apart a radio."


class TestUcasOnlyStatements:
    def test_a_statement_written_on_an_application_is_surfaced(self, sf):
        """The reported symptom: it did not show up here at all."""
        ucas, ps = sf
        app = ucas.create_application({
            "student_id": "SF001", "cycle_year": 2027,
            "personal_statement": BODY})
        assert ps.list_statements() == []
        found = ps.ucas_only_statements()
        assert [u.application_id for u in found] == [app.application_id]
        assert found[0].body == BODY
        assert found[0].char_count == len(BODY)
        assert found[0].cycle_year == 2027

    def test_an_application_with_no_statement_is_not_listed(self, sf):
        ucas, ps = sf
        ucas.create_application({"student_id": "SF001", "cycle_year": 2027})
        assert ps.ucas_only_statements() == []

    def test_a_pushed_draft_is_not_listed_twice(self, sf):
        """A draft pushed to an application is in both places.

        Listing it as 'only on the application' would suggest a second,
        different statement.
        """
        ucas, ps = sf
        ucas.create_application({"student_id": "SF001", "cycle_year": 2027})
        draft = ps.create_statement({"student_id": "SF001", "body": BODY})
        ps.push_to_ucas(draft.statement_id)
        assert ps.ucas_only_statements() == []

    def test_whitespace_alone_does_not_make_it_a_different_statement(
            self, sf):
        ucas, ps = sf
        ucas.create_application({
            "student_id": "SF001", "cycle_year": 2027,
            "personal_statement": f"  {BODY}\n"})
        ps.create_statement({"student_id": "SF001", "body": BODY})
        assert ps.ucas_only_statements() == []

    def test_a_genuinely_different_statement_is_listed(self, sf):
        ucas, ps = sf
        ucas.create_application({
            "student_id": "SF001", "cycle_year": 2027,
            "personal_statement": BODY})
        ps.create_statement({"student_id": "SF001",
                             "body": "An entirely different draft."})
        assert len(ps.ucas_only_statements()) == 1

    def test_filtering_by_student(self, sf):
        ucas, ps = sf
        ucas.create_application({
            "student_id": "SF001", "cycle_year": 2027,
            "personal_statement": BODY})
        assert len(ps.ucas_only_statements(student_id="SF001")) == 1
        assert ps.ucas_only_statements(student_id="SF999") == []


class TestImportFromUcas:
    def test_import_creates_a_reviewable_draft(self, sf):
        ucas, ps = sf
        app = ucas.create_application({
            "student_id": "SF001", "cycle_year": 2027,
            "personal_statement": BODY})
        draft = ps.import_from_ucas(app.application_id)
        assert draft.student_id == "SF001"
        assert draft.body == BODY
        assert draft.status == ps.DEFAULT_STATUS
        assert str(app.application_id) in (draft.title or "")

    def test_the_application_keeps_its_own_copy(self, sf):
        """An import is a copy, not a move.

        The application's column is the one that goes to UCAS; nothing
        in this module should be able to empty it.
        """
        ucas, ps = sf
        app = ucas.create_application({
            "student_id": "SF001", "cycle_year": 2027,
            "personal_statement": BODY})
        ps.import_from_ucas(app.application_id)
        assert ucas.get_application(
            app.application_id).personal_statement == BODY

    def test_an_imported_statement_stops_being_listed_as_ucas_only(self, sf):
        ucas, ps = sf
        app = ucas.create_application({
            "student_id": "SF001", "cycle_year": 2027,
            "personal_statement": BODY})
        ps.import_from_ucas(app.application_id)
        assert ps.ucas_only_statements() == []

    def test_unknown_application_is_refused(self, sf):
        _ucas, ps = sf
        with pytest.raises(ps.ValidationError):
            ps.import_from_ucas(999_999)

    def test_an_application_with_nothing_on_it_is_refused(self, sf):
        ucas, ps = sf
        app = ucas.create_application({"student_id": "SF001",
                                       "cycle_year": 2027})
        with pytest.raises(ps.ValidationError) as e:
            ps.import_from_ucas(app.application_id)
        assert "no personal statement" in str(e.value)


class TestFeedbackEmail:
    def _reviewed(self, ps, **over):
        payload = {"student_id": "SF001", "body": BODY,
                   "title": "First draft", "status": "In Review",
                   "reviewer": "A. Tutor",
                   "feedback": "Cut the second paragraph."}
        payload.update(over)
        return ps.create_statement(payload)

    def _capture(self, monkeypatch):
        captured: list[dict] = []
        import education_system.systems.sixth_form.domain.operations.communications.messages.email_templates as tpl

        def _send(name, context, **kwargs):
            captured.append({"name": name, **context, **kwargs})
            return type("M", (), {"message_id": 42})()

        monkeypatch.setattr(tpl, "send_from_template", _send)
        return captured

    def test_feedback_reaches_the_student(self, sf, monkeypatch):
        _ucas, ps = sf
        captured = self._capture(monkeypatch)
        from education_system.systems.sixth_form.domain.progression.university import feedback_notice
        msg = feedback_notice.send_feedback_email(self._reviewed(ps))
        assert msg is not None
        ctx = captured[0]
        assert ctx["name"] == "personal_statement_feedback"
        assert ctx["to_address"] == "robin.fielding@example.test"
        assert ctx["feedback"] == "Cut the second paragraph."
        assert ctx["reviewer"] == "A. Tutor"
        assert ctx["status"] == "In Review"

    def test_an_explicit_reviewer_overrides_the_stored_one(
            self, sf, monkeypatch):
        _ucas, ps = sf
        captured = self._capture(monkeypatch)
        from education_system.systems.sixth_form.domain.progression.university import feedback_notice
        feedback_notice.send_feedback_email(
            self._reviewed(ps), reviewer="B. Head of Sixth")
        assert captured[0]["reviewer"] == "B. Head of Sixth"

    def test_headroom_is_reported_when_within_the_limits(
            self, sf, monkeypatch):
        _ucas, ps = sf
        captured = self._capture(monkeypatch)
        from education_system.systems.sixth_form.domain.progression.university import feedback_notice
        feedback_notice.send_feedback_email(self._reviewed(ps))
        assert "still available" in captured[0]["limits_block"]

    def test_an_overrun_is_reported_as_the_first_job(self, sf, monkeypatch):
        """Over the limit is not 'nearly there' — UCAS refuses it."""
        _ucas, ps = sf
        captured = self._capture(monkeypatch)
        from education_system.systems.sixth_form.domain.progression.university import feedback_notice
        # Built past the limit directly: create_statement would refuse it,
        # which is the point — the overrun this reports comes from a
        # draft that predates the check or was cut too fine.
        statement = self._reviewed(ps)
        statement.char_count = ps.MAX_CHARS + 300
        feedback_notice.send_feedback_email(statement)
        block = captured[0]["limits_block"]
        assert "300 characters over" in block
        assert "will not accept it" in block

    def test_nothing_is_sent_when_there_is_no_feedback(self, sf, monkeypatch):
        _ucas, ps = sf
        captured = self._capture(monkeypatch)
        from education_system.systems.sixth_form.domain.progression.university import feedback_notice
        assert feedback_notice.send_feedback_email(
            self._reviewed(ps, feedback="")) is None
        assert captured == []

    def test_a_failing_send_returns_none_rather_than_raising(
            self, sf, monkeypatch):
        """The review is already saved by the time this runs."""
        _ucas, ps = sf
        import education_system.systems.sixth_form.domain.operations.communications.messages.email_templates as tpl

        def _boom(*_a, **_k):
            raise RuntimeError("mail server down")

        monkeypatch.setattr(tpl, "send_from_template", _boom)
        from education_system.systems.sixth_form.domain.progression.university import feedback_notice
        assert feedback_notice.send_feedback_email(self._reviewed(ps)) is None

    def test_a_student_with_no_address_is_skipped(self, sf, monkeypatch):
        _ucas, ps = sf
        captured = self._capture(monkeypatch)
        conn = sqlite3.connect(str(ps.DB_PATH))
        conn.execute("UPDATE students SET email='' WHERE student_id='SF001'")
        conn.commit()
        conn.close()
        from education_system.systems.sixth_form.domain.progression.university import feedback_notice
        assert feedback_notice.send_feedback_email(self._reviewed(ps)) is None
        assert captured == []
