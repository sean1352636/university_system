import tkinter as tk
from tkinter import ttk, scrolledtext


class SearchMixin:
    """Mixin for chat history search functionality."""

    def create_search_functionality(self):
        """Create chat history search functionality"""
        def show_search_dialog():
            search_window = tk.Toplevel(self.root)
            search_window.title("Search Chat History")
            search_window.geometry("500x400")

            # Search input
            search_frame = ttk.Frame(search_window)
            search_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
            search_entry = ttk.Entry(search_frame, width=30)
            search_entry.pack(side=tk.LEFT, padx=(5, 10), fill=tk.X, expand=True)

            def perform_search():
                query = search_entry.get().strip().lower()
                if not query:
                    return

                results_text.delete(1.0, tk.END)
                results_text.insert(1.0, f"Search results for: '{query}'\n" + "="*50 + "\n\n")

                # Search through conversation history
                found_count = 0
                if hasattr(self.chatbot, 'conversation_history'):
                    for username, history in self.chatbot.conversation_history.items():
                        for conv in history:
                            message = conv.get('message', '').lower()
                            response = conv.get('response', '').lower()

                            if query in message or query in response:
                                found_count += 1
                                timestamp = conv.get('timestamp', 'Unknown')
                                results_text.insert(tk.END, f"[{timestamp}] {username}:\n")
                                results_text.insert(tk.END, f"Q: {conv.get('message', '')}\n")
                                results_text.insert(tk.END, f"A: {conv.get('response', '')}\n\n")

                if found_count == 0:
                    results_text.insert(tk.END, "No results found.")
                else:
                    results_text.insert(1.0, f"Found {found_count} results\n\n")

            ttk.Button(search_frame, text="Search", command=perform_search).pack(side=tk.LEFT)

            # Results display
            results_text = scrolledtext.ScrolledText(search_window, height=20)
            results_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Bind Enter key to search
            search_entry.bind('<Return>', lambda e: perform_search())
            search_entry.focus()

        return show_search_dialog
