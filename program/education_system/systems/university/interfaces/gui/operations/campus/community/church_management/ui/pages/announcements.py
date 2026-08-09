"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiPagesAnnouncementsMixin:
    def show_announcements(self):
        """Display church announcements."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.announcements.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text=_t("church.announcements.add_announcement"), command=self.add_announcement,
                  bg="#27ae60", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        # Announcements display
        announcements_frame = tk.Frame(self.content_frame, bg="white")
        announcements_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(announcements_frame, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(announcements_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="white")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for announcement in self.announcements:
            ann_frame = tk.Frame(scrollable_frame, bg="#fff8dc", relief=tk.RAISED, bd=1)
            ann_frame.pack(fill=tk.X, pady=5, padx=10)

            tk.Label(ann_frame, text=announcement['title'], font=("Arial", 12, "bold"),
                    bg="#fff8dc", fg="#8b4513").pack(anchor="w", padx=10, pady=5)
            tk.Label(ann_frame, text=announcement['content'], font=("Arial", 10),
                    bg="#fff8dc", fg="#5d4037", wraplength=600, justify="left").pack(anchor="w", padx=10)
            tk.Label(ann_frame, text=f"Posted: {announcement['date']} by {announcement.get('posted_by', 'Admin')}",
                    font=("Arial", 8), bg="#fff8dc", fg="gray").pack(anchor="e", padx=10, pady=5)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
