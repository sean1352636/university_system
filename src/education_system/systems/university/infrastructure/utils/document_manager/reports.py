from education_system.systems.university.infrastructure.utils.document_manager._common import (
    csv, datetime, timedelta, sqlite3,
    get_connection, _t,
)


class ReportsMixin:
    def generate_reports_menu(self):
        """Menu for generating various reports"""
        print(_t("shared.utils.document_manager.reports_header", default="\n📊 REPORT GENERATION"))
        print(_t("shared.utils.document_manager.menu_status_report", default="1. Status Report"))
        print(_t("shared.utils.document_manager.menu_expiry_report", default="2. Expiry Report"))
        print(_t("shared.utils.document_manager.menu_dept_analysis", default="3. Department Analysis"))
        print(_t("shared.utils.document_manager.menu_monthly_summary", default="4. Monthly Summary"))
        print(_t("shared.utils.document_manager.menu_student_progress", default="5. Student Progress Report"))
        print(_t("shared.utils.document_manager.menu_compliance_report", default="6. Compliance Report"))
        print(_t("shared.utils.document_manager.menu_custom_report", default="7. Custom Report Builder"))
        print(_t("shared.utils.document_manager.menu_return_main", default="8. Return to Main Menu"))

        choice = input(_t("shared.utils.document_manager.prompt_choose_report", default="\nChoose report type (1-8): ")).strip()

        if choice == '1':
            self.generate_status_report()
        elif choice == '2':
            self.generate_expiry_report()
        elif choice == '3':
            self.generate_department_analysis()
        elif choice == '4':
            self.generate_monthly_summary()
        elif choice == '5':
            self.generate_student_progress_report()
        elif choice == '6':
            self.generate_compliance_report()
        elif choice == '7':
            self.custom_report_builder()

    def generate_compliance_report(self):
        """Generate detailed compliance report"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📊 COMPLIANCE REPORT")
            print("=" * 80)

            # Get filters
            course_filter = input("Filter by course (leave blank for all): ").strip()
            year_filter = input("Filter by year (leave blank for all): ").strip()

            # Build query
            query = '''
            SELECT s.student_id, s.first_name, s.last_name, s.course, s.year,
                   COUNT(DISTINCT dt.type_id) as total_required,
                   COUNT(DISTINCT CASE WHEN sd.document_id IS NOT NULL THEN dt.type_id END) as submitted,
                   COUNT(DISTINCT CASE WHEN sd.verification_status = 'Verified' THEN dt.type_id END) as verified
            FROM students s
            CROSS JOIN document_types dt
            LEFT JOIN documents sd ON s.student_id = sd.owner_id
                AND sd.source_type = 'student'
                AND dt.type_id = CAST(sd.document_type AS INTEGER) AND sd.is_current_version = 1
            WHERE dt.is_required = 1 AND dt.is_active = 1
            '''

            params = []

            if course_filter:
                query += " AND s.course = ?"
                params.append(course_filter)

            if year_filter:
                query += " AND s.year = ?"
                params.append(year_filter)

            query += '''
            GROUP BY s.student_id
            ORDER BY s.last_name, s.first_name
            '''

            cursor.execute(query, params)
            data = cursor.fetchall()

            if not data:
                print("No data found for the specified criteria.")
                conn.close()
                return

            print(f"\n{'Student ID':<12} {'Name':<25} {'Course':<15} {'Year':<5} {'Required':<10} {'Submitted':<10} {'Verified':<10} {'Compliance'}")
            print("-" * 105)

            compliant_count = 0
            for row in data:
                student_id, first_name, last_name, course, year, total_req, submitted, verified = row

                compliance_pct = (submitted / total_req * 100) if total_req > 0 else 0
                compliance_text = f"{compliance_pct:.0f}%"

                if compliance_pct == 100:
                    compliant_count += 1

                name = f"{first_name} {last_name}"
                print(f"{student_id:<12} {name:<25} {course or 'N/A':<15} {year or 'N/A':<5} {total_req:<10} {submitted:<10} {verified:<10} {compliance_text}")

            # Summary
            total_students = len(data)
            overall_compliance = (compliant_count / total_students * 100) if total_students > 0 else 0

            print(f"\n{'='*105}")
            print(f"Total Students: {total_students}")
            print(f"Fully Compliant: {compliant_count} ({overall_compliance:.1f}%)")
            print(f"Non-Compliant: {total_students - compliant_count}")

            # Export option
            export = input("\nExport compliance report? (y/n): ").strip().lower()
            if export == 'y':
                self.export_compliance_report(data, course_filter, year_filter)

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def export_compliance_report(self, data, course_filter, year_filter):
        """Export compliance report to CSV"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"compliance_report_{timestamp}.csv"

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Student ID', 'First Name', 'Last Name', 'Course', 'Year',
                           'Required Documents', 'Submitted', 'Verified', 'Compliance %'])

            for row in data:
                student_id, first_name, last_name, course, year, total_req, submitted, verified = row
                compliance_pct = (submitted / total_req * 100) if total_req > 0 else 0
                writer.writerow([student_id, first_name, last_name, course, year,
                               total_req, submitted, verified, f"{compliance_pct:.1f}"])

        print(f"✅ Report exported to {filename}")

    def generate_status_report(self):
        """Generate a comprehensive status report for all documents"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📊 DOCUMENT STATUS REPORT")
            print("=" * 80)

            # Overall statistics
            cursor.execute('''
            SELECT verification_status, COUNT(*) as count
            FROM documents
            WHERE is_current_version = 1
            GROUP BY verification_status
            ''')

            status_counts = cursor.fetchall()

            print("\nDocument Status Summary:")
            total_docs = 0
            for status, count in status_counts:
                print(f"  {status}: {count}")
                total_docs += count
            print(f"  Total: {total_docs}")

            # Workflow status
            cursor.execute('''
            SELECT workflow_status, COUNT(*) as count
            FROM documents
            WHERE is_current_version = 1
            GROUP BY workflow_status
            ''')

            workflow_counts = cursor.fetchall()

            print("\nWorkflow Status Summary:")
            for workflow, count in workflow_counts:
                print(f"  {workflow}: {count}")

            # By document type
            cursor.execute('''
            SELECT dt.type_name, COUNT(*) as count,
                   SUM(CASE WHEN sd.verification_status = 'Verified' THEN 1 ELSE 0 END) as verified
            FROM documents sd
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            WHERE sd.is_current_version = 1
            GROUP BY dt.type_name
            ORDER BY count DESC
            ''')

            type_counts = cursor.fetchall()

            print("\nDocuments by Type:")
            for type_name, count, verified in type_counts:
                print(f"  {type_name}: {count} total, {verified} verified")

            # Export option
            export = input("\nExport this report to CSV? (y/n): ").strip().lower()
            if export == 'y':
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"status_report_{timestamp}.csv"

                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Status', 'Count'])
                    writer.writerows(status_counts)
                    writer.writerow([])
                    writer.writerow(['Document Type', 'Total', 'Verified'])
                    writer.writerows(type_counts)

                print(f"✅ Report exported to {filename}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def generate_expiry_report(self):
        """Generate report of documents expiring soon"""
        try:
            days_ahead = input("Check documents expiring within how many days? (default 30): ").strip()
            days_ahead = int(days_ahead) if days_ahead else 30

            conn = get_connection()
            cursor = conn.cursor()

            future_date = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
            current_date = datetime.now().strftime('%Y-%m-%d')

            cursor.execute('''
            SELECT sd.document_id, sd.owner_id as student_id, s.first_name, s.last_name,
                   dt.type_name, sd.expiry_date, sd.verification_status
            FROM documents sd
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            LEFT JOIN students s ON sd.owner_id = s.student_id
            WHERE sd.expiry_date IS NOT NULL
              AND sd.expiry_date <= ?
              AND sd.expiry_date >= ?
              AND sd.is_current_version = 1
            ORDER BY sd.expiry_date ASC
            ''', (future_date, current_date))

            expiring_docs = cursor.fetchall()

            print(f"\n📅 EXPIRY REPORT - Documents expiring within {days_ahead} days")
            print("=" * 80)

            if not expiring_docs:
                print("No documents expiring within the specified period.")
                conn.close()
                return

            for doc in expiring_docs:
                doc_id, student_id, first_name, last_name, type_name, expiry_date, status = doc

                expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d')
                days_left = (expiry_dt - datetime.now()).days

                urgency = "🔴 URGENT" if days_left <= 7 else "🟡 WARNING" if days_left <= 30 else "🟢 OK"

                print(f"\n{urgency} Document ID: {doc_id}")
                print(f"  Student: {first_name} {last_name} ({student_id})")
                print(f"  Type: {type_name}")
                print(f"  Expires: {expiry_date} ({days_left} days)")
                print(f"  Status: {status}")

            print(f"\nTotal expiring documents: {len(expiring_docs)}")

            # Export option
            export = input("\nExport this report to CSV? (y/n): ").strip().lower()
            if export == 'y':
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"expiry_report_{timestamp}.csv"

                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Document ID', 'Student ID', 'Student Name', 'Document Type',
                                   'Expiry Date', 'Days Remaining', 'Status'])

                    for doc in expiring_docs:
                        expiry_dt = datetime.strptime(doc[5], '%Y-%m-%d')
                        days_left = (expiry_dt - datetime.now()).days
                        writer.writerow([doc[0], doc[1], f"{doc[2]} {doc[3]}",
                                       doc[4], doc[5], days_left, doc[6]])

                print(f"✅ Report exported to {filename}")

            conn.close()

        except ValueError:
            print(_t("shared.utils.document_manager.invalid_input", default="Invalid input."))
        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def generate_department_analysis(self):
        """Generate analysis report by department/program"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n🏢 DEPARTMENT ANALYSIS REPORT")
            print("=" * 80)

            # Get programs from students
            cursor.execute('''
            SELECT DISTINCT s.course, COUNT(DISTINCT s.student_id) as student_count,
                   COUNT(sd.document_id) as doc_count,
                   SUM(CASE WHEN sd.verification_status = 'Verified' THEN 1 ELSE 0 END) as verified_count
            FROM students s
            LEFT JOIN documents sd ON s.student_id = sd.owner_id
                AND sd.source_type = 'student'
                AND sd.is_current_version = 1
            WHERE s.course IS NOT NULL
            GROUP BY s.course
            ORDER BY s.course
            ''')

            programs = cursor.fetchall()

            if not programs:
                print(_t("shared.utils.document_manager.no_program_data", default="No program data available."))
                conn.close()
                return

            print("\nDocuments by Program:")
            print(f"{'Program':<30} {'Students':<10} {'Documents':<12} {'Verified':<10}")
            print("-" * 80)

            for program, students, docs, verified in programs:
                completion_rate = (verified / docs * 100) if docs > 0 else 0
                print(f"{program:<30} {students:<10} {docs:<12} {verified:<10} ({completion_rate:.1f}%)")

            # Detailed breakdown by document type for each program
            show_details = input("\nShow detailed breakdown by document type? (y/n): ").strip().lower()

            if show_details == 'y':
                for program, _, _, _ in programs:
                    print(f"\n{program}:")

                    cursor.execute('''
                    SELECT dt.type_name, COUNT(*) as count,
                           SUM(CASE WHEN sd.verification_status = 'Verified' THEN 1 ELSE 0 END) as verified
                    FROM documents sd
                    JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
                    JOIN students s ON sd.owner_id = s.student_id
                    WHERE s.course = ? AND sd.is_current_version = 1
                    GROUP BY dt.type_name
                    ''', (program,))

                    type_breakdown = cursor.fetchall()

                    for type_name, count, verified in type_breakdown:
                        print(f"  {type_name}: {count} total, {verified} verified")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def generate_monthly_summary(self):
        """Generate monthly activity summary"""
        try:
            month_input = input("Enter month (YYYY-MM) or press Enter for current month: ").strip()

            if not month_input:
                target_month = datetime.now().strftime('%Y-%m')
            else:
                target_month = month_input

            conn = get_connection()
            cursor = conn.cursor()

            print(f"\n📆 MONTHLY SUMMARY - {target_month}")
            print("=" * 80)

            # Documents uploaded this month
            cursor.execute('''
            SELECT COUNT(*)
            FROM documents
            WHERE strftime('%Y-%m', upload_date) = ?
            ''', (target_month,))

            uploaded_count = cursor.fetchone()[0]
            print(f"\nDocuments Uploaded: {uploaded_count}")

            # Documents verified this month
            cursor.execute('''
            SELECT COUNT(*)
            FROM documents
            WHERE strftime('%Y-%m', verification_date) = ?
            ''', (target_month,))

            verified_count = cursor.fetchone()[0]
            print(f"Documents Verified: {verified_count}")

            # Most active users
            cursor.execute('''
            SELECT uploaded_by, COUNT(*) as count
            FROM documents
            WHERE strftime('%Y-%m', upload_date) = ?
            GROUP BY uploaded_by
            ORDER BY count DESC
            LIMIT 5
            ''', (target_month,))

            active_users = cursor.fetchall()

            if active_users:
                print("\nMost Active Users:")
                for user, count in active_users:
                    print(f"  {user}: {count} uploads")

            # Document types uploaded
            cursor.execute('''
            SELECT dt.type_name, COUNT(*) as count
            FROM documents sd
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            WHERE strftime('%Y-%m', sd.upload_date) = ?
            GROUP BY dt.type_name
            ORDER BY count DESC
            ''', (target_month,))

            type_breakdown = cursor.fetchall()

            if type_breakdown:
                print("\nDocument Types Uploaded:")
                for type_name, count in type_breakdown:
                    print(f"  {type_name}: {count}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def generate_student_progress_report(self):
        """Generate comprehensive progress report for a student"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            student_id = self.select_student(cursor)
            if not student_id:
                conn.close()
                return

            # Get student info
            cursor.execute('''
            SELECT first_name, last_name, program, enrollment_year
            FROM students WHERE student_id = ?
            ''', (student_id,))

            student_info = cursor.fetchone()

            if not student_info:
                print(_t("shared.utils.document_manager.student_not_found", default="Student not found."))
                conn.close()
                return

            first_name, last_name, program, enrollment_year = student_info

            print("\n📊 STUDENT PROGRESS REPORT")
            print("=" * 80)
            print(f"Student: {first_name} {last_name} ({student_id})")
            print(f"Program: {program}")
            print(f"Enrollment Year: {enrollment_year}")
            print("=" * 80)

            # Get all documents
            cursor.execute('''
            SELECT dt.type_name, dt.is_required, sd.verification_status,
                   sd.upload_date, sd.expiry_date
            FROM document_types dt
            LEFT JOIN documents sd ON dt.type_id = CAST(sd.document_type AS INTEGER)
                AND sd.owner_id = ? AND sd.source_type = 'student' AND sd.is_current_version = 1
            WHERE dt.is_active = 1
            ORDER BY dt.category, dt.sort_order
            ''', (student_id,))

            documents = cursor.fetchall()

            required_count = 0
            required_submitted = 0
            total_verified = 0

            print("\nDocument Completion Status:")
            print(f"{'Document Type':<30} {'Required':<10} {'Status':<15} {'Upload Date':<15}")
            print("-" * 80)

            for doc in documents:
                type_name, is_required, status, upload_date, expiry_date = doc

                if is_required:
                    required_count += 1
                    if status:
                        required_submitted += 1

                if status == 'Verified':
                    total_verified += 1

                req_text = "Yes" if is_required else "No"
                status_text = status if status else "Not Submitted"
                upload_text = upload_date[:10] if upload_date else "-"

                print(f"{type_name:<30} {req_text:<10} {status_text:<15} {upload_text:<15}")

            # Summary
            print("\n" + "=" * 80)
            print(f"Required Documents: {required_submitted}/{required_count}")
            print(f"Total Verified: {total_verified}")

            completion_pct = (required_submitted / required_count * 100) if required_count > 0 else 0
            print(f"Completion Rate: {completion_pct:.1f}%")

            # Check for missing required documents
            cursor.execute('''
            SELECT dt.type_name
            FROM document_types dt
            LEFT JOIN documents sd ON dt.type_id = CAST(sd.document_type AS INTEGER)
                AND sd.owner_id = ? AND sd.source_type = 'student' AND sd.is_current_version = 1
            WHERE dt.is_required = 1 AND dt.is_active = 1 AND sd.document_id IS NULL
            ''', (student_id,))

            missing_docs = cursor.fetchall()

            if missing_docs:
                print("\n⚠️  Missing Required Documents:")
                for doc in missing_docs:
                    print(f"  - {doc[0]}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def custom_report_builder(self):
        """Custom report builder with flexible criteria"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📊 CUSTOM REPORT BUILDER")
            print("=" * 80)

            print("\nSelect Report Fields:")
            print("1. Student Information (ID, Name, Course, Year)")
            print("2. Document Details (Type, Filename, Upload Date)")
            print("3. Verification Status")
            print("4. Workflow Information")
            print("5. Expiry Information")

            fields = input("Select fields to include (e.g., 1,2,3): ").strip()

            if not fields:
                conn.close()
                return

            field_indices = [int(f.strip()) for f in fields.split(',')]

            # Build SELECT clause
            select_parts = []
            headers = []

            if 1 in field_indices:
                select_parts.extend(['s.student_id', "s.first_name || ' ' || s.last_name as student_name",
                                   's.course', 's.year'])
                headers.extend(['Student ID', 'Student Name', 'Course', 'Year'])

            if 2 in field_indices:
                select_parts.extend(['dt.type_name', 'sd.original_filename',
                                   'DATE(sd.upload_date) as upload_date'])
                headers.extend(['Document Type', 'Filename', 'Upload Date'])

            if 3 in field_indices:
                select_parts.extend(['sd.verification_status', 'sd.verification_date',
                                   'sd.verification_notes'])
                headers.extend(['Status', 'Verified Date', 'Notes'])

            if 4 in field_indices:
                select_parts.extend(['sd.workflow_status', 'sd.priority'])
                headers.extend(['Workflow Status', 'Priority'])

            if 5 in field_indices:
                select_parts.extend(['sd.expiry_date', 'sd.version_number'])
                headers.extend(['Expiry Date', 'Version'])

            if not select_parts:
                print("No fields selected.")
                conn.close()
                return

            # Build query
            query = f'''
            SELECT {', '.join(select_parts)}
            FROM documents sd
            JOIN students s ON sd.owner_id = s.student_id
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            WHERE sd.is_current_version = 1
            '''

            # Add filters
            params = []

            status_filter = input("\nFilter by status (leave blank for all): ").strip()
            if status_filter:
                query += " AND sd.verification_status = ?"
                params.append(status_filter)

            course_filter = input("Filter by course (leave blank for all): ").strip()
            if course_filter:
                query += " AND s.course = ?"
                params.append(course_filter)

            query += " ORDER BY s.last_name, s.first_name LIMIT 500"

            cursor.execute(query, params)
            data = cursor.fetchall()

            if not data:
                print("No data found for the specified criteria.")
                conn.close()
                return

            # Display results
            print(f"\nResults ({len(data)} records):")
            print("-" * 120)

            # Print headers
            header_line = " | ".join(f"{h:<15}" for h in headers)
            print(header_line)
            print("-" * 120)

            for row in data[:50]:  # Display first 50 rows
                row_line = " | ".join(f"{str(val)[:15]:<15}" for val in row)
                print(row_line)

            if len(data) > 50:
                print(f"\n... and {len(data) - 50} more records")

            # Export option
            export = input("\nExport full report to CSV? (y/n): ").strip().lower()
            if export == 'y':
                filters = {'status': status_filter, 'course': course_filter}
                self.export_custom_report(data, headers, filters)

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def export_custom_report(self, data, headers, filters):
        """Export custom report data"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"custom_report_{timestamp}.csv"

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(data)

        print(f"✅ Report exported to {filename}")
        print(f"Total records: {len(data)}")
