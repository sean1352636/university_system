"""
Feedback & Suggestion Box GUI Interface

Provides graphical interface for:
- Submitting feedback and suggestions
- Browsing and voting on suggestions
- Tracking submission status and responses
- Viewing impact metrics
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional, List, Dict, Any
from education_system.systems.university.domain.operations.communications.feedback.services.feedback_service import FeedbackService
from education_system.systems.university.infrastructure.shared_context import get_auth


class FeedbackGUI:
    """GUI interface for feedback and suggestion system"""

    def __init__(self, parent=None):
        """Initialize the GUI"""
        self.service = FeedbackService()
        self.auth = get_auth()
        if not self.auth or not getattr(self.auth, "current_user", None):
            try:
                from tkinter import messagebox
                messagebox.showerror(
                    "Login required",
                    "You must be logged in via the main GUI to use Feedback.",
                )
            except Exception:
                pass
            raise PermissionError("Feedback GUI requires an authenticated user")

        # When ``parent`` is a workspace tab Frame (passed by
        # ``open_in_workspace``), embed inside it directly. Frames
        # have no ``wm_title``; Tk/Toplevel do.
        if parent is None:
            self.root = tk.Tk()
            self.root.title("Feedback & Suggestion Box")
            self.root.geometry("1200x800")
            self.is_standalone = True
        elif not hasattr(parent, "wm_title"):
            self.root = parent
            self.is_standalone = False
        else:
            self.root = tk.Toplevel(parent)
            self.root.title("Feedback & Suggestion Box")
            self.root.geometry("1200x800")
            self.is_standalone = False

        self.current_user = None
        if self.auth.current_user:
            self.current_user = self.auth.get_current_user()

        self.current_filter_category = None
        self.current_filter_status = None
        self.current_sort = "votes"
        self.my_votes = []

        self._load_user_votes()
        self._setup_ui()
        self._load_data()

    def _load_user_votes(self):
        """Load user's votes"""
        if self.current_user:
            user_id = self.current_user.get('user_id')
            self.my_votes = self.service.get_user_votes(user_id)

    def _setup_ui(self):
        """Setup the user interface"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        title_label = ttk.Label(
            header_frame,
            text="Feedback & Suggestion Box",
            font=("Arial", 18, "bold")
        )
        title_label.pack(side=tk.LEFT)

        if self.current_user:
            user_label = ttk.Label(
                header_frame,
                text=f"Logged in as: {self.current_user.get('username', 'User')}",
                font=("Arial", 10)
            )
            user_label.pack(side=tk.RIGHT)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.rowconfigure(1, weight=1)
        main_frame.columnconfigure(0, weight=1)

        # Create tabs
        self._create_browse_tab()
        self._create_trending_tab()
        self._create_submit_tab()
        self._create_my_submissions_tab()
        self._create_implemented_tab()
        self._create_stats_tab()

        if self._is_admin():
            self._create_admin_tab()

    def _create_browse_tab(self):
        """Create browse suggestions tab"""
        browse_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(browse_frame, text="Browse Suggestions")

        # Filter controls
        filter_frame = ttk.LabelFrame(browse_frame, text="Filters", padding="5")
        filter_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # Category filter
        ttk.Label(filter_frame, text="Category:").grid(row=0, column=0, padx=5)
        categories = ["All"] + [cat['name'] for cat in self.service.get_categories()]
        self.category_var = tk.StringVar(value="All")
        category_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.category_var,
            values=categories,
            state="readonly",
            width=15
        )
        category_combo.grid(row=0, column=1, padx=5)
        category_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_filters())

        # Status filter
        ttk.Label(filter_frame, text="Status:").grid(row=0, column=2, padx=5)
        statuses = ["All", "Submitted", "Under Review", "Planned", "In Progress", "Implemented", "Declined"]
        self.status_var = tk.StringVar(value="All")
        status_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.status_var,
            values=statuses,
            state="readonly",
            width=15
        )
        status_combo.grid(row=0, column=3, padx=5)
        status_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_filters())

        # Sort options
        ttk.Label(filter_frame, text="Sort by:").grid(row=0, column=4, padx=5)
        sorts = ["Most Votes", "Most Recent", "Recently Updated"]
        self.sort_var = tk.StringVar(value="Most Votes")
        sort_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.sort_var,
            values=sorts,
            state="readonly",
            width=15
        )
        sort_combo.grid(row=0, column=5, padx=5)
        sort_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_filters())

        # Search
        ttk.Label(filter_frame, text="Search:").grid(row=0, column=6, padx=5)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_frame, textvariable=self.search_var, width=20)
        search_entry.grid(row=0, column=7, padx=5)
        ttk.Button(
            filter_frame,
            text="Search",
            command=self._search_submissions
        ).grid(row=0, column=8, padx=5)

        # Suggestions list
        list_frame = ttk.Frame(browse_frame)
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        browse_frame.rowconfigure(1, weight=1)
        browse_frame.columnconfigure(0, weight=1)

        # Create treeview
        columns = ("ID", "Title", "Category", "Status", "Votes", "Date")
        self.browse_tree = ttk.Treeview(list_frame, columns=columns, show="tree headings", height=20)

        # Define column headings
        self.browse_tree.heading("#0", text="")
        self.browse_tree.heading("ID", text="ID")
        self.browse_tree.heading("Title", text="Title")
        self.browse_tree.heading("Category", text="Category")
        self.browse_tree.heading("Status", text="Status")
        self.browse_tree.heading("Votes", text="Votes")
        self.browse_tree.heading("Date", text="Date")

        # Define column widths
        self.browse_tree.column("#0", width=30)
        self.browse_tree.column("ID", width=50)
        self.browse_tree.column("Title", width=400)
        self.browse_tree.column("Category", width=100)
        self.browse_tree.column("Status", width=120)
        self.browse_tree.column("Votes", width=80)
        self.browse_tree.column("Date", width=150)

        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.browse_tree.yview)
        self.browse_tree.configure(yscrollcommand=scrollbar.set)

        self.browse_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        # Bind double-click
        self.browse_tree.bind('<Double-1>', lambda e: self._view_selected_submission(self.browse_tree))

        # Action buttons
        btn_frame = ttk.Frame(browse_frame)
        btn_frame.grid(row=2, column=0, pady=(10, 0))

        ttk.Button(
            btn_frame,
            text="View Details",
            command=lambda: self._view_selected_submission(self.browse_tree)
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="Upvote",
            command=lambda: self._upvote_selected(self.browse_tree)
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="Refresh",
            command=self._load_data
        ).pack(side=tk.LEFT, padx=5)

    def _create_trending_tab(self):
        """Create trending suggestions tab"""
        trending_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(trending_frame, text="Trending")

        # Header
        header = ttk.Label(
            trending_frame,
            text="Trending Suggestions",
            font=("Arial", 14, "bold")
        )
        header.grid(row=0, column=0, pady=(0, 10))

        desc = ttk.Label(
            trending_frame,
            text="Most popular suggestions with recent activity",
            font=("Arial", 10)
        )
        desc.grid(row=1, column=0, pady=(0, 10))

        # Trending list
        list_frame = ttk.Frame(trending_frame)
        list_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        trending_frame.rowconfigure(2, weight=1)
        trending_frame.columnconfigure(0, weight=1)

        columns = ("ID", "Title", "Category", "Votes", "Status", "Responses")
        self.trending_tree = ttk.Treeview(list_frame, columns=columns, show="tree headings", height=15)

        self.trending_tree.heading("#0", text="")
        self.trending_tree.heading("ID", text="ID")
        self.trending_tree.heading("Title", text="Title")
        self.trending_tree.heading("Category", text="Category")
        self.trending_tree.heading("Votes", text="Votes")
        self.trending_tree.heading("Status", text="Status")
        self.trending_tree.heading("Responses", text="Responses")

        self.trending_tree.column("#0", width=30)
        self.trending_tree.column("ID", width=50)
        self.trending_tree.column("Title", width=500)
        self.trending_tree.column("Category", width=100)
        self.trending_tree.column("Votes", width=80)
        self.trending_tree.column("Status", width=120)
        self.trending_tree.column("Responses", width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.trending_tree.yview)
        self.trending_tree.configure(yscrollcommand=scrollbar.set)

        self.trending_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.trending_tree.bind('<Double-1>', lambda e: self._view_selected_submission(self.trending_tree))

        # Buttons
        btn_frame = ttk.Frame(trending_frame)
        btn_frame.grid(row=3, column=0, pady=(10, 0))

        ttk.Button(
            btn_frame,
            text="View Details",
            command=lambda: self._view_selected_submission(self.trending_tree)
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="Upvote",
            command=lambda: self._upvote_selected(self.trending_tree)
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="Refresh",
            command=self._load_trending
        ).pack(side=tk.LEFT, padx=5)

    def _create_submit_tab(self):
        """Create submission form tab"""
        submit_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(submit_frame, text="Submit New")

        # Check login
        if not self.current_user:
            ttk.Label(
                submit_frame,
                text="You must be logged in to submit feedback or suggestions.",
                font=("Arial", 12)
            ).pack(pady=50)
            return

        # Type selection
        type_frame = ttk.LabelFrame(submit_frame, text="Type", padding="10")
        type_frame.pack(fill=tk.X, pady=(0, 10))

        self.submit_type_var = tk.StringVar(value="suggestion")
        ttk.Radiobutton(
            type_frame,
            text="Suggestion (Public, votable)",
            variable=self.submit_type_var,
            value="suggestion"
        ).pack(anchor=tk.W)
        ttk.Radiobutton(
            type_frame,
            text="Feedback (Private, direct to admin)",
            variable=self.submit_type_var,
            value="feedback"
        ).pack(anchor=tk.W)

        # Category
        category_frame = ttk.LabelFrame(submit_frame, text="Category", padding="10")
        category_frame.pack(fill=tk.X, pady=(0, 10))

        categories = [cat['name'] for cat in self.service.get_categories()]
        self.submit_category_var = tk.StringVar(value=categories[0] if categories else "")
        category_combo = ttk.Combobox(
            category_frame,
            textvariable=self.submit_category_var,
            values=categories,
            state="readonly",
            width=30
        )
        category_combo.pack(fill=tk.X)

        # Title
        title_frame = ttk.LabelFrame(submit_frame, text="Title", padding="10")
        title_frame.pack(fill=tk.X, pady=(0, 10))

        self.submit_title_var = tk.StringVar()
        title_entry = ttk.Entry(title_frame, textvariable=self.submit_title_var, width=80)
        title_entry.pack(fill=tk.X)

        # Description
        desc_frame = ttk.LabelFrame(submit_frame, text="Description", padding="10")
        desc_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.submit_desc_text = scrolledtext.ScrolledText(desc_frame, height=10, wrap=tk.WORD)
        self.submit_desc_text.pack(fill=tk.BOTH, expand=True)

        # Options
        options_frame = ttk.Frame(submit_frame)
        options_frame.pack(fill=tk.X, pady=(0, 10))

        self.submit_anonymous_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            options_frame,
            text="Submit anonymously",
            variable=self.submit_anonymous_var
        ).pack(anchor=tk.W)

        # Submit button
        ttk.Button(
            submit_frame,
            text="Submit",
            command=self._submit_new,
            style="Accent.TButton"
        ).pack(pady=10)

    def _create_my_submissions_tab(self):
        """Create my submissions tab"""
        my_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(my_frame, text="My Submissions")

        if not self.current_user:
            ttk.Label(
                my_frame,
                text="You must be logged in to view your submissions.",
                font=("Arial", 12)
            ).pack(pady=50)
            return

        # Header
        header = ttk.Label(
            my_frame,
            text="My Submissions",
            font=("Arial", 14, "bold")
        )
        header.grid(row=0, column=0, pady=(0, 10))

        # List
        list_frame = ttk.Frame(my_frame)
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        my_frame.rowconfigure(1, weight=1)
        my_frame.columnconfigure(0, weight=1)

        columns = ("ID", "Type", "Title", "Category", "Status", "Votes", "Date")
        self.my_tree = ttk.Treeview(list_frame, columns=columns, show="tree headings", height=15)

        self.my_tree.heading("#0", text="")
        self.my_tree.heading("ID", text="ID")
        self.my_tree.heading("Type", text="Type")
        self.my_tree.heading("Title", text="Title")
        self.my_tree.heading("Category", text="Category")
        self.my_tree.heading("Status", text="Status")
        self.my_tree.heading("Votes", text="Votes")
        self.my_tree.heading("Date", text="Date")

        self.my_tree.column("#0", width=30)
        self.my_tree.column("ID", width=50)
        self.my_tree.column("Type", width=100)
        self.my_tree.column("Title", width=350)
        self.my_tree.column("Category", width=100)
        self.my_tree.column("Status", width=120)
        self.my_tree.column("Votes", width=80)
        self.my_tree.column("Date", width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.my_tree.yview)
        self.my_tree.configure(yscrollcommand=scrollbar.set)

        self.my_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.my_tree.bind('<Double-1>', lambda e: self._view_selected_submission(self.my_tree))

        # Buttons
        btn_frame = ttk.Frame(my_frame)
        btn_frame.grid(row=2, column=0, pady=(10, 0))

        ttk.Button(
            btn_frame,
            text="View Details",
            command=lambda: self._view_selected_submission(self.my_tree)
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="Refresh",
            command=self._load_my_submissions
        ).pack(side=tk.LEFT, padx=5)

    def _create_implemented_tab(self):
        """Create implemented suggestions tab"""
        impl_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(impl_frame, text="Implemented")

        # Header
        header = ttk.Label(
            impl_frame,
            text="Implemented Suggestions",
            font=("Arial", 14, "bold")
        )
        header.grid(row=0, column=0, pady=(0, 10))

        desc = ttk.Label(
            impl_frame,
            text="See what ideas have been brought to life!",
            font=("Arial", 10)
        )
        desc.grid(row=1, column=0, pady=(0, 10))

        # List
        list_frame = ttk.Frame(impl_frame)
        list_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        impl_frame.rowconfigure(2, weight=1)
        impl_frame.columnconfigure(0, weight=1)

        columns = ("ID", "Title", "Category", "Votes", "Impl Date", "Users", "Impact")
        self.impl_tree = ttk.Treeview(list_frame, columns=columns, show="tree headings", height=15)

        self.impl_tree.heading("#0", text="")
        self.impl_tree.heading("ID", text="ID")
        self.impl_tree.heading("Title", text="Title")
        self.impl_tree.heading("Category", text="Category")
        self.impl_tree.heading("Votes", text="Votes")
        self.impl_tree.heading("Impl Date", text="Implemented")
        self.impl_tree.heading("Users", text="Users Affected")
        self.impl_tree.heading("Impact", text="Impact")

        self.impl_tree.column("#0", width=30)
        self.impl_tree.column("ID", width=50)
        self.impl_tree.column("Title", width=350)
        self.impl_tree.column("Category", width=100)
        self.impl_tree.column("Votes", width=80)
        self.impl_tree.column("Impl Date", width=120)
        self.impl_tree.column("Users", width=120)
        self.impl_tree.column("Impact", width=300)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.impl_tree.yview)
        self.impl_tree.configure(yscrollcommand=scrollbar.set)

        self.impl_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.impl_tree.bind('<Double-1>', lambda e: self._view_selected_submission(self.impl_tree))

        # Buttons
        btn_frame = ttk.Frame(impl_frame)
        btn_frame.grid(row=3, column=0, pady=(10, 0))

        ttk.Button(
            btn_frame,
            text="View Details",
            command=lambda: self._view_selected_submission(self.impl_tree)
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="Refresh",
            command=self._load_implemented
        ).pack(side=tk.LEFT, padx=5)

    def _create_stats_tab(self):
        """Create statistics tab"""
        stats_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(stats_frame, text="Statistics")

        # Header
        header = ttk.Label(
            stats_frame,
            text="Feedback System Statistics",
            font=("Arial", 14, "bold")
        )
        header.pack(pady=(0, 20))

        # Stats display
        self.stats_text = scrolledtext.ScrolledText(stats_frame, height=30, wrap=tk.WORD)
        self.stats_text.pack(fill=tk.BOTH, expand=True)

        # Refresh button
        ttk.Button(
            stats_frame,
            text="Refresh Statistics",
            command=self._load_statistics
        ).pack(pady=10)

    def _create_admin_tab(self):
        """Create admin management tab"""
        admin_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(admin_frame, text="Admin")

        # Header
        header = ttk.Label(
            admin_frame,
            text="Administrative Functions",
            font=("Arial", 14, "bold")
        )
        header.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # Response section
        response_frame = ttk.LabelFrame(admin_frame, text="Respond to Submission", padding="10")
        response_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))

        ttk.Label(response_frame, text="Submission ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.admin_response_id_var = tk.StringVar()
        ttk.Entry(response_frame, textvariable=self.admin_response_id_var, width=15).grid(
            row=0, column=1, sticky=tk.W, pady=5
        )

        ttk.Label(response_frame, text="Response:").grid(row=1, column=0, sticky=tk.NW, pady=5)
        self.admin_response_text = scrolledtext.ScrolledText(response_frame, height=8, width=50)
        self.admin_response_text.grid(row=1, column=1, pady=5)

        ttk.Button(
            response_frame,
            text="Submit Response",
            command=self._admin_add_response
        ).grid(row=2, column=1, pady=5)

        # Status update section
        status_frame = ttk.LabelFrame(admin_frame, text="Update Status", padding="10")
        status_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))

        ttk.Label(status_frame, text="Submission ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.admin_status_id_var = tk.StringVar()
        ttk.Entry(status_frame, textvariable=self.admin_status_id_var, width=15).grid(
            row=0, column=1, sticky=tk.W, pady=5
        )

        ttk.Label(status_frame, text="New Status:").grid(row=1, column=0, sticky=tk.W, pady=5)
        statuses = ["Submitted", "Under Review", "Planned", "In Progress", "Implemented", "Declined"]
        self.admin_status_var = tk.StringVar(value=statuses[0])
        ttk.Combobox(
            status_frame,
            textvariable=self.admin_status_var,
            values=statuses,
            state="readonly",
            width=20
        ).grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Label(status_frame, text="Notes:").grid(row=2, column=0, sticky=tk.NW, pady=5)
        self.admin_status_notes = scrolledtext.ScrolledText(status_frame, height=5, width=50)
        self.admin_status_notes.grid(row=2, column=1, pady=5)

        ttk.Button(
            status_frame,
            text="Update Status",
            command=self._admin_update_status
        ).grid(row=3, column=1, pady=5)

        admin_frame.rowconfigure(1, weight=1)
        admin_frame.columnconfigure(0, weight=1)
        admin_frame.columnconfigure(1, weight=1)

    def _load_data(self):
        """Load all data"""
        self._load_browse_data()
        self._load_trending()
        self._load_my_submissions()
        self._load_implemented()
        self._load_statistics()

    def _load_browse_data(self):
        """Load browse tab data"""
        # Clear existing
        for item in self.browse_tree.get_children():
            self.browse_tree.delete(item)

        # Get filters
        category = self.category_var.get()
        if category == "All":
            category = None

        status = self.status_var.get()
        if status == "All":
            status = None

        sort_map = {
            "Most Votes": "votes",
            "Most Recent": "date",
            "Recently Updated": "updated"
        }
        sort_by = sort_map.get(self.sort_var.get(), "votes")

        # Load submissions
        submissions = self.service.get_submissions(
            submission_type='suggestion',
            category=category,
            status=status,
            sort_by=sort_by,
            limit=100
        )

        # Populate tree
        for sub in submissions:
            icon = "▲" if sub['id'] in self.my_votes else ""
            self.browse_tree.insert(
                "",
                tk.END,
                text=icon,
                values=(
                    sub['id'],
                    sub['title'],
                    sub['category'],
                    sub['status'],
                    sub['votes'],
                    sub['created_at']
                ),
                tags=('voted' if sub['id'] in self.my_votes else '',)
            )

        # Tag styling
        self.browse_tree.tag_configure('voted', foreground='green')

    def _load_trending(self):
        """Load trending tab data"""
        for item in self.trending_tree.get_children():
            self.trending_tree.delete(item)

        trending = self.service.get_trending_suggestions(limit=20)

        for sub in trending:
            icon = "▲" if sub['id'] in self.my_votes else ""
            self.trending_tree.insert(
                "",
                tk.END,
                text=icon,
                values=(
                    sub['id'],
                    sub['title'],
                    sub['category'],
                    sub['votes'],
                    sub['status'],
                    sub['response_count']
                ),
                tags=('voted' if sub['id'] in self.my_votes else '',)
            )

        self.trending_tree.tag_configure('voted', foreground='green')

    def _load_my_submissions(self):
        """Load my submissions tab data"""
        if not self.current_user:
            return

        for item in self.my_tree.get_children():
            self.my_tree.delete(item)

        user_id = self.current_user.get('user_id')
        submissions = self.service.get_user_submissions(user_id)

        for sub in submissions:
            self.my_tree.insert(
                "",
                tk.END,
                values=(
                    sub['id'],
                    sub['type'].title(),
                    sub['title'],
                    sub['category'],
                    sub['status'],
                    sub['votes'],
                    sub['created_at']
                )
            )

    def _load_implemented(self):
        """Load implemented tab data"""
        for item in self.impl_tree.get_children():
            self.impl_tree.delete(item)

        implemented = self.service.get_implemented_suggestions(limit=50)

        for sub in implemented:
            impact_desc = sub.get('impact_description', '')
            if not impact_desc and sub.get('users_affected'):
                impact_desc = f"{sub['users_affected']} users affected"

            self.impl_tree.insert(
                "",
                tk.END,
                values=(
                    sub['id'],
                    sub['title'],
                    sub['category'],
                    sub['votes'],
                    sub.get('implementation_date', 'N/A'),
                    sub.get('users_affected', 'N/A'),
                    impact_desc
                )
            )

    def _load_statistics(self):
        """Load statistics"""
        stats = self.service.get_statistics()

        self.stats_text.delete('1.0', tk.END)

        text = f"""FEEDBACK SYSTEM STATISTICS
{'=' * 60}

OVERVIEW
--------
Total Submissions: {stats['total_submissions']}
  - Feedback: {stats['total_feedback']}
  - Suggestions: {stats['total_suggestions']}

Total Votes Cast: {stats['total_votes']}
Average Votes per Submission: {stats['average_votes']}
Total Administrative Responses: {stats['total_responses']}

SUBMISSIONS BY STATUS
---------------------
"""
        for status, count in stats['by_status'].items():
            text += f"{status}: {count}\n"

        text += "\nSUBMISSIONS BY CATEGORY\n"
        text += "-" * 25 + "\n"
        for category, count in stats['by_category'].items():
            text += f"{category}: {count}\n"

        text += f"\nIMPLEMENTED SUGGESTIONS: {stats['implemented_count']}\n"

        self.stats_text.insert('1.0', text)

    def _apply_filters(self):
        """Apply filters and reload data"""
        self._load_browse_data()

    def _search_submissions(self):
        """Search submissions"""
        search_term = self.search_var.get().strip()

        if not search_term:
            messagebox.showwarning("Search", "Please enter a search term.")
            return

        # Clear tree
        for item in self.browse_tree.get_children():
            self.browse_tree.delete(item)

        # Search
        results = self.service.search_submissions(search_term, limit=100)

        if not results:
            messagebox.showinfo("Search", f"No results found for '{search_term}'.")
            return

        # Populate
        for sub in results:
            icon = "▲" if sub['id'] in self.my_votes else ""
            self.browse_tree.insert(
                "",
                tk.END,
                text=icon,
                values=(
                    sub['id'],
                    sub['title'],
                    sub['category'],
                    sub['status'],
                    sub['votes'],
                    sub['created_at']
                ),
                tags=('voted' if sub['id'] in self.my_votes else '',)
            )

    def _submit_new(self):
        """Submit new feedback/suggestion"""
        if not self.current_user:
            messagebox.showerror("Error", "You must be logged in to submit.")
            return

        submission_type = self.submit_type_var.get()
        category = self.submit_category_var.get()
        title = self.submit_title_var.get().strip()
        description = self.submit_desc_text.get('1.0', tk.END).strip()
        is_anonymous = self.submit_anonymous_var.get()

        if not title:
            messagebox.showwarning("Validation", "Please enter a title.")
            return

        if not description:
            messagebox.showwarning("Validation", "Please enter a description.")
            return

        try:
            user_id = self.current_user.get('user_id')
            submission_id = self.service.submit_feedback(
                user_id=user_id,
                category=category,
                title=title,
                description=description,
                is_anonymous=is_anonymous,
                feedback_type=submission_type
            )

            messagebox.showinfo(
                "Success",
                f"{submission_type.title()} submitted successfully!\nID: {submission_id}"
            )

            # Clear form
            self.submit_title_var.set("")
            self.submit_desc_text.delete('1.0', tk.END)
            self.submit_anonymous_var.set(False)

            # Reload data
            self._load_data()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to submit: {e}")

    def _view_selected_submission(self, tree):
        """View details of selected submission"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Selection", "Please select a submission to view.")
            return

        item = tree.item(selection[0])
        submission_id = item['values'][0]

        self._show_submission_details(submission_id)

    def _show_submission_details(self, submission_id: int):
        """Show submission details in a dialog"""
        details = self.service.get_submission_details(submission_id)

        if not details:
            messagebox.showerror("Error", "Submission not found.")
            return

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Submission #{submission_id}")
        dialog.geometry("800x600")

        # Main frame
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(
            main_frame,
            text=details['title'],
            font=("Arial", 14, "bold"),
            wraplength=750
        )
        title_label.pack(pady=(0, 10))

        # Info frame
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        info_text = f"Category: {details['category']} | Status: {details['status']} | "
        info_text += f"Votes: {details['votes']} | Type: {details['type'].title()}"
        ttk.Label(info_frame, text=info_text).pack()

        date_text = f"Created: {details['created_at']} | Updated: {details['updated_at']}"
        ttk.Label(info_frame, text=date_text, font=("Arial", 9)).pack()

        # Description
        desc_frame = ttk.LabelFrame(main_frame, text="Description", padding="10")
        desc_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        desc_text = scrolledtext.ScrolledText(desc_frame, height=10, wrap=tk.WORD)
        desc_text.insert('1.0', details['description'])
        desc_text.config(state=tk.DISABLED)
        desc_text.pack(fill=tk.BOTH, expand=True)

        # Responses
        if details.get('responses'):
            resp_frame = ttk.LabelFrame(main_frame, text="Responses", padding="10")
            resp_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

            resp_text = scrolledtext.ScrolledText(resp_frame, height=8, wrap=tk.WORD)
            for resp in details['responses']:
                resp_text.insert(tk.END, f"From: {resp['responder_name']} ({resp['created_at']})\n")
                resp_text.insert(tk.END, f"{resp['response_text']}\n")
                resp_text.insert(tk.END, "-" * 70 + "\n\n")
            resp_text.config(state=tk.DISABLED)
            resp_text.pack(fill=tk.BOTH, expand=True)

        # Action buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)

        if self.current_user and details['type'] == 'suggestion':
            user_id = self.current_user.get('user_id')
            has_voted = self.service.has_user_voted(submission_id, user_id)

            if has_voted:
                ttk.Button(
                    btn_frame,
                    text="Remove Vote",
                    command=lambda: self._remove_vote_and_close(submission_id, dialog)
                ).pack(side=tk.LEFT, padx=5)
            else:
                ttk.Button(
                    btn_frame,
                    text="Upvote",
                    command=lambda: self._upvote_and_close(submission_id, dialog)
                ).pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _upvote_selected(self, tree):
        """Upvote selected submission"""
        if not self.current_user:
            messagebox.showwarning("Login Required", "You must be logged in to vote.")
            return

        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Selection", "Please select a submission to upvote.")
            return

        item = tree.item(selection[0])
        submission_id = item['values'][0]

        self._upvote_submission(submission_id)

    def _upvote_submission(self, submission_id: int):
        """Upvote a submission"""
        user_id = self.current_user.get('user_id')

        if self.service.has_user_voted(submission_id, user_id):
            messagebox.showinfo("Already Voted", "You have already voted for this submission.")
            return

        if self.service.upvote_submission(submission_id, user_id):
            messagebox.showinfo("Success", "Vote added!")
            self.my_votes.append(submission_id)
            self._load_data()
        else:
            messagebox.showerror("Error", "Failed to add vote.")

    def _upvote_and_close(self, submission_id: int, dialog):
        """Upvote and close dialog"""
        self._upvote_submission(submission_id)
        dialog.destroy()

    def _remove_vote_and_close(self, submission_id: int, dialog):
        """Remove vote and close dialog"""
        user_id = self.current_user.get('user_id')

        if self.service.remove_vote(submission_id, user_id):
            messagebox.showinfo("Success", "Vote removed.")
            if submission_id in self.my_votes:
                self.my_votes.remove(submission_id)
            self._load_data()
        else:
            messagebox.showerror("Error", "Failed to remove vote.")

        dialog.destroy()

    def _admin_add_response(self):
        """Admin: Add response"""
        submission_id = self.admin_response_id_var.get().strip()
        response_text = self.admin_response_text.get('1.0', tk.END).strip()

        if not submission_id or not submission_id.isdigit():
            messagebox.showwarning("Validation", "Please enter a valid submission ID.")
            return

        if not response_text:
            messagebox.showwarning("Validation", "Please enter a response.")
            return

        try:
            responder_id = self.current_user.get('user_id')
            responder_name = self.current_user.get('username', 'Administrator')

            response_id = self.service.add_response(
                int(submission_id), responder_id, responder_name, response_text
            )

            messagebox.showinfo("Success", f"Response added! (ID: {response_id})")

            # Clear form
            self.admin_response_id_var.set("")
            self.admin_response_text.delete('1.0', tk.END)

            # Reload data
            self._load_data()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to add response: {e}")

    def _admin_update_status(self):
        """Admin: Update status"""
        submission_id = self.admin_status_id_var.get().strip()
        new_status = self.admin_status_var.get()
        notes = self.admin_status_notes.get('1.0', tk.END).strip()

        if not submission_id or not submission_id.isdigit():
            messagebox.showwarning("Validation", "Please enter a valid submission ID.")
            return

        try:
            updated_by = self.current_user.get('username', 'Administrator')

            success = self.service.update_status(
                int(submission_id), new_status, updated_by, notes if notes else None
            )

            if success:
                messagebox.showinfo("Success", "Status updated!")

                # Clear form
                self.admin_status_id_var.set("")
                self.admin_status_notes.delete('1.0', tk.END)

                # Reload data
                self._load_data()
            else:
                messagebox.showerror("Error", "Failed to update status.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update status: {e}")

    def _is_admin(self) -> bool:
        """Check if current user is admin"""
        if not self.current_user:
            return False
        role = self.current_user.get('role', '').lower()
        return role in ['admin', 'administrator']

    def run(self):
        """Run the GUI"""
        if self.is_standalone:
            self.root.mainloop()


def main():
    """Main entry point"""
    from education_system.systems.university.interfaces.gui.shell.auth.launch_guard import (
        require_launcher_auth,
    )
    if require_launcher_auth("Feedback GUI") is None:
        return
    app = FeedbackGUI()
    app.run()


if __name__ == '__main__':
    main()
