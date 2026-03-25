"""Tests for LibraryService."""
import pytest

from education_system.secondary_school.infrastructure.database.db import connect
from education_system.secondary_school.modules.domain.student_life.library.services.library_service import LibraryService


@pytest.fixture
def library_service(db_path):
    return LibraryService(db_path)


class TestBooks:
    def test_add_book(self, library_service):
        book = library_service.add_book(
            title="To Kill a Mockingbird", author="Harper Lee",
            isbn="9780061120084", category="fiction",
            location="Shelf A1", copies=3,
        )
        assert book["title"] == "To Kill a Mockingbird"
        assert book["copies_total"] == 3
        assert book["copies_available"] == 3

    def test_list_books(self, library_service):
        library_service.add_book(title="Book A", author="Author A")
        library_service.add_book(title="Book B", author="Author B")
        result = library_service.list_books()
        assert len(result) == 2

    def test_list_books_filter_by_category(self, library_service):
        library_service.add_book(title="Novel", category="fiction")
        library_service.add_book(title="Maths Year 9", category="textbook")
        result = library_service.list_books(category="textbook")
        assert len(result) == 1
        assert result[0]["title"] == "Maths Year 9"

    def test_list_books_search_by_title(self, library_service):
        library_service.add_book(title="Great Expectations")
        library_service.add_book(title="Pride and Prejudice")
        result = library_service.list_books(search="Expectations")
        assert len(result) == 1
        assert result[0]["title"] == "Great Expectations"

    def test_update_book(self, library_service):
        book = library_service.add_book(title="Old Title", author="Someone")
        library_service.update_book(book["id"], title="New Title")
        books = library_service.list_books(search="New Title")
        assert len(books) == 1
        assert books[0]["title"] == "New Title"

    def test_delete_book(self, library_service):
        book = library_service.add_book(title="Temp Book")
        library_service.delete_book(book["id"])
        result = library_service.list_books()
        assert len(result) == 0


class TestLoans:
    def test_issue_loan(self, library_service, sample_student):
        book = library_service.add_book(title="Loan Book", copies=2)
        library_service.issue_loan(book["id"], sample_student["id"])
        loans = library_service.list_loans(student_id=sample_student["id"])
        assert len(loans) == 1
        assert loans[0]["book_title"] == "Loan Book"
        # copies_available should decrease
        books = library_service.list_books(search="Loan Book")
        assert books[0]["copies_available"] == 1

    def test_return_book(self, library_service, sample_student):
        book = library_service.add_book(title="Return Book", copies=1)
        library_service.issue_loan(book["id"], sample_student["id"])
        loans = library_service.list_loans(student_id=sample_student["id"])
        library_service.return_book(loans[0]["id"])
        returned = library_service.list_loans(status="returned")
        assert len(returned) == 1
        # copies restored
        books = library_service.list_books(search="Return Book")
        assert books[0]["copies_available"] == 1

    def test_list_loans(self, library_service, sample_student, sample_student_ks4):
        book = library_service.add_book(title="Popular Book", copies=5)
        library_service.issue_loan(book["id"], sample_student["id"])
        library_service.issue_loan(book["id"], sample_student_ks4["id"])
        loans = library_service.list_loans()
        assert len(loans) == 2

    def test_overdue_loans(self, library_service, sample_student, db_path):
        book = library_service.add_book(title="Overdue Book", copies=1)
        library_service.issue_loan(book["id"], sample_student["id"], loan_days=14)
        # Manually backdate the due_date to make it overdue
        conn = connect(db_path)
        try:
            conn.execute(
                "UPDATE library_loans SET due_date = '2020-01-01' WHERE book_id = ?",
                (book["id"],),
            )
            conn.commit()
        finally:
            conn.close()
        overdue = library_service.overdue_loans()
        assert len(overdue) == 1
        assert overdue[0]["book_title"] == "Overdue Book"
