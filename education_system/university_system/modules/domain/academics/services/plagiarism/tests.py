import os
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

from .exceptions import PlagiarismCheckerError
from .checker import PlagiarismChecker
from .db import get_safe_db_connection


def test_document_repository(checker, auth):
    """Test basic document repository operations"""
    try:
        # Test searching repository
        results = checker.search_repository()
        if not isinstance(results, list):
            print("Error: Could not search repository")
            return False

        print(f"Found {len(results)} documents in repository")

        # Check if we can get document details for existing documents
        if results:
            doc_id = results[0]['id']
            try:
                details = checker.get_document_details(doc_id)

                if not isinstance(details, dict) or not details.get('title'):
                    print(f"Error getting document details: invalid response")
                    return False

                print(f"Successfully retrieved details for document: {details['title']}")
            except Exception as e:
                print(f"Error getting document details: {e}")
                return False

        # Test invalid document ID
        try:
            checker.get_document_details(99999)
            print("Error: Should have failed for invalid document ID")
            return False
        except ValueError:
            print("Correctly handled invalid document ID")
        except Exception as e:
            print(f"Unexpected error for invalid document ID: {e}")
            return False

        return True
    except Exception as e:
        print(f"Error in document repository test: {e}")
        return False


def test_document_submission(checker, auth):
    """Test document submission functionality"""
    try:
        # Get a module code
        try:
            with get_safe_db_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('SELECT module_code FROM modules LIMIT 1')
                module_result = cursor.fetchone()

                module_code = module_result[0] if module_result else 'TEST_MODULE'

        except Exception as e:
            print(f"Error getting module: {e}")
            module_code = 'TEST_MODULE'

        # Test valid document submission
        test_content = f"""
        This is a test document created by the automated testing system.
        It contains some unique content to avoid false positives.
        The current timestamp is: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        This document is being submitted under the user: {auth.current_user['username']}

        The purpose of this document is to test the submission functionality
        of the plagiarism detection system. If this test passes, it means that
        the system can properly accept new documents and add them to the repository.
        Random identifier: TEST_{datetime.now().strftime('%Y%m%d%H%M%S%f')}
        """

        title = f"Test Document - {datetime.now().strftime('%Y%m%d%H%M%S')}"

        try:
            doc_id = checker.add_document_to_repository(
                title,
                test_content,
                auth.current_user['id'],
                module_code,
                'txt'
            )

            if not doc_id:
                print("Error: Failed to add document to repository")
                return False

            print(f"Successfully added document to repository with ID: {doc_id}")
        except Exception as e:
            print(f"Error adding document: {e}")
            return False

        # Verify document exists in repository
        try:
            details = checker.get_document_details(doc_id)

            if details['title'] != title:
                print(f"Error: Document title mismatch: {details['title']} != {title}")
                return False

            print("Document submission verification passed")
        except Exception as e:
            print(f"Error verifying document: {e}")
            return False

        # Test invalid submissions
        invalid_tests = [
            ("", test_content, auth.current_user['id'], module_code, 'txt'),  # Empty title
            (title, "", auth.current_user['id'], module_code, 'txt'),  # Empty content
            (title, test_content, -1, module_code, 'txt'),  # Invalid user ID
        ]

        for i, (t, c, u, m, f) in enumerate(invalid_tests):
            try:
                checker.add_document_to_repository(t, c, u, m, f)
                print(f"Error: Invalid submission test {i+1} should have failed")
                return False
            except (ValueError, PlagiarismCheckerError):
                print(f"Correctly rejected invalid submission {i+1}")
            except Exception as e:
                print(f"Unexpected error in invalid submission test {i+1}: {e}")
                return False

        return True
    except Exception as e:
        print(f"Error in document submission test: {e}")
        return False


def test_plagiarism_check(checker, auth):
    """Test plagiarism checking functionality"""
    try:
        # Get a module code
        try:
            with get_safe_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT module_code FROM modules LIMIT 1')
                module_result = cursor.fetchone()
                module_code = module_result[0] if module_result else 'TEST_MODULE'
        except Exception:
            module_code = 'TEST_MODULE'

        # Create two similar documents
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')

        original_content = f"""
        Artificial intelligence (AI) is revolutionizing education by providing personalized
        learning experiences for students. Machine learning algorithms can analyze student
        performance data to identify areas where additional support is needed. Natural language
        processing allows for automated assessment of written assignments, providing timely
        feedback to students. Virtual tutors can provide 24/7 assistance, helping students
        when human teachers are not available.
        Test identifier: ORIGINAL_{timestamp}
        """

        similar_content = f"""
        AI is transforming education through personalized learning experiences. Machine learning
        algorithms analyze student performance to find areas needing more support. NLP enables
        automated assessment of writing assignments, giving prompt feedback. Virtual tutoring
        systems provide round-the-clock help when human teachers aren't available.
        Test identifier: SIMILAR_{timestamp}
        """

        # Submit original document
        try:
            original_title = f"Original Test - {timestamp}"
            original_id = checker.add_document_to_repository(
                original_title,
                original_content,
                auth.current_user['id'],
                module_code,
                'txt'
            )

            if not original_id:
                print("Error: Failed to add original document")
                return False

            print(f"Added original document with ID: {original_id}")
        except Exception as e:
            print(f"Error adding original document: {e}")
            return False

        # Submit similar document
        try:
            similar_title = f"Similar Test - {timestamp}"
            similar_id = checker.add_document_to_repository(
                similar_title,
                similar_content,
                auth.current_user['id'],
                module_code,
                'txt'
            )

            if not similar_id:
                print("Error: Failed to add similar document")
                return False

            print(f"Added similar document with ID: {similar_id}")
        except Exception as e:
            print(f"Error adding similar document: {e}")
            return False

        # Check similar document for plagiarism
        try:
            result = checker.check_plagiarism(similar_id, auth.current_user['id'], threshold=0.1)

            if not isinstance(result, dict):
                print("Error: Invalid plagiarism check result format")
                return False

            if 'matches' not in result:
                print("Error: No matches field in result")
                return False

            # The similar document should have some similarity
            similarity = result.get('highest_similarity', 0) * 100
            print(f"Similarity between documents: {similarity:.1f}%")

            if similarity < 5:  # Very low threshold for basic functionality
                print("Warning: Similarity score is lower than expected")

            print("Plagiarism check completed successfully")
        except Exception as e:
            print(f"Error in plagiarism check: {e}")
            return False

        # Test invalid plagiarism check
        try:
            checker.check_plagiarism(-1, auth.current_user['id'])
            print("Error: Should have failed for invalid document ID")
            return False
        except ValueError:
            print("Correctly handled invalid document ID in plagiarism check")
        except Exception as e:
            print(f"Unexpected error for invalid plagiarism check: {e}")
            return False

        return True
    except Exception as e:
        print(f"Error in plagiarism check test: {e}")
        return False


def test_error_handling(checker, auth):
    """Test error handling"""
    try:
        print("Testing error handling...")

        # Test invalid inputs
        error_tests = [
            lambda: checker.get_document_details("invalid"),  # Non-integer ID
            lambda: checker.get_document_details(0),  # Zero ID
            lambda: checker.get_plagiarism_result("invalid"),  # Non-integer result ID
            lambda: checker.check_plagiarism("invalid"),  # Non-integer document ID
            lambda: checker.add_document_to_repository(None, "content", 1, "MOD", "txt"),  # None title
        ]

        for i, test_func in enumerate(error_tests):
            try:
                test_func()
                print(f"Error: Error test {i+1} should have raised an exception")
                return False
            except (ValueError, TypeError, PlagiarismCheckerError):
                print(f"Error test {i+1}: Correctly handled invalid input")
            except Exception as e:
                print(f"Error test {i+1}: Unexpected exception type: {e}")
                return False

        # Test database connection resilience
        try:
            # This should work with proper error handling
            stats = checker.get_statistics()
            if not isinstance(stats, dict):
                print("Error: Statistics should return a dictionary")
                return False
            print("Statistics retrieval: Passed")
        except Exception as e:
            print(f"Error getting statistics: {e}")
            return False

        return True
    except Exception as e:
        print(f"Error in error handling test: {e}")
        return False


def test_edge_cases(checker, auth):
    """Test edge cases"""
    try:
        print("Testing edge cases...")

        # Test empty search
        try:
            results = checker.search_repository("")
            print(f"Empty search returned {len(results)} results")
        except Exception as e:
            print(f"Error in empty search: {e}")
            return False

        # Test search with no results
        try:
            results = checker.search_repository("NONEXISTENT_DOCUMENT_TITLE_12345")
            if len(results) != 0:
                print(f"Warning: Search for non-existent title returned {len(results)} results")
            else:
                print("Search for non-existent document correctly returned 0 results")
        except Exception as e:
            print(f"Error in no-results search: {e}")
            return False

        # Test very short content
        try:
            short_content = "AI."
            title = f"Short Test - {datetime.now().strftime('%Y%m%d%H%M%S')}"

            doc_id = checker.add_document_to_repository(
                title, short_content, auth.current_user['id'], 'TEST_MODULE', 'txt'
            )

            if doc_id:
                print("Successfully handled very short content")

                # Try to check it for plagiarism
                result = checker.check_plagiarism(doc_id, auth.current_user['id'])
                print("Successfully checked short document for plagiarism")
            else:
                print("Failed to add short document")
                return False

        except Exception as e:
            print(f"Error with short content: {e}")
            return False

        # Test text preprocessing edge cases
        try:
            edge_texts = [
                "",  # Empty
                "   ",  # Whitespace only
                "123 456 789",  # Numbers only
                "!@#$%^&*()",  # Symbols only
                "a b c",  # Very short words
            ]

            for text in edge_texts:
                tokens = checker.preprocess_text(text)
                print(f"Preprocessed '{text}' -> {len(tokens)} tokens")

        except Exception as e:
            print(f"Error in text preprocessing: {e}")
            return False

        return True
    except Exception as e:
        print(f"Error in edge cases test: {e}")
        return False


def test_plagiarism_checker():
    """Test the plagiarism checker functionality"""
    print("Plagiarism Checker Test Script")
    print("=============================")

    # Check if database exists
    if not os.path.exists(str(DEFAULT_DB_PATH)):
        print("Error: Database file str(DEFAULT_DB_PATH) not found.")
        print("Please initialize the main system first.")
        return False

    # Check database connection
    try:
        with get_safe_db_connection() as conn:
            cursor = conn.cursor()

            # Check if user tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not cursor.fetchone():
                print("Error: User authentication tables not found in database.")
                return False

            # Check for any login credentials
            cursor.execute('SELECT username FROM users LIMIT 1')
            if not cursor.fetchone():
                print("Error: No user accounts found. Please initialize the system first.")
                return False

    except Exception as e:
        print(f"Database error: {e}")
        return False

    print("Database checks passed.")

    # Create a UserAuth object for testing
    try:
        # Try to get centralized auth first
        auth = get_auth()
        if auth is None:
            auth = UserAuth()
        # Get first user for testing
        with get_safe_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT username FROM users LIMIT 1')
            user_data = cursor.fetchone()
            if user_data:
                # Note: In real usage, would use proper login with password
                # For testing, we create a basic session
                auth.current_user = {'username': user_data[0]}
                print(f"Test authentication context created with user: {user_data[0]}")
            else:
                print("No users found for testing.")
                return False
    except Exception as e:
        print(f"Error creating test auth: {e}")
        return False

    # Initialize the plagiarism checker
    try:
        checker = PlagiarismChecker()
        print("Plagiarism checker initialized successfully.")
    except Exception as e:
        print(f"Error initializing plagiarism checker: {e}")
        return False

    # Run basic tests
    test_cases = [
        test_document_repository,
        test_document_submission,
        test_plagiarism_check,
        test_error_handling,
        test_edge_cases
    ]

    test_results = []
    for test_case in test_cases:
        try:
            name = test_case.__name__.replace('_', ' ').title()
            print(f"\nRunning test: {name}")
            result = test_case(checker, auth)
            test_results.append((name, result))
            if result:
                print(f"{name}: PASSED")
            else:
                print(f"{name}: FAILED")
        except Exception as e:
            print(f"Error in test {test_case.__name__}: {e}")
            test_results.append((test_case.__name__.replace('_', ' ').title(), False))

    # Summarize results
    print("\nTest Results Summary:")
    print("====================")

    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)

    for name, result in test_results:
        status = "PASSED" if result else "FAILED"
        print(f"{name}: {status}")

    print(f"\nPassed {passed} out of {total} tests ({passed/total*100:.1f}%)")

    if passed == total:
        print("\nAll tests passed! The plagiarism checker is working correctly.")
        return True
    else:
        print("\nSome tests failed. Please check the error messages above.")
        return False
