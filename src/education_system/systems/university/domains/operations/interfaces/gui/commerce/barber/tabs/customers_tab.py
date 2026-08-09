"""Barber Shop GUI - Customers tab creation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.domains.operations.interfaces.gui.commerce.barber.common import tk, ttk


class CustomersTabMixin:
    """Mixin that creates the customers management tab."""

    def create_customers_tab(self):
        """Create the customers management tab."""
        customers_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(customers_frame, text=_t('gui.operations.commerce.barber.tabs.customers_tab.tabs.customers', default="Customers"))

        # Search frame
        search_frame = ttk.LabelFrame(customers_frame, text=_t('gui.operations.commerce.barber.tabs.customers_tab.labels.search_customers', default="Search Customers"), padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text=_t('gui.operations.commerce.barber.tabs.customers_tab.labels.search', default="Search:")).pack(side=tk.LEFT)
        self.customer_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.customer_search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text=_t('gui.operations.commerce.barber.tabs.customers_tab.buttons.search', default="Search"), command=self.search_customers).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text=_t('gui.operations.commerce.barber.tabs.customers_tab.buttons.show_all', default="Show All"), command=self._load_customers).pack(side=tk.LEFT, padx=5)

        # Customer list
        list_frame = ttk.LabelFrame(customers_frame, text=_t('gui.operations.commerce.barber.tabs.customers_tab.labels.customer_list', default="Customer List"), padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('id', 'name', 'email', 'phone', 'visits', 'last_visit', 'favorite')
        self.customers_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        self.customers_tree.heading('id', text=_t('gui.operations.commerce.barber.tabs.customers_tab.headings.id', default='ID'))
        self.customers_tree.heading('name', text=_t('gui.operations.commerce.barber.tabs.customers_tab.headings.name', default='Name'))
        self.customers_tree.heading('email', text=_t('gui.operations.commerce.barber.tabs.customers_tab.headings.email', default='Email'))
        self.customers_tree.heading('phone', text=_t('gui.operations.commerce.barber.tabs.customers_tab.headings.phone', default='Phone'))
        self.customers_tree.heading('visits', text=_t('gui.operations.commerce.barber.tabs.customers_tab.headings.visits', default='Visits'))
        self.customers_tree.heading('last_visit', text=_t('gui.operations.commerce.barber.tabs.customers_tab.headings.last_visit', default='Last Visit'))
        self.customers_tree.heading('favorite', text=_t('gui.operations.commerce.barber.tabs.customers_tab.headings.favorite', default='Favorite'))

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

        ttk.Button(action_frame, text=_t('gui.operations.commerce.barber.tabs.customers_tab.buttons.create_profile', default="Create Profile"), command=self.create_customer_profile).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text=_t('gui.operations.commerce.barber.tabs.customers_tab.buttons.view_details', default="View Details"), command=self.view_customer_details).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text=_t('gui.operations.commerce.barber.tabs.customers_tab.buttons.add_notes', default="Add Notes"), command=self.add_customer_notes).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text=_t('gui.operations.commerce.barber.tabs.customers_tab.buttons.view_favorites', default="View Favorites"), command=self.view_favorite_customers).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text=_t('gui.operations.commerce.barber.tabs.customers_tab.buttons.send_message', default="Send Message"), command=self.send_customer_message).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text=_t('gui.operations.commerce.barber.tabs.customers_tab.buttons.view_feedback', default="View Feedback"), command=self.view_customer_feedback).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text=_t('gui.operations.commerce.barber.tabs.customers_tab.buttons.merge_profiles', default="Merge Profiles"), command=self.merge_customer_profiles).pack(side=tk.LEFT, padx=3)

        # Import/Export buttons
        action_frame2 = ttk.Frame(customers_frame)
        action_frame2.pack(fill=tk.X, pady=2)

        ttk.Button(action_frame2, text=_t('gui.operations.commerce.barber.tabs.customers_tab.buttons.export_list', default="Export List"), command=self.export_customer_list).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame2, text=_t('gui.operations.commerce.barber.tabs.customers_tab.buttons.import_customers', default="Import Customers"), command=self.import_customers).pack(side=tk.LEFT, padx=3)
