from education_system.post_18.university_system.modules.shared.utils.document_manager._common import sqlite3, get_connection, _t


class DocumentTypeMixin:
    def manage_document_templates(self):
        """Manage document templates and requirements"""
        print(_t("shared.utils.document_manager.template_mgmt_header", default="\n📋 DOCUMENT TEMPLATE MANAGEMENT"))
        print(_t("shared.utils.document_manager.menu_view_doc_types", default="1. View Document Types"))
        print(_t("shared.utils.document_manager.menu_add_doc_type", default="2. Add New Document Type"))
        print(_t("shared.utils.document_manager.menu_modify_doc_type", default="3. Modify Document Type"))
        print(_t("shared.utils.document_manager.menu_set_course_requirements", default="4. Set Course Requirements"))
        print(_t("shared.utils.document_manager.menu_template_analytics", default="5. Template Analytics"))
        print(_t("shared.utils.document_manager.menu_return_main", default="6. Return to Main Menu"))

        choice = input(_t("shared.utils.document_manager.prompt_choose_option_1_6", default="Choose option (1-6): ")).strip()

        if choice == '1':
            self.view_document_types()
        elif choice == '2':
            self.add_document_type()
        elif choice == '3':
            self.modify_document_type()
        elif choice == '4':
            self.set_course_requirements()
        elif choice == '5':
            self.template_analytics()

    def view_document_types(self):
        """View all document types"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT type_id, type_name, category, is_required, has_expiry,
                   max_file_size_mb, allowed_formats, is_active
            FROM document_types
            ORDER BY category, sort_order, type_name
            ''')

            doc_types = cursor.fetchall()

            print(f"\n📋 DOCUMENT TYPES ({len(doc_types)} total)")
            print("=" * 100)
            print(f"{'ID':<4} {'Name':<25} {'Category':<15} {'Required':<9} {'Expiry':<7} {'Size(MB)':<8} {'Active'}")
            print("-" * 100)

            for doc_type in doc_types:
                type_id, name, category, required, expiry, size, formats, active = doc_type

                required_text = "Yes" if required else "No"
                expiry_text = "Yes" if expiry else "No"
                active_text = "Yes" if active else "No"

                print(f"{type_id:<4} {name:<25} {category:<15} {required_text:<9} {expiry_text:<7} {size:<8} {active_text}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def add_document_type(self):
        """Add a new document type to the system"""
        try:
            print(_t("shared.utils.document_manager.add_doc_type_header", default="\n➕ ADD DOCUMENT TYPE"))

            type_name = input(_t("shared.utils.document_manager.prompt_doc_type_name", default="Document type name: ")).strip()
            if not type_name:
                print(_t("shared.utils.document_manager.type_name_required", default="Type name is required."))
                return

            description = input("Description: ").strip()

            is_required = input("Is this document required? (y/n): ").strip().lower() == 'y'

            has_expiry = input("Does this document expire? (y/n): ").strip().lower() == 'y'

            expiry_reminder_days = 0
            if has_expiry:
                try:
                    expiry_reminder_days = int(input("Reminder days before expiry (e.g., 30): ").strip())
                except ValueError:
                    expiry_reminder_days = 30

            try:
                max_file_size = int(input("Maximum file size in MB (default 10): ").strip() or "10")
            except ValueError:
                max_file_size = 10

            allowed_formats = input("Allowed file formats (comma-separated, e.g., pdf,jpg,png): ").strip()
            if not allowed_formats:
                allowed_formats = "pdf,jpg,jpeg,png"

            requires_approval = input("Requires approval? (y/n): ").strip().lower() == 'y'

            category = input("Category (e.g., Identity, Academic, Health): ").strip() or "General"

            try:
                sort_order = int(input("Sort order (default 0): ").strip() or "0")
            except ValueError:
                sort_order = 0

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO document_types (type_name, description, is_required, has_expiry,
                                       expiry_reminder_days, max_file_size_mb, allowed_formats,
                                       requires_approval, category, sort_order, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ''', (type_name, description, is_required, has_expiry, expiry_reminder_days,
                  max_file_size, allowed_formats, requires_approval, category, sort_order))

            conn.commit()
            conn.close()

            print(f"\n✅ Document type '{type_name}' added successfully!")

        except sqlite3.IntegrityError:
            print(f"Error: Document type '{type_name}' already exists.")
        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def modify_document_type(self):
        """Modify an existing document type"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Show existing types
            cursor.execute('''
            SELECT type_id, type_name, is_required, has_expiry, category
            FROM document_types
            WHERE is_active = 1
            ORDER BY category, type_name
            ''')

            types = cursor.fetchall()

            if not types:
                print(_t("shared.utils.document_manager.no_document_types_found", default="No document types found."))
                conn.close()
                return

            print("\n📝 DOCUMENT TYPES:")
            for i, (type_id, name, required, has_expiry, category) in enumerate(types):
                print(f"{i+1}. {name} ({category}) - Required: {required}, Expires: {has_expiry}")

            try:
                choice = int(input("\nSelect type to modify: ")) - 1
                if 0 <= choice < len(types):
                    type_id = types[choice][0]
                else:
                    print(_t("shared.utils.document_manager.invalid_selection", default="Invalid selection."))
                    conn.close()
                    return
            except ValueError:
                print(_t("shared.utils.document_manager.invalid_input", default="Invalid input."))
                conn.close()
                return

            # Get current values
            cursor.execute('SELECT * FROM document_types WHERE type_id = ?', (type_id,))
            current = cursor.fetchone()

            print(f"\nModifying: {current[1]}")
            print("Press Enter to keep current value")

            new_name = input(f"Name [{current[1]}]: ").strip() or current[1]
            new_desc = input(f"Description [{current[2]}]: ").strip() or current[2]

            is_req_input = input(f"Required (y/n) [{current[3]}]: ").strip().lower()
            new_is_required = is_req_input == 'y' if is_req_input else current[3]

            has_exp_input = input(f"Has expiry (y/n) [{current[4]}]: ").strip().lower()
            new_has_expiry = has_exp_input == 'y' if has_exp_input else current[4]

            new_reminder_days = input(f"Reminder days [{current[5]}]: ").strip()
            new_reminder_days = int(new_reminder_days) if new_reminder_days else current[5]

            new_max_size = input(f"Max file size MB [{current[6]}]: ").strip()
            new_max_size = int(new_max_size) if new_max_size else current[6]

            new_formats = input(f"Allowed formats [{current[7]}]: ").strip() or current[7]

            new_category = input(f"Category [{current[9]}]: ").strip() or current[9]

            cursor.execute('''
            UPDATE document_types
            SET type_name = ?, description = ?, is_required = ?, has_expiry = ?,
                expiry_reminder_days = ?, max_file_size_mb = ?, allowed_formats = ?,
                category = ?
            WHERE type_id = ?
            ''', (new_name, new_desc, new_is_required, new_has_expiry, new_reminder_days,
                  new_max_size, new_formats, new_category, type_id))

            conn.commit()
            conn.close()

            print(_t("shared.utils.document_manager.doc_type_updated", default="\nDocument type updated successfully!"))

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def document_type_management(self):
        """Manage document types"""
        print("\n📋 DOCUMENT TYPE MANAGEMENT")
        print("1. View Document Types")
        print("2. Add Document Type")
        print("3. Modify Document Type")
        print("4. Deactivate Document Type")
        print("5. Return to Main Menu")

        choice = input("\nChoose option (1-5): ").strip()

        if choice == '1':
            self.view_document_types()
        elif choice == '2':
            self.add_document_type()
        elif choice == '3':
            self.modify_document_type()
        elif choice == '4':
            type_id = input("Enter document type ID to deactivate: ").strip()
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE document_types SET is_active = 0 WHERE type_id = ?', (type_id,))
                conn.commit()
                conn.close()
                print(_t("shared.utils.document_manager.doc_type_deactivated", default="Document type deactivated."))
            except sqlite3.Error as e:
                print(f"Database error: {e}")

    def template_analytics(self):
        """Analyze document template usage"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📊 TEMPLATE ANALYTICS")
            print("=" * 80)

            # Most used document types
            cursor.execute('''
            SELECT dt.type_name, COUNT(*) as usage_count
            FROM documents sd
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            GROUP BY dt.type_name
            ORDER BY usage_count DESC
            ''')

            usage = cursor.fetchall()

            if usage:
                print("\nDocument Type Usage:")
                for type_name, count in usage:
                    print(f"  {type_name}: {count} documents")

            # Verification success rate by type
            cursor.execute('''
            SELECT dt.type_name,
                   COUNT(*) as total,
                   SUM(CASE WHEN sd.verification_status = 'Verified' THEN 1 ELSE 0 END) as verified
            FROM documents sd
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            WHERE sd.is_current_version = 1
            GROUP BY dt.type_name
            ORDER BY dt.type_name
            ''')

            verification_rates = cursor.fetchall()

            if verification_rates:
                print("\nVerification Success Rate by Type:")
                for type_name, total, verified in verification_rates:
                    rate = (verified / total * 100) if total > 0 else 0
                    print(f"  {type_name}: {rate:.1f}% ({verified}/{total})")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def set_course_requirements(self):
        """Set document requirements for specific courses/programs"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📚 SET COURSE REQUIREMENTS")

            course_code = input("Course code (e.g., CS101): ").strip()
            if not course_code:
                print("Course code is required.")
                conn.close()
                return

            program = input("Program name: ").strip()

            print("\nSelect required document types:")

            cursor.execute('''
            SELECT type_id, type_name, category
            FROM document_types
            WHERE is_active = 1
            ORDER BY category, type_name
            ''')

            doc_types = cursor.fetchall()

            if not doc_types:
                print("No document types available.")
                conn.close()
                return

            print("\nAvailable Document Types:")
            for i, (type_id, type_name, category) in enumerate(doc_types):
                print(f"{i+1}. {type_name} ({category})")

            selected = input("\nEnter numbers of required documents (comma-separated): ").strip()

            if not selected:
                print("No documents selected.")
                conn.close()
                return

            selected_indices = [int(x.strip()) - 1 for x in selected.split(',')]

            for idx in selected_indices:
                if 0 <= idx < len(doc_types):
                    type_id = doc_types[idx][0]

                    is_mandatory = input(f"Is {doc_types[idx][1]} mandatory? (y/n): ").strip().lower() == 'y'

                    deadline_days = input("Deadline (days after enrollment, default 30): ").strip()
                    deadline_days = int(deadline_days) if deadline_days else 30

                    cursor.execute('''
                    INSERT OR REPLACE INTO course_requirements
                    (course_code, program, type_id, is_mandatory, deadline_days)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (course_code, program, type_id, is_mandatory, deadline_days))

            conn.commit()
            conn.close()

            print(f"\n✅ Requirements set for {course_code}")

        except ValueError:
            print(_t("shared.utils.document_manager.invalid_input", default="Invalid input."))
        except sqlite3.Error as e:
            print(f"Database error: {e}")
