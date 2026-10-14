"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiPagesSermonsMixin:
    def show_sermons(self):
        """Display sermon management interface."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.sermons.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text=_t("church.sermons.add_sermon"), command=self.add_sermon,
                  bg="#27ae60", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        # Sermons list
        columns = ("ID", "Title", "Speaker", "Date", "Scripture", "Series")
        self.sermon_tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=12)

        for col in columns:
            self.sermon_tree.heading(col, text=col)
            self.sermon_tree.column(col, width=130)

        for i, sermon in enumerate(self.sermons, 1):
            self.sermon_tree.insert("", tk.END, values=(
                i, sermon['title'], sermon['speaker'],
                sermon['date'], sermon['scripture'], sermon.get('series', '')
            ))

        self.sermon_tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
