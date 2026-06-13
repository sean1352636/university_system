"""
Event Discovery Engine GUI Interface

Provides visual interface for event discovery with:
- Calendar view with event markers
- Event cards with rich details
- Personalized recommendations panel
- Category filters and search
- RSVP and attendance management
- Social features and ratings
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import calendar

from education_system.university_system.modules.domain.student_affairs.events.services.events_service import get_events_service
from education_system.university_system.infrastructure.shared_context import get_auth


class EventsGUI:
    """GUI for Event Discovery Engine"""

    def __init__(self, parent):
        """Initialize the events GUI"""
        self.parent = parent
        self.window = parent  # Store reference to the Toplevel window
        self.service = get_events_service()
        self.auth = get_auth()
        if not self.auth or not getattr(self.auth, "current_user", None):
            try:
                from tkinter import messagebox
                messagebox.showerror(
                    "Login required",
                    "You must be logged in via the main GUI to use Events.",
                )
            except Exception:
                pass
            raise PermissionError("Events GUI requires an authenticated user")

        # Color scheme
        self.colors = {
            'primary': '#2196F3',
            'secondary': '#FF9800',
            'success': '#4CAF50',
            'danger': '#F44336',
            'background': '#F5F5F5',
            'card': '#FFFFFF',
            'text': '#212121',
            'text_light': '#757575',
            'border': '#E0E0E0'
        }

        # Category colors
        self.category_colors = {
            'Academic': '#3F51B5',
            'Social': '#E91E63',
            'Athletic': '#FF5722',
            'Cultural': '#9C27B0',
            'Career': '#00BCD4',
            'Community Service': '#4CAF50',
            'Other': '#9E9E9E'
        }

        # Current view state
        self.current_month = datetime.now().month
        self.current_year = datetime.now().year
        self.selected_date = None
        self.selected_category = None

        self.setup_ui()

    def setup_ui(self):
        """Set up the main UI"""
        # Main container
        main_frame = tk.Frame(self.parent, bg=self.colors['background'])
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        self.create_header(main_frame)

        # Content area with three columns
        content_frame = tk.Frame(main_frame, bg=self.colors['background'])
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left panel - Calendar and filters
        left_panel = tk.Frame(content_frame, bg=self.colors['background'], width=300)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        left_panel.pack_propagate(False)

        self.create_calendar_panel(left_panel)
        self.create_filter_panel(left_panel)

        # Center panel - Event list
        center_panel = tk.Frame(content_frame, bg=self.colors['background'])
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        self.create_event_list_panel(center_panel)

        # Right panel - Recommendations and details
        right_panel = tk.Frame(content_frame, bg=self.colors['background'], width=350)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 0))
        right_panel.pack_propagate(False)

        self.create_recommendations_panel(right_panel)

        # Load initial data
        self.refresh_all()

    def create_header(self, parent):
        """Create header with title and quick actions"""
        header = tk.Frame(parent, bg=self.colors['primary'], height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        # Title
        title_label = tk.Label(
            header,
            text="Event Discovery Engine",
            font=('Helvetica', 24, 'bold'),
            bg=self.colors['primary'],
            fg='white'
        )
        title_label.pack(side=tk.LEFT, padx=20, pady=20)

        # Quick action buttons
        btn_frame = tk.Frame(header, bg=self.colors['primary'])
        btn_frame.pack(side=tk.RIGHT, padx=20, pady=20)

        buttons = [
            ("My RSVPs", self.show_my_rsvps),
            ("Interests", self.manage_interests_dialog),
            ("My Stats", self.show_statistics),
            ("Return to Main Menu", self.close_window)
        ]

        for text, command in buttons:
            btn = tk.Button(
                btn_frame,
                text=text,
                command=command,
                bg='white',
                fg=self.colors['primary'],
                font=('Helvetica', 10, 'bold'),
                relief=tk.FLAT,
                padx=15,
                pady=8,
                cursor='hand2'
            )
            btn.pack(side=tk.LEFT, padx=5)

    def create_calendar_panel(self, parent):
        """Create mini calendar with event markers"""
        # Calendar card
        cal_card = self.create_card(parent, "Calendar")
        cal_card.pack(fill=tk.X, pady=(0, 10))

        # Month navigation
        nav_frame = tk.Frame(cal_card, bg='white')
        nav_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        prev_btn = tk.Button(
            nav_frame,
            text="◀",
            command=self.prev_month,
            bg=self.colors['background'],
            relief=tk.FLAT,
            cursor='hand2',
            width=3
        )
        prev_btn.pack(side=tk.LEFT)

        self.month_label = tk.Label(
            nav_frame,
            text="",
            font=('Helvetica', 12, 'bold'),
            bg='white'
        )
        self.month_label.pack(side=tk.LEFT, expand=True)

        next_btn = tk.Button(
            nav_frame,
            text="▶",
            command=self.next_month,
            bg=self.colors['background'],
            relief=tk.FLAT,
            cursor='hand2',
            width=3
        )
        next_btn.pack(side=tk.RIGHT)

        # Calendar grid
        self.calendar_frame = tk.Frame(cal_card, bg='white')
        self.calendar_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.update_calendar()

    def create_filter_panel(self, parent):
        """Create filter options"""
        filter_card = self.create_card(parent, "Filters")
        filter_card.pack(fill=tk.X, pady=(0, 10))

        # Search box
        search_frame = tk.Frame(filter_card, bg='white')
        search_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(
            search_frame,
            text="Search:",
            font=('Helvetica', 10, 'bold'),
            bg='white'
        ).pack(anchor=tk.W)

        self.search_var = tk.StringVar()
        search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=('Helvetica', 10)
        )
        search_entry.pack(fill=tk.X, pady=5)
        search_entry.bind('<Return>', lambda e: self.apply_filters())

        # Category filter
        category_frame = tk.Frame(filter_card, bg='white')
        category_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(
            category_frame,
            text="Category:",
            font=('Helvetica', 10, 'bold'),
            bg='white'
        ).pack(anchor=tk.W)

        self.category_var = tk.StringVar(value="All")
        categories = ["All"] + self.service.CATEGORIES

        for cat in categories:
            rb = tk.Radiobutton(
                category_frame,
                text=cat,
                variable=self.category_var,
                value=cat,
                bg='white',
                font=('Helvetica', 9),
                command=self.apply_filters
            )
            rb.pack(anchor=tk.W, pady=2)

        # Filter buttons
        btn_frame = tk.Frame(filter_card, bg='white')
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Button(
            btn_frame,
            text="Apply Filters",
            command=self.apply_filters,
            bg=self.colors['primary'],
            fg='white',
            relief=tk.FLAT,
            cursor='hand2'
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

        tk.Button(
            btn_frame,
            text="Clear",
            command=self.clear_filters,
            bg=self.colors['background'],
            relief=tk.FLAT,
            cursor='hand2'
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))

    def create_event_list_panel(self, parent):
        """Create main event list with cards"""
        # Header
        header = tk.Frame(parent, bg='white', height=50)
        header.pack(fill=tk.X, pady=(0, 10))
        header.pack_propagate(False)

        self.event_list_title = tk.Label(
            header,
            text="Upcoming Events",
            font=('Helvetica', 16, 'bold'),
            bg='white',
            anchor=tk.W
        )
        self.event_list_title.pack(side=tk.LEFT, padx=15, pady=10)

        self.event_count_label = tk.Label(
            header,
            text="",
            font=('Helvetica', 10),
            bg='white',
            fg=self.colors['text_light']
        )
        self.event_count_label.pack(side=tk.RIGHT, padx=15)

        # Scrollable event list
        list_container = tk.Frame(parent, bg=self.colors['background'])
        list_container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(list_container, bg=self.colors['background'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=canvas.yview)

        self.event_list_frame = tk.Frame(canvas, bg=self.colors['background'])

        self.event_list_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.event_list_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse wheel scrolling
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def create_recommendations_panel(self, parent):
        """Create personalized recommendations panel"""
        rec_card = self.create_card(parent, "For You - Recommended Events")
        rec_card.pack(fill=tk.BOTH, expand=True)

        # Scrollable recommendations
        canvas = tk.Canvas(rec_card, bg='white', highlightthickness=0)
        scrollbar = ttk.Scrollbar(rec_card, orient=tk.VERTICAL, command=canvas.yview)

        self.recommendations_frame = tk.Frame(canvas, bg='white')

        self.recommendations_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.recommendations_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.load_recommendations()

    def create_card(self, parent, title: str) -> tk.Frame:
        """Create a card container with title"""
        card = tk.Frame(parent, bg='white', relief=tk.FLAT, bd=1)

        if title:
            title_frame = tk.Frame(card, bg=self.colors['primary'], height=40)
            title_frame.pack(fill=tk.X)
            title_frame.pack_propagate(False)

            tk.Label(
                title_frame,
                text=title,
                font=('Helvetica', 12, 'bold'),
                bg=self.colors['primary'],
                fg='white'
            ).pack(side=tk.LEFT, padx=15, pady=10)

        return card

    def create_event_card(self, parent, event: Dict[str, Any]) -> tk.Frame:
        """Create an event card with details and actions"""
        card = tk.Frame(
            parent,
            bg='white',
            relief=tk.RAISED,
            bd=1,
            highlightbackground=self.colors['border'],
            highlightthickness=1
        )

        # Category badge
        category_color = self.category_colors.get(event['category'], '#9E9E9E')
        badge_frame = tk.Frame(card, bg=category_color, height=5)
        badge_frame.pack(fill=tk.X)

        content = tk.Frame(card, bg='white')
        content.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        # Title and category
        title_label = tk.Label(
            content,
            text=event['title'],
            font=('Helvetica', 14, 'bold'),
            bg='white',
            fg=self.colors['text'],
            anchor=tk.W,
            wraplength=400,
            justify=tk.LEFT
        )
        title_label.pack(anchor=tk.W, pady=(0, 5))

        category_label = tk.Label(
            content,
            text=event['category'],
            font=('Helvetica', 9),
            bg=category_color,
            fg='white',
            padx=8,
            pady=2
        )
        category_label.pack(anchor=tk.W, pady=(0, 10))

        # Date and time
        dt_frame = tk.Frame(content, bg='white')
        dt_frame.pack(anchor=tk.W, pady=(0, 5))

        tk.Label(
            dt_frame,
            text="📅",
            font=('Helvetica', 10),
            bg='white'
        ).pack(side=tk.LEFT, padx=(0, 5))

        tk.Label(
            dt_frame,
            text=self.format_datetime(event['start_datetime']),
            font=('Helvetica', 10),
            bg='white',
            fg=self.colors['text']
        ).pack(side=tk.LEFT)

        # Location
        loc_frame = tk.Frame(content, bg='white')
        loc_frame.pack(anchor=tk.W, pady=(0, 10))

        tk.Label(
            loc_frame,
            text="📍",
            font=('Helvetica', 10),
            bg='white'
        ).pack(side=tk.LEFT, padx=(0, 5))

        location_text = event['location']
        if event.get('building'):
            location_text += f" - {event['building']}"
        if event.get('room'):
            location_text += f" {event['room']}"

        tk.Label(
            loc_frame,
            text=location_text,
            font=('Helvetica', 10),
            bg='white',
            fg=self.colors['text']
        ).pack(side=tk.LEFT)

        # Description preview
        if event.get('description'):
            desc = event['description'][:150]
            if len(event['description']) > 150:
                desc += "..."

            desc_label = tk.Label(
                content,
                text=desc,
                font=('Helvetica', 9),
                bg='white',
                fg=self.colors['text_light'],
                anchor=tk.W,
                justify=tk.LEFT,
                wraplength=400
            )
            desc_label.pack(anchor=tk.W, pady=(0, 10))

        # Stats row
        stats_frame = tk.Frame(content, bg='white')
        stats_frame.pack(anchor=tk.W, pady=(0, 10))

        # RSVPs
        tk.Label(
            stats_frame,
            text=f"👥 {event.get('rsvp_count', 0)} going",
            font=('Helvetica', 9),
            bg='white',
            fg=self.colors['text_light']
        ).pack(side=tk.LEFT, padx=(0, 15))

        # Rating
        if event.get('average_rating'):
            stars = '★' * int(round(event['average_rating']))
            stars += '☆' * (5 - int(round(event['average_rating'])))
            tk.Label(
                stats_frame,
                text=f"{stars} ({event['rating_count']})",
                font=('Helvetica', 9),
                bg='white',
                fg=self.colors['secondary']
            ).pack(side=tk.LEFT, padx=(0, 15))

        # Action buttons
        btn_frame = tk.Frame(content, bg='white')
        btn_frame.pack(anchor=tk.W, pady=(5, 0))

        tk.Button(
            btn_frame,
            text="View Details",
            command=lambda: self.show_event_details(event['event_id']),
            bg=self.colors['background'],
            relief=tk.FLAT,
            cursor='hand2',
            padx=10,
            pady=5
        ).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(
            btn_frame,
            text="RSVP",
            command=lambda: self.rsvp_dialog(event['event_id']),
            bg=self.colors['primary'],
            fg='white',
            relief=tk.FLAT,
            cursor='hand2',
            padx=10,
            pady=5
        ).pack(side=tk.LEFT, padx=(0, 5))

        return card

    def create_recommendation_card(self, parent, event: Dict[str, Any]) -> tk.Frame:
        """Create a compact recommendation card"""
        card = tk.Frame(parent, bg=self.colors['background'], relief=tk.FLAT, bd=1)

        content = tk.Frame(card, bg='white', padx=10, pady=10)
        content.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = tk.Label(
            content,
            text=event['title'],
            font=('Helvetica', 11, 'bold'),
            bg='white',
            anchor=tk.W,
            wraplength=280,
            justify=tk.LEFT,
            cursor='hand2'
        )
        title_label.pack(anchor=tk.W, pady=(0, 5))
        title_label.bind('<Button-1>', lambda e: self.show_event_details(event['event_id']))

        # Category
        category_color = self.category_colors.get(event['category'], '#9E9E9E')
        cat_label = tk.Label(
            content,
            text=event['category'],
            font=('Helvetica', 8),
            bg=category_color,
            fg='white',
            padx=6,
            pady=2
        )
        cat_label.pack(anchor=tk.W, pady=(0, 5))

        # Date
        tk.Label(
            content,
            text="📅 " + self.format_date(event['start_datetime']),
            font=('Helvetica', 9),
            bg='white',
            fg=self.colors['text_light']
        ).pack(anchor=tk.W, pady=(0, 5))

        # Match score
        score = event.get('recommendation_score', 0)
        score_color = self.colors['success'] if score > 50 else self.colors['secondary']

        tk.Label(
            content,
            text=f"Match: {score}%",
            font=('Helvetica', 9, 'bold'),
            bg='white',
            fg=score_color
        ).pack(anchor=tk.W, pady=(0, 5))

        # RSVP button
        tk.Button(
            content,
            text="RSVP Now",
            command=lambda: self.rsvp_dialog(event['event_id']),
            bg=self.colors['primary'],
            fg='white',
            relief=tk.FLAT,
            cursor='hand2',
            padx=8,
            pady=4,
            font=('Helvetica', 9)
        ).pack(anchor=tk.W, pady=(5, 0))

        # Separator
        tk.Frame(card, bg=self.colors['border'], height=1).pack(fill=tk.X)

        return card

    # Calendar methods

    def update_calendar(self):
        """Update calendar display"""
        # Clear existing calendar
        for widget in self.calendar_frame.winfo_children():
            widget.destroy()

        # Update month label
        month_name = calendar.month_name[self.current_month]
        self.month_label.config(text=f"{month_name} {self.current_year}")

        # Day headers
        days = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']
        for i, day in enumerate(days):
            tk.Label(
                self.calendar_frame,
                text=day,
                font=('Helvetica', 9, 'bold'),
                bg='white',
                fg=self.colors['text_light'],
                width=4
            ).grid(row=0, column=i, padx=1, pady=1)

        # Get calendar data
        cal = calendar.monthcalendar(self.current_year, self.current_month)

        # Get events for this month
        start_date = f"{self.current_year}-{self.current_month:02d}-01"
        end_date = f"{self.current_year}-{self.current_month:02d}-{calendar.monthrange(self.current_year, self.current_month)[1]}"

        try:
            events = self.service.search_events(
                start_date=start_date,
                end_date=end_date,
                upcoming_only=False
            )

            # Group events by day
            events_by_day = {}
            for event in events:
                day = int(event['start_datetime'][8:10])
                if day not in events_by_day:
                    events_by_day[day] = []
                events_by_day[day].append(event)

        except Exception:
            events_by_day = {}

        # Draw calendar days
        today = datetime.now()
        for week_num, week in enumerate(cal):
            for day_num, day in enumerate(week):
                if day == 0:
                    continue

                # Determine if this is today
                is_today = (
                    day == today.day and
                    self.current_month == today.month and
                    self.current_year == today.year
                )

                # Determine if there are events
                has_events = day in events_by_day

                # Create day button
                bg_color = 'white'
                fg_color = self.colors['text']

                if is_today:
                    bg_color = self.colors['primary']
                    fg_color = 'white'
                elif has_events:
                    bg_color = self.colors['background']

                btn = tk.Button(
                    self.calendar_frame,
                    text=str(day),
                    font=('Helvetica', 9, 'bold' if is_today else 'normal'),
                    bg=bg_color,
                    fg=fg_color,
                    relief=tk.FLAT,
                    cursor='hand2' if has_events else 'arrow',
                    width=4,
                    height=2,
                    command=lambda d=day: self.select_calendar_date(d)
                )
                btn.grid(row=week_num+1, column=day_num, padx=1, pady=1, sticky='nsew')

                # Add event indicator
                if has_events:
                    indicator = tk.Label(
                        btn,
                        text="•",
                        font=('Helvetica', 14),
                        bg=bg_color,
                        fg=self.colors['secondary']
                    )
                    indicator.place(relx=0.8, rely=0.2)

    def prev_month(self):
        """Go to previous month"""
        self.current_month -= 1
        if self.current_month < 1:
            self.current_month = 12
            self.current_year -= 1
        self.update_calendar()

    def next_month(self):
        """Go to next month"""
        self.current_month += 1
        if self.current_month > 12:
            self.current_month = 1
            self.current_year += 1
        self.update_calendar()

    def select_calendar_date(self, day: int):
        """Select a date from calendar"""
        self.selected_date = f"{self.current_year}-{self.current_month:02d}-{day:02d}"
        self.apply_filters()

    # Event list methods

    def load_events(self, events: Optional[List[Dict[str, Any]]] = None):
        """Load and display events"""
        # Clear existing
        for widget in self.event_list_frame.winfo_children():
            widget.destroy()

        if events is None:
            try:
                events = self.service.get_upcoming_events(limit=50)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load events: {e}")
                return

        # Update count
        self.event_count_label.config(text=f"{len(events)} events")

        if not events:
            tk.Label(
                self.event_list_frame,
                text="No events found",
                font=('Helvetica', 12),
                bg=self.colors['background'],
                fg=self.colors['text_light']
            ).pack(pady=50)
            return

        # Create event cards
        for event in events:
            card = self.create_event_card(self.event_list_frame, event)
            card.pack(fill=tk.X, pady=(0, 15))

    def load_recommendations(self):
        """Load personalized recommendations"""
        # Clear existing
        for widget in self.recommendations_frame.winfo_children():
            widget.destroy()

        user_id = self.auth.get_current_user()['id']

        try:
            recommendations = self.service.get_personalized_recommendations(
                user_id=user_id,
                limit=10
            )

            if not recommendations:
                tk.Label(
                    self.recommendations_frame,
                    text="No recommendations yet.\n\nSet your interests to get\npersonalized suggestions!",
                    font=('Helvetica', 10),
                    bg='white',
                    fg=self.colors['text_light'],
                    justify=tk.CENTER
                ).pack(pady=20)

                tk.Button(
                    self.recommendations_frame,
                    text="Set Interests",
                    command=self.manage_interests_dialog,
                    bg=self.colors['primary'],
                    fg='white',
                    relief=tk.FLAT,
                    cursor='hand2',
                    padx=15,
                    pady=8
                ).pack()
                return

            # Create recommendation cards
            for event in recommendations:
                card = self.create_recommendation_card(self.recommendations_frame, event)
                card.pack(fill=tk.X, pady=(0, 5))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load recommendations: {e}")

    def apply_filters(self):
        """Apply search and category filters"""
        keyword = self.search_var.get().strip() or None
        category = self.category_var.get()
        category = category if category != "All" else None

        try:
            events = self.service.search_events(
                category=category,
                keyword=keyword,
                start_date=self.selected_date,
                upcoming_only=True
            )

            self.load_events(events)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to search events: {e}")

    def clear_filters(self):
        """Clear all filters"""
        self.search_var.set("")
        self.category_var.set("All")
        self.selected_date = None
        self.load_events()

    def refresh_all(self):
        """Refresh all panels"""
        self.update_calendar()
        self.load_events()
        self.load_recommendations()

    # Dialog methods

    def rsvp_dialog(self, event_id: int):
        """Show RSVP dialog"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("RSVP to Event")
        dialog.geometry("500x400")
        dialog.transient(self.parent)
        dialog.grab_set()

        # Get event details
        try:
            event = self.service.get_event(event_id)
            if not event:
                messagebox.showerror("Error", "Event not found")
                dialog.destroy()
                return

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load event: {e}")
            dialog.destroy()
            return

        # Event details
        details_frame = tk.Frame(dialog, bg='white', padx=20, pady=20)
        details_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            details_frame,
            text=event['title'],
            font=('Helvetica', 16, 'bold'),
            bg='white'
        ).pack(anchor=tk.W, pady=(0, 10))

        tk.Label(
            details_frame,
            text=f"📅 {self.format_datetime(event['start_datetime'])}",
            font=('Helvetica', 11),
            bg='white'
        ).pack(anchor=tk.W, pady=5)

        tk.Label(
            details_frame,
            text=f"📍 {event['location']}",
            font=('Helvetica', 11),
            bg='white'
        ).pack(anchor=tk.W, pady=5)

        if event['max_capacity'] > 0:
            tk.Label(
                details_frame,
                text=f"Capacity: {event.get('rsvp_count', 0)}/{event['max_capacity']}",
                font=('Helvetica', 10),
                bg='white',
                fg=self.colors['text_light']
            ).pack(anchor=tk.W, pady=10)

        # RSVP options
        tk.Label(
            details_frame,
            text="Your Response:",
            font=('Helvetica', 12, 'bold'),
            bg='white'
        ).pack(anchor=tk.W, pady=(20, 10))

        rsvp_var = tk.StringVar(value="Going")

        for status in self.service.RSVP_STATUS:
            tk.Radiobutton(
                details_frame,
                text=status,
                variable=rsvp_var,
                value=status,
                font=('Helvetica', 11),
                bg='white'
            ).pack(anchor=tk.W, pady=5)

        # Calendar option
        calendar_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            details_frame,
            text="Add to my calendar",
            variable=calendar_var,
            font=('Helvetica', 11),
            bg='white'
        ).pack(anchor=tk.W, pady=10)

        # Buttons
        btn_frame = tk.Frame(dialog, bg='white', padx=20, pady=20)
        btn_frame.pack(fill=tk.X)

        def submit_rsvp():
            try:
                user_id = self.auth.get_current_user()['id']
                self.service.rsvp_to_event(
                    event_id=event_id,
                    user_id=user_id,
                    status=rsvp_var.get(),
                    add_to_calendar=calendar_var.get()
                )

                messagebox.showinfo("Success", f"RSVP saved as '{rsvp_var.get()}'!")
                dialog.destroy()
                self.refresh_all()

            except ValueError as e:
                messagebox.showerror("Error", str(e))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to RSVP: {e}")

        tk.Button(
            btn_frame,
            text="Submit RSVP",
            command=submit_rsvp,
            bg=self.colors['success'],
            fg='white',
            font=('Helvetica', 11, 'bold'),
            relief=tk.FLAT,
            cursor='hand2',
            padx=20,
            pady=10
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

        tk.Button(
            btn_frame,
            text="Cancel",
            command=dialog.destroy,
            bg=self.colors['background'],
            font=('Helvetica', 11),
            relief=tk.FLAT,
            cursor='hand2',
            padx=20,
            pady=10
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))

    def show_event_details(self, event_id: int):
        """Show detailed event information"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Event Details")
        dialog.geometry("700x600")
        dialog.transient(self.parent)

        # Create scrollable content
        canvas = tk.Canvas(dialog, bg='white')
        scrollbar = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=canvas.yview)

        content = tk.Frame(canvas, bg='white', padx=30, pady=20)

        content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=content, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        try:
            event = self.service.get_event(event_id)
            if not event:
                messagebox.showerror("Error", "Event not found")
                dialog.destroy()
                return

            # Title
            tk.Label(
                content,
                text=event['title'],
                font=('Helvetica', 20, 'bold'),
                bg='white',
                wraplength=600,
                justify=tk.LEFT
            ).pack(anchor=tk.W, pady=(0, 10))

            # Category badge
            category_color = self.category_colors.get(event['category'], '#9E9E9E')
            tk.Label(
                content,
                text=event['category'],
                font=('Helvetica', 10),
                bg=category_color,
                fg='white',
                padx=10,
                pady=5
            ).pack(anchor=tk.W, pady=(0, 20))

            # Details
            details = [
                ("📅 Date & Time", f"{self.format_datetime(event['start_datetime'])}\nto {self.format_datetime(event['end_datetime'])}"),
                ("📍 Location", f"{event['location']}{' - ' + event['building'] if event['building'] else ''}{' ' + event['room'] if event['room'] else ''}"),
                ("👤 Organizer", event['organizer_name'] or event['organizer_id'])
            ]

            for label, value in details:
                frame = tk.Frame(content, bg='white')
                frame.pack(anchor=tk.W, pady=10)

                tk.Label(
                    frame,
                    text=label,
                    font=('Helvetica', 11, 'bold'),
                    bg='white'
                ).pack(anchor=tk.W)

                tk.Label(
                    frame,
                    text=value,
                    font=('Helvetica', 11),
                    bg='white',
                    fg=self.colors['text_light'],
                    wraplength=600,
                    justify=tk.LEFT
                ).pack(anchor=tk.W, padx=(20, 0), pady=(5, 0))

            # Description
            if event['description']:
                tk.Label(
                    content,
                    text="Description",
                    font=('Helvetica', 12, 'bold'),
                    bg='white'
                ).pack(anchor=tk.W, pady=(20, 10))

                tk.Label(
                    content,
                    text=event['description'],
                    font=('Helvetica', 11),
                    bg='white',
                    fg=self.colors['text'],
                    wraplength=600,
                    justify=tk.LEFT
                ).pack(anchor=tk.W, pady=(0, 20))

            # Statistics
            stats = self.service.get_event_statistics(event_id)

            tk.Label(
                content,
                text="Event Statistics",
                font=('Helvetica', 12, 'bold'),
                bg='white'
            ).pack(anchor=tk.W, pady=(20, 10))

            stats_text = f"👥 {event.get('rsvp_count', 0)} people going"

            if stats['average_rating']:
                stars = '★' * int(round(stats['average_rating']))
                stars += '☆' * (5 - int(round(stats['average_rating'])))
                stats_text += f"\n{stars} {stats['average_rating']}/5 ({stats['review_count']} reviews)"

            tk.Label(
                content,
                text=stats_text,
                font=('Helvetica', 11),
                bg='white',
                justify=tk.LEFT
            ).pack(anchor=tk.W, padx=(20, 0))

            # Action buttons
            btn_frame = tk.Frame(content, bg='white')
            btn_frame.pack(anchor=tk.W, pady=30)

            tk.Button(
                btn_frame,
                text="RSVP to Event",
                command=lambda: [dialog.destroy(), self.rsvp_dialog(event_id)],
                bg=self.colors['primary'],
                fg='white',
                font=('Helvetica', 11, 'bold'),
                relief=tk.FLAT,
                cursor='hand2',
                padx=20,
                pady=10
            ).pack(side=tk.LEFT, padx=(0, 10))

            tk.Button(
                btn_frame,
                text="Check In",
                command=lambda: self.check_in_to_event(event_id),
                bg=self.colors['success'],
                fg='white',
                font=('Helvetica', 11, 'bold'),
                relief=tk.FLAT,
                cursor='hand2',
                padx=20,
                pady=10
            ).pack(side=tk.LEFT)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load event details: {e}")
            dialog.destroy()

    def check_in_to_event(self, event_id: int):
        """Check in to an event"""
        try:
            user_id = self.auth.get_current_user()['id']
            self.service.check_in_to_event(event_id=event_id, user_id=user_id)

            messagebox.showinfo("Success", "Successfully checked in to the event!\nEnjoy the event!")
            self.refresh_all()

        except ValueError as e:
            messagebox.showerror("Error", str(e))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to check in: {e}")

    def show_my_rsvps(self):
        """Show user's RSVPs"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("My RSVPs")
        dialog.geometry("600x500")
        dialog.transient(self.parent)

        user_id = self.auth.get_current_user()['id']

        try:
            rsvps = self.service.get_user_rsvps(user_id=user_id, upcoming_only=True)

            # Create scrollable content
            canvas = tk.Canvas(dialog, bg='white')
            scrollbar = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=canvas.yview)

            content = tk.Frame(canvas, bg='white', padx=20, pady=20)

            content.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=content, anchor=tk.NW)
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            if not rsvps:
                tk.Label(
                    content,
                    text="You haven't RSVP'd to any events yet.",
                    font=('Helvetica', 12),
                    bg='white',
                    fg=self.colors['text_light']
                ).pack(pady=50)
                return

            # Group by status
            going = [e for e in rsvps if e['rsvp_status'] == 'Going']
            interested = [e for e in rsvps if e['rsvp_status'] == 'Interested']

            if going:
                tk.Label(
                    content,
                    text=f"Going ({len(going)})",
                    font=('Helvetica', 14, 'bold'),
                    bg='white'
                ).pack(anchor=tk.W, pady=(0, 10))

                for event in going:
                    card = self.create_event_card(content, event)
                    card.pack(fill=tk.X, pady=(0, 10))

            if interested:
                tk.Label(
                    content,
                    text=f"Interested ({len(interested)})",
                    font=('Helvetica', 14, 'bold'),
                    bg='white'
                ).pack(anchor=tk.W, pady=(20, 10))

                for event in interested:
                    card = self.create_event_card(content, event)
                    card.pack(fill=tk.X, pady=(0, 10))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load RSVPs: {e}")

    def manage_interests_dialog(self):
        """Show interest preferences dialog"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Manage Interest Preferences")
        dialog.geometry("500x600")
        dialog.transient(self.parent)
        dialog.grab_set()

        # Header
        header = tk.Frame(dialog, bg=self.colors['primary'], height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="Interest Preferences",
            font=('Helvetica', 18, 'bold'),
            bg=self.colors['primary'],
            fg='white'
        ).pack(pady=20)

        # Content
        content = tk.Frame(dialog, bg='white', padx=30, pady=20)
        content.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            content,
            text="Set your interest level for each category (1-10):",
            font=('Helvetica', 11),
            bg='white'
        ).pack(anchor=tk.W, pady=(0, 20))

        user_id = self.auth.get_current_user()['id']

        try:
            current_interests = self.service.get_user_interests(user_id)

            sliders = {}

            for category in self.service.CATEGORIES:
                frame = tk.Frame(content, bg='white')
                frame.pack(fill=tk.X, pady=10)

                # Category label
                tk.Label(
                    frame,
                    text=category,
                    font=('Helvetica', 11, 'bold'),
                    bg='white',
                    width=20,
                    anchor=tk.W
                ).pack(side=tk.LEFT)

                # Slider
                current_value = current_interests.get(category, 5)
                slider = tk.Scale(
                    frame,
                    from_=1,
                    to=10,
                    orient=tk.HORIZONTAL,
                    bg='white',
                    highlightthickness=0,
                    length=200
                )
                slider.set(current_value)
                slider.pack(side=tk.LEFT, padx=10)

                sliders[category] = slider

            # Save button
            def save_interests():
                try:
                    for category, slider in sliders.items():
                        self.service.set_interest_preference(
                            user_id=user_id,
                            category=category,
                            interest_level=slider.get()
                        )

                    messagebox.showinfo("Success", "Interest preferences saved!\n\nYour recommendations will be updated.")
                    dialog.destroy()
                    self.load_recommendations()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save preferences: {e}")

            tk.Button(
                content,
                text="Save Preferences",
                command=save_interests,
                bg=self.colors['success'],
                fg='white',
                font=('Helvetica', 12, 'bold'),
                relief=tk.FLAT,
                cursor='hand2',
                padx=30,
                pady=12
            ).pack(pady=30)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load preferences: {e}")
            dialog.destroy()

    def create_event_dialog(self):
        """Show create event dialog"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Create New Event")
        dialog.geometry("600x700")
        dialog.transient(self.parent)
        dialog.grab_set()

        # Create scrollable content
        canvas = tk.Canvas(dialog, bg='white')
        scrollbar = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=canvas.yview)

        content = tk.Frame(canvas, bg='white', padx=30, pady=20)

        content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=content, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Header
        tk.Label(
            content,
            text="Create New Event",
            font=('Helvetica', 18, 'bold'),
            bg='white'
        ).pack(anchor=tk.W, pady=(0, 20))

        # Form fields
        fields = {}

        def add_field(label, widget_type='entry', options=None):
            frame = tk.Frame(content, bg='white')
            frame.pack(fill=tk.X, pady=10)

            tk.Label(
                frame,
                text=label,
                font=('Helvetica', 11, 'bold'),
                bg='white'
            ).pack(anchor=tk.W, pady=(0, 5))

            if widget_type == 'entry':
                widget = tk.Entry(frame, font=('Helvetica', 11))
                widget.pack(fill=tk.X)
            elif widget_type == 'text':
                widget = scrolledtext.ScrolledText(frame, height=4, font=('Helvetica', 11))
                widget.pack(fill=tk.X)
            elif widget_type == 'combobox':
                widget = ttk.Combobox(frame, values=options, font=('Helvetica', 11), state='readonly')
                widget.pack(fill=tk.X)
                if options:
                    widget.set(options[0])

            fields[label] = widget

        add_field("Event Title *")
        add_field("Description", 'text')
        add_field("Category *", 'combobox', self.service.CATEGORIES)
        add_field("Start Date & Time (YYYY-MM-DD HH:MM) *")
        add_field("End Date & Time (YYYY-MM-DD HH:MM) *")
        add_field("Location *")
        add_field("Building")
        add_field("Room")
        add_field("Max Capacity (0 for unlimited)")

        # Submit button
        def submit():
            try:
                # Get values
                title = fields["Event Title *"].get().strip()
                if not title:
                    messagebox.showerror("Error", "Event title is required")
                    return

                description = fields["Description"].get("1.0", tk.END).strip()
                category = fields["Category *"].get()
                start_datetime = fields["Start Date & Time (YYYY-MM-DD HH:MM) *"].get().strip()
                end_datetime = fields["End Date & Time (YYYY-MM-DD HH:MM) *"].get().strip()
                location = fields["Location *"].get().strip()
                building = fields["Building"].get().strip()
                room = fields["Room"].get().strip()
                max_capacity = fields["Max Capacity (0 for unlimited)"].get().strip()

                if not all([start_datetime, end_datetime, location]):
                    messagebox.showerror("Error", "Please fill in all required fields")
                    return

                max_capacity = int(max_capacity) if max_capacity.isdigit() else 0

                event_data = {
                    'title': title,
                    'description': description,
                    'category': category,
                    'start_datetime': start_datetime,
                    'end_datetime': end_datetime,
                    'location': location,
                    'building': building,
                    'room': room,
                    'max_capacity': max_capacity,
                    'organizer_name': self.auth.get_current_user()['id']
                }

                user_id = self.auth.get_current_user()['id']
                event_id = self.service.create_event(event_data, user_id)

                messagebox.showinfo("Success", f"Event created successfully!\nEvent ID: {event_id}")
                dialog.destroy()
                self.refresh_all()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create event: {e}")

        tk.Button(
            content,
            text="Create Event",
            command=submit,
            bg=self.colors['success'],
            fg='white',
            font=('Helvetica', 12, 'bold'),
            relief=tk.FLAT,
            cursor='hand2',
            padx=30,
            pady=12
        ).pack(pady=30)

    def show_statistics(self):
        """Show user statistics"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("My Event Statistics")
        dialog.geometry("500x400")
        dialog.transient(self.parent)

        content = tk.Frame(dialog, bg='white', padx=30, pady=20)
        content.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            content,
            text="My Event Statistics",
            font=('Helvetica', 18, 'bold'),
            bg='white'
        ).pack(anchor=tk.W, pady=(0, 20))

        user_id = self.auth.get_current_user()['id']

        try:
            stats = self.service.get_user_statistics(user_id)

            # Main stats
            main_stats = [
                ("Total RSVPs", stats['total_rsvps']),
                ("Events Attended", stats['total_attended']),
                ("Reviews Written", stats['reviews_written']),
                ("Photos Uploaded", stats['photos_uploaded'])
            ]

            for label, value in main_stats:
                frame = tk.Frame(content, bg=self.colors['background'], padx=20, pady=15)
                frame.pack(fill=tk.X, pady=5)

                tk.Label(
                    frame,
                    text=str(value),
                    font=('Helvetica', 24, 'bold'),
                    bg=self.colors['background'],
                    fg=self.colors['primary']
                ).pack(side=tk.LEFT)

                tk.Label(
                    frame,
                    text=label,
                    font=('Helvetica', 12),
                    bg=self.colors['background'],
                    fg=self.colors['text_light']
                ).pack(side=tk.LEFT, padx=(20, 0))

            # Category breakdown
            if stats['attendance_by_category']:
                tk.Label(
                    content,
                    text="Attendance by Category",
                    font=('Helvetica', 12, 'bold'),
                    bg='white'
                ).pack(anchor=tk.W, pady=(20, 10))

                for category, count in sorted(
                    stats['attendance_by_category'].items(),
                    key=lambda x: x[1],
                    reverse=True
                ):
                    frame = tk.Frame(content, bg='white')
                    frame.pack(fill=tk.X, pady=3)

                    tk.Label(
                        frame,
                        text=category,
                        font=('Helvetica', 10),
                        bg='white',
                        width=20,
                        anchor=tk.W
                    ).pack(side=tk.LEFT)

                    tk.Label(
                        frame,
                        text=f"{count} events",
                        font=('Helvetica', 10, 'bold'),
                        bg='white',
                        fg=self.colors['primary']
                    ).pack(side=tk.LEFT)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load statistics: {e}")
            dialog.destroy()

    # Helper methods

    def format_datetime(self, dt_str: str) -> str:
        """Format datetime for display"""
        try:
            dt = datetime.fromisoformat(dt_str)
            return dt.strftime("%a, %b %d at %I:%M %p")
        except (ValueError, TypeError):
            return dt_str

    def format_date(self, dt_str: str) -> str:
        """Format date for display"""
        try:
            dt = datetime.fromisoformat(dt_str)
            return dt.strftime("%b %d, %Y")
        except (ValueError, TypeError):
            return dt_str[:10]

    def close_window(self):
        """Close the Events Discovery GUI and return to main menu"""
        # Close the Toplevel window
        self.window.destroy()


def main(parent=None):
    """Entry point for the Events GUI"""
    if parent is None:
        from education_system.university_system.modules.shared.gui.auth.launch_guard import (
            require_launcher_auth,
        )
        if require_launcher_auth("Events GUI") is None:
            return
        root = tk.Tk()
        root.title("Event Discovery Engine")
        root.geometry("1400x800")
        parent = root
    else:
        root = None

    app = EventsGUI(parent)

    if root is not None:
        root.mainloop()


if __name__ == '__main__':
    main()
