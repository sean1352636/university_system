"""Tests for DocumentService."""
import pytest


class TestDocument:
    def test_add_document(self, document_service):
        doc = document_service.add_document(
            title="Safeguarding Policy", filename="safeguarding.pdf",
            file_path="/docs/safeguarding.pdf", category="safeguarding",
        )
        assert doc["title"] == "Safeguarding Policy"
        assert doc["category"] == "safeguarding"

    def test_list_documents(self, document_service):
        document_service.add_document("Doc A", "a.pdf", "/a.pdf")
        document_service.add_document("Doc B", "b.pdf", "/b.pdf")
        docs = document_service.list_documents()
        assert len(docs) >= 2

    def test_list_documents_filters_by_category(self, document_service):
        document_service.add_document("Doc A", "a.pdf", "/a.pdf", category="curriculum")
        document_service.add_document("Doc B", "b.pdf", "/b.pdf", category="safeguarding")
        docs = document_service.list_documents(category="curriculum")
        assert all(d["category"] == "curriculum" for d in docs)

    def test_delete_document(self, document_service):
        doc = document_service.add_document("Del Me", "d.pdf", "/d.pdf")
        document_service.delete_document(doc["id"])
        docs = document_service.list_documents()
        assert all(d["id"] != doc["id"] for d in docs)

    def test_acknowledge(self, document_service):
        doc = document_service.add_document(
            "Ack Doc", "ack.pdf", "/ack.pdf", requires_acknowledgement=True,
        )
        document_service.acknowledge(doc["id"], user_id=1)
        count = document_service.acknowledgement_count(doc["id"])
        assert count == 1

    def test_acknowledgement_count(self, document_service):
        doc = document_service.add_document("Count Doc", "c.pdf", "/c.pdf")
        assert document_service.acknowledgement_count(doc["id"]) == 0
        document_service.acknowledge(doc["id"], user_id=1)
        document_service.acknowledge(doc["id"], user_id=2)
        assert document_service.acknowledgement_count(doc["id"]) == 2
