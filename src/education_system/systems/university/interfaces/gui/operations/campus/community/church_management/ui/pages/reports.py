"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiPagesReportsMixin:
    def show_reports(self):
        """Display reports overview with option to view full report in new window."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.reports.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        # Quick Stats Overview
        stats_frame = tk.Frame(self.content_frame, bg="white")
        stats_frame.pack(pady=20)

        total_donations = sum(d['amount'] for d in self.donations)
        total_expenses = sum(e['amount'] for e in self.expenses)
        balance = total_donations - total_expenses

        stats = [
            (_t("church.reports.total_donations", amount=""), f"£{total_donations:,.2f}", "#27ae60"),
            (_t("church.reports.total_expenses", amount=""), f"£{total_expenses:,.2f}", "#e74c3c"),
            (_t("church.reports.net_balance", amount=""), f"£{balance:,.2f}", "#27ae60" if balance >= 0 else "#e74c3c"),
            (_t("church.reports.total_members", count=""), str(len(self.members)), "#3498db"),
        ]

        for i, (label, value, color) in enumerate(stats):
            stat_card = tk.Frame(stats_frame, bg=color, relief=tk.RAISED, bd=2)
            stat_card.grid(row=0, column=i, padx=10, pady=10, ipadx=20, ipady=15)
            tk.Label(stat_card, text=label.replace(": ", "").replace(":", ""), font=("Arial", 10), bg=color, fg="white").pack()
            tk.Label(stat_card, text=value, font=("Arial", 18, "bold"), bg=color, fg="white").pack()

        # Description
        tk.Label(self.content_frame, text=_t("church.reports.view_full_description"),
                font=("Arial", 11), bg="white", fg="gray").pack(pady=20)

        # Button to open full report in new window
        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=20)

        tk.Button(btn_frame, text=_t("church.reports.view_full_report"), command=self.open_report_window,
                  bg="#4a4a8a", fg="white", font=("Arial", 12, "bold"), width=25, height=2,
                  cursor="hand2").pack()

    def open_report_window(self):
        """Open the full report in a separate window with save and send options."""
        report_window = tk.Toplevel(self.root)
        report_window.title(_t("church.reports.window_title"))
        report_window.geometry("800x700")
        report_window.configure(bg="white")

        # Header
        header = tk.Frame(report_window, bg="#4a4a8a", height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="✝ " + _t("church.reports.report_header"),
                font=("Georgia", 18, "bold"), bg="#4a4a8a", fg="white").pack(pady=20)

        # Report content in scrollable text area
        content_frame = tk.Frame(report_window, bg="white")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        text_scrollbar = ttk.Scrollbar(content_frame)
        text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.report_text = tk.Text(content_frame, wrap=tk.WORD, font=("Courier", 11),
                                   yscrollcommand=text_scrollbar.set, bg="#f9f9f9")
        self.report_text.pack(fill=tk.BOTH, expand=True)
        text_scrollbar.config(command=self.report_text.yview)

        # Generate report content
        report_content = self.generate_report_text()
        self.report_text.insert(tk.END, report_content)
        self.report_text.config(state=tk.DISABLED)

        # Buttons frame
        btn_frame = tk.Frame(report_window, bg="white")
        btn_frame.pack(fill=tk.X, padx=20, pady=15)

        tk.Button(btn_frame, text=_t("church.reports.save_as_txt"), command=self.save_report_as_txt,
                  bg="#27ae60", fg="white", font=("Arial", 11), width=18,
                  cursor="hand2").pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text=_t("church.reports.send_to_admin"), command=self.send_report_to_admin,
                  bg="#3498db", fg="white", font=("Arial", 11), width=18,
                  cursor="hand2").pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text=_t("church.common.close"), command=report_window.destroy,
                  bg="#95a5a6", fg="white", font=("Arial", 11), width=12,
                  cursor="hand2").pack(side=tk.RIGHT, padx=5)

        # Store reference for save/send functions
        self.report_window = report_window
