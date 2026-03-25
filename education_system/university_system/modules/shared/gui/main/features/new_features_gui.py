# GUI launcher functions for new university features (modules 21-30)
import tkinter as tk
from tkinter import ttk, messagebox
import logging

from education_system.university_system.modules.shared.utils.i18n import get_text as _t

logger = logging.getLogger(__name__)


def show_hesa_export_gui(self):
    """Launch HESA Data Export GUI"""
    try:
        from education_system.university_system.modules.domain.hesa_export.gui.hesa_export_gui import HESAExportGUI
        gui = HESAExportGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import HESA Export GUI: {e}")
        messagebox.showerror(_t("common.error"), f"HESA Export GUI not available: {e}")
    except Exception as e:
        logger.error(f"Error launching HESA Export GUI: {e}")
        messagebox.showerror(_t("common.error"), f"Failed to launch HESA Export: {e}")


def show_external_examiner_gui(self):
    """Launch External Examiner GUI"""
    try:
        from education_system.university_system.modules.domain.external_examiners.gui.external_examiner_gui import ExternalExaminerGUI
        gui = ExternalExaminerGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import External Examiner GUI: {e}")
        messagebox.showerror(_t("common.error"), f"External Examiner GUI not available: {e}")
    except Exception as e:
        logger.error(f"Error launching External Examiner GUI: {e}")
        messagebox.showerror(_t("common.error"), f"Failed to launch External Examiner: {e}")


def show_student_app_gui(self):
    """Launch Student App / Portal GUI"""
    try:
        from education_system.university_system.modules.domain.student_app.gui.student_app_gui import StudentAppGUI
        gui = StudentAppGUI(parent=self.root, auth=self.auth)
    except ImportError as e:
        logger.error(f"Failed to import Student App GUI: {e}")
        messagebox.showerror(_t("common.error"), f"Student App GUI not available: {e}")
    except Exception as e:
        logger.error(f"Error launching Student App GUI: {e}")
        messagebox.showerror(_t("common.error"), f"Failed to launch Student App: {e}")


def show_achievement_badge_gui(self):
    """Launch Achievement Badge GUI"""
    try:
        from education_system.university_system.modules.domain.achievement_badges.gui.achievement_badge_gui import AchievementBadgeGUI
        gui = AchievementBadgeGUI(parent=self.root, auth=self.auth)
    except ImportError as e:
        logger.error(f"Failed to import Achievement Badge GUI: {e}")
        messagebox.showerror(_t("common.error"), f"Achievement Badge GUI not available: {e}")
    except Exception as e:
        logger.error(f"Error launching Achievement Badge GUI: {e}")
        messagebox.showerror(_t("common.error"), f"Failed to launch Achievement Badges: {e}")


def show_study_recommendations_gui(self):
    """Launch Study Recommendations GUI"""
    try:
        from education_system.university_system.modules.domain.study_recommendations.gui.study_recommendation_gui import StudyRecommendationGUI
        gui = StudyRecommendationGUI(parent=self.root, auth=self.auth)
    except ImportError as e:
        logger.error(f"Failed to import Study Recommendations GUI: {e}")
        messagebox.showerror(_t("common.error"), f"Study Recommendations GUI not available: {e}")
    except Exception as e:
        logger.error(f"Error launching Study Recommendations GUI: {e}")
        messagebox.showerror(_t("common.error"), f"Failed to launch Study Recommendations: {e}")


def show_clearing_adjustment_gui(self):
    """Launch Clearing & Adjustment GUI"""
    try:
        from education_system.university_system.modules.domain.clearing_adjustment.gui.clearing_adjustment_gui import ClearingAdjustmentGUI
        gui = ClearingAdjustmentGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Clearing & Adjustment GUI: {e}")
        messagebox.showerror(_t("common.error"), f"Clearing & Adjustment GUI not available: {e}")
    except Exception as e:
        logger.error(f"Error launching Clearing & Adjustment GUI: {e}")
        messagebox.showerror(_t("common.error"), f"Failed to launch Clearing & Adjustment: {e}")
