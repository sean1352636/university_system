from education_system.university_system.modules.domain.academics.services.plagiarism.exceptions import PlagiarismCheckerError


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


def view_statistics(checker, auth):
    """View system statistics"""
    if not auth.check_permission('manage_plagiarism_system'):
        print("You don't have permission to view system statistics.")
        return

    try:
        print("\nGathering statistics, please wait...")
        try:
            stats = checker.get_statistics()
        except PlagiarismCheckerError as e:
            print(f"Error retrieving statistics: {e}")
            return

        print("\nPlagiarism Checker Statistics")
        print("=============================")
        print(f"Total Documents in Repository: {stats['total_documents']}")
        print(f"Total Plagiarism Checks Performed: {stats['total_checks']}")

        if stats.get('status_counts'):
            print("\nCheck Results by Status:")
            for status, count in stats['status_counts'].items():
                print(f"  {status}: {count}")

        if stats.get('documents_by_module'):
            print("\nDocuments by Module:")
            for module, count in stats['documents_by_module'].items():
                print(f"  {module}: {count}")

        if stats.get('recent_checks'):
            print("\nRecent Plagiarism Checks:")
            for i, check in enumerate(stats['recent_checks'][:10], 1):
                similarity = check['similarity_score'] * 100  # Convert to percentage
                print(f"{i}. {check['document_title']} - {check['status']} ({similarity:.1f}%)")
                print(f"   Checked: {check['check_date']}")

        safe_input("\nPress Enter to return to menu...")

    except Exception as e:
        print(f"Error retrieving statistics: {e}")


def display_document_details(checker, doc_id):
    """Display detailed information about a document"""
    try:
        print("\nRetrieving document details, please wait...")
        try:
            doc_details = checker.get_document_details(doc_id)
        except PlagiarismCheckerError as e:
            print(f"Error retrieving document details: {e}")
            return

        print("\nDocument Details")
        print("================")
        print(f"ID: {doc_details['id']}")
        print(f"Title: {doc_details['title']}")
        print(f"Author: {doc_details['author_name']}")
        print(f"Module: {doc_details['module_code'] or 'N/A'}")
        print(f"Submission Date: {doc_details['submission_date']}")
        print(f"File Type: {doc_details['file_type']}")
        print(f"Word Count: {doc_details['word_count']}")

        if doc_details['latest_check']:
            similarity = doc_details['latest_check']['similarity_score'] * 100  # Convert to percentage
            print("\nLatest Plagiarism Check:")
            print(f"  Status: {doc_details['latest_check']['status']}")
            print(f"  Similarity Score: {similarity:.1f}%")
            print(f"  Check Date: {doc_details['latest_check']['check_date']}")
            print(f"  Threshold Used: {doc_details['latest_check']['threshold_used']:.1%}")

            # Option to view full check details
            view_check = safe_input("\nView complete check results? (y/n): ").lower()
            if view_check == 'y':
                display_result_details(checker, doc_details['latest_check']['result_id'])
        else:
            print("\nThis document has not been checked for plagiarism.")

        # Show check history
        try:
            check_history = checker.get_document_check_history(doc_id)
            if len(check_history) > 1:
                print("\nPlagiarism Check History:")
                for i, check in enumerate(check_history, 1):
                    similarity = check['similarity_score'] * 100  # Convert to percentage
                    print(f"{i}. {check['check_date']} - {check['status']} ({similarity:.1f}%)")

                # Option to view a specific check result
                view_hist = safe_input(f"\nEnter number to view detailed results (1-{len(check_history)}, or press Enter to return): ")
                if view_hist:
                    try:
                        hist_num = int(view_hist)
                        if 1 <= hist_num <= len(check_history):
                            display_result_details(checker, check_history[hist_num-1]['result_id'])
                        else:
                            print("Invalid selection.")
                    except ValueError:
                        print("Please enter a valid number.")
        except Exception as e:
            print(f"Error retrieving check history: {e}")

    except Exception as e:
        print(f"Error displaying document details: {e}")


def display_result_details(checker, result_id):
    """Display detailed information about a plagiarism check result"""
    try:
        print("\nRetrieving plagiarism check results, please wait...")
        try:
            result = checker.get_plagiarism_result(result_id)
        except PlagiarismCheckerError as e:
            print(f"Error retrieving result details: {e}")
            return

        similarity = result['similarity_score'] * 100  # Convert to percentage
        print("\nPlagiarism Check Result")
        print("======================")
        print(f"Document: {result['document_title']}")
        print(f"Author: {result['author_name'] or 'Unknown'}")
        print(f"Check Date: {result['check_date']}")
        print(f"Checked By: {result['checker_name'] or 'Unknown'}")
        print(f"Status: {result['status']}")
        print(f"Similarity Score: {similarity:.1f}%")
        print(f"Threshold Used: {result['threshold_used']:.1%}")

        if result['matched_document_id']:
            print(f"\nMatched with: {result['matched_document_title']} (ID: {result['matched_document_id']})")

            # Option to view matched document
            view_match = safe_input("\nView matched document details? (y/n): ").lower()
            if view_match == 'y':
                display_document_details(checker, result['matched_document_id'])

        print("\nDetailed Report:")
        print(result['report'])

        safe_input("\nPress Enter to continue...")

    except Exception as e:
        print(f"Error displaying result details: {e}")


def display_check_result(result):
    """Display the results of a plagiarism check"""
    try:
        print("\nPlagiarism Check Complete")
        print("========================")

        if result['match_type'] == 'exact':
            print("\u26a0\ufe0f ALERT: EXACT MATCH FOUND! \u26a0\ufe0f")
            print(f"This document exactly matches {len(result['matches'])} document(s) in the repository.")

            print("\nMatched Documents:")
            for i, match in enumerate(result['matches'], 1):
                match_id, match_title, similarity = match
                print(f"{i}. {match_title} (ID: {match_id}) - 100% match")

        else:
            if result['status'] == "NO_MATCH":
                print("\u2713 No significant similarities found.")
                print("This document appears to be original.")
            else:
                print(f"Status: {result['status']}")
                similarity = result['highest_similarity'] * 100  # Convert to percentage
                print(f"Highest Similarity: {similarity:.1f}%")
                print(f"Threshold Used: {result['threshold_used']:.1%}")

                if result['matches']:
                    print("\nSimilar Documents:")
                    for i, match in enumerate(result['matches'][:5], 1):  # Show top 5
                        match_id, match_title, match_similarity = match
                        similarity = match_similarity * 100  # Convert to percentage
                        print(f"{i}. {match_title} (ID: {match_id}) - {similarity:.1f}% similarity")

                    if len(result['matches']) > 5:
                        print(f"... and {len(result['matches']) - 5} more matches")

        print(f"\nCheck ID: {result['result_id']}")
        print("To view complete results, use the 'View Plagiarism Check Results' option.")

        safe_input("\nPress Enter to continue...")

    except Exception as e:
        print(f"Error displaying check result: {e}")
