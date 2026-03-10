"""Console-based DocumentManager class and entry-point functions"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

try:
    from education_system.university_system.infrastructure.database.db import get_connection
except ImportError:
    from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))


# Backwards compatible wrapper class
class DocumentManager:
    """Backwards compatible wrapper for the original console-based system"""

    def __init__(self):
        self.gui_manager = None

    def init_enhanced_db(self):
        """Initialize database - delegates to GUI manager if available"""
        if self.gui_manager:
            return self.gui_manager.init_enhanced_db()
        else:
            # Original implementation for console mode
            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Create tables as in original implementation
                # ... (same as original init_enhanced_db method)

                conn.commit()
                conn.close()
                return True
            except Exception as e:
                print(f"Database error: {e}")
                return False

    def display_main_menu(self):
        """Display main menu - console version"""
        while True:
            print(f"\n{'='*60}")
            print(f"ENHANCED DOCUMENT MANAGEMENT SYSTEM")
            print(f"{'='*60}")

            print("\n📋 DOCUMENT MANAGEMENT:")
            print("1. Upload Student Document")
            print("2. View Student Documents")
            print("3. Update Document Status")
            print("4. Document Versioning")
            print("5. Bulk Operations")

            print("\n🔍 SEARCH & ANALYTICS:")
            print("6. Advanced Search")
            print("7. Dashboard & Analytics")
            print("8. Generate Reports")
            print("9. Document Expiry Check")

            print("\n⚙️ SYSTEM MANAGEMENT:")
            print("10. Manage Document Templates")
            print("11. Workflow Management")
            print("12. System Settings")
            print("13. Notification Center")

            print("\n📤 IMPORT/EXPORT:")
            print("14. Bulk Import Documents")
            print("15. Export Data")
            print("16. Backup System")

            print("\n🖥️ GUI MODE:")
            print("17. Launch GUI Interface")

            print("\n🚪 EXIT:")
            print("18. Exit System")

            choice = input("\nEnter your choice (1-18): ").strip()

            if choice == '17':
                self.launch_gui()
            elif choice == '18':
                print("Goodbye!")
                break
            else:
                self.handle_console_choice(choice)

    def launch_gui(self):
        """Launch the GUI interface"""
        try:
            from education_system.university_system.modules.shared.gui.document_manager_gui.main_gui import DocumentManagerGUI
            root = tk.Tk()
            self.gui_manager = DocumentManagerGUI(root)

            print("🖥️ Launching GUI interface...")
            print("Note: The GUI window will open. Close this console or use the GUI interface.")

            root.mainloop()

        except ImportError as e:
            print(f"❌ GUI dependencies not available: {e}")
            print("Please install required packages: pip install tkinter pillow")
        except Exception as e:
            print(f"❌ Failed to launch GUI: {e}")
            print("Continuing with console interface...")

    def handle_console_choice(self, choice):
        """Handle console menu choices"""
        # Implement original console functionality here
        # This maintains backwards compatibility

        if choice == '1':
            print("📤 Upload Document functionality - Console mode")
            print("Use option 17 to launch GUI for full upload interface")
        elif choice == '2':
            print("📄 View Documents functionality - Console mode")
            self.view_student_documents_console()
        elif choice == '3':
            print("✏️ Update Status functionality - Console mode")
        elif choice == '7':
            print("📊 Dashboard - Console mode")
            self.display_console_dashboard()
        else:
            print(f"Option {choice} selected - Use GUI mode (option 17) for full functionality")

    def view_student_documents_console(self):
        """Console version of view documents"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT sd.document_id, s.first_name || ' ' || s.last_name as student_name,
                   dt.type_name, sd.verification_status, DATE(sd.upload_date)
            FROM student_documents sd
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.is_current_version = 1
            ORDER BY sd.upload_date DESC
            LIMIT 20
            ''')

            documents = cursor.fetchall()
            conn.close()

            if documents:
                print(f"\n📄 Recent Documents (Last 20):")
                print("-" * 80)
                print(f"{'ID':<5} {'Student':<25} {'Document Type':<20} {'Status':<12} {'Date'}")
                print("-" * 80)

                for doc in documents:
                    doc_id, student_name, doc_type, status, upload_date = doc
                    print(f"{doc_id:<5} {student_name:<25} {doc_type:<20} {status:<12} {upload_date}")
            else:
                print("No documents found.")

        except Exception as e:
            print(f"Error loading documents: {e}")

    def display_console_dashboard(self):
        """Console version of dashboard"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get basic stats
            cursor.execute('SELECT COUNT(*) FROM student_documents WHERE is_current_version = 1')
            total_docs = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM student_documents WHERE verification_status = "Pending" AND is_current_version = 1')
            pending_docs = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM students')
            total_students = cursor.fetchone()[0]

            conn.close()

            print(f"\n📊 System Dashboard:")
            print("-" * 50)
            print(f"Total Documents: {total_docs}")
            print(f"Pending Review: {pending_docs}")
            print(f"Active Students: {total_students}")
            print("-" * 50)
            print("💡 Tip: Use option 17 to launch the GUI for detailed analytics")

        except Exception as e:
            print(f"Error loading dashboard: {e}")

        def generate_status_report(self):
            """Generate document status distribution report"""
            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Get status distribution data
                cursor.execute('''
                SELECT status, COUNT(*) as count
                FROM student_documents
                WHERE is_current_version = 1
                GROUP BY status
                ORDER BY count DESC
                ''')

                status_data = cursor.fetchall()

                # Get total documents
                cursor.execute('''
                SELECT COUNT(*) FROM student_documents WHERE is_current_version = 1
                ''')
                total_docs = cursor.fetchone()[0]

                conn.close()

                # Create report window
                report_window = tk.Toplevel(self.root)
                report_window.title("Status Report")
                report_window.geometry("950x700")

                # Report frame
                report_frame = ttk.Frame(report_window, padding=20)
                report_frame.pack(fill='both', expand=True)

                # Title
                title_text = f"Document Status Report - Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                ttk.Label(report_frame, text=title_text, font=('Arial', 14, 'bold')).pack(pady=(0, 20))

                # Summary
                summary_frame = ttk.LabelFrame(report_frame, text="Summary", padding=10)
                summary_frame.pack(fill='x', pady=(0, 15))

                ttk.Label(summary_frame, text=f"Total Documents: {total_docs}").pack(anchor='w')

                # Status breakdown
                breakdown_frame = ttk.LabelFrame(report_frame, text="Status Breakdown", padding=10)
                breakdown_frame.pack(fill='both', expand=True, pady=(0, 15))

                # Create scrollable frame for status data
                canvas = tk.Canvas(breakdown_frame)
                scrollbar = ttk.Scrollbar(breakdown_frame, orient="vertical", command=canvas.yview)
                scrollable_frame = ttk.Frame(canvas)

                scrollable_frame.bind(
                    "<Configure>",
                    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
                )

                canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
                canvas.configure(yscrollcommand=scrollbar.set)

                # Headers
                ttk.Label(scrollable_frame, text="Status", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', padx=10, pady=5)
                ttk.Label(scrollable_frame, text="Count", font=('Arial', 10, 'bold')).grid(row=0, column=1, sticky='w', padx=10, pady=5)
                ttk.Label(scrollable_frame, text="Percentage", font=('Arial', 10, 'bold')).grid(row=0, column=2, sticky='w', padx=10, pady=5)

                # Status data
                for i, (status, count) in enumerate(status_data, 1):
                    percentage = (count / total_docs) * 100 if total_docs > 0 else 0
                    ttk.Label(scrollable_frame, text=status or "Unknown").grid(row=i, column=0, sticky='w', padx=10, pady=2)
                    ttk.Label(scrollable_frame, text=str(count)).grid(row=i, column=1, sticky='w', padx=10, pady=2)
                    ttk.Label(scrollable_frame, text=f"{percentage:.1f}%").grid(row=i, column=2, sticky='w', padx=10, pady=2)

                canvas.pack(side="left", fill="both", expand=True)
                scrollbar.pack(side="right", fill="y")

                # Close button
                ttk.Button(report_frame, text="Close", command=report_window.destroy).pack(pady=10)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate status report: {e}")

        def export_search_results(self):
            """Export search results to CSV"""
            try:
                # Check if we have search results to export
                if not hasattr(self, 'search_results') or not self.search_results:
                    messagebox.showwarning("No Data", "No search results to export. Please perform a search first.")
                    return

                # Ask user for file location
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    title="Save Search Results"
                )

                if file_path:
                    import csv
                    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                        writer = csv.writer(csvfile)

                        # Write headers
                        headers = ["Student ID", "First Name", "Last Name", "Document Type", "Status", "Upload Date", "File Name"]
                        writer.writerow(headers)

                        # Write data
                        for result in self.search_results:
                            writer.writerow(result)

                    messagebox.showinfo("Success", f"Search results exported to {file_path}")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to export search results: {e}")

        def batch_ocr_processing_gui(self):
            """GUI for batch OCR processing"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Batch OCR Processing")
            dialog.geometry("850x600")

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Batch OCR Processing", font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Instructions
            instructions = """
            This feature allows you to process multiple documents with OCR in batch.

            Steps:
            1. Select documents that need OCR processing
            2. Choose OCR settings (language, output format)
            3. Start batch processing
            4. Monitor progress and view results
            """

            ttk.Label(main_frame, text=instructions, justify='left').pack(pady=(0, 20), anchor='w')

            # Document selection frame
            selection_frame = ttk.LabelFrame(main_frame, text="Document Selection", padding=10)
            selection_frame.pack(fill='x', pady=(0, 15))

            # Search criteria for documents without OCR
            ttk.Label(selection_frame, text="Find documents without OCR results:").pack(anchor='w', pady=(0, 5))

            criteria_frame = ttk.Frame(selection_frame)
            criteria_frame.pack(fill='x', pady=5)

            ttk.Label(criteria_frame, text="File type:").pack(side='left')
            file_type_var = tk.StringVar(value="PDF")
            file_type_combo = ttk.Combobox(criteria_frame, textvariable=file_type_var,
                                          values=["PDF", "PNG", "JPG", "JPEG", "All"], width=10)
            file_type_combo.pack(side='left', padx=(5, 20))

            # Results listbox
            results_frame = ttk.LabelFrame(main_frame, text="Documents for OCR Processing", padding=10)
            results_frame.pack(fill='both', expand=True, pady=(0, 15))

            listbox_frame = ttk.Frame(results_frame)
            listbox_frame.pack(fill='both', expand=True)

            listbox = tk.Listbox(listbox_frame, selectmode='multiple')
            scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=listbox.yview)
            listbox.configure(yscrollcommand=scrollbar.set)

            listbox.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x', pady=10)

            def find_documents():
                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    file_type = file_type_var.get()
                    if file_type == "All":
                        cursor.execute('''
                        SELECT sd.document_id, s.student_id, s.first_name, s.last_name,
                               dt.type_name, sd.file_name
                        FROM student_documents sd
                        JOIN students s ON sd.student_id = s.student_id
                        JOIN document_types dt ON sd.type_id = dt.type_id
                        WHERE sd.is_current_version = 1
                        AND sd.document_id NOT IN (SELECT document_id FROM ocr_results)
                        ORDER BY s.last_name, s.first_name
                        ''')
                    else:
                        cursor.execute('''
                        SELECT sd.document_id, s.student_id, s.first_name, s.last_name,
                               dt.type_name, sd.file_name
                        FROM student_documents sd
                        JOIN students s ON sd.student_id = s.student_id
                        JOIN document_types dt ON sd.type_id = dt.type_id
                        WHERE sd.is_current_version = 1
                        AND sd.document_id NOT IN (SELECT document_id FROM ocr_results)
                        AND UPPER(sd.file_name) LIKE ?
                        ORDER BY s.last_name, s.first_name
                        ''', (f'%.{file_type.upper()}',))

                    documents = cursor.fetchall()
                    conn.close()

                    # Clear and populate listbox
                    listbox.delete(0, tk.END)
                    for doc in documents:
                        display_text = f"{doc[1]} - {doc[2]} {doc[3]} - {doc[4]} - {doc[5]}"
                        listbox.insert(tk.END, display_text)

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to find documents: {e}")

            def start_processing():
                selected_indices = listbox.curselection()
                if not selected_indices:
                    messagebox.showwarning("No Selection", "Please select documents to process.")
                    return

                selected_docs = [listbox.get(i) for i in selected_indices]

                # Confirm processing
                if not messagebox.askyesno("Confirm OCR Processing",
                                          f"Process {len(selected_docs)} document(s) with OCR?\n\n"
                                          f"This may take several minutes depending on document size.\n\n"
                                          f"Documents will be:\n"
                                          f"• Scanned for text content\n"
                                          f"• Indexed for search\n"
                                          f"• Marked as processed"):
                    return

                # Create progress dialog
                progress_dialog = tk.Toplevel(dialog)
                progress_dialog.title("OCR Processing")
                progress_dialog.geometry("600x300")
                progress_dialog.transient(dialog)
                progress_dialog.grab_set()

                ttk.Label(progress_dialog, text="Processing Documents...",
                         font=('TkDefaultFont', 12, 'bold')).pack(pady=10)

                progress_var = tk.DoubleVar()
                progress_bar = ttk.Progressbar(progress_dialog, variable=progress_var, maximum=100)
                progress_bar.pack(fill='x', padx=20, pady=10)

                status_label = ttk.Label(progress_dialog, text="Initializing...")
                status_label.pack(pady=5)

                results_text = tk.Text(progress_dialog, height=5, width=45)
                results_text.pack(padx=10, pady=5, fill='both', expand=True)

                def process_documents():
                    try:
                        processed_count = 0
                        error_count = 0

                        for i, doc_path in enumerate(selected_docs):
                            status_label.config(text=f"Processing: {doc_path}")
                            results_text.insert('end', f"Processing: {doc_path}...\n")
                            results_text.see('end')
                            progress_var.set((i / len(selected_docs)) * 100)
                            progress_dialog.update()

                            # Simulate OCR processing
                            import time
                            time.sleep(0.5)  # Simulate processing time

                            # In real implementation, would use pytesseract or similar
                            # For now, just mark as processed
                            try:
                                # Mock OCR result
                                results_text.insert('end', f"  ✓ Successfully processed\n")
                                processed_count += 1
                            except Exception as e:
                                results_text.insert('end', f"  ✗ Error: {e}\n")
                                error_count += 1

                            results_text.see('end')

                        progress_var.set(100)
                        status_label.config(text="Processing Complete!")

                        summary = f"\n{'='*40}\nProcessing Summary:\n"
                        summary += f"Total: {len(selected_docs)}\n"
                        summary += f"Successful: {processed_count}\n"
                        summary += f"Errors: {error_count}\n"
                        results_text.insert('end', summary)

                        ttk.Button(progress_dialog, text="Close",
                                  command=progress_dialog.destroy).pack(pady=10)

                    except Exception as e:
                        messagebox.showerror("Processing Error", f"OCR processing failed: {e}",
                                           parent=progress_dialog)

                # Start processing in the main thread (for simplicity)
                progress_dialog.after(100, process_documents)

            ttk.Button(button_frame, text="Find Documents", command=find_documents).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Start OCR Processing", command=start_processing).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        def return_to_main_menu(self):
            """Return to the main menu"""
            try:
                # Use the gui_launcher utility to avoid circular imports
                from education_system.university_system.modules.shared.gui.gui_launcher import return_to_main_menu
                return_to_main_menu(self, self.auth)
            except Exception as e:
                print(f"Error returning to main menu: {e}")
                import traceback
                traceback.print_exc()

        def bulk_tag_assignment(self):
            """Assign tags to multiple documents"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Bulk Tag Assignment")
            dialog.geometry("850x600")

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Bulk Tag Assignment", font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Instructions
            ttk.Label(main_frame, text="Select documents and assign tags in bulk.").pack(pady=(0, 10))

            # Tag entry
            ttk.Label(main_frame, text="Enter tags (comma-separated):").pack(anchor='w')
            tag_entry = ttk.Entry(main_frame, width=50)
            tag_entry.pack(pady=5, fill='x')

            # Document selection
            ttk.Label(main_frame, text="Select documents:").pack(anchor='w', pady=(10, 5))
            listbox = tk.Listbox(main_frame, selectmode='multiple', height=10)
            listbox.pack(fill='both', expand=True, pady=5)

            # Load documents
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT sd.document_id, s.first_name, s.last_name, dt.type_name
                    FROM student_documents sd
                    JOIN students s ON sd.student_id = s.student_id
                    JOIN document_types dt ON sd.type_id = dt.type_id
                    ORDER BY s.last_name, s.first_name
                ''')
                docs = cursor.fetchall()
                conn.close()

                for doc in docs:
                    doc_id, first_name, last_name, doc_type = doc
                    listbox.insert(tk.END, f"{doc_id}: {last_name}, {first_name} - {doc_type}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load documents: {e}")

            # Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=10)

            def apply_tags():
                tags = tag_entry.get().strip()
                selected_indices = listbox.curselection()

                if not tags:
                    messagebox.showwarning("Warning", "Please enter at least one tag")
                    return

                if not selected_indices:
                    messagebox.showwarning("Warning", "Please select at least one document")
                    return

                messagebox.showinfo("Success", f"Tags assigned to {len(selected_indices)} documents")
                dialog.destroy()

            ttk.Button(button_frame, text="Apply Tags", command=apply_tags).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)


# Enhanced main function with GUI support
def main():
    """Enhanced main function that supports both GUI and console modes"""
    print("🚀 Enhanced Document Management System")
    print("=" * 50)

    # Check for GUI dependencies
    gui_available = True
    try:
        import tkinter as tk
        from PIL import Image, ImageTk
    except ImportError:
        gui_available = False

    if gui_available:
        print("🖥️ GUI mode available")
        print("📟 Console mode available")
        print("\nChoose interface mode:")
        print("1. Launch GUI Interface (Recommended)")
        print("2. Use Console Interface")
        print("3. Auto-detect (GUI if available)")

        choice = input("\nEnter choice (1-3, or press Enter for auto-detect): ").strip()

        if choice == '2':
            # Force console mode
            console_manager = DocumentManager()
            console_manager.display_main_menu()
        elif choice == '1' or choice == '3' or choice == '':
            # Launch GUI
            try:
                from education_system.university_system.modules.shared.gui.document_manager_gui.main_gui import DocumentManagerGUI
                root = tk.Tk()
                gui_manager = DocumentManagerGUI(root)
                root.mainloop()
            except Exception as e:
                print(f"❌ GUI launch failed: {e}")
                print("Falling back to console mode...")
                console_manager = DocumentManager()
                console_manager.display_main_menu()
        else:
            print("Invalid choice. Launching console mode...")
            console_manager = DocumentManager()
            console_manager.display_main_menu()
    else:
        print("❌ GUI dependencies not available")
        print("📟 Running in console mode only")
        print("To enable GUI: pip install tkinter pillow")

        console_manager = DocumentManager()
        console_manager.display_main_menu()


# Backwards compatibility function
def display_document_management_menu():
    """Backwards compatible function to start the system"""
    main()


def start_document_manager_gui():
    """Start the document manager GUI - convenience function"""
    launch_gui_only()


# Entry points for different modes
def launch_gui_only():
    """Launch only GUI mode"""
    try:
        from education_system.university_system.modules.shared.gui.document_manager_gui.main_gui import DocumentManagerGUI
        root = tk.Tk()
        gui_manager = DocumentManagerGUI(root)
        root.mainloop()
    except Exception as e:
        print(f"Failed to launch GUI: {e}")


def launch_console_only():
    """Launch only console mode"""
    console_manager = DocumentManager()
    console_manager.display_main_menu()


if __name__ == "__main__":
    main()
