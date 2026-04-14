"""
GUI Interface for Interest-Based Social Matching.

Features:
- Visual interest profile with tag cloud
- Match results with compatibility scores
- Profile cards with shared interests
- Buddy request management
- Team formation interface
- Club recommendations grid
- Activity calendar view
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
import json
from typing import Optional

from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.modules.domain.student_affairs.social_matching.services.social_matching_service import (
    SocialMatchingService,
    INTEREST_CATEGORIES,
    PERSONALITY_TYPES,
    GROUP_SIZE_PREFERENCES,
    ACTIVITY_LEVELS
)


class SocialMatchingGUI:
    """GUI interface for social matching system."""

    def __init__(self, parent):
        """Initialize the GUI."""
        self.parent = parent
        self.service = SocialMatchingService()
        self.auth = get_auth()

        self.window = tk.Toplevel(parent)
        self.window.title("Interest-Based Social Matching")
        self.window.geometry("1200x800")

        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to use Social Matching.")
            self.window.destroy()
            return

        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface."""
        # Main notebook for tabs
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create tabs
        self.create_interests_tab()
        self.create_matches_tab()
        self.create_buddy_requests_tab()
        self.create_teams_tab()
        self.create_clubs_tab()
        self.create_activities_tab()
        self.create_profile_tab()

    # ========== Interests Tab ==========

    def create_interests_tab(self):
        """Create interests management tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Interests")

        # Header
        header = ttk.Label(tab, text="My Interest Profile", font=('Arial', 16, 'bold'))
        header.pack(pady=10)

        # Top frame for buttons
        button_frame = ttk.Frame(tab)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Add Interest", command=self.add_interest).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Remove Selected", command=self.remove_interest).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_interests).pack(side=tk.LEFT, padx=5)

        # Interests display
        columns = ('ID', 'Category', 'Interest', 'Level', 'Public')
        self.interests_tree = ttk.Treeview(tab, columns=columns, show='headings', height=15)

        for col in columns:
            self.interests_tree.heading(col, text=col)

        self.interests_tree.column('ID', width=50)
        self.interests_tree.column('Category', width=120)
        self.interests_tree.column('Interest', width=250)
        self.interests_tree.column('Level', width=200)
        self.interests_tree.column('Public', width=80)

        self.interests_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Scrollbar
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.interests_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.interests_tree.configure(yscrollcommand=scrollbar.set)

        # Load interests
        self.load_interests()

    def load_interests(self):
        """Load and display user interests."""
        # Clear tree
        for item in self.interests_tree.get_children():
            self.interests_tree.delete(item)

        user_id = self.auth.get_current_user()['username']
        interests = self.service.get_user_interests(user_id)

        for interest in interests:
            level_bar = "█" * interest['level'] + "░" * (10 - interest['level'])
            level_display = f"{level_bar} ({interest['level']}/10)"
            public = "Yes" if interest['is_public'] else "No"

            self.interests_tree.insert('', tk.END, values=(
                interest['interest_id'],
                interest['category'],
                interest['name'],
                level_display,
                public
            ))

    def add_interest(self):
        """Open dialog to add new interest."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Add Interest")
        dialog.geometry("400x350")

        ttk.Label(dialog, text="Add New Interest", font=('Arial', 14, 'bold')).pack(pady=10)

        # Category
        ttk.Label(dialog, text="Category:").pack(pady=5)
        category_var = tk.StringVar()
        category_combo = ttk.Combobox(dialog, textvariable=category_var, values=INTEREST_CATEGORIES, state='readonly')
        category_combo.pack(pady=5)
        category_combo.current(0)

        # Interest name
        ttk.Label(dialog, text="Interest Name:").pack(pady=5)
        name_var = tk.StringVar()
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=30)
        name_entry.pack(pady=5)

        # Interest level
        ttk.Label(dialog, text="Interest Level (1-10):").pack(pady=5)
        level_var = tk.IntVar(value=5)
        level_scale = ttk.Scale(dialog, from_=1, to=10, variable=level_var, orient=tk.HORIZONTAL)
        level_scale.pack(pady=5)

        level_label = ttk.Label(dialog, text="5")
        level_label.pack()

        def update_level_label(val):
            level_label.config(text=str(int(float(val))))

        level_scale.configure(command=update_level_label)

        # Public checkbox
        public_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(dialog, text="Make this interest public", variable=public_var).pack(pady=10)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def save_interest():
            category = category_var.get()
            name = name_var.get().strip()
            level = level_var.get()
            is_public = public_var.get()

            if not name:
                messagebox.showerror("Error", "Please enter an interest name.")
                return

            user_id = self.auth.get_current_user()['username']

            try:
                if self.service.add_user_interest(user_id, category, name, level, is_public):
                    messagebox.showinfo("Success", f"Added '{name}' to {category}!")
                    dialog.destroy()
                    self.load_interests()
                else:
                    messagebox.showerror("Error", "Failed to add interest (may already exist).")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(button_frame, text="Save", command=save_interest).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def remove_interest(self):
        """Remove selected interest."""
        selection = self.interests_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an interest to remove.")
            return

        item = self.interests_tree.item(selection[0])
        interest_id = item['values'][0]
        interest_name = item['values'][2]

        if messagebox.askyesno("Confirm", f"Remove '{interest_name}'?"):
            user_id = self.auth.get_current_user()['username']
            if self.service.remove_user_interest(user_id, interest_id):
                messagebox.showinfo("Success", "Interest removed!")
                self.load_interests()
            else:
                messagebox.showerror("Error", "Failed to remove interest.")

    # ========== Matches Tab ==========

    def create_matches_tab(self):
        """Create interest matches tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Find Matches")

        # Header
        header = ttk.Label(tab, text="Interest-Based Matches", font=('Arial', 16, 'bold'))
        header.pack(pady=10)

        # Search controls
        search_frame = ttk.Frame(tab)
        search_frame.pack(pady=10)

        ttk.Label(search_frame, text="Min Score:").pack(side=tk.LEFT, padx=5)
        self.min_score_var = tk.StringVar(value="30")
        ttk.Entry(search_frame, textvariable=self.min_score_var, width=10).pack(side=tk.LEFT, padx=5)

        ttk.Label(search_frame, text="Max Results:").pack(side=tk.LEFT, padx=5)
        self.max_results_var = tk.StringVar(value="20")
        ttk.Entry(search_frame, textvariable=self.max_results_var, width=10).pack(side=tk.LEFT, padx=5)

        ttk.Button(search_frame, text="Find Matches", command=self.find_matches).pack(side=tk.LEFT, padx=10)

        # Results frame
        results_frame = ttk.Frame(tab)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Matches list
        columns = ('User ID', 'Score', 'Shared Count')
        self.matches_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.matches_tree.heading(col, text=col)

        self.matches_tree.column('User ID', width=200)
        self.matches_tree.column('Score', width=150)
        self.matches_tree.column('Shared Count', width=150)

        self.matches_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Match details
        details_frame = ttk.LabelFrame(results_frame, text="Match Details")
        details_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10)

        self.match_details_text = scrolledtext.ScrolledText(details_frame, wrap=tk.WORD, height=20)
        self.match_details_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Button frame
        button_frame = ttk.Frame(details_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Send Buddy Request", command=self.send_request_to_match).pack(side=tk.LEFT, padx=5)

        # Bind selection event
        self.matches_tree.bind('<<TreeviewSelect>>', self.on_match_selected)

    def find_matches(self):
        """Find interest matches."""
        try:
            min_score = float(self.min_score_var.get())
            max_results = int(self.max_results_var.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid score or results value.")
            return

        # Clear tree
        for item in self.matches_tree.get_children():
            self.matches_tree.delete(item)

        user_id = self.auth.get_current_user()['username']
        matches = self.service.find_interest_matches(user_id, min_score, max_results)

        if not matches:
            messagebox.showinfo("Info", "No matches found. Try lowering the minimum score or adding more interests.")
            return

        for match in matches:
            self.matches_tree.insert('', tk.END, values=(
                match['user_id'],
                f"{match['compatibility_score']:.1f}%",
                match['shared_count']
            ), tags=(json.dumps(match),))

        messagebox.showinfo("Success", f"Found {len(matches)} matches!")

    def on_match_selected(self, event):
        """Handle match selection."""
        selection = self.matches_tree.selection()
        if not selection:
            return

        item = self.matches_tree.item(selection[0])
        # Get match data from tags
        match_data = json.loads(item['tags'][0])

        # Display match details
        self.match_details_text.delete(1.0, tk.END)
        self.match_details_text.insert(tk.END, f"Student ID: {match_data['user_id']}\n\n")
        self.match_details_text.insert(tk.END, f"Compatibility Score: {match_data['compatibility_score']:.1f}%\n\n")
        self.match_details_text.insert(tk.END, f"Shared Interests ({match_data['shared_count']}):\n")

        for interest in match_data['shared_interests']:
            self.match_details_text.insert(tk.END, f"  • {interest}\n")

    def send_request_to_match(self):
        """Send buddy request to selected match."""
        selection = self.matches_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a match first.")
            return

        item = self.matches_tree.item(selection[0])
        receiver_id = item['values'][0]

        self.open_buddy_request_dialog(receiver_id)

    # ========== Buddy Requests Tab ==========

    def create_buddy_requests_tab(self):
        """Create buddy requests tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Buddy Requests")

        # Header
        header = ttk.Label(tab, text="Buddy Requests", font=('Arial', 16, 'bold'))
        header.pack(pady=10)

        # Sub-tabs for sent/received
        sub_notebook = ttk.Notebook(tab)
        sub_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Received requests
        received_frame = ttk.Frame(sub_notebook)
        sub_notebook.add(received_frame, text="Received")

        ttk.Button(received_frame, text="Refresh", command=self.load_received_requests).pack(pady=5)

        columns = ('ID', 'From', 'Type', 'Destination', 'Message', 'Date')
        self.received_tree = ttk.Treeview(received_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.received_tree.heading(col, text=col)

        self.received_tree.column('ID', width=50)
        self.received_tree.column('From', width=120)
        self.received_tree.column('Type', width=100)
        self.received_tree.column('Destination', width=150)
        self.received_tree.column('Message', width=300)
        self.received_tree.column('Date', width=150)

        self.received_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        button_frame = ttk.Frame(received_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Accept", command=lambda: self.respond_to_request(True)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Decline", command=lambda: self.respond_to_request(False)).pack(side=tk.LEFT, padx=5)

        # Sent requests
        sent_frame = ttk.Frame(sub_notebook)
        sub_notebook.add(sent_frame, text="Sent")

        ttk.Button(sent_frame, text="Refresh", command=self.load_sent_requests).pack(pady=5)

        columns = ('ID', 'To', 'Type', 'Destination', 'Status', 'Date')
        self.sent_tree = ttk.Treeview(sent_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.sent_tree.heading(col, text=col)

        self.sent_tree.column('ID', width=50)
        self.sent_tree.column('To', width=120)
        self.sent_tree.column('Type', width=100)
        self.sent_tree.column('Destination', width=150)
        self.sent_tree.column('Status', width=100)
        self.sent_tree.column('Date', width=150)

        self.sent_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Load requests
        self.load_received_requests()
        self.load_sent_requests()

    def load_received_requests(self):
        """Load received buddy requests."""
        for item in self.received_tree.get_children():
            self.received_tree.delete(item)

        user_id = self.auth.get_current_user()['username']
        requests = self.service.get_buddy_requests(user_id, 'pending', 'received')

        for req in requests:
            self.received_tree.insert('', tk.END, values=(
                req['request_id'],
                req['sender_id'],
                req['type'],
                req['destination'] or 'N/A',
                req['message'][:50] if req['message'] else 'N/A',
                req['sent_at']
            ))

    def load_sent_requests(self):
        """Load sent buddy requests."""
        for item in self.sent_tree.get_children():
            self.sent_tree.delete(item)

        user_id = self.auth.get_current_user()['username']
        requests = self.service.get_buddy_requests(user_id, 'pending', 'sent')

        for req in requests:
            self.sent_tree.insert('', tk.END, values=(
                req['request_id'],
                req['receiver_id'],
                req['type'],
                req['destination'] or 'N/A',
                req['status'],
                req['sent_at']
            ))

    def respond_to_request(self, accept: bool):
        """Respond to a buddy request."""
        selection = self.received_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a request first.")
            return

        item = self.received_tree.item(selection[0])
        request_id = item['values'][0]

        user_id = self.auth.get_current_user()['username']

        if self.service.respond_to_buddy_request(request_id, user_id, accept):
            status = "accepted" if accept else "declined"
            messagebox.showinfo("Success", f"Request {status}!")
            self.load_received_requests()
        else:
            messagebox.showerror("Error", "Failed to respond to request.")

    def open_buddy_request_dialog(self, receiver_id: str = ""):
        """Open dialog to send buddy request."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Send Buddy Request")
        dialog.geometry("400x400")

        ttk.Label(dialog, text="Send Buddy Request", font=('Arial', 14, 'bold')).pack(pady=10)

        # Receiver ID
        ttk.Label(dialog, text="To Student ID:").pack(pady=5)
        receiver_var = tk.StringVar(value=receiver_id)
        ttk.Entry(dialog, textvariable=receiver_var, width=30).pack(pady=5)

        # Request type
        ttk.Label(dialog, text="Request Type:").pack(pady=5)
        type_var = tk.StringVar(value="general")
        types = [("General Buddy", "general"), ("Study Abroad", "study_abroad"),
                ("Sports/Fitness", "sports"), ("Academic/Study", "academic"), ("Other", "other")]

        for text, value in types:
            ttk.Radiobutton(dialog, text=text, variable=type_var, value=value).pack(anchor=tk.W, padx=50)

        # Destination (for study abroad)
        ttk.Label(dialog, text="Destination (if study abroad):").pack(pady=5)
        dest_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=dest_var, width=30).pack(pady=5)

        # Message
        ttk.Label(dialog, text="Personal Message:").pack(pady=5)
        message_text = tk.Text(dialog, height=5, width=40)
        message_text.pack(pady=5)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def send_request():
            receiver = receiver_var.get().strip()
            if not receiver:
                messagebox.showerror("Error", "Please enter a student ID.")
                return

            req_type = type_var.get()
            destination = dest_var.get().strip()
            message = message_text.get(1.0, tk.END).strip()

            user_id = self.auth.get_current_user()['username']

            try:
                request_id = self.service.send_buddy_request(
                    user_id, receiver, req_type, destination, message
                )
                messagebox.showinfo("Success", f"Buddy request sent! (ID: {request_id})")
                dialog.destroy()
                self.load_sent_requests()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(button_frame, text="Send", command=send_request).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    # ========== Teams Tab ==========

    def create_teams_tab(self):
        """Create teams tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Teams")

        # Header
        header = ttk.Label(tab, text="Intramural Team Formation", font=('Arial', 16, 'bold'))
        header.pack(pady=10)

        # Buttons
        button_frame = ttk.Frame(tab)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Create Team", command=self.create_team).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Join Team", command=self.join_team).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_teams).pack(side=tk.LEFT, padx=5)

        # Teams list
        columns = ('ID', 'Name', 'Sport', 'Members', 'Skill', 'Description')
        self.teams_tree = ttk.Treeview(tab, columns=columns, show='headings', height=20)

        for col in columns:
            self.teams_tree.heading(col, text=col)

        self.teams_tree.column('ID', width=50)
        self.teams_tree.column('Name', width=200)
        self.teams_tree.column('Sport', width=120)
        self.teams_tree.column('Members', width=100)
        self.teams_tree.column('Skill', width=100)
        self.teams_tree.column('Description', width=300)

        self.teams_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.load_teams()

    def load_teams(self):
        """Load available teams."""
        for item in self.teams_tree.get_children():
            self.teams_tree.delete(item)

        teams = self.service.get_available_teams()

        for team in teams:
            self.teams_tree.insert('', tk.END, values=(
                team['team_id'],
                team['team_name'],
                team['sport_type'],
                f"{team['current_members']}/{team['team_size']}",
                team['skill_level'],
                team['description'][:50] if team['description'] else 'N/A'
            ))

    def create_team(self):
        """Open dialog to create team."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Create Team")
        dialog.geometry("400x400")

        ttk.Label(dialog, text="Create New Team", font=('Arial', 14, 'bold')).pack(pady=10)

        # Team name
        ttk.Label(dialog, text="Team Name:").pack(pady=5)
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var, width=30).pack(pady=5)

        # Sport type
        ttk.Label(dialog, text="Sport Type:").pack(pady=5)
        sport_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=sport_var, width=30).pack(pady=5)

        # Team size
        ttk.Label(dialog, text="Team Size:").pack(pady=5)
        size_var = tk.StringVar(value="5")
        ttk.Entry(dialog, textvariable=size_var, width=30).pack(pady=5)

        # Skill level
        ttk.Label(dialog, text="Skill Level:").pack(pady=5)
        skill_var = tk.StringVar(value="Mixed")
        skill_combo = ttk.Combobox(dialog, textvariable=skill_var,
                                   values=["Beginner", "Intermediate", "Advanced", "Mixed"],
                                   state='readonly')
        skill_combo.pack(pady=5)

        # Description
        ttk.Label(dialog, text="Description:").pack(pady=5)
        desc_text = tk.Text(dialog, height=4, width=40)
        desc_text.pack(pady=5)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def save_team():
            name = name_var.get().strip()
            sport = sport_var.get().strip()

            if not name or not sport:
                messagebox.showerror("Error", "Please enter team name and sport.")
                return

            try:
                size = int(size_var.get())
            except ValueError:
                messagebox.showerror("Error", "Invalid team size.")
                return

            skill = skill_var.get()
            description = desc_text.get(1.0, tk.END).strip()

            user_id = self.auth.get_current_user()['username']

            try:
                team_id = self.service.create_team(user_id, name, sport, size, skill, description)
                messagebox.showinfo("Success", f"Team created! (ID: {team_id})")
                dialog.destroy()
                self.load_teams()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(button_frame, text="Create", command=save_team).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def join_team(self):
        """Join selected team."""
        selection = self.teams_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a team first.")
            return

        item = self.teams_tree.item(selection[0])
        team_id = item['values'][0]
        team_name = item['values'][1]

        if messagebox.askyesno("Confirm", f"Join team '{team_name}'?"):
            user_id = self.auth.get_current_user()['username']

            if self.service.join_team(team_id, user_id):
                messagebox.showinfo("Success", "Successfully joined the team!")
                self.load_teams()
            else:
                messagebox.showerror("Error", "Failed to join team (may be full or already a member).")

    # ========== Clubs Tab ==========

    def create_clubs_tab(self):
        """Create clubs recommendations tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Club Recommendations")

        # Header
        header = ttk.Label(tab, text="Recommended Clubs", font=('Arial', 16, 'bold'))
        header.pack(pady=10)

        # Button
        ttk.Button(tab, text="Generate Recommendations", command=self.generate_club_recs).pack(pady=10)

        # Recommendations grid
        columns = ('Club Name', 'Category', 'Score', 'Reason')
        self.clubs_tree = ttk.Treeview(tab, columns=columns, show='headings', height=20)

        for col in columns:
            self.clubs_tree.heading(col, text=col)

        self.clubs_tree.column('Club Name', width=250)
        self.clubs_tree.column('Category', width=120)
        self.clubs_tree.column('Score', width=100)
        self.clubs_tree.column('Reason', width=400)

        self.clubs_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def generate_club_recs(self):
        """Generate club recommendations."""
        user_id = self.auth.get_current_user()['username']

        # Clear tree
        for item in self.clubs_tree.get_children():
            self.clubs_tree.delete(item)

        recommendations = self.service.generate_club_recommendations(user_id)

        if not recommendations:
            messagebox.showinfo("Info", "No recommendations available. Add interests to your profile!")
            return

        for rec in recommendations:
            self.clubs_tree.insert('', tk.END, values=(
                rec['club_name'],
                rec['club_category'],
                rec['match_score'],
                rec['reason']
            ))

        messagebox.showinfo("Success", f"Generated {len(recommendations)} recommendations!")

    # ========== Activities Tab ==========

    def create_activities_tab(self):
        """Create social activities tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Social Activities")

        # Header
        header = ttk.Label(tab, text="Social Activities", font=('Arial', 16, 'bold'))
        header.pack(pady=10)

        # Buttons
        button_frame = ttk.Frame(tab)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Create Activity", command=self.create_activity).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="View Suggested", command=self.load_suggested_activities).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Join Activity", command=self.join_activity).pack(side=tk.LEFT, padx=5)

        # Activities list
        columns = ('ID', 'Name', 'Type', 'Date', 'Time', 'Location', 'Participants')
        self.activities_tree = ttk.Treeview(tab, columns=columns, show='headings', height=18)

        for col in columns:
            self.activities_tree.heading(col, text=col)

        self.activities_tree.column('ID', width=50)
        self.activities_tree.column('Name', width=200)
        self.activities_tree.column('Type', width=120)
        self.activities_tree.column('Date', width=100)
        self.activities_tree.column('Time', width=80)
        self.activities_tree.column('Location', width=150)
        self.activities_tree.column('Participants', width=100)

        self.activities_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def load_suggested_activities(self):
        """Load suggested activities."""
        for item in self.activities_tree.get_children():
            self.activities_tree.delete(item)

        user_id = self.auth.get_current_user()['username']
        activities = self.service.get_suggested_activities(user_id, 30)

        if not activities:
            messagebox.showinfo("Info", "No suggested activities found.")
            return

        for activity in activities:
            self.activities_tree.insert('', tk.END, values=(
                activity['activity_id'],
                activity['activity_name'],
                activity['activity_type'],
                activity['activity_date'],
                activity['activity_time'],
                activity['location'],
                f"{activity['current_participants']}/{activity['max_participants']}"
            ))

        messagebox.showinfo("Success", f"Found {len(activities)} suggested activities!")

    def create_activity(self):
        """Open dialog to create activity."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Create Activity")
        dialog.geometry("450x500")

        ttk.Label(dialog, text="Create Social Activity", font=('Arial', 14, 'bold')).pack(pady=10)

        # Activity name
        ttk.Label(dialog, text="Activity Name:").pack(pady=5)
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var, width=40).pack(pady=5)

        # Activity type
        ttk.Label(dialog, text="Activity Type:").pack(pady=5)
        type_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=type_var, width=40).pack(pady=5)

        # Location
        ttk.Label(dialog, text="Location:").pack(pady=5)
        location_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=location_var, width=40).pack(pady=5)

        # Date
        ttk.Label(dialog, text="Date (YYYY-MM-DD):").pack(pady=5)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(dialog, textvariable=date_var, width=40).pack(pady=5)

        # Time
        ttk.Label(dialog, text="Time (HH:MM):").pack(pady=5)
        time_var = tk.StringVar(value="18:00")
        ttk.Entry(dialog, textvariable=time_var, width=40).pack(pady=5)

        # Max participants
        ttk.Label(dialog, text="Max Participants:").pack(pady=5)
        max_var = tk.StringVar(value="10")
        ttk.Entry(dialog, textvariable=max_var, width=40).pack(pady=5)

        # Description
        ttk.Label(dialog, text="Description:").pack(pady=5)
        desc_text = tk.Text(dialog, height=4, width=45)
        desc_text.pack(pady=5)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def save_activity():
            name = name_var.get().strip()
            act_type = type_var.get().strip()
            location = location_var.get().strip()
            date = date_var.get().strip()
            time = time_var.get().strip()

            if not all([name, act_type, location, date, time]):
                messagebox.showerror("Error", "Please fill all required fields.")
                return

            try:
                max_participants = int(max_var.get())
            except ValueError:
                messagebox.showerror("Error", "Invalid max participants.")
                return

            description = desc_text.get(1.0, tk.END).strip()

            user_id = self.auth.get_current_user()['username']

            try:
                activity_id = self.service.create_social_activity(
                    user_id, name, act_type, description, location,
                    date, time, max_participants, []
                )
                messagebox.showinfo("Success", f"Activity created! (ID: {activity_id})")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(button_frame, text="Create", command=save_activity).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def join_activity(self):
        """Join selected activity."""
        selection = self.activities_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an activity first.")
            return

        item = self.activities_tree.item(selection[0])
        activity_id = item['values'][0]
        activity_name = item['values'][1]

        # Ask for RSVP status
        dialog = tk.Toplevel(self.window)
        dialog.title("Join Activity")
        dialog.geometry("300x200")

        ttk.Label(dialog, text=f"Join: {activity_name}", font=('Arial', 12, 'bold')).pack(pady=20)

        ttk.Label(dialog, text="RSVP Status:").pack(pady=5)
        status_var = tk.StringVar(value="going")

        ttk.Radiobutton(dialog, text="Going", variable=status_var, value="going").pack(anchor=tk.W, padx=50)
        ttk.Radiobutton(dialog, text="Interested", variable=status_var, value="interested").pack(anchor=tk.W, padx=50)
        ttk.Radiobutton(dialog, text="Maybe", variable=status_var, value="maybe").pack(anchor=tk.W, padx=50)

        def confirm_join():
            user_id = self.auth.get_current_user()['username']
            status = status_var.get()

            if self.service.join_activity(activity_id, user_id, status):
                messagebox.showinfo("Success", f"Joined activity with status '{status}'!")
                dialog.destroy()
            else:
                messagebox.showerror("Error", "Failed to join activity.")

        ttk.Button(dialog, text="Confirm", command=confirm_join).pack(pady=20)

    # ========== Profile Tab ==========

    def create_profile_tab(self):
        """Create personality profile tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Profile & Settings")

        # Header
        header = ttk.Label(tab, text="Personality Profile & Privacy", font=('Arial', 16, 'bold'))
        header.pack(pady=10)

        # Personality section
        personality_frame = ttk.LabelFrame(tab, text="Personality Profile")
        personality_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Display current profile
        self.profile_display = scrolledtext.ScrolledText(personality_frame, wrap=tk.WORD, height=10)
        self.profile_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Button(personality_frame, text="Update Profile", command=self.update_personality).pack(pady=5)

        # Privacy section
        privacy_frame = ttk.LabelFrame(tab, text="Privacy Settings")
        privacy_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.privacy_vars = {}
        privacy_options = [
            ('allow_matching', 'Allow Matching'),
            ('show_profile', 'Show Profile'),
            ('allow_messages', 'Allow Messages'),
            ('show_interests', 'Show Interests'),
            ('show_in_search', 'Show in Search'),
            ('match_same_major', 'Match Same Major Only'),
            ('match_same_year', 'Match Same Year Only')
        ]

        for key, label in privacy_options:
            self.privacy_vars[key] = tk.BooleanVar()
            ttk.Checkbutton(privacy_frame, text=label, variable=self.privacy_vars[key]).pack(anchor=tk.W, padx=20, pady=2)

        ttk.Button(privacy_frame, text="Save Privacy Settings", command=self.save_privacy).pack(pady=10)

        # Statistics section
        stats_frame = ttk.LabelFrame(tab, text="My Statistics")
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.stats_display = scrolledtext.ScrolledText(stats_frame, wrap=tk.WORD, height=8)
        self.stats_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Button(stats_frame, text="Refresh Statistics", command=self.load_statistics).pack(pady=5)

        # Load initial data
        self.load_profile_data()

    def load_profile_data(self):
        """Load personality profile and privacy settings."""
        user_id = self.auth.get_current_user()['username']

        # Load personality
        profile = self.service.get_personality_profile(user_id)
        self.profile_display.delete(1.0, tk.END)

        if profile:
            self.profile_display.insert(tk.END, f"Personality Type: {profile['personality_type']}\n")
            self.profile_display.insert(tk.END, f"Extroversion: {profile['extroversion_score']}/10\n")
            self.profile_display.insert(tk.END, f"Openness: {profile['openness_score']}/10\n")
            self.profile_display.insert(tk.END, f"Social Preference: {profile['social_preference']}\n")
            self.profile_display.insert(tk.END, f"Group Size: {profile['group_size_preference']}\n")
            self.profile_display.insert(tk.END, f"Activity Level: {profile['activity_level']}\n")
        else:
            self.profile_display.insert(tk.END, "No personality profile set.\n")
            self.profile_display.insert(tk.END, "Click 'Update Profile' to create one.")

        # Load privacy settings
        settings = self.service.get_privacy_settings(user_id)
        for key, var in self.privacy_vars.items():
            var.set(settings.get(key, True))

        # Load statistics
        self.load_statistics()

    def update_personality(self):
        """Open dialog to update personality profile."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Update Personality Profile")
        dialog.geometry("400x500")

        ttk.Label(dialog, text="Personality Profile", font=('Arial', 14, 'bold')).pack(pady=10)

        # Personality type
        ttk.Label(dialog, text="Personality Type:").pack(pady=5)
        type_var = tk.StringVar(value=PERSONALITY_TYPES[0])
        type_combo = ttk.Combobox(dialog, textvariable=type_var, values=PERSONALITY_TYPES, state='readonly')
        type_combo.pack(pady=5)

        # Extroversion
        ttk.Label(dialog, text="Extroversion (1-10):").pack(pady=5)
        extro_var = tk.IntVar(value=5)
        ttk.Scale(dialog, from_=1, to=10, variable=extro_var, orient=tk.HORIZONTAL).pack(pady=5)

        # Openness
        ttk.Label(dialog, text="Openness (1-10):").pack(pady=5)
        open_var = tk.IntVar(value=5)
        ttk.Scale(dialog, from_=1, to=10, variable=open_var, orient=tk.HORIZONTAL).pack(pady=5)

        # Social preference
        ttk.Label(dialog, text="Social Preference:").pack(pady=5)
        social_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=social_var, width=40).pack(pady=5)

        # Group size
        ttk.Label(dialog, text="Group Size Preference:").pack(pady=5)
        group_var = tk.StringVar(value=GROUP_SIZE_PREFERENCES[0])
        group_combo = ttk.Combobox(dialog, textvariable=group_var, values=GROUP_SIZE_PREFERENCES, state='readonly')
        group_combo.pack(pady=5)

        # Activity level
        ttk.Label(dialog, text="Activity Level:").pack(pady=5)
        activity_var = tk.StringVar(value=ACTIVITY_LEVELS[1])
        activity_combo = ttk.Combobox(dialog, textvariable=activity_var, values=ACTIVITY_LEVELS, state='readonly')
        activity_combo.pack(pady=5)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def save_profile():
            user_id = self.auth.get_current_user()['username']

            try:
                self.service.set_personality_profile(
                    user_id,
                    type_var.get(),
                    extro_var.get(),
                    open_var.get(),
                    social_var.get(),
                    group_var.get(),
                    activity_var.get()
                )
                messagebox.showinfo("Success", "Personality profile updated!")
                dialog.destroy()
                self.load_profile_data()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(button_frame, text="Save", command=save_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def save_privacy(self):
        """Save privacy settings."""
        user_id = self.auth.get_current_user()['username']

        settings = {key: var.get() for key, var in self.privacy_vars.items()}

        try:
            self.service.set_privacy_settings(user_id, **settings)
            messagebox.showinfo("Success", "Privacy settings saved!")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def load_statistics(self):
        """Load and display statistics."""
        user_id = self.auth.get_current_user()['username']
        stats = self.service.get_user_statistics(user_id)

        self.stats_display.delete(1.0, tk.END)
        self.stats_display.insert(tk.END, f"Total Interests: {stats['total_interests']}\n")
        self.stats_display.insert(tk.END, f"Total Matches: {stats['total_matches']}\n")
        self.stats_display.insert(tk.END, f"Buddy Requests Sent: {stats['requests_sent']}\n")
        self.stats_display.insert(tk.END, f"Buddy Requests Received: {stats['requests_received']}\n")
        self.stats_display.insert(tk.END, f"Teams Joined: {stats['teams_joined']}\n")
        self.stats_display.insert(tk.END, f"Activities Joined: {stats['activities_joined']}\n")


def main():
    """Main entry point for GUI."""
    root = tk.Tk()
    root.withdraw()
    app = SocialMatchingGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
