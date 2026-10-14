"""The apprentice domain: the record, the lifecycle, breaks and withdrawals.

Most of this is pure — dates in, judgement out — so it is tested without
a database. The last class drives the rules through
``apprentice_service.change_status`` on the conftest's throwaway
database, because the point of the rules is what the service does with
them.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices import lifecycle
from education_system.systems.apprenticeships.domain.apprentices.breaks import (
    BreakInLearning,
    total_break_days,
    validate_new_break,
)
from education_system.systems.apprenticeships.domain.apprentices.models import (
    Apprentice,
    ApprenticeSummary,
    ValidationError,
    elapsed_percent,
    planned_end_for,
    validate_age_at_start,
    validate_date_of_birth,
    validate_uln,
    years_between,
)
from education_system.systems.apprenticeships.domain.apprentices.withdrawals import (
    TRANSFER_REASON,
    require_not_a_transfer,
    validate_withdrawal,
    within_qualifying_period,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
)
from education_system.systems.apprenticeships.services import apprentice_service


def _apprentice(**overrides) -> Apprentice:
    fields = dict(
        apprentice_id=1, uln=None, given_name="Jo", family_name="Bell",
        date_of_birth="2003-05-01", email=None, phone=None, username=None,
        programme_id=None, employer_id=None, workplace_id=None, tutor_id=None,
        status="On Programme", start_date="2025-01-01", planned_end_date="2026-01-01",
        actual_end_date=None, weekly_hours=30.0, funding_model=None,
        prior_learning=None, support_needs=None, notes=None, created_at="", updated_at="",
    )
    fields.update(overrides)
    return Apprentice(**fields)


def _break(**overrides) -> BreakInLearning:
    fields = dict(
        break_id=1, apprentice_id=1, start_date="2025-03-01",
        expected_return="2025-04-01", actual_return=None, reason="Long-term sickness",
    )
    fields.update(overrides)
    return BreakInLearning(**fields)


# ═════════════════════════════════════════════════════════════════════
# The record
# ═════════════════════════════════════════════════════════════════════

class TestRecord:
    def test_age_counts_whole_years_across_a_leap_day(self):
        assert years_between("2008-02-29", "2024-02-28") == 15
        assert years_between("2008-02-29", "2024-02-29") == 16

    def test_part_time_hours_stretch_the_programme(self):
        assert planned_end_for("2025-01-15", 12, 30.0) == "2026-01-15"
        assert planned_end_for("2025-01-15", 12, 15.0) == "2027-01-15"

    def test_short_programmes_are_held_to_the_minimum_practical_period(self):
        floor = date(2025, 3, 1) + timedelta(days=config.MINIMUM_PRACTICAL_PERIOD_DAYS)
        assert planned_end_for("2025-03-01", 6, 30.0) == floor.isoformat()

    def test_uln_is_cleaned_and_checked(self):
        assert validate_uln(" 12345 67890 ") == "1234567890"
        assert validate_uln("  ") is None
        with pytest.raises(ValidationError, match="10 digits"):
            validate_uln("12345")

    def test_minimum_age_is_judged_on_the_start_date(self):
        validate_age_at_start("2010-09-01", "2026-09-01")
        with pytest.raises(ValidationError, match="at least 16"):
            validate_age_at_start("2010-09-01", "2026-08-31")
        validate_age_at_start(None, "2026-08-31")   # not known yet, so not judged

    def test_date_of_birth_cannot_be_in_the_future(self):
        with pytest.raises(ValidationError, match="future"):
            validate_date_of_birth("2030-01-01", date(2026, 9, 10))
        validate_date_of_birth("2003-05-01", date(2026, 9, 10))

    def test_overdue_means_active_past_the_planned_end(self):
        late = _apprentice(planned_end_date="2026-01-01")
        assert late.days_remaining(date(2026, 1, 11)) == -10
        assert late.is_overdue(date(2026, 1, 11))
        assert not late.is_overdue(date(2025, 12, 31))
        assert not _apprentice(status="Completed").is_overdue(date(2026, 1, 11))


class TestProgress:
    def test_elapsed_share_of_the_programme(self):
        assert elapsed_percent("2025-01-01", "2026-01-01", date(2025, 7, 2)) == 49.9

    def test_break_time_is_not_training_time(self):
        assert elapsed_percent(
            "2025-01-01", "2026-01-01", date(2025, 7, 2), break_days=30
        ) == 41.6

    def test_someone_back_from_a_break_is_not_flagged_behind(self):
        today = date(2025, 7, 2)
        summary = ApprenticeSummary(
            apprentice=_apprentice(), otj_hours_logged=40.0, otj_hours_target=100.0,
        )
        assert summary.is_behind_on(today)
        summary.break_days = 30
        assert not summary.is_behind_on(today)


# ═════════════════════════════════════════════════════════════════════
# The lifecycle
# ═════════════════════════════════════════════════════════════════════

class TestLifecycle:
    def test_every_status_has_a_row_in_the_transition_table(self):
        assert set(lifecycle.TRANSITIONS) == set(config.APPRENTICE_STATUSES)
        for targets in lifecycle.TRANSITIONS.values():
            assert targets <= set(config.APPRENTICE_STATUSES)

    def test_terminal_statuses_are_the_dead_ends(self):
        assert lifecycle.TERMINAL_STATUSES == {"Completed", "Transferred"}
        assert lifecycle.next_statuses("Completed") == ()

    def test_illegal_moves_name_the_legal_ones(self):
        with pytest.raises(ValidationError, match="Allowed from here: On Programme, Withdrawn"):
            lifecycle.require_transition("Applicant", "Completed")

    @pytest.mark.parametrize(("current", "target", "effect"), [
        ("EPA", "Completed", "set"),
        ("On Programme", "Withdrawn", "set"),
        ("Break in Learning", "Transferred", "set"),
        ("Withdrawn", "On Programme", "clear"),
        ("On Programme", "Break in Learning", None),
        ("Break in Learning", "On Programme", None),
    ])
    def test_end_date_is_stamped_leaving_and_cleared_coming_back(self, current, target, effect):
        assert lifecycle.end_date_change(current, target) == effect

    def test_a_listed_reason_is_filed_under_its_category(self):
        assert lifecycle.split_reason(
            "Break in Learning", " long-term SICKNESS ", "Surgery"
        ) == ("Long-term sickness", "Surgery")

    def test_an_unlisted_reason_is_kept_as_other(self):
        assert lifecycle.split_reason(
            "Withdrawn", "Application declined: no employer"
        ) == ("Other", "Application declined: no employer")

    def test_other_on_its_own_says_nothing(self):
        with pytest.raises(ValidationError, match="Other"):
            lifecycle.split_reason("Withdrawn", "Other")
        assert lifecycle.split_reason("Withdrawn", "Other", "Emigrated") == ("Other", "Emigrated")

    def test_moves_without_a_list_keep_the_reason_as_given(self):
        assert lifecycle.split_reason(
            "Transferred", "Moved to Acme Training"
        ) == ("Moved to Acme Training", None)


# ═════════════════════════════════════════════════════════════════════
# Breaks and withdrawals
# ═════════════════════════════════════════════════════════════════════

class TestBreaks:
    def test_an_open_break_runs_to_today(self):
        assert _break().days(date(2025, 3, 11)) == 10
        assert _break(actual_return="2025-03-21").days(date(2025, 12, 1)) == 20

    def test_days_add_up_across_breaks(self):
        breaks = [_break(actual_return="2025-03-21"), _break(break_id=2, start_date="2025-06-01")]
        assert total_break_days(breaks, date(2025, 6, 6)) == 25

    def test_overdue_only_while_open_and_past_the_expected_return(self):
        assert _break().is_overdue(date(2025, 4, 2))
        assert not _break().is_overdue(date(2025, 4, 1))
        assert not _break(actual_return="2025-04-10").is_overdue(date(2025, 5, 1))

    def test_from_row_reads_a_repository_row(self):
        row = {
            "break_id": 7, "apprentice_id": 3, "start_date": "2025-03-01",
            "expected_return": None, "actual_return": None, "reason": "Other",
            "notes": "Carer", "created_at": "2025-03-01 09:00:00",
        }
        assert BreakInLearning.from_row(row) == BreakInLearning(
            break_id=7, apprentice_id=3, start_date="2025-03-01", expected_return=None,
            actual_return=None, reason="Other", notes="Carer",
            created_at="2025-03-01 09:00:00",
        )

    def test_a_break_cannot_predate_the_apprenticeship(self):
        with pytest.raises(ValidationError, match="before the apprenticeship"):
            validate_new_break(
                start_date="2024-12-31", expected_return=None, programme_start="2025-01-01"
            )

    def test_expected_return_must_follow_the_start(self):
        with pytest.raises(ValidationError, match="expected return"):
            validate_new_break(
                start_date="2025-03-01", expected_return="2025-03-01",
                programme_start="2025-01-01",
            )


class TestWithdrawals:
    def test_last_day_of_learning_sits_between_start_and_withdrawal(self):
        validate_withdrawal(
            withdrawal_date="2025-06-10", last_activity_date="2025-06-01", start_date="2025-01-01"
        )
        with pytest.raises(ValidationError, match="after the withdrawal date"):
            validate_withdrawal(
                withdrawal_date="2025-06-01", last_activity_date="2025-06-10",
                start_date="2025-01-01",
            )
        with pytest.raises(ValidationError, match="before the apprenticeship started"):
            validate_withdrawal(
                withdrawal_date="2025-06-01", last_activity_date="2024-12-01",
                start_date="2025-01-01",
            )

    def test_leaving_early_falls_inside_the_qualifying_period(self):
        def day(n: int) -> str:
            return (date(2025, 1, 1) + timedelta(days=n)).isoformat()

        assert within_qualifying_period("2025-01-01", day(config.QUALIFYING_PERIOD_DAYS - 1))
        assert not within_qualifying_period("2025-01-01", day(config.QUALIFYING_PERIOD_DAYS))
        assert not within_qualifying_period(None, day(3))

    def test_leaving_for_another_provider_is_a_transfer_when_one_is_possible(self):
        assert TRANSFER_REASON in config.WITHDRAWAL_REASONS
        with pytest.raises(ValidationError, match="Transferred"):
            require_not_a_transfer(TRANSFER_REASON, transfer_allowed=True)
        require_not_a_transfer(TRANSFER_REASON, transfer_allowed=False)


# ═════════════════════════════════════════════════════════════════════
# What the service does with the rules
# ═════════════════════════════════════════════════════════════════════

class TestChangeStatusSideEffects:
    def test_reinstatement_clears_the_end_date(self, cohort, admin):
        aid = cohort["apprentice_id"]
        gone = apprentice_service.change_status(admin, aid, "Withdrawn", reason="Left employment")
        assert gone.actual_end_date is not None
        back = apprentice_service.change_status(admin, aid, "On Programme", reason="Appeal upheld")
        assert back.actual_end_date is None

    def test_the_end_date_is_the_last_day_of_learning(self, cohort, admin):
        last = (date.today() - timedelta(days=14)).isoformat()
        gone = apprentice_service.change_status(
            admin, cohort["apprentice_id"], "Withdrawn", reason="Health",
            last_activity_date=last,
        )
        assert gone.actual_end_date == last

    def test_a_break_records_its_category_detail_and_expected_return(self, cohort, admin):
        aid = cohort["apprentice_id"]
        back_by = (date.today() + timedelta(days=60)).isoformat()
        apprentice_service.change_status(
            admin, aid, "Break in Learning", reason="long-term sickness",
            notes="Surgery", expected_return=back_by,
        )
        (brk,) = apprentice_service.list_breaks(admin, aid)
        assert (brk["reason"], brk["notes"], brk["expected_return"]) == (
            "Long-term sickness", "Surgery", back_by,
        )

    def test_an_unlisted_withdrawal_reason_is_kept_as_other(self, cohort, admin):
        aid = cohort["apprentice_id"]
        apprentice_service.change_status(admin, aid, "Withdrawn", reason="Moved abroad")
        (row,) = apprentice_repository.list_withdrawals(apprentice_id=aid)
        assert (row["reason"], row["notes"]) == ("Other", "Moved abroad")

    def test_leaving_for_another_provider_must_be_a_transfer(self, cohort, admin):
        with pytest.raises(ValidationError, match="Transferred"):
            apprentice_service.change_status(
                admin, cohort["apprentice_id"], "Withdrawn", reason=TRANSFER_REASON
            )

    def test_withdrawing_from_a_break_closes_it(self, cohort, admin):
        aid = cohort["apprentice_id"]
        apprentice_service.change_status(
            admin, aid, "Break in Learning", reason="Personal circumstances"
        )
        apprentice_service.change_status(admin, aid, "Withdrawn", reason="Personal circumstances")
        (brk,) = apprentice_service.list_breaks(admin, aid)
        assert brk["actual_return"] is not None

    def test_break_days_come_off_elapsed_progress(self, cohort, admin):
        aid = cohort["apprentice_id"]
        apprentice_service.change_status(
            admin, aid, "Break in Learning", reason="Long-term sickness",
            effective_date=(date.today() - timedelta(days=30)).isoformat(),
        )
        apprentice_service.change_status(admin, aid, "On Programme")
        assert apprentice_service.get_apprentice(admin, aid).break_days == 30

    def test_under_16s_cannot_be_started(self, cohort, admin):
        young = apprentice_service.create_apprentice(admin, {
            "given_name": "Sam", "family_name": "Young",
            "date_of_birth": date(date.today().year - 15, 1, 1).isoformat(),
            "programme_id": cohort["programme"].programme_id,
        })
        with pytest.raises(ValidationError, match="at least 16"):
            apprentice_service.start_programme(
                admin, young.apprentice_id, start_date=date.today().isoformat()
            )
