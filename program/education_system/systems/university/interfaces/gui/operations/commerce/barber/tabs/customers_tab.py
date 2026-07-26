"""Barber Shop GUI - Customers tab creation."""

from education_system.systems.university.interfaces.gui.operations.commerce.barber.common import tk, ttk


class CustomersTabMixin:
    """Mixin that creates the customers management tab."""

    def create_customers_tab(self):
        """Create the customers management tab."""
        customers_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(customers_frame, text="Customers")

        # Search frame
        search_frame = ttk.LabelFrame(customers_frame, text="Search Customers", padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.customer_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.customer_search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Search", command=self.search_customers).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Show All", command=self._load_customers).pack(side=tk.LEFT, padx=5)

        # Customer list
        list_frame = ttk.LabelFrame(customers_frame, text="Customer List", padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('id', 'name', 'email', 'phone', 'visits', 'last_visit', 'favorite')
        self.customers_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        self.customers_tree.heading('id', text='ID')
        self.customers_tree.heading('name', text='Name')
        self.customers_tree.heading('email', text='Email')
        self.customers_tree.heading('phone', text='Phone')
        self.customers_tree.heading('visits', text='Visits')
        self.customers_tree.heading('last_visit', text='Last Visit')
        self.customers_tree.heading('favorite', text='Favorite')

        self.customers_tree.column('id', width=50)
        self.customers_tree.column('name', width=150)
        self.customers_tree.column('email', width=180)
        self.customers_tree.column('phone', width=120)
        self.customers_tree.column('visits', width=60)
        self.customers_tree.column('last_visit', width=100)
        self.customers_tree.column('favorite', width=70)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.customers_tree.yview)
        self.customers_tree.configure(yscrollcommand=scrollbar.set)

        self.customers_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons
        action_frame = ttk.Frame(customers_frame)
        action_frame.pack(fill=tk.X, pady=5)

        ttk.Button(action_frame, text="Create Profile", command=self.create_customer_profile).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="View Details", command=self.view_customer_details).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Add Notes", command=self.add_customer_notes).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="View Favorites", command=self.view_favorite_customers).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Send Message", command=self.send_customer_message).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="View Feedback", command=self.view_customer_feedback).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Merge Profiles", command=self.merge_customer_profiles).pack(side=tk.LEFT, padx=3)

        # Import/Export buttons
        action_frame2 = ttk.Frame(customers_frame)
        action_frame2.pack(fill=tk.X, pady=2)

        ttk.Button(action_frame2, text="Export List", command=self.export_customer_list).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame2, text="Import Customers", command=self.import_customers).pack(side=tk.LEFT, padx=3)
