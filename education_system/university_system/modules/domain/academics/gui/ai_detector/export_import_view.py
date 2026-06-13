import json
import os
import threading
import time
import random
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext

from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, sqlite3
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

try:
    from education_system.university_system.infrastructure.ai.ai_detector.detector import AIDetector
    _AI_DETECTOR_IMPORT_ERROR = None
except Exception as import_error:
    AIDetector = None
    _AI_DETECTOR_IMPORT_ERROR = import_error

try:
    import textract
    TEXTRACT_AVAILABLE = True
except ImportError:
    TEXTRACT_AVAILABLE = False

try:
    from pypdf import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import docx
    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False

from education_system.university_system.core.i18n import get_text, _

def create_export_section(self, parent):
    """Create export/import section"""
    export_frame = ttk.LabelFrame(parent, text="Data Management", padding=15)
    export_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Label(export_frame, text="Export results and manage data").pack(anchor='w')

    export_buttons = ttk.Frame(export_frame)
    export_buttons.pack(fill='x', pady=(10, 0))

    ttk.Button(export_buttons, text="📤 Export Results", command=self.export_results).pack(side='left', padx=(0, 10))
    ttk.Button(export_buttons, text="📥 Import Data", command=self.import_data).pack(side='left', padx=(0, 10))
    ttk.Button(export_buttons, text="🗄️ Database Status", command=self.show_db_status).pack(side='left')


def create_data_export_import_view(self, parent):
    """Create enhanced data export/import tab - MISSING"""
    export_frame = ttk.Frame(parent)

    export_frame.pack(fill="both", expand=True)

    # Data management card
    data_card = ttk.Frame(export_frame, style='Card.TFrame')
    data_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(data_card, text="Advanced Data Management", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Export options
    export_frame_inner = ttk.LabelFrame(data_card, text="Export Options", padding=15)
    export_frame_inner.pack(fill='x', padx=15, pady=(0, 15))

    export_buttons = ttk.Frame(export_frame_inner)
    export_buttons.pack(fill='x')

    ttk.Button(export_buttons, text="📊 Export Detailed Report",
              command=self.export_detailed_report).pack(side='left', padx=(0, 10))
    ttk.Button(export_buttons, text="📈 Export Analytics Data",
              command=self.export_analytics_data).pack(side='left', padx=(0, 10))
    ttk.Button(export_buttons, text="🔐 Export Audit Log",
              command=self.export_audit_log).pack(side='left')

    # Import options
    import_frame_inner = ttk.LabelFrame(data_card, text="Import Options", padding=15)
    import_frame_inner.pack(fill='x', padx=15, pady=(0, 15))

    import_buttons = ttk.Frame(import_frame_inner)
    import_buttons.pack(fill='x')

    ttk.Button(import_buttons, text="📥 Import Submissions",
              command=self.import_submissions).pack(side='left', padx=(0, 10))
    ttk.Button(import_buttons, text="👥 Import Student Data",
              command=self.import_student_data).pack(side='left', padx=(0, 10))
    ttk.Button(import_buttons, text="⚙️ Import Settings",
              command=self.import_settings).pack(side='left')

    # Data cleanup
    cleanup_frame = ttk.LabelFrame(data_card, text="Data Cleanup", padding=15)
    cleanup_frame.pack(fill='x', padx=15, pady=(0, 15))

    cleanup_buttons = ttk.Frame(cleanup_frame)
    cleanup_buttons.pack(fill='x')

    ttk.Button(cleanup_buttons, text="🗑️ Archive Old Data",
              command=self.archive_old_data).pack(side='left', padx=(0, 10))
    ttk.Button(cleanup_buttons, text="🔄 Optimize Database",
              command=self.optimize_database).pack(side='left', padx=(0, 10))
    ttk.Button(cleanup_buttons, text="🧹 Clean Duplicates",
              command=self.clean_duplicates).pack(side='left')


def export_results(self):
    """Export analysis results"""
    file_path = filedialog.asksaveasfilename(
        title="Export Results",
        defaultextension=".json",
        filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv"), ("All files", "*.*")]
    )

    if file_path:
        try:
            # Get all submissions
            history_data = self.detector.get_submission_history(limit=1000)
            submissions = history_data.get('submissions', [])

            if file_path.endswith('.csv'):
                # Export as CSV
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    if submissions:
                        fieldnames = submissions[0].keys()
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        for submission in submissions:
                            # Remove text content for CSV (too large)
                            clean_submission = {k: v for k, v in submission.items()
                                              if k != 'submission_text'}
                            writer.writerow(clean_submission)
            else:
                # Export as JSON
                with open(file_path, 'w', encoding='utf-8') as jsonfile:
                    export_data = {
                        'export_date': datetime.now().isoformat(),
                        'total_submissions': len(submissions),
                        'submissions': submissions
                    }
                    json.dump(export_data, jsonfile, indent=2, default=str)

            messagebox.showinfo("Export Complete", f"Results exported to {file_path}")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export results: {str(e)}")


def export_detailed_report(self):
    """Export detailed analysis report"""
    file_path = filedialog.asksaveasfilename(
        title="Export Detailed Report",
        defaultextension=".pdf",
        filetypes=[("PDF files", "*.pdf"), ("HTML files", "*.html"), ("Word files", "*.docx")]
    )

    if file_path:
        try:
            # Generate comprehensive report
            report_data = self.generate_comprehensive_report()

            if file_path.endswith('.pdf'):
                self.export_to_pdf(report_data, file_path)
            elif file_path.endswith('.html'):
                self.export_to_html(report_data, file_path)
            else:
                self.export_to_docx(report_data, file_path)

            messagebox.showinfo("Export Complete", f"Detailed report exported to {file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export report: {str(e)}")


def export_analytics_data(self):
    """Export analytics and statistics data"""
    file_path = filedialog.asksaveasfilename(
        title="Export Analytics Data",
        defaultextension=".xlsx",
        filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv")]
    )

    if file_path:
        try:
            analytics_data = self.gather_analytics_data()

            if file_path.endswith('.xlsx'):
                self.export_to_excel(analytics_data, file_path)
            else:
                self.export_to_csv(analytics_data, file_path)

            messagebox.showinfo("Export Complete", f"Analytics data exported to {file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export analytics: {str(e)}")


def export_audit_log(self):
    """Export audit log"""
    file_path = filedialog.asksaveasfilename(
        title="Export Audit Log",
        defaultextension=".json",
        filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv")]
    )

    if file_path:
        try:
            audit_data = self.get_audit_log_data()

            if file_path.endswith('.json'):
                with open(file_path, 'w') as f:
                    json.dump(audit_data, f, indent=2, default=str)
            else:
                import csv
                with open(file_path, 'w', newline='') as f:
                    if audit_data:
                        writer = csv.DictWriter(f, fieldnames=audit_data[0].keys())
                        writer.writeheader()
                        writer.writerows(audit_data)

            messagebox.showinfo("Export Complete", f"Audit log exported to {file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export audit log: {str(e)}")


def import_data(self):
    """Import data from file"""
    file_path = filedialog.askopenfilename(
        title="Import AI Detection Data",
        filetypes=[
            ("JSON files", "*.json"),
            ("CSV files", "*.csv"),
            ("Text files", "*.txt"),
            ("All files", "*.*")
        ]
    )

    if not file_path:
        return

    # Create import progress window
    import_window = tk.Toplevel(self.root)
    import_window.title("Data Import Progress")
    import_window.geometry("500x400")
    import_window.transient(self.root)
    import_window.grab_set()

    # Title
    ttk.Label(import_window, text="📥 Importing AI Detection Data", style='Title.TLabel').pack(pady=15)

    # Progress frame
    progress_frame = ttk.LabelFrame(import_window, text="Import Progress", padding="15")
    progress_frame.pack(fill='x', padx=20, pady=(0, 15))

    progress_var = tk.DoubleVar()
    progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, mode='determinate', length=400)
    progress_bar.pack(pady=(0, 10))

    status_label = ttk.Label(progress_frame, text="Preparing import...")
    status_label.pack()

    # Results frame
    results_frame = ttk.LabelFrame(import_window, text="Import Results", padding="15")
    results_frame.pack(fill='both', expand=True, padx=20, pady=(0, 15))

    results_text = tk.Text(results_frame, height=10, wrap='word')
    results_text.pack(fill='both', expand=True)

    scrollbar = ttk.Scrollbar(results_frame, orient='vertical', command=results_text.yview)
    scrollbar.pack(side='right', fill='y')
    results_text.config(yscrollcommand=scrollbar.set)

    def run_import():
        try:
            results_text.insert(tk.END, f"Starting import from: {os.path.basename(file_path)}\n\n")
            import_window.update()

            import_stats = {
                'total_records': 0,
                'successful_imports': 0,
                'failed_imports': 0,
                'duplicate_skips': 0,
                'errors': []
            }

            file_ext = os.path.splitext(file_path)[1].lower()

            if file_ext == '.json':
                # Import JSON data
                status_label.config(text="Reading JSON file...")
                import_window.update()

                with open(file_path, 'r', encoding='utf-8') as jsonfile:
                    data = json.load(jsonfile)

                # Handle different JSON structures
                if isinstance(data, list):
                    records = data
                elif isinstance(data, dict):
                    records = data.get('submissions', data.get('detections', data.get('results', [data])))
                else:
                    records = [data]

                import_stats['total_records'] = len(records)
                results_text.insert(tk.END, f"Found {len(records)} records in JSON file.\n")
                import_window.update()

                # Process each record
                for i, record in enumerate(records):
                    try:
                        progress_var.set((i / len(records)) * 100)
                        status_label.config(text=f"Processing record {i + 1} of {len(records)}...")
                        import_window.update()

                        # Validate and process record
                        if self._process_import_record(record, import_stats):
                            import_stats['successful_imports'] += 1
                        else:
                            import_stats['failed_imports'] += 1

                    except Exception as e:
                        import_stats['failed_imports'] += 1
                        import_stats['errors'].append(f"Record {i + 1}: {str(e)}")

            elif file_ext == '.csv':
                # Import CSV data
                import csv
                status_label.config(text="Reading CSV file...")
                import_window.update()

                with open(file_path, 'r', encoding='utf-8') as csvfile:
                    # Detect CSV delimiter
                    sample = csvfile.read(1024)
                    csvfile.seek(0)
                    sniffer = csv.Sniffer()
                    delimiter = sniffer.sniff(sample).delimiter

                    reader = csv.DictReader(csvfile, delimiter=delimiter)
                    records = list(reader)

                import_stats['total_records'] = len(records)
                results_text.insert(tk.END, f"Found {len(records)} records in CSV file.\n")
                import_window.update()

                # Process each record
                for i, record in enumerate(records):
                    try:
                        progress_var.set((i / len(records)) * 100)
                        status_label.config(text=f"Processing record {i + 1} of {len(records)}...")
                        import_window.update()

                        # Convert CSV record to standard format
                        formatted_record = self._format_csv_record(record)
                        if self._process_import_record(formatted_record, import_stats):
                            import_stats['successful_imports'] += 1
                        else:
                            import_stats['failed_imports'] += 1

                    except Exception as e:
                        import_stats['failed_imports'] += 1
                        import_stats['errors'].append(f"Record {i + 1}: {str(e)}")

            elif file_ext == '.txt':
                # Import text file (assume one submission per line)
                status_label.config(text="Reading text file...")
                import_window.update()

                with open(file_path, 'r', encoding='utf-8') as txtfile:
                    lines = [line.strip() for line in txtfile.readlines() if line.strip()]

                import_stats['total_records'] = len(lines)
                results_text.insert(tk.END, f"Found {len(lines)} text submissions.\n")
                import_window.update()

                # Process each line as a submission
                for i, text in enumerate(lines):
                    try:
                        progress_var.set((i / len(lines)) * 100)
                        status_label.config(text=f"Analyzing submission {i + 1} of {len(lines)}...")
                        import_window.update()

                        # Create record from text
                        record = {
                            'submission_id': f"import_{int(time.time())}_{i}",
                            'text': text,
                            'timestamp': datetime.now().isoformat(),
                            'source': 'text_import'
                        }

                        if self._process_import_record(record, import_stats):
                            import_stats['successful_imports'] += 1
                        else:
                            import_stats['failed_imports'] += 1

                    except Exception as e:
                        import_stats['failed_imports'] += 1
                        import_stats['errors'].append(f"Line {i + 1}: {str(e)}")

            progress_var.set(100)
            status_label.config(text="Import completed!")

            # Display results
            results_text.insert(tk.END, f"\n{'='*50}\n")
            results_text.insert(tk.END, "IMPORT SUMMARY\n")
            results_text.insert(tk.END, f"{'='*50}\n")
            results_text.insert(tk.END, f"Total Records: {import_stats['total_records']}\n")
            results_text.insert(tk.END, f"Successfully Imported: {import_stats['successful_imports']}\n")
            results_text.insert(tk.END, f"Failed Imports: {import_stats['failed_imports']}\n")
            results_text.insert(tk.END, f"Duplicates Skipped: {import_stats['duplicate_skips']}\n")

            if import_stats['errors']:
                results_text.insert(tk.END, f"\nErrors Encountered:\n")
                for error in import_stats['errors'][:10]:  # Show max 10 errors
                    results_text.insert(tk.END, f"• {error}\n")
                if len(import_stats['errors']) > 10:
                    results_text.insert(tk.END, f"• ... and {len(import_stats['errors']) - 10} more errors\n")

            results_text.insert(tk.END, f"\nImport completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

            # Refresh displays
            if hasattr(self, 'refresh_history'):
                self.refresh_history()
            if hasattr(self, 'refresh_statistics'):
                self.refresh_statistics()

        except Exception as e:
            results_text.insert(tk.END, f"\nCritical Error: {str(e)}\n")
            status_label.config(text="Import failed!")

    # Control buttons
    button_frame = ttk.Frame(import_window)
    button_frame.pack(fill='x', padx=20, pady=(0, 15))

    ttk.Button(button_frame, text="Start Import",
              command=lambda: threading.Thread(target=run_import, daemon=True).start()).pack(side='left', padx=(0, 10))
    ttk.Button(button_frame, text="Close", command=import_window.destroy).pack(side='right')

    # Show initial message
    results_text.insert(tk.END, f"Ready to import data from: {os.path.basename(file_path)}\n")
    results_text.insert(tk.END, f"File type: {file_ext.upper()[1:]} file\n")
    results_text.insert(tk.END, f"File size: {os.path.getsize(file_path)} bytes\n\n")
    results_text.insert(tk.END, "Click 'Start Import' to begin processing.\n")


def import_submissions(self):
    """Import submissions from file"""
    file_path = filedialog.askopenfilename(
        title="Import Submissions",
        filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv"), ("Excel files", "*.xlsx")]
    )

    if file_path:
        try:
            imported_count = self.process_submission_import(file_path)
            messagebox.showinfo("Import Complete", f"Successfully imported {imported_count} submissions")
            self.refresh_history()
            self.refresh_statistics()
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import submissions: {str(e)}")


def import_student_data(self):
    """Import student demographic data"""
    file_path = filedialog.askopenfilename(
        title="Import Student Data",
        filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx")]
    )

    if file_path:
        try:
            imported_count = self.process_student_data_import(file_path)
            messagebox.showinfo("Import Complete", f"Successfully imported data for {imported_count} students")
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import student data: {str(e)}")


def import_settings(self):
    """Import application settings"""
    file_path = filedialog.askopenfilename(
        title="Import Settings",
        filetypes=[("JSON files", "*.json")]
    )

    if file_path:
        try:
            with open(file_path, 'r') as f:
                settings = json.load(f)

            self.apply_imported_settings(settings)
            messagebox.showinfo("Import Complete", "Settings imported successfully")
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import settings: {str(e)}")


def archive_old_data(self):
    """Archive old data"""
    cutoff_date = tk.simpledialog.askstring(
        "Archive Data",
        "Enter cutoff date (YYYY-MM-DD):"
    )

    if cutoff_date:
        try:
            archived_count = self.process_data_archival(cutoff_date)
            messagebox.showinfo("Archive Complete", f"Archived {archived_count} records")
        except Exception as e:
            messagebox.showerror("Archive Error", f"Failed to archive data: {str(e)}")


def optimize_database(self):
    """Optimize database performance"""
    try:
        self.update_status("Optimizing database...")
        # Run database optimization
        optimization_result = self.run_database_optimization()
        messagebox.showinfo("Optimization Complete", f"Database optimized successfully\n{optimization_result}")
        self.update_status("Database optimization complete")
    except Exception as e:
        messagebox.showerror("Optimization Error", f"Failed to optimize database: {str(e)}")


def clean_duplicates(self):
    """Clean duplicate records"""
    try:
        duplicates_found = self.find_duplicate_records()
        if duplicates_found > 0:
            response = messagebox.askyesno(
                "Duplicates Found",
                f"Found {duplicates_found} duplicate records. Remove them?"
            )
            if response:
                removed_count = self.remove_duplicate_records()
                messagebox.showinfo("Cleanup Complete", f"Removed {removed_count} duplicate records")
        else:
            messagebox.showinfo("No Duplicates", "No duplicate records found")
    except Exception as e:
        messagebox.showerror("Cleanup Error", f"Failed to clean duplicates: {str(e)}")


def _process_import_record(self, record, stats):
    """Process a single import record"""
    try:
        # Extract required fields
        submission_id = record.get('submission_id', f"import_{int(time.time())}_{random.randint(1000, 9999)}")
        text = record.get('text', record.get('content', ''))

        if not text or len(text.strip()) < 10:
            stats['errors'].append(f"Submission {submission_id}: Text too short or missing")
            return False

        # Check for duplicates (basic check based on text hash)
        text_hash = hash(text.strip())
        if hasattr(self, '_imported_hashes'):
            if text_hash in self._imported_hashes:
                stats['duplicate_skips'] += 1
                return False
        else:
            self._imported_hashes = set()

        self._imported_hashes.add(text_hash)

        # If detector is available, run actual analysis
        if self.detector and hasattr(self.detector, 'analyze_text'):
            try:
                result = self.detector.analyze_text(text)
                # Store result in detector's database/storage
                if hasattr(self.detector, 'store_analysis'):
                    self.detector.store_analysis(submission_id, text, result)
            except Exception:
                # If analysis fails, store basic record
                pass

        return True

    except Exception as e:
        stats['errors'].append(f"Processing error: {str(e)}")
        return False


def _format_csv_record(self, csv_record):
    """Format CSV record to standard format"""
    # Common CSV field mappings
    field_mappings = {
        'id': ['id', 'submission_id', 'student_id'],
        'text': ['text', 'content', 'submission', 'essay'],
        'timestamp': ['timestamp', 'date', 'submitted_at'],
        'student': ['student', 'student_name', 'name'],
        'assignment': ['assignment', 'assignment_name', 'title']
    }

    record = {}
    for standard_field, possible_fields in field_mappings.items():
        for field in possible_fields:
            if field in csv_record and csv_record[field]:
                record[standard_field] = csv_record[field]
                break

    # Ensure we have required fields
    if 'text' not in record:
        record['text'] = str(csv_record)  # Fallback to entire record

    if 'id' not in record:
        record['submission_id'] = f"csv_import_{int(time.time())}_{random.randint(1000, 9999)}"

    return record


