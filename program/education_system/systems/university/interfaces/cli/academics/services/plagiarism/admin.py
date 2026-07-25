from education_system.systems.university.domain.academics.services.plagiarism.exceptions import PlagiarismCheckerError


def safe_input(prompt, default=None, validator=None):
    """Safe input function with validation"""
    while True:
        try:
            value = input(prompt).strip()
            if not value and default is not None:
                return default
            if validator:
                if validator(value):
                    return value
                else:
                    print("Invalid input. Please try again.")
                    continue
            return value
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return None
        except Exception as e:
            print(f"Input error: {e}")
            continue


def manage_repository(checker, auth):
    """Manage the document repository"""
    if not auth.check_permission('manage_plagiarism_system'):
        print("You don't have permission to manage the document repository.")
        return

    while True:
        try:
            print("\nManage Document Repository")
            print("==========================")
            print("1. Delete Document")
            print("2. Check Repository Integrity")
            print("3. Back")

            choice = safe_input("\nEnter your choice (1-3): ")
            if not choice:
                return

            if choice == '1':
                delete_document_interactive(checker)
            elif choice == '2':
                check_repository_integrity(checker)
            elif choice == '3':
                return
            else:
                print("Invalid choice. Please try again.")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            return
        except Exception as e:
            print(f"Error in repository management: {e}")


def delete_document_interactive(checker):
    """Interactive document deletion"""
    try:
        search_term = safe_input("\nEnter document title to search: ")
        if not search_term:
            return

        print("\nSearching for documents, please wait...")
        try:
            documents = checker.search_repository(search_term)
        except PlagiarismCheckerError as e:
            print(f"Error searching documents: {e}")
            return

        if not documents:
            print("No documents found matching your criteria.")
            return

        print("\nDocuments:")
        for i, doc in enumerate(documents, 1):
            print(f"{i}. {doc['title']} (ID: {doc['id']})")

        delete_choice = safe_input(f"\nEnter document number to delete (1-{len(documents)}, or 0 to cancel): ")
        if not delete_choice:
            return

        try:
            delete_num = int(delete_choice)
            if delete_num == 0:
                print("Deletion cancelled.")
                return

            if 1 <= delete_num <= len(documents):
                doc_id = documents[delete_num-1]['id']
                doc_title = documents[delete_num-1]['title']

                confirm = safe_input(f"Are you sure you want to delete '{doc_title}'? (y/n): ").lower()
                if confirm == 'y':
                    second_confirm = safe_input("This action cannot be undone. Type 'DELETE' to confirm: ")
                    if second_confirm == 'DELETE':
                        print("\nDeleting document, please wait...")
                        try:
                            if checker.delete_document(doc_id):
                                print(f"Document '{doc_title}' has been deleted.")
                            else:
                                print("Error deleting document.")
                        except PlagiarismCheckerError as e:
                            print(f"Error deleting document: {e}")
                    else:
                        print("Deletion cancelled.")
                else:
                    print("Deletion cancelled.")
            else:
                print("Invalid selection.")
        except ValueError:
            print("Please enter a valid number.")
    except Exception as e:
        print(f"Error during document deletion: {e}")


def check_repository_integrity(checker):
    """Check repository integrity"""
    try:
        print("\nChecking repository integrity...")

        with checker.get_db_connection() as conn:
            cursor = conn.cursor()

            # Check for orphaned records in plagiarism_results
            cursor.execute('''
            SELECT COUNT(*) FROM plagiarism_results pr
            LEFT JOIN document_repository dr ON pr.document_id = dr.id
            WHERE dr.id IS NULL
            ''')

            orphaned_results = cursor.fetchone()[0]

            # Check for documents without content
            cursor.execute('''
            SELECT COUNT(*) FROM document_repository
            WHERE content IS NULL OR content = ''
            ''')

            empty_docs = cursor.fetchone()[0]

            # Check for documents with invalid authors
            cursor.execute('''
            SELECT COUNT(*) FROM document_repository dr
            LEFT JOIN users u ON dr.author_id = u.id
            WHERE u.id IS NULL
            ''')

            invalid_authors = cursor.fetchone()[0]

            print("\nRepository Integrity Check Results:")
            print(f"  Orphaned plagiarism results: {orphaned_results}")
            print(f"  Documents without content: {empty_docs}")
            print(f"  Documents with invalid authors: {invalid_authors}")

            total_issues = orphaned_results + empty_docs + invalid_authors

            if total_issues > 0:
                fix = safe_input(f"\nFound {total_issues} issues. Would you like to fix them? (y/n): ").lower()
                if fix == 'y':
                    try:
                        if orphaned_results > 0:
                            cursor.execute('''
                            DELETE FROM plagiarism_results
                            WHERE document_id NOT IN (SELECT id FROM document_repository)
                            ''')
                            print(f"Deleted {cursor.rowcount} orphaned plagiarism results.")

                        if empty_docs > 0:
                            cursor.execute('''
                            DELETE FROM document_repository
                            WHERE content IS NULL OR content = ''
                            ''')
                            print(f"Deleted {cursor.rowcount} empty documents.")

                        if invalid_authors > 0:
                            cursor.execute('''
                            DELETE FROM document_repository
                            WHERE author_id NOT IN (SELECT id FROM users)
                            ''')
                            print(f"Deleted {cursor.rowcount} documents with invalid authors.")

                        conn.commit()
                        print("\nIntegrity issues fixed successfully.")
                    except Exception as e:
                        print(f"Error fixing integrity issues: {e}")
                        conn.rollback()
            else:
                print("\nNo integrity issues found. Repository is healthy!")

    except Exception as e:
        print(f"Error during integrity check: {e}")
