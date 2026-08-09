"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiPagesMembersMixin:
    def show_members(self):
        """Display member management interface."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.members.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        # Buttons frame
        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text=_t("church.members.add_member"), command=self.add_member,
                  bg="#27ae60", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text=_t("church.members.edit_member"), command=self.edit_member,
                  bg="#3498db", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text=_t("church.members.delete_member"), command=self.delete_member,
                  bg="#e74c3c", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        # Members list
        columns = ("ID", "Name", "Email", "Phone", "Join Date", "Status")
        self.member_tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=15)

        for col in columns:
            self.member_tree.heading(col, text=col)
            self.member_tree.column(col, width=120)

        for i, member in enumerate(self.members, 1):
            self.member_tree.insert("", tk.END, values=(
                i, member['name'], member['email'], member['phone'],
                member['join_date'], member['status']
            ))

        scrollbar = ttk.Scrollbar(self.content_frame, orient=tk.VERTICAL, command=self.member_tree.yview)
        self.member_tree.configure(yscrollcommand=scrollbar.set)

        self.member_tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
