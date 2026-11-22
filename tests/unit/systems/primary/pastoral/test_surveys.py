"""Surveys (systems.primary.domain.pastoral.surveys.surveys)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.pastoral.surveys import surveys as SV

TODAY = dt.date.today().isoformat()

QUESTIONS = [
    {"prompt": "How happy are you at school?", "type": "Likert", "required": True},
    {"prompt": "Do you feel safe?", "type": "Yes/No"},
    {"prompt": "Favourite lesson", "type": "Single Choice", "choices": ["Maths", "Art", "PE"]},
    {"prompt": "Clubs you attend", "type": "Multi Choice",
     "choices": ["Choir", "Chess", "Football"]},
    {"prompt": "Minutes reading a day", "type": "Number"},
    {"prompt": "Anything else?", "type": "Text"},
]


def _survey(name="Pupil voice", **extra):
    return SV.create_survey({"name": name, "questions": QUESTIONS, **extra})


def _open(name="Pupil voice", **extra):
    return SV.publish(_survey(name, **extra).survey_id, open_on="2025-10-01")


def _payload(s, **changes):
    return {**SV._to_dict(s), **changes}


# ── create / read ────────────────────────────────────────────────────

def test_create_defaults_and_round_trip():
    s = _survey(description="  Autumn  ", created_by="Ms Lee", notes="")
    assert s.survey_id > 0
    assert (s.audience, s.status, s.anonymous) == ("Students", "Draft", True)
    assert s.description == "Autumn" and s.notes is None and s.created_by == "Ms Lee"
    assert [q.to_dict() for q in s.questions] == [
        SV.Question.from_dict(q).to_dict() for q in QUESTIONS]
    assert s.questions[2].choices == ["Maths", "Art", "PE"]
    assert s.questions[0].required is True and s.questions[1].required is False
    assert s.is_editable and not s.is_open
    assert SV.get_survey(s.survey_id) == s


def test_question_objects_accepted():
    s = SV.create_survey({"name": "Q objs", "anonymous": False,
                          "questions": [SV.Question("Any comments?", "Text")]})
    assert s.questions == [SV.Question("Any comments?", "Text", [], False)]
    assert s.anonymous is False


def test_question_from_dict_defaults():
    q = SV.Question.from_dict({"prompt": "Hi"})
    assert (q.type, q.choices, q.required) == ("Text", [], False)


def test_empty_database():
    assert SV.get_survey(1) is None
    assert SV.list_surveys() == []
    assert SV.list_responses(1) == [] and SV.response_count(1) == 0
    assert SV.get_response(1) is None
    assert SV.summary() == SV.SurveysSummary()


# ── survey validation ────────────────────────────────────────────────

@pytest.mark.parametrize("bad, msg", [
    ({"name": "  "}, "Name is required"),
    ({"audience": "Pupils"}, "Audience must be one of"),
    ({"status": "Live"}, "Status must be one of"),
    ({"open_on": "01/10/2025"}, "Open on must be YYYY-MM-DD"),
    ({"close_on": "2025-02-30"}, "Close on must be YYYY-MM-DD"),
    ({"open_on": "2025-10-10", "close_on": "2025-10-09"}, "Close date must be on or after"),
    ({"questions": None}, "Questions are required"),
    ({"questions": []}, "At least one question is required"),
    ({"questions": ["How?"]}, "Question 1: must be a dict or Question"),
    ({"questions": [{"prompt": "", "type": "Text"}]}, "Question 1: prompt is required"),
    ({"questions": [{"prompt": "A", "type": "Text"}, {"prompt": "B", "type": "Essay"}]},
     "Question 2: type must be one of"),
    ({"questions": [{"prompt": "A", "type": "Single Choice"}]}, "choices required"),
    ({"questions": [{"prompt": "A", "type": "Multi Choice", "choices": ["x", " "]}]},
     "choices must be non-empty strings"),
])
def test_survey_validation(bad, msg):
    with pytest.raises(SV.ValidationError, match=msg):
        SV.create_survey({"name": "S", "questions": QUESTIONS, **bad})


def test_same_open_and_close_date_allowed():
    s = _survey(open_on="2025-10-01", close_on="2025-10-01")
    assert (s.open_on, s.close_on) == ("2025-10-01", "2025-10-01")


def test_duplicate_name_refused_but_update_keeps_own_name():
    s = _survey()
    with pytest.raises(SV.ValidationError, match="already exists"):
        _survey()
    upd = SV.update_survey(s.survey_id, _payload(s, audience="Parents / Carers"))
    assert upd.name == "Pupil voice" and upd.audience == "Parents / Carers"
    other = _survey("Staff voice")
    with pytest.raises(SV.ValidationError, match="already exists"):
        SV.update_survey(other.survey_id, _payload(other, name="Pupil voice"))


# ── update / delete / list ───────────────────────────────────────────

def test_update_draft_questions_and_missing_id():
    s = _survey()
    upd = SV.update_survey(s.survey_id, _payload(
        s, questions=[{"prompt": "New?", "type": "Yes/No"}]))
    assert [q.prompt for q in upd.questions] == ["New?"]
    with pytest.raises(SV.ValidationError, match="No survey with id 99"):
        SV.update_survey(99, _payload(s))


def test_questions_locked_once_open_but_metadata_editable():
    s = _open()
    with pytest.raises(SV.ValidationError, match="only be edited while in Draft"):
        SV.update_survey(s.survey_id, _payload(
            s, questions=[{"prompt": "Changed", "type": "Text"}]))
    upd = SV.update_survey(s.survey_id, _payload(s, notes="Reminder sent"))
    assert upd.notes == "Reminder sent" and upd.status == "Open"


def test_delete_survey_cascades_responses():
    s = _open()
    r = SV.submit_response(s.survey_id, answers={0: 4})
    assert SV.delete_survey(s.survey_id) is True
    assert SV.get_survey(s.survey_id) is None and SV.get_response(r.response_id) is None
    assert SV.delete_survey(s.survey_id) is False


def test_list_filters_and_newest_first():
    a = _survey("Pupil voice", created_by="Ms Lee")
    b = _survey("Parent survey", audience="Parents / Carers", created_by="Mr Head")
    c = _open("Staff wellbeing", audience="Staff")
    assert [s.survey_id for s in SV.list_surveys()] == [c.survey_id, b.survey_id, a.survey_id]
    assert [s.survey_id for s in SV.list_surveys(audience="Staff")] == [c.survey_id]
    assert [s.survey_id for s in SV.list_surveys(status="Draft")] == [b.survey_id, a.survey_id]
    assert [s.survey_id for s in SV.list_surveys(created_by_like="Head")] == [b.survey_id]
    assert [s.survey_id for s in SV.list_surveys(name_like="voice")] == [a.survey_id]
    assert [s.survey_id for s in SV.list_surveys(open_only=True)] == [c.survey_id]


# ── workflow ─────────────────────────────────────────────────────────

def test_publish_sets_open_and_open_date():
    s = _survey()
    pub = SV.publish(s.survey_id, open_on="2025-10-01")
    assert (pub.status, pub.open_on, pub.is_open, pub.is_editable) == (
        "Open", "2025-10-01", True, False)
    assert SV.publish(_survey("Other").survey_id).open_on == TODAY


def test_publish_keeps_existing_open_date():
    s = _survey(open_on="2025-09-15")
    assert SV.publish(s.survey_id, open_on="2025-10-01").open_on == "2025-09-15"


def test_close_archive_and_set_status():
    s = _open()
    closed = SV.close_survey(s.survey_id, close_on="2025-10-20")
    assert (closed.status, closed.close_on) == ("Closed", "2025-10-20")
    assert SV.archive(s.survey_id).status == "Archived"
    assert SV.set_status(s.survey_id, "Open").status == "Open"
    with pytest.raises(SV.ValidationError, match="Status must be one of"):
        SV.set_status(s.survey_id, "Live")


def test_close_defaults_to_today():
    s = _open()
    assert SV.close_survey(s.survey_id).close_on == TODAY


@pytest.mark.parametrize("fn", [SV.publish, SV.close_survey, SV.archive])
def test_workflow_missing_survey(fn):
    with pytest.raises(SV.ValidationError, match="No survey with id 5"):
        fn(5)


def test_set_status_missing_survey():
    with pytest.raises(SV.ValidationError, match="No survey with id 5"):
        SV.set_status(5, "Open")


# ── responses ────────────────────────────────────────────────────────

def test_submit_normalises_every_answer_type():
    s = _open()
    r = SV.submit_response(s.survey_id, answers={
        0: "4", 1: "y", 2: " Art ", 3: "Choir, Chess", 4: "25", 5: "  Lovely  ", 9: "ignored"},
        respondent_role="Pupil", submitted_on="2025-10-02", notes=" ")
    assert r.answers == {0: 4, 1: "Yes", 2: "Art", 3: ["Choir", "Chess"], 4: 25.0, 5: "Lovely"}
    assert r.anonymous is True and r.respondent_name is None
    assert (r.respondent_role, r.submitted_on, r.notes) == ("Pupil", "2025-10-02", None)
    assert SV.get_response(r.response_id) == r


def test_optional_blank_answers_are_dropped():
    s = _open()
    r = SV.submit_response(s.survey_id, answers={0: 3, 1: "", 3: []})
    assert r.answers == {0: 3, 3: []}
    assert r.submitted_on == TODAY


@pytest.mark.parametrize("answers, msg", [
    ({}, "an answer is required"),
    ({0: ""}, "an answer is required"),
    ({0: 6}, "Likert answer must be 1-5"),
    ({0: "great"}, "Likert answer must be 1-5"),
    ({0: 3, 1: "maybe"}, "answer must be Yes or No"),
    ({0: 3, 2: "Music"}, "answer must be one of"),
    ({0: 3, 3: "Choir, Drama"}, "'Drama' not in choices"),
    ({0: 3, 3: 7}, "multi-choice expects a list"),
    ({0: 3, 4: "lots"}, "answer must be a number"),
])
def test_answer_validation(answers, msg):
    s = _open()
    with pytest.raises(SV.ValidationError, match=msg):
        SV.submit_response(s.survey_id, answers=answers)


def test_yes_no_synonyms():
    s = _open()
    for raw, want in (("TRUE", "Yes"), ("1", "Yes"), ("n", "No"), ("false", "No")):
        assert SV.submit_response(s.survey_id, answers={0: 1, 1: raw}).answers[1] == want


def test_only_open_surveys_take_responses():
    s = _survey()
    with pytest.raises(SV.ValidationError, match=r"not Open \(current: Draft\)"):
        SV.submit_response(s.survey_id, answers={0: 3})
    with pytest.raises(SV.ValidationError, match="No survey with id 42"):
        SV.submit_response(42, answers={0: 3})


def test_named_responses():
    s = _open(anonymous=False)
    with pytest.raises(SV.ValidationError, match="Respondent name required"):
        SV.submit_response(s.survey_id, answers={0: 5})
    r = SV.submit_response(s.survey_id, answers={0: 5}, respondent_name=" Ada ")
    assert (r.anonymous, r.respondent_name) == (False, "Ada")
    anon = SV.submit_response(s.survey_id, answers={0: 5}, respondent_name="Ben",
                              anonymous=True)
    assert (anon.anonymous, anon.respondent_name) == (True, None)


def test_bad_submitted_on_refused():
    s = _open()
    with pytest.raises(SV.ValidationError, match="Submitted on must be YYYY-MM-DD"):
        SV.submit_response(s.survey_id, answers={0: 3}, submitted_on="2/10/2025")


def test_list_count_and_delete_responses():
    s = _open()
    r1 = SV.submit_response(s.survey_id, answers={0: 1}, submitted_on="2025-10-02")
    r2 = SV.submit_response(s.survey_id, answers={0: 2}, submitted_on="2025-10-05")
    r3 = SV.submit_response(s.survey_id, answers={0: 3}, submitted_on="2025-10-02")
    assert [r.response_id for r in SV.list_responses(s.survey_id)] == [
        r2.response_id, r3.response_id, r1.response_id]
    assert SV.response_count(s.survey_id) == 3
    assert SV.delete_response(r1.response_id) is True
    assert SV.delete_response(r1.response_id) is False
    assert SV.response_count(s.survey_id) == 2


# ── analysis ─────────────────────────────────────────────────────────

def test_question_stats():
    s = _open()
    for ans in ({0: 5, 1: "Yes", 2: "Art", 3: ["Choir", "Chess"], 4: 10, 5: "Fun"},
                {0: 4, 1: "No", 2: "Art", 3: ["Chess"], 4: 20},
                {0: 4, 1: "Yes", 5: "  "}):
        SV.submit_response(s.survey_id, answers=ans)
    st = {q.index: q for q in SV.question_stats(s.survey_id)}
    assert (st[0].answered, st[0].skipped, st[0].mean) == (3, 0, 4.33)
    assert st[0].counts == {"5": 1, "4": 2}
    assert st[1].counts == {"Yes": 2, "No": 1} and st[1].mean is None
    assert (st[2].answered, st[2].skipped, st[2].counts) == (2, 1, {"Art": 2})
    assert st[3].counts == {"Choir": 1, "Chess": 2}
    assert (st[4].mean, st[4].answered) == (15.0, 2)
    # "  " is stripped to "" on submit and so stored as an answer of ""
    assert st[5].text_samples == ["Fun"]
    assert st[5].prompt == "Anything else?" and st[5].type == "Text"


def test_question_stats_no_responses_and_missing_survey():
    s = _open()
    st = SV.question_stats(s.survey_id)
    assert len(st) == len(QUESTIONS)
    assert all(q.answered == 0 and q.skipped == 0 and q.mean is None for q in st)
    with pytest.raises(SV.ValidationError, match="No survey with id 99"):
        SV.question_stats(99)


def test_text_samples_capped_at_ten():
    s = SV.publish(SV.create_survey({"name": "T", "questions": [
        {"prompt": "Say", "type": "Text"}]}).survey_id)
    for i in range(12):
        SV.submit_response(s.survey_id, answers={0: f"note {i}"})
    st = SV.question_stats(s.survey_id)[0]
    assert st.answered == 12 and len(st.text_samples) == 10


def test_summary():
    _survey("A")
    o = _open("B", audience="Parents / Carers")
    c = _open("C", audience="Staff")
    SV.close_survey(c.survey_id)
    arch = _survey("D")
    SV.archive(arch.survey_id)
    SV.submit_response(o.survey_id, answers={0: 3})
    SV.submit_response(o.survey_id, answers={0: 4})
    sm = SV.summary()
    assert (sm.total, sm.drafts, sm.open_count, sm.closed, sm.archived) == (4, 1, 1, 1, 1)
    assert sm.total_responses == 2
    assert sm.by_audience == {"Students": 2, "Parents / Carers": 1, "Staff": 1}
    assert sm.by_status == {"Draft": 1, "Open": 1, "Closed": 1, "Archived": 1}
