"""Record documents: where the files go, what gets in, and who sees them.

The rules are tested pure. Uploading, scoping, approval and versions run
through the service on the conftest's throwaway database, with every
apprenticeships directory — the document store included — pointed at
``tmp_path``, so nothing lands in the real var/ tree.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta

import pytest

from education_system import paths
from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.records import documents as rules
from education_system.systems.apprenticeships.domain.records.audit import FieldChange
from education_system.systems.apprenticeships.domain.records.documents import Document
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    document_repository,
)
from education_system.systems.apprenticeships.infrastructure.storage import document_store
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.compliance import compliance_service
from education_system.systems.apprenticeships.application.records import document_service
from education_system.systems.apprenticeships.application.security.access import Actor, PermissionDenied

TODAY = date.today()
CONTENT = b"%PDF-1.4 apprenticeship agreement, signed"


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    """Every apprenticeships directory under tmp_path; returns the document store."""
    data = tmp_path / "var"
    monkeypatch.setattr(paths, "APPRENTICESHIPS_DATA_DIR", data)
    monkeypatch.setattr(paths, "APPRENTICESHIPS_EVIDENCE_DIR", data / "evidence")
    monkeypatch.setattr(paths, "APPRENTICESHIPS_EXPORTS_DIR", data / "exports")
    monkeypatch.setattr(paths, "APPRENTICESHIPS_DOCUMENTS_DIR", data / "documents")
    return data / "documents"


def _file(tmp_path, name="passport.pdf", content=CONTENT):
    folder = tmp_path / "incoming"
    folder.mkdir(exist_ok=True)
    path = folder / name
    path.write_bytes(content)
    return path


def _upload(actor, cohort, tmp_path, *, category="Identity", name="passport.pdf",
            content=CONTENT, **kwargs):
    kwargs.setdefault("apprentice_id", cohort["apprentice_id"])
    return document_service.upload_document(
        actor, _file(tmp_path, name, content), category=category, **kwargs
    )


def _stored(store) -> list[str]:
    return sorted(p.name for p in store.iterdir()) if store.exists() else []


def _doc(**overrides) -> Document:
    fields = dict(
        document_id=1, category="Identity", title="Passport",
        original_filename="passport.pdf", stored_name="0" * 32 + ".pdf", size_bytes=10,
        sha256="x", uploaded_by="admin5", uploaded_role="admin",
    )
    fields.update(overrides)
    return Document(**fields)


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

class TestRules:
    @pytest.mark.parametrize("name", ["setup.exe", "page.html", "logo.svg", "README", ""])
    def test_only_allowlisted_types_get_in(self, name):
        with pytest.raises(ValidationError):
            rules.validate_upload(name, 100)

    def test_the_extension_returned_is_the_allowlists_own(self):
        assert rules.validate_upload("Signed Agreement.PDF", 100) == ".pdf"

    def test_empty_and_oversized_files_are_refused(self):
        with pytest.raises(ValidationError, match="empty"):
            rules.validate_upload("scan.pdf", 0)
        with pytest.raises(ValidationError, match="limit"):
            rules.validate_upload("scan.pdf", config.DOCUMENT_MAX_BYTES + 1)
        assert rules.validate_upload("scan.pdf", config.DOCUMENT_MAX_BYTES) == ".pdf"

    @pytest.mark.parametrize(("raw", "expected"), [
        ("../../etc/passwd.pdf", "passwd.pdf"),
        ("C:\\Users\\jo\\cv.docx", "cv.docx"),
        ("bell\x07.pdf", "bell.pdf"),
    ])
    def test_the_display_name_keeps_only_the_last_component(self, raw, expected):
        assert rules.clean_filename(raw) == expected

    def test_expiry_is_flagged_inside_the_warning_window(self):
        past = _doc(expiry_date=(TODAY - timedelta(days=1)).isoformat())
        soon = _doc(expiry_date=(TODAY + timedelta(days=5)).isoformat())
        later = _doc(expiry_date=(TODAY + timedelta(days=365)).isoformat())
        assert (past.expiry_flag(TODAY), past.rag(TODAY)) == ("Expired", "Red")
        assert (soon.expiry_flag(TODAY), soon.rag(TODAY)) == ("Expiring soon", "Amber")
        assert (later.expiry_flag(TODAY), later.rag(TODAY)) == (None, None)
        assert _doc().expiry_flag(TODAY) is None


# ═════════════════════════════════════════════════════════════════════
# Storage
# ═════════════════════════════════════════════════════════════════════

class TestStorage:
    def test_the_stored_name_is_generated_never_the_uploaders(
        self, cohort, admin, tmp_path, store
    ):
        name = "..evil name; rm -rf.pdf"
        document = _upload(admin, cohort, tmp_path, name=name)

        assert document_store.STORED_NAME.fullmatch(document.stored_name)
        assert "evil" not in document.stored_name
        assert document.original_filename == name
        assert _stored(store) == [document.stored_name]
        assert (store / document.stored_name).read_bytes() == CONTENT
        assert document.sha256 == hashlib.sha256(CONTENT).hexdigest()
        assert document.size_bytes == len(CONTENT)

    def test_the_same_filename_twice_is_two_files(self, cohort, admin, tmp_path, store):
        first = _upload(admin, cohort, tmp_path)
        second = _upload(admin, cohort, tmp_path)
        assert first.stored_name != second.stored_name
        assert len(_stored(store)) == 2

    @pytest.mark.parametrize("stored_name", [
        "../apprenticeships.db", "passport.pdf", "a" * 32 + ".pdf/../../x", "",
    ])
    def test_a_stored_name_that_is_not_ours_is_never_followed(self, stored_name):
        with pytest.raises(ValidationError):
            document_store.path_for(stored_name)

    def test_the_size_limit_is_enforced(self, cohort, admin, tmp_path, store, monkeypatch):
        monkeypatch.setattr(config, "DOCUMENT_MAX_BYTES", 16)
        with pytest.raises(ValidationError, match="limit"):
            _upload(admin, cohort, tmp_path, content=b"x" * 17)
        assert _stored(store) == []

    def test_the_store_enforces_the_limit_during_the_copy_too(self, tmp_path, store):
        with pytest.raises(ValidationError, match="limit"):
            document_store.store(_file(tmp_path, content=b"x" * 10), ".pdf", max_bytes=4)
        assert _stored(store) == []

    def test_a_type_off_the_allowlist_is_refused(self, cohort, admin, tmp_path, store):
        with pytest.raises(ValidationError, match="not a type"):
            _upload(admin, cohort, tmp_path, name="payload.exe")
        assert _stored(store) == []

    def test_a_failed_database_write_leaves_no_orphan_file(
        self, cohort, admin, tmp_path, store, monkeypatch
    ):
        def fail(_payload):
            raise RuntimeError("database locked")

        monkeypatch.setattr(document_repository, "create", fail)
        with pytest.raises(RuntimeError):
            _upload(admin, cohort, tmp_path)
        assert _stored(store) == []

    def test_a_saved_copy_is_the_same_bytes(self, cohort, admin, tmp_path, store):
        document = _upload(admin, cohort, tmp_path)
        out = tmp_path / "out"
        out.mkdir()
        saved = document_service.save_copy(admin, document.document_id, out)
        assert saved == out / "passport.pdf"
        assert saved.read_bytes() == CONTENT

        with pytest.raises(ValidationError, match="already exists"):
            document_service.save_copy(admin, document.document_id, saved)
        document_service.save_copy(admin, document.document_id, saved, overwrite=True)
        with pytest.raises(ValidationError, match="outside the document store"):
            document_service.save_copy(admin, document.document_id, store / "copy.pdf")


# ═════════════════════════════════════════════════════════════════════
# Who sees what
# ═════════════════════════════════════════════════════════════════════

class TestScope:
    def test_the_end_point_assessor_sees_only_epa_documents(
        self, cohort, admin, assessor, tmp_path
    ):
        epa = _upload(admin, cohort, tmp_path, category="EPA", name="epa-plan.pdf")
        identity = _upload(admin, cohort, tmp_path, category="Identity")

        assert [d.document_id for d in document_service.list_documents(assessor)] == [
            epa.document_id
        ]
        assert document_service.list_documents(assessor, category="Identity") == []
        assert document_service.get_document(assessor, epa.document_id).category == "EPA"
        with pytest.raises(PermissionDenied):
            document_service.get_document(assessor, identity.document_id)
        with pytest.raises(PermissionDenied):
            document_service.file_path(assessor, identity.document_id)

    def test_an_outsider_employer_is_refused(self, cohort, admin, tmp_path):
        outsider = cohort["outsider"]
        document = _upload(admin, cohort, tmp_path)

        assert document_service.list_documents(outsider) == []
        with pytest.raises(PermissionDenied):
            document_service.get_document(outsider, document.document_id)
        with pytest.raises(PermissionDenied):
            document_service.save_copy(outsider, document.document_id, tmp_path)
        with pytest.raises(PermissionDenied):
            document_service.upload_new_version(
                outsider, document.document_id, _file(tmp_path, "v2.pdf")
            )
        with pytest.raises(PermissionDenied):
            _upload(outsider, cohort, tmp_path)

    def test_an_employer_sees_their_apprentices_and_their_own_paperwork(
        self, cohort, admin, tmp_path
    ):
        employer = cohort["employer_actor"]
        theirs = _upload(admin, cohort, tmp_path)
        own = document_service.upload_document(
            employer, _file(tmp_path, "contract.pdf"), category="Other"
        )
        assert (own.apprentice_id, own.employer_id) == (None, cohort["employer"].employer_id)
        assert own.approval_status == "Pending"

        assert {d.document_id for d in document_service.list_documents(employer)} == {
            theirs.document_id, own.document_id,
        }
        # The organisation's paperwork is not the apprentice's to read.
        assert [d.document_id for d in document_service.list_documents(cohort["learner"])] == [
            theirs.document_id
        ]
        with pytest.raises(PermissionDenied):
            document_service.get_document(cohort["outsider"], own.document_id)

    def test_a_tutor_sees_their_caseload_only(self, cohort, admin, tmp_path):
        document = _upload(admin, cohort, tmp_path)
        other_tutor = Actor(username="tutor2", role="staff", staff_id=9999)
        assert [d.document_id for d in document_service.list_documents(cohort["tutor"])] == [
            document.document_id
        ]
        assert document_service.list_documents(other_tutor) == []
        with pytest.raises(PermissionDenied):
            document_service.get_document(other_tutor, document.document_id)

    def test_an_apprentice_uploads_to_their_own_record_only(self, cohort, admin, tmp_path):
        other = apprentice_service.create_apprentice(
            admin, {"given_name": "Ali", "family_name": "Khan"}
        )
        with pytest.raises(PermissionDenied):
            _upload(cohort["learner"], cohort, tmp_path, apprentice_id=other.apprentice_id)
        mine = _upload(cohort["learner"], cohort, tmp_path, apprentice_id=None)
        assert mine.apprentice_id == cohort["apprentice_id"]


# ═════════════════════════════════════════════════════════════════════
# Approval, versions, expiry, the checklist
# ═════════════════════════════════════════════════════════════════════

class TestApprovalAndVersions:
    def test_an_apprentice_upload_waits_for_provider_approval(self, cohort, admin, tmp_path):
        document = _upload(cohort["learner"], cohort, tmp_path, apprentice_id=None)
        assert document.approval_status == "Pending"
        with pytest.raises(PermissionDenied):
            document_service.approve_document(cohort["employer_actor"], document.document_id)

        approved = document_service.approve_document(cohort["tutor"], document.document_id)
        assert (approved.approval_status, approved.approved_by) == ("Approved", "tutor1")
        (entry,) = compliance_service.audit_trail(
            admin, entity="document", entity_id=document.document_id, action="approve"
        )
        assert FieldChange("approval_status", "Pending", "Approved") in entry.changes

    def test_a_provider_upload_lands_approved(self, cohort, admin, tmp_path):
        assert _upload(admin, cohort, tmp_path).approval_status == "Approved"

    def test_rejecting_needs_a_reason(self, cohort, tmp_path):
        document = _upload(cohort["learner"], cohort, tmp_path, apprentice_id=None)
        with pytest.raises(ValidationError, match="reason"):
            document_service.reject_document(cohort["tutor"], document.document_id, reason=" ")
        rejected = document_service.reject_document(
            cohort["tutor"], document.document_id, reason="Photo page is cut off"
        )
        assert (rejected.approval_status, rejected.rejection_reason) == (
            "Rejected", "Photo page is cut off",
        )

    def test_a_new_version_keeps_the_history(self, cohort, admin, tmp_path, store):
        first = _upload(admin, cohort, tmp_path)
        second = document_service.upload_new_version(
            admin, first.document_id, _file(tmp_path, "passport-renewed.pdf", b"%PDF new"),
        )
        assert (second.version, second.supersedes, second.series_id) == (
            2, first.document_id, first.document_id,
        )
        assert [d.document_id for d in document_service.list_documents(admin)] == [
            second.document_id
        ]
        history = document_service.version_history(admin, first.document_id)
        assert [d.version for d in history] == [2, 1]
        assert history[1].is_superseded
        assert len(_stored(store)) == 2
        with pytest.raises(ValidationError, match="newer version"):
            document_service.upload_new_version(
                admin, first.document_id, _file(tmp_path, "again.pdf")
            )

    def test_expired_and_expiring_documents_are_flagged(self, cohort, admin, tmp_path):
        def upload(days: int, name: str):
            return _upload(admin, cohort, tmp_path, name=name,
                           expiry_date=(TODAY + timedelta(days=days)).isoformat())

        past, soon, _later = upload(-1, "old.pdf"), upload(5, "soon.pdf"), upload(365, "ok.pdf")
        assert [d.document_id for d in document_service.expiring_documents(admin)] == [
            past.document_id, soon.document_id,
        ]
        counts = document_service.document_counts(admin)
        assert (counts["expired"], counts["expiring"], counts["total"]) == (1, 1, 3)

    def test_a_file_can_evidence_a_checklist_item(self, cohort, admin, tmp_path):
        document = _upload(admin, cohort, tmp_path, category="Commitment Statement",
                           checklist_key="commitment_statement")
        files = document_service.checklist_files(admin, cohort["apprentice_id"])
        assert [d.document_id for d in files["commitment_statement"]] == [document.document_id]
        with pytest.raises(ValidationError):
            _upload(admin, cohort, tmp_path, checklist_key="not_a_checklist_item")
        with pytest.raises(ValidationError, match="checklist"):
            document_service.upload_document(
                admin, _file(tmp_path, "contract.pdf"), category="Other",
                employer_id=cohort["employer"].employer_id, checklist_key="employer_contract",
            )
