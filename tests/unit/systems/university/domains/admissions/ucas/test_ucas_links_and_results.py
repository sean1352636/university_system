"""Links, internal notes, results day, and the clearing reconciliation.

The parts of the university's UCAS module that are wholly ours: the link
between a sixth-form choice and our own records, the notes the sixth form
never sees, the results-day board that makes good on the offer email, and
the join to clearing that the ``ucas_id`` column has been waiting for.
"""

from __future__ import annotations

import pytest

from education_system.systems.university.domains.admissions.domain.ucas import (
    results_day,
)


def _patch_results(monkeypatch, grades, *, released=True, release_at=None):
    """Stand in for the sixth form adapter's ``exam_results_for_admissions``."""
    rows = [{"subject": subject, "grade": grade,
             "qualification_type": "A Level", "released": released,
             "release_at": release_at, "season": "Summer", "year": 2027}
            for subject, grade in grades.items()]
    monkeypatch.setattr(results_day, "_results_for",
                        lambda student_id, year=None: [dict(r) for r in rows])


@pytest.fixture
def link(ucas_env):
    """A link, created the way a decision creates one."""
    return ucas_env.links.ensure_link_for_choice(
        sf_application_id=ucas_env.application_id,
        sf_choice_id=ucas_env.our_choice_id,
        sf_student_id=ucas_env.student_id,
        linked_by="a.officer",
    )


class TestLinks:
    def test_a_link_records_who_made_it(self, link):
        assert link.sf_choice_id
        assert link.linked_by == "a.officer"
        assert link.status == "open"

    def test_linking_the_same_choice_twice_returns_the_same_link(
            self, ucas_env, link):
        again = ucas_env.links.ensure_link_for_choice(
            sf_application_id=ucas_env.application_id,
            sf_choice_id=ucas_env.our_choice_id,
            sf_student_id=ucas_env.student_id,
            linked_by="someone.else",
        )
        assert again.link_id == link.link_id
        assert again.linked_by == "a.officer"

    def test_links_can_be_found_by_student(self, ucas_env, link):
        found = ucas_env.links.list_links(sf_student_id=ucas_env.student_id)
        assert [c.link_id for c in found] == [link.link_id]

    def test_an_unknown_status_is_refused(self, ucas_env, link):
        with pytest.raises(ucas_env.links.UcasLinkError):
            ucas_env.links.set_link_status(link.link_id, "abandoned")

    def test_status_can_be_moved_through_its_states(self, ucas_env, link):
        assert ucas_env.links.set_link_status(
            link.link_id, "withdrawn").status == "withdrawn"

    def test_attaching_an_application_that_does_not_exist_is_refused(
            self, ucas_env, link):
        with pytest.raises(ucas_env.links.UcasLinkError):
            ucas_env.links.attach_uni_application(link.link_id, 424242)

    def test_attaching_a_real_application_sticks(self, ucas_env, link):
        conn = ucas_env.uni_connection()
        conn.execute("INSERT INTO admission_applications (application_id) "
                     "VALUES (77)")
        conn.commit()
        conn.close()
        out = ucas_env.links.attach_uni_application(link.link_id, 77)
        assert out.uni_application_id == 77


class TestInternalNotes:
    def test_a_note_needs_a_body(self, ucas_env, link):
        with pytest.raises(ucas_env.links.UcasLinkError):
            ucas_env.links.add_note(link.link_id, "   ")

    def test_a_note_cannot_hang_off_a_link_that_is_not_there(self, ucas_env):
        with pytest.raises(ucas_env.links.UcasLinkError):
            ucas_env.links.add_note(9999, "orphan")

    def test_notes_come_back_newest_first(self, ucas_env, link):
        ucas_env.links.add_note(link.link_id, "Interview booked",
                                author="a.officer")
        ucas_env.links.add_note(link.link_id, "Strong personal statement",
                                author="b.officer")
        bodies = [n.body for n in ucas_env.links.list_notes(link.link_id)]
        assert "Strong personal statement" in bodies
        assert len(bodies) == 2

    def test_a_note_can_be_corrected_and_removed(self, ucas_env, link):
        note = ucas_env.links.add_note(link.link_id, "Typo here")
        assert ucas_env.links.update_note(
            note.note_id, "Corrected").body == "Corrected"
        assert ucas_env.links.delete_note(note.note_id) is True
        assert ucas_env.links.delete_note(note.note_id) is False


class TestGradeArithmetic:
    """Pure functions — the part of results day that must never guess."""

    @pytest.mark.parametrize("text,expected", [
        ("ABB", ["A", "B", "B"]),
        ("A*AA", ["A*", "A", "A"]),
        ("bbc", ["B", "B", "C"]),
        ("ABB including B in Mathematics", ["A", "B", "B"]),
        ("see offer letter", None),
        ("", None),
        (None, None),
    ])
    def test_parsing_a_condition(self, text, expected):
        assert results_day.parse_grade_profile(text) == expected

    @pytest.mark.parametrize("required,achieved,met", [
        (["A", "B", "B"], ["A", "A", "B"], True),
        (["A", "B", "B"], ["A", "B", "B"], True),
        (["A", "B", "B"], ["A", "B", "C"], False),
        (["A*", "A", "A"], ["A", "A", "A"], False),
        (["A*", "A", "A"], ["A*", "A", "A"], True),
        # A fourth subject never hurts.
        (["A", "B", "B"], ["A", "A", "A", "C"], True),
        # Fewer results than the offer asks for is not "met".
        (["A", "B", "B"], ["A", "B"], False),
    ])
    def test_whether_a_profile_is_met(self, required, achieved, met):
        assert results_day.profile_is_met(required, achieved) is met


class TestResultsDayBoard:
    """The promise the offer email makes, and who is allowed to keep it."""

    @pytest.fixture
    def firm_conditional(self, ucas_env):
        """Our choice, holding a firm conditional offer of ABB."""
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Conditional Offer",
            offer_terms="ABB",
            terms={"grade_requirement": "ABB"},
            issued_by="a.officer")
        ucas_env.sf_ucas.update_choice(ucas_env.our_choice_id,
                                       {"final_decision": "Firm"})
        return ucas_env

    def _grades(self, monkeypatch, grades):
        _patch_results(monkeypatch, grades)

    def test_met_conditions_are_recognised(self, firm_conditional,
                                           monkeypatch):
        self._grades(monkeypatch, {"Mathematics": "A", "Physics": "A",
                                   "Chemistry": "B"})
        board = results_day.board()
        assert len(board) == 1
        assert board[0].verdict == results_day.MET
        assert board[0].is_firm

    def test_missed_conditions_are_recognised(self, firm_conditional,
                                              monkeypatch):
        self._grades(monkeypatch, {"Mathematics": "B", "Physics": "C",
                                   "Chemistry": "C"})
        assert results_day.board()[0].verdict == results_day.MISSED

    def test_no_results_yet_is_pending_not_a_rejection(self, firm_conditional,
                                                       monkeypatch):
        self._grades(monkeypatch, {})
        candidate = results_day.board()[0]
        assert candidate.verdict == results_day.PENDING

    def test_partial_results_are_pending(self, firm_conditional, monkeypatch):
        self._grades(monkeypatch, {"Mathematics": "A"})
        assert results_day.board()[0].verdict == results_day.PENDING

    def _offer(self, ucas_env, text):
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Conditional Offer",
            offer_terms=text, terms={"grade_requirement": text},
            issued_by="a.officer")
        ucas_env.sf_ucas.update_choice(ucas_env.our_choice_id,
                                       {"final_decision": "Firm"})

    def test_an_unreadable_prose_condition_goes_to_a_person(
            self, ucas_env, monkeypatch):
        """What cannot be read word by word is never treated as checked."""
        self._offer(ucas_env, "ABB excluding General Studies")
        self._grades(monkeypatch, {"Mathematics": "B", "Physics": "A",
                                   "Chemistry": "A"})
        assert results_day.board()[0].verdict == results_day.REVIEW

    def test_a_subject_requirement_is_checked_in_full(self, ucas_env,
                                                      monkeypatch):
        self._offer(ucas_env, "ABB including B in Mathematics")
        self._grades(monkeypatch, {"Mathematics": "B", "Physics": "A",
                                   "Chemistry": "A"})
        assert results_day.board()[0].verdict == results_day.MET
        self._grades(monkeypatch, {"Mathematics": "C", "Physics": "A",
                                   "Chemistry": "A"})
        assert results_day.board()[0].verdict == results_day.MISSED

    def test_a_tariff_offer_is_checked(self, ucas_env, monkeypatch):
        self._offer(ucas_env, "112 UCAS points")
        self._grades(monkeypatch, {"Mathematics": "B", "Physics": "C",
                                   "Chemistry": "C"})          # 40+32+32
        assert results_day.board()[0].verdict == results_day.MET

    def test_applicants_without_a_reply_are_not_on_the_board(self, ucas_env,
                                                             monkeypatch):
        """No firm or insurance choice means results day is not ours yet."""
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Conditional Offer",
            offer_terms="ABB", issued_by="a.officer")
        self._grades(monkeypatch, {"Mathematics": "A"})
        assert results_day.board() == []


class TestConfirmingAPlace:
    @pytest.fixture
    def firm_met(self, ucas_env, monkeypatch):
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Conditional Offer",
            offer_terms="ABB", terms={"grade_requirement": "ABB"},
            issued_by="a.officer")
        ucas_env.sf_ucas.update_choice(ucas_env.our_choice_id,
                                       {"final_decision": "Firm"})
        _patch_results(monkeypatch, {"Mathematics": "A", "Physics": "A",
                                     "Chemistry": "B"})
        return ucas_env

    def test_confirming_makes_the_offer_unconditional(self, firm_met):
        results_day.confirm_place(firm_met.our_choice_id,
                                  decided_by="a.officer")
        choice = firm_met.uni_ucas._sf().get_choice(firm_met.our_choice_id)
        assert choice.decision_status == "Unconditional Offer"

    def test_confirming_settles_the_sixth_forms_application(self, firm_met):
        """What the handover reads as the record of results day."""
        results_day.confirm_place(firm_met.our_choice_id,
                                  decided_by="a.officer")
        app = firm_met.sf_ucas.get_application(firm_met.application_id)
        assert app.status == "Confirmed"

    def test_a_confirmation_is_attributed_like_any_other_decision(
            self, firm_met):
        results_day.confirm_place(firm_met.our_choice_id,
                                  decided_by="results.officer")
        last = firm_met.decision_log.last_decision(firm_met.our_choice_id)
        assert last.decided_by == "results.officer"
        assert last.decision_status == "Unconditional Offer"

    def test_auto_confirm_defaults_to_a_dry_run(self, firm_met):
        would = results_day.auto_confirm(decided_by="a.officer")
        assert [c.choice_id for c in would] == [firm_met.our_choice_id]
        # Nothing actually changed.
        assert firm_met.uni_ucas._sf().get_choice(
            firm_met.our_choice_id).decision_status == "Conditional Offer"

    def test_auto_confirm_when_asked_actually_confirms(self, firm_met):
        done = results_day.auto_confirm(decided_by="a.officer", dry_run=False)
        assert len(done) == 1
        assert firm_met.uni_ucas._sf().get_choice(
            firm_met.our_choice_id).decision_status == "Unconditional Offer"

    def test_auto_confirm_leaves_a_missed_condition_alone(self, ucas_env,
                                                          monkeypatch):
        """Confirming a met condition is a promise already made. Rejecting
        a missed one is a judgement, and not the program's to make."""
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Conditional Offer",
            offer_terms="ABB", terms={"grade_requirement": "ABB"},
            issued_by="a.officer")
        ucas_env.sf_ucas.update_choice(ucas_env.our_choice_id,
                                       {"final_decision": "Firm"})
        _patch_results(monkeypatch, {"Mathematics": "C", "Physics": "C",
                                     "Chemistry": "D"})
        assert results_day.auto_confirm(dry_run=False) == []
        assert ucas_env.uni_ucas._sf().get_choice(
            ucas_env.our_choice_id).decision_status == "Conditional Offer"

    def test_declining_records_a_rejection_with_a_reason(self, firm_met):
        results_day.decline_place(firm_met.our_choice_id,
                                  decided_by="a.officer",
                                  reason="Missed by two grades.")
        assert firm_met.uni_ucas._sf().get_choice(
            firm_met.our_choice_id).decision_status == "Rejected"
        assert firm_met.decision_log.last_decision(
            firm_met.our_choice_id).notes == "Missed by two grades."


class TestResultsEmbargo:
    """Nothing is confirmed or e-mailed before results are public."""

    @pytest.fixture
    def embargoed(self, ucas_env, monkeypatch):
        ucas_env.uni_ucas.record_decision(
            ucas_env.our_choice_id, "Conditional Offer",
            offer_terms="ABB", terms={"grade_requirement": "ABB"},
            issued_by="a.officer")
        ucas_env.sf_ucas.update_choice(ucas_env.our_choice_id,
                                       {"final_decision": "Firm"})
        _patch_results(monkeypatch, {"Mathematics": "A", "Physics": "A",
                                     "Chemistry": "B"},
                       released=False, release_at="2999-08-13 08:00")
        return ucas_env

    def test_a_met_verdict_is_worked_out_but_held(self, embargoed):
        candidate = results_day.board()[0]
        assert candidate.verdict == results_day.MET
        assert candidate.is_embargoed

    def test_confirming_under_embargo_holds_and_sends_nothing(self, embargoed):
        out = results_day.confirm_place(embargoed.our_choice_id,
                                        decided_by="a.officer")
        assert isinstance(out, results_day.Hold)
        assert out.held_by == "a.officer"
        assert embargoed.uni_ucas._sf().get_choice(
            embargoed.our_choice_id).decision_status == "Conditional Offer"
        assert results_day.board()[0].hold is not None

    def test_a_hold_is_applied_once_results_are_released(self, embargoed,
                                                         monkeypatch):
        results_day.auto_confirm(decided_by="a.officer", dry_run=False)
        assert embargoed.uni_ucas._sf().get_choice(
            embargoed.our_choice_id).decision_status == "Conditional Offer"
        _patch_results(monkeypatch, {"Mathematics": "A", "Physics": "A",
                                     "Chemistry": "B"})
        counts = results_day.release_held(released_by="b.officer")
        assert counts["Applied"] == 1
        assert embargoed.uni_ucas._sf().get_choice(
            embargoed.our_choice_id).decision_status == "Unconditional Offer"
        hold = results_day.list_holds(status="Applied")[0]
        assert hold.released_by == "b.officer" and hold.released_at


class TestClearingReconciliation:
    def _add_clearing_row(self, ucas_env, ucas_id, name="Robin Fielding"):
        conn = ucas_env.uni_connection()
        conn.execute(
            "INSERT INTO clearing_applications (applicant_name, ucas_id, "
            "preferred_course) VALUES (?, ?, 'Mechanical Engineering')",
            (name, ucas_id))
        conn.commit()
        conn.close()

    def test_a_rejection_finds_the_applicant_already_in_clearing(
            self, ucas_env):
        self._add_clearing_row(ucas_env, "1234567890")
        choice = ucas_env.sf_ucas.get_choice(ucas_env.our_choice_id)
        match = ucas_env.clearing_link.note_rejection(
            choice, ucas_env.student_id)
        assert match is not None
        assert match.ucas_decision == "Rejected"
        assert match.sf_choice_id == ucas_env.our_choice_id

    def test_a_ucas_id_typed_with_spaces_still_matches(self, ucas_env):
        """Clearing ids are typed in by hand on the phone."""
        self._add_clearing_row(ucas_env, "123 456 7890")
        assert ucas_env.clearing_link.find_clearing_application(
            "1234567890") is not None

    def test_no_clearing_application_is_not_an_error(self, ucas_env):
        choice = ucas_env.sf_ucas.get_choice(ucas_env.our_choice_id)
        assert ucas_env.clearing_link.note_rejection(
            choice, ucas_env.student_id) is None

    def test_unmatched_lists_only_people_we_hold_no_choice_for(self, ucas_env):
        self._add_clearing_row(ucas_env, "1234567890")           # ours
        self._add_clearing_row(ucas_env, "9999999999", "A Stranger")
        unmatched = ucas_env.clearing_link.unmatched_clearing_applications()
        assert [m.ucas_id for m in unmatched] == ["9999999999"]

    def test_referring_twice_does_not_create_a_second_applicant(
            self, ucas_env, monkeypatch):
        created = []

        class _FakeService:
            def submit_clearing_application(self, **kwargs):
                created.append(kwargs)
                conn = ucas_env.uni_connection()
                cur = conn.execute(
                    "INSERT INTO clearing_applications (applicant_name, "
                    "ucas_id) VALUES (?, ?)",
                    (kwargs["applicant_name"], kwargs["ucas_id"]))
                conn.commit()
                new_id = cur.lastrowid
                conn.close()
                return new_id

        monkeypatch.setattr(ucas_env.clearing_link, "_service",
                            lambda: _FakeService())
        first = ucas_env.clearing_link.refer_to_clearing(
            ucas_env.our_choice_id, referred_by="a.officer")
        second = ucas_env.clearing_link.refer_to_clearing(
            ucas_env.our_choice_id, referred_by="a.officer")
        assert first == second
        assert len(created) == 1

    def test_referring_an_unknown_choice_is_refused(self, ucas_env):
        with pytest.raises(ValueError):
            ucas_env.clearing_link.refer_to_clearing(999999)


class TestTheAuditWriteItself:
    """The fixture stubs the audit sink so the other tests do not need a
    real audit database. This one does not stub it — the mirroring is the
    whole point of the change and deserves to be exercised for real."""

    def test_a_decision_reaches_the_platform_audit_log(self, ucas_env,
                                                       tmp_path, monkeypatch):
        import sqlite3

        from education_system.platform.governance import audit as audit_pkg
        from education_system.systems.university.domains.admissions.domain.ucas import (
            decision_log,
        )

        audit_db = str(tmp_path / "audit.db")
        real_logger = audit_pkg.AuditLogger
        monkeypatch.setattr(
            audit_pkg, "AuditLogger",
            lambda system_key, db_path=None: real_logger(system_key, audit_db))
        # Undo the fixture's stub for this test only.
        monkeypatch.setattr(decision_log, "_audit", ucas_env.real_audit)

        decision_log.record(
            sf_choice_id=ucas_env.our_choice_id,
            decision_status="Unconditional Offer",
            sf_student_id=ucas_env.student_id,
            decided_by="a.officer",
        )

        conn = sqlite3.connect(audit_db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE resource_type = 'ucas_choice'"
        ).fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0]["resource_id"] == str(ucas_env.our_choice_id)
        assert rows[0]["username"] == "a.officer"


class TestPipelineLink:
    def test_an_existing_reference_is_adopted_not_duplicated(self, ucas_env):
        conn = ucas_env.uni_connection()
        conn.execute("INSERT INTO admission_applications "
                     "(application_id, external_reference) VALUES (5, ?)",
                     ("1234567890",))
        conn.commit()
        conn.close()
        assert ucas_env.pipeline_link.find_application_by_reference(
            "1234567890") == 5

    def test_a_link_that_already_has_an_application_is_left_alone(
            self, ucas_env):
        conn = ucas_env.uni_connection()
        conn.execute("INSERT INTO admission_applications (application_id) "
                     "VALUES (9)")
        conn.commit()
        conn.close()
        link = ucas_env.links.ensure_link_for_choice(
            sf_application_id=ucas_env.application_id,
            sf_choice_id=ucas_env.our_choice_id,
            sf_student_id=ucas_env.student_id)
        ucas_env.links.attach_uni_application(link.link_id, 9)
        link = ucas_env.links.get_link(link.link_id)
        choice = ucas_env.sf_ucas.get_choice(ucas_env.our_choice_id)
        assert ucas_env.pipeline_link.ensure_application_for_link(
            link, choice=choice) == 9

    def test_an_unknown_reference_finds_nothing(self, ucas_env):
        assert ucas_env.pipeline_link.find_application_by_reference(
            "0000000000") is None
        assert ucas_env.pipeline_link.find_application_by_reference("") is None
