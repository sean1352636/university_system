"""
Random Skill Generator
Database of 100+ skills across categories. Generate random weekly suggestions,
track attempted/completed skills, view history. SQLite persistence.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import os
import random
from datetime import datetime, timedelta


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills.db")

SKILLS_DATA = [
    # (name, category, difficulty 1-5, resources)
    # Programming
    ("Learn Python Basics", "Programming", 2, "python.org/tutorial"),
    ("Build a REST API", "Programming", 3, "flask.palletsprojects.com"),
    ("Learn Git Version Control", "Programming", 2, "git-scm.com/book"),
    ("Build a CLI Tool", "Programming", 3, "docs.python.org/3/howto/argparse.html"),
    ("Learn SQL Fundamentals", "Programming", 2, "sqlbolt.com"),
    ("Create a Web Scraper", "Programming", 3, "realpython.com/python-web-scraping"),
    ("Learn TypeScript", "Programming", 3, "typescriptlang.org/docs"),
    ("Build a Chat Bot", "Programming", 4, "rasa.com/docs"),
    ("Learn Docker Basics", "Programming", 3, "docs.docker.com/get-started"),
    ("Contribute to Open Source", "Programming", 4, "firsttimersonly.com"),
    ("Learn Regular Expressions", "Programming", 3, "regexone.com"),
    ("Build a Todo App", "Programming", 2, "developer.mozilla.org"),
    ("Learn Data Structures", "Programming", 4, "visualgo.net"),
    ("Create a Game with Pygame", "Programming", 3, "pygame.org/docs"),
    ("Learn React Basics", "Programming", 3, "react.dev/learn"),
    ("Automate Your Workflow", "Programming", 2, "automatetheboringstuff.com"),

    # Art & Design
    ("Sketch Daily for a Week", "Art", 1, "drawabox.com"),
    ("Learn Watercolour Basics", "Art", 2, "youtube.com/watercolour-tutorials"),
    ("Digital Art with GIMP", "Art", 3, "gimp.org/tutorials"),
    ("Typography Design", "Art", 2, "typewolf.com/resources"),
    ("Learn Colour Theory", "Art", 2, "colormatters.com"),
    ("Create a Logo", "Art", 3, "canva.com/designschool"),
    ("Pixel Art Basics", "Art", 2, "lospec.com/pixel-art-tutorials"),
    ("Photography Composition", "Art", 2, "digital-photography-school.com"),
    ("Hand Lettering", "Art", 2, "youtube.com/hand-lettering"),
    ("Learn Perspective Drawing", "Art", 3, "drawabox.com/lesson/1"),
    ("Create a Mood Board", "Art", 1, "pinterest.com/ideas"),
    ("UI/UX Design Fundamentals", "Art", 3, "nngroup.com/articles"),

    # Music
    ("Learn Basic Guitar Chords", "Music", 2, "justinguitar.com"),
    ("Music Theory Fundamentals", "Music", 3, "musictheory.net"),
    ("Learn a Song by Ear", "Music", 3, "youtube.com/ear-training"),
    ("Beat Making Basics", "Music", 3, "learningmusic.ableton.com"),
    ("Learn Piano Scales", "Music", 2, "pianonanny.com"),
    ("Songwriting 101", "Music", 3, "berklee.edu/songwriting"),
    ("Ukulele for Beginners", "Music", 1, "ukulele-tabs.com"),
    ("Learn Music Production", "Music", 4, "coursera.org/music-production"),
    ("Vocal Training Basics", "Music", 2, "youtube.com/vocal-lessons"),
    ("Rhythm and Timing", "Music", 2, "metronomeonline.com"),
    ("Learn to Read Sheet Music", "Music", 3, "musictheory.net/lessons"),
    ("Harmonica Basics", "Music", 2, "harmonicatunes.com"),

    # Cooking
    ("Master Knife Skills", "Cooking", 2, "seriouseats.com/knife-skills"),
    ("Bake Bread from Scratch", "Cooking", 3, "kingarthurbaking.com"),
    ("Learn to Make Pasta", "Cooking", 2, "bonappetit.com/pasta"),
    ("5 Basic Sauces", "Cooking", 3, "foodnetwork.com/mother-sauces"),
    ("Meal Prep Mastery", "Cooking", 2, "budgetbytes.com"),
    ("Learn Fermentation", "Cooking", 4, "wildfermentation.com"),
    ("Cook a 3-Course Meal", "Cooking", 3, "allrecipes.com"),
    ("Master Egg Cooking", "Cooking", 1, "seriouseats.com/eggs"),
    ("Learn Indian Cuisine", "Cooking", 3, "vegrecipesofindia.com"),
    ("Sushi Making Basics", "Cooking", 4, "justonecookbook.com"),
    ("Coffee Brewing Methods", "Cooking", 2, "homegrounds.co"),
    ("Pastry Basics", "Cooking", 3, "sallysbakingaddiction.com"),

    # Fitness
    ("Start a Running Habit", "Fitness", 2, "couch25k.com"),
    ("Learn Basic Yoga", "Fitness", 1, "yogawithadriene.com"),
    ("Bodyweight Training", "Fitness", 2, "darebee.com"),
    ("Learn to Jump Rope", "Fitness", 2, "crossrope.com"),
    ("Flexibility Challenge", "Fitness", 2, "gmb.io/stretching"),
    ("Swimming Technique", "Fitness", 3, "yourswimlog.com"),
    ("Learn Rock Climbing", "Fitness", 3, "climbing.com/skills"),
    ("Meditation for Beginners", "Fitness", 1, "headspace.com"),
    ("Learn Martial Arts Basics", "Fitness", 3, "youtube.com/martial-arts"),
    ("Cycling Training Plan", "Fitness", 2, "bicycling.com/training"),
    ("Balance and Stability", "Fitness", 2, "acefitness.org"),
    ("HIIT Workout Basics", "Fitness", 2, "darebee.com/hiit"),

    # Languages
    ("Learn 50 Spanish Words", "Languages", 1, "duolingo.com"),
    ("French Pronunciation", "Languages", 2, "forvo.com"),
    ("Japanese Hiragana", "Languages", 3, "tofugu.com/japanese/hiragana"),
    ("German Basics", "Languages", 2, "dw.com/learn-german"),
    ("Mandarin Tones", "Languages", 4, "chinesepod.com"),
    ("Italian Conversation", "Languages", 2, "languagetransfer.org"),
    ("Korean Hangul", "Languages", 2, "howtostudykorean.com"),
    ("Portuguese Essentials", "Languages", 2, "practiceportuguese.com"),
    ("Arabic Script Basics", "Languages", 4, "arabic101.org"),
    ("Sign Language Alphabet", "Languages", 1, "lifeprint.com"),
    ("Latin Fundamentals", "Languages", 3, "latin-is-simple.com"),
    ("Swedish for Beginners", "Languages", 2, "duolingo.com/course/sv"),

    # Life Skills
    ("Basic First Aid", "Life Skills", 2, "redcross.org/first-aid"),
    ("Personal Finance Basics", "Life Skills", 2, "investopedia.com"),
    ("Speed Reading Techniques", "Life Skills", 2, "spreeder.com"),
    ("Public Speaking Practice", "Life Skills", 3, "toastmasters.org"),
    ("Learn to Sew", "Life Skills", 2, "sewguide.com"),
    ("Basic Car Maintenance", "Life Skills", 2, "popularmechanics.com"),
    ("Time Management Methods", "Life Skills", 2, "todoist.com/productivity-methods"),
    ("Learn Memory Techniques", "Life Skills", 3, "artofmemory.com"),
    ("Negotiation Skills", "Life Skills", 3, "masterclass.com/negotiation"),
    ("Home Repair Basics", "Life Skills", 2, "familyhandyman.com"),
    ("Touch Typing Mastery", "Life Skills", 2, "keybr.com"),
    ("Conflict Resolution", "Life Skills", 3, "mindtools.com"),

    # Science & Math
    ("Astronomy Basics", "Science", 2, "nasa.gov/audience/foreducators"),
    ("Learn Statistics", "Science", 3, "khanacademy.org/math/statistics"),
    ("Chemistry at Home", "Science", 2, "acs.org/education"),
    ("Logic Puzzles Daily", "Science", 2, "brainbashers.com"),
    ("Learn About DNA", "Science", 3, "yourgenome.org"),
    ("Basic Electronics", "Science", 3, "sparkfun.com/tutorials"),
    ("Calculus Fundamentals", "Science", 4, "3blue1brown.com"),
    ("Weather Patterns", "Science", 2, "weather.gov/education"),
    ("Plant Biology Basics", "Science", 2, "britannica.com/science/botany"),
    ("Probability Theory", "Science", 3, "seeing-theory.brown.edu"),

    # Crafts & DIY
    ("Origami for Beginners", "Crafts", 1, "origami-instructions.com"),
    ("Knitting a Scarf", "Crafts", 2, "lovecrafts.com/knitting"),
    ("Woodworking Basics", "Crafts", 3, "woodworkingformeremortals.com"),
    ("Candle Making", "Crafts", 2, "candlescience.com"),
    ("Soap Making Basics", "Crafts", 2, "soapqueen.com"),
    ("Learn Pottery Basics", "Crafts", 3, "thesprucecrafts.com"),
    ("Macrame Projects", "Crafts", 2, "youtube.com/macrame-tutorials"),
    ("Card Making", "Crafts", 1, "stampinup.com/ideas"),
]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                difficulty INTEGER NOT NULL,
                resources TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS skill_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_id INTEGER NOT NULL,
                suggested_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'suggested',
                notes TEXT DEFAULT '',
                completed_date TEXT,
                FOREIGN KEY (skill_id) REFERENCES skills(id)
            );
        """)

        existing = conn.execute("SELECT COUNT(*) as c FROM skills").fetchone()["c"]
        if existing == 0:
            conn.executemany(
                "INSERT OR IGNORE INTO skills (name, category, difficulty, resources) VALUES (?, ?, ?, ?)",
                SKILLS_DATA
            )
        conn.commit()
    finally:
        conn.close()


class RandomSkillGeneratorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Random Skill Generator")
        self.geometry("950x700")
        self.minsize(800, 600)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Heading.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Skill.TLabel", font=("Segoe UI", 20, "bold"), foreground="#1565c0")
        style.configure("Category.TLabel", font=("Segoe UI", 12), foreground="#555")
        style.configure("Diff.TLabel", font=("Segoe UI", 11))
        style.configure("Stat.TLabel", font=("Segoe UI", 11))
        style.configure("Green.TLabel", font=("Segoe UI", 11, "bold"), foreground="#2e7d32")

        init_db()
        self._build_ui()
        self._refresh_history()
        self._refresh_stats()
        self._refresh_browse()

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Random Skill Generator", style="Title.TLabel").pack(side=tk.LEFT)

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # -- Generate tab --
        gen_tab = ttk.Frame(notebook, padding=20)
        notebook.add(gen_tab, text="  Generate  ")

        filter_frame = ttk.Frame(gen_tab)
        filter_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(filter_frame, text="Category Filter:", style="Heading.TLabel").pack(side=tk.LEFT)
        self.cat_filter_var = tk.StringVar(value="Any")
        categories = ["Any"] + sorted(set(s[1] for s in SKILLS_DATA))
        ttk.Combobox(filter_frame, textvariable=self.cat_filter_var, values=categories,
                     width=18, state="readonly").pack(side=tk.LEFT, padx=10)

        ttk.Label(filter_frame, text="Max Difficulty:").pack(side=tk.LEFT, padx=(15, 0))
        self.max_diff_var = tk.StringVar(value="5")
        ttk.Spinbox(filter_frame, from_=1, to=5, textvariable=self.max_diff_var,
                    width=4).pack(side=tk.LEFT, padx=5)

        self.exclude_attempted_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(filter_frame, text="Exclude attempted",
                        variable=self.exclude_attempted_var).pack(side=tk.LEFT, padx=15)

        # Skill display card
        card = ttk.LabelFrame(gen_tab, text="This Week's Skill Suggestion", padding=25)
        card.pack(fill=tk.X, pady=10)

        self.skill_name_label = ttk.Label(card, text="Click 'Generate' to get a skill!",
                                          style="Skill.TLabel")
        self.skill_name_label.pack(pady=(0, 5))

        self.skill_cat_label = ttk.Label(card, text="", style="Category.TLabel")
        self.skill_cat_label.pack()

        self.skill_diff_label = ttk.Label(card, text="", style="Diff.TLabel")
        self.skill_diff_label.pack(pady=3)

        self.skill_res_label = ttk.Label(card, text="", style="Stat.TLabel")
        self.skill_res_label.pack(pady=3)

        self.current_skill_id = None

        btn_row = ttk.Frame(gen_tab)
        btn_row.pack(pady=15)
        ttk.Button(btn_row, text="Generate Random Skill", command=self._generate).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_row, text="Accept & Start", command=self._accept).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_row, text="Skip", command=self._generate).pack(side=tk.LEFT, padx=10)

        # -- History tab --
        hist_tab = ttk.Frame(notebook, padding=10)
        notebook.add(hist_tab, text="  History  ")

        hist_filter = ttk.Frame(hist_tab)
        hist_filter.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(hist_filter, text="Show:").pack(side=tk.LEFT)
        self.hist_filter_var = tk.StringVar(value="All")
        for val in ["All", "In Progress", "Completed", "Abandoned"]:
            ttk.Radiobutton(hist_filter, text=val, variable=self.hist_filter_var,
                            value=val, command=self._refresh_history).pack(side=tk.LEFT, padx=5)

        cols = ("skill", "category", "difficulty", "suggested", "status", "completed")
        self.hist_tree = ttk.Treeview(hist_tab, columns=cols, show="headings", height=14)
        self.hist_tree.heading("skill", text="Skill")
        self.hist_tree.heading("category", text="Category")
        self.hist_tree.heading("difficulty", text="Difficulty")
        self.hist_tree.heading("suggested", text="Suggested")
        self.hist_tree.heading("status", text="Status")
        self.hist_tree.heading("completed", text="Completed")
        self.hist_tree.column("skill", width=200)
        self.hist_tree.column("category", width=100)
        self.hist_tree.column("difficulty", width=80, anchor=tk.CENTER)
        self.hist_tree.column("suggested", width=100, anchor=tk.CENTER)
        self.hist_tree.column("status", width=100, anchor=tk.CENTER)
        self.hist_tree.column("completed", width=100, anchor=tk.CENTER)
        vsb = ttk.Scrollbar(hist_tab, orient=tk.VERTICAL, command=self.hist_tree.yview)
        self.hist_tree.configure(yscrollcommand=vsb.set)
        self.hist_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        hist_btn = ttk.Frame(hist_tab)
        hist_btn.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(hist_btn, text="Mark Completed", command=self._mark_completed).pack(side=tk.LEFT, padx=3)
        ttk.Button(hist_btn, text="Mark Abandoned", command=self._mark_abandoned).pack(side=tk.LEFT, padx=3)
        ttk.Button(hist_btn, text="Delete Entry", command=self._delete_entry).pack(side=tk.LEFT, padx=3)

        # -- Browse tab --
        browse_tab = ttk.Frame(notebook, padding=10)
        notebook.add(browse_tab, text="  Browse Skills  ")

        browse_filter = ttk.Frame(browse_tab)
        browse_filter.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(browse_filter, text="Category:").pack(side=tk.LEFT)
        self.browse_cat_var = tk.StringVar(value="All")
        ttk.Combobox(browse_filter, textvariable=self.browse_cat_var,
                     values=["All"] + sorted(set(s[1] for s in SKILLS_DATA)),
                     width=18, state="readonly").pack(side=tk.LEFT, padx=5)
        self.browse_cat_var.trace_add("write", lambda *a: self._refresh_browse())

        ttk.Label(browse_filter, text="Search:").pack(side=tk.LEFT, padx=(15, 0))
        self.browse_search_var = tk.StringVar()
        self.browse_search_var.trace_add("write", lambda *a: self._refresh_browse())
        ttk.Entry(browse_filter, textvariable=self.browse_search_var, width=25).pack(side=tk.LEFT, padx=5)

        bcols = ("name", "category", "difficulty", "resources")
        self.browse_tree = ttk.Treeview(browse_tab, columns=bcols, show="headings", height=18)
        self.browse_tree.heading("name", text="Skill Name")
        self.browse_tree.heading("category", text="Category")
        self.browse_tree.heading("difficulty", text="Difficulty")
        self.browse_tree.heading("resources", text="Resources")
        self.browse_tree.column("name", width=220)
        self.browse_tree.column("category", width=110)
        self.browse_tree.column("difficulty", width=80, anchor=tk.CENTER)
        self.browse_tree.column("resources", width=250)
        bvsb = ttk.Scrollbar(browse_tab, orient=tk.VERTICAL, command=self.browse_tree.yview)
        self.browse_tree.configure(yscrollcommand=bvsb.set)
        self.browse_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bvsb.pack(side=tk.RIGHT, fill=tk.Y)

        # -- Stats tab --
        stats_tab = ttk.Frame(notebook, padding=10)
        notebook.add(stats_tab, text="  Statistics  ")

        self.stats_text = tk.Text(stats_tab, font=("Consolas", 11), wrap=tk.WORD,
                                  state=tk.DISABLED, bg="#fafafa", relief=tk.FLAT)
        self.stats_text.pack(fill=tk.BOTH, expand=True)

    def _generate(self):
        conn = get_conn()
        try:
            cat = self.cat_filter_var.get()
            try:
                max_diff = int(self.max_diff_var.get())
            except ValueError:
                max_diff = 5

            query = "SELECT * FROM skills WHERE difficulty <= ?"
            params = [max_diff]

            if cat != "Any":
                query += " AND category = ?"
                params.append(cat)

            if self.exclude_attempted_var.get():
                query += " AND id NOT IN (SELECT skill_id FROM skill_history)"

            skills = conn.execute(query, params).fetchall()
            if not skills:
                # Fall back to all skills in category
                query2 = "SELECT * FROM skills WHERE difficulty <= ?"
                params2 = [max_diff]
                if cat != "Any":
                    query2 += " AND category = ?"
                    params2.append(cat)
                skills = conn.execute(query2, params2).fetchall()

            if not skills:
                self.skill_name_label.configure(text="No skills match your filters!")
                self.skill_cat_label.configure(text="")
                self.skill_diff_label.configure(text="")
                self.skill_res_label.configure(text="")
                self.current_skill_id = None
                return

            skill = random.choice(skills)
            self.current_skill_id = skill["id"]

            stars = "*" * skill["difficulty"] + "-" * (5 - skill["difficulty"])
            self.skill_name_label.configure(text=skill["name"])
            self.skill_cat_label.configure(text=f"Category: {skill['category']}")
            self.skill_diff_label.configure(text=f"Difficulty: [{stars}] ({skill['difficulty']}/5)")
            self.skill_res_label.configure(text=f"Resources: {skill['resources']}")
        finally:
            conn.close()

    def _accept(self):
        if not self.current_skill_id:
            messagebox.showinfo("Generate First", "Generate a skill first.")
            return

        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO skill_history (skill_id, suggested_date, status) VALUES (?, ?, ?)",
                (self.current_skill_id, datetime.now().strftime("%Y-%m-%d"), "in_progress")
            )
            conn.commit()
            messagebox.showinfo("Started",
                                f"Skill accepted! It's been added to your history as 'In Progress'.")
            self._refresh_history()
            self._refresh_stats()
        finally:
            conn.close()

    def _refresh_history(self):
        self.hist_tree.delete(*self.hist_tree.get_children())
        conn = get_conn()
        try:
            filt = self.hist_filter_var.get().lower().replace(" ", "_")
            query = """
                SELECT sh.id, s.name, s.category, s.difficulty, sh.suggested_date,
                       sh.status, sh.completed_date
                FROM skill_history sh
                JOIN skills s ON s.id = sh.skill_id
            """
            if filt != "all":
                query += f" WHERE sh.status = ?"
                rows = conn.execute(query + " ORDER BY sh.suggested_date DESC", (filt,)).fetchall()
            else:
                rows = conn.execute(query + " ORDER BY sh.suggested_date DESC").fetchall()

            for row in rows:
                stars = "*" * row["difficulty"]
                completed = row["completed_date"] or "--"
                status_display = row["status"].replace("_", " ").title()
                self.hist_tree.insert("", tk.END, iid=str(row["id"]),
                                      values=(row["name"], row["category"], stars,
                                              row["suggested_date"], status_display, completed))
        finally:
            conn.close()

    def _mark_completed(self):
        sel = self.hist_tree.selection()
        if not sel:
            return
        conn = get_conn()
        try:
            for s in sel:
                conn.execute(
                    "UPDATE skill_history SET status='completed', completed_date=? WHERE id=?",
                    (datetime.now().strftime("%Y-%m-%d"), int(s))
                )
            conn.commit()
            self._refresh_history()
            self._refresh_stats()
        finally:
            conn.close()

    def _mark_abandoned(self):
        sel = self.hist_tree.selection()
        if not sel:
            return
        conn = get_conn()
        try:
            for s in sel:
                conn.execute("UPDATE skill_history SET status='abandoned' WHERE id=?", (int(s),))
            conn.commit()
            self._refresh_history()
            self._refresh_stats()
        finally:
            conn.close()

    def _delete_entry(self):
        sel = self.hist_tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", f"Delete {len(sel)} history entry/entries?"):
            conn = get_conn()
            try:
                for s in sel:
                    conn.execute("DELETE FROM skill_history WHERE id=?", (int(s),))
                conn.commit()
                self._refresh_history()
                self._refresh_stats()
            finally:
                conn.close()

    def _refresh_browse(self):
        self.browse_tree.delete(*self.browse_tree.get_children())
        conn = get_conn()
        try:
            cat = self.browse_cat_var.get()
            search = self.browse_search_var.get().lower()
            query = "SELECT * FROM skills"
            params = []
            conditions = []
            if cat != "All":
                conditions.append("category = ?")
                params.append(cat)
            if search:
                conditions.append("LOWER(name) LIKE ?")
                params.append(f"%{search}%")
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY category, name"

            rows = conn.execute(query, params).fetchall()
            for row in rows:
                stars = "*" * row["difficulty"] + "-" * (5 - row["difficulty"])
                self.browse_tree.insert("", tk.END, values=(
                    row["name"], row["category"], stars, row["resources"]
                ))
        finally:
            conn.close()

    def _refresh_stats(self):
        conn = get_conn()
        try:
            total_skills = conn.execute("SELECT COUNT(*) as c FROM skills").fetchone()["c"]
            total_attempted = conn.execute("SELECT COUNT(*) as c FROM skill_history").fetchone()["c"]
            completed = conn.execute(
                "SELECT COUNT(*) as c FROM skill_history WHERE status='completed'"
            ).fetchone()["c"]
            in_progress = conn.execute(
                "SELECT COUNT(*) as c FROM skill_history WHERE status='in_progress'"
            ).fetchone()["c"]
            abandoned = conn.execute(
                "SELECT COUNT(*) as c FROM skill_history WHERE status='abandoned'"
            ).fetchone()["c"]

            # Category breakdown
            cat_stats = conn.execute("""
                SELECT s.category, COUNT(*) as total,
                       SUM(CASE WHEN sh.status='completed' THEN 1 ELSE 0 END) as done
                FROM skill_history sh
                JOIN skills s ON s.id = sh.skill_id
                GROUP BY s.category
                ORDER BY total DESC
            """).fetchall()

            # Completion rate
            rate = (completed / total_attempted * 100) if total_attempted > 0 else 0

            lines = []
            lines.append("=" * 55)
            lines.append("  SKILL LEARNING STATISTICS")
            lines.append("=" * 55)
            lines.append("")
            lines.append(f"  Total Skills Available:  {total_skills}")
            lines.append(f"  Skills Attempted:        {total_attempted}")
            lines.append(f"  Completed:               {completed}")
            lines.append(f"  In Progress:             {in_progress}")
            lines.append(f"  Abandoned:               {abandoned}")
            lines.append(f"  Completion Rate:         {rate:.1f}%")
            lines.append("")
            lines.append("-" * 55)
            lines.append("  CATEGORY BREAKDOWN")
            lines.append("-" * 55)

            if cat_stats:
                for row in cat_stats:
                    cat_rate = (row["done"] / row["total"] * 100) if row["total"] > 0 else 0
                    lines.append(f"  {row['category']:<15}  "
                                 f"Attempted: {row['total']}  "
                                 f"Completed: {row['done']}  "
                                 f"Rate: {cat_rate:.0f}%")
            else:
                lines.append("  No skills attempted yet.")

            lines.append("")
            lines.append("=" * 55)

            # Difficulty distribution of completed
            diff_stats = conn.execute("""
                SELECT s.difficulty, COUNT(*) as c
                FROM skill_history sh
                JOIN skills s ON s.id = sh.skill_id
                WHERE sh.status = 'completed'
                GROUP BY s.difficulty
                ORDER BY s.difficulty
            """).fetchall()

            if diff_stats:
                lines.append("  COMPLETED BY DIFFICULTY")
                lines.append("-" * 55)
                for row in diff_stats:
                    stars = "*" * row["difficulty"]
                    bar = "#" * row["c"]
                    lines.append(f"  [{stars:<5}]  {bar}  ({row['c']})")
                lines.append("")
                lines.append("=" * 55)

            self.stats_text.configure(state=tk.NORMAL)
            self.stats_text.delete("1.0", tk.END)
            self.stats_text.insert("1.0", "\n".join(lines))
            self.stats_text.configure(state=tk.DISABLED)
        finally:
            conn.close()


if __name__ == "__main__":
    app = RandomSkillGeneratorApp()
    app.mainloop()
