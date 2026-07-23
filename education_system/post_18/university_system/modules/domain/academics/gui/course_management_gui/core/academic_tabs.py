"""Degree Audit and Course Evaluation mixins — embed as tabs in CourseManagementGUI."""

from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.core._imports import (
    _, tk, ttk, messagebox,
)

# Lazy imports so the module loads even when dependencies are missing.
_degree_audit_cls = None
_course_eval_cls = None


def _get_degree_audit_cls():
    global _degree_audit_cls
    if _degree_audit_cls is None:
        from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.degree_audit_gui import DegreeAuditGUI
        _degree_audit_cls = DegreeAuditGUI
    return _degree_audit_cls


def _get_course_eval_cls():
    global _course_eval_cls
    if _course_eval_cls is None:
        from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.course_evaluation_gui import CourseEvaluationGUI
        _course_eval_cls = CourseEvaluationGUI
    return _course_eval_cls


class DegreeAuditTabMixin:
    """Adds a Degree Audit tab to the course management GUI."""

    def create_degree_audit_tab(self):
        """Embed the Degree Audit GUI inside a tab."""
        try:
            DegreeAuditGUI = _get_degree_audit_cls()
        except Exception:
            return  # dependency not available

        outer = ttk.Frame(self.notebook)
        self.notebook.add(outer, text=_("degree_audit.title"))

        # Create a headless instance that builds into *our* frame
        # instead of opening its own Toplevel.
        gui = object.__new__(DegreeAuditGUI)
        gui.root = self.root
        gui.auth = self.auth

        # Initialize database
        try:
            from education_system.post_18.university_system.modules.domain.academics.services.degree_audit.degree_audit_core import (
                initialize_degree_audit_database,
            )
            initialize_degree_audit_database()
        except Exception:
            pass

        # Build the sub-notebook inside our frame
        gui.notebook = ttk.Notebook(outer)
        gui.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        gui.create_progress_tab()
        gui.create_prerequisites_tab()
        gui.create_whatif_tab()
        gui.create_advising_tab()
        gui.create_graduation_tab()

        try:
            gui.load_courses()
        except Exception:
            pass

        self._degree_audit_gui = gui


class CourseEvalTabMixin:
    """Adds a Course Evaluation tab to the course management GUI."""

    def create_course_eval_tab(self):
        """Embed the Course Evaluation GUI inside a tab."""
        try:
            CourseEvaluationGUI = _get_course_eval_cls()
        except Exception:
            return  # dependency not available

        outer = ttk.Frame(self.notebook)
        self.notebook.add(outer, text=_("course_evaluation.title"))

        # Create a headless instance
        gui = object.__new__(CourseEvaluationGUI)
        gui.root = self.root
        gui.auth = self.auth

        # Initialize database
        try:
            from education_system.post_18.university_system.modules.domain.academics.services.evaluation.course_evaluation_core import (
                initialize_evaluation_database,
            )
            initialize_evaluation_database()
        except Exception:
            pass

        # Build the sub-notebook inside our frame
        gui.notebook = ttk.Notebook(outer)
        gui.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        gui.create_templates_tab()
        gui.create_evaluations_tab()
        gui.create_responses_tab()
        gui.create_results_tab()

        try:
            gui.load_evaluations()
        except Exception:
            pass

        self._course_eval_gui = gui
