"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import bulk_operations_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def create_student_groups(self):
    """Create student groups from search results"""
    if not self.search_results:
        messagebox.showwarning(_t("advanced_search.bulk_operations.no_results_title"), _t("advanced_search.bulk_operations.no_results_available"))
        return

    dialog = tk.Toplevel(self.master)
    dialog.title(f"👥 {_t('advanced_search.create_groups_dialog_title')}")
    dialog.geometry("400x350")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t("advanced_search.bulk_operations.create_groups_title", count=len(self.search_results)),
             style='Title.TLabel').pack(pady=(0, 20))

    # Grouping method
    ttk.Label(frame, text=_t("advanced_search.bulk_operations.grouping_method")).pack(anchor='w')
    method_var = tk.StringVar(value=_t('gui.shell.advanced_search.bulk_operations_parts.create_student_groups.values.course', default="course"))

    methods = [
        (_t("advanced_search.bulk_operations.group_by_course"), "course"),
        (_t("advanced_search.bulk_operations.group_by_age_range"), "age"),
        (_t("advanced_search.bulk_operations.random_assignment"), "random"),
        (_t("advanced_search.bulk_operations.alphabetical_order"), "alpha"),
    ]

    for text, value in methods:
        ttk.Radiobutton(frame, text=text, variable=method_var, value=value).pack(anchor='w', pady=2)

    # Additional options
    options_frame = ttk.LabelFrame(frame, text=_t("advanced_search.bulk_operations.options_label"), padding="10")
    options_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Label(options_frame, text=_t("advanced_search.bulk_operations.group_size_label")).pack(anchor='w')
    size_var = tk.StringVar(value="5")
    ttk.Entry(options_frame, textvariable=size_var, width=10).pack(anchor='w')

    def create_groups():
        method = method_var.get()
        groups = {}

        if method == "course":
            for student in self.search_results:
                course = student[9]  # course field
                if course not in groups:
                    groups[course] = []
                groups[course].append(student)

        elif method == "age":
            for student in self.search_results:
                age = student[8]  # age field
                if age < 20:
                    age_group = "Under 20"
                elif age <= 25:
                    age_group = "20-25"
                elif age <= 30:
                    age_group = "26-30"
                else:
                    age_group = "Over 30"

                if age_group not in groups:
                    groups[age_group] = []
                groups[age_group].append(student)

        elif method == "random":
            import random
            try:
                group_size = int(size_var.get())
                students_copy = self.search_results.copy()
                random.shuffle(students_copy)

                for i, student in enumerate(students_copy):
                    group_name = f"Group {(i // group_size) + 1}"
                    if group_name not in groups:
                        groups[group_name] = []
                    groups[group_name].append(student)
            except ValueError:
                messagebox.showerror(_t("advanced_search.bulk_operations.invalid_size_title"), _t("advanced_search.bulk_operations.invalid_size_msg"))
                return

        elif method == "alpha":
            try:
                group_size = int(size_var.get())
                sorted_students = sorted(self.search_results, key=lambda x: f"{x[3]} {x[5]}")

                for i in range(0, len(sorted_students), group_size):
                    group_name = f"Group {(i // group_size) + 1}"
                    groups[group_name] = sorted_students[i:i+group_size]
            except ValueError:
                messagebox.showerror(_t("advanced_search.bulk_operations.invalid_size_title"), _t("advanced_search.bulk_operations.invalid_size_msg"))
                return

        # Show groups result
        self.show_groups_result(groups)
        dialog.destroy()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Button(button_frame, text=f"👥 {_t('advanced_search.bulk_operations.create_groups_btn')}", command=create_groups).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
