"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiPagesPrayerRequestsMixin:
    def show_prayer_requests(self):
        """Display prayer requests interface."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.prayer_requests.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text=_t("church.prayer_requests.add_request"), command=self.add_prayer_request,
                  bg="#27ae60", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text=_t("church.prayer_requests.mark_answered"), command=self.mark_prayer_answered,
                  bg="#9b59b6", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        # Prayer requests list
        columns = ("ID", "Requested By", "Request", "Date", "Status")
        self.prayer_tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=12)

        for col in columns:
            self.prayer_tree.heading(col, text=col)
            self.prayer_tree.column(col, width=150)

        for i, prayer in enumerate(self.prayer_requests, 1):
            self.prayer_tree.insert("", tk.END, values=(
                i, prayer['requested_by'], prayer['request'][:40],
                prayer['date'], prayer['status']
            ))

        self.prayer_tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

    def mark_prayer_answered(self):
        """Mark a prayer request as answered."""
        selection = self.prayer_tree.selection()
        if not selection:
            messagebox.showwarning(_t("church.common.warning"), _t("church.errors.select_prayer"))
            return

        item = self.prayer_tree.item(selection[0])
        idx = int(item['values'][0]) - 1

        self.prayer_requests[idx]['status'] = "Answered"
        self.save_data()
        messagebox.showinfo(_t("church.prayer_requests.praise_god"), _t("church.prayer_requests.success_answered"))
        self.show_prayer_requests()
