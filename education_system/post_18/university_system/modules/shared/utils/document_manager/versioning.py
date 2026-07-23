from education_system.post_18.university_system.modules.shared.utils.document_manager._common import (
    os, shutil, zipfile, datetime, sqlite3,
    get_connection, _t,
)


class VersioningMixin:
    def document_versioning_menu(self):
        """Document versioning management"""
        print("\n📋 DOCUMENT VERSIONING")
        print("1. View Document History")
        print("2. Compare Versions")
        print("3. Restore Previous Version")
        print("4. Archive Old Versions")
        print("5. Version Analytics")
        print("6. Return to Main Menu")

        choice = input("\nChoose option (1-6): ").strip()

        if choice == '1':
            self.view_document_history()
        elif choice == '2':
            self.compare_document_versions()
        elif choice == '3':
            self.restore_previous_version()
        elif choice == '4':
            self.archive_old_versions()
        elif choice == '5':
            self.version_analytics()

    def view_document_history(self):
        """View complete version history of a document"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            student_id = self.select_student(cursor)
            if not student_id:
                conn.close()
                return

            # Get current documents for the student
            cursor.execute('''
            SELECT sd.document_id, dt.type_name, sd.version_number
            FROM documents sd
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            WHERE sd.owner_id = ? AND sd.source_type = 'student' AND sd.is_current_version = 1
            ORDER BY dt.type_name
            ''', (student_id,))

            documents = cursor.fetchall()

            if not documents:
                print("No documents found for this student.")
                conn.close()
                return

            print("\nSelect document to view history:")
            for i, (doc_id, type_name, version) in enumerate(documents):
                print(f"{i+1}. {type_name} (Current: Version {version})")

            try:
                choice = int(input("\nSelect: ")) - 1
                if 0 <= choice < len(documents):
                    selected_doc_id = documents[choice][0]
                else:
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Invalid input.")
                conn.close()
                return

            # Get all versions
            cursor.execute('''
            SELECT document_id, version_number, upload_date, uploaded_by,
                   original_filename, file_size, is_current_version
            FROM documents
            WHERE (document_id = ? OR parent_document_id = ?)
            ORDER BY version_number DESC
            ''', (selected_doc_id, selected_doc_id))

            versions = cursor.fetchall()

            print("\n📋 VERSION HISTORY")
            print("=" * 80)
            for ver in versions:
                doc_id, ver_num, upload_date, uploaded_by, filename, size, is_current = ver
                current_text = " (CURRENT)" if is_current else ""
                size_text = f"{size / 1024:.1f} KB" if size else "Unknown"
                print(f"\nVersion {ver_num}{current_text}")
                print(f"  Document ID: {doc_id}")
                print(f"  Filename: {filename}")
                print(f"  Uploaded: {upload_date} by {uploaded_by}")
                print(f"  Size: {size_text}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def compare_document_versions(self):
        """Compare two versions of a document"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            doc_id = input("Enter document ID to compare versions: ").strip()

            cursor.execute('''
            SELECT document_id, version_number, upload_date, file_size,
                   file_hash, verification_status
            FROM documents
            WHERE document_id = ? OR parent_document_id = ?
            ORDER BY version_number
            ''', (doc_id, doc_id))

            versions = cursor.fetchall()

            if len(versions) < 2:
                print("Need at least 2 versions to compare.")
                conn.close()
                return

            print("\nAvailable versions:")
            for ver in versions:
                print(f"  Version {ver[1]} - Uploaded: {ver[2]}, Size: {ver[3]} bytes, Status: {ver[5]}")

            v1 = input("First version number: ").strip()
            v2 = input("Second version number: ").strip()

            # Find and compare
            ver1 = next((v for v in versions if str(v[1]) == v1), None)
            ver2 = next((v for v in versions if str(v[1]) == v2), None)

            if not ver1 or not ver2:
                print("Invalid version numbers.")
                conn.close()
                return

            print(f"\n📊 COMPARISON: Version {v1} vs Version {v2}")
            print("=" * 60)

            # Size comparison
            size_diff = (ver2[3] or 0) - (ver1[3] or 0)
            print(f"\nFile Size: {ver1[3]} bytes → {ver2[3]} bytes ({'+' if size_diff > 0 else ''}{size_diff} bytes)")

            # Hash comparison
            if ver1[4] == ver2[4]:
                print("File Hash: IDENTICAL (files are the same)")
            else:
                print("File Hash: DIFFERENT (files have changed)")

            # Status comparison
            print(f"Status: {ver1[5]} → {ver2[5]}")

            # Upload date comparison
            print(f"Upload Date: {ver1[2]} → {ver2[2]}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def restore_previous_version(self):
        """Restore a previous version as current"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            doc_id = input("Enter document ID to restore a version: ").strip()

            cursor.execute('''
            SELECT document_id, version_number, upload_date, original_filename
            FROM documents
            WHERE (document_id = ? OR parent_document_id = ?)
            AND is_current_version = 0
            ORDER BY version_number DESC
            ''', (doc_id, doc_id))

            old_versions = cursor.fetchall()

            if not old_versions:
                print("No previous versions available to restore.")
                conn.close()
                return

            print("\nAvailable versions to restore:")
            for ver in old_versions:
                print(f"  Version {ver[1]} - {ver[3]} (Uploaded: {ver[2]})")

            restore_version = input("\nSelect version number to restore: ").strip()

            selected = next((v for v in old_versions if str(v[1]) == restore_version), None)

            if not selected:
                print("Invalid version number.")
                conn.close()
                return

            confirm = input(f"\nRestore version {restore_version}? This will replace the current version. (y/n): ").strip().lower()

            if confirm == 'y':
                # Mark current version as not current
                cursor.execute('''
                UPDATE documents
                SET is_current_version = 0
                WHERE (document_id = ? OR parent_document_id = ?)
                AND is_current_version = 1
                ''', (doc_id, doc_id))

                # Mark selected version as current
                cursor.execute('''
                UPDATE documents
                SET is_current_version = 1
                WHERE document_id = ?
                ''', (selected[0],))

                conn.commit()
                print(f"✅ Version {restore_version} restored as current version.")
            else:
                print(_t("shared.utils.document_manager.operation_cancelled", default="Operation cancelled."))

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def archive_old_versions(self):
        """Archive old document versions to free up space"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📦 ARCHIVE OLD VERSIONS")

            # Count old versions
            cursor.execute('''
            SELECT COUNT(*), SUM(file_size)
            FROM documents
            WHERE is_current_version = 0
            ''')

            count, total_size = cursor.fetchone()

            if count == 0:
                print("No old versions to archive.")
                conn.close()
                return

            size_mb = (total_size or 0) / (1024 * 1024)

            print(f"\nFound {count} old versions")
            print(f"Total size: {size_mb:.2f} MB")

            print("\nArchive Options:")
            print("1. Move to archive directory")
            print("2. Create compressed archive")
            print("3. Delete old versions (WARNING: Cannot be undone)")
            print("4. Cancel")

            choice = input("\nChoose option (1-4): ").strip()

            if choice == '1' or choice == '2':
                archive_dir = 'document_archive'
                os.makedirs(archive_dir, exist_ok=True)

                cursor.execute('''
                SELECT document_id, file_path, original_filename
                FROM documents
                WHERE is_current_version = 0 AND file_path IS NOT NULL
                ''')

                old_docs = cursor.fetchall()

                if choice == '2':
                    # Create zip archive
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    zip_filename = f"archived_versions_{timestamp}.zip"
                    zip_path = os.path.join(archive_dir, zip_filename)

                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as archive_zip:
                        for doc_id, file_path, orig_name in old_docs:
                            if os.path.exists(file_path):
                                arcname = f"{doc_id}_{orig_name}"
                                archive_zip.write(file_path, arcname)

                    print(f"\n✅ Created archive: {zip_path}")
                else:
                    # Move files
                    for doc_id, file_path, orig_name in old_docs:
                        if os.path.exists(file_path):
                            new_path = os.path.join(archive_dir, f"{doc_id}_{orig_name}")
                            shutil.move(file_path, new_path)

                            # Update database
                            cursor.execute('''
                            UPDATE documents
                            SET file_path = ?
                            WHERE document_id = ?
                            ''', (new_path, doc_id))

                    conn.commit()
                    print(f"\n✅ Moved {len(old_docs)} files to archive directory")

            elif choice == '3':
                confirm = input("\n⚠️  Delete all old versions? Type 'DELETE' to confirm: ").strip()

                if confirm == 'DELETE':
                    cursor.execute('''
                    SELECT file_path FROM documents
                    WHERE is_current_version = 0 AND file_path IS NOT NULL
                    ''')

                    files_to_delete = cursor.fetchall()

                    # Delete files
                    deleted_count = 0
                    for file_path, in files_to_delete:
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                                deleted_count += 1
                            except Exception as e:
                                print(f"Error deleting {file_path}: {e}")

                    # Delete database records
                    cursor.execute('DELETE FROM documents WHERE is_current_version = 0')

                    conn.commit()
                    print(f"\n✅ Deleted {deleted_count} old version files and {count} database records")
                else:
                    print(_t("shared.utils.document_manager.operation_cancelled", default="Operation cancelled."))

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def version_analytics(self):
        """Analyze document versioning patterns"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📊 VERSION ANALYTICS")
            print("=" * 80)

            # Documents with multiple versions
            cursor.execute('''
            SELECT parent_document_id, COUNT(*) as version_count
            FROM documents
            WHERE parent_document_id IS NOT NULL
            GROUP BY parent_document_id
            HAVING COUNT(*) > 1
            ORDER BY version_count DESC
            LIMIT 10
            ''')

            multi_version = cursor.fetchall()

            if multi_version:
                print("\nDocuments with Most Versions:")
                for parent_id, count in multi_version:
                    print(f"  Document {parent_id}: {count} versions")

            # Average versions per document type
            cursor.execute('''
            SELECT dt.type_name, AVG(version_count) as avg_versions
            FROM document_types dt
            JOIN (
                SELECT type_id, COUNT(*) as version_count
                FROM documents
                GROUP BY owner_id, type_id
            ) vc ON dt.type_id = vc.type_id
            GROUP BY dt.type_name
            ORDER BY avg_versions DESC
            ''')

            avg_versions = cursor.fetchall()

            if avg_versions:
                print("\nAverage Versions by Document Type:")
                for type_name, avg_ver in avg_versions:
                    print(f"  {type_name}: {avg_ver:.2f} versions")

            # Total storage used by versions
            cursor.execute('''
            SELECT SUM(file_size) as total_size,
                   COUNT(*) as version_count
            FROM documents
            WHERE is_current_version = 0
            ''')

            total_size, old_versions = cursor.fetchone()

            if total_size:
                size_mb = total_size / (1024 * 1024)
                print("\nOld Versions Storage:")
                print(f"  Old versions: {old_versions}")
                print(f"  Storage used: {size_mb:.2f} MB")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")
