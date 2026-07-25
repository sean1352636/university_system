from education_system.systems.university.infrastructure.utils.document_manager._common import (
    os, shutil, datetime, sqlite3,
    get_connection, _t,
)


class BulkOperationsMixin:
    def bulk_operations_menu(self):
        """Menu for bulk operations"""
        print("\n📦 BULK OPERATIONS")
        print("1. Bulk Status Update")
        print("2. Bulk Document Download")
        print("3. Bulk Expiry Update")
        print("4. Bulk Tag Assignment")
        print("5. Bulk Update from Search")
        print("6. Return to Main Menu")

        choice = input("\nChoose option (1-6): ").strip()

        if choice == '1':
            self.bulk_status_update()
        elif choice == '2':
            self.bulk_document_download()
        elif choice == '3':
            self.bulk_expiry_update()
        elif choice == '4':
            self.bulk_tag_assignment()
        elif choice == '5':
            self.bulk_update_from_search()

    def bulk_status_update(self):
        """Bulk update document status"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📦 BULK STATUS UPDATE")

            # Select criteria
            print("\nUpdate documents by:")
            print("1. Document Type")
            print("2. Current Status")
            print("3. Student")
            print("4. Upload Date Range")

            criteria_choice = input("\nChoose criteria (1-4): ").strip()

            if criteria_choice == '1':
                type_info = self.select_document_type(cursor)
                if not type_info:
                    conn.close()
                    return

                cursor.execute('''
                SELECT COUNT(*) FROM documents
                WHERE type_id = ? AND is_current_version = 1
                ''', (type_info[0],))

                count = cursor.fetchone()[0]
                print(f"\nFound {count} documents of type '{type_info[1]}'")

                new_status = input("New status (Pending/Verified/Rejected): ").strip()
                notes = input("Bulk update notes: ").strip()

                confirm = input(f"\nUpdate {count} documents to '{new_status}'? (y/n): ").strip().lower()

                if confirm == 'y':
                    cursor.execute('''
                    UPDATE documents
                    SET verification_status = ?,
                        verification_notes = ?,
                        verification_date = ?
                    WHERE type_id = ? AND is_current_version = 1
                    ''', (new_status, notes, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), type_info[0]))

                    conn.commit()
                    print(f"\n✅ Updated {count} documents to '{new_status}'")
                else:
                    print(_t("shared.utils.document_manager.operation_cancelled", default="Operation cancelled."))

            elif criteria_choice == '2':
                current_status = input("Current status to change from: ").strip()
                new_status = input("New status to change to: ").strip()

                cursor.execute('''
                SELECT COUNT(*) FROM documents
                WHERE verification_status = ? AND is_current_version = 1
                ''', (current_status,))

                count = cursor.fetchone()[0]
                print(f"\nFound {count} documents with status '{current_status}'")

                confirm = input(f"\nUpdate all to '{new_status}'? (y/n): ").strip().lower()

                if confirm == 'y':
                    cursor.execute('''
                    UPDATE documents
                    SET verification_status = ?,
                        verification_date = ?
                    WHERE verification_status = ? AND is_current_version = 1
                    ''', (new_status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), current_status))

                    conn.commit()
                    print(f"\n✅ Updated {count} documents")
                else:
                    print(_t("shared.utils.document_manager.operation_cancelled", default="Operation cancelled."))

            elif criteria_choice == '3':
                student_id = self.select_student(cursor)
                if not student_id:
                    conn.close()
                    return

                cursor.execute('''
                SELECT COUNT(*) FROM documents
                WHERE owner_id = ? AND source_type = 'student' AND is_current_version = 1
                ''', (student_id,))

                count = cursor.fetchone()[0]
                new_status = input("New status: ").strip()

                confirm = input(f"\nUpdate {count} documents for student {student_id}? (y/n): ").strip().lower()

                if confirm == 'y':
                    cursor.execute('''
                    UPDATE documents
                    SET verification_status = ?,
                        verification_date = ?
                    WHERE owner_id = ? AND source_type = 'student' AND is_current_version = 1
                    ''', (new_status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), student_id))

                    conn.commit()
                    print(f"\n✅ Updated {count} documents")
                else:
                    print(_t("shared.utils.document_manager.operation_cancelled", default="Operation cancelled."))

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def bulk_document_download(self):
        """Download multiple documents at once"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📥 BULK DOCUMENT DOWNLOAD")
            print("1. Download all documents for a student")
            print("2. Download documents by type")
            print("3. Download documents by status")
            print("4. Download from search results")

            choice = input("\nChoose option (1-4): ").strip()

            documents = []

            if choice == '1':
                student_id = self.select_student(cursor)
                if student_id:
                    cursor.execute('''
                    SELECT document_id, file_path, original_filename
                    FROM documents
                    WHERE owner_id = ? AND source_type = 'student' AND is_current_version = 1
                    ''', (student_id,))
                    documents = cursor.fetchall()

            elif choice == '2':
                type_info = self.select_document_type(cursor)
                if type_info:
                    cursor.execute('''
                    SELECT document_id, file_path, original_filename
                    FROM documents
                    WHERE type_id = ? AND is_current_version = 1
                    ''', (type_info[0],))
                    documents = cursor.fetchall()

            elif choice == '3':
                status = input("Enter status (Pending/Verified/Rejected): ").strip()
                cursor.execute('''
                SELECT document_id, file_path, original_filename
                FROM documents
                WHERE verification_status = ? AND is_current_version = 1
                ''', (status,))
                documents = cursor.fetchall()

            if not documents:
                print(_t("shared.utils.document_manager.no_docs_for_download", default="No documents found for download."))
                conn.close()
                return

            print(f"\nFound {len(documents)} documents.")

            # Create download directory
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            download_dir = f"bulk_download_{timestamp}"

            os.makedirs(download_dir, exist_ok=True)

            print(f"Downloading to: {download_dir}/")

            success_count = 0
            for doc_id, file_path, original_filename in documents:
                try:
                    if os.path.exists(file_path):
                        dest_path = os.path.join(download_dir, f"{doc_id}_{original_filename}")
                        shutil.copy2(file_path, dest_path)
                        success_count += 1
                        print(f"  ✓ {original_filename}")
                    else:
                        print(f"  ✗ {original_filename} (file not found)")
                except Exception as e:
                    print(f"  ✗ {original_filename} (error: {e})")

            print(f"\n✅ Downloaded {success_count}/{len(documents)} documents to {download_dir}/")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def bulk_expiry_update(self):
        """Update expiry dates for multiple documents"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📅 BULK EXPIRY UPDATE")

            type_info = self.select_document_type(cursor)
            if not type_info:
                conn.close()
                return

            type_id = type_info[0]

            cursor.execute('''
            SELECT document_id, owner_id as student_id, original_filename, expiry_date
            FROM documents
            WHERE type_id = ? AND is_current_version = 1
            ''', (type_id,))

            documents = cursor.fetchall()

            if not documents:
                print(_t("shared.utils.document_manager.no_docs_for_type", default="No documents found for this type."))
                conn.close()
                return

            print(f"\nFound {len(documents)} documents of this type.")

            new_expiry = self.get_expiry_date()

            confirm = input(f"\nUpdate expiry date to {new_expiry} for all {len(documents)} documents? (y/n): ").strip().lower()

            if confirm == 'y':
                cursor.execute('''
                UPDATE documents
                SET expiry_date = ?
                WHERE type_id = ? AND is_current_version = 1
                ''', (new_expiry, type_id))

                conn.commit()
                print(f"✅ Updated expiry date for {len(documents)} documents.")
            else:
                print(_t("shared.utils.document_manager.operation_cancelled", default="Operation cancelled."))

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def bulk_tag_assignment(self):
        """Assign tags to multiple documents"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n🏷️  BULK TAG ASSIGNMENT")

            # Get documents to tag
            print("Select documents to tag:")
            print("1. By student")
            print("2. By document type")
            print("3. By status")

            choice = input("\nChoose option (1-3): ").strip()

            if choice == '1':
                student_id = self.select_student(cursor)
                if not student_id:
                    conn.close()
                    return

                cursor.execute('''
                SELECT document_id, original_filename
                FROM documents
                WHERE owner_id = ? AND source_type = 'student' AND is_current_version = 1
                ''', (student_id,))

            elif choice == '2':
                type_info = self.select_document_type(cursor)
                if not type_info:
                    conn.close()
                    return

                cursor.execute('''
                SELECT document_id, original_filename
                FROM documents
                WHERE type_id = ? AND is_current_version = 1
                ''', (type_info[0],))

            elif choice == '3':
                status = input("Enter status: ").strip()
                cursor.execute('''
                SELECT document_id, original_filename
                FROM documents
                WHERE verification_status = ? AND is_current_version = 1
                ''', (status,))

            else:
                print(_t("shared.utils.document_manager.invalid_choice", default="Invalid choice. Please try again."))
                conn.close()
                return

            documents = cursor.fetchall()

            if not documents:
                print(_t("shared.utils.document_manager.no_documents_found", default="No documents found."))
                conn.close()
                return

            print(f"\nFound {len(documents)} documents.")

            # Select tags
            tags = self.select_tags(cursor)
            if not tags:
                conn.close()
                return

            confirm = input(f"\nAssign tags '{tags}' to {len(documents)} documents? (y/n): ").strip().lower()

            if confirm == 'y':
                for doc_id, _ in documents:
                    cursor.execute('''
                    UPDATE documents
                    SET tags = ?
                    WHERE document_id = ?
                    ''', (tags, doc_id))

                conn.commit()
                print(f"✅ Tags assigned to {len(documents)} documents.")
            else:
                print(_t("shared.utils.document_manager.operation_cancelled", default="Operation cancelled."))

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def bulk_update_from_search(self, results=None):
        """Perform bulk updates on search results"""
        print("\n🔍 BULK UPDATE FROM SEARCH")

        if results is None:
            print("First, perform a search to find documents...")
            results = self.execute_advanced_search({})

        if not results:
            print(_t("shared.utils.document_manager.no_documents_found", default="No documents found."))
            return

        print(f"\nFound {len(results)} documents.")
        print("\nBulk Operations:")
        print("1. Update Status")
        print("2. Assign Tags")
        print("3. Update Expiry Date")
        print("4. Change Priority")

        choice = input("\nChoose operation (1-4): ").strip()

        try:
            conn = get_connection()
            cursor = conn.cursor()

            doc_ids = [r[0] for r in results]

            if choice == '1':
                new_status = input("New status (Pending/Verified/Rejected): ").strip()
                cursor.execute(f'''
                UPDATE documents
                SET verification_status = ?
                WHERE document_id IN ({','.join('?' * len(doc_ids))})
                ''', [new_status] + doc_ids)

            elif choice == '2':
                tags = self.select_tags(cursor)
                cursor.execute(f'''
                UPDATE documents
                SET tags = ?
                WHERE document_id IN ({','.join('?' * len(doc_ids))})
                ''', [tags] + doc_ids)

            elif choice == '3':
                new_expiry = self.get_expiry_date()
                cursor.execute(f'''
                UPDATE documents
                SET expiry_date = ?
                WHERE document_id IN ({','.join('?' * len(doc_ids))})
                ''', [new_expiry] + doc_ids)

            elif choice == '4':
                priority = input("New priority (0-5): ").strip()
                cursor.execute(f'''
                UPDATE documents
                SET priority = ?
                WHERE document_id IN ({','.join('?' * len(doc_ids))})
                ''', [priority] + doc_ids)

            conn.commit()
            conn.close()

            print(f"✅ Updated {len(results)} documents.")

        except sqlite3.Error as e:
            print(f"Database error: {e}")
