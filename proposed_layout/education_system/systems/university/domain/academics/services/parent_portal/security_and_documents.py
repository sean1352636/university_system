from education_system.systems.university.infrastructure.database.db import sqlite3, DatabaseManager
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH
import datetime


class SecurityAndDocumentsMixin:
    def manage_documents(self):
        """Upload and manage documents"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to manage documents.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('manage_documents'):
            print("You don't have permission to manage documents.")
            return

        children = self.view_children()

        if not children:
            print("You have no children registered in the system.")
            return

        print("\nSelect child for document management:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")

        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError

            selected_child = children[index]
            student_id = selected_child[0]

            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()

                # Get existing documents
                cursor.execute('''
                SELECT document_type, document_name, upload_date, status, expiry_date
                FROM documents
                WHERE source_type = 'parent' AND reference_id = ?
                  AND reference_type = 'student'
                ORDER BY upload_date DESC
                ''', (student_id,))

                documents = cursor.fetchall()

                print(f"\nDocuments for {selected_child[1]} {selected_child[3]}:")

                if documents:
                    print("\nExisting Documents:")
                    for doc in documents:
                        doc_type, name, upload_date, status, expiry_date = doc
                        expiry_info = f" (expires: {expiry_date})" if expiry_date else ""
                        print(f"- {name} ({doc_type}) - {status.upper()}{expiry_info}")
                        print(f"  Uploaded: {upload_date}")
                        print()

                print("\nDocument Types:")
                print("1. Permission slip")
                print("2. Medical form")
                print("3. Emergency contact form")
                print("4. Photo consent")
                print("5. Other")

                doc_type_choice = input("Select document type to upload: ")
                doc_types = {
                    '1': 'permission_slip',
                    '2': 'medical_form',
                    '3': 'emergency_contact',
                    '4': 'photo_consent',
                    '5': 'other'
                }

                doc_type = doc_types.get(doc_type_choice)
                if not doc_type:
                    print("Invalid choice.")
                    return

                if doc_type == 'other':
                    doc_type = input("Specify document type: ")

                document_name = input("Document name/description: ")
                file_path = input("File path to the document to upload: ")

                expiry_date = input("Expiry date (YYYY-MM-DD, or leave blank): ")
                if expiry_date:
                    try:
                        datetime.datetime.strptime(expiry_date, '%Y-%m-%d')
                    except ValueError:
                        print("Invalid date format.")
                        return

                parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
                if not parent_id:
                    print("Error retrieving parent ID.")
                    return

                upload_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Validate the source file and copy it into the managed document store.
                import shutil
                from pathlib import Path
                from education_system.systems.university.infrastructure import paths

                MAX_DOCUMENT_BYTES = 25 * 1024 * 1024  # 25 MB

                source = Path(file_path.strip()).expanduser()
                if not source.is_file():
                    print(f"Error: no file found at '{source}'. Document not uploaded.")
                    return

                if source.stat().st_size > MAX_DOCUMENT_BYTES:
                    print("Error: document exceeds the 25 MB size limit. Document not uploaded.")
                    return

                dest_dir = paths.STUDENT_DOCUMENTS_DIR / str(student_id)
                dest_dir.mkdir(parents=True, exist_ok=True)
                safe_name = "".join(
                    c if c.isalnum() or c in ('-', '_', '.') else '_'
                    for c in document_name.strip().replace(' ', '_')
                ) or "document"
                timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                dest_path = dest_dir / f"{parent_id}_{timestamp}_{safe_name}{source.suffix.lower()}"
                shutil.copy2(source, dest_path)
                file_path = str(dest_path)

                cursor.execute('''
                INSERT INTO documents
                (source_type, owner_id, owner_type, reference_id, reference_type,
                 document_type, document_name, file_path, upload_date, expiry_date)
                VALUES ('parent', ?, 'parent', ?, 'student', ?, ?, ?, ?, ?)
                ''', (parent_id, student_id, doc_type, document_name, file_path, upload_date, expiry_date))

                conn.commit()
                print("Document uploaded successfully.")

            except sqlite3.Error as e:
                print(f"Database error managing documents: {e}")
            finally:
                if conn:
                    conn.close()

        except (ValueError, IndexError):
            print("Invalid choice.")

    def manage_pickup_authorization(self):
        """Manage who can pick up children"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to manage pickup authorization.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('manage_pickup_auth'):
            print("You don't have permission to manage pickup authorization.")
            return

        children = self.view_children()

        if not children:
            print("You have no children registered in the system.")
            return

        print("\nSelect child for pickup authorization:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")

        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError

            selected_child = children[index]
            student_id = selected_child[0]

            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()

                # Get existing authorizations
                cursor.execute('''
                SELECT authorized_person_name, relationship, phone_number, valid_from, valid_until, active
                FROM pickup_authorizations
                WHERE student_id = ?
                ORDER BY authorized_person_name
                ''', (student_id,))

                authorizations = cursor.fetchall()

                print(f"\nPickup Authorization for {selected_child[1]} {selected_child[3]}:")

                if authorizations:
                    print("\nAuthorized Persons:")
                    for auth in authorizations:
                        name, relationship, phone, valid_from, valid_until, active = auth
                        status = "Active" if active else "Inactive"
                        print(f"- {name} ({relationship}) - {status}")
                        print(f"  Phone: {phone}")
                        print(f"  Valid: {valid_from} to {valid_until}")
                        print()

                print("\nOptions:")
                print("1. Add authorized person")
                print("2. Remove authorization")
                print("3. Back to menu")

                option = input("Select option: ")

                if option == '1':
                    print("\nAdd Authorized Person:")
                    person_name = input("Full name: ")
                    relationship = input("Relationship to student: ")
                    phone_number = input("Phone number: ")
                    id_number = input("ID number: ")

                    valid_from = input("Valid from (YYYY-MM-DD, or leave blank for today): ")
                    if not valid_from:
                        valid_from = datetime.datetime.now().strftime('%Y-%m-%d')

                    valid_until = input("Valid until (YYYY-MM-DD, or leave blank for one year): ")
                    if not valid_until:
                        future_date = datetime.datetime.now() + datetime.timedelta(days=365)
                        valid_until = future_date.strftime('%Y-%m-%d')

                    # Validate dates
                    try:
                        datetime.datetime.strptime(valid_from, '%Y-%m-%d')
                        datetime.datetime.strptime(valid_until, '%Y-%m-%d')
                    except ValueError:
                        print("Invalid date format.")
                        return

                    parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])

                    cursor.execute('''
                    INSERT INTO pickup_authorizations
                    (student_id, authorized_person_name, relationship, phone_number, id_number,
                     valid_from, valid_until, active, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                    ''', (student_id, person_name, relationship, phone_number, id_number,
                          valid_from, valid_until, parent_id))

                    conn.commit()
                    print("Authorized person added successfully.")

                elif option == '2' and authorizations:
                    print("\nSelect person to remove authorization:")
                    for i, auth in enumerate(authorizations):
                        name, relationship = auth[0], auth[1]
                        print(f"{i+1}. {name} ({relationship})")

                    remove_choice = input("Enter number: ")
                    try:
                        remove_index = int(remove_choice) - 1
                        if remove_index < 0 or remove_index >= len(authorizations):
                            raise ValueError

                        selected_auth = authorizations[remove_index]
                        person_name = selected_auth[0]

                        cursor.execute('''
                        UPDATE pickup_authorizations
                        SET active = 0
                        WHERE student_id = ? AND authorized_person_name = ?
                        ''', (student_id, person_name))

                        conn.commit()
                        print(f"Authorization removed for {person_name}.")

                    except (ValueError, IndexError):
                        print("Invalid choice.")

            except sqlite3.Error as e:
                print(f"Database error managing pickup authorization: {e}")
            finally:
                if conn:
                    conn.close()

        except (ValueError, IndexError):
            print("Invalid choice.")

    def manage_photo_permissions(self):
        """Manage photo and media permissions"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to manage photo permissions.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('manage_photo_permissions'):
            print("You don't have permission to manage photo permissions.")
            return

        children = self.view_children()

        if not children:
            print("You have no children registered in the system.")
            return

        print("\nSelect child for photo permissions:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")

        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError

            selected_child = children[index]
            student_id = selected_child[0]

            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()

                # Get existing permissions
                cursor.execute('''
                SELECT permission_type, consent_given, conditions, valid_from, valid_until, date_signed
                FROM photo_permissions
                WHERE student_id = ?
                ORDER BY date_signed DESC
                ''', (student_id,))

                permissions = cursor.fetchall()

                print(f"\nPhoto Permissions for {selected_child[1]} {selected_child[3]}:")

                if permissions:
                    print("\nCurrent Permissions:")
                    for perm in permissions:
                        perm_type, consent, conditions, valid_from, valid_until, date_signed = perm
                        status = "GRANTED" if consent else "DENIED"
                        print(f"- {perm_type}: {status}")
                        if conditions:
                            print(f"  Conditions: {conditions}")
                        print(f"  Valid: {valid_from} to {valid_until}")
                        print(f"  Signed: {date_signed}")
                        print()

                print("\nPermission Types:")
                print("1. School website photos")
                print("2. Social media posts")
                print("3. Yearbook photos")
                print("4. Promotional materials")
                print("5. News/media coverage")

                perm_choice = input("Select permission type to update: ")
                perm_types = {
                    '1': 'website_photos',
                    '2': 'social_media',
                    '3': 'yearbook',
                    '4': 'promotional',
                    '5': 'media_coverage'
                }

                perm_type = perm_types.get(perm_choice)
                if not perm_type:
                    print("Invalid choice.")
                    return

                consent = input("Grant permission? (y/n): ").lower() == 'y'
                conditions = input("Any conditions or restrictions: ")

                valid_from = input("Valid from (YYYY-MM-DD, or leave blank for today): ")
                if not valid_from:
                    valid_from = datetime.datetime.now().strftime('%Y-%m-%d')

                valid_until = input("Valid until (YYYY-MM-DD, or leave blank for one year): ")
                if not valid_until:
                    future_date = datetime.datetime.now() + datetime.timedelta(days=365)
                    valid_until = future_date.strftime('%Y-%m-%d')

                # Validate dates
                try:
                    datetime.datetime.strptime(valid_from, '%Y-%m-%d')
                    datetime.datetime.strptime(valid_until, '%Y-%m-%d')
                except ValueError:
                    print("Invalid date format.")
                    return

                parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
                if not parent_id:
                    print("Error retrieving parent ID.")
                    return

                date_signed = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Remove any existing permission of this type
                cursor.execute('''
                DELETE FROM photo_permissions
                WHERE student_id = ? AND permission_type = ?
                ''', (student_id, perm_type))

                # Insert new permission
                cursor.execute('''
                INSERT INTO photo_permissions
                (student_id, permission_type, consent_given, conditions, valid_from, valid_until,
                 parent_signature, date_signed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, perm_type, consent, conditions, valid_from, valid_until,
                      parent_id, date_signed))

                conn.commit()

                status = "granted" if consent else "denied"
                print(f"Photo permission {status} successfully for {perm_type.replace('_', ' ')}.")

            except sqlite3.Error as e:
                print(f"Database error managing photo permissions: {e}")
            finally:
                if conn:
                    conn.close()

        except (ValueError, IndexError):
            print("Invalid choice.")
