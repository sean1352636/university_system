"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiPagesSmallGroupsMixin:
    def show_small_groups(self):
        """Display small groups management."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.small_groups.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text=_t("church.small_groups.add_group"),
                  command=self.add_small_group,
                  bg="#27ae60", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        columns = ("ID", "Group Name", "Leader", "Meeting Day", "Location", "Members")
        tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=12)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=130)

        for i, group in enumerate(self.small_groups, 1):
            tree.insert("", tk.END, values=(
                i, group['name'], group['leader'], group['meeting_day'],
                group['location'], group.get('member_count', 0)
            ))

        tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
