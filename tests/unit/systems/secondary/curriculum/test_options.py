"""Year 9 options rules (domain.options) on a scratch school DB.

"Today" is pinned to 10 Feb 2026 (options season). The activity log and
auth.db are redirected, so nothing touches live data.
"""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.curriculum.domain import options as OP
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TUTOR = Principal(username="tutor", role="teacher")
TODAY = dt.date(2026, 2, 10)

#: Each pupil's three choices then one reserve.
PATTERNS = [("HIST", "ART", "COMP", "MUS"), ("GEOG", "ART", "COMP", "DT"),
            ("HIST", "GEOG", "FREN", "ART"), ("FREN", "COMP", "MUS", "ART"),
            ("HIST", "DT", "COMP", "GEOG"), ("HIST", "ART", "MUS", "DT")]


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    monkeypatch.setattr(OP, "_today", lambda: TODAY)
    yield
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


@pytest.fixture
def school():
    subs = {}
    for code, name, cat, core in (
            ("ENG", "English", "English", True), ("MATH", "Maths", "Maths", True),
            ("HIST", "History", "Humanities", False), ("GEOG", "Geography", "Humanities", False),
            ("FREN", "French", "Languages", False), ("ART", "Art", None, False),
            ("COMP", "Computing", None, False), ("MUS", "Music", None, False),
            ("DT", "Design Tech", None, False)):
        subs[code] = S.create({"code": code, "name": name, "ebacc_category": cat,
                               "is_core": core}, actor=ADMIN)
    pupils = [P.create_pupil({"legal_first_name": n, "legal_last_name": "Nine",
                              "date_of_birth": "2012-03-01", "gender": "Female",
                              "year_group": 9, "admission_date": "2023-09-01"}, actor=ADMIN)
              for n in ("Ava", "Ben", "Cat", "Dan", "Eve", "Fin", "Gus")]
    return {"subs": subs, "pupils": [p.pupil_id for p in pupils]}


def ids(school, *codes):
    return [school["subs"][c].subject_id for c in codes]


def _round(school, **extra):
    r = OP.create_round({"name": "Year 9 options 2026", "closes_on": "2026-03-01",
                         "choices_required": 3, "reserves_required": 1, "class_size": 5,
                         **extra}, actor=ADMIN)
    for code in ("HIST", "GEOG", "FREN", "ART", "COMP", "MUS", "DT"):
        OP.add_round_subject(r.round_id, school["subs"][code].subject_id, actor=ADMIN)
    return r


def _open_with_choices(school, n: int = len(PATTERNS)):
    r = _round(school)
    OP.set_status(r.round_id, "Open", actor=ADMIN)
    for pid, pat in zip(school["pupils"][:n], PATTERNS[:n]):
        OP.submit_choices(r.round_id, pid, ids(school, *pat[:3]), ids(school, pat[3]),
                          actor=TUTOR)
    return r


# ── Rounds ───────────────────────────────────────────────────────────

def test_new_round_defaults(school):
    r = OP.create_round({"name": "Options 2026"}, actor=ADMIN)
    assert (r.status, r.year_group, r.next_year, r.choices_required, r.reserves_required,
            r.blocks, r.class_size) == ("Draft", 9, 10, 4, 1, 4, 28)


@pytest.mark.parametrize("data, msg", [
    ({"name": ""}, "Give the round a name"),
    ({"name": "x", "year_group": 11}, "Year group must be"),
    ({"name": "x", "opens_on": "2026-03-01", "closes_on": "2026-02-01"}, "can't be before"),
    ({"name": "x", "choices_required": 5, "blocks": 4}, "at least 5 blocks"),
    ({"name": "x", "class_size": 2}, "Class size"),
])
def test_bad_rounds_refused(school, data, msg):
    with pytest.raises(OP.ValidationError, match=msg):
        OP.create_round(data, actor=ADMIN)


def test_round_names_unique_and_lead_only(school):
    OP.create_round({"name": "Options 2026"}, actor=ADMIN)
    with pytest.raises(OP.ValidationError, match="already a round"):
        OP.create_round({"name": "OPTIONS 2026"}, actor=ADMIN)
    with pytest.raises(OP.PermissionDenied):
        OP.create_round({"name": "Mine"}, actor=TUTOR)


def test_subjects_on_offer(school):
    r = OP.create_round({"name": "Options 2026"}, actor=ADMIN)
    with pytest.raises(OP.ValidationError, match="core - everyone takes it"):
        OP.add_round_subject(r.round_id, school["subs"]["ENG"].subject_id, actor=ADMIN)
    OP.add_round_subject(r.round_id, school["subs"]["HIST"].subject_id, actor=ADMIN)
    with pytest.raises(OP.ValidationError, match="already offered"):
        OP.add_round_subject(r.round_id, school["subs"]["HIST"].subject_id, actor=ADMIN)
    assert "HIST" not in [s.code for s in OP.available_subjects(r.round_id)]
    assert "ENG" not in [s.code for s in OP.available_subjects(r.round_id)]


def test_opening_needs_subjects_and_a_closing_date(school):
    r = OP.create_round({"name": "Options 2026", "choices_required": 3}, actor=ADMIN)
    with pytest.raises(OP.ValidationError) as e:
        OP.set_status(r.round_id, "Open", actor=ADMIN)
    assert any("Offer at least 4 subjects" in p for p in e.value.problems)
    assert any("closing date" in p for p in e.value.problems)


def test_status_path(school):
    r = _open_with_choices(school, 1)
    with pytest.raises(OP.ValidationError, match="can't go back to Draft"):
        OP.set_status(r.round_id, "Draft", actor=ADMIN)
    with pytest.raises(OP.ValidationError, match="Close the round"):
        OP.set_status(r.round_id, "Finalised", actor=ADMIN)
    OP.set_status(r.round_id, "Closed", actor=ADMIN)
    with pytest.raises(OP.ValidationError, match="run the allocation"):
        OP.set_status(r.round_id, "Finalised", actor=ADMIN)


# ── Choices and rules ────────────────────────────────────────────────

def test_choices_are_checked(school):
    r = _round(school)
    ava = school["pupils"][0]
    with pytest.raises(OP.ValidationError, match="only be entered while it's open"):
        OP.submit_choices(r.round_id, ava, ids(school, "HIST", "ART", "COMP"),
                          ids(school, "MUS"), actor=TUTOR)
    OP.set_status(r.round_id, "Open", actor=ADMIN)
    with pytest.raises(OP.ValidationError, match="exactly 3 subjects"):
        OP.submit_choices(r.round_id, ava, ids(school, "HIST", "ART"), ids(school, "MUS"),
                          actor=TUTOR)
    with pytest.raises(OP.ValidationError, match="only be chosen once"):
        OP.submit_choices(r.round_id, ava, ids(school, "HIST", "ART", "COMP"),
                          ids(school, "ART"), actor=TUTOR)
    with pytest.raises(OP.ValidationError, match="Not offered"):
        OP.submit_choices(r.round_id, ava, ids(school, "HIST", "ART", "ENG"),
                          ids(school, "MUS"), actor=TUTOR)
    x = OP.submit_choices(r.round_id, ava, ids(school, "HIST", "ART", "COMP"),
                          ids(school, "MUS"), actor=TUTOR)
    assert (x.label, x.submitted_by) == ("HIST, ART, COMP  (reserve MUS)", "tutor")
    x = OP.submit_choices(r.round_id, ava, ids(school, "GEOG", "ART", "COMP"),
                          ids(school, "MUS"), actor=TUTOR)        # replaces
    assert [c.code for c in x.primary] == ["GEOG", "ART", "COMP"]


def test_only_year_9_pupils_choose(school):
    r = _round(school)
    OP.set_status(r.round_id, "Open", actor=ADMIN)
    y8 = P.create_pupil({"legal_first_name": "Zed", "legal_last_name": "Eight",
                         "date_of_birth": "2013-03-01", "gender": "Male", "year_group": 8,
                         "admission_date": "2024-09-01"}, actor=ADMIN)
    with pytest.raises(OP.ValidationError, match="isn't in Year 9"):
        OP.submit_choices(r.round_id, y8.pupil_id, ids(school, "HIST", "ART", "COMP"),
                          ids(school, "MUS"), actor=TUTOR)


def test_rules_and_override(school):
    r = _round(school)
    OP.add_rule(r.round_id, "Humanities, Languages", 1, actor=ADMIN)
    with pytest.raises(OP.ValidationError, match="already a rule"):
        OP.add_rule(r.round_id, ["Languages", "Humanities"], 1, actor=ADMIN)
    with pytest.raises(OP.ValidationError, match="isn't a category"):
        OP.add_rule(r.round_id, "Cookery", 1, actor=ADMIN)
    OP.set_status(r.round_id, "Open", actor=ADMIN)
    gus = school["pupils"][6]
    no_humanity = (ids(school, "ART", "COMP", "MUS"), ids(school, "DT"))
    with pytest.raises(OP.ValidationError, match="don't meet the round's rules"):
        OP.submit_choices(r.round_id, gus, *no_humanity, actor=TUTOR)
    with pytest.raises(OP.ValidationError, match="give a reason"):
        OP.submit_choices(r.round_id, gus, *no_humanity, actor=ADMIN)
    x = OP.submit_choices(r.round_id, gus, *no_humanity, actor=ADMIN,
                          override_reason="Agreed pathway")
    assert x.override_reason == "Agreed pathway"
    assert OP.summary(r.round_id)["overrides"] == 1


def test_late_choices_only_by_the_lead(school, monkeypatch):
    r = _round(school)
    OP.set_status(r.round_id, "Open", actor=ADMIN)
    monkeypatch.setattr(OP, "_today", lambda: dt.date(2026, 3, 2))
    args = (r.round_id, school["pupils"][0], ids(school, "HIST", "ART", "COMP"),
            ids(school, "MUS"))
    with pytest.raises(OP.ValidationError, match="closed on 2026-03-01"):
        OP.submit_choices(*args, actor=TUTOR)
    OP.submit_choices(*args, actor=ADMIN)


def test_summary_and_not_chosen(school):
    r = _open_with_choices(school)
    s = OP.summary(r.round_id)
    assert (s["cohort"], s["pupils_submitted"], s["pupils_complete"]) == (7, 6, 6)
    art = next(x for x in s["subject_picks"] if x["code"] == "ART")
    assert (art["primary"], art["reserve"], art["groups"]) == (3, 2, 1)
    assert [p.legal_first_name for p in OP.not_submitted(r.round_id)] == ["Gus"]


def test_remove_subject_someone_chose(school):
    r = _open_with_choices(school, 1)
    with pytest.raises(OP.ValidationError, match="have chosen it"):
        OP.remove_round_subject(r.round_id, school["subs"]["HIST"].subject_id, actor=ADMIN)
    OP.remove_round_subject(r.round_id, school["subs"]["DT"].subject_id, actor=ADMIN)


def test_reminders_go_to_families_who_havent_chosen(school):
    r = _open_with_choices(school)
    gus = school["pupils"][6]
    C.add_contact(gus, {"full_name": "Gus's Mum", "relationship": "Mother",
                        "email": "mum@example.org", "receives_email": True,
                        "parental_responsibility": True}, actor=ADMIN)
    result = OP.remind_families(r.round_id, actor=ADMIN)
    assert result.recipients == 1
    with database.connect() as conn:
        (subject, body) = conn.execute("SELECT subject, body FROM email_recipients WHERE "
                                       "message_id = ?", (result.message_id,)).fetchone()
    assert "Gus's option choices" in subject and body.startswith("Dear Gus's Mum")


# ── Blocks and allocation ────────────────────────────────────────────

def test_blocks_are_checked(school):
    r = _open_with_choices(school, 1)
    with pytest.raises(OP.ValidationError, match="isn't one of A, B, C"):
        OP.set_blocks(r.round_id, {"D": [(school["subs"]["HIST"].subject_id, None)]},
                      actor=ADMIN)
    with pytest.raises(OP.ValidationError, match="isn't offered"):
        OP.set_blocks(r.round_id, {"A": [(school["subs"]["ENG"].subject_id, None)]},
                      actor=ADMIN)
    rows = OP.set_blocks(r.round_id, {"A": [(school["subs"]["HIST"].subject_id, None)]},
                         actor=ADMIN)
    assert [(b["block"], b["code"], b["capacity"]) for b in rows] == [("A", "HIST", 5)]


def test_suggested_blocks_separate_subjects_chosen_together(school):
    r = _open_with_choices(school)
    plan = OP.suggest_blocks(r.round_id)
    where = {sid: b for b, items in plan.items() for sid, _size in items}
    assert set(plan) == {"A", "B", "C"}
    assert set(where) == set(ids(school, "HIST", "GEOG", "FREN", "ART", "COMP", "MUS", "DT"))
    assert all(size >= r.class_size for items in plan.values() for _sid, size in items)
    hist, comp = ids(school, "HIST", "COMP")
    assert where[hist] != where[comp]          # chosen together by three pupils


def test_allocation_uses_reserves_and_keeps_hand_placing(school):
    # Ava: HIST ART COMP (MUS) · Ben: GEOG ART COMP (DT) · Cat: HIST GEOG FREN (ART)
    r = _open_with_choices(school, 3)
    OP.set_status(r.round_id, "Closed", actor=ADMIN)
    s = school["subs"]
    OP.set_blocks(r.round_id, {
        "A": [(s["HIST"].subject_id, None), (s["GEOG"].subject_id, None)],
        "B": [(s["ART"].subject_id, 1), (s["DT"].subject_id, None)],
        "C": [(s["COMP"].subject_id, None), (s["FREN"].subject_id, None)]}, actor=ADMIN)
    ava, ben, cat = school["pupils"][:3]
    rep = OP.allocate(r.round_id, actor=ADMIN)
    assert (rep["placed"], rep["reserves_used"]) == (2, 1)
    assert {a.code: a.block for a in OP.allocations(r.round_id, ava)} == {
        "HIST": "A", "ART": "B", "COMP": "C"}
    # Art's one place went to Ava, so Ben gets his reserve (DT) instead.
    assert {a.code: (a.block, a.from_reserve) for a in OP.allocations(r.round_id, ben)} == {
        "GEOG": ("A", False), "DT": ("B", True), "COMP": ("C", False)}
    # Cat's HIST and GEOG are both in block A and her reserve (ART) is full.
    assert [u["pupil_id"] for u in rep["unresolved"]] == [cat]
    assert "can't fit HIST, GEOG, FREN" in rep["unresolved"][0]["why"]
    status = OP.allocation_status(r.round_id)
    assert (status["allocated"], status["all_first_choices"]) == (2, 1)
    with pytest.raises(OP.ValidationError, match="GEOG doesn't run in block B"):
        OP.place_by_hand(r.round_id, cat, {"A": s["HIST"].subject_id,
                                           "B": s["GEOG"].subject_id,
                                           "C": s["FREN"].subject_id}, actor=ADMIN)
    _a, warnings = OP.place_by_hand(r.round_id, cat, {"A": s["HIST"].subject_id,
                                                      "B": s["DT"].subject_id,
                                                      "C": s["FREN"].subject_id},
                                    actor=ADMIN)
    assert warnings == ["Cat didn't choose DT"]
    rep = OP.allocate(r.round_id, actor=ADMIN)            # hand placements are kept
    assert (rep["manual"], rep["unresolved"]) == (1, [])
    assert {a.code for a in OP.allocations(r.round_id, cat)} == {"HIST", "DT", "FREN"}


def test_allocation_needs_a_closed_round_with_blocks(school):
    r = _open_with_choices(school, 1)
    with pytest.raises(OP.ValidationError, match="Close the round"):
        OP.allocate(r.round_id, actor=ADMIN)
    OP.set_status(r.round_id, "Closed", actor=ADMIN)
    with pytest.raises(OP.ValidationError, match="blocks first"):
        OP.allocate(r.round_id, actor=ADMIN)


def _finalised(school):
    r = _open_with_choices(school, 1)                    # Ava: HIST ART COMP (MUS)
    OP.set_status(r.round_id, "Closed", actor=ADMIN)
    s = school["subs"]
    OP.set_blocks(r.round_id, {"A": [(s["HIST"].subject_id, None)],
                               "B": [(s["ART"].subject_id, None)],
                               "C": [(s["COMP"].subject_id, None)]}, actor=ADMIN)
    assert OP.allocate(r.round_id, actor=ADMIN)["unresolved"] == []
    return OP.set_status(r.round_id, "Finalised", actor=ADMIN)


def test_finalised_round_is_locked(school):
    r = _finalised(school)
    ava = school["pupils"][0]
    with pytest.raises(OP.ValidationError, match="finalised"):
        OP.submit_choices(r.round_id, ava, ids(school, "HIST", "ART", "COMP"),
                          ids(school, "MUS"), actor=ADMIN)
    with pytest.raises(OP.ValidationError, match="can't be deleted"):
        OP.delete_round(r.round_id, actor=ADMIN)


def test_results_email_and_year_10_groups(school):
    r = _finalised(school)
    ava = school["pupils"][0]
    C.add_contact(ava, {"full_name": "Ava's Dad", "relationship": "Father",
                        "email": "dad@example.org", "receives_email": True,
                        "parental_responsibility": True}, actor=ADMIN)
    ids_sent, no_email = OP.email_results(r.round_id, actor=ADMIN)
    assert len(ids_sent) == 1 and no_email == []
    with database.connect() as conn:
        (body,) = conn.execute("SELECT body FROM email_recipients WHERE message_id = ?",
                               (ids_sent[0],)).fetchone()
    assert "Block A: History" in body and "Everyone also studies: English, Maths." in body
    with pytest.raises(OP.ValidationError, match="after the year rollover"):
        OP.create_groups(r.round_id, actor=ADMIN)
    P.update_pupil(ava, {"year_group": 10}, actor=ADMIN)
    rep = OP.create_groups(r.round_id, actor=ADMIN)
    assert sorted(rep["created"]) == ["10A/HIST", "10B/ART", "10C/COMP"]
    assert rep["added"] == 3
    g = TG.find("10A/HIST")
    assert (g.kind, g.year_group) == ("Option", 10)
    assert [p.pupil_id for p in TG.members(g.group_id)] == [ava]
    again = OP.create_groups(r.round_id, actor=ADMIN)
    assert (again["created"], again["added"], again["refused"]) == ([], 0, [])


def test_export_choices(school, tmp_path):
    r = _finalised(school)
    path = tmp_path / "options.csv"
    assert OP.export_choices(r.round_id, path, actor=TUTOR) == 1
    header, row = list(csv.reader(path.open(encoding="utf-8")))
    assert header[3:10] == ["Choice 1", "Choice 2", "Choice 3", "Reserve 1", "Block A",
                            "Block B", "Block C"]
    assert row[3:10] == ["HIST", "ART", "COMP", "MUS", "HIST", "ART", "COMP"]
