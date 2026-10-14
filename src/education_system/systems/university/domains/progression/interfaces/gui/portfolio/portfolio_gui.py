"""
Portfolio GUI Interface - Achievement & Portfolio System

Professional Tkinter-based GUI for managing student portfolios,
achievements, badges, skills, endorsements, and resumes.
"""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from typing import Optional
from datetime import datetime

from education_system.systems.university.domains.progression.domain.portfolio.services.portfolio_service import PortfolioService
from education_system.systems.university.infrastructure.shared_context import get_auth


def _has_session(auth) -> bool:
    """True when ``auth`` carries a logged-in user this GUI can key off."""
    return isinstance(getattr(auth, "current_user", None), dict)


def _resolve_auth(auth=None):
    """Prefer the caller's session; fall back to the process-wide one.

    ``get_auth()`` is not a session: it hands back whichever ``UserAuth`` was
    seeded at bootstrap, which is created *before* login and so can carry no
    ``current_user`` at all — and in a subprocess launch it raises outright.
    Taking it as gospel is what made this screen report "Please log in first"
    to a user who was plainly logged in.
    """
    if _has_session(auth):
        return auth
    try:
        fallback = get_auth()
    except Exception:
        logger.debug("shared-context auth unavailable", exc_info=True)
        fallback = None
    return fallback if _has_session(fallback) else (auth or fallback)


class PortfolioGUI:
    """
    GUI interface for portfolio management.

    Features:
    - Portfolio builder with tabbed interface
    - Badge showcase with verification
    - Skills matrix with endorsements
    - Project/item cards
    - Resume preview
    - Public profile editor
    - Statistics dashboard
    """

    def __init__(self, parent=None, auth=None):
        """Initialize GUI."""
        self.service = PortfolioService()
        self.auth = _resolve_auth(auth)

        # When ``parent`` is a workspace tab Frame (passed by
        # ``open_in_workspace``), embed inside it. Frames have no
        # ``wm_title``; Tk/Toplevel do.
        if parent is None:
            self.root = tk.Tk()
        elif not hasattr(parent, "wm_title"):
            self.root = parent
        else:
            self.root = tk.Toplevel(parent)

        if hasattr(self.root, "wm_title"):
            self.root.title(_t('gui.progression.portfolio.portfolio.windows.achievement_portfolio_system', default="Achievement & Portfolio System"))
            self.root.geometry("1200x800")

        self.student_id = None
        self.portfolio = None

        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        """Setup the user interface."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Header
        self.create_header(main_frame)

        # Tabbed interface
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        # Create tabs
        self.create_overview_tab()
        self.create_portfolio_tab()
        self.create_skills_tab()
        self.create_badges_tab()
        self.create_endorsements_tab()
        self.create_resume_tab()
        self.create_settings_tab()

    def create_header(self, parent):
        """Create header with student info and stats."""
        header_frame = ttk.LabelFrame(parent, text=_t('gui.progression.portfolio.portfolio.labels.portfolio_dashboard', default="Portfolio Dashboard"), padding="10")
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # Student info
        self.student_label = ttk.Label(header_frame, text="", font=("Arial", 14, "bold"))
        self.student_label.grid(row=0, column=0, columnspan=2, sticky=tk.W)

        # Stats
        stats_frame = ttk.Frame(header_frame)
        stats_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))

        self.completeness_label = ttk.Label(stats_frame, text=_t('gui.progression.portfolio.portfolio.labels.completeness_0', default="Completeness: 0%"))
        self.completeness_label.grid(row=0, column=0, padx=(0, 20))

        self.items_label = ttk.Label(stats_frame, text=_t('gui.progression.portfolio.portfolio.labels.items_0', default="Items: 0"))
        self.items_label.grid(row=0, column=1, padx=(0, 20))

        self.skills_label = ttk.Label(stats_frame, text=_t('gui.progression.portfolio.portfolio.labels.skills_0', default="Skills: 0"))
        self.skills_label.grid(row=0, column=2, padx=(0, 20))

        self.badges_label = ttk.Label(stats_frame, text=_t('gui.progression.portfolio.portfolio.labels.badges_0', default="Badges: 0"))
        self.badges_label.grid(row=0, column=3, padx=(0, 20))

        self.views_label = ttk.Label(stats_frame, text=_t('gui.progression.portfolio.portfolio.labels.views_0', default="Views: 0"))
        self.views_label.grid(row=0, column=4)

    def create_overview_tab(self):
        """Create overview/statistics tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.progression.portfolio.portfolio.tabs.overview', default="Overview"))

        # Main stats
        stats_frame = ttk.LabelFrame(tab, text=_t('gui.progression.portfolio.portfolio.labels.portfolio_statistics', default="Portfolio Statistics"), padding="10")
        stats_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)

        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)

        # Stats text area
        self.stats_text = scrolledtext.ScrolledText(stats_frame, height=20, width=80, wrap=tk.WORD)
        self.stats_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        stats_frame.columnconfigure(0, weight=1)
        stats_frame.rowconfigure(0, weight=1)

        # Buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=10, pady=10)

        ttk.Button(btn_frame, text=_t('gui.progression.portfolio.portfolio.buttons.refresh_stats', default="Refresh Stats"), command=self.refresh_stats).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text=_t('gui.progression.portfolio.portfolio.buttons.share_portfolio', default="Share Portfolio"), command=self.share_portfolio).grid(row=0, column=1, padx=5)

    def create_portfolio_tab(self):
        """Create portfolio items management tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.progression.portfolio.portfolio.tabs.portfolio_items', default="Portfolio Items"))

        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        # Controls
        controls_frame = ttk.Frame(tab)
        controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=10, pady=10)

        ttk.Label(controls_frame, text=_t('gui.progression.portfolio.portfolio.labels.filter', default="Filter:")).grid(row=0, column=0)
        self.category_filter = ttk.Combobox(controls_frame, values=[
            "All", "Projects", "Research", "Leadership", "Work Experience",
            "Awards", "Certifications", "Publications", "Presentations"
        ], state="readonly", width=20)
        self.category_filter.set("All")
        self.category_filter.grid(row=0, column=1, padx=5)
        self.category_filter.bind("<<ComboboxSelected>>", lambda e: self.load_portfolio_items())

        ttk.Button(controls_frame, text=_t('gui.progression.portfolio.portfolio.buttons.add_item', default="Add Item"), command=self.add_portfolio_item).grid(row=0, column=2, padx=5)
        ttk.Button(controls_frame, text=_t('gui.progression.portfolio.portfolio.buttons.edit_item', default="Edit Item"), command=self.edit_portfolio_item).grid(row=0, column=3, padx=5)
        ttk.Button(controls_frame, text=_t('gui.progression.portfolio.portfolio.buttons.delete_item', default="Delete Item"), command=self.delete_portfolio_item).grid(row=0, column=4, padx=5)

        # Items list with scrollbar
        list_frame = ttk.Frame(tab)
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        self.items_tree = ttk.Treeview(list_frame, columns=("Category", "Title", "Organization", "Date", "Featured"),
                                       show="headings", yscrollcommand=scrollbar.set)
        self.items_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.config(command=self.items_tree.yview)

        self.items_tree.heading("Category", text=_t('gui.progression.portfolio.portfolio.headings.category', default="Category"))
        self.items_tree.heading("Title", text=_t('gui.progression.portfolio.portfolio.headings.title', default="Title"))
        self.items_tree.heading("Organization", text=_t('gui.progression.portfolio.portfolio.headings.organization', default="Organization"))
        self.items_tree.heading("Date", text=_t('gui.progression.portfolio.portfolio.headings.date', default="Date"))
        self.items_tree.heading("Featured", text=_t('gui.progression.portfolio.portfolio.headings.featured', default="Featured"))

        self.items_tree.column("Category", width=120)
        self.items_tree.column("Title", width=250)
        self.items_tree.column("Organization", width=200)
        self.items_tree.column("Date", width=150)
        self.items_tree.column("Featured", width=80)

        self.items_tree.bind("<Double-1>", lambda e: self.view_item_details())

    def create_skills_tab(self):
        """Create skills management tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.progression.portfolio.portfolio.tabs.skills', default="Skills"))

        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        # Controls
        controls_frame = ttk.Frame(tab)
        controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=10, pady=10)

        ttk.Button(controls_frame, text=_t('gui.progression.portfolio.portfolio.buttons.add_skill', default="Add Skill"), command=self.add_skill).grid(row=0, column=0, padx=5)
        ttk.Button(controls_frame, text=_t('gui.progression.portfolio.portfolio.buttons.update_skill', default="Update Skill"), command=self.update_skill).grid(row=0, column=1, padx=5)
        ttk.Button(controls_frame, text=_t('gui.progression.portfolio.portfolio.buttons.remove_skill', default="Remove Skill"), command=self.remove_skill).grid(row=0, column=2, padx=5)
        ttk.Button(controls_frame, text=_t('gui.progression.portfolio.portfolio.buttons.toggle_featured', default="Toggle Featured"), command=self.toggle_featured_skill).grid(row=0, column=3, padx=5)

        # Skills list
        list_frame = ttk.Frame(tab)
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        self.skills_tree = ttk.Treeview(list_frame, columns=("Skill", "Category", "Proficiency", "Endorsements", "Featured"),
                                        show="headings", yscrollcommand=scrollbar.set)
        self.skills_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.config(command=self.skills_tree.yview)

        self.skills_tree.heading("Skill", text=_t('gui.progression.portfolio.portfolio.headings.skill', default="Skill"))
        self.skills_tree.heading("Category", text=_t('gui.progression.portfolio.portfolio.headings.category', default="Category"))
        self.skills_tree.heading("Proficiency", text=_t('gui.progression.portfolio.portfolio.headings.proficiency', default="Proficiency"))
        self.skills_tree.heading("Endorsements", text=_t('gui.progression.portfolio.portfolio.headings.endorsements', default="Endorsements"))
        self.skills_tree.heading("Featured", text=_t('gui.progression.portfolio.portfolio.headings.featured', default="Featured"))

        self.skills_tree.column("Skill", width=250)
        self.skills_tree.column("Category", width=150)
        self.skills_tree.column("Proficiency", width=150)
        self.skills_tree.column("Endorsements", width=120)
        self.skills_tree.column("Featured", width=100)

    def create_badges_tab(self):
        """Create badges showcase tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.progression.portfolio.portfolio.tabs.badges', default="Badges"))

        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)

        # Badges list
        list_frame = ttk.Frame(tab)
        list_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        self.badges_tree = ttk.Treeview(list_frame, columns=("Badge", "Type", "Issuer", "Date", "Status"),
                                        show="headings", yscrollcommand=scrollbar.set)
        self.badges_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.config(command=self.badges_tree.yview)

        self.badges_tree.heading("Badge", text=_t('gui.progression.portfolio.portfolio.headings.badge_name', default="Badge Name"))
        self.badges_tree.heading("Type", text=_t('gui.progression.portfolio.portfolio.headings.type', default="Type"))
        self.badges_tree.heading("Issuer", text=_t('gui.progression.portfolio.portfolio.headings.issuer', default="Issuer"))
        self.badges_tree.heading("Date", text=_t('gui.progression.portfolio.portfolio.headings.issue_date', default="Issue Date"))
        self.badges_tree.heading("Status", text=_t('gui.progression.portfolio.portfolio.headings.status', default="Status"))

        self.badges_tree.column("Badge", width=250)
        self.badges_tree.column("Type", width=150)
        self.badges_tree.column("Issuer", width=200)
        self.badges_tree.column("Date", width=120)
        self.badges_tree.column("Status", width=100)

        self.badges_tree.bind("<Double-1>", lambda e: self.view_badge_details())

    def create_endorsements_tab(self):
        """Create endorsements management tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.progression.portfolio.portfolio.tabs.endorsements', default="Endorsements"))

        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        # Controls
        controls_frame = ttk.Frame(tab)
        controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=10, pady=10)

        ttk.Button(controls_frame, text=_t('gui.progression.portfolio.portfolio.buttons.request_endorsement', default="Request Endorsement"), command=self.request_endorsement).grid(row=0, column=0, padx=5)
        ttk.Button(controls_frame, text=_t('gui.progression.portfolio.portfolio.buttons.view_details', default="View Details"), command=self.view_endorsement_details).grid(row=0, column=1, padx=5)

        # Endorsements list
        list_frame = ttk.Frame(tab)
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        self.endorsements_tree = ttk.Treeview(list_frame, columns=("Skill", "Endorser", "Role", "Date"),
                                              show="headings", yscrollcommand=scrollbar.set)
        self.endorsements_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.config(command=self.endorsements_tree.yview)

        self.endorsements_tree.heading("Skill", text=_t('gui.progression.portfolio.portfolio.headings.skill', default="Skill"))
        self.endorsements_tree.heading("Endorser", text=_t('gui.progression.portfolio.portfolio.headings.endorsed_by', default="Endorsed By"))
        self.endorsements_tree.heading("Role", text=_t('gui.progression.portfolio.portfolio.headings.role', default="Role"))
        self.endorsements_tree.heading("Date", text=_t('gui.progression.portfolio.portfolio.headings.date', default="Date"))

        self.endorsements_tree.column("Skill", width=250)
        self.endorsements_tree.column("Endorser", width=200)
        self.endorsements_tree.column("Role", width=150)
        self.endorsements_tree.column("Date", width=150)

    def create_resume_tab(self):
        """Create resume builder tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.progression.portfolio.portfolio.tabs.resumes', default="Resumes"))

        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        # Controls
        controls_frame = ttk.Frame(tab)
        controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=10, pady=10)

        ttk.Button(controls_frame, text=_t('gui.progression.portfolio.portfolio.buttons.generate_resume', default="Generate Resume"), command=self.generate_resume).grid(row=0, column=0, padx=5)
        ttk.Button(controls_frame, text=_t('gui.progression.portfolio.portfolio.buttons.view_resume', default="View Resume"), command=self.view_resume).grid(row=0, column=1, padx=5)

        # Resumes list
        list_frame = ttk.Frame(tab)
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        self.resumes_tree = ttk.Treeview(list_frame, columns=("Name", "Generated", "Format"),
                                         show="headings", yscrollcommand=scrollbar.set)
        self.resumes_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.config(command=self.resumes_tree.yview)

        self.resumes_tree.heading("Name", text=_t('gui.progression.portfolio.portfolio.headings.resume_name', default="Resume Name"))
        self.resumes_tree.heading("Generated", text=_t('gui.progression.portfolio.portfolio.headings.generated', default="Generated"))
        self.resumes_tree.heading("Format", text=_t('gui.progression.portfolio.portfolio.headings.format', default="Format"))

        self.resumes_tree.column("Name", width=400)
        self.resumes_tree.column("Generated", width=200)
        self.resumes_tree.column("Format", width=100)

    def create_settings_tab(self):
        """Create public profile settings tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.progression.portfolio.portfolio.tabs.settings', default="Settings"))
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)

        # Scrollable container so the long settings form is reachable on small windows.
        canvas = tk.Canvas(tab, borderwidth=0, highlightthickness=0)
        vbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        vbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        scroll_inner = ttk.Frame(canvas)
        inner_window = canvas.create_window((0, 0), window=scroll_inner, anchor="nw")

        def _on_inner_configure(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfigure(inner_window, width=event.width)

        scroll_inner.bind("<Configure>", _on_inner_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event):
            delta = -1 if getattr(event, "num", None) == 5 or event.delta < 0 else 1
            canvas.yview_scroll(-delta, "units")

        # Bind mousewheel only while the cursor is over the settings tab.
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            canvas.bind_all(seq, lambda e, c=canvas: _on_mousewheel(e) if str(c.winfo_containing(e.x_root, e.y_root)).startswith(str(c)) else None)

        # Profile settings
        settings_frame = ttk.LabelFrame(scroll_inner, text=_t('gui.progression.portfolio.portfolio.labels.public_profile_settings', default="Public Profile Settings"), padding="10")
        settings_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=10, pady=10)
        scroll_inner.columnconfigure(0, weight=1)

        # Portfolio info
        ttk.Label(settings_frame, text=_t('gui.progression.portfolio.portfolio.labels.portfolio_title', default="Portfolio Title:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(settings_frame, width=50)
        self.title_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))

        ttk.Label(settings_frame, text=_t('gui.progression.portfolio.portfolio.labels.headline', default="Headline:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.headline_entry = ttk.Entry(settings_frame, width=50)
        self.headline_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))

        ttk.Label(settings_frame, text=_t('gui.progression.portfolio.portfolio.labels.bio', default="Bio:")).grid(row=2, column=0, sticky=(tk.W, tk.N), pady=5)
        self.bio_text = scrolledtext.ScrolledText(settings_frame, width=50, height=5)
        self.bio_text.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))

        # Links
        ttk.Label(settings_frame, text=_t('gui.progression.portfolio.portfolio.labels.linkedin_url', default="LinkedIn URL:")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.linkedin_entry = ttk.Entry(settings_frame, width=50)
        self.linkedin_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))

        ttk.Label(settings_frame, text=_t('gui.progression.portfolio.portfolio.labels.github_url', default="GitHub URL:")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.github_entry = ttk.Entry(settings_frame, width=50)
        self.github_entry.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))

        ttk.Label(settings_frame, text=_t('gui.progression.portfolio.portfolio.labels.website', default="Website:")).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.website_entry = ttk.Entry(settings_frame, width=50)
        self.website_entry.grid(row=5, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))

        # Visibility
        ttk.Label(settings_frame, text=_t('gui.progression.portfolio.portfolio.labels.visibility', default="Visibility:")).grid(row=6, column=0, sticky=tk.W, pady=5)
        self.visibility_combo = ttk.Combobox(settings_frame, values=["Public", "Unlisted", "Private"],
                                             state="readonly", width=20)
        self.visibility_combo.grid(row=6, column=1, sticky=tk.W, pady=5, padx=(10, 0))

        # Privacy checkboxes
        privacy_frame = ttk.LabelFrame(settings_frame, text=_t('gui.progression.portfolio.portfolio.labels.privacy_options', default="Privacy Options"), padding="5")
        privacy_frame.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)

        self.show_contact_var = tk.BooleanVar()
        ttk.Checkbutton(privacy_frame, text=_t('gui.progression.portfolio.portfolio.buttons.show_contact_information', default="Show Contact Information"), variable=self.show_contact_var).grid(row=0, column=0, sticky=tk.W)

        self.show_gpa_var = tk.BooleanVar()
        ttk.Checkbutton(privacy_frame, text=_t('gui.progression.portfolio.portfolio.buttons.show_gpa', default="Show GPA"), variable=self.show_gpa_var).grid(row=1, column=0, sticky=tk.W)

        self.show_projects_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(privacy_frame, text=_t('gui.progression.portfolio.portfolio.buttons.show_projects', default="Show Projects"), variable=self.show_projects_var).grid(row=2, column=0, sticky=tk.W)

        self.show_skills_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(privacy_frame, text=_t('gui.progression.portfolio.portfolio.buttons.show_skills', default="Show Skills"), variable=self.show_skills_var).grid(row=3, column=0, sticky=tk.W)

        self.show_endorsements_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(privacy_frame, text=_t('gui.progression.portfolio.portfolio.buttons.show_endorsements', default="Show Endorsements"), variable=self.show_endorsements_var).grid(row=4, column=0, sticky=tk.W)

        # Save button
        ttk.Button(settings_frame, text=_t('gui.progression.portfolio.portfolio.buttons.save_settings', default="Save Settings"), command=self.save_settings).grid(row=8, column=0, columnspan=2, pady=10)

        settings_frame.columnconfigure(1, weight=1)

    def load_data(self):
        """Load student data and portfolio."""
        if not _has_session(self.auth):
            messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), _t('gui.progression.portfolio.portfolio.dialogs.please_log_in_first', default="Please log in first"))
            self.root.destroy()
            return

        user = self.auth.current_user
        # Try multiple possible keys for user ID
        self.student_id = user.get('user_id') or user.get('id') or user.get('username')

        if not self.student_id:
            messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), _t('gui.progression.portfolio.portfolio.dialogs.could_not_determine_user_id_please_log_in_again', default="Could not determine user ID. Please log in again."))
            self.root.destroy()
            return

        # Update header
        self.student_label.config(text=f"Student: {user.get('name', self.student_id)}")

        # Load portfolio
        self.portfolio = self.service.get_portfolio(self.student_id)

        if not self.portfolio:
            # Create portfolio if it doesn't exist
            result = messagebox.askyesno(_t('gui.progression.portfolio.portfolio.dialogs.create_portfolio', default="Create Portfolio"),
                                        _t('gui.progression.portfolio.portfolio.dialogs.you_don_t_have_a_portfolio_yet_would_you_like_to_create_one', default="You don't have a portfolio yet. Would you like to create one?"))
            if result:
                self.create_portfolio_wizard()
            else:
                self.root.destroy()
                return

        # Load all data
        self.refresh_all()

    def refresh_all(self):
        """Refresh all data displays."""
        self.refresh_stats()
        self.load_portfolio_items()
        self.load_skills()
        self.load_badges()
        self.load_endorsements()
        self.load_resumes()
        self.load_settings()

    def refresh_stats(self):
        """Refresh statistics display."""
        stats = self.service.get_portfolio_stats(self.student_id)

        # Update header
        self.completeness_label.config(text=f"Completeness: {stats.get('completeness_score', 0)}%")
        self.items_label.config(text=f"Items: {stats.get('total_items', 0)}")
        self.skills_label.config(text=f"Skills: {stats.get('total_skills', 0)}")
        self.badges_label.config(text=f"Badges: {stats.get('verified_badges', 0)}")
        self.views_label.config(text=f"Views: {stats.get('profile_views', 0)}")

        # Update stats text
        self.stats_text.delete('1.0', tk.END)
        self.stats_text.insert('1.0', "PORTFOLIO STATISTICS\n\n")
        self.stats_text.insert(tk.END, f"Completeness Score: {stats.get('completeness_score', 0)}%\n\n")
        self.stats_text.insert(tk.END, f"Total Portfolio Items: {stats.get('total_items', 0)}\n")

        items_by_cat = stats.get('items_by_category', {})
        if items_by_cat:
            self.stats_text.insert(tk.END, "\nItems by Category:\n")
            for category, count in items_by_cat.items():
                self.stats_text.insert(tk.END, f"  {category.replace('_', ' ').title()}: {count}\n")

        self.stats_text.insert(tk.END, f"\nTotal Skills: {stats.get('total_skills', 0)}\n")
        self.stats_text.insert(tk.END, f"Total Endorsements: {stats.get('total_endorsements', 0)}\n")
        self.stats_text.insert(tk.END, f"Verified Badges: {stats.get('verified_badges', 0)}\n")
        self.stats_text.insert(tk.END, f"Achievement Points: {stats.get('achievement_points', 0)}\n\n")

        self.stats_text.insert(tk.END, f"Profile Visibility: {stats.get('profile_visibility', 'private').upper()}\n")
        self.stats_text.insert(tk.END, f"Profile Views: {stats.get('profile_views', 0)}\n")

    def load_portfolio_items(self):
        """Load portfolio items into tree view."""
        # Clear existing
        for item in self.items_tree.get_children():
            self.items_tree.delete(item)

        if not self.portfolio:
            return

        # Get filter
        category_filter = self.category_filter.get()

        items = self.portfolio.get('items', [])
        for item in items:
            if category_filter != "All":
                filter_cat = category_filter.lower().replace(' ', '_')
                if item['category'] != filter_cat:
                    continue

            date_str = item.get('start_date', 'N/A')
            if item.get('is_current'):
                date_str += " - Present"
            elif item.get('end_date'):
                date_str += f" - {item['end_date']}"

            self.items_tree.insert('', tk.END, values=(
                item['category'].replace('_', ' ').title(),
                item['title'],
                item.get('organization', 'N/A'),
                date_str,
                "Yes" if item.get('is_featured') else "No"
            ), tags=(item['item_id'],))

    def load_skills(self):
        """Load skills into tree view."""
        # Clear existing
        for item in self.skills_tree.get_children():
            self.skills_tree.delete(item)

        skills = self.service.get_student_skills(self.student_id)
        for skill in skills:
            self.skills_tree.insert('', tk.END, values=(
                skill['skill_name'],
                skill.get('skill_category', 'N/A').replace('_', ' ').title(),
                skill.get('proficiency_level', 'N/A').title(),
                skill.get('endorsement_count', 0),
                "Yes" if skill.get('is_featured') else "No"
            ), tags=(skill['skill_id'],))

    def load_badges(self):
        """Load badges into tree view."""
        # Clear existing
        for item in self.badges_tree.get_children():
            self.badges_tree.delete(item)

        badges = self.service.get_student_badges(self.student_id)
        for badge in badges:
            self.badges_tree.insert('', tk.END, values=(
                badge['badge_name'],
                badge['badge_type'].replace('_', ' ').title(),
                badge['issuer'],
                badge['issue_date'],
                badge['verification_status'].upper()
            ), tags=(badge['badge_id'],))

    def load_endorsements(self):
        """Load endorsements into tree view."""
        # Clear existing
        for item in self.endorsements_tree.get_children():
            self.endorsements_tree.delete(item)

        endorsements = self.service.get_student_endorsements(self.student_id)
        for e in endorsements:
            self.endorsements_tree.insert('', tk.END, values=(
                e['skill_name'],
                e['endorser_id'],
                e['endorser_role'].title(),
                e['endorsed_at']
            ), tags=(e['endorsement_id'],))

    def load_resumes(self):
        """Load resumes into tree view."""
        # Clear existing
        for item in self.resumes_tree.get_children():
            self.resumes_tree.delete(item)

        resumes = self.service.get_student_resumes(self.student_id)
        for resume in resumes:
            self.resumes_tree.insert('', tk.END, values=(
                resume['resume_name'],
                resume['last_generated'],
                resume['format'].upper()
            ), tags=(resume['resume_id'],))

    def load_settings(self):
        """Load profile settings."""
        if self.portfolio:
            # dict.get returns stored None when the DB column is NULL, so
            # coerce with `or ''` before feeding Tk widgets (they reject None).
            self.title_entry.delete(0, tk.END)
            self.title_entry.insert(0, self.portfolio.get('title') or '')

            self.headline_entry.delete(0, tk.END)
            self.headline_entry.insert(0, self.portfolio.get('headline') or '')

            self.bio_text.delete('1.0', tk.END)
            self.bio_text.insert('1.0', self.portfolio.get('bio') or '')

            self.linkedin_entry.delete(0, tk.END)
            self.linkedin_entry.insert(0, self.portfolio.get('linkedin_url') or '')

            self.github_entry.delete(0, tk.END)
            self.github_entry.insert(0, self.portfolio.get('github_url') or '')

            self.website_entry.delete(0, tk.END)
            self.website_entry.insert(0, self.portfolio.get('personal_website') or '')

        # Load public profile settings
        profile = self.service.get_public_profile(self.student_id)
        if profile:
            visibility = profile.get('visibility', 'private')
            self.visibility_combo.set(visibility.title())

            self.show_contact_var.set(profile.get('show_contact', False))
            self.show_gpa_var.set(profile.get('show_gpa', False))
            self.show_projects_var.set(profile.get('show_projects', True))
            self.show_skills_var.set(profile.get('show_skills', True))
            self.show_endorsements_var.set(profile.get('show_endorsements', True))

    def create_portfolio_wizard(self):
        """Wizard to create initial portfolio."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.progression.portfolio.portfolio.windows.create_portfolio', default="Create Portfolio"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=_t('gui.progression.portfolio.portfolio.labels.create_your_portfolio', default="Create Your Portfolio"), font=("Arial", 14, "bold")).pack(pady=10)

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t('gui.progression.portfolio.portfolio.labels.title', default="Title:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        title_entry = ttk.Entry(frame, width=40)
        title_entry.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text=_t('gui.progression.portfolio.portfolio.labels.headline', default="Headline:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        headline_entry = ttk.Entry(frame, width=40)
        headline_entry.grid(row=1, column=1, pady=5)

        ttk.Label(frame, text=_t('gui.progression.portfolio.portfolio.labels.bio', default="Bio:")).grid(row=2, column=0, sticky=(tk.W, tk.N), pady=5)
        bio_text = scrolledtext.ScrolledText(frame, width=40, height=5)
        bio_text.grid(row=2, column=1, pady=5)

        def create():
            title = title_entry.get().strip()
            if not title:
                messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), _t('gui.progression.portfolio.portfolio.dialogs.title_is_required', default="Title is required"))
                return

            success, message, portfolio_id = self.service.create_portfolio(
                student_id=self.student_id,
                title=title,
                headline=headline_entry.get().strip() or None,
                bio=bio_text.get('1.0', tk.END).strip() or None
            )

            if success:
                messagebox.showinfo(_t('gui.progression.portfolio.portfolio.dialogs.success', default="Success"), message)
                dialog.destroy()
                self.portfolio = self.service.get_portfolio(self.student_id)
                self.refresh_all()
            else:
                messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), message)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text=_t('gui.progression.portfolio.portfolio.buttons.create', default="Create"), command=create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.progression.portfolio.portfolio.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def add_portfolio_item(self):
        """Dialog to add portfolio item."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.progression.portfolio.portfolio.windows.add_portfolio_item', default="Add Portfolio Item"))
        dialog.geometry("600x500")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Category
        ttk.Label(frame, text=_t('gui.progression.portfolio.portfolio.labels.category', default="Category:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        category_combo = ttk.Combobox(frame, values=[
            "Project", "Research", "Leadership", "Work Experience",
            "Award", "Certification", "Publication", "Presentation"
        ], state="readonly", width=30)
        category_combo.grid(row=0, column=1, sticky=tk.W, pady=5)

        # Title
        ttk.Label(frame, text=_t('gui.progression.portfolio.portfolio.labels.title', default="Title:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        title_entry = ttk.Entry(frame, width=40)
        title_entry.grid(row=1, column=1, pady=5)

        # Description
        ttk.Label(frame, text=_t('gui.progression.portfolio.portfolio.labels.description', default="Description:")).grid(row=2, column=0, sticky=(tk.W, tk.N), pady=5)
        desc_text = scrolledtext.ScrolledText(frame, width=40, height=4)
        desc_text.grid(row=2, column=1, pady=5)

        # Organization
        ttk.Label(frame, text=_t('gui.progression.portfolio.portfolio.labels.organization', default="Organization:")).grid(row=3, column=0, sticky=tk.W, pady=5)
        org_entry = ttk.Entry(frame, width=40)
        org_entry.grid(row=3, column=1, pady=5)

        # Role
        ttk.Label(frame, text=_t('gui.progression.portfolio.portfolio.labels.role', default="Role:")).grid(row=4, column=0, sticky=tk.W, pady=5)
        role_entry = ttk.Entry(frame, width=40)
        role_entry.grid(row=4, column=1, pady=5)

        # Featured
        featured_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text=_t('gui.progression.portfolio.portfolio.buttons.feature_this_item', default="Feature this item"), variable=featured_var).grid(row=5, column=1, sticky=tk.W, pady=5)

        def add():
            category = category_combo.get()
            if not category:
                messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), _t('gui.progression.portfolio.portfolio.dialogs.please_select_a_category', default="Please select a category"))
                return

            title = title_entry.get().strip()
            if not title:
                messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), _t('gui.progression.portfolio.portfolio.dialogs.title_is_required', default="Title is required"))
                return

            category_map = {
                "Project": "project", "Research": "research", "Leadership": "leadership",
                "Work Experience": "work_experience", "Award": "award",
                "Certification": "certification", "Publication": "publication",
                "Presentation": "presentation"
            }

            success, message, item_id = self.service.add_portfolio_item(
                portfolio_id=self.portfolio['portfolio_id'],
                category=category_map[category],
                title=title,
                description=desc_text.get('1.0', tk.END).strip() or None,
                organization=org_entry.get().strip() or None,
                role=role_entry.get().strip() or None,
                is_featured=featured_var.get()
            )

            if success:
                messagebox.showinfo(_t('gui.progression.portfolio.portfolio.dialogs.success', default="Success"), message)
                dialog.destroy()
                self.portfolio = self.service.get_portfolio(self.student_id)
                self.load_portfolio_items()
                self.refresh_stats()
            else:
                messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), message)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text=_t('gui.progression.portfolio.portfolio.buttons.add', default="Add"), command=add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.progression.portfolio.portfolio.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def edit_portfolio_item(self):
        """Edit selected portfolio item."""
        selection = self.items_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.progression.portfolio.portfolio.dialogs.warning', default="Warning"), _t('gui.progression.portfolio.portfolio.dialogs.please_select_an_item_to_edit', default="Please select an item to edit"))
            return

        messagebox.showinfo(_t('gui.progression.portfolio.portfolio.dialogs.info', default="Info"), _t('gui.progression.portfolio.portfolio.dialogs.edit_functionality_would_open_a_detailed_edit_dialog', default="Edit functionality would open a detailed edit dialog"))

    def delete_portfolio_item(self):
        """Delete selected portfolio item."""
        selection = self.items_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.progression.portfolio.portfolio.dialogs.warning', default="Warning"), _t('gui.progression.portfolio.portfolio.dialogs.please_select_an_item_to_delete', default="Please select an item to delete"))
            return

        if messagebox.askyesno(_t('gui.progression.portfolio.portfolio.dialogs.confirm', default="Confirm"), _t('gui.progression.portfolio.portfolio.dialogs.are_you_sure_you_want_to_delete_this_item', default="Are you sure you want to delete this item?")):
            item_id = self.items_tree.item(selection[0])['tags'][0]
            success, message = self.service.delete_portfolio_item(item_id)

            if success:
                messagebox.showinfo(_t('gui.progression.portfolio.portfolio.dialogs.success', default="Success"), message)
                self.portfolio = self.service.get_portfolio(self.student_id)
                self.load_portfolio_items()
                self.refresh_stats()
            else:
                messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), message)

    def view_item_details(self):
        """View details of selected item."""
        selection = self.items_tree.selection()
        if not selection:
            return

        messagebox.showinfo(_t('gui.progression.portfolio.portfolio.dialogs.info', default="Info"), _t('gui.progression.portfolio.portfolio.dialogs.item_details_would_be_displayed_here', default="Item details would be displayed here"))

    def add_skill(self):
        """Dialog to add skill."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.progression.portfolio.portfolio.windows.add_skill', default="Add Skill"))
        dialog.geometry("400x350")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t('gui.progression.portfolio.portfolio.labels.skill_name', default="Skill Name:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        skill_entry = ttk.Entry(frame, width=30)
        skill_entry.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text=_t('gui.progression.portfolio.portfolio.labels.category', default="Category:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        category_combo = ttk.Combobox(frame, values=[
            "Technical", "Soft Skill", "Language", "Tool", "Domain"
        ], state="readonly", width=28)
        category_combo.grid(row=1, column=1, pady=5)

        ttk.Label(frame, text=_t('gui.progression.portfolio.portfolio.labels.proficiency', default="Proficiency:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        prof_combo = ttk.Combobox(frame, values=[
            "Beginner", "Intermediate", "Advanced", "Expert"
        ], state="readonly", width=28)
        prof_combo.grid(row=2, column=1, pady=5)

        featured_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text=_t('gui.progression.portfolio.portfolio.buttons.feature_this_skill', default="Feature this skill"), variable=featured_var).grid(row=3, column=1, sticky=tk.W, pady=5)

        def add():
            skill_name = skill_entry.get().strip()
            if not skill_name:
                messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), _t('gui.progression.portfolio.portfolio.dialogs.skill_name_is_required', default="Skill name is required"))
                return

            cat_map = {
                "Technical": "technical", "Soft Skill": "soft_skill",
                "Language": "language", "Tool": "tool", "Domain": "domain"
            }
            prof_map = {
                "Beginner": "beginner", "Intermediate": "intermediate",
                "Advanced": "advanced", "Expert": "expert"
            }

            category = cat_map.get(category_combo.get())
            proficiency = prof_map.get(prof_combo.get())

            success, message, skill_id = self.service.add_skill(
                student_id=self.student_id,
                skill_name=skill_name,
                skill_category=category,
                proficiency_level=proficiency,
                is_featured=featured_var.get()
            )

            if success:
                messagebox.showinfo(_t('gui.progression.portfolio.portfolio.dialogs.success', default="Success"), message)
                dialog.destroy()
                self.load_skills()
                self.refresh_stats()
            else:
                messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), message)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text=_t('gui.progression.portfolio.portfolio.buttons.add', default="Add"), command=add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.progression.portfolio.portfolio.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def update_skill(self):
        """Update selected skill."""
        selection = self.skills_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.progression.portfolio.portfolio.dialogs.warning', default="Warning"), _t('gui.progression.portfolio.portfolio.dialogs.please_select_a_skill_to_update', default="Please select a skill to update"))
            return

        messagebox.showinfo(_t('gui.progression.portfolio.portfolio.dialogs.info', default="Info"), _t('gui.progression.portfolio.portfolio.dialogs.skill_update_dialog_would_open_here', default="Skill update dialog would open here"))

    def remove_skill(self):
        """Remove selected skill."""
        selection = self.skills_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.progression.portfolio.portfolio.dialogs.warning', default="Warning"), _t('gui.progression.portfolio.portfolio.dialogs.please_select_a_skill_to_remove', default="Please select a skill to remove"))
            return

        if messagebox.askyesno(_t('gui.progression.portfolio.portfolio.dialogs.confirm', default="Confirm"), _t('gui.progression.portfolio.portfolio.dialogs.are_you_sure_you_want_to_remove_this_skill', default="Are you sure you want to remove this skill?")):
            skill_id = self.skills_tree.item(selection[0])['tags'][0]
            success, message = self.service.remove_skill(skill_id)

            if success:
                messagebox.showinfo(_t('gui.progression.portfolio.portfolio.dialogs.success', default="Success"), message)
                self.load_skills()
                self.refresh_stats()
            else:
                messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), message)

    def toggle_featured_skill(self):
        """Toggle featured status of skill."""
        selection = self.skills_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.progression.portfolio.portfolio.dialogs.warning', default="Warning"), _t('gui.progression.portfolio.portfolio.dialogs.please_select_a_skill', default="Please select a skill"))
            return

        skill_id = self.skills_tree.item(selection[0])['tags'][0]
        values = self.skills_tree.item(selection[0])['values']
        is_featured = values[4] == "Yes"

        success, message = self.service.update_skill(skill_id, is_featured=not is_featured)

        if success:
            self.load_skills()
        else:
            messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), message)

    def view_badge_details(self):
        """View details of selected badge."""
        selection = self.badges_tree.selection()
        if not selection:
            return

        messagebox.showinfo(_t('gui.progression.portfolio.portfolio.dialogs.info', default="Info"), _t('gui.progression.portfolio.portfolio.dialogs.badge_details_would_be_displayed_here', default="Badge details would be displayed here"))

    def request_endorsement(self):
        """Request skill endorsement from another user."""
        skills = self.service.get_student_skills(self.student_id)
        if not skills:
            messagebox.showwarning(
                _t('gui.progression.portfolio.portfolio.dialogs.no_skills', default="No Skills"),
                _t('gui.progression.portfolio.portfolio.dialogs.add_at_least_one_skill_on_the_skills_tab_before_requesting_an_en', default="Add at least one skill on the Skills tab before requesting an endorsement."),
            )
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.progression.portfolio.portfolio.windows.request_endorsement', default="Request Endorsement"))
        dialog.geometry("500x380")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t('gui.progression.portfolio.portfolio.labels.skill', default="Skill:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        skill_combo = ttk.Combobox(
            frame,
            values=[f"{s['skill_name']} ({(s.get('proficiency_level') or '').title()})" for s in skills],
            state="readonly",
            width=40,
        )
        skill_combo.grid(row=0, column=1, pady=5, sticky=tk.W)
        skill_combo.current(0)

        ttk.Label(frame, text=_t('gui.progression.portfolio.portfolio.labels.endorser_username', default="Endorser username:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        endorser_entry = ttk.Entry(frame, width=42)
        endorser_entry.grid(row=1, column=1, pady=5, sticky=tk.W)

        ttk.Label(frame, text=_t('gui.progression.portfolio.portfolio.labels.endorser_role', default="Endorser role:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        role_combo = ttk.Combobox(
            frame,
            values=["Faculty", "Peer", "Employer", "Mentor"],
            state="readonly",
            width=40,
        )
        role_combo.set("Faculty")
        role_combo.grid(row=2, column=1, pady=5, sticky=tk.W)

        ttk.Label(frame, text=_t('gui.progression.portfolio.portfolio.labels.message_optional', default="Message (optional):")).grid(row=3, column=0, sticky=(tk.W, tk.N), pady=5)
        message_text = scrolledtext.ScrolledText(frame, width=42, height=6)
        message_text.grid(row=3, column=1, pady=5, sticky=tk.W)

        def submit():
            idx = skill_combo.current()
            if idx < 0:
                messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), _t('gui.progression.portfolio.portfolio.dialogs.please_select_a_skill', default="Please select a skill"), parent=dialog)
                return
            endorser = endorser_entry.get().strip()
            if not endorser:
                messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), _t('gui.progression.portfolio.portfolio.dialogs.endorser_username_is_required', default="Endorser username is required"), parent=dialog)
                return

            skill = skills[idx]
            role = role_combo.get().lower()
            note = message_text.get('1.0', tk.END).strip() or None

            success, message = self.service.request_endorsement(
                skill_id=skill['skill_id'],
                endorser_id=endorser,
                message=note,
            )
            if not success:
                messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), message, parent=dialog)
                return

            # Best-effort: notify the endorser through the email service.
            try:
                from education_system.systems.university.infrastructure.email.email_service import send_email
                user = (getattr(self.auth, "current_user", None) or {})
                requester = user.get('name') or user.get('username') or self.student_id
                subject = f"Endorsement request: {skill['skill_name']}"
                body = (
                    f"Hi {endorser},\n\n"
                    f"{requester} has requested that you endorse their skill "
                    f"\"{skill['skill_name']}\" ({role}).\n\n"
                    + (f"Message:\n{note}\n\n" if note else "")
                    + "Open the Portfolio system to respond.\n"
                )
                # Treat the username as a deliverable address only when it looks like one.
                if "@" in endorser:
                    send_email(endorser, subject, body)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

            messagebox.showinfo(_t('gui.progression.portfolio.portfolio.dialogs.sent', default="Sent"), message, parent=dialog)
            dialog.destroy()
            self.load_endorsements()

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text=_t('gui.progression.portfolio.portfolio.buttons.send_request', default="Send Request"), command=submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.progression.portfolio.portfolio.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def view_endorsement_details(self):
        """View endorsement details."""
        selection = self.endorsements_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.progression.portfolio.portfolio.dialogs.warning', default="Warning"), _t('gui.progression.portfolio.portfolio.dialogs.please_select_an_endorsement', default="Please select an endorsement"))
            return

        item = self.endorsements_tree.item(selection[0])
        skill, endorser, role, date = item['values']
        details = (
            f"Skill: {skill}\n"
            f"Endorsed by: {endorser}\n"
            f"Role: {role}\n"
            f"Date: {date}"
        )
        messagebox.showinfo(_t('gui.progression.portfolio.portfolio.dialogs.endorsement_details', default="Endorsement Details"), details)

    def generate_resume(self):
        """Generate new resume."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.progression.portfolio.portfolio.windows.generate_resume', default="Generate Resume"))
        dialog.geometry("400x250")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t('gui.progression.portfolio.portfolio.labels.resume_name', default="Resume Name:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        name_entry = ttk.Entry(frame, width=30)
        name_entry.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text=_t('gui.progression.portfolio.portfolio.labels.template', default="Template:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        template_combo = ttk.Combobox(frame, values=[
            "Traditional", "Modern", "Creative", "Technical", "Academic"
        ], state="readonly", width=28)
        template_combo.set("Traditional")
        template_combo.grid(row=1, column=1, pady=5)

        def generate():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), _t('gui.progression.portfolio.portfolio.dialogs.resume_name_is_required', default="Resume name is required"))
                return

            template_map = {
                "Traditional": "traditional", "Modern": "modern",
                "Creative": "creative", "Technical": "technical",
                "Academic": "academic"
            }

            success, message, resume_data = self.service.generate_resume(
                student_id=self.student_id,
                resume_name=name,
                template_type=template_map[template_combo.get()]
            )

            if success:
                messagebox.showinfo(_t('gui.progression.portfolio.portfolio.dialogs.success', default="Success"), message)
                dialog.destroy()
                self.load_resumes()
            else:
                messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), message)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text=_t('gui.progression.portfolio.portfolio.buttons.generate', default="Generate"), command=generate).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.progression.portfolio.portfolio.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def view_resume(self):
        """View selected resume."""
        selection = self.resumes_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.progression.portfolio.portfolio.dialogs.warning', default="Warning"), _t('gui.progression.portfolio.portfolio.dialogs.please_select_a_resume_to_view', default="Please select a resume to view"))
            return

        messagebox.showinfo(_t('gui.progression.portfolio.portfolio.dialogs.info', default="Info"), _t('gui.progression.portfolio.portfolio.dialogs.resume_preview_would_be_displayed_here', default="Resume preview would be displayed here"))

    def save_settings(self):
        """Save portfolio and profile settings."""
        if not self.portfolio:
            return

        # Update portfolio
        updates = {
            'title': self.title_entry.get().strip(),
            'headline': self.headline_entry.get().strip(),
            'bio': self.bio_text.get('1.0', tk.END).strip(),
            'linkedin_url': self.linkedin_entry.get().strip(),
            'github_url': self.github_entry.get().strip(),
            'personal_website': self.website_entry.get().strip()
        }

        success, message = self.service.update_portfolio(self.portfolio['portfolio_id'], **updates)

        if not success:
            messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), message)
            return

        # Update public profile
        vis_map = {"Public": "public", "Unlisted": "unlisted", "Private": "private"}
        profile_updates = {
            'visibility': vis_map.get(self.visibility_combo.get(), 'private'),
            'show_contact': self.show_contact_var.get(),
            'show_gpa': self.show_gpa_var.get(),
            'show_projects': self.show_projects_var.get(),
            'show_skills': self.show_skills_var.get(),
            'show_endorsements': self.show_endorsements_var.get()
        }

        success, message = self.service.update_public_profile(self.student_id, **profile_updates)

        if success:
            messagebox.showinfo(_t('gui.progression.portfolio.portfolio.dialogs.success', default="Success"), _t('gui.progression.portfolio.portfolio.dialogs.settings_saved_successfully', default="Settings saved successfully"))
            self.portfolio = self.service.get_portfolio(self.student_id)
            self.refresh_stats()
        else:
            messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), message)

    def share_portfolio(self):
        """Display portfolio sharing URL."""
        url = self.service.get_portfolio_url(self.student_id)

        if url:
            dialog = tk.Toplevel(self.root)
            dialog.title(_t('gui.progression.portfolio.portfolio.windows.share_portfolio', default="Share Portfolio"))
            dialog.geometry("500x200")
            dialog.transient(self.root)

            frame = ttk.Frame(dialog, padding="20")
            frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frame, text=_t('gui.progression.portfolio.portfolio.labels.your_portfolio_url', default="Your Portfolio URL:"), font=("Arial", 12, "bold")).pack(pady=10)

            url_entry = ttk.Entry(frame, width=60)
            url_entry.insert(0, url)
            url_entry.config(state='readonly')
            url_entry.pack(pady=10)

            ttk.Label(frame, text=_t('gui.progression.portfolio.portfolio.labels.share_this_url_with_employers_recruiters_and_networks', default="Share this URL with employers, recruiters, and networks")).pack(pady=10)

            ttk.Button(frame, text=_t('gui.progression.portfolio.portfolio.buttons.close', default="Close"), command=dialog.destroy).pack(pady=10)
        else:
            messagebox.showerror(_t('gui.progression.portfolio.portfolio.dialogs.error', default="Error"), _t('gui.progression.portfolio.portfolio.dialogs.portfolio_url_not_found', default="Portfolio URL not found"))

    def run(self):
        """Run the GUI."""
        self.root.mainloop()


def main():
    """Main entry point."""
    app = PortfolioGUI()
    app.run()


if __name__ == "__main__":
    main()
