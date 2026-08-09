"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiPagesAttendanceMixin:
    def show_attendance(self):
        """Display attendance tracking interface."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.attendance.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        tk.Label(self.content_frame, text=_t("church.attendance.description"),
                font=("Arial", 12), bg="white", fg="gray").pack()

        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=20)

        tk.Button(btn_frame, text=_t("church.attendance.record_attendance"),
                  command=self.record_attendance,
                  bg="#27ae60", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        # Attendance history
        columns = ("Date", "Service", "Adults", "Children", "Total", "Notes")
        tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=10)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)

        for record in self.attendance_records:
            tree.insert("", tk.END, values=(
                record['date'], record['service'], record['adults'],
                record['children'], record['adults'] + record['children'], record.get('notes', '')
            ))

        tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
