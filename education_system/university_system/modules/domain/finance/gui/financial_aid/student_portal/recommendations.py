"""
Recommendations mixin - personalized scholarship recommendations.
"""

from education_system.university_system.modules.domain.finance.gui.financial_aid.common_imports import (
    tk,
    ttk,
    scrolledtext,
    logging,
    clear_frame,
    create_data_table,
    format_date,
    show_error,
    show_success,
    show_warning,
)
from education_system.university_system.modules.shared.utils.i18n import get_text

logger = logging.getLogger(__name__)


class RecommendationsMixin:
    """Scholarship recommendation functionality"""

    def show_recommendations(self):
        """Display personalized scholarship recommendations"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text("financial_aid.student_portal.recommendations.title", "Personalized Scholarship Recommendations"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.student_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Control buttons
        button_frame = ttk.Frame(self.parent_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=get_text("financial_aid.student_portal.buttons.generate_recommendations", "Generate New Recommendations"),
                  command=self._generate_recommendations).pack(side='left', padx=5)
        ttk.Button(button_frame, text=get_text("financial_aid.student_portal.buttons.refresh", "Refresh"), command=self._load_recommendations).pack(side='left', padx=5)

        # Recommendations table
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        col_name = get_text("financial_aid.student_portal.recommendations.columns.name", "Name")
        col_award = get_text("financial_aid.student_portal.recommendations.columns.award", "Award")
        col_deadline = get_text("financial_aid.student_portal.recommendations.columns.deadline", "Deadline")
        col_match = get_text("financial_aid.student_portal.recommendations.columns.match_score", "Match Score")
        col_priority = get_text("financial_aid.student_portal.recommendations.columns.priority", "Priority")
        col_eligibility = get_text("financial_aid.student_portal.recommendations.columns.eligibility", "Eligibility")
        columns = [col_name, col_award, col_deadline, col_match, col_priority, col_eligibility]
        self.rec_tree = create_data_table(table_frame, columns, {
            col_name: 250, col_award: 120, col_deadline: 100,
            col_match: 80, col_priority: 80, col_eligibility: 120
        })

        # Details panel
        details_frame = ttk.LabelFrame(self.parent_frame, text=get_text("financial_aid.student_portal.recommendations.details", "Recommendation Details"), padding=10)
        details_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.rec_details_text = scrolledtext.ScrolledText(details_frame, wrap=tk.WORD, height=10)
        self.rec_details_text.pack(fill='both', expand=True)

        # Action buttons
        btn_frame = ttk.Frame(self.parent_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(btn_frame, text=get_text("financial_aid.student_portal.buttons.start_application", "Start Application"),
                  command=self._start_application_from_rec, style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.student_portal.buttons.view_full_details", "View Full Details"),
                  command=self._view_rec_details).pack(side='left', padx=5)

        # Bind selection
        self.rec_tree.bind('<<TreeviewSelect>>', self._on_rec_selection)

        # Load recommendations
        self._load_recommendations()

    def _load_recommendations(self):
        """Load and display recommendations"""
        try:
            # Clear tree
            for item in self.rec_tree.get_children():
                self.rec_tree.delete(item)

            from education_system.university_system.modules.domain.finance.scholarship_finder.services.scholarship_service import RecommendationEngine

            recommendations = RecommendationEngine.get_cached_recommendations(self.student_id)

            if not recommendations:
                show_warning(get_text("financial_aid.student_portal.warnings.no_recommendations_title", "No Recommendations"),
                           get_text("financial_aid.student_portal.warnings.no_recommendations_message", "No recommendations found. Click 'Generate New Recommendations'."))
                return

            for rec in recommendations:
                award_range = f"${rec['award_amount_min']:,.0f}"
                if rec.get('award_amount_max'):
                    award_range += f"-${rec['award_amount_max']:,.0f}"

                self.rec_tree.insert('', 'end', values=(
                    rec['scholarship_name'][:40],
                    award_range,
                    format_date(rec['application_deadline']),
                    f"{rec['match_score']:.0f}%",
                    rec['priority_level'].upper(),
                    rec['eligibility_status']
                ), tags=(str(rec['scholarship_id']), str(rec['match_score'])))

            # Color code by priority
            for item in self.rec_tree.get_children():
                values = self.rec_tree.item(item)['values']
                if 'HIGH' in str(values):
                    self.rec_tree.item(item, tags=('high',))
                elif 'MEDIUM' in str(values):
                    self.rec_tree.item(item, tags=('medium',))

            self.rec_tree.tag_configure('high', background='#d4edda')
            self.rec_tree.tag_configure('medium', background='#fff3cd')

        except Exception as e:
            logger.error(f"Error loading recommendations: {e}")
            show_error(get_text("financial_aid.student_portal.errors.title", "Error"), get_text("financial_aid.student_portal.errors.failed_load_recommendations", "Failed to load recommendations: {error}", error=str(e)))

    def _generate_recommendations(self):
        """Generate new recommendations"""
        from tkinter import messagebox
        if messagebox.askyesno(get_text("financial_aid.student_portal.confirm", "Confirm"), get_text("financial_aid.student_portal.recommendations.confirm_generate", "Generate new personalized recommendations?\n\nThis will analyze your profile and find matching scholarships.")):
            try:
                from education_system.university_system.modules.domain.finance.scholarship_finder.services.scholarship_service import RecommendationEngine

                recommendations = RecommendationEngine.generate_recommendations(self.student_id, limit=20)

                if recommendations:
                    show_success(get_text("financial_aid.student_portal.success.title", "Success"), get_text("financial_aid.student_portal.success.recommendations_generated", "Generated {count} recommendations!", count=len(recommendations)))
                    self._load_recommendations()
                else:
                    show_warning(get_text("financial_aid.student_portal.warning", "Warning"),
                               get_text("financial_aid.student_portal.warnings.generate_recommendations_failed", "Could not generate recommendations.\n\nPlease complete your profile in the Profile tab."))

            except Exception as e:
                logger.error(f"Error generating recommendations: {e}")
                show_error(get_text("financial_aid.student_portal.errors.title", "Error"), get_text("financial_aid.student_portal.errors.failed_generate_recommendations", "Failed to generate recommendations: {error}", error=str(e)))

    def _on_rec_selection(self, event):
        """Handle recommendation selection"""
        selection = self.rec_tree.selection()
        if not selection:
            return

        try:
            tags = self.rec_tree.item(selection[0])['tags']
            if tags:
                scholarship_id = int(tags[0])
                from education_system.university_system.modules.domain.finance.scholarship_finder.services.scholarship_service import ScholarshipDatabase
                scholarship = ScholarshipDatabase.get_scholarship_details(scholarship_id)
                if scholarship:
                    self._display_recommendation_details(scholarship, tags)
        except Exception as e:
            logger.error(f"Error on selection: {e}")

    def _display_recommendation_details(self, scholarship: dict, tags: tuple):
        """Display recommendation details"""
        self.rec_details_text.delete('1.0', tk.END)

        self.rec_details_text.insert(tk.END, f"{scholarship['scholarship_name']}\n", 'title')
        self.rec_details_text.tag_config('title', font=('Arial', 12, 'bold'))

        if len(tags) > 1:
            self.rec_details_text.insert(tk.END, f"\n{get_text('financial_aid.student_portal.recommendations.match_score_label', 'Match Score: {score}%', score=tags[1])}\n", 'score')
            self.rec_details_text.tag_config('score', foreground='green', font=('Arial', 10, 'bold'))

        self.rec_details_text.insert(tk.END, f"\n{get_text('financial_aid.student_portal.recommendations.organization_label', 'Organization: {org}', org=scholarship['organization'])}\n")

        award_range = f"${scholarship['award_amount_min']:,.0f}"
        if scholarship.get('award_amount_max'):
            award_range += f" - ${scholarship['award_amount_max']:,.0f}"
        self.rec_details_text.insert(tk.END, f"{get_text('financial_aid.student_portal.recommendations.award_label', 'Award: {amount}', amount=award_range)}\n")

        self.rec_details_text.insert(tk.END, f"{get_text('financial_aid.student_portal.recommendations.deadline_label', 'Deadline: {date}', date=scholarship['application_deadline'])}\n\n")
        self.rec_details_text.insert(tk.END, f"{scholarship['description']}\n\n")

        self.rec_details_text.insert(tk.END, f"{get_text('financial_aid.student_portal.recommendations.requirements_heading', 'Requirements:')}\n", 'subtitle')
        self.rec_details_text.tag_config('subtitle', font=('Arial', 10, 'bold'))

        if scholarship.get('min_gpa'):
            self.rec_details_text.insert(tk.END, f"  \u2022 {get_text('financial_aid.student_portal.recommendations.min_gpa', 'Min GPA: {gpa}', gpa=scholarship['min_gpa'])}\n")
        if scholarship.get('essay_required'):
            self.rec_details_text.insert(tk.END, f"  \u2022 {get_text('financial_aid.student_portal.recommendations.essay_required', 'Essay required')}\n")
        if scholarship.get('recommendation_letters_required'):
            self.rec_details_text.insert(tk.END,
                f"  \u2022 {get_text('financial_aid.student_portal.recommendations.recommendation_letters', '{count} recommendation letters', count=scholarship['recommendation_letters_required'])}\n")

    def _start_application_from_rec(self):
        """Start application from recommendation"""
        selection = self.rec_tree.selection()
        if not selection:
            show_warning(get_text("financial_aid.student_portal.warning", "Warning"), get_text("financial_aid.student_portal.warnings.select_recommendation", "Please select a recommendation."))
            return

        try:
            tags = self.rec_tree.item(selection[0])['tags']
            if not tags:
                return

            scholarship_id = int(tags[0])
            match_score = float(tags[1]) if len(tags) > 1 else None

            from tkinter import messagebox
            if messagebox.askyesno(get_text("financial_aid.student_portal.confirm", "Confirm"), get_text("financial_aid.student_portal.recommendations.confirm_start_application", "Start application for this scholarship?")):
                from education_system.university_system.modules.domain.finance.scholarship_finder.services.scholarship_service import ApplicationManager

                app_id = ApplicationManager.start_application(self.student_id, scholarship_id, match_score)
                show_success(get_text("financial_aid.student_portal.success.title", "Success"), get_text("financial_aid.student_portal.success.application_started", "Application started! ID: {id}", id=app_id))
                self.show_my_applications()

        except Exception as e:
            logger.error(f"Error starting application: {e}")
            show_error(get_text("financial_aid.student_portal.errors.title", "Error"), get_text("financial_aid.student_portal.errors.failed_start_application", "Failed to start application: {error}", error=str(e)))

    def _view_rec_details(self):
        """View full details from recommendation"""
        selection = self.rec_tree.selection()
        if not selection:
            show_warning(get_text("financial_aid.student_portal.warning", "Warning"), get_text("financial_aid.student_portal.warnings.select_recommendation", "Please select a recommendation."))
            return

        tags = self.rec_tree.item(selection[0])['tags']
        if tags:
            scholarship_id = int(tags[0])
            self._show_scholarship_details_dialog(scholarship_id)
