from ._imports import (
    tk, ttk, messagebox, sqlite3, _, DEFAULT_DB_PATH, datetime,
)
from .validation import ValidationMixin
from .prerequisites import PrerequisitesMixin
from .scheduling import SchedulingMixin
from .waitlists import WaitlistsMixin
from .course_status import CourseStatusMixin
from .wrappers import WrappersMixin


class RecommendationsDialog(
    ValidationMixin,
    PrerequisitesMixin,
    SchedulingMixin,
    WaitlistsMixin,
    CourseStatusMixin,
    WrappersMixin,
):
    def __init__(self, parent):
        self.parent = parent
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Course Recommendations")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.dialog.focus_set()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="Course Recommendations", font=("Arial", 12, "bold")).pack(pady=10)

        # Recommendation types
        types_frame = ttk.LabelFrame(main_frame, text="Recommendation Type", padding=10)
        types_frame.pack(fill=tk.X, pady=5)

        self.rec_type = tk.StringVar(value="popular")

        ttk.Radiobutton(types_frame, text="Most Popular Courses", variable=self.rec_type,
                       value="popular").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(types_frame, text="Courses with Available Spots", variable=self.rec_type,
                       value="available").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(types_frame, text="Under-enrolled Courses", variable=self.rec_type,
                       value="under_enrolled").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(types_frame, text="New Courses", variable=self.rec_type,
                       value="new").pack(anchor=tk.W, pady=2)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Generate Recommendations", command=self.generate_recommendations).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def generate_recommendations(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            rec_type = self.rec_type.get()

            recommendations = "COURSE RECOMMENDATIONS\n"
            recommendations += "=" * 50 + "\n\n"

            if rec_type == "popular":
                recommendations += "MOST POPULAR COURSES:\n\n"
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                       COALESCE(max_enrollment, 0) as capacity
                FROM courses
                WHERE course_code IS NOT NULL
                  AND course_name IS NOT NULL
                  AND LOWER(COALESCE(status, 'active')) = 'active'
                  AND COALESCE(max_enrollment, 0) > 0
                ORDER BY enrolled DESC
                LIMIT 10
                """)

                courses = cursor.fetchall()
                recommendations += f"{'Code':<10} {'Name':<30} {'Enrolled':<10} {'Capacity':<10}\n"
                recommendations += "-" * 60 + "\n"

                for code, name, enrolled, capacity in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    recommendations += f"{code:<10} {name_short:<30} {enrolled:<10} {capacity:<10}\n"

            elif rec_type == "available":
                recommendations += "COURSES WITH AVAILABLE SPOTS:\n\n"
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                       COALESCE(max_enrollment, 0) as capacity,
                       (COALESCE(max_enrollment, 0) - COALESCE(current_enrollment, 0)) as available
                FROM courses
                WHERE course_code IS NOT NULL
                  AND course_name IS NOT NULL
                  AND LOWER(COALESCE(status, 'active')) = 'active'
                  AND COALESCE(current_enrollment, 0) < COALESCE(max_enrollment, 0)
                ORDER BY available DESC
                LIMIT 15
                """)

                courses = cursor.fetchall()
                recommendations += f"{'Code':<10} {'Name':<30} {'Available':<10} {'Total':<10}\n"
                recommendations += "-" * 60 + "\n"

                for code, name, enrolled, capacity, available in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    recommendations += f"{code:<10} {name_short:<30} {available:<10} {capacity:<10}\n"

            elif rec_type == "under_enrolled":
                recommendations += "UNDER-ENROLLED COURSES (< 50% capacity):\n\n"
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                       COALESCE(max_enrollment, 0) as capacity
                FROM courses
                WHERE course_code IS NOT NULL
                  AND course_name IS NOT NULL
                  AND LOWER(COALESCE(status, 'active')) = 'active'
                  AND COALESCE(max_enrollment, 0) > 0
                  AND COALESCE(current_enrollment, 0) < (COALESCE(max_enrollment, 0) * 0.5)
                ORDER BY (CAST(current_enrollment AS FLOAT) / max_enrollment)
                LIMIT 15
                """)

                courses = cursor.fetchall()
                recommendations += f"{'Code':<10} {'Name':<30} {'Fill Rate':<10} {'Enrolled':<10}\n"
                recommendations += "-" * 60 + "\n"

                for code, name, enrolled, capacity in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    fill_rate = f"{(enrolled/capacity*100):.1f}%" if capacity > 0 else "0%"
                    enrollment_str = f"{enrolled}/{capacity}"
                    recommendations += f"{code:<10} {name_short:<30} {fill_rate:<10} {enrollment_str:<10}\n"

            elif rec_type == "new":
                recommendations += "RECENTLY CREATED COURSES:\n\n"
                cursor.execute("""
                SELECT course_code, course_name, created_at, status
                FROM courses
                WHERE created_at >= date('now', '-6 months')
                ORDER BY created_at DESC
                LIMIT 10
                """)

                courses = cursor.fetchall()
                recommendations += f"{'Code':<10} {'Name':<30} {'Created':<12} {'Status':<10}\n"
                recommendations += "-" * 62 + "\n"

                for code, name, created, status in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    created_date = created.split()[0] if created else "Unknown"
                    recommendations += f"{code:<10} {name_short:<30} {created_date:<12} {status:<10}\n"

            conn.close()

            if not courses:
                recommendations += "No recommendations found for the selected criteria.\n"

            self.result = recommendations
            self.dialog.destroy()

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to generate recommendations: {e}")
