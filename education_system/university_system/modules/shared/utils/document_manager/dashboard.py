from ._common import datetime, timedelta, sqlite3, get_connection


class DashboardMixin:
    def display_dashboard(self):
        """Display comprehensive dashboard"""
        print("\n📊 SYSTEM DASHBOARD")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Quick stats
            self.display_quick_stats(cursor)

            # Document status overview
            self.display_status_overview(cursor)

            # Recent activity
            self.display_recent_activity(cursor)

            # Expiry alerts
            self.display_expiry_alerts(cursor)

            # Performance metrics
            self.display_performance_metrics(cursor)

            conn.close()

        except sqlite3.Error as e:
            print(f"Dashboard error: {e}")

    def display_quick_stats(self, cursor):
        """Display quick statistics"""
        print("\n📈 Quick Statistics:")
        print("-" * 50)

        # Total documents
        cursor.execute('SELECT COUNT(*) FROM student_documents WHERE is_current_version = 1')
        total_docs = cursor.fetchone()[0]

        # Total students with documents
        cursor.execute('SELECT COUNT(DISTINCT student_id) FROM student_documents')
        students_with_docs = cursor.fetchone()[0]

        # Pending documents
        cursor.execute('SELECT COUNT(*) FROM student_documents WHERE verification_status = "Pending" AND is_current_version = 1')
        pending_docs = cursor.fetchone()[0]

        # Documents uploaded today
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('SELECT COUNT(*) FROM student_documents WHERE DATE(upload_date) = ?', (today,))
        today_uploads = cursor.fetchone()[0]

        print(f"Total Documents: {total_docs}")
        print(f"Students with Documents: {students_with_docs}")
        print(f"Pending Review: {pending_docs}")
        print(f"Uploaded Today: {today_uploads}")

    def display_status_overview(self, cursor):
        """Display document status overview"""
        print("\n📋 Document Status Overview:")
        print("-" * 50)

        cursor.execute('''
        SELECT verification_status, COUNT(*) as count
        FROM student_documents
        WHERE is_current_version = 1
        GROUP BY verification_status
        ORDER BY count DESC
        ''')

        status_data = cursor.fetchall()

        if status_data:
            total = sum(count for _, count in status_data)
            for status, count in status_data:
                percentage = (count / total) * 100 if total > 0 else 0
                print(f"{status:<15}: {count:>5} ({percentage:>5.1f}%)")

    def display_recent_activity(self, cursor):
        """Display recent activity"""
        print("\n🕒 Recent Activity (Last 7 days):")
        print("-" * 80)

        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        cursor.execute('''
        SELECT DATE(sd.upload_date) as upload_day,
               COUNT(*) as daily_count
        FROM student_documents sd
        WHERE DATE(sd.upload_date) >= ?
        GROUP BY DATE(sd.upload_date)
        ORDER BY upload_day DESC
        ''', (week_ago,))

        activity_data = cursor.fetchall()

        if activity_data:
            print(f"{'Date':<12} {'Documents Uploaded':<20}")
            print("-" * 35)
            for date, count in activity_data:
                print(f"{date:<12} {count:<20}")
        else:
            print("No recent activity found.")

    def display_expiry_alerts(self, cursor):
        """Display expiry alerts"""
        print("\n⚠️ Expiry Alerts:")
        print("-" * 80)

        # Documents expiring in next 30 days
        future_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')

        cursor.execute('''
        SELECT COUNT(*)
        FROM student_documents sd
        WHERE sd.expiry_date BETWEEN ? AND ?
        AND sd.verification_status != 'Expired'
        AND sd.is_current_version = 1
        ''', (today, future_date))

        expiring_soon = cursor.fetchone()[0]

        # Already expired documents
        cursor.execute('''
        SELECT COUNT(*)
        FROM student_documents sd
        WHERE sd.expiry_date < ?
        AND sd.verification_status != 'Expired'
        AND sd.is_current_version = 1
        ''', (today,))

        already_expired = cursor.fetchone()[0]

        print(f"Expiring within 30 days: {expiring_soon}")
        print(f"Already expired: {already_expired}")

        if expiring_soon > 0 or already_expired > 0:
            print("\n💡 Tip: Use 'Check Document Expiry' to view details and take action.")

    def display_performance_metrics(self, cursor):
        """Display performance metrics"""
        print("\n⚡ Performance Metrics:")
        print("-" * 50)

        # Average processing time (mock calculation)
        cursor.execute('''
        SELECT AVG(
            CASE
                WHEN verification_date IS NOT NULL
                THEN julianday(verification_date) - julianday(upload_date)
                ELSE NULL
            END
        ) as avg_processing_days
        FROM student_documents
        WHERE verification_date IS NOT NULL
        ''')

        avg_processing = cursor.fetchone()[0]

        if avg_processing:
            print(f"Average Processing Time: {avg_processing:.1f} days")
        else:
            print("Average Processing Time: No data available")

        # Compliance rate
        cursor.execute('''
        SELECT
            COUNT(DISTINCT s.student_id) as total_students,
            COUNT(DISTINCT CASE WHEN req_count.missing_count = 0 THEN s.student_id END) as compliant_students
        FROM students s
        LEFT JOIN (
            SELECT s.student_id,
                   COUNT(dt.type_id) - COUNT(sd.document_id) as missing_count
            FROM students s
            CROSS JOIN document_types dt
            LEFT JOIN student_documents sd ON s.student_id = sd.student_id
                AND dt.type_id = sd.type_id
                AND sd.is_current_version = 1
            WHERE dt.is_required = 1
            GROUP BY s.student_id
        ) req_count ON s.student_id = req_count.student_id
        ''')

        total_students, compliant_students = cursor.fetchone()

        if total_students > 0:
            compliance_rate = (compliant_students / total_students) * 100
            print(f"Compliance Rate: {compliance_rate:.1f}% ({compliant_students}/{total_students})")
