"""Tests for the LibraryService in the Primary School system."""

import pytest


class TestAddBook:
    """Tests for adding books."""

    def test_add_book_returns_dict(self, library_service):
        """Adding a book returns a dict with id, title, and copies."""
        result = library_service.add_book(
            title="The Gruffalo", author="Julia Donaldson", isbn="9780142403877",
            category="Fiction", copies=3,
        )
        assert isinstance(result, dict)
        assert result["id"] > 0
        assert result["title"] == "The Gruffalo"
        assert result["copies"] == 3

    def test_add_book_persists(self, library_service):
        """A created book can be retrieved by id."""
        result = library_service.add_book(
            title="Matilda", author="Roald Dahl", category="Fiction",
        )
        book = library_service.get_book(result["id"])
        assert book is not None
        assert book["title"] == "Matilda"
        assert book["author"] == "Roald Dahl"


class TestGetBook:
    """Tests for retrieving a single book."""

    def test_get_nonexistent_book(self, library_service):
        """Getting a non-existent book returns None."""
        assert library_service.get_book(99999) is None


class TestListBooks:
    """Tests for listing books."""

    def test_list_books_empty_db(self, library_service):
        """Listing books on an empty database returns an empty list."""
        assert library_service.list_books() == []

    def test_list_books_returns_all(self, library_service):
        """Listing books returns all books."""
        library_service.add_book(title="Book A")
        library_service.add_book(title="Book B")
        books = library_service.list_books()
        assert len(books) == 2

    def test_list_books_filter_by_category(self, library_service):
        """Filtering by category returns only matching books."""
        library_service.add_book(title="Story", category="Fiction")
        library_service.add_book(title="Atlas", category="Non-Fiction")
        books = library_service.list_books(category="Fiction")
        assert len(books) == 1
        assert books[0]["title"] == "Story"


class TestUpdateBook:
    """Tests for updating books."""

    def test_update_title(self, library_service):
        """Updating a book title persists the change."""
        result = library_service.add_book(title="Old Title")
        updated = library_service.update_book(result["id"], title="New Title")
        assert updated["title"] == "New Title"

    def test_update_with_no_valid_fields(self, library_service):
        """Passing no recognised fields returns None."""
        result = library_service.add_book(title="Test")
        assert library_service.update_book(result["id"], bogus="val") is None


class TestDeleteBook:
    """Tests for deleting books."""

    def test_delete_existing_book(self, library_service):
        """Deleting an existing book returns True and removes it."""
        result = library_service.add_book(title="Gone")
        assert library_service.delete_book(result["id"]) is True
        assert library_service.get_book(result["id"]) is None

    def test_delete_nonexistent_book(self, library_service):
        """Deleting a non-existent book returns False."""
        assert library_service.delete_book(99999) is False


class TestLoans:
    """Tests for book loan operations."""

    def test_loan_book_returns_dict(self, library_service, sample_pupil):
        """Loaning a book returns a dict with loan details."""
        book = library_service.add_book(title="Diary of a Wimpy Kid", copies=2)
        loan = library_service.loan_book(book["id"], sample_pupil["pupil_id"], due_date="2026-04-18")
        assert isinstance(loan, dict)
        assert loan["id"] > 0
        assert loan["book_id"] == book["id"]
        assert loan["pupil_id"] == sample_pupil["pupil_id"]
        assert loan["due_date"] == "2026-04-18"

    def test_loan_reduces_available_copies(self, library_service, sample_pupil):
        """Loaning a book reduces the available copies count."""
        book = library_service.add_book(title="Charlotte's Web", copies=1)
        library_service.loan_book(book["id"], sample_pupil["pupil_id"], due_date="2026-04-18")
        updated_book = library_service.get_book(book["id"])
        assert updated_book["available_copies"] == 0

    def test_return_book(self, library_service, sample_pupil):
        """Returning a book marks the loan as returned."""
        book = library_service.add_book(title="BFG", copies=1)
        loan = library_service.loan_book(book["id"], sample_pupil["pupil_id"], due_date="2026-04-18")
        assert library_service.return_book(loan["id"]) is True
        loans = library_service.get_loans(pupil_id=sample_pupil["pupil_id"], status="On Loan")
        assert len(loans) == 0

    def test_return_book_restores_copies(self, library_service, sample_pupil):
        """Returning a book restores the available copies count."""
        book = library_service.add_book(title="Charlie", copies=1)
        loan = library_service.loan_book(book["id"], sample_pupil["pupil_id"], due_date="2026-04-18")
        library_service.return_book(loan["id"])
        updated_book = library_service.get_book(book["id"])
        assert updated_book["available_copies"] == 1

    def test_return_nonexistent_loan(self, library_service):
        """Returning a non-existent loan returns False."""
        assert library_service.return_book(99999) is False

    def test_get_loans_empty(self, library_service):
        """Getting loans with no data returns an empty list."""
        assert library_service.get_loans() == []

    def test_get_overdue_loans(self, library_service, sample_pupil):
        """get_overdue_loans returns loans past their due date."""
        book = library_service.add_book(title="Overdue Book", copies=1)
        library_service.loan_book(book["id"], sample_pupil["pupil_id"], due_date="2020-01-01")
        overdue = library_service.get_overdue_loans()
        assert len(overdue) == 1
        assert overdue[0]["title"] == "Overdue Book"

    def test_get_overdue_loans_excludes_returned(self, library_service, sample_pupil):
        """Returned books do not appear in overdue loans."""
        book = library_service.add_book(title="Returned Book", copies=1)
        loan = library_service.loan_book(book["id"], sample_pupil["pupil_id"], due_date="2020-01-01")
        library_service.return_book(loan["id"])
        overdue = library_service.get_overdue_loans()
        assert len(overdue) == 0
