from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.modules.domain.academics.services.plagiarism.exceptions import PlagiarismCheckerError


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


def search_repository(checker, auth):
    """Search the document repository"""
    if not auth.check_permission('check_plagiarism'):
        print("You don't have permission to search the document repository.")
        return

    try:
        search_term = safe_input("\nEnter search term for document title: ")
        if search_term is None:
            return

        author_filter = None
        module_filter = None

        use_filters = safe_input("Apply additional filters? (y/n): ").lower()
        if use_filters == 'y':
            # Author filter
            author_name = safe_input("Filter by author name (leave blank for all): ")
            if author_name:
                author_filter = get_author_selection(checker, author_name)

            # Module filter
            if auth.check_permission('check_plagiarism_any_course'):
                module_name = safe_input("Filter by module (leave blank for all): ")
                if module_name:
                    module_filter = get_module_selection_by_name(checker, module_name)

        # Search for documents
        print("\nSearching repository, please wait...")
        try:
            documents = checker.search_repository(search_term, author_id=author_filter, module_code=module_filter)
        except PlagiarismCheckerError as e:
            print(f"Error searching repository: {e}")
            return

        if not documents:
            print("No documents found matching your criteria.")
            return

        print("\nSearch Results:")
        print("===============")

        for i, doc in enumerate(documents, 1):
            try:
                doc_details = checker.get_document_details(doc['id'])

                author_name = doc_details.get('author_name', 'Unknown')
                status_info = ""

                if doc_details['latest_check']:
                    check = doc_details['latest_check']
                    similarity = check['similarity_score'] * 100  # Convert to percentage
                    status_info = f"{check['status']} ({similarity:.1f}%)"
                else:
                    status_info = "Not checked"

                print(f"{i}. {doc['title']} - {status_info}")
                print(f"   Author: {author_name}, Module: {doc['module_code']}")
                print(f"   Submitted: {doc['submission_date']}, Type: {doc['file_type']}")
            except Exception as e:
                print(f"{i}. {doc['title']} - Error retrieving details: {e}")

        # Select document to view details
        view_choice = safe_input(f"\nEnter document number to view details (1-{len(documents)}, or press Enter to return): ")
        if view_choice:
            try:
                view_num = int(view_choice)
                if 1 <= view_num <= len(documents):
                    from education_system.post_18.university_system.modules.domain.academics.services.plagiarism.cli.reporting import display_document_details
                    doc_id = documents[view_num-1]['id']
                    display_document_details(checker, doc_id)
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a valid number.")

    except Exception as e:
        print(f"Error searching repository: {e}")


def get_author_selection(checker, author_name):
    """Helper function to get author selection"""
    try:
        with checker.get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
            SELECT id, first_name, last_name
            FROM users
            WHERE first_name LIKE ? OR last_name LIKE ?
            ORDER BY last_name, first_name
            ''', (f"%{escape_like(author_name)}%", f"%{escape_like(author_name)}%"))

            authors = cursor.fetchall()

            if not authors:
                print("No authors found matching that name.")
                return None

            print("\nSelect Author:")
            for i, author in enumerate(authors, 1):
                print(f"{i}. {author[1]} {author[2]}")

            author_choice = safe_input(f"\nAuthor number (1-{len(authors)}): ")
            if not author_choice:
                return None

            try:
                author_idx = int(author_choice) - 1
                if 0 <= author_idx < len(authors):
                    return authors[author_idx][0]
                else:
                    print("Invalid author selection.")
                    return None
            except ValueError:
                print("Invalid choice.")
                return None

    except Exception as e:
        print(f"Error filtering by author: {e}")
        return None


def get_module_selection_by_name(checker, module_name):
    """Helper function to get module selection by name"""
    try:
        with checker.get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
            SELECT module_code, module_name
            FROM modules
            WHERE module_code LIKE ? OR module_name LIKE ?
            ORDER BY module_code
            ''', (f"%{escape_like(module_name)}%", f"%{escape_like(module_name)}%"))

            modules = cursor.fetchall()

            if not modules:
                print("No modules found matching that name.")
                return None

            print("\nSelect Module:")
            for i, module in enumerate(modules, 1):
                print(f"{i}. {module[0]} - {module[1]}")

            module_choice = safe_input(f"\nModule number (1-{len(modules)}): ")
            if not module_choice:
                return None

            try:
                module_idx = int(module_choice) - 1
                if 0 <= module_idx < len(modules):
                    return modules[module_idx][0]
                else:
                    print("Invalid module selection.")
                    return None
            except ValueError:
                print("Invalid choice.")
                return None

    except Exception as e:
        print(f"Error filtering by module: {e}")
        return None
