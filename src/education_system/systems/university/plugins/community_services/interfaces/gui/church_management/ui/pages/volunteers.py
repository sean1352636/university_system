"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiPagesVolunteersMixin:
    def show_volunteers(self):
        """Display volunteer management interface."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.volunteers.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text=_t("church.volunteers.add_volunteer"), command=self.add_volunteer,
                  bg="#27ae60", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        # Volunteers list
        columns = ("ID", "Name", "Ministry", "Role", "Phone", "Email", "Availability")
        self.volunteer_tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=12)

        for col in columns:
            self.volunteer_tree.heading(col, text=col)
            self.volunteer_tree.column(col, width=110)

        for i, vol in enumerate(self.volunteers, 1):
            self.volunteer_tree.insert("", tk.END, values=(
                i, vol['name'], vol['ministry'], vol['role'],
                vol['phone'], vol['email'], vol['availability']
            ))

        self.volunteer_tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
