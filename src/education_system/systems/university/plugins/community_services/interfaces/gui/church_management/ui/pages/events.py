"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiPagesEventsMixin:
    def show_events(self):
        """Display event management interface."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.events.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text=_t("church.events.add_event"), command=self.add_event,
                  bg="#27ae60", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        # Events list
        columns = ("ID", "Event Name", "Date", "Time", "Location", "Description")
        self.event_tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=12)

        for col in columns:
            self.event_tree.heading(col, text=col)
            self.event_tree.column(col, width=130)

        for i, event in enumerate(self.events, 1):
            self.event_tree.insert("", tk.END, values=(
                i, event['name'], event['date'], event['time'],
                event['location'], event.get('description', '')[:30]
            ))

        self.event_tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
