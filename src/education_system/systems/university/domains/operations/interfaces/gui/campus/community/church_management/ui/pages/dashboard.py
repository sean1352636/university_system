"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiPagesDashboardMixin:
    def show_dashboard(self):
        """Display the main dashboard with statistics."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.dashboard.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        # Statistics frame
        stats_frame = tk.Frame(self.content_frame, bg="white")
        stats_frame.pack(pady=20)

        stats = [
            (_t("church.dashboard.total_members"), len(self.members), "#3498db"),
            (_t("church.dashboard.total_donations"), f"£{sum(d['amount'] for d in self.donations):,.2f}", "#27ae60"),
            (_t("church.dashboard.upcoming_events"), len([e for e in self.events if e.get('date', '') >= datetime.now().strftime('%Y-%m-%d')]), "#e74c3c"),
            (_t("church.dashboard.prayer_requests"), len(self.prayer_requests), "#9b59b6"),
            (_t("church.dashboard.active_volunteers"), len(self.volunteers), "#f39c12"),
            (_t("church.dashboard.small_groups"), len(self.small_groups), "#1abc9c"),
        ]

        for i, (label, value, color) in enumerate(stats):
            row, col = divmod(i, 3)
            stat_card = tk.Frame(stats_frame, bg=color, relief=tk.RAISED, bd=2)
            stat_card.grid(row=row, column=col, padx=15, pady=15, ipadx=30, ipady=20)

            tk.Label(stat_card, text=label, font=("Arial", 12), bg=color, fg="white").pack()
            tk.Label(stat_card, text=str(value), font=("Arial", 24, "bold"), bg=color, fg="white").pack()

        # Quick verse
        verses = [
            '"For where two or three gather in my name, there am I with them." - Matthew 18:20',
            '"Love one another as I have loved you." - John 13:34',
            '"The Lord is my shepherd; I shall not want." - Psalm 23:1',
            '"I can do all things through Christ who strengthens me." - Philippians 4:13',
        ]
        verse_frame = tk.Frame(self.content_frame, bg="#fff8dc", relief=tk.GROOVE, bd=2)
        verse_frame.pack(pady=30, padx=50, fill=tk.X)
        tk.Label(
            verse_frame,
            text=_t("church.dashboard.verse_of_the_day"),
            font=("Georgia", 14, "bold"),
            bg="#fff8dc",
            fg="#8b4513"
        ).pack(pady=10)
        tk.Label(
            verse_frame,
            text=random.choice(verses),
            font=("Georgia", 12, "italic"),
            bg="#fff8dc",
            fg="#5d4037",
            wraplength=600
        ).pack(pady=10)
