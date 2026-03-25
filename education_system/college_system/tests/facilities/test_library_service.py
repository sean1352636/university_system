"""Tests for LibraryService."""

import pytest


class TestLibraryService:
    @pytest.fixture
    def library_service(self, db_path):
        from education_system.college_system.modules.domain.library.services.library_service import LibraryService
        return LibraryService(db_path)

    def test_add_item(self, library_service):
        item = library_service.add_item(
            title="Introduction to Algorithms",
            author="Cormen et al.",
            isbn="978-0262033848",
            category="textbook",
        )
        assert item["title"] == "Introduction to Algorithms"
        assert item["available_copies"] == 1

    def test_list_items(self, library_service):
        library_service.add_item(title="Book A", author="Author A")
        library_service.add_item(title="Book B", author="Author B")
        items = library_service.list_items()
        assert len(items) >= 2

    def test_list_items_search(self, library_service):
        library_service.add_item(title="Unique Title XYZ", author="Test")
        items = library_service.list_items(search="Unique Title")
        assert len(items) >= 1

    def test_get_item(self, library_service):
        created = library_service.add_item(title="Get This", author="Author")
        found = library_service.get_item(created["id"])
        assert found["title"] == "Get This"

    def test_update_item(self, library_service):
        item = library_service.add_item(title="Old Title", author="Author")
        updated = library_service.update_item(item["id"], title="New Title")
        assert updated["title"] == "New Title"

    def test_checkout_and_return(self, library_service, sample_student):
        item = library_service.add_item(title="Borrow Me", author="Author")
        loan = library_service.checkout(
            item_id=item["id"], student_id=sample_student["id"],
        )
        assert loan["item_id"] == item["id"]
        assert loan["status"] == "on_loan"

        returned = library_service.return_item(loan["id"])
        assert returned["status"] == "returned"

    def test_list_loans(self, library_service, sample_student):
        item = library_service.add_item(title="Loanable", author="Auth")
        library_service.checkout(item_id=item["id"], student_id=sample_student["id"])
        loans = library_service.list_loans(student_id=sample_student["id"])
        assert len(loans) >= 1

    def test_renew_loan(self, library_service, sample_student):
        item = library_service.add_item(title="Renewable", author="Auth")
        loan = library_service.checkout(item_id=item["id"], student_id=sample_student["id"])
        renewed = library_service.renew_loan(loan["id"])
        assert renewed is not None
        assert renewed["status"] == "on_loan"
