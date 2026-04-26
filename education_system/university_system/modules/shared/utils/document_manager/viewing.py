from education_system.university_system.modules.shared.utils.document_manager._common import datetime, sqlite3, get_connection, _t


class ViewingMixin:
    def view_student_documents(self):
        """View all documents for a specific student"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            student_id = self.select_student(cursor)
            if not student_id:
                conn.close()
                return

            cursor.execute('''
            SELECT sd.document_id, dt.type_name, sd.original_filename,
                   sd.upload_date, sd.expiry_date, sd.verification_status,
                   sd.version_number, sd.workflow_status, sd.tags
            FROM documents sd
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            WHERE sd.owner_id = ? AND sd.source_type = 'student' AND sd.is_current_version = 1
            ORDER BY sd.upload_date DESC
            ''', (student_id,))

            documents = cursor.fetchall()

            if not documents:
                print(f"\nNo documents found for student {student_id}.")
                conn.close()
                return

            print(f"\n{'='*80}")
            print(f"DOCUMENTS FOR STUDENT: {student_id}")
            print(f"{'='*80}")

            for doc in documents:
                doc_id, type_name, filename, upload_date, expiry_date, status, version, workflow, tags = doc

                print(f"\nDocument ID: {doc_id}")
                print(f"Type: {type_name}")
                print(f"Filename: {filename}")
                print(f"Uploaded: {upload_date}")
                print(f"Version: {version}")
                print(f"Status: {status} | Workflow: {workflow}")

                if expiry_date:
                    expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d')
                    days_until_expiry = (expiry_dt - datetime.now()).days

                    if days_until_expiry < 0:
                        print(f"Expiry: {expiry_date} (EXPIRED)")
                    elif days_until_expiry < 30:
                        print(f"Expiry: {expiry_date} (Expires in {days_until_expiry} days - WARNING)")
                    else:
                        print(f"Expiry: {expiry_date}")

                if tags:
                    print(f"Tags: {tags}")
                print("-" * 80)

            print(f"\nTotal Documents: {len(documents)}")

            # Offer to view document details
            view_details = input("\nView detailed info for a document? (y/n): ").strip().lower()
            if view_details == 'y':
                self.view_document_details()

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def view_document_details(self, doc_id=None):
        """View detailed information about a specific document"""
        if doc_id is None:
            doc_id = input("Enter document ID: ").strip()

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT sd.document_id, sd.owner_id as student_id, s.first_name, s.last_name,
                   dt.type_name, sd.original_filename, sd.file_path, sd.upload_date,
                   sd.expiry_date, sd.verification_status, sd.verification_date,
                   sd.verification_notes, sd.version_number, sd.uploaded_by,
                   sd.file_size, sd.file_hash, sd.tags, sd.workflow_status, sd.priority
            FROM documents sd
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            LEFT JOIN students s ON sd.owner_id = s.student_id
            WHERE sd.document_id = ?
            ''', (doc_id,))

            doc = cursor.fetchone()

            if not doc:
                print(_t("shared.utils.document_manager.document_not_found", default="Document not found."))
                conn.close()
                return

            print(f"\n{'='*80}")
            print("DOCUMENT DETAILS")
            print(f"{'='*80}")

            print(f"\nDocument ID: {doc[0]}")
            print(f"Student: {doc[2]} {doc[3]} (ID: {doc[1]})")
            print(f"Document Type: {doc[4]}")
            print(f"Original Filename: {doc[5]}")
            print(f"File Path: {doc[6]}")
            print(f"Upload Date: {doc[7]}")
            print(f"Uploaded By: {doc[13]}")
            print(f"File Size: {doc[14]} bytes")
            print(f"File Hash: {doc[15]}")
            print(f"Version: {doc[12]}")
            print(f"Verification Status: {doc[9]}")
            print(f"Workflow Status: {doc[17]}")
            print(f"Priority: {doc[18]}")

            if doc[8]:
                print(f"Expiry Date: {doc[8]}")

            if doc[10]:
                print(f"Verification Date: {doc[10]}")

            if doc[11]:
                print(f"Verification Notes: {doc[11]}")

            if doc[16]:
                print(f"Tags: {doc[16]}")

            # Show workflow steps
            cursor.execute('''
            SELECT step_name, step_order, assigned_to, status, comments,
                   completed_date, completed_by
            FROM document_workflow
            WHERE document_id = ?
            ORDER BY step_order
            ''', (doc_id,))

            workflow_steps = cursor.fetchall()

            if workflow_steps:
                print(f"\n{'='*80}")
                print("WORKFLOW STEPS:")
                for step in workflow_steps:
                    print(f"\nStep {step[1]}: {step[0]}")
                    print(f"  Assigned to: {step[2]}")
                    print(f"  Status: {step[3]}")
                    if step[4]:
                        print(f"  Comments: {step[4]}")
                    if step[5]:
                        print(f"  Completed: {step[5]} by {step[6]}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")
