import json
import os
import threading
import time
import random
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext

from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH, sqlite3
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth

try:
    from education_system.systems.university.infrastructure.ai.ai_detector.detector import AIDetector
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

from education_system.systems.university.infrastructure.i18n import get_text, _

def create_batch_processing_section(self, parent):
    """Create batch processing section"""
    batch_frame = ttk.LabelFrame(parent, text="Batch Processing", padding=15)
    batch_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Label(batch_frame, text="Process multiple files at once").pack(anchor='w')

    batch_buttons = ttk.Frame(batch_frame)
    batch_buttons.pack(fill='x', pady=(10, 0))

    ttk.Button(batch_buttons, text="📁 Select Files", command=self.select_batch_files).pack(side='left', padx=(0, 10))
    ttk.Button(batch_buttons, text="⚡ Process Batch", command=self.process_batch).pack(side='left')


def create_batch_processing_view(self, parent):
    """Create batch processing management view"""
    batch_frame = ttk.Frame(parent)
    batch_frame.pack(fill="both", expand=True)

    # Main card
    batch_card = ttk.Frame(batch_frame, style='Card.TFrame')
    batch_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(batch_card, text="Batch Processing", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Folder Analysis Section
    folder_frame = ttk.LabelFrame(batch_card, text="Folder Analysis", padding=15)
    folder_frame.pack(fill='x', padx=15, pady=(0, 15))

    folder_input = ttk.Frame(folder_frame)
    folder_input.pack(fill='x', pady=(0, 10))
    ttk.Label(folder_input, text="Selected Folder:").pack(side='left')
    self.batch_folder_var = tk.StringVar(value="No folder selected")
    ttk.Label(folder_input, textvariable=self.batch_folder_var,
             foreground=self.colors['text_secondary']).pack(side='left', padx=(5, 10))
    ttk.Button(folder_input, text="Browse...",
              command=self._select_batch_folder).pack(side='left')

    ttk.Button(folder_frame, text="Analyze Folder",
              command=self.batch_analyze_folder).pack(anchor='w')

    # LMS Export Section
    lms_frame = ttk.LabelFrame(batch_card, text="LMS Export Analysis", padding=15)
    lms_frame.pack(fill='x', padx=15, pady=(0, 15))

    lms_input = ttk.Frame(lms_frame)
    lms_input.pack(fill='x', pady=(0, 10))
    ttk.Label(lms_input, text="LMS Type:").pack(side='left')
    self.lms_type_var = tk.StringVar(value="Canvas")
    lms_combo = ttk.Combobox(lms_input, textvariable=self.lms_type_var,
                            values=["Canvas", "Blackboard", "Moodle"], width=15, state='readonly')
    lms_combo.pack(side='left', padx=(5, 15))

    ttk.Label(lms_input, text="Export File:").pack(side='left')
    self.lms_file_var = tk.StringVar(value="No file selected")
    ttk.Label(lms_input, textvariable=self.lms_file_var,
             foreground=self.colors['text_secondary']).pack(side='left', padx=(5, 10))
    ttk.Button(lms_input, text="Browse...",
              command=self._select_lms_file).pack(side='left')

    ttk.Button(lms_frame, text="Process LMS Export",
              command=self.batch_analyze_lms_export).pack(anchor='w')

    # Scheduled Jobs Section
    schedule_frame = ttk.LabelFrame(batch_card, text="Scheduled Batch Jobs", padding=15)
    schedule_frame.pack(fill='x', padx=15, pady=(0, 15))

    schedule_input = ttk.Frame(schedule_frame)
    schedule_input.pack(fill='x', pady=(0, 10))
    ttk.Label(schedule_input, text="Schedule Time:").pack(side='left')
    self.schedule_hour_var = tk.StringVar(value="02")
    ttk.Spinbox(schedule_input, textvariable=self.schedule_hour_var,
               from_=0, to=23, width=5, format="%02.0f").pack(side='left', padx=(5, 0))
    ttk.Label(schedule_input, text=":").pack(side='left')
    self.schedule_min_var = tk.StringVar(value="00")
    ttk.Spinbox(schedule_input, textvariable=self.schedule_min_var,
               from_=0, to=59, width=5, format="%02.0f").pack(side='left', padx=(0, 10))
    ttk.Button(schedule_input, text="Schedule Job",
              command=self.schedule_batch_job).pack(side='left')

    # Job Status Section
    status_frame = ttk.LabelFrame(batch_card, text="Batch Job Status", padding=15)
    status_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    status_controls = ttk.Frame(status_frame)
    status_controls.pack(fill='x', pady=(0, 10))
    ttk.Button(status_controls, text="Refresh Status",
              command=self.view_batch_job_status).pack(side='left', padx=(0, 10))
    ttk.Button(status_controls, text="Cancel Selected Job",
              command=self.cancel_batch_job).pack(side='left', padx=(0, 10))
    ttk.Button(status_controls, text="Retry Failed",
              command=self.retry_failed_analyses).pack(side='left')

    # Job status treeview
    columns = ('id', 'type', 'status', 'progress', 'started', 'files')
    self.batch_job_tree = ttk.Treeview(status_frame, columns=columns, show='headings', height=6)
    self.batch_job_tree.heading('id', text='Job ID')
    self.batch_job_tree.heading('type', text='Type')
    self.batch_job_tree.heading('status', text='Status')
    self.batch_job_tree.heading('progress', text='Progress')
    self.batch_job_tree.heading('started', text='Started')
    self.batch_job_tree.heading('files', text='Files')

    self.batch_job_tree.column('id', width=60)
    self.batch_job_tree.column('type', width=100)
    self.batch_job_tree.column('status', width=80)
    self.batch_job_tree.column('progress', width=80)
    self.batch_job_tree.column('started', width=120)
    self.batch_job_tree.column('files', width=60)

    batch_scroll = ttk.Scrollbar(status_frame, orient='vertical', command=self.batch_job_tree.yview)
    self.batch_job_tree.configure(yscrollcommand=batch_scroll.set)
    self.batch_job_tree.pack(side='left', fill='both', expand=True)
    batch_scroll.pack(side='right', fill='y')


def select_batch_files(self):
    """Select files for batch processing"""
    file_paths = filedialog.askopenfilenames(
        title="Select files for batch processing",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
    )

    if file_paths:
        self.batch_files = file_paths
        messagebox.showinfo("Files Selected", f"Selected {len(file_paths)} files for processing")
    else:
        self.batch_files = []


def process_batch(self):
    """Process batch files"""
    if not hasattr(self, 'batch_files') or not self.batch_files:
        messagebox.showwarning("Warning", "Please select files first")
        return

    # Create batch processing window
    batch_window = tk.Toplevel(self.root)
    batch_window.title("Batch Processing")
    batch_window.geometry("600x400")
    batch_window.configure(bg=self.colors['bg_primary'])

    ttk.Label(batch_window, text="Batch Processing", style='Title.TLabel').pack(pady=20)

    # Progress
    progress_frame = ttk.Frame(batch_window)
    progress_frame.pack(fill='x', padx=20, pady=20)

    progress_label = ttk.Label(progress_frame, text="Processing files...")
    progress_label.pack()

    progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=400)
    progress_bar.pack(pady=10)

    # Results area
    results_frame = scrolledtext.ScrolledText(batch_window, height=15,
                                            bg=self.colors['bg_secondary'],
                                            fg=self.colors['text_primary'])
    results_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))

    def process_files():
        total_files = len(self.batch_files)
        results = []

        for i, file_path in enumerate(self.batch_files):
            try:
                # Update progress
                progress = (i + 1) / total_files * 100
                progress_bar['value'] = progress
                progress_label.config(text=f"Processing {i+1}/{total_files}: {file_path.split('/')[-1]}")
                batch_window.update()

                # Read file
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()

                # Analyze
                result = self.detector.analyze_text_enhanced(
                    text=text,
                    title=file_path.split('/')[-1].split('.')[0],
                    student_id=f"BATCH_{i+1}"
                )

                # Store result
                results.append({
                    'file': file_path.split('/')[-1],
                    'ai_score': result.get('ai_score', 0),
                    'is_ai_generated': result.get('is_ai_generated', False)
                })

                # Update results display
                result_text = f"✓ {file_path.split('/')[-1]}: {result.get('ai_score', 0):.1%} AI probability\n"
                results_frame.insert(tk.END, result_text)
                results_frame.see(tk.END)

            except Exception as e:
                error_text = f"✗ {file_path.split('/')[-1]}: Error - {str(e)}\n"
                results_frame.insert(tk.END, error_text)
                results_frame.see(tk.END)

        # Complete
        progress_label.config(text="Batch processing complete!")
        progress_bar['value'] = 100

        # Show summary
        summary_text = f"\n--- SUMMARY ---\nProcessed {total_files} files\n"
        ai_generated_count = sum(1 for r in results if r['is_ai_generated'])
        summary_text += f"AI Generated: {ai_generated_count}\n"
        summary_text += f"Human Written: {total_files - ai_generated_count}\n"
        results_frame.insert(tk.END, summary_text)

    threading.Thread(target=process_files, daemon=True).start()


def _select_batch_folder(self):
    """Select folder for batch analysis"""
    folder = filedialog.askdirectory(title="Select Folder for Batch Analysis")
    if folder:
        self.batch_folder_var.set(folder)


def _select_lms_file(self):
    """Select LMS export file"""
    file_path = filedialog.askopenfilename(
        title="Select LMS Export File",
        filetypes=[("ZIP files", "*.zip"), ("CSV files", "*.csv"), ("All files", "*.*")]
    )
    if file_path:
        self.lms_file_var.set(os.path.basename(file_path))
        self._lms_file_path = file_path


def batch_analyze_folder(self):
    """Analyze all documents in a selected folder"""
    folder = self.batch_folder_var.get()
    if folder == "No folder selected":
        messagebox.showwarning("Warning", "Please select a folder first")
        return

    if not os.path.isdir(folder):
        messagebox.showerror("Error", "Selected folder does not exist")
        return

    try:
        # Get list of files
        supported_extensions = ['.txt', '.pdf', '.docx', '.doc']
        files = []
        for f in os.listdir(folder):
            if any(f.lower().endswith(ext) for ext in supported_extensions):
                files.append(os.path.join(folder, f))

        if not files:
            messagebox.showinfo("Info", "No supported files found in folder")
            return

        # Create batch job
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_batch_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT,
                status TEXT DEFAULT 'pending',
                total_files INTEGER,
                processed_files INTEGER DEFAULT 0,
                failed_files INTEGER DEFAULT 0,
                source_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')

        cursor.execute('''
            INSERT INTO ai_batch_jobs (job_type, total_files, source_path, status)
            VALUES (?, ?, ?, 'running')
        ''', ('folder_analysis', len(files), folder))

        job_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Start background processing
        def process_files():
            processed = 0
            failed = 0
            for file_path in files:
                try:
                    text = self._extract_text_from_file(file_path)
                    if text and hasattr(self.detector, 'analyze_text'):
                        self.detector.analyze_text(text)
                    processed += 1
                except Exception:
                    failed += 1

                # Update progress
                conn = sqlite3.connect(DEFAULT_DB_PATH)
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE ai_batch_jobs
                    SET processed_files = ?, failed_files = ?
                    WHERE id = ?
                ''', (processed, failed, job_id))
                conn.commit()
                conn.close()

            # Mark complete
            conn = sqlite3.connect(DEFAULT_DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE ai_batch_jobs
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (job_id,))
            conn.commit()
            conn.close()

        thread = threading.Thread(target=process_files, daemon=True)
        thread.start()

        messagebox.showinfo("Success", f"Batch job started for {len(files)} files.\nJob ID: {job_id}")
        self.view_batch_job_status()
        self.update_status(f"Batch job {job_id} started")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to start batch analysis: {str(e)}")


def batch_analyze_lms_export(self):
    """Process exported assignments from Canvas/Blackboard/Moodle"""
    if not hasattr(self, '_lms_file_path'):
        messagebox.showwarning("Warning", "Please select an LMS export file first")
        return

    lms_type = self.lms_type_var.get()
    file_path = self._lms_file_path

    if not os.path.exists(file_path):
        messagebox.showerror("Error", "Selected file does not exist")
        return

    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_batch_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT,
                status TEXT DEFAULT 'pending',
                total_files INTEGER,
                processed_files INTEGER DEFAULT 0,
                failed_files INTEGER DEFAULT 0,
                source_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')

        cursor.execute('''
            INSERT INTO ai_batch_jobs (job_type, total_files, source_path, status)
            VALUES (?, ?, ?, 'queued')
        ''', (f'lms_{lms_type.lower()}', 0, file_path))

        job_id = cursor.lastrowid
        conn.commit()
        conn.close()

        messagebox.showinfo("Success",
                          f"LMS export queued for processing.\n\n"
                          f"LMS Type: {lms_type}\nJob ID: {job_id}")
        self.view_batch_job_status()
        self.update_status(f"LMS batch job {job_id} queued")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to queue LMS export: {str(e)}")


def schedule_batch_job(self):
    """Schedule batch analysis for off-peak hours"""
    try:
        hour = int(self.schedule_hour_var.get())
        minute = int(self.schedule_min_var.get())

        folder = self.batch_folder_var.get()
        if folder == "No folder selected":
            messagebox.showwarning("Warning", "Please select a folder first")
            return

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_scheduled_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT,
                source_path TEXT,
                scheduled_hour INTEGER,
                scheduled_minute INTEGER,
                status TEXT DEFAULT 'scheduled',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                next_run TIMESTAMP
            )
        ''')

        cursor.execute('''
            INSERT INTO ai_scheduled_jobs (job_type, source_path, scheduled_hour, scheduled_minute)
            VALUES (?, ?, ?, ?)
        ''', ('folder_analysis', folder, hour, minute))

        job_id = cursor.lastrowid
        conn.commit()
        conn.close()

        messagebox.showinfo("Success",
                          f"Batch job scheduled.\n\n"
                          f"Time: {hour:02d}:{minute:02d}\nJob ID: {job_id}")
        self.update_status(f"Batch job scheduled for {hour:02d}:{minute:02d}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to schedule batch job: {str(e)}")


def view_batch_job_status(self):
    """Monitor progress of running batch jobs"""
    try:
        for item in self.batch_job_tree.get_children():
            self.batch_job_tree.delete(item)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='ai_batch_jobs'
        ''')

        if not cursor.fetchone():
            conn.close()
            return

        cursor.execute('''
            SELECT id, job_type, status,
                   CASE WHEN total_files > 0
                        THEN CAST(processed_files AS FLOAT) / total_files * 100
                        ELSE 0 END as progress,
                   datetime(created_at) as started,
                   total_files
            FROM ai_batch_jobs
            ORDER BY created_at DESC
            LIMIT 20
        ''')

        jobs = cursor.fetchall()
        conn.close()

        for job in jobs:
            job_id, job_type, status, progress, started, files = job
            progress_str = f"{progress:.0f}%"
            self.batch_job_tree.insert('', 'end',
                                      values=(job_id, job_type, status, progress_str, started, files))

        self.update_status(f"Loaded {len(jobs)} batch jobs")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load job status: {str(e)}")


def cancel_batch_job(self):
    """Cancel a running or queued batch job"""
    selected = self.batch_job_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select a job to cancel")
        return

    job_id = self.batch_job_tree.item(selected[0])['values'][0]
    job_status = self.batch_job_tree.item(selected[0])['values'][2]

    if job_status == 'completed':
        messagebox.showinfo("Info", "This job has already completed")
        return

    if not messagebox.askyesno("Confirm", f"Cancel batch job {job_id}?"):
        return

    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE ai_batch_jobs SET status = 'cancelled' WHERE id = ?
        ''', (job_id,))
        conn.commit()
        conn.close()

        self.view_batch_job_status()
        messagebox.showinfo("Success", f"Job {job_id} cancelled")
        self.update_status(f"Batch job {job_id} cancelled")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to cancel job: {str(e)}")


def retry_failed_analyses(self):
    """Retry all failed analyses from a batch"""
    selected = self.batch_job_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select a batch job first")
        return

    job_id = self.batch_job_tree.item(selected[0])['values'][0]

    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('SELECT failed_files, source_path FROM ai_batch_jobs WHERE id = ?', (job_id,))
        result = cursor.fetchone()

        if not result or result[0] == 0:
            messagebox.showinfo("Info", "No failed analyses to retry")
            conn.close()
            return

        # Reset status to retry
        cursor.execute('''
            UPDATE ai_batch_jobs
            SET status = 'retrying', failed_files = 0
            WHERE id = ?
        ''', (job_id,))

        conn.commit()
        conn.close()

        messagebox.showinfo("Success", f"Retrying {result[0]} failed analyses from job {job_id}")
        self.view_batch_job_status()
        self.update_status(f"Retrying failed analyses for job {job_id}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to retry analyses: {str(e)}")


def _extract_text_from_file(self, file_path):
    """Extract text from various file formats"""
    file_ext = os.path.splitext(file_path)[1].lower()

    # Try textract first if available (supports many formats)
    if TEXTRACT_AVAILABLE:
        try:
            content = textract.process(file_path).decode('utf-8')
            return content
        except Exception as e:
            print(f"Textract extraction failed: {e}, trying format-specific extractors...")

    # Format-specific extraction
    if file_ext == '.txt':
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    elif file_ext == '.pdf':
        if PYPDF2_AVAILABLE:
            try:
                reader = PdfReader(file_path)
                text = []
                for page in reader.pages:
                    text.append(page.extract_text())
                return '\n'.join(text)
            except Exception as e:
                raise Exception(f"Failed to extract PDF text: {e}")
        else:
            raise Exception("PDF support not available. Install pypdf: pip install pypdf")

    elif file_ext in ['.docx', '.doc']:
        if PYTHON_DOCX_AVAILABLE:
            try:
                doc = docx.Document(file_path)
                text = []
                for paragraph in doc.paragraphs:
                    text.append(paragraph.text)
                return '\n'.join(text)
            except Exception as e:
                raise Exception(f"Failed to extract DOCX text: {e}")
        else:
            raise Exception("DOCX support not available. Install python-docx: pip install python-docx")

    else:
        # Try reading as plain text as fallback
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            raise Exception(f"Unsupported file format: {file_ext}")


