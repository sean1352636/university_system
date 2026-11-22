"""Digital signatures: who signs as what, and a signature lapsing on an edit.

Hashing and sign-off state are tested pure. Signing plans and documents
runs through the services on the conftest's throwaway database, with
the document store under ``tmp_path``.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system import paths
from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.records import signatures as rules
from education_system.systems.apprenticeships.domain.records.signatures import (
    AWAITING,
    INVALIDATED,
    SIGNED,
    Signature,
)
from education_system.systems.apprenticeships.domain.training.learning_plan import (
    LearningObjective,
)
from education_system.systems.apprenticeships.domain.training.sessions import TrainingPlanItem
from education_system.systems.apprenticeships.application.compliance import compliance_service
from education_system.systems.apprenticeships.application.learning import (
    learning_plan_service,
    training_service,
)
from education_system.systems.apprenticeships.application.records import (
    document_service,
    signature_service,
)
from education_system.systems.apprenticeships.application.security.access import PermissionDenied


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    data = tmp_path / "var"
    monkeypatch.setattr(paths, "APPRENTICESHIPS_DATA_DIR", data)
    monkeypatch.setattr(paths, "APPRENTICESHIPS_EVIDENCE_DIR", data / "evidence")
    monkeypatch.setattr(paths, "APPRENTICESHIPS_EXPORTS_DIR", data / "exports")
    monkeypatch.setattr(paths, "APPRENTICESHIPS_DOCUMENTS_DIR", data / "documents")
    return data / "documents"


def _plan(admin, cohort):
    """One objective with one activity under it."""
    aid = cohort["apprentice_id"]
    objective = learning_plan_service.add_objective(admin, aid, {
        "title": "Build a small network",
        "target_date": (date.today() + timedelta(days=60)).isoformat(),
    })
    training_service.add_plan_item(admin, aid, {
        "title": "Cabling workshop", "objective_id": objective.objective_id,
    })
    return objective


def _agreement(admin, cohort, tmp_path, *, category="Learning Agreement", name="agreement.pdf"):
    path = tmp_path / name
    path.write_bytes(b"%PDF-1.4 " + name.encode())
    return document_service.upload_document(
        admin, path, category=category, apprentice_id=cohort["apprentice_id"]
    )


def _objective(**overrides) -> LearningObjective:
    fields = dict(objective_id=1, apprentice_id=1, title="Configure a network",
                  target_date="2026-12-01")
    fields.update(overrides)
    return LearningObjective(**fields)


def _signature(role: str, content_hash: str, signature_id: int = 1) -> Signature:
    return Signature(
        signature_id=signature_id, entity_type="learning_plan", entity_id=1,
        signatory_role=role, signed_by=role.lower(), statement="Agreed",
        content_hash=content_hash, signed_at=f"2026-09-0{signature_id} 10:00:00",
    )


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

class TestHashing:
    def test_the_plan_hash_ignores_order_and_progress(self):
        a, b = _objective(objective_id=1), _objective(objective_id=2, title="Second")
        baseline = rules.plan_hash([a, b], [])
        assert rules.plan_hash([b, a], []) == baseline
        worked = _objective(objective_id=1, status="In progress", progress=60)
        assert rules.plan_hash([worked, b], []) == baseline

    def test_changing_what_was_agreed_changes_the_hash(self):
        baseline = rules.plan_hash([_objective()], [])
        assert rules.plan_hash([_objective(title="Something else")], []) != baseline
        assert rules.plan_hash([_objective(target_date="2027-01-01")], []) != baseline
        activity = TrainingPlanItem(item_id=1, apprentice_id=1, title="Workshop")
        assert rules.plan_hash([_objective()], [activity]) != baseline

    def test_hours_compare_as_numbers(self):
        seven = TrainingPlanItem(item_id=1, apprentice_id=1, title="W", planned_hours=7)
        seven_point_oh = TrainingPlanItem(item_id=1, apprentice_id=1, title="W",
                                          planned_hours=7.0)
        assert rules.plan_hash([], [seven]) == rules.plan_hash([], [seven_point_oh])


class TestSignOffState:
    def test_signed_invalidated_and_awaiting(self):
        state = rules.signoff(
            "learning_plan", 1, "now", rules.required_signatories("learning_plan"),
            [_signature("Apprentice", "now", 1), _signature("Employer", "before", 2)],
        )
        assert [state.state(r) for r in ("Apprentice", "Employer", "Provider")] == [
            SIGNED, INVALIDATED, AWAITING,
        ]
        assert state.outstanding == ["Employer", "Provider"]
        assert state.invalidated == ["Employer"]
        assert state.summary.startswith("1 of 3 signed")
        assert not state.is_complete

    def test_re_signing_after_a_change_counts(self):
        state = rules.signoff(
            "learning_plan", 1, "now", ("Apprentice",),
            [_signature("Apprentice", "before", 1), _signature("Apprentice", "now", 2)],
        )
        assert state.state("Apprentice") == SIGNED and state.is_complete

    def test_requirements_come_from_config(self):
        assert rules.required_signatories("learning_plan") == config.SIGNATORY_ROLES
        assert rules.required_signatories("document", "Commitment Statement") == (
            config.SIGNATORY_ROLES
        )
        assert rules.required_signatories("document", "Identity") == ()

    def test_each_role_signs_as_one_signatory(self):
        assert [rules.signatory_for(r) for r in config.ROLES] == [
            "Provider", "Provider", "Apprentice", "Employer", None,
        ]


# ═════════════════════════════════════════════════════════════════════
# The learning plan
# ═════════════════════════════════════════════════════════════════════

class TestPlanSignOff:
    def test_each_party_signs_as_their_own_signatory(self, cohort, admin):
        _plan(admin, cohort)
        aid = cohort["apprentice_id"]
        signed = [
            learning_plan_service.sign_plan(cohort[who], aid)
            for who in ("learner", "employer_actor", "tutor")
        ]
        assert [(s.signatory_role, s.signed_by) for s in signed] == [
            ("Apprentice", "apprentice1"), ("Employer", "employer1"), ("Provider", "tutor1"),
        ]
        state = learning_plan_service.plan_signatures(admin, aid)
        assert state.is_complete and state.summary == "Fully signed"

    def test_editing_the_plan_invalidates_the_signatures(self, cohort, admin):
        objective = _plan(admin, cohort)
        aid = cohort["apprentice_id"]
        learning_plan_service.sign_plan(cohort["learner"], aid)
        learning_plan_service.sign_plan(cohort["employer_actor"], aid)

        learning_plan_service.update_objective(
            admin, objective.objective_id, {"title": "Build and document a small network"}
        )
        state = learning_plan_service.plan_signatures(admin, aid)
        assert (state.state("Apprentice"), state.state("Employer")) == (INVALIDATED, INVALIDATED)

        (waiting,) = [p for p in signature_service.awaiting_signature(cohort["learner"])
                      if p.entity_type == "learning_plan"]
        assert waiting.status == INVALIDATED

        learning_plan_service.sign_plan(cohort["learner"], aid)
        state = learning_plan_service.plan_signatures(admin, aid)
        assert state.state("Apprentice") == SIGNED
        assert len(state.for_role("Apprentice")) == 2

    def test_adding_an_activity_invalidates_them_too(self, cohort, admin):
        _plan(admin, cohort)
        aid = cohort["apprentice_id"]
        learning_plan_service.sign_plan(cohort["tutor"], aid)
        training_service.add_plan_item(admin, aid, {"title": "Fibre splicing"})
        assert learning_plan_service.plan_signatures(admin, aid).state("Provider") == INVALIDATED

    def test_recording_progress_does_not(self, cohort, admin):
        objective = _plan(admin, cohort)
        aid = cohort["apprentice_id"]
        learning_plan_service.sign_plan(cohort["learner"], aid)
        learning_plan_service.record_progress(admin, objective.objective_id, progress=60)
        assert learning_plan_service.plan_signatures(admin, aid).state("Apprentice") == SIGNED

    def test_signing_the_same_content_twice_is_refused(self, cohort, admin):
        _plan(admin, cohort)
        learning_plan_service.sign_plan(cohort["learner"], cohort["apprentice_id"])
        with pytest.raises(ValidationError, match="already"):
            learning_plan_service.sign_plan(cohort["learner"], cohort["apprentice_id"])

    def test_an_empty_plan_cannot_be_signed(self, cohort):
        with pytest.raises(ValidationError, match="nothing on this plan"):
            learning_plan_service.sign_plan(cohort["learner"], cohort["apprentice_id"])

    def test_outsiders_cannot_sign(self, cohort, admin, assessor):
        _plan(admin, cohort)
        with pytest.raises(PermissionDenied):
            learning_plan_service.sign_plan(cohort["outsider"], cohort["apprentice_id"])
        with pytest.raises(PermissionDenied):
            learning_plan_service.sign_plan(assessor, cohort["apprentice_id"])

    def test_a_signature_is_audited(self, cohort, admin):
        _plan(admin, cohort)
        learning_plan_service.sign_plan(cohort["learner"], cohort["apprentice_id"])
        (entry,) = compliance_service.audit_trail(admin, entity="learning_plan", action="sign")
        assert entry.entity_id == str(cohort["apprentice_id"])
        assert entry.changes[0].after == SIGNED


# ═════════════════════════════════════════════════════════════════════
# Documents
# ═════════════════════════════════════════════════════════════════════

class TestDocumentSignOff:
    def test_agreements_need_three_signatures_and_identity_none(self, cohort, admin, tmp_path):
        agreement = _agreement(admin, cohort, tmp_path)
        identity = _agreement(admin, cohort, tmp_path, category="Identity", name="id.pdf")
        assert signature_service.signoff(admin, "document", agreement.document_id).required == (
            config.SIGNATORY_ROLES
        )
        assert signature_service.signoff(admin, "document", identity.document_id).required == ()
        with pytest.raises(ValidationError, match="does not need signing"):
            signature_service.sign(cohort["learner"], "document", identity.document_id)

    def test_a_new_version_needs_signing_afresh(self, cohort, admin, tmp_path):
        first = _agreement(admin, cohort, tmp_path)
        signature_service.sign(cohort["learner"], "document", first.document_id)
        replacement = tmp_path / "agreement-v2.pdf"
        replacement.write_bytes(b"%PDF-1.4 revised terms")
        second = document_service.upload_new_version(admin, first.document_id, replacement)

        assert signature_service.signoff(
            admin, "document", second.document_id
        ).state("Apprentice") == AWAITING
        assert signature_service.signoff(
            admin, "document", first.document_id
        ).state("Apprentice") == SIGNED
        with pytest.raises(ValidationError, match="newer version"):
            signature_service.sign(cohort["employer_actor"], "document", first.document_id)

    def test_a_file_changed_on_disk_cannot_be_signed(self, cohort, admin, tmp_path, store):
        agreement = _agreement(admin, cohort, tmp_path)
        (store / agreement.stored_name).write_bytes(b"%PDF-1.4 quietly different terms")
        with pytest.raises(ValidationError, match="no longer matches"):
            signature_service.sign(cohort["learner"], "document", agreement.document_id)

    def test_awaiting_holds_what_the_signatory_still_owes(self, cohort, admin, tmp_path):
        _plan(admin, cohort)
        agreement = _agreement(admin, cohort, tmp_path)
        employer = cohort["employer_actor"]
        keys = {p.key for p in signature_service.awaiting_signature(employer)}
        assert keys == {
            f"learning_plan:{cohort['apprentice_id']}", f"document:{agreement.document_id}",
        }

        learning_plan_service.sign_plan(employer, cohort["apprentice_id"])
        signature_service.sign(employer, "document", agreement.document_id)
        assert signature_service.awaiting_signature(employer) == []
        assert signature_service.awaiting_signature(cohort["outsider"]) == []

    def test_a_rejected_agreement_is_not_awaited(self, cohort, tmp_path):
        path = tmp_path / "commitment.pdf"
        path.write_bytes(b"%PDF-1.4 commitment")
        document = document_service.upload_document(
            cohort["learner"], path, category="Commitment Statement"
        )
        document_service.reject_document(cohort["tutor"], document.document_id, reason="Unsigned")
        assert not [p for p in signature_service.awaiting_signature(cohort["tutor"])
                    if p.entity_type == "document"]
        with pytest.raises(ValidationError, match="rejected"):
            signature_service.sign(cohort["tutor"], "document", document.document_id)
