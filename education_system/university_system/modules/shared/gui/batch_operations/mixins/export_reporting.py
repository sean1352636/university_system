"""Export and reporting mixin."""

from education_system.university_system.modules.shared.gui.batch_operations.constants import (
    csv, datetime, json, logging,
    Dict, List, Tuple,
    pd,
    DATA_DIR,
    logger,
)


class ExportReportingMixin:
    """Mixin providing data export and report generation methods."""

    def export_data_to_file(self, data: List[Tuple], columns: List[str],
                           filename: str, format_type: str = 'csv',
                           progress_callback=None) -> str:
        """Generic export utility function - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, f"Exporting {len(data)} records to {format_type.upper()}...")

            # Ensure filename has correct extension
            if format_type == 'csv' and not filename.endswith('.csv'):
                filename += '.csv'
            elif format_type == 'excel' and not filename.endswith('.xlsx'):
                filename += '.xlsx'

            # Create full path
            export_path = DATA_DIR / 'exports' / filename
            export_path.parent.mkdir(parents=True, exist_ok=True)

            if format_type == 'csv':
                # Export to CSV
                with open(export_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(columns)
                    writer.writerows(data)

            elif format_type == 'excel':
                # Export to Excel
                df = pd.DataFrame(data, columns=columns)
                df.to_excel(export_path, index=False, engine='openpyxl')

            else:
                raise ValueError(f"Unsupported format type: {format_type}")

            if progress_callback:
                progress_callback(100, f"Export complete: {export_path}")

            logger.info(f"Exported {len(data)} records to {export_path}")
            return str(export_path)

        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            raise

    def export_enrollment_statistics(self, output_format: str = 'csv',
                                     progress_callback=None) -> str:
        """Export enrollment statistics report - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, "Gathering enrollment statistics...")

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get enrollment statistics by course
                cursor.execute("""
                    SELECT
                        course,
                        COUNT(*) as total_students,
                        SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active_students,
                        SUM(CASE WHEN status = 'Inactive' THEN 1 ELSE 0 END) as inactive_students,
                        SUM(CASE WHEN status = 'Graduated' THEN 1 ELSE 0 END) as graduated_students,
                        MIN(enrollment_date) as earliest_enrollment,
                        MAX(enrollment_date) as latest_enrollment
                    FROM students
                    GROUP BY course
                    ORDER BY total_students DESC
                """)

                stats = cursor.fetchall()

                if not stats:
                    raise ValueError("No enrollment data found")

                columns = [
                    'Course', 'Total Students', 'Active', 'Inactive', 'Graduated',
                    'Earliest Enrollment', 'Latest Enrollment'
                ]

                if progress_callback:
                    progress_callback(50, "Generating report...")

                # Generate filename with timestamp
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'enrollment_statistics_{timestamp}'

                # Export data
                export_path = self.export_data_to_file(
                    stats,
                    columns,
                    filename,
                    output_format,
                    None  # Don't pass progress callback to avoid double updates
                )

                if progress_callback:
                    progress_callback(100, f"Statistics exported: {export_path}")

                logger.info(f"Exported enrollment statistics to {export_path}")
                return export_path

        except Exception as e:
            logger.error(f"Error exporting enrollment statistics: {e}")
            raise

    def generate_import_reports(self, report_type: str = 'summary',
                                start_date: str = None, end_date: str = None,
                                progress_callback=None) -> Dict:
        """Generate import reports - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, f"Generating {report_type} import report...")

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Ensure import_history table exists
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS import_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        operation_type TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        total_records INTEGER DEFAULT 0,
                        successful_imports INTEGER DEFAULT 0,
                        failed_imports INTEGER DEFAULT 0,
                        duplicates_found INTEGER DEFAULT 0,
                        validation_errors INTEGER DEFAULT 0,
                        error_details TEXT,
                        duration_seconds REAL,
                        status TEXT DEFAULT 'completed'
                    )
                """)

                # Build query based on report type
                query = "SELECT * FROM import_history WHERE 1=1"
                params = []

                if start_date:
                    query += " AND timestamp >= ?"
                    params.append(start_date)

                if end_date:
                    query += " AND timestamp <= ?"
                    params.append(end_date)

                query += " ORDER BY timestamp DESC"

                cursor.execute(query, params)
                history = cursor.fetchall()

                if progress_callback:
                    progress_callback(50, "Analyzing import history...")

                # Generate report based on type
                report = {
                    'report_type': report_type,
                    'generated_at': datetime.datetime.now().isoformat(),
                    'period': {
                        'start_date': start_date or 'All time',
                        'end_date': end_date or 'Present'
                    },
                    'total_operations': len(history)
                }

                if report_type == 'summary':
                    total_records = sum(h[4] for h in history)
                    successful = sum(h[5] for h in history)
                    failed = sum(h[6] for h in history)
                    duplicates = sum(h[7] for h in history)

                    report['summary'] = {
                        'total_records_processed': total_records,
                        'successful_imports': successful,
                        'failed_imports': failed,
                        'duplicates_found': duplicates,
                        'success_rate': round((successful / total_records * 100) if total_records > 0 else 0, 2)
                    }

                elif report_type == 'detailed':
                    report['operations'] = []
                    for h in history:
                        report['operations'].append({
                            'id': h[0],
                            'timestamp': h[1],
                            'operation_type': h[2],
                            'file_path': h[3],
                            'total_records': h[4],
                            'successful_imports': h[5],
                            'failed_imports': h[6],
                            'duplicates_found': h[7],
                            'status': h[11] if len(h) > 11 else 'unknown'
                        })

                elif report_type == 'errors':
                    report['errors'] = []
                    for h in history:
                        if h[6] > 0:  # failed_imports > 0
                            error_details = json.loads(h[9]) if h[9] else {}
                            report['errors'].append({
                                'timestamp': h[1],
                                'operation': h[2],
                                'file': h[3],
                                'failed_count': h[6],
                                'error_details': error_details.get('errors', [])[:10]
                            })

                elif report_type == 'trends':
                    report['trends'] = []
                    date_groups = {}
                    for h in history:
                        date = h[1][:10]
                        if date not in date_groups:
                            date_groups[date] = {'total': 0, 'successful': 0, 'failed': 0}
                        date_groups[date]['total'] += h[4]
                        date_groups[date]['successful'] += h[5]
                        date_groups[date]['failed'] += h[6]

                    report['trends'] = [
                        {'date': date, **stats}
                        for date, stats in sorted(date_groups.items())
                    ]

                if progress_callback:
                    progress_callback(100, "Report generation complete")

                logger.info(f"Generated {report_type} import report")
                return report

        except Exception as e:
            logger.error(f"Error generating import reports: {e}")
            raise
