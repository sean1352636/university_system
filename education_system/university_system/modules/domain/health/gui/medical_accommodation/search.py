# search.py
# Search functionality mixin for AccommodationGUI.

from ._common import (
    tk, messagebox, sqlite3,
    CLI_AVAILABLE, get_connection,
)


class SearchMixin:
    """Search and filter methods for AccommodationGUI."""

    def perform_search(self):
        """Perform search based on criteria"""
        if not CLI_AVAILABLE:
            return

        try:
            # Clear search results
            for item in self.search_tree.get_children():
                self.search_tree.delete(item)

            # Build query
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                query = '''
                    SELECT a.id, a.student_id, a.accommodation_type, a.description,
                           a.start_date, a.end_date, a.status, a.created_at,
                           s.first_name, s.last_name, s.email_address
                    FROM accommodations a
                    LEFT JOIN students s ON a.student_id = s.student_id
                '''

                where_clauses = []
                params = []

                # Add search criteria
                if self.search_student_id.get().strip():
                    where_clauses.append('a.student_id = ?')
                    params.append(self.search_student_id.get().strip())

                if self.search_type.get().strip():
                    where_clauses.append('a.accommodation_type = ?')
                    params.append(self.search_type.get().strip())

                if self.search_status.get().strip():
                    where_clauses.append('a.status = ?')
                    params.append(self.search_status.get().strip())

                if self.search_start_date.get().strip():
                    where_clauses.append('a.start_date >= ?')
                    params.append(self.search_start_date.get().strip())

                if self.search_end_date.get().strip():
                    where_clauses.append('a.end_date <= ?')
                    params.append(self.search_end_date.get().strip())

                if self.search_keyword.get().strip():
                    where_clauses.append('(a.description LIKE ? OR a.notes LIKE ?)')
                    keyword = f"%{self.search_keyword.get().strip()}%"
                    params.extend([keyword, keyword])

                if where_clauses:
                    query += ' WHERE ' + ' AND '.join(where_clauses)

                query += ' ORDER BY a.id DESC'

                cursor.execute(query, params)
                results = cursor.fetchall()

                # Populate search results
                for acc in results:
                    name = f"{acc['first_name'] or ''} {acc['last_name'] or ''}".strip() or 'N/A'

                    self.search_tree.insert('', 'end', values=(
                        acc['id'],
                        acc['student_id'],
                        name,
                        acc['accommodation_type'],
                        acc['start_date'] or 'N/A',
                        acc['end_date'] or 'N/A',
                        acc['status'],
                        acc['description'] or 'N/A'
                    ))

                self.status_var.set(f"Found {len(results)} matching accommodations")

        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {str(e)}")

    def clear_search(self):
        """Clear all search criteria"""
        self.search_student_id.delete(0, tk.END)
        self.search_type.set('')
        self.search_status.set('')
        self.search_start_date.delete(0, tk.END)
        self.search_end_date.delete(0, tk.END)
        self.search_keyword.delete(0, tk.END)

        # Clear search results
        for item in self.search_tree.get_children():
            self.search_tree.delete(item)

        self.status_var.set("Search criteria cleared")
