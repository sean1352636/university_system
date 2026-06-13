import tkinter as tk
from education_system.university_system.infrastructure.email.template_utils import render_template
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection as db_get_connection
from education_system.university_system.core import paths
from datetime import datetime, timedelta
from pathlib import Path
import threading
import shutil
from functools import partial

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.core.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Alumni service functions
from education_system.university_system.modules.domain.student_affairs.gui.alumni._service_imports import (
    init_alumni_db, register_alumni, view_alumni, update_alumni,
    view_events, create_enhanced_event, event_check_in_system,
    record_donation, view_donations, setup_mentorship, view_mentorships,
    search_alumni_directory, view_connection_requests, manage_business_directory,
    create_newsletter, manage_alumni_forum, post_job_opportunity, view_job_board,
    schedule_career_counseling, view_fundraising_campaigns, create_fundraising_campaign,
    view_engagement_leaderboard, view_my_badges, manage_photo_gallery,
    manage_class_reunions, manage_regional_chapters, setup_alumni_directory,
    generate_alumni_report, set_auth, setup_alumni_permissions,
    smart_mentorship_matching, generate_engagement_recommendations,
    create_alumni_story, view_alumni_stories, get_connection,
)



class JobsCareerMixin:
        def _display_job_detail_window(self, job_data):
            """Display detailed job information window"""
            detail_window = tk.Toplevel(self.root)
            detail_window.title(f"Job Details - {job_data[0]}")
            detail_window.geometry("700x600")
            detail_window.configure(bg='white')

            # Main frame
            main_frame = ttk.Frame(detail_window, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Job title
            ttk.Label(main_frame, text=job_data[0],
                     font=('Arial', 16, 'bold')).pack(pady=(0, 10))

            # Company info
            company_frame = ttk.LabelFrame(main_frame, text="Company Information", padding=10)
            company_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(company_frame, text=f"Company: {job_data[1]}",
                     font=('Arial', 11)).pack(anchor='w')
            ttk.Label(company_frame, text=f"Location: {job_data[2]}",
                     font=('Arial', 11)).pack(anchor='w')

            # Job details
            details_frame = ttk.LabelFrame(main_frame, text="Job Details", padding=10)
            details_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(details_frame, text=f"Job Type: {job_data[3]}",
                     font=('Arial', 11)).pack(anchor='w')
            ttk.Label(details_frame, text=f"Salary Range: {job_data[4]}",
                     font=('Arial', 11)).pack(anchor='w')

            # Description
            desc_frame = ttk.LabelFrame(main_frame, text="Job Description", padding=10)
            desc_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

            desc_text = ScrolledText(desc_frame, wrap=tk.WORD, height=8)
            desc_text.pack(fill=tk.BOTH, expand=True)

            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT description, requirements, contact_email
                        FROM job_postings
                        WHERE job_title = ? AND company_name = ?
                    """, (job_data[0], job_data[1]))
                    result = cursor.fetchone()

                    if result:
                        desc_text.insert(tk.END, f"{result[0]}\n\nRequirements:\n{result[1]}\n\nContact: {result[2]}")
                    else:
                        desc_text.insert(tk.END, "Job description not available.")
            except sqlite3.Error:
                desc_text.insert(tk.END, "Job description not available.")

            desc_text.config(state='disabled')

            # Action buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X)

            ttk.Button(button_frame, text="Express Interest",
                      command=lambda: self._record_interest_from_detail(job_data[0], job_data[1], detail_window)).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Close",
                      command=detail_window.destroy).pack(side=tk.LEFT)

        def _record_interest_from_detail(self, job_title, company_name, window):
            """Record interest from job detail window"""
            try:
                self.record_job_interest(job_title, company_name)
                messagebox.showinfo("Success", "Your interest has been recorded!")
                window.destroy()
            except (sqlite3.Error, ValueError) as e:
                messagebox.showerror("Error", f"Failed to record interest: {str(e)}")

        def clear_job_form(self):
            """Clear job posting form"""
            for var in self.job_vars.values():
                var.set("")
            self.job_description.delete(1.0, tk.END)
            self.job_requirements.delete(1.0, tk.END)

        def create_counseling_form(self, parent):
            """Create career counseling scheduling form"""
            ttk.Label(parent, text="Schedule Career Counseling Session",
                     font=('Arial', 14, 'bold')).pack(pady=(10, 20))

            form_frame = ttk.Frame(parent)
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20)

            # Counselor selection
            self.counseling_vars = {}

            counselor_frame = ttk.Frame(form_frame)
            counselor_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(counselor_frame, text="Select Counselor:").pack(side=tk.LEFT, padx=(0, 10))
            self.counseling_vars['counselor'] = tk.StringVar()
            counselor_combo = ttk.Combobox(counselor_frame, textvariable=self.counseling_vars['counselor'],
                                          values=["Sarah Johnson - Tech Careers", "Michael Chen - Finance", "Dr. Lisa Martinez - Healthcare"])
            counselor_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Session type
            type_frame = ttk.Frame(form_frame)
            type_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(type_frame, text="Session Type:").pack(side=tk.LEFT, padx=(0, 10))
            self.counseling_vars['session_type'] = tk.StringVar()
            type_combo = ttk.Combobox(type_frame, textvariable=self.counseling_vars['session_type'],
                                     values=["Career Planning", "Resume Review", "Interview Preparation", "Industry Insights", "Networking Advice"])
            type_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Preferred date/time
            datetime_frame = ttk.Frame(form_frame)
            datetime_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(datetime_frame, text="Preferred Date & Time: (YYYY-MM-DD HH:MM)").pack(anchor='w')
            self.counseling_vars['datetime'] = tk.StringVar()
            ttk.Entry(datetime_frame, textvariable=self.counseling_vars['datetime']).pack(fill=tk.X, pady=(5, 0))

            # Duration
            duration_frame = ttk.Frame(form_frame)
            duration_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(duration_frame, text="Duration (minutes):").pack(side=tk.LEFT, padx=(0, 10))
            self.counseling_vars['duration'] = tk.StringVar(value="60")
            duration_combo = ttk.Combobox(duration_frame, textvariable=self.counseling_vars['duration'],
                                         values=["30", "60", "90"])
            duration_combo.pack(side=tk.LEFT)

            # Notes
            ttk.Label(form_frame, text="Additional Notes or Specific Topics:").pack(anchor='w', pady=(10, 5))
            self.counseling_notes = ScrolledText(form_frame, height=4, wrap=tk.WORD)
            self.counseling_notes.pack(fill=tk.X)

            # Submit button
            ttk.Button(form_frame, text="Schedule Session",
                      command=self.submit_counseling_request).pack(pady=20)

        def load_job_listings(self):
            """Load job listings into the text widget"""
            self.job_text.delete(1.0, tk.END)

            job_content = """Current Job Opportunities:

    💼 Senior Software Developer
    Company: Tech Innovations Inc.
    Posted by: Sarah Johnson (Class of 2015)
    Location: San Francisco, CA (Remote available)
    Type: Full-time | Experience: Mid-Senior Level
    Salary: £120,000 - £150,000

    Description: Join our growing team developing cutting-edge web applications.
    Looking for experienced developers with React, Node.js, and cloud experience.

    Requirements:
    • 3+ years software development experience
    • Strong JavaScript, React, Node.js skills
    • Experience with AWS or similar cloud platforms
    • Bachelor's degree in Computer Science or related field

    Contact: careers@techinnovations.com
    Posted: August 10, 2025 | Expires: September 10, 2025

    [Apply Now] [Save Job] [Contact Poster]

    ---

    💼 Financial Analyst
    Company: Finance Plus Corp
    Posted by: Michael Chen (Class of 2018)
    Location: New York, NY
    Type: Full-time | Experience: Entry-Mid Level
    Salary: £70,000 - £90,000

    Description: Seeking detail-oriented financial analyst to join our investment team.
    Great opportunity for recent graduates or career changers.

    Requirements:
    • Bachelor's degree in Finance, Economics, or related field
    • Strong analytical and Excel skills
    • CFA Level 1 preferred but not required
    • Excellent communication skills

    Contact: hiring@financeplus.com
    Posted: August 8, 2025 | Expires: September 8, 2025

    [Apply Now] [Save Job] [Contact Poster]

    ---

    💼 Marketing Manager
    Company: Creative Solutions LLC
    Posted by: Lisa Brown (Class of 2016)
    Location: Boston, MA (Hybrid)
    Type: Full-time | Experience: Mid Level
    Salary: £80,000 - £100,000

    Description: Lead marketing initiatives for B2B software company.
    Manage campaigns, content strategy, and team development.

    Requirements:
    • 3-5 years marketing experience
    • Experience with digital marketing platforms
    • Strong project management skills
    • MBA preferred

    Contact: jobs@creativesolutions.com
    Posted: August 5, 2025 | Expires: September 5, 2025

    [Apply Now] [Save Job] [Contact Poster]
    """
            self.job_text.insert(tk.END, job_content)

        def record_job_interest(self, job_title=None, company_name=None):
            """Record user's interest in a job posting"""
            if not job_title or not company_name:
                # Show job selection dialog
                messagebox.showinfo("Info", "Please use 'View Job Details' to express interest in a job.")
                return

            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    user_id = self._current_user_id()

                    # Get job_id
                    cursor.execute("""
                        SELECT job_id FROM job_postings
                        WHERE job_title = ? AND company_name = ?
                    """, (job_title, company_name))
                    result = cursor.fetchone()

                    if not result:
                        raise ValueError("Job posting not found")

                    job_id = result[0]

                    # Check if already expressed interest
                    cursor.execute("""
                        SELECT interest_id FROM job_interests
                        WHERE job_id = ? AND user_id = ?
                    """, (job_id, user_id))

                    if cursor.fetchone():
                        messagebox.showinfo("Already Interested",
                                          "You have already expressed interest in this job.")
                        return

                    # Record interest
                    cursor.execute("""
                        INSERT INTO job_interests (job_id, user_id, expressed_date, status)
                        VALUES (?, ?, datetime('now'), 'interested')
                    """, (job_id, user_id))

                    # Update job interest count
                    cursor.execute("""
                        UPDATE job_postings
                        SET interest_count = interest_count + 1
                        WHERE job_id = ?
                    """, (job_id,))

                    conn.commit()
                    self.update_status("Job interest recorded")

                    # Log activity
                    from education_system.university_system.core.activity_logger import log_activity
                    log_activity('create', 'job_interest', interest_id=cursor.lastrowid,
                               details={'job_id': job_id, 'job_title': job_title, 'company': company_name})

            except sqlite3.Error as e:
                raise sqlite3.Error(f"Failed to record job interest: {str(e)}")

        def search_jobs(self):
            """Search jobs based on criteria"""
            search_term = self.job_search.get()
            category = self.job_category.get()

            # For demo, just show search message
            if search_term or category != "All":
                self.job_text.delete(1.0, tk.END)
                self.job_text.insert(tk.END, f"Searching for jobs...\n")
                self.job_text.insert(tk.END, f"Search term: {search_term}\n")
                self.job_text.insert(tk.END, f"Category: {category}\n\n")
                self.load_job_listings()  # Then show all jobs for demo
            else:
                self.load_job_listings()

        def show_career_counseling(self):
            """Show career counseling interface"""
            self.clear_content()
            self.update_status("Career Counseling")

            ttk.Label(self.content_frame, text="Career Counseling Services",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Tabs for different counseling views
            notebook = ttk.Notebook(self.content_frame)
            notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Available counselors tab
            counselors_frame = ttk.Frame(notebook)
            notebook.add(counselors_frame, text="Available Counselors")

            counselors_text = ScrolledText(counselors_frame, wrap=tk.WORD)
            counselors_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            counselors_content = """Available Career Counselors:

    👩‍💼 Sarah Johnson (Class of 2015)
    Title: Senior Developer & Tech Entrepreneur
    Company: Tech Innovations Inc.
    Specialties: Software Development, Startup Leadership, Career Transitions
    Experience: 8+ years in technology industry
    Available: Weekday evenings, weekends

    Bio: Sarah has successfully transitioned from software developer to startup founder.
    She specializes in helping alumni navigate tech careers and entrepreneurship.

    [Schedule Session] [View Full Profile]

    ---

    👨‍💼 Michael Chen (Class of 2018)
    Title: Financial Analyst & Investment Advisor
    Company: Finance Plus Corp
    Specialties: Finance, Investment Banking, Career Planning
    Experience: 5+ years in financial services
    Available: Weekday afternoons, Saturday mornings

    Bio: Michael provides guidance on finance careers, industry transitions,
    and professional development in the financial sector.

    [Schedule Session] [View Full Profile]

    ---

    👩‍💼 Dr. Lisa Martinez (Class of 2012)
    Title: Healthcare Administrator & Physician
    Company: Regional Medical Center
    Specialties: Healthcare Careers, Work-Life Balance, Leadership
    Experience: 10+ years in healthcare
    Available: Weekend afternoons

    Bio: Dr. Martinez helps alumni explore healthcare careers and develop
    leadership skills in medical and administrative roles.

    [Schedule Session] [View Full Profile]
    """
            counselors_text.insert(tk.END, counselors_content)

            # Schedule session tab
            schedule_frame = ttk.Frame(notebook)
            notebook.add(schedule_frame, text="Schedule Session")

            self.create_counseling_form(schedule_frame)

        def show_job_board(self):
            """Show job board interface"""
            self.clear_content()
            self.update_status("Job Board")

            ttk.Label(self.content_frame, text="Alumni Job Board",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Search and filter
            search_frame = ttk.Frame(self.content_frame)
            search_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

            ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 10))
            self.job_search = tk.StringVar()
            ttk.Entry(search_frame, textvariable=self.job_search, width=20).pack(side=tk.LEFT, padx=(0, 10))

            ttk.Label(search_frame, text="Category:").pack(side=tk.LEFT, padx=(10, 5))
            self.job_category = tk.StringVar()
            category_combo = ttk.Combobox(search_frame, textvariable=self.job_category,
                                         values=["All", "Technology", "Finance", "Healthcare", "Education", "Marketing"])
            category_combo.pack(side=tk.LEFT, padx=(0, 10))
            category_combo.set("All")

            ttk.Button(search_frame, text="Search Jobs",
                      command=self.search_jobs).pack(side=tk.LEFT)

            # Job listings
            self.job_text = ScrolledText(self.content_frame, wrap=tk.WORD)
            self.job_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Load job listings
            self.load_job_listings()

            # Action buttons
            button_frame = ttk.Frame(self.content_frame)
            button_frame.pack(fill=tk.X, padx=20)

            if self.has_permission('post_jobs'):
                ttk.Button(button_frame, text="Post New Job",
                          command=self.show_post_job).pack(side=tk.LEFT, padx=(0, 10))

            ttk.Button(button_frame, text="Refresh Listings",
                      command=self.load_job_listings).pack(side=tk.LEFT)

        def show_post_job(self):
            """Show post job interface"""
            self.clear_content()
            self.update_status("Post Job Opportunity")

            ttk.Label(self.content_frame, text="Post Job Opportunity",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Create scrollable form
            canvas = tk.Canvas(self.content_frame)
            scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Job form
            self.job_vars = {}

            # Company info
            company_frame = ttk.LabelFrame(scrollable_frame, text="Company Information", padding=10)
            company_frame.pack(fill=tk.X, pady=(0, 10), padx=20)

            company_fields = [
                ("Company Name*", "company_name"),
                ("Industry*", "industry"),
                ("Company Website", "website"),
                ("Contact Email*", "contact_email")
            ]

            for i, (label, var_name) in enumerate(company_fields):
                row = i // 2
                col = i % 2

                field_frame = ttk.Frame(company_frame)
                field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')

                ttk.Label(field_frame, text=label).pack(anchor='w')
                self.job_vars[var_name] = tk.StringVar()
                ttk.Entry(field_frame, textvariable=self.job_vars[var_name]).pack(fill=tk.X)

            company_frame.columnconfigure(0, weight=1)
            company_frame.columnconfigure(1, weight=1)

            # Job details
            job_frame = ttk.LabelFrame(scrollable_frame, text="Job Details", padding=10)
            job_frame.pack(fill=tk.X, pady=(0, 10), padx=20)

            job_fields = [
                ("Job Title*", "job_title"),
                ("Location*", "location"),
                ("Job Type*", "job_type"),
                ("Experience Level*", "experience_level")
            ]

            for i, (label, var_name) in enumerate(job_fields):
                row = i // 2
                col = i % 2

                field_frame = ttk.Frame(job_frame)
                field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')

                ttk.Label(field_frame, text=label).pack(anchor='w')

                if var_name == "job_type":
                    self.job_vars[var_name] = tk.StringVar()
                    combo = ttk.Combobox(field_frame, textvariable=self.job_vars[var_name],
                                       values=["Full-time", "Part-time", "Contract", "Internship", "Remote"])
                    combo.pack(fill=tk.X)
                elif var_name == "experience_level":
                    self.job_vars[var_name] = tk.StringVar()
                    combo = ttk.Combobox(field_frame, textvariable=self.job_vars[var_name],
                                       values=["Entry Level", "Mid Level", "Senior Level", "Executive"])
                    combo.pack(fill=tk.X)
                else:
                    self.job_vars[var_name] = tk.StringVar()
                    ttk.Entry(field_frame, textvariable=self.job_vars[var_name]).pack(fill=tk.X)

            job_frame.columnconfigure(0, weight=1)
            job_frame.columnconfigure(1, weight=1)

            # Salary range
            salary_frame = ttk.Frame(job_frame)
            salary_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky='ew')

            ttk.Label(salary_frame, text="Salary Range (optional)").pack(anchor='w')
            self.job_vars['salary_range'] = tk.StringVar()
            ttk.Entry(salary_frame, textvariable=self.job_vars['salary_range']).pack(fill=tk.X)

            # Job description
            desc_frame = ttk.LabelFrame(scrollable_frame, text="Job Description", padding=10)
            desc_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10), padx=20)

            ttk.Label(desc_frame, text="Job Description*:").pack(anchor='w')
            self.job_description = ScrolledText(desc_frame, height=6, wrap=tk.WORD)
            self.job_description.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

            ttk.Label(desc_frame, text="Requirements*:").pack(anchor='w')
            self.job_requirements = ScrolledText(desc_frame, height=4, wrap=tk.WORD)
            self.job_requirements.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

            # Buttons
            button_frame = ttk.Frame(scrollable_frame)
            button_frame.pack(fill=tk.X, pady=20, padx=20)

            ttk.Button(button_frame, text="Post Job",
                      command=self.submit_job_posting).pack(side=tk.RIGHT, padx=(10, 0))
            ttk.Button(button_frame, text="Clear Form",
                      command=self.clear_job_form).pack(side=tk.RIGHT)

            # Pack canvas and scrollbar
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

        def submit_counseling_request(self):
            """Submit counseling session request"""
            if not self.counseling_vars['counselor'].get():
                messagebox.showerror("Validation Error", "Please select a counselor!")
                return

            if not self.counseling_vars['session_type'].get():
                messagebox.showerror("Validation Error", "Please select a session type!")
                return

            if not self.counseling_vars['datetime'].get():
                messagebox.showerror("Validation Error", "Please enter preferred date and time!")
                return

            messagebox.showinfo("Session Scheduled", "Career counseling session request submitted successfully!")
            self.update_status("Counseling session requested")

            # Clear form
            for var in self.counseling_vars.values():
                var.set("")
            self.counseling_notes.delete(1.0, tk.END)

        def submit_job_posting(self):
            """Submit job posting"""
            required_fields = ['company_name', 'industry', 'contact_email', 'job_title', 'location', 'job_type', 'experience_level']
            for field in required_fields:
                if not self.job_vars[field].get().strip():
                    messagebox.showerror("Validation Error", f"{field.replace('_', ' ').title()} is required!")
                    return

            description = self.job_description.get(1.0, tk.END).strip()
            requirements = self.job_requirements.get(1.0, tk.END).strip()

            if not description:
                messagebox.showerror("Validation Error", "Job description is required!")
                return

            if not requirements:
                messagebox.showerror("Validation Error", "Job requirements are required!")
                return

            messagebox.showinfo("Job Posted", "Job opportunity posted successfully!")
            self.update_status("Job posting submitted")
            self.clear_job_form()

        def view_job_details(self):
            """View details for a specific job posting"""
            # Create job selection dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Select Job to View")
            dialog.geometry("700x500")
            dialog.configure(bg='white')
            dialog.grab_set()

            frame = ttk.Frame(dialog, padding=20)
            frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frame, text="Select a Job Posting",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Job listings table
            table_frame = ttk.Frame(frame)
            table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

            columns = ('Title', 'Company', 'Location', 'Type', 'Salary')
            job_tree = ttk.Treeview(table_frame, columns=columns, show='headings')

            for col in columns:
                job_tree.heading(col, text=col)
                job_tree.column(col, width=130)

            scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=job_tree.yview)
            job_tree.configure(yscrollcommand=scrollbar_y.set)

            job_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            # Load job listings
            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT job_id, job_title, company_name, location, job_type, salary_range
                        FROM job_postings
                        WHERE status = 'active' AND expiry_date > datetime('now')
                        ORDER BY posted_date DESC
                    """)
                    jobs = cursor.fetchall()

                    for job in jobs:
                        job_tree.insert('', tk.END, values=job[1:])

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load jobs: {str(e)}")

            def show_selected_job():
                selection = job_tree.selection()
                if not selection:
                    messagebox.showwarning("No Selection", "Please select a job to view.")
                    return

                item = job_tree.item(selection[0])
                job_data = item['values']
                self._display_job_detail_window(job_data)
                dialog.destroy()

            # Buttons
            button_frame = ttk.Frame(frame)
            button_frame.pack(fill=tk.X)

            ttk.Button(button_frame, text="View Details",
                      command=show_selected_job).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Cancel",
                      command=dialog.destroy).pack(side=tk.LEFT)

