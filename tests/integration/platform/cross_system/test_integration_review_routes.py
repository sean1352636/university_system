"""The changes from the 2026-11 integration review (systems.txt).

* eight more declared boundaries: University → FE College / Sixth Form, and
  a same-phase (change of institution) route for every system but nursery;
* same-phase moves go through ``transfer_within_phase`` — never the
  destination adapter, which is the learner's own system;
* a name + DOB match that fits two journeys links to neither;
* failed best-effort syncs are kept, listed, retried and abandoned.

Every case runs against an isolated temp auth DB.
"""

from __future__ import annotations

import pytest

from education_system.platform.cross_system import (
    destinations,
    enrolment_schema,
    enrolments,
    handover,
    identity_service,
    progression,
    route_support,
    sync_failures,
    transitions,
)
from education_system.platform.cross_system.adapters.base import (
    ExportResult,
    PhaseAdapter,
)

NEW_BOUNDARIES = [
    ("university", "fe_college"), ("university", "sixth_form"),
    ("primary", "primary"), ("secondary", "secondary"),
    ("sixth_form", "sixth_form"), ("fe_college", "fe_college"),
    ("apprenticeships", "apprenticeships"), ("university", "university"),
]


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "auth.db")
    enrolment_schema.reset_schema_cache_for_test()
    destinations.reset_schema_cache_for_test()
    identity_service._initialised.clear()
    enrolment_schema.ensure_enrolment_schema(path)
    yield path
    enrolment_schema.reset_schema_cache_for_test()
    destinations.reset_schema_cache_for_test()
    identity_service._initialised.clear()


# ── Specs ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("source,destination", NEW_BOUNDARIES)
def test_new_boundary_is_declared(source, destination):
    spec = handover.get_spec(source, destination)
    assert spec is not None
    assert "safeguarding_reference" in spec.restricted_keys()
    assert "documents_received" in spec.checklist_keys()


@pytest.mark.parametrize("system", sorted(handover.IN_PHASE_SPECS))
def test_in_phase_specs_require_the_receiving_institution(system):
    spec = handover.IN_PHASE_SPECS[system]
    assert spec.source_system == spec.destination_system == system
    assert {"receiving_institution", "move_details"} <= set(spec.required_keys())


def test_new_specs_do_not_downgrade_any_key():
    # _KEY_SENSITIVITY takes the most restrictive level; a new spec marking
    # a known-sensitive key routine would be ignored there but would leak
    # on its own boundary.
    sensitive_elsewhere = {
        f.key for (s, d), spec in handover.HANDOVER_SPECS.items()
        if (s, d) not in NEW_BOUNDARIES for f in spec.fields
        if f.sensitivity is not handover.Sensitivity.ROUTINE}
    for boundary in NEW_BOUNDARIES:
        for f in handover.HANDOVER_SPECS[boundary].fields:
            if f.key in sensitive_elsewhere:
                assert f.sensitivity is not handover.Sensitivity.ROUTINE, (
                    boundary, f.key)


# ── Same-phase transfer ──────────────────────────────────────────────

class _FakeFE(PhaseAdapter):
    system = "fe_college"

    def __init__(self):
        super().__init__()
        self.closed: list[tuple[str, str, dict]] = []

    def export_handover(self, local_student_id, consent=None, *,
                        destination_system=None):
        return ExportResult(record={
            "learner_identity": {"first_name": "Grace", "last_name": "Hopper",
                                 "date_of_birth": "2007-12-09", "uln": "1234567890"},
            "contact_details": {"email": "g@example.org"},
            "send_support": "Extra time",
        }, local_student_id=local_student_id)

    def create_applicant(self, handover):  # pragma: no cover - must not run
        raise AssertionError("an in-phase move must not create an applicant")

    def create_enrolment(self, *a, **k):  # pragma: no cover - must not run
        raise AssertionError("an in-phase move must not create an enrolment")

    def close_enrolment(self, local_student_id, reason, **details):
        self.closed.append((local_student_id, reason, details))


@pytest.fixture
def fe(monkeypatch):
    adapter = _FakeFE()
    monkeypatch.setattr(route_support, "adapter_for", lambda system: adapter)
    return adapter


def test_transfer_refuses_a_same_phase_move(db, fe):
    with pytest.raises(route_support.RouteError, match="transfer_within_phase"):
        route_support.transfer(source_system="fe_college",
                               destination_system="fe_college",
                               student_id="FE1", reason="moving", db_path=db)


def test_transfer_within_phase_records_and_closes(db, fe):
    out = route_support.transfer_within_phase(
        system="fe_college", student_id="FE1",
        receiving_institution={"name": "Northgate College", "ukprn": "10001234"},
        reason="family moved", leaving_date="2026-10-30", db_path=db)

    row = out.transition
    assert row["status"] == "completed"
    assert row["source_system"] == row["destination_system"] == "fe_college"
    assert row.get("destination_enrolment_id") in (None, "")
    stored = transitions.get_handover(row["transition_id"], db_path=db)
    assert stored["receiving_institution"]["name"] == "Northgate College"
    assert stored["move_details"]["reason"] == "family moved"
    assert "send_support" not in stored            # no consent given
    source = enrolments.get_enrolment(row["source_enrolment_id"], db_path=db)
    assert source["status"] == "transferred"
    [(local_id, reason, details)] = fe.closed
    assert local_id == "FE1"
    assert "transfer" in reason.lower()
    assert details["destination_school"] == "Northgate College"


def test_transfer_within_phase_needs_a_destination(db, fe):
    with pytest.raises(route_support.RouteError, match="institution"):
        route_support.transfer_within_phase(
            system="fe_college", student_id="FE1", receiving_institution="  ",
            reason="moving", db_path=db)
    with pytest.raises(route_support.RouteError, match="no in-phase"):
        route_support.transfer_within_phase(
            system="nursery", student_id="N1", receiving_institution="X",
            reason="moving", db_path=db)


# ── Identity matching ────────────────────────────────────────────────

def test_two_equal_name_dob_matches_link_to_neither(db):
    kw = dict(first_name="Sam", last_name="Smith", date_of_birth="2012-03-04",
              db_path=db)
    first = identity_service.get_or_create_journey(system="primary",
                                                   student_id="P1", **kw)
    second = identity_service.get_or_create_journey(system="primary",
                                                    student_id="P2", **kw)
    assert first != second   # P1 is open, so P2 is someone else

    third = identity_service.get_or_create_journey(system="secondary",
                                                   student_id="S1", **kw)
    assert third not in (first, second)


def test_a_single_name_dob_match_still_links(db):
    kw = dict(first_name="Ana", last_name="Diaz", date_of_birth="2012-05-06",
              db_path=db)
    first = identity_service.get_or_create_journey(system="primary",
                                                   student_id="P9", **kw)
    assert identity_service.get_or_create_journey(
        system="secondary", student_id="S9", **kw) == first


# ── Failed syncs ─────────────────────────────────────────────────────

def test_failed_registration_is_kept_and_retried(db, monkeypatch):
    real = identity_service.get_or_create_journey

    def broken(**kw):
        raise RuntimeError("auth.db locked")

    monkeypatch.setattr(identity_service, "get_or_create_journey", broken)
    assert progression.register_local_student(
        "primary", student_id="P5", first_name="Lee", last_name="Ng",
        date_of_birth="2015-01-01", db_path=db) is None

    [failure] = sync_failures.list_failures(db_path=db)
    assert failure["operation"] == "register_local_student"
    assert failure["system"] == "primary" and failure["local_id"] == "P5"
    assert "auth.db locked" in failure["error_message"]

    with pytest.raises(RuntimeError):
        sync_failures.retry(failure["failure_id"], actor="t", db_path=db)
    assert sync_failures.get_failure(failure["failure_id"], db_path=db)["attempts"] == 2

    monkeypatch.setattr(identity_service, "get_or_create_journey", real)
    jid = sync_failures.retry(failure["failure_id"], actor="t", db_path=db)
    assert identity_service.find_by_student("primary", "P5", db_path=db)["journey_id"] == jid
    assert sync_failures.list_failures(db_path=db) == []
    with pytest.raises(sync_failures.SyncFailureError):
        sync_failures.retry(failure["failure_id"], db_path=db)


def test_a_failure_can_be_abandoned_with_a_reason(db):
    fid = sync_failures.record_failure(
        "publish_progression", {"journey_id": "j"}, RuntimeError("x"), db_path=db)
    with pytest.raises(sync_failures.SyncFailureError):
        sync_failures.abandon(fid, reason=" ", db_path=db)
    assert sync_failures.abandon(fid, reason="learner left", actor="t", db_path=db)
    assert not sync_failures.abandon(fid, reason="again", db_path=db)
    assert sync_failures.count_open(db_path=db) == 0
