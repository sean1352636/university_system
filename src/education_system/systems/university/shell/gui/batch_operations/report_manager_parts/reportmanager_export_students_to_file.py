"""Methods export_students_to_file through generate_success_rate_report."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import report_manager_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class ReportManager:
    def export_students_to_file(self, output_file: str, export_format: str, filter_params: Dict, include_modules: bool, progress_callback=None):
        """Export students to file with progress callback"""
        import pandas as pd
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Build query
            base_query = """
            SELECT s.student_id, s.email_address, s.title, s.first_name, s.middle_name,
                   s.last_name, s.gender, s.dob, s.age, s.course, s.registration_datetime
            FROM students s
            """

            if include_modules:
                base_query += """
                LEFT JOIN (
                    SELECT student_id, GROUP_CONCAT(module_code || ': ' || module_name, '; ') as modules
                    FROM student_modules GROUP BY student_id
                ) sm ON s.student_id = sm.student_id
                """

            params = []
            conditions = []

            if filter_params.get('course'):
                conditions.append("s.course = ?")
                params.append(filter_params['course'])

            if filter_params.get('start_date') and filter_params.get('end_date'):
                conditions.append("DATE(s.registration_datetime) BETWEEN ? AND ?")
                params.extend([filter_params['start_date'], filter_params['end_date']])

            if conditions:
                base_query += " WHERE " + " AND ".join(conditions)

            base_query += " ORDER BY s.last_name, s.first_name"

            cursor.execute(base_query, params)
            results = cursor.fetchall()

            if not results:
                raise ValueError("No students found matching criteria")

            columns = [description[0] for description in cursor.description]

            if progress_callback:
                progress_callback(50, "Exporting data...")

            # Export based on format
            if export_format == 'csv':
                with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(columns)
                    writer.writerows(results)

            elif export_format == 'xlsx':
                df = pd.DataFrame(results, columns=columns)
                df.to_excel(output_file, index=False)

            elif export_format == 'json':
                json_data = [dict(zip(columns, row)) for row in results]
                with open(output_file, 'w', encoding='utf-8') as jsonfile:
                    json.dump(json_data, jsonfile, indent=2, default=str)

            if progress_callback:
                progress_callback(100, "Export complete")

            conn.close()

        except Exception as e:
            logger.error(f"Error exporting students: {e}")
            raise

    def generate_success_rate_report(self):
        """Generate success rate report and prompt for export location."""
        if not self.gui.backend.import_history:
            try:
                with open(IMPORT_HISTORY_PATH, 'r') as f:
                    self.gui.backend.import_history = json.load(f)
            except FileNotFoundError:
                self.gui.backend.import_history = []

        total_operations = len(self.gui.backend.import_history)
        total_records = sum(op.get('total_records', 0) for op in self.gui.backend.import_history)
        total_successful = sum(op.get('successful_imports', 0) for op in self.gui.backend.import_history)
        total_failed = total_records - total_successful

        success_rate = (total_successful / total_records * 100) if total_records > 0 else 0

        now = datetime.datetime.now()
        report = {
            'report_type': 'success_rate',
            'generated': now.isoformat(),
            'total_operations': total_operations,
            'total_records': total_records,
            'total_successful': total_successful,
            'total_failed': total_failed,
            'success_rate': round(success_rate, 2),
            'operations': []
        }

        # Per-operation breakdown
        for op in self.gui.backend.import_history:
            op_total = op.get('total_records', 0)
            op_success = op.get('successful_imports', 0)
            op_rate = (op_success / op_total * 100) if op_total > 0 else 0
            report['operations'].append({
                'timestamp': op.get('timestamp', 'N/A'),
                'filename': op.get('filename', 'N/A'),
                'total_records': op_total,
                'successful': op_success,
                'failed': op_total - op_success,
                'success_rate': round(op_rate, 2),
            })

        default_name = f"success_rate_report_{now.strftime('%Y%m%d_%H%M%S')}"
        file_path = filedialog.asksaveasfilename(
            title=_t('gui.shell.batch_operations.report_manager_parts.reportmanager_export_students_to_file.dialogs.export_success_rate_report', default="Export Success Rate Report"),
            initialfile=default_name,
            defaultextension=".json",
            filetypes=[
                ("JSON files", "*.json"),
                ("CSV files", "*.csv"),
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ]
        )
        if not file_path:
            return

        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.csv':
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Filename", "Total Records",
                                 "Successful", "Failed", "Success Rate (%)"])
                for op in report['operations']:
                    writer.writerow([
                        op['timestamp'], op['filename'], op['total_records'],
                        op['successful'], op['failed'], op['success_rate'],
                    ])
                writer.writerow([])
                writer.writerow(["TOTALS", "", total_records, total_successful,
                                 total_failed, round(success_rate, 2)])
        elif ext == '.txt':
            with open(file_path, 'w') as f:
                f.write("SUCCESS RATE REPORT\n")
                f.write(f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")
                f.write(f"Total Operations: {total_operations}\n")
                f.write(f"Total Records:    {total_records}\n")
                f.write(f"Successful:       {total_successful}\n")
                f.write(f"Failed:           {total_failed}\n")
                f.write(f"Success Rate:     {success_rate:.2f}%\n\n")
                f.write("-" * 60 + "\n")
                f.write("PER-OPERATION BREAKDOWN:\n")
                f.write("-" * 60 + "\n")
                for op in report['operations']:
                    f.write(f"  {op['timestamp']}  {op['filename']}\n")
                    f.write(f"    Records: {op['total_records']}  "
                            f"Success: {op['successful']}  "
                            f"Failed: {op['failed']}  "
                            f"Rate: {op['success_rate']}%\n")
        else:
            with open(file_path, 'w') as f:
                json.dump(report, f, indent=2)

        messagebox.showinfo(
            _t("batch_ops.msg_titles.exported"),
            f"Success rate report saved to:\n{file_path}"
        )
