"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiPagesExpensesMixin:
    def show_expenses(self):
        """Display expense tracking."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.expenses.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        total = sum(e['amount'] for e in self.expenses)
        tk.Label(self.content_frame, text=_t("church.expenses.total_expenses", amount=f"£{total:,.2f}"),
                font=("Arial", 18, "bold"), bg="white", fg="#e74c3c").pack()

        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text=_t("church.expenses.add_expense"),
                  command=self.add_expense,
                  bg="#e74c3c", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        columns = ("ID", "Description", "Amount", "Category", "Date", "Approved By")
        tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=12)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=130)

        for i, expense in enumerate(self.expenses, 1):
            tree.insert("", tk.END, values=(
                i, expense['description'], f"£{expense['amount']:,.2f}",
                expense['category'], expense['date'], expense.get('approved_by', '')
            ))

        tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
