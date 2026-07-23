import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime


class MedicalHistoryMixin:
    """Mixin for medical history view and management."""

    def create_view_medical_history(self):
        """View and manage medical history"""
        content_frame = ttk.Frame(self.content_area)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        title_label = ttk.Label(content_frame, text="Medical History",
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))

        add_frame = ttk.LabelFrame(content_frame, text="Add Medical History Record", padding=15)
        add_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(add_frame, text="Condition:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.condition_name = ttk.Entry(add_frame, width=30)
        self.condition_name.grid(row=0, column=1, sticky=tk.W, padx=(10, 20), pady=5)

        ttk.Label(add_frame, text="Date:").grid(row=0, column=2, sticky=tk.W, pady=5)
        self.condition_date = ttk.Entry(add_frame, width=15)
        self.condition_date.grid(row=0, column=3, sticky=tk.W, padx=(10, 20), pady=5)
        self.condition_date.insert(0, datetime.now().strftime('%Y-%m-%d'))

        ttk.Button(add_frame, text="Add Record",
                  command=self.add_medical_history_record).grid(row=0, column=4)

        history_frame = ttk.LabelFrame(content_frame, text="Medical History Records", padding=15)
        history_frame.pack(fill=tk.BOTH, expand=True)

        self.medical_history_text = scrolledtext.ScrolledText(history_frame, wrap=tk.WORD, height=15)
        self.medical_history_text.pack(fill=tk.BOTH, expand=True)

        self.load_medical_history_display()

    def add_medical_history_record(self):
        """Add a new medical history record"""
        if not self.condition_name.get().strip():
            messagebox.showerror("Validation Error", "Condition name is required.")
            return

        try:
            history_info = f"Condition: {self.condition_name.get()}\n"
            history_info += f"Date: {self.condition_date.get()}\n"
            history_info += f"Recorded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            history_info += "Status: Active\n"
            history_info += "-" * 40 + "\n"

            self.medical_history_text.insert(tk.END, history_info)

            self.condition_name.delete(0, tk.END)
            self.condition_date.delete(0, tk.END)
            self.condition_date.insert(0, datetime.now().strftime('%Y-%m-%d'))

            messagebox.showinfo("Success", "Medical history record added successfully!")
            self.log_audit_event('add_medical_history', 'medical_history', self.condition_name.get())

        except Exception as e:
            messagebox.showerror("Error", f"Failed to add medical history record: {str(e)}")

    def load_medical_history_display(self):
        """Load and display medical history"""
        try:
            empty_state_text = "MEDICAL HISTORY\n"
            empty_state_text += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            empty_state_text += "=" * 50 + "\n\n"
            empty_state_text += "No medical history records are loaded for this session.\n"
            empty_state_text += "Use the form above to add a new medical record.\n"

            self.medical_history_text.insert(tk.END, empty_state_text)
        except Exception as e:
            self.medical_history_text.insert(tk.END, f"Error loading medical history: {str(e)}")
