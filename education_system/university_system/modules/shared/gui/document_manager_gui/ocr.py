import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime
import os
import csv
import logging

logger = logging.getLogger(__name__)

try:
    from education_system.university_system.infrastructure.database.db import get_connection
except ImportError:
    from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")


class OCRManager:
    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def ocr_integration_menu(self):
        """OCR integration menu in GUI"""
        dialog = tk.Toplevel(self.root)
        dialog.title("OCR Integration")
        dialog.geometry("600x450")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="OCR Integration", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        ocr_options = [
            ("Extract Text from Document", self.extract_text_from_document_gui),
            ("Batch OCR Processing", self.batch_ocr_processing_gui),
            ("OCR Settings", self.ocr_settings_gui),
            ("🏠 Return to Main Menu", self.gui.return_to_main_menu)
        ]

        for text, command in ocr_options:
            ttk.Button(main_frame, text=text, command=command, width=25).pack(pady=5)

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=20)

    def extract_text_from_document_gui(self):
        """Extract text from document with GUI"""
        doc_id = simpledialog.askstring("OCR", "Enter document ID:")
        if not doc_id:
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT sd.file_path, sd.original_filename, dt.type_name, s.first_name, s.last_name
            FROM documents sd
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            JOIN students s ON sd.owner_id = s.student_id
            WHERE sd.source_type = 'student' AND sd.document_id = ?
            ''', (doc_id,))

            doc = cursor.fetchone()

            if not doc:
                messagebox.showerror("Error", "Document not found")
                conn.close()
                return

            file_path, filename, doc_type, first_name, last_name = doc

            # Show processing dialog
            progress_dialog = tk.Toplevel(self.root)
            progress_dialog.title("OCR Processing")
            progress_dialog.geometry("450x150")
            progress_dialog.transient(self.root)

            ttk.Label(progress_dialog, text="Processing document with OCR...").pack(pady=20)
            progress_bar = ttk.Progressbar(progress_dialog, mode='indeterminate')
            progress_bar.pack(pady=10)
            progress_bar.start()

            # Simulate OCR processing
            self.root.after(3000, lambda: self.show_ocr_results(progress_dialog, doc_id, filename, doc_type, first_name, last_name))

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"OCR processing failed: {str(e)}")

    def show_ocr_results(self, progress_dialog, doc_id, filename, doc_type, first_name, last_name):
        """Show OCR results"""
        progress_dialog.destroy()

        # Create results window
        results_window = tk.Toplevel(self.root)
        results_window.title("OCR Results")
        results_window.geometry("850x700")

        main_frame = ttk.Frame(results_window, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="OCR Extraction Results", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Mock extracted text
        mock_text = f"""EXTRACTED TEXT FROM {filename.upper()}

    Document Type: {doc_type}
    Student Name: {first_name} {last_name}
    Document ID: {doc_id}

    [OCR Placeholder Results]
    Name: {first_name} {last_name}
    Document Type: {doc_type}
    Issue Date: 2024-01-15
    Expiry Date: 2029-01-15
    Document Number: ABC123456789

    Confidence: 95%"""

        text_widget = tk.Text(main_frame, wrap='word', height=20, width=70)
        text_widget.insert('1.0', mock_text)
        text_widget.config(state='disabled')
        text_widget.pack(fill='both', expand=True)

        # Save button
        def save_ocr_results():
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                CREATE TABLE IF NOT EXISTS ocr_results (
                    ocr_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER,
                    extracted_text TEXT,
                    confidence_score REAL,
                    processing_date TEXT,
                    FOREIGN KEY (document_id) REFERENCES documents (document_id)
                )
                ''')

                cursor.execute('''
                INSERT INTO ocr_results (document_id, extracted_text, confidence_score, processing_date)
                VALUES (?, ?, ?, ?)
                ''', (doc_id, mock_text, 0.95, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "OCR results saved to database")
                results_window.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to save OCR results: {str(e)}")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text="Save Results", command=save_ocr_results).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Close", command=results_window.destroy).pack(side='right')

    def batch_ocr_processing_gui(self):
        """Process multiple documents with OCR"""
        try:
            # Get selected documents
            selected = self.gui.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select documents for OCR processing")
                return

            # Create progress dialog
            progress_dialog = tk.Toplevel(self.root)
            progress_dialog.title("Batch OCR Processing")
            progress_dialog.geometry("700x450")
            progress_dialog.transient(self.root)

            main_frame = ttk.Frame(progress_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"Processing {len(selected)} document(s) with OCR",
                     font=('Arial', 12, 'bold')).pack(pady=(0, 20))

            # Progress bar
            progress = ttk.Progressbar(main_frame, length=400, mode='determinate')
            progress.pack(pady=10)

            # Status label
            status_label = ttk.Label(main_frame, text="Initializing...")
            status_label.pack(pady=10)

            # Results text
            results_text = tk.Text(main_frame, height=10, width=50)
            results_text.pack(fill='both', expand=True, pady=10)

            def process_documents():
                total = len(selected)
                for i, item in enumerate(selected):
                    doc_id = self.gui.tree.item(item)['values'][0]
                    doc_name = self.gui.tree.item(item)['values'][3]

                    status_label.config(text=f"Processing {doc_name}...")
                    progress['value'] = (i + 1) / total * 100

                    results_text.insert('end', f"✓ Processed: {doc_name}\n")
                    results_text.see('end')
                    progress_dialog.update()

                status_label.config(text="OCR Processing Complete!")
                ttk.Button(main_frame, text="Close", command=progress_dialog.destroy).pack(pady=10)

            # Start processing
            progress_dialog.after(100, process_documents)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process OCR batch: {e}")

    def extract_text_from_document(self):
        """
        Extract text from document using OCR
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("OCR Text Extraction")
            dialog.geometry("1000x750")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="OCR Text Extraction",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # File selection
            file_frame = ttk.LabelFrame(main_frame, text="Select Document", padding=10)
            file_frame.pack(fill='x', pady=(0, 15))

            file_path_var = tk.StringVar()
            ttk.Label(file_frame, text="File:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            ttk.Entry(file_frame, textvariable=file_path_var, width=50, state='readonly').grid(row=0, column=1, padx=5, pady=5, sticky='ew')

            def browse_file():
                file_path = filedialog.askopenfilename(
                    title="Select Document for OCR",
                    filetypes=[
                        ("Image files", "*.jpg *.jpeg *.png *.tiff *.bmp"),
                        ("PDF files", "*.pdf"),
                        ("All files", "*.*")
                    ]
                )
                if file_path:
                    file_path_var.set(file_path)

            ttk.Button(file_frame, text="Browse...", command=browse_file).grid(row=0, column=2, padx=5, pady=5)

            file_frame.grid_columnconfigure(1, weight=1)

            # OCR options
            options_frame = ttk.LabelFrame(main_frame, text="OCR Options", padding=10)
            options_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(options_frame, text="Language:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            language = ttk.Combobox(options_frame, values=['English', 'Spanish', 'French', 'German', 'Chinese'], width=20, state='readonly')
            language.set('English')
            language.grid(row=0, column=1, sticky='w', padx=5, pady=5)

            ttk.Label(options_frame, text="Page (PDF only):").grid(row=1, column=0, sticky='w', padx=5, pady=5)
            page_number = tk.StringVar(value="1")
            ttk.Spinbox(options_frame, from_=1, to=999, textvariable=page_number, width=10).grid(row=1, column=1, sticky='w', padx=5, pady=5)

            enhance_quality = tk.BooleanVar(value=True)
            ttk.Checkbutton(options_frame, text="Enhance image quality before OCR", variable=enhance_quality).grid(row=2, column=0, columnspan=2, sticky='w', padx=5, pady=3)

            # Extracted text display
            text_frame = ttk.LabelFrame(main_frame, text="Extracted Text", padding=10)
            text_frame.pack(fill='both', expand=True, pady=(0, 15))

            text_widget = tk.Text(text_frame, wrap=tk.WORD, font=('Arial', 10))
            text_widget.pack(side='left', fill='both', expand=True)

            text_scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=text_widget.yview)
            text_widget.configure(yscrollcommand=text_scrollbar.set)
            text_scrollbar.pack(side='right', fill='y')

            # Status label
            status_label = ttk.Label(main_frame, text="", font=('Arial', 9))
            status_label.pack(pady=5)

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x')

            def extract_text():
                file_path = file_path_var.get()
                if not file_path:
                    messagebox.showerror("Error", "Please select a file first")
                    return

                status_label.config(text="Processing... This may take a moment.", foreground='blue')
                dialog.update()

                try:
                    # Simulate OCR processing (in production, use pytesseract or similar)
                    import time
                    time.sleep(1)  # Simulate processing time

                    # Mock extracted text
                    extracted_text = f"""OCR EXTRACTED TEXT
File: {os.path.basename(file_path)}
Language: {language.get()}
Page: {page_number.get()}

[In production, this would contain the actual OCR-extracted text from the document]

Sample extracted content:
This is a sample document that has been processed using Optical Character Recognition (OCR).
The system can extract text from images and PDF files to make them searchable and editable.

Features:
- Multi-language support
- Image enhancement
- Page-by-page processing for PDFs
- High accuracy text recognition

Confidence Score: 95.2%
Processing Time: 1.23 seconds
"""

                    text_widget.delete('1.0', tk.END)
                    text_widget.insert('1.0', extracted_text)

                    status_label.config(text="✓ Text extraction completed successfully", foreground='green')

                    # Log the OCR operation
                    self.gui.log_event('ocr', 'document', None, {
                        'file': os.path.basename(file_path),
                        'language': language.get(),
                        'page': page_number.get()
                    })

                except Exception as e:
                    status_label.config(text=f"✗ Extraction failed: {str(e)}", foreground='red')
                    messagebox.showerror("Error", f"OCR extraction failed: {e}")

            def save_text():
                text_content = text_widget.get('1.0', tk.END).strip()
                if not text_content:
                    messagebox.showwarning("Warning", "No text to save")
                    return

                file_path = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                    initialfile=f"ocr_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                )

                if file_path:
                    try:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(text_content)
                        messagebox.showinfo("Success", f"Text saved to:\n{file_path}")
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to save text: {e}")

            ttk.Button(action_frame, text="Extract Text", command=extract_text).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Save Text", command=save_text).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Clear", command=lambda: text_widget.delete('1.0', tk.END)).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open OCR extraction: {e}")

    def ocr_settings(self):
        """
        Configure OCR settings
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("OCR Settings")
            dialog.geometry("700x650")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="OCR Configuration",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # OCR Engine
            engine_frame = ttk.LabelFrame(main_frame, text="OCR Engine", padding=15)
            engine_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(engine_frame, text="OCR Engine:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            ocr_engine = ttk.Combobox(engine_frame, values=['Tesseract', 'Google Cloud Vision', 'AWS Textract', 'Azure Computer Vision'],
                                     width=30, state='readonly')
            ocr_engine.set('Tesseract')
            ocr_engine.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

            engine_frame.grid_columnconfigure(1, weight=1)

            # Default languages
            lang_frame = ttk.LabelFrame(main_frame, text="Default Languages", padding=15)
            lang_frame.pack(fill='x', pady=(0, 15))

            lang_english = tk.BooleanVar(value=True)
            lang_spanish = tk.BooleanVar(value=False)
            lang_french = tk.BooleanVar(value=False)
            lang_german = tk.BooleanVar(value=False)
            lang_chinese = tk.BooleanVar(value=False)

            ttk.Checkbutton(lang_frame, text="English", variable=lang_english).pack(anchor='w', pady=3)
            ttk.Checkbutton(lang_frame, text="Spanish", variable=lang_spanish).pack(anchor='w', pady=3)
            ttk.Checkbutton(lang_frame, text="French", variable=lang_french).pack(anchor='w', pady=3)
            ttk.Checkbutton(lang_frame, text="German", variable=lang_german).pack(anchor='w', pady=3)
            ttk.Checkbutton(lang_frame, text="Chinese", variable=lang_chinese).pack(anchor='w', pady=3)

            # Processing options
            processing_frame = ttk.LabelFrame(main_frame, text="Processing Options", padding=15)
            processing_frame.pack(fill='x', pady=(0, 15))

            auto_enhance = tk.BooleanVar(value=True)
            auto_rotate = tk.BooleanVar(value=True)
            remove_noise = tk.BooleanVar(value=True)
            auto_deskew = tk.BooleanVar(value=False)

            ttk.Checkbutton(processing_frame, text="Auto-enhance image quality", variable=auto_enhance).pack(anchor='w', pady=3)
            ttk.Checkbutton(processing_frame, text="Auto-rotate pages", variable=auto_rotate).pack(anchor='w', pady=3)
            ttk.Checkbutton(processing_frame, text="Remove background noise", variable=remove_noise).pack(anchor='w', pady=3)
            ttk.Checkbutton(processing_frame, text="Auto-deskew text", variable=auto_deskew).pack(anchor='w', pady=3)

            # Performance settings
            perf_frame = ttk.LabelFrame(main_frame, text="Performance", padding=15)
            perf_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(perf_frame, text="Concurrent OCR jobs:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            concurrent_jobs = tk.StringVar(value="3")
            ttk.Spinbox(perf_frame, from_=1, to=10, textvariable=concurrent_jobs, width=10).grid(row=0, column=1, sticky='w', padx=5, pady=5)

            ttk.Label(perf_frame, text="Timeout (seconds):").grid(row=1, column=0, sticky='w', padx=5, pady=5)
            timeout = tk.StringVar(value="120")
            ttk.Spinbox(perf_frame, from_=30, to=600, increment=30, textvariable=timeout, width=10).grid(row=1, column=1, sticky='w', padx=5, pady=5)

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x', pady=(15, 0))

            def save_ocr_settings():
                try:
                    settings = {
                        'engine': ocr_engine.get(),
                        'languages': {
                            'english': lang_english.get(),
                            'spanish': lang_spanish.get(),
                            'french': lang_french.get(),
                            'german': lang_german.get(),
                            'chinese': lang_chinese.get()
                        },
                        'processing': {
                            'auto_enhance': auto_enhance.get(),
                            'auto_rotate': auto_rotate.get(),
                            'remove_noise': remove_noise.get(),
                            'auto_deskew': auto_deskew.get()
                        },
                        'performance': {
                            'concurrent_jobs': int(concurrent_jobs.get()),
                            'timeout': int(timeout.get())
                        }
                    }

                    self.gui.log_event('update', 'ocr_settings', None, settings)

                    messagebox.showinfo("Success", "OCR settings saved successfully")
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save settings: {e}")

            ttk.Button(action_frame, text="Save Settings", command=save_ocr_settings).pack(side='right', padx=5)
            ttk.Button(action_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open OCR settings: {e}")

    def batch_ocr_processing(self):
        """
        Batch OCR processing for multiple documents
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Batch OCR Processing")
            dialog.geometry("1000x750")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Batch OCR Processing",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # File selection
            files_frame = ttk.LabelFrame(main_frame, text="Files to Process", padding=10)
            files_frame.pack(fill='both', expand=True, pady=(0, 15))

            files_listbox = tk.Listbox(files_frame, height=10, font=('Arial', 10))
            files_listbox.pack(side='left', fill='both', expand=True)

            files_scrollbar = ttk.Scrollbar(files_frame, orient='vertical', command=files_listbox.yview)
            files_listbox.configure(yscrollcommand=files_scrollbar.set)
            files_scrollbar.pack(side='right', fill='y')

            file_paths = []

            def add_files():
                files = filedialog.askopenfilenames(
                    title="Select Files for Batch OCR",
                    filetypes=[
                        ("Image files", "*.jpg *.jpeg *.png *.tiff *.bmp"),
                        ("PDF files", "*.pdf"),
                        ("All files", "*.*")
                    ]
                )
                for file in files:
                    if file not in file_paths:
                        file_paths.append(file)
                        files_listbox.insert(tk.END, os.path.basename(file))

            def remove_file():
                selection = files_listbox.curselection()
                if selection:
                    index = selection[0]
                    files_listbox.delete(index)
                    del file_paths[index]

            def clear_all():
                files_listbox.delete(0, tk.END)
                file_paths.clear()

            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(fill='x', pady=(0, 15))

            ttk.Button(btn_frame, text="Add Files", command=add_files).pack(side='left', padx=5)
            ttk.Button(btn_frame, text="Remove Selected", command=remove_file).pack(side='left', padx=5)
            ttk.Button(btn_frame, text="Clear All", command=clear_all).pack(side='left', padx=5)

            # Progress frame
            progress_frame = ttk.LabelFrame(main_frame, text="Processing Progress", padding=10)
            progress_frame.pack(fill='x', pady=(0, 15))

            progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=500)
            progress_bar.pack(fill='x', pady=5)

            progress_label = ttk.Label(progress_frame, text="Ready to start", font=('Arial', 9))
            progress_label.pack(pady=5)

            # Results log
            results_frame = ttk.LabelFrame(main_frame, text="Results", padding=10)
            results_frame.pack(fill='both', expand=True)

            results_text = tk.Text(results_frame, height=8, wrap=tk.WORD, font=('Courier', 9))
            results_text.pack(fill='both', expand=True)

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x', pady=(15, 0))

            def start_batch_processing():
                if not file_paths:
                    messagebox.showwarning("Warning", "Please add files first")
                    return

                results_text.delete('1.0', tk.END)
                results_text.insert('1.0', f"Starting batch OCR processing for {len(file_paths)} files...\n\n")

                progress_bar['maximum'] = len(file_paths)
                progress_bar['value'] = 0

                success_count = 0
                fail_count = 0

                for idx, file_path in enumerate(file_paths, 1):
                    progress_label.config(text=f"Processing {idx}/{len(file_paths)}: {os.path.basename(file_path)}")
                    dialog.update()

                    try:
                        # Simulate OCR processing
                        import time
                        time.sleep(0.5)

                        results_text.insert(tk.END, f"✓ {os.path.basename(file_path)} - SUCCESS\n")
                        success_count += 1

                    except Exception as e:
                        results_text.insert(tk.END, f"✗ {os.path.basename(file_path)} - FAILED: {e}\n")
                        fail_count += 1

                    progress_bar['value'] = idx
                    results_text.see(tk.END)

                results_text.insert(tk.END, f"\n{'='*60}\n")
                results_text.insert(tk.END, f"Batch processing completed!\n")
                results_text.insert(tk.END, f"Success: {success_count}, Failed: {fail_count}\n")

                progress_label.config(text="Processing completed!")

                self.gui.log_event('batch_ocr', 'documents', None, {
                    'total_files': len(file_paths),
                    'success': success_count,
                    'failed': fail_count
                })

                messagebox.showinfo("Completed",
                                  f"Batch OCR processing completed!\n\n"
                                  f"Success: {success_count}\n"
                                  f"Failed: {fail_count}")

            ttk.Button(action_frame, text="Start Processing", command=start_batch_processing).pack(side='left', padx=5)
            ttk.Button(action_frame, text="View OCR Results", command=self.view_ocr_results).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open batch OCR: {e}")

    def view_ocr_results(self):
        """
        View OCR processing results history
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("OCR Results History")
            dialog.geometry("1100x700")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="OCR Results History",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Summary
            summary_frame = ttk.Frame(main_frame)
            summary_frame.pack(fill='x', pady=(0, 20))

            # Mock stats
            self.gui.create_stat_card(summary_frame, "Total Processed", 127, '#3498db', 0)
            self.gui.create_stat_card(summary_frame, "Successful", 115, '#27ae60', 1)
            self.gui.create_stat_card(summary_frame, "Failed", 12, '#e74c3c', 2)
            self.gui.create_stat_card(summary_frame, "Avg. Confidence", "94.3%", '#9b59b6', 3)

            # Results list
            results_frame = ttk.LabelFrame(main_frame, text="OCR Processing History", padding=10)
            results_frame.pack(fill='both', expand=True)

            columns = ('File Name', 'Process Date', 'Status', 'Confidence', 'Language', 'Pages', 'Processing Time')
            results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=15)

            for col in columns:
                results_tree.heading(col, text=col)
                if col in ['Status', 'Confidence', 'Language', 'Pages']:
                    results_tree.column(col, width=80)
                elif col == 'Processing Time':
                    results_tree.column(col, width=120)
                else:
                    results_tree.column(col, width=200)

            scrollbar = ttk.Scrollbar(results_frame, orient='vertical', command=results_tree.yview)
            results_tree.configure(yscrollcommand=scrollbar.set)
            results_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Load mock results
            mock_results = [
                ('document1.pdf', '2025-11-07 10:30', 'Success', '95.2%', 'English', '3', '1.2s'),
                ('scan_image.jpg', '2025-11-07 10:25', 'Success', '98.1%', 'English', '1', '0.8s'),
                ('form_2024.pdf', '2025-11-07 10:20', 'Failed', 'N/A', 'English', '1', '2.1s'),
                ('contract.tiff', '2025-11-07 10:15', 'Success', '92.7%', 'English', '5', '3.4s'),
            ]

            for result in mock_results:
                results_tree.insert('', 'end', values=result)

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x', pady=(20, 0))

            def export_results():
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile=f"ocr_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                )

                if file_path:
                    try:
                        with open(file_path, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.writer(f)
                            writer.writerow(columns)
                            for item in results_tree.get_children():
                                writer.writerow(results_tree.item(item)['values'])

                        messagebox.showinfo("Success", f"Results exported to:\n{file_path}")
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to export: {e}")

            ttk.Button(action_frame, text="Export Results", command=export_results).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Clear History", command=lambda: results_tree.delete(*results_tree.get_children())).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open OCR results: {e}")

    def ocr_settings_gui(self):
        """OCR settings GUI - redirects to ocr_settings()"""
        # This is a wrapper that redirects to the existing ocr_settings method
        self.ocr_settings()
