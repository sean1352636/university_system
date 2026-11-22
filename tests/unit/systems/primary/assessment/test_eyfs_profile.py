"""EYFS Profile (domain.assessment.eyfs_profile.eyfs_profile)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.assessment.eyfs_profile import eyfs_profile as EY
from education_system.systems.primary.domain.learners.pupils import pupils as P

YEAR = "2025-26"
_n = 0


def _pupil(year="R", last=None):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Child{_n}", "last_name": last or f"Test{_n:03d}",
                           "year_group": year, "date_of_birth": "2020-03-01"})


def _all(pupil, status="Expected", codes=None, year=YEAR):
    for code in codes or EY.ELG_CODES:
        EY.set_elg(pupil.pupil_id, year, code, status)


# ── the framework ────────────────────────────────────────────────────

def test_seventeen_elgs_in_seven_areas():
    assert len(EY.ELG_CODES) == 17
    assert len(set(EY.ELG_CODES)) == 17
    assert len(EY.AREAS) == 7
    assert EY.AREAS[0] == "Communication & Language"


def test_gld_uses_prime_areas_plus_literacy_and_maths():
    assert len(EY.GLD_CODES) == 12
    gld_areas = {EY.ELG_AREAS[c] for c in EY.GLD_CODES}
    assert gld_areas == {"Communication & Language",
                         "Personal, Social & Emotional Development",
                         "Physical Development", "Literacy", "Mathematics"}
    assert not any(EY.ELG_GLD[c] for c in ("UW01", "UW02", "UW03", "EAD01", "EAD02"))


def test_statuses_are_emerging_and_expected_only():
    assert EY.STATUSES == ("Emerging", "Expected")


# ── set_elg / get / delete ───────────────────────────────────────────

def test_set_elg_stores_and_normalises():
    p = _pupil()
    r = EY.set_elg(p.pupil_id, YEAR, " lit02 ", "expected",
                   assessed_on="2026-06-20", notes="  reads CVC words ")
    assert (r.elg_code, r.status, r.assessed_on, r.notes) == (
        "LIT02", "Expected", "2026-06-20", "reads CVC words")
    assert r.area == "Literacy" and r.label == "Word Reading" and r.contributes_to_gld
    assert EY.get(r.result_id) == r


def test_set_elg_upserts_the_same_row():
    p = _pupil()
    first = EY.set_elg(p.pupil_id, YEAR, "UW01", "Emerging", notes="n1")
    again = EY.set_elg(p.pupil_id, YEAR, "UW01", "Expected")
    assert again.result_id == first.result_id
    assert again.status == "Expected" and again.notes is None
    assert not again.contributes_to_gld
    assert EY.get_profile(p.pupil_id, YEAR).elgs_recorded == 1


def test_same_elg_in_another_year_is_a_new_row():
    p = _pupil()
    a = EY.set_elg(p.pupil_id, "2025-26", "CL01", "Expected")
    b = EY.set_elg(p.pupil_id, "2026-27", "CL01", "Emerging")
    assert a.result_id != b.result_id


@pytest.mark.parametrize("args, message", [
    (("", YEAR, "CL01", "Expected"), "Pupil ID is required"),
    (("@", "", "CL01", "Expected"), "Academic year is required"),
    (("@", "2025/26", "CL01", "Expected"), "Academic year must look like"),
    (("@", YEAR, "", "Expected"), "ELG code is required"),
    (("@", YEAR, "CL09", "Expected"), "ELG code must be one of"),
    (("@", YEAR, "CL01", ""), "Status is required"),
    (("@", YEAR, "CL01", "Exceeding"), "Status must be one of Emerging, Expected"),
])
def test_set_elg_refuses_invalid(args, message):
    p = _pupil()
    args = tuple(p.pupil_id if a == "@" else a for a in args)
    with pytest.raises(P.ValidationError, match=message):
        EY.set_elg(*args)


def test_set_elg_refuses_bad_date_and_unknown_pupil():
    p = _pupil()
    with pytest.raises(P.ValidationError, match="Assessed-on date must be YYYY-MM-DD"):
        EY.set_elg(p.pupil_id, YEAR, "CL01", "Expected", assessed_on="20/06/2026")
    with pytest.raises(P.ValidationError, match="No pupil with id P0000000"):
        EY.set_elg("P0000000", YEAR, "CL01", "Expected")
    assert EY.get_profile(p.pupil_id, YEAR).elgs_recorded == 0


def test_get_and_delete():
    p = _pupil()
    r = EY.set_elg(p.pupil_id, YEAR, "PD01", "Expected")
    assert EY.delete(r.result_id) is True
    assert EY.get(r.result_id) is None
    assert EY.delete(r.result_id) is False


def test_clear_pupil_year_removes_only_that_year():
    p = _pupil()
    _all(p, codes=("CL01", "CL02", "PD01"))
    EY.set_elg(p.pupil_id, "2026-27", "CL01", "Expected")
    assert EY.clear_pupil_year(p.pupil_id, YEAR) == 3
    assert EY.get_profile(p.pupil_id, YEAR).elgs_recorded == 0
    assert EY.get_profile(p.pupil_id, "2026-27").elgs_recorded == 1
    assert EY.clear_pupil_year(p.pupil_id, YEAR) == 0
    with pytest.raises(P.ValidationError, match="No pupil"):
        EY.clear_pupil_year("P0000000", YEAR)


# ── profile and GLD ──────────────────────────────────────────────────

def test_profile_counts():
    p = _pupil()
    _all(p, codes=EY.GLD_CODES)
    EY.set_elg(p.pupil_id, YEAR, "UW01", "Emerging")
    EY.set_elg(p.pupil_id, YEAR, "EAD01", "Expected")
    pr = EY.get_profile(p.pupil_id, YEAR)
    assert pr.elgs_recorded == 14 and pr.elgs_total == 17
    assert pr.expected_count == 13
    assert pr.has_gld and pr.gld_missing == []


def test_gld_needs_every_gld_elg_recorded():
    p = _pupil()
    _all(p, codes=[c for c in EY.GLD_CODES if c != "MAT02"])
    pr = EY.get_profile(p.pupil_id, YEAR)
    assert not pr.has_gld and pr.gld_missing == ["MAT02"]


def test_one_emerging_gld_elg_breaks_gld_even_if_all_else_expected():
    p = _pupil()
    _all(p)
    EY.set_elg(p.pupil_id, YEAR, "PSED02", "Emerging")
    pr = EY.get_profile(p.pupil_id, YEAR)
    assert pr.expected_count == 16
    assert not pr.has_gld and pr.gld_missing == ["PSED02"]


def test_emerging_in_uw_or_ead_still_has_gld():
    p = _pupil()
    _all(p)
    for code in ("UW01", "UW02", "UW03", "EAD01", "EAD02"):
        EY.set_elg(p.pupil_id, YEAR, code, "Emerging")
    assert EY.get_profile(p.pupil_id, YEAR).has_gld


def test_empty_profile_misses_all_gld_codes():
    pr = EY.get_profile(_pupil().pupil_id, YEAR)
    assert pr.elgs_recorded == 0 and not pr.has_gld
    assert pr.gld_missing == list(EY.GLD_CODES)


def test_get_profile_unknown_pupil_is_refused():
    with pytest.raises(P.ValidationError, match="No pupil"):
        EY.get_profile("P0000000", YEAR)


# ── cohort ───────────────────────────────────────────────────────────

def test_list_pupils_with_profiles_sorted_by_name_and_filtered():
    zed = _pupil("R", last="Zed")
    abe = _pupil("R", last="Abe")
    y1 = _pupil("1", last="Mid")
    _pupil("R", last="Nobody")                     # no rows: not listed
    for p in (zed, abe, y1):
        EY.set_elg(p.pupil_id, YEAR, "CL01", "Expected")
    EY.set_elg(abe.pupil_id, "2024-25", "CL01", "Expected")
    rows = EY.list_pupils_with_profiles(YEAR)
    assert [p.last_name for p, _ in rows] == ["Abe", "Mid", "Zed"]
    assert all(pr.elgs_recorded == 1 for _, pr in rows)
    assert [p.last_name for p, _ in EY.list_pupils_with_profiles(YEAR, year_group="1")] == ["Mid"]
    with pytest.raises(P.ValidationError, match="Year filter"):
        EY.list_pupils_with_profiles(YEAR, year_group="N")


def test_cohort_summary():
    full_gld = _pupil()
    _all(full_gld)                                 # complete + GLD
    gld_only = _pupil()
    _all(gld_only, codes=EY.GLD_CODES)             # GLD, incomplete
    complete_no_gld = _pupil()
    _all(complete_no_gld)
    EY.set_elg(complete_no_gld.pupil_id, YEAR, "CL02", "Emerging")
    partial = _pupil()
    _all(partial, codes=("CL01",))
    s = EY.cohort_summary(YEAR)
    assert s == {"academic_year": YEAR, "pupils": 4, "complete_profiles": 2,
                 "gld_count": 2, "gld_pct": 50.0}


def test_cohort_summary_empty_year():
    assert EY.cohort_summary("2030-31") == {"academic_year": "2030-31", "pupils": 0,
                                            "complete_profiles": 0, "gld_count": 0,
                                            "gld_pct": 0.0}


def test_known_years_newest_first():
    assert EY.known_years() == []
    p = _pupil()
    EY.set_elg(p.pupil_id, "2024-25", "CL01", "Expected")
    EY.set_elg(p.pupil_id, "2025-26", "CL01", "Expected")
    EY.set_elg(p.pupil_id, "2025-26", "CL02", "Expected")
    assert EY.known_years() == ["2025-26", "2024-25"]
