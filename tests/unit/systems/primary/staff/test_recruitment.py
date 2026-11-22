"""Vacancies + applicants (systems.primary.domain.staff.recruitment.recruitment)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.staff.recruitment import recruitment as RC

TODAY = dt.date.today()


def _d(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _vacancy(title="Year 3 Teacher", **extra):
    return RC.create_vacancy({"title": title, **extra})


def _applicant(vacancy_id, first="Ada", last="Lovelace", **extra):
    return RC.add_applicant(vacancy_id, {"first_name": first, "last_name": last, **extra})


# ── Vacancies ────────────────────────────────────────────────────────

def test_create_vacancy_defaults_and_values():
    v = _vacancy(reference=" V1 ", department=" KS2 ", salary_min="31650", salary_max=43607,
                 fte_percent="60", closing_date=_d(14))
    assert (v.title, v.role_type, v.contract_type, v.status) == (
        "Year 3 Teacher", "Teacher", "Permanent", "Draft")
    assert (v.reference, v.department, v.fte_percent) == ("V1", "KS2", 60.0)
    assert (v.salary_min, v.salary_max) == (31650.0, 43607.0)
    assert v.safeguarding_statement is True
    assert v.is_open is True and v.closing_passed is False
    assert RC.get_vacancy(v.vacancy_id) == v
    assert RC.get_vacancy(999) is None
    assert _vacancy("Full time").fte_percent == 100.0


def test_safeguarding_statement_can_be_turned_off():
    assert _vacancy(safeguarding_statement=False).safeguarding_statement is False


@pytest.mark.parametrize("bad, msg", [
    ({"title": " "}, "Title is required"),
    ({"role_type": "Dean"}, "Role type must be one of"),
    ({"contract_type": "Zero hours"}, "Contract type must be one of"),
    ({"status": "Live"}, "Status must be one of"),
    ({"fte_percent": "full"}, "FTE percent must be a number"),
    ({"fte_percent": 120}, "FTE percent must be between 0 and 100"),
    ({"fte_percent": -10}, "FTE percent must be between 0 and 100"),
    ({"salary_min": "lots"}, "salary min must be a number"),
    ({"salary_max": -1}, "salary max must be >= 0"),
    ({"salary_min": 40000, "salary_max": 30000}, "Salary min must be <= salary max"),
    ({"advertised_on": "x"}, "Advertised on must be YYYY-MM-DD"),
    ({"closing_date": "x"}, "Closing date must be YYYY-MM-DD"),
    ({"shortlisting_date": "x"}, "Shortlisting date must be YYYY-MM-DD"),
    ({"interview_date": "x"}, "Interview date must be YYYY-MM-DD"),
    ({"start_date": "x"}, "Start date must be YYYY-MM-DD"),
])
def test_vacancy_refusals(bad, msg):
    with pytest.raises(RC.ValidationError, match=msg):
        RC.create_vacancy({"title": "T", **bad})
    assert RC.list_vacancies() == []


def test_zero_fte_is_refused_not_turned_into_full_time():
    """0% FTE is not a post; the rule says FTE must be above 0."""
    with pytest.raises(RC.ValidationError, match="FTE percent must be between 0 and 100"):
        RC.create_vacancy({"title": "T", "fte_percent": 0})


def test_closing_passed_only_for_open_vacancies():
    assert _vacancy(closing_date=_d(-1), status="Advertised").closing_passed is True
    assert _vacancy(closing_date=_d(0), status="Advertised").closing_passed is False
    filled = _vacancy(closing_date=_d(-5), status="Filled")
    assert filled.is_open is False and filled.closing_passed is False


def test_update_advertise_status_fill_delete():
    v = _vacancy()
    up = RC.update_vacancy(v.vacancy_id, {"title": "Year 4 Teacher", "role_type": "Teacher"})
    assert up.title == "Year 4 Teacher" and up.department is None
    with pytest.raises(RC.ValidationError, match="No vacancy with id 999"):
        RC.update_vacancy(999, {"title": "x"})
    adv = RC.advertise(v.vacancy_id, advertised_on="2026-10-01")
    assert (adv.status, adv.advertised_on) == ("Advertised", "2026-10-01")
    # an existing advert date is kept on re-advertising
    assert RC.advertise(v.vacancy_id, advertised_on="2026-10-20").advertised_on == "2026-10-01"
    assert RC.advertise(_vacancy("Other").vacancy_id).advertised_on == TODAY.isoformat()
    assert RC.set_vacancy_status(v.vacancy_id, "Interview").status == "Interview"
    with pytest.raises(RC.ValidationError, match="Status must be one of"):
        RC.set_vacancy_status(v.vacancy_id, "Done")
    filled = RC.mark_filled(v.vacancy_id)
    assert filled.status == "Filled" and filled.is_open is False
    for fn in (RC.advertise, RC.mark_filled):
        with pytest.raises(RC.ValidationError, match="No vacancy with id 999"):
            fn(999)
    with pytest.raises(RC.ValidationError, match="No vacancy with id 999"):
        RC.set_vacancy_status(999, "Closed")
    assert RC.delete_vacancy(v.vacancy_id) is True
    assert RC.delete_vacancy(v.vacancy_id) is False


def test_list_vacancies_filters_and_order():
    nodate = _vacancy("TA", role_type="Teaching Assistant", contract_type="Fixed Term")
    late = _vacancy("Y6 Teacher", department="KS2", closing_date=_d(20), status="Advertised")
    early = _vacancy("Cook", role_type="Catering", closing_date=_d(-3), status="Advertised")
    done = _vacancy("Office", closing_date=_d(-10), status="Filled")
    ids = lambda rows: [x.vacancy_id for x in rows]  # noqa: E731
    assert ids(RC.list_vacancies()) == [nodate.vacancy_id, done.vacancy_id, early.vacancy_id,
                                        late.vacancy_id]
    assert ids(RC.list_vacancies(role_type="Catering")) == [early.vacancy_id]
    assert ids(RC.list_vacancies(contract_type="Fixed Term")) == [nodate.vacancy_id]
    assert ids(RC.list_vacancies(status="Filled")) == [done.vacancy_id]
    assert ids(RC.list_vacancies(department_like="ks2")) == [late.vacancy_id]
    assert ids(RC.list_vacancies(title_like="teacher")) == [late.vacancy_id]
    assert ids(RC.list_vacancies(open_only=True)) == [nodate.vacancy_id, early.vacancy_id,
                                                      late.vacancy_id]
    assert ids(RC.list_vacancies(closing_passed=True)) == [early.vacancy_id]


# ── Applicants ───────────────────────────────────────────────────────

def test_add_applicant_defaults():
    v = _vacancy()
    a = _applicant(v.vacancy_id, email=" ada@example.test ", cv_received=1,
                   interview_score="75", offer_salary="35000")
    assert (a.full_name, a.email, a.source, a.status) == (
        "Ada Lovelace", "ada@example.test", "School Website", "Applied")
    assert a.application_received_on == TODAY.isoformat()
    assert (a.cv_received, a.shortlisted, a.interview_score, a.offer_salary) == (
        True, False, 75, 35000.0)
    assert a.is_active is True and a.has_offer is False
    assert RC.get_applicant(a.applicant_id) == a
    assert RC.get_applicant(999) is None
    assert RC.applicant_count(v.vacancy_id) == 1


@pytest.mark.parametrize("bad, msg", [
    ({"first_name": ""}, "First name is required"),
    ({"last_name": " "}, "Last name is required"),
    ({"application_received_on": "x"}, "Application received must be YYYY-MM-DD"),
    ({"interview_date": "x"}, "Interview date must be YYYY-MM-DD"),
    ({"offer_made_on": "x"}, "Offer made on must be YYYY-MM-DD"),
    ({"offer_response_on": "x"}, "Offer response on must be YYYY-MM-DD"),
    ({"started_on": "x"}, "Started on must be YYYY-MM-DD"),
    ({"source": "Newspaper"}, "Source must be one of"),
    ({"status": "Hired"}, "Status must be one of"),
    ({"interview_score": 101}, "Interview score must be 0-100"),
    ({"interview_score": "good"}, "Interview score must be 0-100"),
    ({"offer_salary": "x"}, "Offer salary must be a number"),
    ({"offer_salary": -1}, "Offer salary must be >= 0"),
])
def test_applicant_refusals(bad, msg):
    v = _vacancy()
    data = {"first_name": "Ada", "last_name": "Lovelace", **bad}
    with pytest.raises(RC.ValidationError, match=msg):
        RC.add_applicant(v.vacancy_id, data)
    assert RC.applicant_count(v.vacancy_id) == 0


def test_applicant_needs_vacancy_and_cascades_with_it():
    with pytest.raises(RC.ValidationError, match="No vacancy with id 999"):
        _applicant(999)
    v = _vacancy()
    a = _applicant(v.vacancy_id)
    RC.delete_vacancy(v.vacancy_id)
    assert RC.get_applicant(a.applicant_id) is None


def test_full_hiring_pipeline():
    v = _vacancy()
    a = _applicant(v.vacancy_id)
    s = RC.shortlist(a.applicant_id)
    assert (s.shortlisted, s.status) == (True, "Shortlisted")
    iv = RC.schedule_interview(a.applicant_id, interview_date="2026-12-01")
    assert (iv.status, iv.interview_date, iv.shortlisted) == (
        "Interview Scheduled", "2026-12-01", True)
    done = RC.record_interview(a.applicant_id, score=82, notes="strong phonics lesson")
    assert (done.status, done.interview_score, done.interview_notes) == (
        "Interviewed", 82, "strong phonics lesson")
    offer = RC.make_offer(a.applicant_id, salary=36000, offer_made_on="2026-12-02")
    assert (offer.status, offer.offer_salary, offer.offer_made_on) == (
        "Offer Made", 36000.0, "2026-12-02")
    assert offer.has_offer and offer.is_active
    acc = RC.offer_response(a.applicant_id, accepted=True, response_on="2026-12-03")
    assert (acc.status, acc.offer_response_on) == ("Offer Accepted", "2026-12-03")
    started = RC.mark_started(a.applicant_id, started_on="2027-01-05")
    assert (started.status, started.started_on) == ("Started", "2027-01-05")
    assert started.has_offer is True and started.is_active is False


def test_pipeline_defaults_and_declines():
    v = _vacancy()
    a = _applicant(v.vacancy_id, status="Under Review")
    # shortlisting only moves status on from "Applied"
    assert RC.shortlist(a.applicant_id).status == "Under Review"
    un = RC.shortlist(a.applicant_id, shortlisted=False)
    assert un.shortlisted is False
    assert RC.make_offer(a.applicant_id).offer_made_on == TODAY.isoformat()
    dec = RC.offer_response(a.applicant_id, accepted=False)
    assert (dec.status, dec.offer_response_on, dec.is_active) == (
        "Offer Declined", TODAY.isoformat(), False)
    assert RC.mark_started(a.applicant_id).started_on == TODAY.isoformat()
    with pytest.raises(RC.ValidationError, match="Interview date must be YYYY-MM-DD"):
        RC.schedule_interview(a.applicant_id, interview_date="tomorrow")
    with pytest.raises(RC.ValidationError, match="Interview score must be 0-100"):
        RC.record_interview(a.applicant_id, score=-1)


def test_reject_withdraw_and_status():
    v = _vacancy()
    a = _applicant(v.vacancy_id)
    with pytest.raises(RC.ValidationError, match="Rejection reason is required"):
        RC.reject_applicant(a.applicant_id, reason="")
    pre = RC.reject_applicant(a.applicant_id, reason="No QTS")
    assert (pre.status, pre.rejection_reason, pre.is_active) == (
        "Rejected (Pre-Interview)", "No QTS", False)
    post = RC.reject_applicant(a.applicant_id, reason="Weak lesson", post_interview=True)
    assert post.status == "Rejected (Post-Interview)"
    b = _applicant(v.vacancy_id, "Bea", "Brown", notes="keen")
    w = RC.withdraw_applicant(b.applicant_id, reason="Took other post")
    assert w.status == "Withdrew"
    assert w.notes == f"keen\nWithdrew ({TODAY.isoformat()}): Took other post"
    c = _applicant(v.vacancy_id, "Cal", "Cole")
    assert RC.withdraw_applicant(c.applicant_id).notes is None
    assert RC.set_applicant_status(c.applicant_id, "Under Review").status == "Under Review"
    with pytest.raises(RC.ValidationError, match="Status must be one of"):
        RC.set_applicant_status(c.applicant_id, "Hired")


def test_applicant_helpers_refuse_missing():
    calls = (
        lambda: RC.shortlist(404),
        lambda: RC.schedule_interview(404, interview_date="2026-12-01"),
        lambda: RC.record_interview(404),
        lambda: RC.make_offer(404),
        lambda: RC.offer_response(404, accepted=True),
        lambda: RC.mark_started(404),
        lambda: RC.reject_applicant(404, reason="x"),
        lambda: RC.withdraw_applicant(404),
        lambda: RC.set_applicant_status(404, "Applied"),
        lambda: RC.update_applicant(404, {"first_name": "a", "last_name": "b"}),
    )
    for call in calls:
        with pytest.raises(RC.ValidationError, match="No applicant with id 404"):
            call()


def test_update_and_delete_applicant():
    v = _vacancy()
    a = _applicant(v.vacancy_id)
    up = RC.update_applicant(a.applicant_id, {"first_name": "Ada", "last_name": "King",
                                              "source": "TES"})
    assert (up.last_name, up.source, up.vacancy_id) == ("King", "TES", v.vacancy_id)
    assert RC.delete_applicant(a.applicant_id) is True
    assert RC.delete_applicant(a.applicant_id) is False
    assert RC.applicant_count(v.vacancy_id) == 0


def test_list_applicants_filters_and_order():
    v1 = _vacancy()
    v2 = _vacancy("TA")
    a = _applicant(v1.vacancy_id, application_received_on="2026-10-01", shortlisted=True)
    b = _applicant(v1.vacancy_id, "B", "B", application_received_on="2026-10-05",
                   status="Interview Scheduled")
    c = _applicant(v2.vacancy_id, "C", "C", application_received_on="2026-10-03",
                   status="Offer Declined")
    ids = lambda rows: [x.applicant_id for x in rows]  # noqa: E731
    assert ids(RC.list_applicants()) == [b.applicant_id, c.applicant_id, a.applicant_id]
    assert ids(RC.list_applicants(vacancy_id=v1.vacancy_id)) == [b.applicant_id,
                                                                 a.applicant_id]
    assert ids(RC.list_applicants(status="Offer Declined")) == [c.applicant_id]
    assert ids(RC.list_applicants(shortlisted_only=True)) == [a.applicant_id]
    assert ids(RC.list_applicants(interview_scheduled=True)) == [b.applicant_id]
    assert ids(RC.list_applicants(offer_made=True)) == [c.applicant_id]


# ── Summary ──────────────────────────────────────────────────────────

def test_summary_empty():
    sm = RC.summary()
    assert (sm.total_vacancies, sm.total_applicants, sm.by_source) == (0, 0, {})


def test_summary_figures():
    v1 = _vacancy(status="Advertised", closing_date=_d(-2))
    v2 = _vacancy("TA", role_type="Teaching Assistant", status="Advertised", closing_date=_d(5))
    _vacancy("Old", status="Filled", closing_date=_d(-30))
    _applicant(v1.vacancy_id, "A", "A", shortlisted=True)
    _applicant(v1.vacancy_id, "B", "B", status="Offer Made", source="TES")
    _applicant(v1.vacancy_id, "C", "C", status="Started", shortlisted=True)
    _applicant(v2.vacancy_id, "D", "D", status="Rejected (Pre-Interview)")
    _applicant(v2.vacancy_id, "E", "E", status="Rejected (Post-Interview)")
    _applicant(v2.vacancy_id, "F", "F", status="Offer Accepted", source="TES")
    sm = RC.summary()
    assert (sm.total_vacancies, sm.open_vacancies, sm.advertised, sm.closing_passed) == (
        3, 2, 2, 1)
    assert (sm.total_applicants, sm.active_applicants, sm.shortlisted) == (6, 3, 2)
    assert (sm.interviewed, sm.offers_made, sm.offers_accepted, sm.started, sm.rejected) == (
        4, 1, 2, 1, 2)
    assert sm.by_role_type == {"Teacher": 2, "Teaching Assistant": 1}
    assert sm.by_vacancy_status == {"Advertised": 2, "Filled": 1}
    assert sm.by_source == {"School Website": 4, "TES": 2}
    assert sum(sm.by_applicant_status.values()) == 6
