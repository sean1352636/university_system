"""Tests for DocumentService."""

import pytest


@pytest.fixture
def doc_svc(shared_auth_db, tmp_path):
    from education_system.shared.documents.document_service import DocumentService
    docs_dir = str(tmp_path / "docs")
    return DocumentService(auth_db=shared_auth_db, documents_dir=docs_dir)


def _upload(svc, student_name="Jane Doe", title="EHCP Report", doc_type="ehcp",
            file_data=b"PDF content here", filename="report.pdf"):
    return svc.upload_document(
        student_name=student_name, student_id="STU001", system="university",
        doc_type=doc_type, title=title, description="Test document",
        file_data=file_data, filename=filename,
        uploaded_by="admin", uploaded_system="university",
    )


class TestUploadDocument:
    def test_returns_int_id(self, doc_svc):
        doc_id = _upload(doc_svc)
        assert isinstance(doc_id, int)
        assert doc_id > 0

    def test_file_saved_to_disk(self, doc_svc):
        doc_id = _upload(doc_svc, file_data=b"hello world")
        doc = doc_svc.get_document(doc_id)
        from pathlib import Path
        assert Path(doc["file_path"]).exists()
        assert Path(doc["file_path"]).read_bytes() == b"hello world"

    def test_invalid_doc_type_raises(self, doc_svc):
        with pytest.raises(ValueError, match="Invalid doc_type"):
            _upload(doc_svc, doc_type="invalid")


class TestGetDocuments:
    def test_get_by_student_name(self, doc_svc):
        _upload(doc_svc, student_name="Jane Doe")
        _upload(doc_svc, student_name="John Smith")
        results = doc_svc.get_documents(student_name="Jane Doe")
        assert len(results) == 1
        assert results[0]["student_name"] == "Jane Doe"

    def test_get_by_system(self, doc_svc):
        _upload(doc_svc)
        results = doc_svc.get_documents(system="university")
        assert len(results) == 1

    def test_get_by_doc_type(self, doc_svc):
        _upload(doc_svc, doc_type="ehcp")
        _upload(doc_svc, doc_type="medical", title="Medical Note")
        results = doc_svc.get_documents(doc_type="medical")
        assert len(results) == 1
        assert results[0]["title"] == "Medical Note"

    def test_get_all(self, doc_svc):
        _upload(doc_svc, title="Doc A")
        _upload(doc_svc, title="Doc B")
        assert len(doc_svc.get_documents()) == 2


class TestGetSingleDocument:
    def test_get_document_by_id(self, doc_svc):
        doc_id = _upload(doc_svc, title="My Report")
        doc = doc_svc.get_document(doc_id)
        assert doc["title"] == "My Report"
        assert doc["student_id"] == "STU001"

    def test_get_nonexistent_returns_none(self, doc_svc):
        assert doc_svc.get_document(9999) is None


class TestDeleteDocument:
    def test_delete_removes_record(self, doc_svc):
        doc_id = _upload(doc_svc)
        assert doc_svc.delete_document(doc_id) is True
        assert doc_svc.get_document(doc_id) is None

    def test_delete_removes_file(self, doc_svc):
        doc_id = _upload(doc_svc, file_data=b"remove me")
        doc = doc_svc.get_document(doc_id)
        from pathlib import Path
        file_path = Path(doc["file_path"])
        assert file_path.exists()
        doc_svc.delete_document(doc_id)
        assert not file_path.exists()

    def test_delete_nonexistent_returns_false(self, doc_svc):
        assert doc_svc.delete_document(9999) is False


class TestSearchDocuments:
    def test_search_by_title(self, doc_svc):
        _upload(doc_svc, title="Annual Review 2026")
        _upload(doc_svc, title="Medical Note")
        results = doc_svc.search_documents("Annual")
        assert len(results) == 1
        assert results[0]["title"] == "Annual Review 2026"

    def test_search_by_student_name(self, doc_svc):
        _upload(doc_svc, student_name="Jane Doe", title="Doc A")
        _upload(doc_svc, student_name="Bob Smith", title="Doc B")
        results = doc_svc.search_documents("Bob")
        assert len(results) == 1

    def test_search_empty_query(self, doc_svc):
        _upload(doc_svc)
        assert doc_svc.search_documents("") == []


class TestDocumentTypes:
    def test_get_document_types(self, doc_svc):
        types = doc_svc.get_document_types()
        assert "ehcp" in types
        assert "medical" in types
        assert "safeguarding" in types
        assert isinstance(types, list)
