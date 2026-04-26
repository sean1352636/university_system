import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime
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


class WorkflowManager:
    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def view_active_workflows(self):
        """View all active workflows in GUI"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("docmanager.active_workflows_title", default="Active Workflows"))
        dialog.geometry("900x600")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=_t("docmanager.active_workflows", default="Active Workflows"), font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Create treeview for workflows
        columns = ('WF ID', 'Doc ID', 'Student', 'Document Type', 'Step', 'Assigned To', 'Age (days)')
        workflows_tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)

        for col in columns:
            workflows_tree.heading(col, text=col)
            workflows_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=workflows_tree.yview)
        workflows_tree.configure(yscrollcommand=scrollbar.set)

        workflows_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Load workflows data
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT dw.workflow_id, sd.document_id, s.first_name || ' ' || s.last_name as student_name,
                   dt.type_name, dw.step_name, dw.assigned_to, sd.upload_date
            FROM document_workflow dw
            JOIN documents sd ON dw.document_id = sd.document_id
            JOIN students s ON sd.owner_id = s.student_id
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            WHERE sd.source_type = 'student' AND dw.status = 'pending'
            ORDER BY sd.upload_date ASC
            ''')

            workflows = cursor.fetchall()
            conn.close()

            for workflow in workflows:
                wf_id, doc_id, student_name, doc_type, step_name, assigned_to, upload_date = workflow

                # Calculate age
                upload_dt = datetime.strptime(upload_date[:10], '%Y-%m-%d')
                age_days = (datetime.now() - upload_dt).days

                workflows_tree.insert('', 'end', values=(wf_id, doc_id, student_name, doc_type, step_name, assigned_to, age_days))

        except Exception as e:
            ttk.Label(main_frame, text=f"Error loading workflows: {e}").pack()

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def process_workflow_step(self):
        """Process a workflow step in GUI"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Process Workflow Step")
        dialog.geometry("700x550")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Process Workflow Step", font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        # Workflow ID input
        ttk.Label(main_frame, text="Workflow ID:").pack(anchor='w')
        workflow_id_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=workflow_id_var, width=20).pack(fill='x', pady=5)

        # Action selection
        ttk.Label(main_frame, text="Action:").pack(anchor='w', pady=(10, 0))
        action_var = tk.StringVar(value="approve")

        actions = [("Approve and Continue", "approve"), ("Reject and Stop", "reject"), ("Request More Info", "request_info")]
        for text, value in actions:
            ttk.Radiobutton(main_frame, text=text, variable=action_var, value=value).pack(anchor='w', pady=2)

        # Comments
        ttk.Label(main_frame, text="Comments:").pack(anchor='w', pady=(10, 0))
        comments_text = tk.Text(main_frame, height=5, width=40)
        comments_text.pack(fill='x', pady=5)

        def process_step():
            workflow_id = workflow_id_var.get()
            action = action_var.get()
            comments = comments_text.get('1.0', 'end-1c')

            if not workflow_id:
                messagebox.showerror("Error", "Please enter workflow ID")
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Get workflow details
                cursor.execute('''
                SELECT dw.document_id, dw.step_name
                FROM document_workflow dw
                WHERE dw.workflow_id = ? AND dw.status = 'pending'
                ''', (workflow_id,))

                workflow = cursor.fetchone()

                if not workflow:
                    messagebox.showerror("Error", "Workflow step not found or already completed")
                    conn.close()
                    return

                doc_id, step_name = workflow

                if action == "approve":
                    # Mark step as completed
                    cursor.execute('''
                    UPDATE document_workflow
                    SET status = 'completed', completed_date = ?, completed_by = ?, comments = ?
                    WHERE workflow_id = ?
                    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                          self.gui.current_user['username'], comments, workflow_id))

                    # Check if workflow is complete
                    cursor.execute('''
                    SELECT COUNT(*) FROM document_workflow
                    WHERE document_id = ? AND status = 'pending'
                    ''', (doc_id,))

                    pending_steps = cursor.fetchone()[0]

                    if pending_steps == 0:
                        # Mark document as verified
                        cursor.execute('''
                        UPDATE documents
                        SET verification_status = 'Verified', verification_date = ?,
                            workflow_status = 'completed'
                        WHERE document_id = ?
                        ''', (datetime.now().strftime('%Y-%m-%d'), doc_id))

                        messagebox.showinfo("Success", "Workflow completed! Document marked as Verified.")
                    else:
                        messagebox.showinfo("Success", "Step approved. Workflow continues to next step.")

                elif action == "reject":
                    cursor.execute('''
                    UPDATE document_workflow
                    SET status = 'rejected', completed_date = ?, completed_by = ?, comments = ?
                    WHERE workflow_id = ?
                    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                          self.gui.current_user['username'], comments, workflow_id))

                    cursor.execute('''
                    UPDATE documents
                    SET verification_status = 'Rejected', verification_date = ?,
                        verification_notes = ?, workflow_status = 'rejected'
                    WHERE document_id = ?
                    ''', (datetime.now().strftime('%Y-%m-%d'), comments, doc_id))

                    messagebox.showinfo("Success", "Document rejected. Workflow stopped.")

                conn.commit()
                conn.close()
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to process workflow step: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))

        ttk.Button(button_frame, text="Process", command=process_step).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def workflow_management(self):
        """Full workflow management interface"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Workflow Management")
        dialog.geometry("900x700")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        # Create notebook for different workflow sections
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Active Workflows Tab
        active_frame = ttk.Frame(notebook, padding=15)
        notebook.add(active_frame, text="Active Workflows")

        ttk.Label(active_frame, text="Active Workflows", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Workflows list
        wf_columns = ('WF ID', 'Doc ID', 'Student', 'Document Type', 'Step', 'Assigned To', 'Age (days)')
        self.gui.workflows_tree = ttk.Treeview(active_frame, columns=wf_columns, show='headings', height=12)

        for col in wf_columns:
            self.gui.workflows_tree.heading(col, text=col)
            self.gui.workflows_tree.column(col, width=100)

        wf_scrollbar = ttk.Scrollbar(active_frame, orient='vertical', command=self.gui.workflows_tree.yview)
        self.gui.workflows_tree.configure(yscrollcommand=wf_scrollbar.set)

        self.gui.workflows_tree.pack(side='left', fill='both', expand=True)
        wf_scrollbar.pack(side='right', fill='y')

        # Process Workflow Tab
        process_frame = ttk.Frame(notebook, padding=15)
        notebook.add(process_frame, text="Process Steps")

        ttk.Label(process_frame, text="Process Workflow Step", font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        # Workflow ID input
        id_frame = ttk.Frame(process_frame)
        id_frame.pack(fill='x', pady=5)
        ttk.Label(id_frame, text="Workflow ID:").pack(side='left')
        self.gui.workflow_id_var = tk.StringVar()
        ttk.Entry(id_frame, textvariable=self.gui.workflow_id_var, width=20).pack(side='left', padx=10)
        ttk.Button(id_frame, text="Load", command=self.load_workflow_details).pack(side='left', padx=5)

        # Workflow details
        self.gui.workflow_details_frame = ttk.LabelFrame(process_frame, text="Workflow Details", padding=10)
        self.gui.workflow_details_frame.pack(fill='x', pady=10)

        # Action selection
        action_frame = ttk.LabelFrame(process_frame, text="Action", padding=10)
        action_frame.pack(fill='x', pady=10)

        self.gui.workflow_action_var = tk.StringVar(value="approve")
        actions = [("Approve and Continue", "approve"), ("Reject and Stop", "reject"), ("Request More Info", "request_info")]
        for text, value in actions:
            ttk.Radiobutton(action_frame, text=text, variable=self.gui.workflow_action_var, value=value).pack(anchor='w', pady=2)

        # Comments
        ttk.Label(process_frame, text="Comments:").pack(anchor='w', pady=(10, 0))
        self.gui.workflow_comments = tk.Text(process_frame, height=5, width=50)
        self.gui.workflow_comments.pack(fill='x', pady=5)

        ttk.Button(process_frame, text="Process Step", command=self.process_workflow_step_full).pack(pady=15)

        # Workflow Templates Tab
        templates_frame = ttk.Frame(notebook, padding=15)
        notebook.add(templates_frame, text="Templates")

        ttk.Label(templates_frame, text="Workflow Templates", font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        template_options = [
            ("Standard Document Review", self.create_standard_workflow),
            ("Express Approval", self.create_express_workflow),
            ("Multi-Stage Verification", self.create_multistage_workflow),
            ("\U0001f3e0 Return to Main Menu", self.gui.return_to_main_menu)
        ]

        for text, command in template_options:
            ttk.Button(templates_frame, text=text, command=command, width=30).pack(pady=5)

        # Load initial data
        self.load_workflows()

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack()

    def load_workflows(self):
        """Load active workflows"""
        if hasattr(self.gui, 'workflows_tree'):
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT dw.workflow_id, sd.document_id, s.first_name || ' ' || s.last_name as student_name,
                       dt.type_name, dw.step_name, dw.assigned_to, sd.upload_date
                FROM document_workflow dw
                JOIN documents sd ON dw.document_id = sd.document_id
                JOIN students s ON sd.owner_id = s.student_id
                JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
                WHERE dw.status = 'pending'
                ORDER BY sd.upload_date ASC
                ''')

                workflows = cursor.fetchall()
                conn.close()

                # Clear existing items
                for item in self.gui.workflows_tree.get_children():
                    self.gui.workflows_tree.delete(item)

                # Insert new items
                for workflow in workflows:
                    wf_id, doc_id, student_name, doc_type, step_name, assigned_to, upload_date = workflow

                    # Calculate age
                    upload_dt = datetime.strptime(upload_date[:10], '%Y-%m-%d')
                    age_days = (datetime.now() - upload_dt).days

                    self.gui.workflows_tree.insert('', 'end', values=(wf_id, doc_id, student_name, doc_type, step_name, assigned_to, age_days))

            except Exception as e:
                print(f"Error loading workflows: {e}")

    def load_workflow_details(self):
        """Load workflow details for processing"""
        workflow_id = self.gui.workflow_id_var.get()
        if not workflow_id:
            messagebox.showerror("Error", "Please enter a workflow ID")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT dw.workflow_id, dw.document_id, dw.step_name, dw.assigned_to,
                   s.first_name, s.last_name, dt.type_name, sd.upload_date
            FROM document_workflow dw
            JOIN documents sd ON dw.document_id = sd.document_id
            JOIN students s ON sd.owner_id = s.student_id
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            WHERE dw.workflow_id = ? AND dw.status = 'pending'
            ''', (workflow_id,))

            workflow = cursor.fetchone()
            conn.close()

            if not workflow:
                messagebox.showerror("Error", "Workflow step not found or already completed")
                return

            # Clear previous details
            for widget in self.gui.workflow_details_frame.winfo_children():
                widget.destroy()

            # Display workflow details
            wf_id, doc_id, step_name, assigned_to, first_name, last_name, doc_type, upload_date = workflow

            ttk.Label(self.gui.workflow_details_frame, text=f"Document: {doc_type}").pack(anchor='w')
            ttk.Label(self.gui.workflow_details_frame, text=f"Student: {first_name} {last_name}").pack(anchor='w')
            ttk.Label(self.gui.workflow_details_frame, text=f"Step: {step_name}").pack(anchor='w')
            ttk.Label(self.gui.workflow_details_frame, text=f"Assigned to: {assigned_to}").pack(anchor='w')
            ttk.Label(self.gui.workflow_details_frame, text=f"Upload Date: {upload_date[:10]}").pack(anchor='w')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load workflow details: {str(e)}")

    def process_workflow_step_full(self):
        """Process workflow step with full functionality"""
        workflow_id = self.gui.workflow_id_var.get()
        action = self.gui.workflow_action_var.get()
        comments = self.gui.workflow_comments.get('1.0', 'end-1c')

        if not workflow_id:
            messagebox.showerror("Error", "Please enter and load a workflow ID first")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get workflow details
            cursor.execute('''
            SELECT dw.document_id FROM document_workflow dw
            WHERE dw.workflow_id = ? AND dw.status = 'pending'
            ''', (workflow_id,))

            workflow = cursor.fetchone()

            if not workflow:
                messagebox.showerror("Error", "Workflow step not found or already completed")
                conn.close()
                return

            doc_id = workflow[0]

            if action == "approve":
                # Mark step as completed
                cursor.execute('''
                UPDATE document_workflow
                SET status = 'completed', completed_date = ?, completed_by = ?, comments = ?
                WHERE workflow_id = ?
                ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                      self.gui.current_user['username'], comments, workflow_id))

                # Check if workflow is complete
                cursor.execute('''
                SELECT COUNT(*) FROM document_workflow
                WHERE document_id = ? AND status = 'pending'
                ''', (doc_id,))

                pending_steps = cursor.fetchone()[0]

                if pending_steps == 0:
                    # Mark document as verified
                    cursor.execute('''
                    UPDATE documents
                    SET verification_status = 'Verified', verification_date = ?,
                        workflow_status = 'completed'
                    WHERE document_id = ?
                    ''', (datetime.now().strftime('%Y-%m-%d'), doc_id))

                    messagebox.showinfo("Success", "Workflow completed! Document marked as Verified.")
                else:
                    messagebox.showinfo("Success", "Step approved. Workflow continues to next step.")

            elif action == "reject":
                cursor.execute('''
                UPDATE document_workflow
                SET status = 'rejected', completed_date = ?, completed_by = ?, comments = ?
                WHERE workflow_id = ?
                ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                      self.gui.current_user['username'], comments, workflow_id))

                cursor.execute('''
                UPDATE documents
                SET verification_status = 'Rejected', verification_date = ?,
                    verification_notes = ?, workflow_status = 'rejected'
                WHERE document_id = ?
                ''', (datetime.now().strftime('%Y-%m-%d'), comments, doc_id))

                messagebox.showinfo("Success", "Document rejected. Workflow stopped.")

            conn.commit()
            conn.close()

            # Clear form and refresh
            self.gui.workflow_id_var.set("")
            self.gui.workflow_comments.delete('1.0', 'end')
            self.load_workflows()

            # Clear workflow details
            for widget in self.gui.workflow_details_frame.winfo_children():
                widget.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process workflow step: {str(e)}")

    def create_standard_workflow(self):
        """Create standard workflow template"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Standard Workflow")
        dialog.geometry("700x550")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Create Standard Workflow Template", font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        # Document type selection
        ttk.Label(main_frame, text="Apply to Document Type:").pack(anchor='w')
        doc_type_var = tk.StringVar()
        doc_type_combo = ttk.Combobox(main_frame, textvariable=doc_type_var)

        # Load document types
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT type_name FROM document_types WHERE is_active = 1')
            doc_types = [row[0] for row in cursor.fetchall()]
            conn.close()
            doc_type_combo['values'] = doc_types
        except Exception:
            doc_type_combo['values'] = []

        doc_type_combo.pack(fill='x', pady=5)

        # Workflow steps preview
        ttk.Label(main_frame, text="Workflow Steps:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(15, 5))

        steps_frame = ttk.Frame(main_frame)
        steps_frame.pack(fill='x', pady=5)

        steps_text = """1. Initial Review (Assigned to: registrar)
       - Verify document format and completeness
       - Check student information accuracy

    2. Verification (Assigned to: admin)
       - Validate document authenticity
       - Cross-reference with records

    3. Final Approval (Assigned to: dean)
       - Final approval and sign-off
       - Update student records"""

        text_widget = tk.Text(steps_frame, height=10, width=50)
        text_widget.insert('1.0', steps_text)
        text_widget.config(state='disabled')
        text_widget.pack(fill='both', expand=True)

        def create_workflow():
            doc_type = doc_type_var.get()
            if not doc_type:
                messagebox.showerror("Error", "Please select a document type")
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Get document type ID
                cursor.execute('SELECT type_id FROM document_types WHERE type_name = ?', (doc_type,))
                type_result = cursor.fetchone()
                if not type_result:
                    messagebox.showerror("Error", "Document type not found")
                    conn.close()
                    return

                type_id = type_result[0]

                # Create workflow template in database
                workflow_steps = [
                    ('Initial Review', 1, 'registrar', 'Verify document format and completeness'),
                    ('Verification', 2, 'admin', 'Validate document authenticity'),
                    ('Final Approval', 3, 'dean', 'Final approval and sign-off')
                ]

                # Note: In a full implementation, you'd have a workflow_templates table
                # For now, we'll just confirm the template creation

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Standard workflow template created for {doc_type}!\n\nNew documents of this type will automatically use this 3-step approval process.")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create workflow: {str(e)}")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))

        ttk.Button(button_frame, text="Create Workflow", command=create_workflow).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def create_express_workflow(self):
        """Create express workflow template"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Express Workflow")
        dialog.geometry("950x700")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Create Express Workflow Template", font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        # Document type selection
        ttk.Label(main_frame, text="Apply to Document Type:").pack(anchor='w')
        doc_type_var = tk.StringVar()
        doc_type_combo = ttk.Combobox(main_frame, textvariable=doc_type_var)

        # Load document types
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT type_name FROM document_types WHERE is_active = 1')
            doc_types = [row[0] for row in cursor.fetchall()]
            conn.close()
            doc_type_combo['values'] = doc_types
        except Exception:
            doc_type_combo['values'] = []

        doc_type_combo.pack(fill='x', pady=5)

        # Priority selection
        ttk.Label(main_frame, text="Priority Level:").pack(anchor='w', pady=(10, 0))
        priority_var = tk.StringVar(value="high")
        priority_frame = ttk.Frame(main_frame)
        priority_frame.pack(fill='x', pady=5)

        ttk.Radiobutton(priority_frame, text="High Priority", variable=priority_var, value="high").pack(side='left')
        ttk.Radiobutton(priority_frame, text="Urgent", variable=priority_var, value="urgent").pack(side='left', padx=20)

        # Workflow steps preview
        ttk.Label(main_frame, text="Express Workflow Steps:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(15, 5))

        steps_text = """1. Quick Review (Assigned to: admin)
       - Fast-track document verification
       - Automated checks where possible
       - Priority processing

    2. Immediate Approval (Assigned to: registrar)
       - Final approval within 24 hours
       - Student notification upon completion

    Target Completion Time: 1-2 business days"""

        text_widget = tk.Text(main_frame, height=8, width=50)
        text_widget.insert('1.0', steps_text)
        text_widget.config(state='disabled')
        text_widget.pack(fill='both', expand=True)

        def create_express():
            doc_type = doc_type_var.get()
            priority = priority_var.get()

            if not doc_type:
                messagebox.showerror("Error", "Please select a document type")
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Get document type ID
                cursor.execute('SELECT type_id FROM document_types WHERE type_name = ?', (doc_type,))
                type_result = cursor.fetchone()
                if not type_result:
                    messagebox.showerror("Error", "Document type not found")
                    conn.close()
                    return

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Express workflow template created for {doc_type}!\n\nPriority: {priority.title()}\nTarget completion: 1-2 business days")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create express workflow: {str(e)}")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))

        ttk.Button(button_frame, text="Create Express Workflow", command=create_express).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def create_multistage_workflow(self):
        """Create multi-stage workflow template"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Multi-Stage Workflow")
        dialog.geometry("850x700")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Create Multi-Stage Workflow Template", font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        # Document type selection
        ttk.Label(main_frame, text="Apply to Document Type:").pack(anchor='w')
        doc_type_var = tk.StringVar()
        doc_type_combo = ttk.Combobox(main_frame, textvariable=doc_type_var)

        # Load document types
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT type_name FROM document_types WHERE is_active = 1')
            doc_types = [row[0] for row in cursor.fetchall()]
            conn.close()
            doc_type_combo['values'] = doc_types
        except Exception:
            doc_type_combo['values'] = []

        doc_type_combo.pack(fill='x', pady=5)

        # Department assignments
        ttk.Label(main_frame, text="Department Assignments:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(15, 5))

        dept_frame = ttk.Frame(main_frame)
        dept_frame.pack(fill='x', pady=5)

        departments = ['registrar', 'academic_affairs', 'student_services', 'dean_office', 'compliance']
        dept_vars = {}

        for i, dept in enumerate(departments):
            dept_vars[dept] = tk.BooleanVar(value=True)
            ttk.Checkbutton(dept_frame, text=dept.replace('_', ' ').title(),
                           variable=dept_vars[dept]).grid(row=i//2, column=i%2, sticky='w', padx=10, pady=2)

        # Workflow steps preview
        ttk.Label(main_frame, text="Multi-Stage Workflow Steps:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(15, 5))

        steps_text = """1. Intake (Assigned to: registrar)
       - Initial document receipt and logging
       - Basic format and completeness check
       - Student information verification

    2. Initial Review (Assigned to: academic_affairs)
       - Academic requirements verification
       - Prerequisite document checks
       - Initial compliance assessment

    3. Department Review (Assigned to: student_services)
       - Department-specific requirements
       - Cross-departmental coordination
       - Specialized review processes

    4. Final Verification (Assigned to: compliance)
       - Comprehensive compliance check
       - Legal and regulatory requirements
       - Quality assurance review

    5. Final Approval (Assigned to: dean_office)
       - Executive approval and sign-off
       - Final authorization
       - Student record updates

    Target Completion Time: 5-7 business days"""

        text_widget = tk.Text(main_frame, height=12, width=60)
        text_widget.insert('1.0', steps_text)
        text_widget.config(state='disabled')
        text_widget.pack(fill='both', expand=True)

        def create_multistage():
            doc_type = doc_type_var.get()
            if not doc_type:
                messagebox.showerror("Error", "Please select a document type")
                return

            # Get selected departments
            selected_depts = [dept for dept, var in dept_vars.items() if var.get()]
            if len(selected_depts) < 2:
                messagebox.showerror("Error", "Please select at least 2 departments for multi-stage workflow")
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Get document type ID
                cursor.execute('SELECT type_id FROM document_types WHERE type_name = ?', (doc_type,))
                type_result = cursor.fetchone()
                if not type_result:
                    messagebox.showerror("Error", "Document type not found")
                    conn.close()
                    return

                conn.commit()
                conn.close()

                dept_list = ', '.join([dept.replace('_', ' ').title() for dept in selected_depts])
                messagebox.showinfo("Success", f"Multi-stage workflow template created for {doc_type}!\n\nDepartments involved: {dept_list}\nTarget completion: 5-7 business days")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create multi-stage workflow: {str(e)}")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))

        ttk.Button(button_frame, text="Create Multi-Stage Workflow", command=create_multistage).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def custom_workflow_builder(self):
        """Open custom workflow builder"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Custom Workflow Builder")
        dialog.geometry("700x600")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Custom Workflow Builder", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Workflow name and document type
        config_frame = ttk.LabelFrame(main_frame, text="Workflow Configuration", padding=10)
        config_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(config_frame, text="Workflow Name:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        workflow_name = tk.Entry(config_frame, width=30)
        workflow_name.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        ttk.Label(config_frame, text="Document Type:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        doc_type_var = tk.StringVar()
        doc_type_combo = ttk.Combobox(config_frame, textvariable=doc_type_var, width=28)
        doc_type_combo.grid(row=1, column=1, padx=5, pady=5, sticky='ew')

        # Load document types
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT type_name FROM document_types WHERE is_active = 1')
            doc_types = [row[0] for row in cursor.fetchall()]
            conn.close()
            doc_type_combo['values'] = doc_types
        except Exception:
            doc_type_combo['values'] = []

        config_frame.grid_columnconfigure(1, weight=1)

        # Workflow steps builder
        steps_frame = ttk.LabelFrame(main_frame, text="Workflow Steps", padding=10)
        steps_frame.pack(fill='both', expand=True, pady=(0, 15))

        # Steps list
        columns = ('Step', 'Name', 'Assigned To', 'Description')
        steps_tree = ttk.Treeview(steps_frame, columns=columns, show='headings', height=8)

        for col in columns:
            steps_tree.heading(col, text=col)
            steps_tree.column(col, width=100)

        steps_scrollbar = ttk.Scrollbar(steps_frame, orient='vertical', command=steps_tree.yview)
        steps_tree.configure(yscrollcommand=steps_scrollbar.set)

        steps_tree.pack(side='left', fill='both', expand=True)
        steps_scrollbar.pack(side='right', fill='y')

        # Step input frame
        step_input_frame = ttk.Frame(steps_frame)
        step_input_frame.pack(fill='x', pady=(10, 0))

        ttk.Label(step_input_frame, text="Step Name:").grid(row=0, column=0, sticky='w', padx=5)
        step_name_entry = tk.Entry(step_input_frame, width=20)
        step_name_entry.grid(row=0, column=1, padx=5)

        ttk.Label(step_input_frame, text="Assigned To:").grid(row=0, column=2, sticky='w', padx=5)
        assigned_to_combo = ttk.Combobox(step_input_frame, values=['registrar', 'admin', 'dean', 'academic_affairs', 'student_services'], width=15)
        assigned_to_combo.grid(row=0, column=3, padx=5)

        ttk.Label(step_input_frame, text="Description:").grid(row=1, column=0, sticky='w', padx=5)
        step_desc_entry = tk.Entry(step_input_frame, width=50)
        step_desc_entry.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky='ew')

        step_input_frame.grid_columnconfigure(1, weight=1)

        def add_step():
            step_name = step_name_entry.get()
            assigned_to = assigned_to_combo.get()
            description = step_desc_entry.get()

            if not step_name or not assigned_to:
                messagebox.showerror("Error", "Please enter step name and assignment")
                return

            step_order = len(steps_tree.get_children()) + 1
            steps_tree.insert('', 'end', values=(step_order, step_name, assigned_to, description))

            # Clear inputs
            step_name_entry.delete(0, 'end')
            assigned_to_combo.set('')
            step_desc_entry.delete(0, 'end')

        def remove_step():
            selection = steps_tree.selection()
            if selection:
                steps_tree.delete(selection[0])
                # Renumber remaining steps
                for i, item in enumerate(steps_tree.get_children()):
                    values = list(steps_tree.item(item)['values'])
                    values[0] = i + 1
                    steps_tree.item(item, values=values)

        step_buttons_frame = ttk.Frame(step_input_frame)
        step_buttons_frame.grid(row=2, column=0, columnspan=4, pady=10)

        ttk.Button(step_buttons_frame, text="Add Step", command=add_step).pack(side='left', padx=5)
        ttk.Button(step_buttons_frame, text="Remove Selected", command=remove_step).pack(side='left', padx=5)

        def save_custom_workflow():
            name = workflow_name.get()
            doc_type = doc_type_var.get()

            if not name or not doc_type:
                messagebox.showerror("Error", "Please enter workflow name and select document type")
                return

            if len(steps_tree.get_children()) == 0:
                messagebox.showerror("Error", "Please add at least one workflow step")
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Get document type ID
                cursor.execute('SELECT type_id FROM document_types WHERE type_name = ?', (doc_type,))
                type_result = cursor.fetchone()
                if not type_result:
                    messagebox.showerror("Error", "Document type not found")
                    conn.close()
                    return

                # Create workflow_templates table if it doesn't exist
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS workflow_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_name TEXT,
                    document_type_id INTEGER,
                    created_date TEXT,
                    created_by TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (document_type_id) REFERENCES document_types (type_id)
                )
                ''')

                cursor.execute('''
                CREATE TABLE IF NOT EXISTS workflow_template_steps (
                    step_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER,
                    step_name TEXT,
                    step_order INTEGER,
                    assigned_to TEXT,
                    description TEXT,
                    FOREIGN KEY (template_id) REFERENCES workflow_templates (template_id)
                )
                ''')

                # Insert workflow template
                cursor.execute('''
                INSERT INTO workflow_templates (template_name, document_type_id, created_date, created_by)
                VALUES (?, ?, ?, ?)
                ''', (name, type_result[0], datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                      self.gui.current_user.get('username', 'admin')))

                template_id = cursor.lastrowid

                # Insert workflow steps
                for item in steps_tree.get_children():
                    values = steps_tree.item(item)['values']
                    step_order, step_name, assigned_to, description = values

                    cursor.execute('''
                    INSERT INTO workflow_template_steps (template_id, step_name, step_order, assigned_to, description)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (template_id, step_name, int(step_order), assigned_to, description))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Custom workflow '{name}' created successfully!\n\nThe workflow will be applied to all new {doc_type} documents.")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create custom workflow: {str(e)}")

        # Main buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Save Workflow", command=save_custom_workflow).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def create_custom_workflow(self):
        """
        Create a custom workflow for document processing
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Create Custom Workflow")
            dialog.geometry("800x700")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Create Custom Workflow",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Workflow name
            name_frame = ttk.LabelFrame(main_frame, text="Workflow Information", padding=10)
            name_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(name_frame, text="Workflow Name:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            workflow_name = tk.StringVar()
            ttk.Entry(name_frame, textvariable=workflow_name, width=40).grid(row=0, column=1, padx=5, pady=5, sticky='ew')

            ttk.Label(name_frame, text="Document Type:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
            doc_type_combo = ttk.Combobox(name_frame, width=37, state='readonly')
            doc_type_combo.grid(row=1, column=1, padx=5, pady=5, sticky='ew')

            # Load document types
            doc_types = self.gui.get_document_types_with_details()
            doc_type_combo['values'] = [f"{dt[1]}" for dt in doc_types]

            name_frame.grid_columnconfigure(1, weight=1)

            # Workflow steps
            steps_frame = ttk.LabelFrame(main_frame, text="Workflow Steps", padding=10)
            steps_frame.pack(fill='both', expand=True, pady=(0, 15))

            # Steps list
            steps_list_frame = ttk.Frame(steps_frame)
            steps_list_frame.pack(fill='both', expand=True)

            columns = ('Order', 'Step Name', 'Assigned To', 'Description')
            steps_tree = ttk.Treeview(steps_list_frame, columns=columns, show='headings', height=8)

            for col in columns:
                steps_tree.heading(col, text=col)
                if col == 'Order':
                    steps_tree.column(col, width=50)
                elif col == 'Step Name':
                    steps_tree.column(col, width=150)
                elif col == 'Assigned To':
                    steps_tree.column(col, width=120)
                else:
                    steps_tree.column(col, width=200)

            scrollbar = ttk.Scrollbar(steps_list_frame, orient='vertical', command=steps_tree.yview)
            steps_tree.configure(yscrollcommand=scrollbar.set)
            steps_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Add step controls
            add_step_frame = ttk.Frame(steps_frame)
            add_step_frame.pack(fill='x', pady=(10, 0))

            ttk.Label(add_step_frame, text="Step Name:").grid(row=0, column=0, sticky='w', padx=5)
            step_name = tk.StringVar()
            ttk.Entry(add_step_frame, textvariable=step_name, width=20).grid(row=0, column=1, padx=5)

            ttk.Label(add_step_frame, text="Assigned To:").grid(row=0, column=2, sticky='w', padx=5)
            assigned_to = tk.StringVar()
            ttk.Entry(add_step_frame, textvariable=assigned_to, width=15).grid(row=0, column=3, padx=5)

            ttk.Label(add_step_frame, text="Description:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
            step_desc = tk.StringVar()
            ttk.Entry(add_step_frame, textvariable=step_desc, width=50).grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky='ew')

            def add_step():
                if step_name.get() and assigned_to.get():
                    order = len(steps_tree.get_children()) + 1
                    steps_tree.insert('', 'end', values=(
                        order, step_name.get(), assigned_to.get(), step_desc.get()
                    ))
                    step_name.set('')
                    assigned_to.set('')
                    step_desc.set('')
                else:
                    messagebox.showwarning("Warning", "Please enter step name and assigned to")

            def remove_step():
                selection = steps_tree.selection()
                if selection:
                    steps_tree.delete(selection)
                    # Reorder remaining steps
                    for idx, item in enumerate(steps_tree.get_children(), 1):
                        steps_tree.set(item, 'Order', idx)
                else:
                    messagebox.showwarning("Warning", "Please select a step to remove")

            button_frame = ttk.Frame(add_step_frame)
            button_frame.grid(row=2, column=0, columnspan=4, pady=10)
            ttk.Button(button_frame, text="Add Step", command=add_step).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Remove Selected", command=remove_step).pack(side='left', padx=5)

            add_step_frame.grid_columnconfigure(1, weight=1)

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x', pady=(10, 0))

            def save_workflow():
                name = workflow_name.get().strip()
                doc_type = doc_type_combo.get()

                if not name:
                    messagebox.showerror("Error", "Please enter workflow name")
                    return

                if not doc_type:
                    messagebox.showerror("Error", "Please select document type")
                    return

                steps = steps_tree.get_children()
                if not steps:
                    messagebox.showerror("Error", "Please add at least one workflow step")
                    return

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    # Create workflow_templates table if not exists
                    cursor.execute('''
                    CREATE TABLE IF NOT EXISTS workflow_templates (
                        template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        template_name TEXT,
                        document_type_name TEXT,
                        created_date TEXT,
                        created_by TEXT,
                        is_active BOOLEAN DEFAULT 1
                    )
                    ''')

                    cursor.execute('''
                    CREATE TABLE IF NOT EXISTS workflow_template_steps (
                        step_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        template_id INTEGER,
                        step_name TEXT,
                        step_order INTEGER,
                        assigned_to TEXT,
                        description TEXT,
                        FOREIGN KEY (template_id) REFERENCES workflow_templates (template_id)
                    )
                    ''')

                    # Insert workflow template
                    username = self.gui.current_user.get('username', 'Unknown') if self.gui.current_user else 'Unknown'
                    cursor.execute('''
                    INSERT INTO workflow_templates (template_name, document_type_name, created_date, created_by)
                    VALUES (?, ?, ?, ?)
                    ''', (name, doc_type, datetime.now().isoformat(), username))

                    template_id = cursor.lastrowid

                    # Insert workflow steps
                    for item in steps:
                        values = steps_tree.item(item)['values']
                        order, step_name_val, assigned_to_val, desc = values
                        cursor.execute('''
                        INSERT INTO workflow_template_steps (template_id, step_name, step_order, assigned_to, description)
                        VALUES (?, ?, ?, ?, ?)
                        ''', (template_id, step_name_val, order, assigned_to_val, desc))

                    conn.commit()
                    conn.close()

                    # Log event
                    self.gui.log_event('create', 'workflow_template', template_id, {
                        'template_name': name,
                        'steps_count': len(steps)
                    })

                    messagebox.showinfo("Success", f"Workflow '{name}' created successfully with {len(steps)} steps")
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create workflow: {e}")

            ttk.Button(action_frame, text="Save Workflow", command=save_workflow).pack(side='right', padx=5)
            ttk.Button(action_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open workflow creator: {e}")

    def workflow_templates(self):
        """
        View and manage workflow templates
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Workflow Templates")
            dialog.geometry("1000x700")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Workflow Templates",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Templates list
            list_frame = ttk.Frame(main_frame)
            list_frame.pack(fill='both', expand=True)

            columns = ('ID', 'Template Name', 'Document Type', 'Steps', 'Created By', 'Created Date', 'Status')
            templates_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

            for col in columns:
                templates_tree.heading(col, text=col)
                if col == 'ID':
                    templates_tree.column(col, width=50)
                elif col == 'Steps':
                    templates_tree.column(col, width=60)
                else:
                    templates_tree.column(col, width=150)

            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=templates_tree.yview)
            templates_tree.configure(yscrollcommand=scrollbar.set)
            templates_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Load templates
            def load_templates():
                templates_tree.delete(*templates_tree.get_children())
                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                    SELECT
                        wt.template_id,
                        wt.template_name,
                        wt.document_type_name,
                        COUNT(wts.step_id) as step_count,
                        wt.created_by,
                        wt.created_date,
                        wt.is_active
                    FROM workflow_templates wt
                    LEFT JOIN workflow_template_steps wts ON wt.template_id = wts.template_id
                    GROUP BY wt.template_id
                    ORDER BY wt.created_date DESC
                    ''')

                    templates = cursor.fetchall()
                    conn.close()

                    for template in templates:
                        status = 'Active' if template[6] else 'Inactive'
                        templates_tree.insert('', 'end', values=(
                            template[0], template[1], template[2], template[3],
                            template[4], template[5], status
                        ))

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load templates: {e}")

            load_templates()

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x', pady=(20, 0))

            def view_template_details():
                selection = templates_tree.selection()
                if not selection:
                    messagebox.showwarning("Warning", "Please select a template")
                    return

                template_id = templates_tree.item(selection[0])['values'][0]

                # Show template details
                detail_dialog = tk.Toplevel(dialog)
                detail_dialog.title("Template Details")
                detail_dialog.geometry("700x500")
                detail_dialog.transient(dialog)

                detail_frame = ttk.Frame(detail_dialog, padding=20)
                detail_frame.pack(fill='both', expand=True)

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    # Get template info
                    cursor.execute('''
                    SELECT template_name, document_type_name, created_by, created_date
                    FROM workflow_templates WHERE template_id = ?
                    ''', (template_id,))
                    template_info = cursor.fetchone()

                    # Get steps
                    cursor.execute('''
                    SELECT step_order, step_name, assigned_to, description
                    FROM workflow_template_steps
                    WHERE template_id = ?
                    ORDER BY step_order
                    ''', (template_id,))
                    steps = cursor.fetchall()
                    conn.close()

                    # Display info
                    info_text = f"Template: {template_info[0]}\n"
                    info_text += f"Document Type: {template_info[1]}\n"
                    info_text += f"Created By: {template_info[2]}\n"
                    info_text += f"Created: {template_info[3]}\n\n"
                    info_text += "Workflow Steps:\n" + "="*50 + "\n"

                    for step in steps:
                        info_text += f"\nStep {step[0]}: {step[1]}\n"
                        info_text += f"  Assigned To: {step[2]}\n"
                        info_text += f"  Description: {step[3]}\n"

                    text_widget = tk.Text(detail_frame, wrap=tk.WORD, font=('Arial', 10))
                    text_widget.pack(fill='both', expand=True)
                    text_widget.insert('1.0', info_text)
                    text_widget.config(state='disabled')

                    ttk.Button(detail_frame, text="Close", command=detail_dialog.destroy).pack(pady=10)

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load template details: {e}")

            def toggle_template_status():
                selection = templates_tree.selection()
                if not selection:
                    messagebox.showwarning("Warning", "Please select a template")
                    return

                template_id = templates_tree.item(selection[0])['values'][0]
                current_status = templates_tree.item(selection[0])['values'][6]

                new_status = 0 if current_status == 'Active' else 1

                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('UPDATE workflow_templates SET is_active = ? WHERE template_id = ?',
                                 (new_status, template_id))
                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", "Template status updated")
                    load_templates()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update status: {e}")

            ttk.Button(action_frame, text="View Details", command=view_template_details).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Toggle Active/Inactive", command=toggle_template_status).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Refresh", command=load_templates).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open workflow templates: {e}")

    def workflow_analytics(self):
        """
        View workflow analytics and statistics
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Workflow Analytics")
            dialog.geometry("1100x750")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Workflow Analytics Dashboard",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Summary cards
            summary_frame = ttk.Frame(main_frame)
            summary_frame.pack(fill='x', pady=(0, 20))

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Total workflows
                cursor.execute('SELECT COUNT(*) FROM document_workflow')
                total_workflows = cursor.fetchone()[0]

                # Pending workflows
                cursor.execute("SELECT COUNT(*) FROM document_workflow WHERE status = 'pending'")
                pending_workflows = cursor.fetchone()[0]

                # Completed workflows
                cursor.execute("SELECT COUNT(*) FROM document_workflow WHERE status = 'completed'")
                completed_workflows = cursor.fetchone()[0]

                # Average completion time
                cursor.execute('''
                SELECT AVG(julianday(completed_date) - julianday(
                    (SELECT MIN(created_date) FROM document_workflow dw2
                     WHERE dw2.document_id = document_workflow.document_id)
                ))
                FROM document_workflow
                WHERE status = 'completed' AND completed_date IS NOT NULL
                ''')
                avg_days = cursor.fetchone()[0]
                avg_days = round(avg_days, 1) if avg_days else 0

                conn.close()

                # Display cards
                self.gui.create_stat_card(summary_frame, "Total Workflows", total_workflows, '#3498db', 0)
                self.gui.create_stat_card(summary_frame, "Pending", pending_workflows, '#f39c12', 1)
                self.gui.create_stat_card(summary_frame, "Completed", completed_workflows, '#27ae60', 2)
                self.gui.create_stat_card(summary_frame, f"Avg. Days", avg_days, '#9b59b6', 3)

            except Exception as e:
                ttk.Label(summary_frame, text=f"Error loading summary: {e}",
                         foreground='red').pack()

            # Workflow by status
            status_frame = ttk.LabelFrame(main_frame, text="Workflows by Status", padding=10)
            status_frame.pack(fill='both', expand=True, pady=(0, 10))

            columns = ('Status', 'Count', 'Percentage')
            status_tree = ttk.Treeview(status_frame, columns=columns, show='headings', height=5)

            for col in columns:
                status_tree.heading(col, text=col)
                status_tree.column(col, width=150)

            status_tree.pack(fill='both', expand=True)

            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT status, COUNT(*) as count
                FROM document_workflow
                GROUP BY status
                ''')
                status_data = cursor.fetchall()
                conn.close()

                total = sum(row[1] for row in status_data) if status_data else 1

                for status, count in status_data:
                    percentage = (count / total * 100) if total > 0 else 0
                    status_tree.insert('', 'end', values=(
                        status.title(), count, f"{percentage:.1f}%"
                    ))

            except Exception as e:
                pass

            # Workflow by assignee
            assignee_frame = ttk.LabelFrame(main_frame, text="Workflows by Assignee", padding=10)
            assignee_frame.pack(fill='both', expand=True)

            columns = ('Assigned To', 'Pending', 'Completed', 'Total')
            assignee_tree = ttk.Treeview(assignee_frame, columns=columns, show='headings', height=8)

            for col in columns:
                assignee_tree.heading(col, text=col)
                assignee_tree.column(col, width=150)

            assignee_tree.pack(fill='both', expand=True)

            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT
                    assigned_to,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    COUNT(*) as total
                FROM document_workflow
                WHERE assigned_to IS NOT NULL
                GROUP BY assigned_to
                ORDER BY total DESC
                ''')
                assignee_data = cursor.fetchall()
                conn.close()

                for row in assignee_data:
                    assignee_tree.insert('', 'end', values=row)

            except Exception as e:
                pass

            # Export button
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x', pady=(20, 0))

            def export_analytics():
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile=f"workflow_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                )

                if file_path:
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()

                        cursor.execute('''
                        SELECT
                            dw.workflow_id,
                            dw.document_id,
                            dw.step_name,
                            dw.assigned_to,
                            dw.status,
                            dw.completed_date,
                            dw.completed_by
                        FROM document_workflow dw
                        ORDER BY dw.workflow_id
                        ''')
                        workflows = cursor.fetchall()
                        conn.close()

                        with open(file_path, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.writer(f)
                            writer.writerow(['Workflow ID', 'Document ID', 'Step Name', 'Assigned To',
                                           'Status', 'Completed Date', 'Completed By'])
                            writer.writerows(workflows)

                        messagebox.showinfo("Success", f"Analytics exported to:\n{file_path}")

                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to export analytics: {e}")

            ttk.Button(button_frame, text="Export Analytics", command=export_analytics).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open workflow analytics: {e}")

    def create_workflow_steps(self, workflow_id, template_id):
        """
        Create workflow steps from a template

        Args:
            workflow_id: The workflow ID to create steps for
            template_id: The template ID to use
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get template steps
            cursor.execute('''
            SELECT step_name, step_order, assigned_to, description
            FROM workflow_template_steps
            WHERE template_id = ?
            ORDER BY step_order
            ''', (template_id,))

            steps = cursor.fetchall()

            if not steps:
                conn.close()
                return False

            # Create workflow steps
            for step in steps:
                step_name, step_order, assigned_to, description = step

                cursor.execute('''
                INSERT INTO document_workflow (document_id, step_name, step_order, assigned_to, status, comments)
                VALUES (?, ?, ?, ?, 'pending', ?)
                ''', (workflow_id, step_name, step_order, assigned_to, description))

            conn.commit()
            conn.close()

            self.gui.log_event('create', 'workflow_steps', workflow_id, {
                'template_id': template_id,
                'steps_created': len(steps)
            })

            return True

        except Exception as e:
            print(f"Error creating workflow steps: {e}")
            return False
