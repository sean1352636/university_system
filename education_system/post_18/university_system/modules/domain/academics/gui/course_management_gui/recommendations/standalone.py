from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.recommendations.recommend_dialog import RecommendCoursesDialog
from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.recommendations.alternative_dialog import AlternativeCourseDialog


def show_recommend_courses(self):
    """Show course recommendations dialog"""
    RecommendCoursesDialog(self.root, self.auth)


def find_alternative_courses(self):
    """Show find alternative courses dialog"""
    AlternativeCourseDialog(self.root, self.auth)


def recommend_courses_wrapper(self):
    """Recommend courses to student. Calls existing show_recommendations()."""
    self.show_recommendations()


def find_alternative_courses_wrapper(self):
    """Find alternative courses. Calls existing find_alternative_courses()."""
    self.find_alternative_courses()
