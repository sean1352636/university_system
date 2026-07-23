import os
from education_system.post_18.university_system.modules.domain.academics.services.plagiarism.exceptions import PlagiarismCheckerError, FileProcessingError


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


def submit_document(checker, auth):
    """Submit a document to the repository"""
    try:
        print("\nSubmit Document")
        print("===============")

        # Get document information
        title = safe_input("Document Title: ")
        if not title:
            print("Operation cancelled or invalid title.")
            return

        # Get list of modules/courses
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
                    module_code = safe_input("Enter module code manually (optional): ")
                else:
                    print("\nSelect Module/Course:")
                    for i, module in enumerate(modules, 1):
                        print(f"{i}. {module[0]} - {module[1]}")

                    print(f"{len(modules) + 1}. Enter manually")

                    module_choice = safe_input(f"\nModule number (1-{len(modules) + 1}): ")
                    if not module_choice:
                        return

                    try:
                        module_idx = int(module_choice) - 1
                        if 0 <= module_idx < len(modules):
                            module_code = modules[module_idx][0]
                        elif module_idx == len(modules):
                            module_code = safe_input("Enter module code: ")
                        else:
                            print("Invalid module selection.")
                            return
                    except ValueError:
                        print("Please enter a valid number.")
                        return

        except Exception as e:
            print(f"Error retrieving modules: {e}")
            module_code = safe_input("Enter module code manually: ")

        # Get file path
        while True:
            file_path = safe_input("\nEnter the full path to the document file (or 'cancel' to abort): ")
            if not file_path or file_path.lower() == 'cancel':
                print("Document submission cancelled.")
                return

            if not os.path.exists(file_path):
                print("File not found. Please enter a valid path.")
                continue

            # Check file size
            try:
                file_size = os.path.getsize(file_path) / (1024 * 1024)  # Size in MB
                if file_size > 50:  # Limit to 50MB
                    print(f"File is too large ({file_size:.1f}MB). Maximum size is 50MB.")
                    continue
            except Exception as e:
                print(f"Error checking file size: {e}")
                continue

            break

        # Extract text from the file
        print("\nExtracting text from file, please wait...")
        try:
            content, file_type = checker.extract_text_from_file(file_path)
        except FileProcessingError as e:
            print(f"Error extracting text from file: {e}")
            return
        except Exception as e:
            print(f"Unexpected error extracting text: {e}")
            return

        # Add document to repository
        print("Adding document to repository...")
        try:
            document_id = checker.add_document_to_repository(
                title, content, auth.current_user['id'], module_code, file_type
            )

            print(f"\nDocument '{title}' successfully added to the repository with ID: {document_id}")

            # Ask if user wants to check for plagiarism now
            if auth.check_permission('check_plagiarism'):
                check_now = safe_input("\nDo you want to check this document for plagiarism now? (y/n): ").lower()
                if check_now == 'y':
                    print("\nChecking for plagiarism, please wait...")
                    try:
                        from education_system.post_18.university_system.modules.domain.academics.services.plagiarism.cli.reporting import display_check_result
                        result = checker.check_plagiarism(document_id, auth.current_user['id'])
                        display_check_result(result)
                    except Exception as e:
                        print(f"Error during plagiarism check: {e}")
        except PlagiarismCheckerError as e:
            print(f"Error adding document: {e}")
        except Exception as e:
            print(f"Unexpected error adding document: {e}")

    except Exception as e:
        print(f"Error during document submission: {e}")


def view_my_documents(checker, auth):
    """View documents submitted by the current user"""
    try:
        print("\nFetching your documents, please wait...")
        try:
            documents = checker.search_repository("", author_id=auth.current_user['id'])
        except PlagiarismCheckerError as e:
            print(f"Error retrieving documents: {e}")
            return

        if not documents:
            print("You haven't submitted any documents yet.")
            return

        print("\nYour Documents:")
        print("===============")

        for i, doc in enumerate(documents, 1):
            try:
                status_info = ""
                doc_details = checker.get_document_details(doc['id'])

                if doc_details['latest_check']:
                    check = doc_details['latest_check']
                    similarity = check['similarity_score'] * 100  # Convert to percentage
                    status_info = f"{check['status']} (Similarity: {similarity:.1f}%)"
                else:
                    status_info = "Not checked yet"

                print(f"{i}. {doc['title']} ({doc['file_type']}) - {status_info}")
                print(f"   Submitted: {doc['submission_date']}, Words: {doc['word_count']}")
            except Exception as e:
                print(f"{i}. {doc['title']} - Error retrieving details: {e}")

        # Ask if user wants to view details for a specific document
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
        print(f"Error retrieving your documents: {e}")
