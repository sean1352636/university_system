from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.modules.shared.utils.document_manager._common import sqlite3, get_connection


class SearchMixin:
    def advanced_search(self):
        """Advanced search with multiple filters"""
        print("\n🔍 ADVANCED SEARCH")

        # Build search criteria
        criteria = {}

        print("\nSearch Filters (press Enter to skip):")

        student_search = input("Student name or ID: ").strip()
        if student_search:
            criteria['student'] = student_search

        doc_type = input("Document type: ").strip()
        if doc_type:
            criteria['doc_type'] = doc_type

        status = input("Status (Pending/Verified/Rejected/Expired): ").strip()
        if status:
            criteria['status'] = status

        from_date = input("From date (YYYY-MM-DD): ").strip()
        if from_date:
            criteria['from_date'] = from_date

        to_date = input("To date (YYYY-MM-DD): ").strip()
        if to_date:
            criteria['to_date'] = to_date

        tags = input("Tags (comma-separated): ").strip()
        if tags:
            criteria['tags'] = tags

        # Execute search
        results = self.execute_advanced_search(criteria)

        if not results:
            print("No documents found matching your criteria.")
            return

        print(f"\n📊 Search Results ({len(results)} documents found):")
        print("-" * 120)
        print(f"{'ID':<5} {'Student':<20} {'Document Type':<25} {'Status':<12} {'Upload Date':<12} {'Version':<8} {'Tags'}")
        print("-" * 120)

        for result in results:
            doc_id, student_name, doc_type, status, upload_date, version, tags = result
            tags_display = tags[:20] + "..." if tags and len(tags) > 20 else tags or ""
            print(f"{doc_id:<5} {student_name:<20} {doc_type:<25} {status:<12} {upload_date:<12} {version:<8} {tags_display}")

        # Options for search results
        print("\nSearch Result Options:")
        print("1. View document details")
        print("2. Export results")
        print("3. Bulk update status")
        print("4. Return to menu")

        choice = input("Choose option (1-4): ").strip()

        if choice == '1':
            doc_id = input("Enter document ID to view: ").strip()
            if doc_id.isdigit():
                self.view_document_details(int(doc_id))
        elif choice == '2':
            self.export_search_results(results)
        elif choice == '3':
            self.bulk_update_from_search(results)

    def execute_advanced_search(self, criteria):
        """Execute the advanced search query"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Build dynamic query
            query = '''
            SELECT sd.document_id,
                   s.first_name || ' ' || s.last_name as student_name,
                   dt.type_name,
                   sd.verification_status,
                   DATE(sd.upload_date) as upload_date,
                   sd.version_number,
                   sd.tags
            FROM documents sd
            JOIN students s ON sd.owner_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.is_current_version = 1
            '''

            params = []

            # Add search conditions
            if 'student' in criteria:
                query += " AND (s.first_name LIKE ? OR s.last_name LIKE ? OR s.student_id LIKE ?)"
                search_term = f"%{escape_like(criteria['student'])}%"
                params.extend([search_term, search_term, search_term])

            if 'doc_type' in criteria:
                query += " AND dt.type_name LIKE ?"
                params.append(f"%{escape_like(criteria['doc_type'])}%")

            if 'status' in criteria:
                query += " AND sd.verification_status = ?"
                params.append(criteria['status'])

            if 'from_date' in criteria:
                query += " AND DATE(sd.upload_date) >= ?"
                params.append(criteria['from_date'])

            if 'to_date' in criteria:
                query += " AND DATE(sd.upload_date) <= ?"
                params.append(criteria['to_date'])

            if 'tags' in criteria:
                tag_list = [tag.strip() for tag in criteria['tags'].split(',')]
                tag_conditions = []
                for tag in tag_list:
                    tag_conditions.append("sd.tags LIKE ?")
                    params.append(f"%{escape_like(tag)}%")
                query += " AND (" + " OR ".join(tag_conditions) + ")"

            query += " ORDER BY sd.upload_date DESC LIMIT 100"

            cursor.execute(query, params)
            results = cursor.fetchall()

            conn.close()
            return results

        except sqlite3.Error as e:
            print(f"Search error: {e}")
            return []
