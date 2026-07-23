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


def check_document(checker, auth):
    """Check a document for plagiarism"""
    if not auth.check_permission('check_plagiarism'):
        print("You don't have permission to check documents for plagiarism.")
        return

    try:
        # Let user search for a document first
        search_term = safe_input("\nEnter document title to search (or leave blank to see all): ")
        if search_term is None:
            return

        # Get module filter if they have permission to check across all modules
        module_code = None
        if auth.check_permission('check_plagiarism_any_course'):
            use_filter = safe_input("Filter by module? (y/n): ").lower()
            if use_filter == 'y':
                module_code = get_module_selection(checker)
                if module_code is None:
                    return
        else:
            # Get instructor's assigned modules
            module_code = get_module_selection(checker)
            if module_code is None:
                return

        # Search for documents
        print("\nSearching for documents, please wait...")
        try:
            documents = checker.search_repository(search_term, module_code=module_code)
        except PlagiarismCheckerError as e:
            print(f"Error searching documents: {e}")
            return

        if not documents:
            print("No documents found matching your criteria.")
            return

        print("\nDocuments:")
        print("==========")

        for i, doc in enumerate(documents, 1):
            try:
                doc_details = checker.get_document_details(doc['id'])

                if doc_details['latest_check']:
                    check = doc_details['latest_check']
                    status_info = f"{check['status']} (Last checked: {check['check_date']})"
                else:
                    status_info = "Not checked yet"

                print(f"{i}. {doc['title']} - {status_info}")
                print(f"   Author: {doc_details.get('author_name', 'Unknown')}, Module: {doc['module_code']}")
            except Exception as e:
                print(f"{i}. {doc['title']} - Error retrieving details: {e}")

        # Select document to check
        check_choice = safe_input(f"\nEnter document number to check for plagiarism (1-{len(documents)}): ")
        if not check_choice:
            return

        try:
            check_num = int(check_choice)
            if 1 <= check_num <= len(documents):
                doc_id = documents[check_num-1]['id']

                # Get similarity threshold
                threshold = 0.3  # Default
                custom_threshold = safe_input("\nEnter similarity threshold (0.1-0.9, default is 0.3): ")
                if custom_threshold:
                    try:
                        threshold = float(custom_threshold)
                        threshold = max(0.1, min(0.9, threshold))  # Clamp between 0.1 and 0.9
                    except ValueError:
                        print("Invalid threshold. Using default 0.3.")

                print(f"\nChecking document '{documents[check_num-1]['title']}' for plagiarism...")
                print("This may take a moment, please wait...")

                try:
                    from education_system.post_18.university_system.modules.domain.academics.services.plagiarism.cli.reporting import display_check_result
                    result = checker.check_plagiarism(doc_id, auth.current_user['id'], threshold)
                    display_check_result(result)
                except PlagiarismCheckerError as e:
                    print(f"Error during plagiarism check: {e}")
            else:
                print("Invalid selection.")
        except ValueError:
            print("Please enter a valid number.")

    except Exception as e:
        print(f"Error during plagiarism check: {e}")


def get_module_selection(checker):
    """Helper function to get module selection"""
    try:
        with checker.get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
            SELECT module_code, module_name FROM modules
            ORDER BY module_code
            ''')

            modules = cursor.fetchall()

            if not modules:
                print("No modules found in the system.")
                return safe_input("Enter module code manually (optional): ")

            print("\nSelect Module/Course:")
            for i, module in enumerate(modules, 1):
                print(f"{i}. {module[0]} - {module[1]}")
            print(f"{len(modules) + 1}. All modules")

            module_choice = safe_input(f"\nModule number (1-{len(modules) + 1}): ")
            if not module_choice:
                return None

            try:
                module_idx = int(module_choice) - 1
                if 0 <= module_idx < len(modules):
                    return modules[module_idx][0]
                elif module_idx == len(modules):
                    return None  # All modules
                else:
                    print("Invalid module selection.")
                    return None
            except ValueError:
                print("Please enter a valid number.")
                return None

    except Exception as e:
        print(f"Error selecting module: {e}")
        return None


def view_results(checker, auth):
    """View plagiarism check results"""
    if not auth.check_permission('check_plagiarism'):
        print("You don't have permission to view plagiarism check results.")
        return

    try:
        # Let user search for a document first
        search_term = safe_input("\nEnter document title to search (or leave blank to see all): ")
        if search_term is None:
            return

        # Get module filter if they have permission to check across all modules
        module_code = None
        if auth.check_permission('check_plagiarism_any_course'):
            use_filter = safe_input("Filter by module? (y/n): ").lower()
            if use_filter == 'y':
                module_code = get_module_selection(checker)

        # Search for documents
        print("\nSearching for documents, please wait...")
        try:
            documents = checker.search_repository(search_term, module_code=module_code)
        except PlagiarismCheckerError as e:
            print(f"Error searching documents: {e}")
            return

        if not documents:
            print("No documents found matching your criteria.")
            return

        print("\nDocuments with Check Results:")
        print("=============================")

        # Filter to only show documents that have been checked
        checked_docs = []
        for doc in documents:
            try:
                doc_details = checker.get_document_details(doc['id'])
                if doc_details['latest_check']:
                    checked_docs.append((doc, doc_details['latest_check']))
            except Exception as e:
                print(f"Error retrieving details for document {doc['title']}: {e}")

        if not checked_docs:
            print("No documents with plagiarism check results found.")
            return

        for i, (doc, check) in enumerate(checked_docs, 1):
            status_color = ""
            if check['status'] == "EXACT_MATCH" or check['status'] == "HIGH_SIMILARITY":
                status_color = "HIGH RISK"
            elif check['status'] == "MODERATE_SIMILARITY":
                status_color = "MEDIUM RISK"
            else:
                status_color = "LOW RISK"

            similarity = check['similarity_score'] * 100  # Convert to percentage
            print(f"{i}. {doc['title']} - [{status_color}] {check['status']}")
            print(f"   Similarity: {similarity:.1f}%, Checked: {check['check_date']}")

        # Select document to view details
        view_choice = safe_input(f"\nEnter document number to view detailed results (1-{len(checked_docs)}): ")
        if view_choice:
            try:
                view_num = int(view_choice)
                if 1 <= view_num <= len(checked_docs):
                    from education_system.post_18.university_system.modules.domain.academics.services.plagiarism.cli.reporting import display_result_details
                    result_id = checked_docs[view_num-1][1]['result_id']
                    display_result_details(checker, result_id)
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a valid number.")

    except Exception as e:
        print(f"Error viewing results: {e}")
