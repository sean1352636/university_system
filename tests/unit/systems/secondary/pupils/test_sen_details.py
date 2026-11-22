"""SEN details (domain.sen_details) on a scratch school DB.

The activity log is redirected, so nothing touches live data.
"""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.secondary.modules.pupils.domain import sen_details as SEN
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="teacher1", role="teacher")


@pytest.fixture(autouse=True)
def scratch(tmp_path):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    yield
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


_n = 0


def _pupil(sen="K", year=11):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Sen{_n:03d}",
        "date_of_birth": f"{2026 - year - 4}-01-15", "gender": "Female", "year_group": year,
        "admission_date": "2021-09-01", "sen_status": sen}, actor=ADMIN)


def test_only_the_senco_saves():
    p = _pupil()
    with pytest.raises(SEN.PermissionDenied):
        SEN.save(p.pupil_id, {"primary_need": "SPLD"}, actor=TEACHER)
    assert SEN.get(p.pupil_id) is None


def test_save_upper_cases_the_need_and_audits():
    p = _pupil()
    d = SEN.save(p.pupil_id, {"primary_need": "spld", "exam_access": "Reader"}, actor=ADMIN)
    assert d.primary_need == "SPLD"
    assert d.primary_label == "Specific learning difficulty"
    hist = SEN.history(p.pupil_id)
    assert hist[0]["action"] == "save"
    assert "primary_need" in hist[0]["fields"]


def test_rules_are_collected_together():
    p = _pupil(sen="K")
    future = (dt.date.today() + dt.timedelta(days=5)).isoformat()
    with pytest.raises(SEN.ValidationError) as e:
        SEN.save(p.pupil_id, {"secondary_need": "XYZ", "ehcp_reference": "R1",
                              "ehcp_issued_on": future}, actor=ADMIN)
    text = " ".join(e.value.problems)
    assert "Choose the primary area of need" in text
    assert "Secondary need must be one of" in text
    assert "can't be in the future" in text
    assert "Only a pupil with an EHC plan" in text


def test_secondary_need_differs_from_primary():
    p = _pupil()
    with pytest.raises(SEN.ValidationError):
        SEN.save(p.pupil_id, {"primary_need": "ASD", "secondary_need": "asd"}, actor=ADMIN)


def test_no_details_without_sen_status():
    p = _pupil(sen="N")
    with pytest.raises(SEN.ValidationError) as e:
        SEN.save(p.pupil_id, {"primary_need": "ASD"}, actor=ADMIN)
    assert "no SEN status" in e.value.problems[0]


def test_ehc_plan_details_and_partial_update_keeps_the_rest():
    p = _pupil(sen="E")
    SEN.save(p.pupil_id, {"primary_need": "ASD", "ehcp_reference": "EHC-1",
                          "ehcp_issued_on": "2020-01-01", "provision": "TA"}, actor=ADMIN)
    d = SEN.save(p.pupil_id, {"strategies": "Seat at front"}, actor=ADMIN)
    assert (d.ehcp_reference, d.provision, d.strategies) == ("EHC-1", "TA", "Seat at front")


def test_handover_block():
    none = _pupil(sen="N")
    assert SEN.handover_block(none) is None
    p = _pupil(sen="E")
    SEN.save(p.pupil_id, {"primary_need": "ASD", "secondary_need": "SEMH",
                          "ehcp_reference": "EHC-9", "exam_access": "25% extra time"},
             actor=ADMIN)
    b = SEN.handover_block(P.get_pupil(p.pupil_id))
    assert b["sen_status"] == "E"
    assert b["primary_need"] == "ASD"
    assert b["secondary_need_label"].startswith("Social")
    assert b["ehcp_reference"] == "EHC-9"
    assert b["exam_access"] == "25% extra time"
    # A pupil with SEN support but no details yet still says so.
    k = _pupil(sen="K")
    assert SEN.handover_block(k) == {"sen_status": "K", "sen_status_label": "SEN support"}


def test_clear_and_register():
    p = _pupil()
    q = _pupil()
    _pupil(sen="N")
    SEN.save(p.pupil_id, {"primary_need": "MLD"}, actor=ADMIN)
    reg = {pp.pupil_id: d for pp, d in SEN.register(year_group=11)}
    assert set(reg) >= {p.pupil_id, q.pupil_id}
    assert reg[q.pupil_id] is None
    SEN.clear(p.pupil_id, actor=ADMIN)
    assert SEN.get(p.pupil_id) is None
    assert SEN.history(p.pupil_id)[0]["action"] == "clear"


def test_summary_line():
    p = _pupil(sen="K")
    assert "details not recorded" in SEN.summary_line(p)
    SEN.save(p.pupil_id, {"primary_need": "HI"}, actor=ADMIN)
    assert "Hearing impairment (HI)" in SEN.summary_line(p)
