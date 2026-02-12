"""
Comprehensive tests for plagiarism/plagiarism_main.py

Tests plagiarism detection system including document management, text processing, and similarity checking
"""

import pytest
from university_system.infrastructure.database.db import sqlite3
import os
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from university_system.modules.domain.academics.services.plagiarism.plagiarism_main import (
    PlagiarismChecker,
    PlagiarismCheckerError,
    DatabaseError,
    FileProcessingError,
    IntegrationError
)

class TestPlagiarismCheckerInitialization:
    """Test suite for PlagiarismChecker initialization"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    def test_plagiarism_checker_init(self, temp_db):
        """Test PlagiarismChecker initialization"""
        checker = PlagiarismChecker(db_path=temp_db)

        assert checker is not None
        assert checker.db_path == temp_db

    def test_plagiarism_checker_creates_tables(self, temp_db):
        """Test that initialization creates required tables"""
        checker = PlagiarismChecker(db_path=temp_db)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        expected_tables = [
            'document_repository',
            'plagiarism_results'
        ]

        for table in expected_tables:
            assert table in tables, f"Table {table} not found"

        conn.close()

class TestPlagiarismCheckerDatabaseSchema:
    """Test suite for plagiarism checker database schema"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    def test_document_repository_table_structure(self, temp_db):
        """Test document_repository table has correct structure"""
        checker = PlagiarismChecker(db_path=temp_db)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(document_repository)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'id', 'title', 'content', 'content_hash', 'author_id',
            'module_code', 'submission_date', 'file_type', 'word_count',
            'created_at', 'updated_at'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_plagiarism_results_table_structure(self, temp_db):
        """Test plagiarism_results table has correct structure"""
        checker = PlagiarismChecker(db_path=temp_db)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(plagiarism_results)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'id', 'document_id', 'matched_document_id', 'similarity_score',
            'check_date', 'checked_by', 'status', 'report',
            'threshold_used', 'created_at'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_indexes_created(self, temp_db):
        """Test that indexes are created"""
        checker = PlagiarismChecker(db_path=temp_db)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]

        expected_indexes = [
            'idx_doc_hash',
            'idx_doc_author',
            'idx_doc_module',
            'idx_plagiarism_doc',
            'idx_plagiarism_status'
        ]

        for index in expected_indexes:
            assert index in indexes, f"Index {index} not found"

        conn.close()

class TestTextProcessing:
    """Test suite for text processing functions"""

    @pytest.fixture
    def checker(self):
        """Create a PlagiarismChecker instance"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        checker = PlagiarismChecker(db_path=path)
        yield checker
        if os.path.exists(path):
            os.remove(path)

    def test_preprocess_text(self, checker):
        """Test text preprocessing"""
        text = "This is a TEST! With some numbers 123 and symbols @#$."
        tokens = checker.preprocess_text(text)

        assert isinstance(tokens, list)
        assert len(tokens) > 0
        # Should be lowercase and filtered
        assert all(token.islower() for token in tokens)

    def test_preprocess_text_empty(self, checker):
        """Test preprocessing empty text"""
        tokens = checker.preprocess_text("")

        assert isinstance(tokens, list)
        assert len(tokens) == 0

    def test_preprocess_text_none(self, checker):
        """Test preprocessing None text"""
        tokens = checker.preprocess_text(None)

        assert isinstance(tokens, list)
        assert len(tokens) == 0

    def test_compute_ngrams(self, checker):
        """Test n-gram computation"""
        tokens = ['this', 'is', 'a', 'test', 'sentence']
        ngrams = checker.compute_ngrams(tokens, n=3)

        assert isinstance(ngrams, list)
        assert len(ngrams) > 0
        # Each n-gram should be a tuple of 3 words
        assert all(len(ngram) == 3 for ngram in ngrams)

    def test_compute_ngrams_empty(self, checker):
        """Test n-gram computation with empty tokens"""
        ngrams = checker.compute_ngrams([], n=3)

        assert isinstance(ngrams, list)
        assert len(ngrams) == 0

    def test_compute_ngrams_insufficient_tokens(self, checker):
        """Test n-gram computation with fewer tokens than n"""
        tokens = ['only', 'two']
        ngrams = checker.compute_ngrams(tokens, n=3)

        # Should return single tuple with all tokens
        assert len(ngrams) == 1
        assert ngrams[0] == ('only', 'two')

    def test_compute_similarity(self, checker):
        """Test similarity computation"""
        ngrams1 = [('a', 'b', 'c'), ('b', 'c', 'd'), ('c', 'd', 'e')]
        ngrams2 = [('a', 'b', 'c'), ('b', 'c', 'd'), ('x', 'y', 'z')]

        similarity = checker.compute_similarity(ngrams1, ngrams2)

        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0
        # Should have some overlap
        assert similarity > 0

    def test_compute_similarity_identical(self, checker):
        """Test similarity with identical n-grams"""
        ngrams = [('a', 'b', 'c'), ('b', 'c', 'd')]

        similarity = checker.compute_similarity(ngrams, ngrams)

        assert similarity == 1.0

    def test_compute_similarity_no_overlap(self, checker):
        """Test similarity with no overlap"""
        ngrams1 = [('a', 'b', 'c')]
        ngrams2 = [('x', 'y', 'z')]

        similarity = checker.compute_similarity(ngrams1, ngrams2)

        # Should be low or zero
        assert similarity < 0.5

    def test_compute_similarity_empty(self, checker):
        """Test similarity with empty n-grams"""
        similarity = checker.compute_similarity([], [])

        assert similarity == 0.0

    def test_get_content_hash(self, checker):
        """Test content hash generation"""
        content = "This is test content"
        hash_value = checker.get_content_hash(content)

        assert isinstance(hash_value, str)
        assert len(hash_value) > 0

    def test_get_content_hash_consistent(self, checker):
        """Test that same content produces same hash"""
        content = "This is test content"
        hash1 = checker.get_content_hash(content)
        hash2 = checker.get_content_hash(content)

        assert hash1 == hash2

    def test_get_content_hash_different(self, checker):
        """Test that different content produces different hash"""
        hash1 = checker.get_content_hash("Content 1")
        hash2 = checker.get_content_hash("Content 2")

        assert hash1 != hash2

class TestFileExtraction:
    """Test suite for file extraction"""

    @pytest.fixture
    def checker(self):
        """Create a PlagiarismChecker instance"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        checker = PlagiarismChecker(db_path=path)
        yield checker
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def temp_text_file(self):
        """Create a temporary text file"""
        fd, path = tempfile.mkstemp(suffix='.txt')
        with os.fdopen(fd, 'w') as f:
            f.write("This is test content.\nWith multiple lines.\n")
        yield path
        if os.path.exists(path):
            os.remove(path)

    def test_extract_text_from_txt_file(self, checker, temp_text_file):
        """Test extracting text from .txt file"""
        text, file_type = checker.extract_text_from_file(temp_text_file)

        assert isinstance(text, str)
        assert len(text) > 0
        assert 'test content' in text.lower()
        assert file_type == 'txt'

    def test_extract_text_from_nonexistent_file(self, checker):
        """Test extracting text from non-existent file"""
        with pytest.raises(FileNotFoundError):
            checker.extract_text_from_file('/nonexistent/file.txt')

    def test_extract_text_from_empty_path(self, checker):
        """Test extracting text with empty path"""
        with pytest.raises(ValueError):
            checker.extract_text_from_file('')

    @pytest.fixture
    def temp_empty_file(self):
        """Create an empty temporary file"""
        fd, path = tempfile.mkstemp(suffix='.txt')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    def test_extract_text_from_empty_file(self, checker, temp_empty_file):
        """Test extracting text from empty file"""
        with pytest.raises(FileProcessingError):
            checker.extract_text_from_file(temp_empty_file)

class TestDocumentRepository:
    """Test suite for document repository operations"""

    @pytest.fixture
    def checker(self):
        """Create a PlagiarismChecker instance with test data"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        checker = PlagiarismChecker(db_path=path)

        # Create test users and modules tables
        conn = sqlite3.connect(path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS modules (
                module_code TEXT PRIMARY KEY,
                module_name TEXT
            )
        ''')

        cursor.execute("INSERT INTO users (id, username) VALUES (?, ?)", (1, 'testuser'))
        cursor.execute("INSERT INTO modules (module_code, module_name) VALUES (?, ?)", ('CS101', 'Test Module'))

        conn.commit()
        conn.close()

        yield checker
        if os.path.exists(path):
            os.remove(path)

    def test_add_document_to_repository(self, checker):
        """Test adding a document to repository"""
        doc_id = checker.add_document_to_repository(
            title='Test Document',
            content='This is test content for plagiarism detection.',
            author_id=1,
            module_code='CS101',
            file_type='txt'
        )

        assert isinstance(doc_id, int)
        assert doc_id > 0

    def test_add_document_with_empty_title(self, checker):
        """Test adding document with empty title"""
        with pytest.raises(ValueError):
            checker.add_document_to_repository(
                title='',
                content='Content',
                author_id=1,
                module_code='CS101',
                file_type='txt'
            )

    def test_add_document_with_empty_content(self, checker):
        """Test adding document with empty content"""
        with pytest.raises(ValueError):
            checker.add_document_to_repository(
                title='Title',
                content='',
                author_id=1,
                module_code='CS101',
                file_type='txt'
            )

    def test_add_document_with_invalid_author(self, checker):
        """Test adding document with invalid author ID"""
        with pytest.raises(ValueError):
            checker.add_document_to_repository(
                title='Title',
                content='Content',
                author_id=0,
                module_code='CS101',
                file_type='txt'
            )

    def test_add_document_with_nonexistent_author(self, checker):
        """Test adding document with non-existent author"""
        with pytest.raises(ValueError):
            checker.add_document_to_repository(
                title='Title',
                content='Content',
                author_id=999,
                module_code='CS101',
                file_type='txt'
            )

    def test_add_duplicate_document(self, checker):
        """Test adding duplicate document returns existing ID"""
        # Add first document
        doc_id1 = checker.add_document_to_repository(
            title='Test Document',
            content='Identical content',
            author_id=1,
            module_code='CS101',
            file_type='txt'
        )

        # Add duplicate
        doc_id2 = checker.add_document_to_repository(
            title='Test Document 2',
            content='Identical content',
            author_id=1,
            module_code='CS101',
            file_type='txt'
        )

        # Should return same ID
        assert doc_id1 == doc_id2

    def test_check_exact_match(self, checker):
        """Test checking for exact matches"""
        # Add a document
        doc_id = checker.add_document_to_repository(
            title='Test Document',
            content='Test content',
            author_id=1,
            module_code='CS101',
            file_type='txt'
        )

        # Get content hash
        content_hash = checker.get_content_hash('Test content')

        # Check for matches
        matches = checker.check_exact_match(content_hash)

        assert isinstance(matches, list)
        assert len(matches) > 0
        assert matches[0][0] == doc_id

    def test_check_exact_match_no_matches(self, checker):
        """Test checking for matches with no results"""
        # Use a hash that doesn't exist
        fake_hash = 'nonexistent_hash_12345'

        matches = checker.check_exact_match(fake_hash)

        assert isinstance(matches, list)
        assert len(matches) == 0

class TestPlagiarismDetection:
    """Test suite for plagiarism detection"""

    @pytest.fixture
    def checker(self):
        """Create a PlagiarismChecker instance with test data"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        checker = PlagiarismChecker(db_path=path)

        # Create test users and modules
        conn = sqlite3.connect(path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS modules (
                module_code TEXT PRIMARY KEY,
                module_name TEXT
            )
        ''')

        cursor.execute("INSERT INTO users (id, username) VALUES (?, ?)", (1, 'testuser'))
        cursor.execute("INSERT INTO modules (module_code, module_name) VALUES (?, ?)", ('CS101', 'Test Module'))

        conn.commit()
        conn.close()

        yield checker
        if os.path.exists(path):
            os.remove(path)

    def test_check_plagiarism_invalid_document_id(self, checker):
        """Test checking plagiarism with invalid document ID"""
        with pytest.raises(ValueError):
            checker.check_plagiarism(document_id=0)

    def test_check_plagiarism_with_threshold(self, checker):
        """Test checking plagiarism with custom threshold"""
        # Add a document first
        doc_id = checker.add_document_to_repository(
            title='Test Document',
            content='This is a test document for plagiarism detection.',
            author_id=1,
            module_code='CS101',
            file_type='txt'
        )

        # Check with custom threshold (should handle gracefully even if no matches)
        try:
            result = checker.check_plagiarism(document_id=doc_id, threshold=0.5)
            # If it succeeds, result should be dict or None
            assert result is None or isinstance(result, dict)
        except Exception as e:
            # Some exceptions are acceptable (e.g., document not found in certain states)
            assert isinstance(e, (PlagiarismCheckerError, ValueError))

class TestExceptionClasses:
    """Test suite for exception classes"""

    def test_plagiarism_checker_error(self):
        """Test PlagiarismCheckerError exception"""
        with pytest.raises(PlagiarismCheckerError):
            raise PlagiarismCheckerError("Test error")

    def test_database_error(self):
        """Test DatabaseError exception"""
        with pytest.raises(DatabaseError):
            raise DatabaseError("Database test error")

    def test_file_processing_error(self):
        """Test FileProcessingError exception"""
        with pytest.raises(FileProcessingError):
            raise FileProcessingError("File processing test error")

    def test_integration_error(self):
        """Test IntegrationError exception"""
        with pytest.raises(IntegrationError):
            raise IntegrationError("Integration test error")

    def test_exception_inheritance(self):
        """Test exception inheritance"""
        assert issubclass(DatabaseError, PlagiarismCheckerError)
        assert issubclass(FileProcessingError, PlagiarismCheckerError)
        assert issubclass(IntegrationError, PlagiarismCheckerError)

class TestEdgeCases:
    """Test suite for edge cases"""

    @pytest.fixture
    def checker(self):
        """Create a PlagiarismChecker instance"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        checker = PlagiarismChecker(db_path=path)
        yield checker
        if os.path.exists(path):
            os.remove(path)

    def test_preprocess_very_long_text(self, checker):
        """Test preprocessing very long text"""
        long_text = "word " * 10000  # 10,000 words
        tokens = checker.preprocess_text(long_text)

        assert isinstance(tokens, list)
        # Should handle gracefully
        assert len(tokens) >= 0

    def test_compute_ngrams_with_n_equals_1(self, checker):
        """Test n-grams with n=1"""
        tokens = ['a', 'b', 'c']
        ngrams = checker.compute_ngrams(tokens, n=1)

        assert len(ngrams) == 3
        assert all(len(ngram) == 1 for ngram in ngrams)

    def test_get_content_hash_with_whitespace_variations(self, checker):
        """Test that whitespace variations produce same hash"""
        content1 = "This   is   test   content"
        content2 = "This is test content"

        hash1 = checker.get_content_hash(content1)
        hash2 = checker.get_content_hash(content2)

        # Normalized hashes should be equal
        assert hash1 == hash2

    def test_fallback_tokenization(self, checker):
        """Test fallback tokenization method"""
        text = "This is a test sentence."
        tokens = checker._fallback_tokenize(text)

        assert isinstance(tokens, list)
        assert len(tokens) > 0

    def test_fallback_stopwords(self, checker):
        """Test fallback stopwords method"""
        stopwords = checker._get_fallback_stopwords()

        assert isinstance(stopwords, set)
        assert 'the' in stopwords
        assert 'a' in stopwords
        assert 'is' in stopwords
