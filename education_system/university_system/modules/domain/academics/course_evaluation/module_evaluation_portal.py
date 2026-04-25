"""
University Module Evaluation Survey Portal
A GUI application for students to evaluate university modules.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import os
from datetime import datetime


class ModuleEvaluationPortal:
    def __init__(self, root):
        self.root = root
        self.root.title("University Module Evaluation Portal")
        self.root.geometry("800x700")
        self.root.configure(bg="#f0f4f8")

        # Data storage
        self.data_file = "survey_responses.json"
        self.current_user = None
        self.current_module = None

        # Sample modules (in a real system, these would come from a database)
        self.modules = {
            "CS101": "Introduction to Computer Science",
            "CS201": "Data Structures & Algorithms",
            "MA102": "Calculus II",
            "EN110": "Academic Writing",
            "PH150": "Physics for Engineers",
            "BS200": "Business Strategy",
            "PS101": "Introduction to Psychology",
            "HI210": "Modern World History",
        }

        # Likert scale options
        self.likert_scale = [
            "Strongly Disagree",
            "Disagree",
            "Neutral",
            "Agree",
            "Strongly Agree",
        ]

        # Evaluation questions
        self.questions = [
            "The module learning objectives were clearly explained.",
            "The content was well-structured and organised.",
            "The lecturer was knowledgeable and engaging.",
            "Assessment methods were fair and appropriate.",
            "Feedback on assignments was timely and helpful.",
            "The workload was reasonable for the credits awarded.",
            "Learning resources (materials, readings) were useful.",
            "I would recommend this module to other students.",
        ]

        self.responses = {}
        self.setup_styles()
        self.show_login_screen()

    def setup_styles(self):
        """Configure ttk styles for a modern look."""
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Title.TLabel",
            font=("Helvetica", 20, "bold"),
            background="#f0f4f8",
            foreground="#1a365d",
        )
        style.configure(
            "Heading.TLabel",
            font=("Helvetica", 14, "bold"),
            background="#f0f4f8",
            foreground="#2d3748",
        )
        style.configure(
            "Body.TLabel",
            font=("Helvetica", 11),
            background="#f0f4f8",
            foreground="#2d3748",
        )
        style.configure(
            "Primary.TButton",
            font=("Helvetica", 11, "bold"),
            padding=10,
        )
        style.configure("TEntry", padding=6)
        style.configure("TCombobox", padding=6)

    def clear_window(self):
        """Remove all widgets from the main window."""
        for widget in self.root.winfo_children():
            widget.destroy()

    # ---------- LOGIN SCREEN ----------
    def show_login_screen(self):
        self.clear_window()

        container = tk.Frame(self.root, bg="#f0f4f8")
        container.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(
            container, text="🎓 University Module Evaluation", style="Title.TLabel"
        ).pack(pady=(0, 10))
        ttk.Label(
            container,
            text="Student Login Portal",
            style="Heading.TLabel",
        ).pack(pady=(0, 30))

        form = tk.Frame(container, bg="#f0f4f8")
        form.pack()

        ttk.Label(form, text="Student ID:", style="Body.TLabel").grid(
            row=0, column=0, sticky="w", pady=8
        )
        self.student_id_entry = ttk.Entry(form, width=30)
        self.student_id_entry.grid(row=0, column=1, padx=10, pady=8)

        ttk.Label(form, text="Full Name:", style="Body.TLabel").grid(
            row=1, column=0, sticky="w", pady=8
        )
        self.student_name_entry = ttk.Entry(form, width=30)
        self.student_name_entry.grid(row=1, column=1, padx=10, pady=8)

        btn_frame = tk.Frame(container, bg="#f0f4f8")
        btn_frame.pack(pady=25)

        ttk.Button(
            btn_frame, text="Login", style="Primary.TButton", command=self.handle_login
        ).pack(side="left", padx=5)
        ttk.Button(
            btn_frame,
            text="View Submissions",
            style="Primary.TButton",
            command=self.view_submissions,
        ).pack(side="left", padx=5)

        # Bind Enter key to login
        self.root.bind("<Return>", lambda e: self.handle_login())

    def handle_login(self):
        student_id = self.student_id_entry.get().strip()
        name = self.student_name_entry.get().strip()

        if not student_id or not name:
            messagebox.showerror(
                "Login Error", "Please enter both Student ID and Full Name."
            )
            return

        if not student_id.isalnum():
            messagebox.showerror(
                "Login Error", "Student ID must be alphanumeric (no spaces/symbols)."
            )
            return

        self.current_user = {"id": student_id, "name": name}
        self.root.unbind("<Return>")
        self.show_module_selection()

    # ---------- MODULE SELECTION ----------
    def show_module_selection(self):
        self.clear_window()

        header = tk.Frame(self.root, bg="#1a365d", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text=f"Welcome, {self.current_user['name']}",
            font=("Helvetica", 14, "bold"),
            bg="#1a365d",
            fg="white",
        ).pack(side="left", padx=20, pady=20)

        tk.Button(
            header,
            text="Logout",
            font=("Helvetica", 10),
            bg="#e53e3e",
            fg="white",
            bd=0,
            padx=15,
            pady=6,
            cursor="hand2",
            command=self.show_login_screen,
        ).pack(side="right", padx=20, pady=20)

        body = tk.Frame(self.root, bg="#f0f4f8")
        body.pack(fill="both", expand=True, padx=40, pady=30)

        ttk.Label(
            body, text="Select a Module to Evaluate", style="Title.TLabel"
        ).pack(pady=(0, 20))

        ttk.Label(
            body,
            text="Choose the module you wish to provide feedback for:",
            style="Body.TLabel",
        ).pack(pady=(0, 15))

        module_options = [f"{code} — {name}" for code, name in self.modules.items()]
        self.module_var = tk.StringVar()
        module_combo = ttk.Combobox(
            body,
            textvariable=self.module_var,
            values=module_options,
            state="readonly",
            width=50,
            font=("Helvetica", 11),
        )
        module_combo.pack(pady=10)
        module_combo.current(0)

        ttk.Button(
            body,
            text="Start Evaluation →",
            style="Primary.TButton",
            command=self.start_evaluation,
        ).pack(pady=30)

    def start_evaluation(self):
        selected = self.module_var.get()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a module.")
            return
        code = selected.split(" — ")[0]
        self.current_module = {"code": code, "name": self.modules[code]}
        self.show_evaluation_form()

    # ---------- EVALUATION FORM ----------
    def show_evaluation_form(self):
        self.clear_window()
        self.responses = {}

        # Header
        header = tk.Frame(self.root, bg="#1a365d", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text=f"Evaluating: {self.current_module['code']} — {self.current_module['name']}",
            font=("Helvetica", 13, "bold"),
            bg="#1a365d",
            fg="white",
            wraplength=700,
        ).pack(side="left", padx=20, pady=20)

        # Scrollable area
        canvas = tk.Canvas(self.root, bg="#f0f4f8", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#f0f4f8")

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=(30, 0), pady=20)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        ttk.Label(
            scroll_frame,
            text="Please rate the following statements:",
            style="Heading.TLabel",
        ).pack(anchor="w", pady=(0, 15))

        # Questions with Likert scale
        self.question_vars = []
        for i, question in enumerate(self.questions, 1):
            q_frame = tk.Frame(scroll_frame, bg="white", relief="flat", bd=1)
            q_frame.pack(fill="x", pady=8, padx=5)

            tk.Label(
                q_frame,
                text=f"Q{i}. {question}",
                font=("Helvetica", 11, "bold"),
                bg="white",
                fg="#2d3748",
                wraplength=650,
                justify="left",
            ).pack(anchor="w", padx=15, pady=(12, 8))

            var = tk.StringVar(value="")
            self.question_vars.append(var)

            options_frame = tk.Frame(q_frame, bg="white")
            options_frame.pack(anchor="w", padx=15, pady=(0, 12))

            for option in self.likert_scale:
                tk.Radiobutton(
                    options_frame,
                    text=option,
                    variable=var,
                    value=option,
                    bg="white",
                    font=("Helvetica", 10),
                    activebackground="white",
                    selectcolor="#e6f0ff",
                ).pack(side="left", padx=4)

        # Overall rating
        rating_frame = tk.Frame(scroll_frame, bg="white", bd=1)
        rating_frame.pack(fill="x", pady=15, padx=5)

        tk.Label(
            rating_frame,
            text="Overall Module Rating (1 = Poor, 5 = Excellent):",
            font=("Helvetica", 11, "bold"),
            bg="white",
            fg="#2d3748",
        ).pack(anchor="w", padx=15, pady=(12, 8))

        self.rating_var = tk.IntVar(value=0)
        rating_buttons = tk.Frame(rating_frame, bg="white")
        rating_buttons.pack(anchor="w", padx=15, pady=(0, 12))
        for i in range(1, 6):
            tk.Radiobutton(
                rating_buttons,
                text=f"★ {i}",
                variable=self.rating_var,
                value=i,
                bg="white",
                font=("Helvetica", 11),
                activebackground="white",
                selectcolor="#fff9db",
            ).pack(side="left", padx=8)

        # Comments box
        comments_frame = tk.Frame(scroll_frame, bg="white", bd=1)
        comments_frame.pack(fill="x", pady=15, padx=5)

        tk.Label(
            comments_frame,
            text="Additional Comments (optional):",
            font=("Helvetica", 11, "bold"),
            bg="white",
            fg="#2d3748",
        ).pack(anchor="w", padx=15, pady=(12, 8))

        self.comments_text = scrolledtext.ScrolledText(
            comments_frame, height=5, font=("Helvetica", 10), wrap="word"
        )
        self.comments_text.pack(fill="x", padx=15, pady=(0, 12))

        # Buttons
        btn_frame = tk.Frame(scroll_frame, bg="#f0f4f8")
        btn_frame.pack(pady=20)

        ttk.Button(
            btn_frame,
            text="← Back",
            style="Primary.TButton",
            command=self.show_module_selection,
        ).pack(side="left", padx=5)
        ttk.Button(
            btn_frame,
            text="Submit Evaluation",
            style="Primary.TButton",
            command=self.submit_evaluation,
        ).pack(side="left", padx=5)

    def submit_evaluation(self):
        # Validate all questions answered
        for i, var in enumerate(self.question_vars, 1):
            if not var.get():
                messagebox.showwarning(
                    "Incomplete Form",
                    f"Please answer question {i} before submitting.",
                )
                return

        if self.rating_var.get() == 0:
            messagebox.showwarning(
                "Incomplete Form", "Please provide an overall rating."
            )
            return

        # Confirm submission
        if not messagebox.askyesno(
            "Confirm Submission",
            "Are you sure you want to submit? You cannot edit after submission.",
        ):
            return

        # Build response record
        response = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "student_id": self.current_user["id"],
            "student_name": self.current_user["name"],
            "module_code": self.current_module["code"],
            "module_name": self.current_module["name"],
            "answers": {
                f"Q{i+1}": var.get() for i, var in enumerate(self.question_vars)
            },
            "overall_rating": self.rating_var.get(),
            "comments": self.comments_text.get("1.0", "end").strip(),
        }

        self.save_response(response)
        self.show_thank_you()

    def save_response(self, response):
        """Save response to a JSON file."""
        data = []
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, IOError):
                data = []
        data.append(response)
        try:
            with open(self.data_file, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            messagebox.showerror("Save Error", f"Could not save response: {e}")

    # ---------- THANK YOU SCREEN ----------
    def show_thank_you(self):
        self.clear_window()

        container = tk.Frame(self.root, bg="#f0f4f8")
        container.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            container,
            text="✓",
            font=("Helvetica", 60, "bold"),
            bg="#f0f4f8",
            fg="#38a169",
        ).pack()

        ttk.Label(
            container, text="Thank You!", style="Title.TLabel"
        ).pack(pady=10)

        ttk.Label(
            container,
            text="Your evaluation has been submitted successfully.",
            style="Body.TLabel",
        ).pack(pady=5)
        ttk.Label(
            container,
            text="Your feedback helps us improve teaching and learning.",
            style="Body.TLabel",
        ).pack(pady=5)

        btn_frame = tk.Frame(container, bg="#f0f4f8")
        btn_frame.pack(pady=30)

        ttk.Button(
            btn_frame,
            text="Evaluate Another Module",
            style="Primary.TButton",
            command=self.show_module_selection,
        ).pack(side="left", padx=5)
        ttk.Button(
            btn_frame,
            text="Logout",
            style="Primary.TButton",
            command=self.show_login_screen,
        ).pack(side="left", padx=5)

    # ---------- VIEW SUBMISSIONS (Admin) ----------
    def view_submissions(self):
        if not os.path.exists(self.data_file):
            messagebox.showinfo("No Data", "No submissions have been recorded yet.")
            return

        try:
            with open(self.data_file, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            messagebox.showerror("Error", "Could not read submissions file.")
            return

        if not data:
            messagebox.showinfo("No Data", "No submissions have been recorded yet.")
            return

        # Create new window
        win = tk.Toplevel(self.root)
        win.title("Submitted Evaluations")
        win.geometry("750x550")
        win.configure(bg="#f0f4f8")

        tk.Label(
            win,
            text=f"All Submissions ({len(data)} total)",
            font=("Helvetica", 16, "bold"),
            bg="#f0f4f8",
            fg="#1a365d",
        ).pack(pady=15)

        # Summary stats
        if data:
            avg_rating = sum(r["overall_rating"] for r in data) / len(data)
            tk.Label(
                win,
                text=f"Average Overall Rating: {avg_rating:.2f} / 5",
                font=("Helvetica", 11, "italic"),
                bg="#f0f4f8",
                fg="#2d3748",
            ).pack(pady=5)

        text_area = scrolledtext.ScrolledText(
            win, font=("Courier", 10), wrap="word", bg="white"
        )
        text_area.pack(fill="both", expand=True, padx=20, pady=10)

        for i, r in enumerate(data, 1):
            text_area.insert("end", f"{'='*70}\n")
            text_area.insert("end", f"Submission #{i}  |  {r['timestamp']}\n")
            text_area.insert(
                "end", f"Student: {r['student_name']} (ID: {r['student_id']})\n"
            )
            text_area.insert(
                "end", f"Module: {r['module_code']} — {r['module_name']}\n"
            )
            text_area.insert("end", f"Overall Rating: {r['overall_rating']}/5\n")
            text_area.insert("end", f"\nResponses:\n")
            for q, a in r["answers"].items():
                text_area.insert("end", f"  {q}: {a}\n")
            if r.get("comments"):
                text_area.insert("end", f"\nComments: {r['comments']}\n")
            text_area.insert("end", "\n")

        text_area.configure(state="disabled")


def main():
    root = tk.Tk()
    app = ModuleEvaluationPortal(root)
    root.mainloop()


if __name__ == "__main__":
    main()
