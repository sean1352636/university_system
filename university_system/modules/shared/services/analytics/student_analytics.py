from university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection
from university_system.modules.shared.constants import paths
from university_system.modules.shared.utils.i18n import get_text, _
import os
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
from datetime import datetime, timedelta
import calendar
from collections import Counter, defaultdict
import seaborn as sns
import json
import warnings
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import openpyxl
from openpyxl.styles import Font, Fill, PatternFill, Alignment
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
# get_connection already imported from university_system.infrastructure.database.db above

def configure_matplotlib():
    """Configure matplotlib backend with proper GUI support and error handling"""
    try:
        import tkinter
        # Test if tkinter actually works
        root = tkinter.Tk()
        root.withdraw()  # Hide the test window
        root.destroy()   # Clean up test window
        
        matplotlib.use('TkAgg')
        print("✓ GUI mode enabled with TkAgg backend")
        return True
    except Exception as e:
        print(f"TkAgg not available ({e}), trying Qt5Agg...")
        try:
            matplotlib.use('Qt5Agg')
            print("✓ GUI mode enabled with Qt5Agg backend")
            return True
        except Exception as e2:
            print(f"Qt5Agg not available ({e2}), trying other backends...")
            try:
                matplotlib.use('GTK3Agg')
                print("✓ GUI mode enabled with GTK3Agg backend")
                return True
            except Exception as e3:
                print(f"No GUI backends available, falling back to Agg")
                matplotlib.use('Agg')
                return False

# Configure matplotlib and seaborn at startup
GUI_AVAILABLE = configure_matplotlib()
sns.set_style("whitegrid")
plt.style.use('seaborn-v0_8')
warnings.filterwarnings('ignore')

# Global configuration
CONFIG = {
    'colors': ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b'],
    'figure_size': (15, 10),
    'dpi': 300,
    'export_formats': ['png', 'pdf', 'svg', 'excel'],
    'email_config': {
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'sender_email': '',
        'sender_password': ''
    }
}

class StudentAnalytics:
    def __init__(self, gui_mode=False):
        # Use the database connection from the infrastructure
        conn = get_connection()
        if hasattr(conn, 'execute'):
            # Get database path from connection
            self.db_path = conn.execute("PRAGMA database_list").fetchone()[2] if conn else str(paths.DEFAULT_DB_PATH)
            conn.close()
        else:
            self.db_path = str(paths.DEFAULT_DB_PATH)
        # Use canonical analytics directories
        self.plots_dir = str(paths.ANALYTICS_PLOTS_DIR)
        self.reports_dir = str(paths.ANALYTICS_REPORTS_DIR)
        self.create_directories()
        self.custom_filters = {}
        self.gui_mode = gui_mode  # Flag to control output mode
        
    def create_directories(self):
        """Create necessary directories"""
        for directory in [self.plots_dir, self.reports_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
    
    def get_connection(self):
        """Get database connection"""
        return get_connection()
    
    def get_all_students(self, filters=None):
        """Retrieve all student records with optional filtering"""
        try:
            conn = self.get_connection()
            query = "SELECT * FROM students"
            params = []
            
            if filters:
                conditions = []
                for field, value in filters.items():
                    if field == 'age_range':
                        conditions.append("age BETWEEN ? AND ?")
                        params.extend(value)
                    elif field == 'date_range':
                        conditions.append("registration_datetime BETWEEN ? AND ?")
                        params.extend(value)
                    elif isinstance(value, list):
                        placeholders = ','.join(['?' for _ in value])
                        conditions.append(f"{field} IN ({placeholders})")
                        params.extend(value)
                    else:
                        conditions.append(f"{field} = ?")
                        params.append(value)
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
            
            students_df = pd.read_sql_query(query, conn, params=params)
            conn.close()
            
            # Simulate additional data fields for enhanced analytics
            if not students_df.empty:
                students_df = self.simulate_additional_data(students_df)
            
            return students_df
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return pd.DataFrame()
    
    def simulate_additional_data(self, df):
        """Simulate additional data fields for demonstration"""
        np.random.seed(42)
        n = len(df)
        
        # Simulate grades (A-F scale)
        grades = np.random.choice(['A', 'B', 'C', 'D', 'F'], n, p=[0.2, 0.3, 0.3, 0.15, 0.05])
        df['overall_grade'] = grades
        
        # Simulate GPA (0.0-4.0)
        grade_mapping = {'A': 4.0, 'B': 3.0, 'C': 2.0, 'D': 1.0, 'F': 0.0}
        df['gpa'] = df['overall_grade'].map(grade_mapping) + np.random.normal(0, 0.3, n)
        df['gpa'] = np.clip(df['gpa'], 0.0, 4.0)
        
        # Simulate completion status
        df['completion_status'] = np.random.choice(['Active', 'Completed', 'Dropped', 'On Hold'], 
                                                  n, p=[0.6, 0.25, 0.1, 0.05])
        
        # Simulate engagement score (0-100)
        df['engagement_score'] = np.random.beta(2, 2, n) * 100
        
        # Simulate location data
        locations = ['London', 'Manchester', 'Birmingham', 'Leeds', 'Liverpool', 'Bristol']
        df['location'] = np.random.choice(locations, n)
        
        # Simulate previous education
        education_levels = ['High School', 'Bachelor', 'Master', 'PhD', 'Professional']
        df['previous_education'] = np.random.choice(education_levels, n, p=[0.4, 0.3, 0.2, 0.05, 0.05])
        
        return df
    
    def get_all_modules(self, filters=None):
        """Retrieve all module assignments with optional filtering"""
        try:
            conn = self.get_connection()
            query = """
            SELECT sm.id, sm.student_id, sm.module_code, sm.enrollment_date,
                   sm.grade, sm.completion_date, sm.status,
                   s.course, s.age, s.gender,
                   m.module_name, m.module_type, m.credits, m.department
            FROM student_modules sm
            JOIN students s ON sm.student_id = s.student_id
            LEFT JOIN modules m ON sm.module_code = m.module_code
            """
            params = []

            if filters:
                conditions = []
                for field, value in filters.items():
                    if field in ['course', 'age', 'gender']:
                        conditions.append(f"s.{field} = ?")
                        params.append(value)
                    elif field in ['module_name', 'module_type', 'department']:
                        conditions.append(f"m.{field} = ?")
                        params.append(value)
                    else:
                        conditions.append(f"sm.{field} = ?")
                        params.append(value)

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

            modules_df = pd.read_sql_query(query, conn, params=params)
            conn.close()

            # Simulate additional module data only for missing columns
            if not modules_df.empty:
                modules_df = self.simulate_module_data(modules_df)

            return modules_df
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return pd.DataFrame()
    
    def simulate_module_data(self, df):
        """Add only missing columns based on actual database data"""
        n = len(df)

        # Only add module_grade if missing and try to derive from status
        if 'module_grade' not in df.columns:
            if 'status' in df.columns:
                # Map status to grades where possible
                grade_map = {'Completed': 'B', 'In Progress': 'C', 'Failed': 'F'}
                df['module_grade'] = df['status'].map(grade_map).fillna('C')
            else:
                # Last resort: use placeholder
                df['module_grade'] = 'B'

        # Only add module_completion if missing
        if 'module_completion' not in df.columns:
            if 'status' in df.columns:
                df['module_completion'] = df['status']
            else:
                df['module_completion'] = 'Completed'

        # Only add module_type if missing from modules join
        if 'module_type' not in df.columns:
            df['module_type'] = 'Standard'
        else:
            # Fill any NaN values with 'Standard'
            df['module_type'] = df['module_type'].fillna('Standard')

        # Only add difficulty_rating if missing
        if 'difficulty_rating' not in df.columns:
            df['difficulty_rating'] = 3  # Medium difficulty default

        # Only add attendance_rate if missing
        if 'attendance_rate' not in df.columns:
            df['attendance_rate'] = 85.0  # Default good attendance

        return df

    def display_main_menu(self):
        """Display the enhanced analytics dashboard menu"""
        if not GUI_AVAILABLE:
            print("\n" + "="*80)
            print("NOTE: GUI display not available in this environment.")
            print(f"All plots will be automatically saved to '{self.plots_dir}' folder.")
            print("="*80)
        
        while True:
            print("\n" + "="*80)
            print("🎓 ENHANCED STUDENT ANALYTICS DASHBOARD 🎓")
            print("="*80)
            print("📊 BASIC ANALYTICS")
            print("1.  Student Demographics")
            print("2.  Module Popularity Analysis") 
            print("3.  Course Enrollment Statistics")
            print("4.  Registration Timeline")
            
            print("\n📈 PERFORMANCE ANALYTICS")
            print("5.  Grade Distribution Analysis")
            print("6.  Academic Risk Assessment")
            print("7.  Module Difficulty Analysis")
            print("8.  Student Performance Trends")
            
            print("\n🔍 ADVANCED ANALYTICS")
            print("9.  Correlation Analysis")
            print("10. Cohort Analysis")
            print("11. Engagement Scoring")
            print("12. Predictive Analytics")
            
            print("\n📋 REPORTING & EXPORT")
            print("13. Generate Complete Report")
            print("14. Custom Report Builder")
            print("15. Export Data")
            print("16. Email Reports")
            
            print("\n🔧 UTILITIES")
            print("17. Data Quality Check")
            print("18. Advanced Filtering")
            print("19. Configuration Settings")
            print("20. Exit")
            
            choice = input("\nEnter your choice (1-20): ")
            
            try:
                if choice == '1':
                    self.analyze_student_demographics()
                elif choice == '2':
                    self.analyze_module_popularity()
                elif choice == '3':
                    self.analyze_course_enrollments()
                elif choice == '4':
                    self.analyze_registration_timeline()
                elif choice == '5':
                    self.analyze_grade_distribution()
                elif choice == '6':
                    self.analyze_academic_risk()
                elif choice == '7':
                    self.analyze_module_difficulty()
                elif choice == '8':
                    self.analyze_performance_trends()
                elif choice == '9':
                    self.analyze_correlations()
                elif choice == '10':
                    self.analyze_cohorts()
                elif choice == '11':
                    self.analyze_engagement()
                elif choice == '12':
                    self.predictive_analytics()
                elif choice == '13':
                    self.generate_complete_report()
                elif choice == '14':
                    self.custom_report_builder()
                elif choice == '15':
                    self.export_data()
                elif choice == '16':
                    self.email_reports()
                elif choice == '17':
                    self.data_quality_check()
                elif choice == '18':
                    self.advanced_filtering()
                elif choice == '19':
                    self.configuration_settings()
                elif choice == '20':
                    print("Thank you for using Enhanced Student Analytics Dashboard!")
                    break
                else:
                    print("Invalid choice. Please try again.")
            except Exception as e:
                print(f"An error occurred: {e}")
                print("Please try again or contact support.")

    def safe_plot_data(self, x_data, y_data):
        """Ensure data is finite before plotting"""
        mask = np.isfinite(x_data) & np.isfinite(y_data)
        return x_data[mask], y_data[mask]
        
    def save_or_display_plot(self, plt_figure, plot_type, export_format='png'):
        """Enhanced plot saving with multiple format support"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if export_format == 'png':
            filename = f"{self.plots_dir}/{plot_type}_{timestamp}.png"
            plt_figure.savefig(filename, dpi=CONFIG['dpi'], bbox_inches='tight')
        elif export_format == 'pdf':
            filename = f"{self.plots_dir}/{plot_type}_{timestamp}.pdf"
            plt_figure.savefig(filename, format='pdf', bbox_inches='tight')
        elif export_format == 'svg':
            filename = f"{self.plots_dir}/{plot_type}_{timestamp}.svg"
            plt_figure.savefig(filename, format='svg', bbox_inches='tight')

        # In GUI mode, just return the figure - let the GUI wrapper handle display
        if self.gui_mode:
            return plt_figure

        # CLI mode - prompt user for action
        if GUI_AVAILABLE:
            while True:
                choice = input(f"Would you like to (1) save, (2) display, or (3) both? Enter 1, 2, or 3: ")

                if choice == '1':
                    print(f"Plot saved to {filename}")
                    plt.close(plt_figure)
                    break
                elif choice == '2':
                    try:
                        plt.figure(plt_figure.number)
                        print(f"Displaying {plot_type}...")
                        plt.show()
                        break
                    except Exception as e:
                        print(f"Error displaying plot: {e}")
                        print(f"Plot saved to {filename}")
                        plt.close(plt_figure)
                        break
                elif choice == '3':
                    try:
                        print(f"Plot saved to {filename}")
                        plt.figure(plt_figure.number)
                        plt.show()
                        break
                    except Exception as e:
                        print(f"Plot saved to {filename}")
                        plt.close(plt_figure)
                        break
                else:
                    print("Invalid choice. Please enter 1, 2, or 3.")
        else:
            print(f"Plot automatically saved to {filename}")
            plt.close(plt_figure)
    
    def analyze_student_demographics(self):
        """Enhanced student demographics analysis"""
        students_df = self.get_all_students(self.custom_filters)

        if students_df.empty:
            print("No student data available for analysis.")
            return

        print("\nGenerating Enhanced Student Demographics Analysis...")

        # Create comprehensive demographics analysis
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Enhanced Student Demographics Analysis', fontsize=20)
        colors = CONFIG['colors']

        # 1. Gender Distribution
        ax1 = fig.add_subplot(331)
        gender_data = students_df['gender'].dropna()
        if len(gender_data) > 0:
            gender_counts = gender_data.value_counts()
            ax1.pie(gender_counts, labels=gender_counts.index, autopct='%1.1f%%',
                    startangle=90, colors=colors[:len(gender_counts)])
        else:
            ax1.text(0.5, 0.5, 'No gender data available', ha='center', va='center', transform=ax1.transAxes)
        ax1.set_title('Gender Distribution')

        # 2. Age Distribution with statistics
        ax2 = fig.add_subplot(332)
        age_data = students_df['age'].dropna()
        if len(age_data) > 0:
            min_age = int(age_data.min())
            max_age = int(age_data.max())
            if min_age < max_age:
                ax2.hist(age_data, bins=range(min_age, max_age + 2),
                        edgecolor='black', alpha=0.7)
            else:
                ax2.hist(age_data, bins=10, edgecolor='black', alpha=0.7)
            ax2.axvline(age_data.mean(), color='red', linestyle='--', label=f'Mean: {age_data.mean():.1f}')
            ax2.axvline(age_data.median(), color='green', linestyle='--', label=f'Median: {age_data.median():.1f}')
            ax2.legend()
        else:
            ax2.text(0.5, 0.5, 'No age data available', ha='center', va='center', transform=ax2.transAxes)
        ax2.set_xlabel('Age')
        ax2.set_ylabel('Number of Students')
        ax2.set_title('Age Distribution')

        # 3. Course Distribution
        ax3 = fig.add_subplot(333)
        course_data = students_df['course'].dropna()
        if len(course_data) > 0:
            course_counts = course_data.value_counts()
            ax3.bar(course_counts.index, course_counts.values, color=colors[:len(course_counts)])
            ax3.tick_params(axis='x', rotation=45)
        else:
            ax3.text(0.5, 0.5, 'No course data available', ha='center', va='center', transform=ax3.transAxes)
        ax3.set_xlabel('Course')
        ax3.set_ylabel('Number of Students')
        ax3.set_title('Course Distribution')

        # 4. GPA Distribution
        ax4 = fig.add_subplot(334)
        gpa_data = students_df['gpa'].dropna() if 'gpa' in students_df.columns else pd.Series()
        if len(gpa_data) > 0:
            ax4.hist(gpa_data, bins=20, edgecolor='black', alpha=0.7)
            ax4.axvline(gpa_data.mean(), color='red', linestyle='--', label=f'Mean GPA: {gpa_data.mean():.2f}')
            ax4.legend()
        else:
            ax4.text(0.5, 0.5, 'No GPA data available', ha='center', va='center', transform=ax4.transAxes)
        ax4.set_xlabel('GPA')
        ax4.set_ylabel('Number of Students')
        ax4.set_title('GPA Distribution')

        # 5. Location Distribution
        ax5 = fig.add_subplot(335)
        location_data = students_df['location'].dropna() if 'location' in students_df.columns else pd.Series()
        if len(location_data) > 0:
            location_counts = location_data.value_counts()
            ax5.bar(location_counts.index, location_counts.values, color=colors[:len(location_counts)])
            ax5.tick_params(axis='x', rotation=45)
        else:
            ax5.text(0.5, 0.5, 'No location data available', ha='center', va='center', transform=ax5.transAxes)
        ax5.set_xlabel('Location')
        ax5.set_ylabel('Number of Students')
        ax5.set_title('Geographic Distribution')

        # 6. Previous Education
        ax6 = fig.add_subplot(336)
        edu_data = students_df['previous_education'].dropna() if 'previous_education' in students_df.columns else pd.Series()
        if len(edu_data) > 0:
            edu_counts = edu_data.value_counts()
            ax6.pie(edu_counts, labels=edu_counts.index, autopct='%1.1f%%', startangle=90)
        else:
            ax6.text(0.5, 0.5, 'No education data available', ha='center', va='center', transform=ax6.transAxes)
        ax6.set_title('Previous Education Level')

        # 7. Completion Status
        ax7 = fig.add_subplot(337)
        status_data = students_df['completion_status'].dropna() if 'completion_status' in students_df.columns else pd.Series()
        if len(status_data) > 0:
            status_counts = status_data.value_counts()
            ax7.bar(status_counts.index, status_counts.values, color=colors[:len(status_counts)])
            ax7.tick_params(axis='x', rotation=45)
        else:
            ax7.text(0.5, 0.5, 'No status data available', ha='center', va='center', transform=ax7.transAxes)
        ax7.set_xlabel('Status')
        ax7.set_ylabel('Number of Students')
        ax7.set_title('Completion Status')

        # 8. Engagement Score Distribution
        ax8 = fig.add_subplot(338)
        engagement_data = students_df['engagement_score'].dropna() if 'engagement_score' in students_df.columns else pd.Series()
        if len(engagement_data) > 0:
            ax8.hist(engagement_data, bins=20, edgecolor='black', alpha=0.7)
            ax8.axvline(engagement_data.mean(), color='red', linestyle='--',
                       label=f'Mean: {engagement_data.mean():.1f}')
            ax8.legend()
        else:
            ax8.text(0.5, 0.5, 'No engagement data available', ha='center', va='center', transform=ax8.transAxes)
        ax8.set_xlabel('Engagement Score')
        ax8.set_ylabel('Number of Students')
        ax8.set_title('Student Engagement Distribution')

        # 9. Age vs GPA Scatter
        ax9 = fig.add_subplot(339)
        # Filter for rows that have both age and gpa data
        scatter_df = students_df.dropna(subset=['age', 'gpa']) if 'gpa' in students_df.columns else pd.DataFrame()
        if len(scatter_df) > 0 and 'engagement_score' in scatter_df.columns:
            scatter = ax9.scatter(scatter_df['age'], scatter_df['gpa'],
                                 c=scatter_df['engagement_score'], cmap='viridis', alpha=0.6)
            plt.colorbar(scatter, ax=ax9, label='Engagement Score')
        elif len(scatter_df) > 0:
            ax9.scatter(scatter_df['age'], scatter_df['gpa'], alpha=0.6)
        else:
            ax9.text(0.5, 0.5, 'Insufficient data for scatter plot', ha='center', va='center', transform=ax9.transAxes)
        ax9.set_xlabel('Age')
        ax9.set_ylabel('GPA')
        ax9.set_title('Age vs GPA (colored by Engagement)')

        plt.tight_layout(rect=[0, 0, 1, 0.95])

        # Build summary statistics
        summary_text = "\n" + "="*60 + "\n"
        summary_text += "ENHANCED DEMOGRAPHICS SUMMARY\n"
        summary_text += "="*60 + "\n"
        summary_text += f"Total students: {len(students_df)}\n"

        if 'completion_status' in students_df.columns:
            active_count = len(students_df[students_df['completion_status'] == 'Active'])
            completed_count = len(students_df[students_df['completion_status'] == 'Completed'])
            summary_text += f"Active students: {active_count}\n"
            summary_text += f"Completion rate: {completed_count / len(students_df) * 100:.1f}%\n"

        summary_text += f"\n📊 Statistical Summary:\n"
        if len(age_data) > 0:
            summary_text += f"Average age: {age_data.mean():.1f} (±{age_data.std():.1f})\n"
        else:
            summary_text += "Average age: N/A (no data)\n"
        if len(gpa_data) > 0:
            summary_text += f"Average GPA: {gpa_data.mean():.2f} (±{gpa_data.std():.2f})\n"
        else:
            summary_text += "Average GPA: N/A (no data)\n"
        if len(engagement_data) > 0:
            summary_text += f"Average engagement: {engagement_data.mean():.1f} (±{engagement_data.std():.1f})\n"
        else:
            summary_text += "Average engagement: N/A (no data)\n"

        summary_text += f"\n🎯 Top Performing Segments:\n"
        if len(gpa_data) > 0:
            high_performers = students_df[students_df['gpa'] >= 3.5]
            if not high_performers.empty:
                summary_text += f"High performers (GPA ≥ 3.5): {len(high_performers)} ({len(high_performers)/len(students_df)*100:.1f}%)\n"
                course_mode = high_performers['course'].dropna().mode()
                if len(course_mode) > 0:
                    summary_text += f"Most common course among high performers: {course_mode.iloc[0]}\n"
            summary_text += f"Average age of high performers: {high_performers['age'].mean():.1f}\n"

        # In GUI mode, return data for the GUI to display
        if self.gui_mode:
            return {
                'figure': fig,
                'summary': summary_text,
                'title': 'Enhanced Student Demographics Analysis'
            }

        # In CLI mode, print and handle display
        print(summary_text)
        self.save_or_display_plot(fig, "enhanced_student_demographics")

    def analyze_grade_distribution(self):
        """Analyze grade distributions across modules and courses"""
        students_df = self.get_all_students(self.custom_filters)
        modules_df = self.get_all_modules(self.custom_filters)
        
        if students_df.empty or modules_df.empty:
            print("Insufficient data for grade analysis.")
            return
        
        # Clean data and handle NaN values
        students_df = students_df.dropna(subset=['overall_grade', 'gpa'])
        modules_df = modules_df.dropna(subset=['module_grade'])
        
        print("\nGenerating Grade Distribution Analysis...")
        
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Grade Distribution Analysis', fontsize=20)
        
        # 1. Overall Grade Distribution
        ax1 = fig.add_subplot(331)
        grade_counts = students_df['overall_grade'].value_counts().reindex(['A', 'B', 'C', 'D', 'F'], fill_value=0)
        ax1.bar(grade_counts.index, grade_counts.values, color=CONFIG['colors'])
        ax1.set_xlabel('Grade')
        ax1.set_ylabel('Number of Students')
        ax1.set_title('Overall Grade Distribution')
        
        # Add percentage labels with null check
        total_students = len(students_df)
        if total_students > 0:
            for i, v in enumerate(grade_counts.values):
                if v > 0:  # Only add labels for non-zero values
                    percentage = v / total_students * 100
                    if not (np.isnan(percentage) or np.isinf(percentage)):
                        ax1.text(i, v + 0.5, f'{percentage:.1f}%', ha='center')
        
        # 2. GPA by Course
        ax2 = fig.add_subplot(332)
        course_gpa = students_df.groupby('course')['gpa'].mean().dropna()
        if not course_gpa.empty:
            ax2.bar(course_gpa.index, course_gpa.values, color=CONFIG['colors'])
            ax2.set_xlabel('Course')
            ax2.set_ylabel('Average GPA')
            ax2.set_title('Average GPA by Course')
        else:
            ax2.text(0.5, 0.5, 'No valid GPA data', ha='center', va='center', transform=ax2.transAxes)
            ax2.set_title('Average GPA by Course (No Data)')
        
        # 3. Grade Distribution by Gender
        ax3 = fig.add_subplot(333)
        if 'gender' in students_df.columns and not students_df['gender'].isna().all():
            grade_gender = pd.crosstab(students_df['gender'], students_df['overall_grade'])
            if not grade_gender.empty:
                grade_gender.plot(kind='bar', ax=ax3, color=CONFIG['colors'])
                ax3.set_xlabel('Gender')
                ax3.set_ylabel('Number of Students')
                ax3.set_title('Grade Distribution by Gender')
                ax3.legend(title='Grade')
                plt.setp(ax3.xaxis.get_majorticklabels(), rotation=0)
            else:
                ax3.text(0.5, 0.5, 'No gender data', ha='center', va='center', transform=ax3.transAxes)
        else:
            ax3.text(0.5, 0.5, 'Gender column not available', ha='center', va='center', transform=ax3.transAxes)
            ax3.set_title('Grade Distribution by Gender (No Data)')
        
        # 4. Module Grade Distribution
        ax4 = fig.add_subplot(334)
        module_grades = modules_df['module_grade'].value_counts().reindex(['A', 'B', 'C', 'D', 'F'], fill_value=0)
        ax4.bar(module_grades.index, module_grades.values, color=CONFIG['colors'])
        ax4.set_xlabel('Module Grade')
        ax4.set_ylabel('Number of Module Enrollments')
        ax4.set_title('Module Grade Distribution')
        
        # 5. GPA Distribution by Age Group
        ax5 = fig.add_subplot(335)
        if 'age' in students_df.columns and not students_df['age'].isna().all():
            students_df['age_group'] = pd.cut(students_df['age'], bins=[0, 25, 35, 45, 100], 
                                             labels=['18-25', '26-35', '36-45', '46+'])
            age_gpa = students_df.groupby('age_group')['gpa'].mean().dropna()
            if not age_gpa.empty:
                ax5.bar(age_gpa.index, age_gpa.values, color=CONFIG['colors'])
                ax5.set_xlabel('Age Group')
                ax5.set_ylabel('Average GPA')
                ax5.set_title('Average GPA by Age Group')
            else:
                ax5.text(0.5, 0.5, 'No valid age/GPA data', ha='center', va='center', transform=ax5.transAxes)
        else:
            ax5.text(0.5, 0.5, 'Age column not available', ha='center', va='center', transform=ax5.transAxes)
            ax5.set_title('Average GPA by Age Group (No Data)')
        
        # 6. Pass/Fail Rate by Course
        ax6 = fig.add_subplot(336)
        students_df['pass_fail'] = students_df['overall_grade'].apply(lambda x: 'Pass' if x != 'F' else 'Fail')
        pass_rate = students_df.groupby('course')['pass_fail'].apply(lambda x: (x == 'Pass').mean() * 100)
        pass_rate = pass_rate.dropna()
        if not pass_rate.empty:
            ax6.bar(pass_rate.index, pass_rate.values, color=CONFIG['colors'])
            ax6.set_xlabel('Course')
            ax6.set_ylabel('Pass Rate (%)')
            ax6.set_title('Pass Rate by Course')
            ax6.set_ylim(0, 100)
        else:
            ax6.text(0.5, 0.5, 'No valid course data', ha='center', va='center', transform=ax6.transAxes)
            ax6.set_title('Pass Rate by Course (No Data)')
        
        # 7. GPA vs Engagement Correlation
        ax7 = fig.add_subplot(337)
        if 'engagement_score' in students_df.columns and not students_df['engagement_score'].isna().all():
            valid_data = students_df.dropna(subset=['engagement_score', 'gpa', 'age'])
            if len(valid_data) > 0:
                scatter = ax7.scatter(valid_data['engagement_score'], valid_data['gpa'], 
                                     c=valid_data['age'], cmap='viridis', alpha=0.6)
                ax7.set_xlabel('Engagement Score')
                ax7.set_ylabel('GPA')
                ax7.set_title('GPA vs Engagement (colored by Age)')
                plt.colorbar(scatter, ax=ax7, label='Age')
                
                # Add correlation coefficient with null check
                correlation = valid_data['engagement_score'].corr(valid_data['gpa'])
                if not (np.isnan(correlation) or np.isinf(correlation)):
                    ax7.text(0.05, 0.95, f'Correlation: {correlation:.3f}', transform=ax7.transAxes, 
                            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
            else:
                ax7.text(0.5, 0.5, 'No valid engagement data', ha='center', va='center', transform=ax7.transAxes)
        else:
            ax7.text(0.5, 0.5, 'Engagement score not available', ha='center', va='center', transform=ax7.transAxes)
            ax7.set_title('GPA vs Engagement (No Data)')
        
        # 8. Top Performing Modules
        ax8 = fig.add_subplot(338)
        if 'module_name' in modules_df.columns:
            module_avg_grades = modules_df.groupby('module_name')['module_grade'].apply(
                lambda x: (x.isin(['A', 'B'])).mean() * 100
            ).dropna().sort_values(ascending=False).head(10)
            
            if not module_avg_grades.empty:
                ax8.barh(range(len(module_avg_grades)), module_avg_grades.values, color=CONFIG['colors'][0])
                ax8.set_yticks(range(len(module_avg_grades)))
                ax8.set_yticklabels(module_avg_grades.index)
                ax8.set_xlabel('% Students with A or B')
                ax8.set_title('Top Performing Modules')
            else:
                ax8.text(0.5, 0.5, 'No valid module data', ha='center', va='center', transform=ax8.transAxes)
                ax8.set_title('Top Performing Modules (No Data)')
        else:
            ax8.text(0.5, 0.5, 'Module name not available', ha='center', va='center', transform=ax8.transAxes)
            ax8.set_title('Top Performing Modules (No Data)')
        
        # 9. Grade Trend Analysis
        ax9 = fig.add_subplot(339)
        if 'registration_datetime' in students_df.columns and not students_df['registration_datetime'].isna().all():
            try:
                students_df['registration_month'] = pd.to_datetime(students_df['registration_datetime']).dt.to_period('M')
                monthly_gpa = students_df.groupby('registration_month')['gpa'].mean().dropna()
                
                if len(monthly_gpa) > 0:
                    ax9.plot(range(len(monthly_gpa)), monthly_gpa.values, marker='o', color=CONFIG['colors'][0])
                    ax9.set_xlabel('Registration Period')
                    ax9.set_ylabel('Average GPA')
                    ax9.set_title('GPA Trend Over Time')
                    
                    # Set x-axis labels with proper spacing
                    if len(monthly_gpa) > 5:
                        step = max(1, len(monthly_gpa) // 5)
                        tick_positions = range(0, len(monthly_gpa), step)
                        ax9.set_xticks(tick_positions)
                        ax9.set_xticklabels([str(monthly_gpa.index[i]) for i in tick_positions], rotation=45)
                    else:
                        ax9.set_xticks(range(len(monthly_gpa)))
                        ax9.set_xticklabels([str(idx) for idx in monthly_gpa.index], rotation=45)
                else:
                    ax9.text(0.5, 0.5, 'No valid time series data', ha='center', va='center', transform=ax9.transAxes)
            except Exception as e:
                ax9.text(0.5, 0.5, f'Error processing dates: {str(e)}', ha='center', va='center', transform=ax9.transAxes)
                ax9.set_title('GPA Trend Over Time (Error)')
        else:
            ax9.text(0.5, 0.5, 'Registration datetime not available', ha='center', va='center', transform=ax9.transAxes)
            ax9.set_title('GPA Trend Over Time (No Data)')
        
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        
        # Build detailed statistics with null checks
        summary_text = "\n" + "="*60 + "\n"
        summary_text += "GRADE DISTRIBUTION SUMMARY\n"
        summary_text += "="*60 + "\n"

        if len(students_df) > 0:
            avg_gpa = students_df['gpa'].mean()
            median_gpa = students_df['gpa'].median()
            std_gpa = students_df['gpa'].std()
            pass_rate = (students_df['overall_grade'] != 'F').mean() * 100

            summary_text += f"Overall Statistics:\n"
            summary_text += f"  Average GPA: {avg_gpa:.2f}\n" if not np.isnan(avg_gpa) else "  Average GPA: N/A\n"
            summary_text += f"  Median GPA: {median_gpa:.2f}\n" if not np.isnan(median_gpa) else "  Median GPA: N/A\n"
            summary_text += f"  GPA Standard Deviation: {std_gpa:.2f}\n" if not np.isnan(std_gpa) else "  GPA Standard Deviation: N/A\n"
            summary_text += f"  Pass Rate: {pass_rate:.1f}%\n" if not np.isnan(pass_rate) else "  Pass Rate: N/A\n"

            summary_text += f"\nGrade Distribution:\n"
            for grade in ['A', 'B', 'C', 'D', 'F']:
                count = (students_df['overall_grade'] == grade).sum()
                percentage = count / len(students_df) * 100 if len(students_df) > 0 else 0
                summary_text += f"  {grade}: {count} students ({percentage:.1f}%)\n"

            summary_text += f"\nCourse Performance:\n"
            for course in students_df['course'].unique():
                if pd.notna(course):
                    course_data = students_df[students_df['course'] == course]
                    avg_gpa = course_data['gpa'].mean()
                    pass_rate = (course_data['overall_grade'] != 'F').mean() * 100

                    gpa_str = f"{avg_gpa:.2f}" if not np.isnan(avg_gpa) else "N/A"
                    pass_str = f"{pass_rate:.1f}%" if not np.isnan(pass_rate) else "N/A"
                    summary_text += f"  {course}: Avg GPA {gpa_str}, Pass Rate {pass_str}\n"
        else:
            summary_text += "No valid student data available for analysis.\n"

        # In GUI mode, return data for the GUI to display
        if self.gui_mode:
            return {
                'figure': fig,
                'summary': summary_text,
                'title': 'Grade Distribution Analysis'
            }

        # In CLI mode, print and handle display
        print(summary_text)
        self.save_or_display_plot(fig, "grade_distribution_analysis")
    
    def analyze_course_enrollments(self):
        """Analyze course enrollment patterns and statistics"""
        students_df = self.get_all_students(self.custom_filters)
        
        if students_df.empty:
            print("No student data available for course enrollment analysis.")
            return
        
        print("\nGenerating Course Enrollment Analysis...")
        
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Course Enrollment Analysis', fontsize=20)
        
        # 1. Course Enrollment Distribution
        ax1 = fig.add_subplot(331)
        course_counts = students_df['course'].value_counts()
        ax1.pie(course_counts.values, labels=course_counts.index, autopct='%1.1f%%', 
               startangle=90, colors=CONFIG['colors'])
        ax1.set_title('Course Enrollment Distribution')
        
        # 2. Course Enrollment Trends Over Time
        ax2 = fig.add_subplot(332)
        if 'registration_datetime' in students_df.columns:
            students_df['reg_month'] = pd.to_datetime(students_df['registration_datetime']).dt.to_period('M')
            course_timeline = students_df.groupby(['reg_month', 'course']).size().unstack(fill_value=0)
            
            for course in course_timeline.columns:
                ax2.plot(range(len(course_timeline)), course_timeline[course], 
                        marker='o', label=course, linewidth=2)
            
            ax2.set_xlabel('Time Period')
            ax2.set_ylabel('Number of Enrollments')
            ax2.set_title('Course Enrollment Trends')
            ax2.legend()
            ax2.set_xticks(range(0, len(course_timeline), max(1, len(course_timeline)//5)))
            ax2.set_xticklabels([str(course_timeline.index[i]) for i in range(0, len(course_timeline), max(1, len(course_timeline)//5))], rotation=45)
        
        # 3. Course Performance Comparison
        ax3 = fig.add_subplot(333)
        course_stats = students_df.groupby('course').agg({
            'gpa': 'mean',
            'engagement_score': 'mean',
            'student_id': 'count'
        })
        
        x = range(len(course_stats))
        width = 0.35
        ax3.bar([i - width/2 for i in x], course_stats['gpa'], width, 
               label='Avg GPA', color=CONFIG['colors'][0])
        ax3_twin = ax3.twinx()
        ax3_twin.bar([i + width/2 for i in x], course_stats['engagement_score'], width, 
                    label='Avg Engagement', color=CONFIG['colors'][1], alpha=0.7)
        
        ax3.set_xlabel('Course')
        ax3.set_ylabel('Average GPA')
        ax3_twin.set_ylabel('Average Engagement Score')
        ax3.set_title('Course Performance Metrics')
        ax3.set_xticks(x)
        ax3.set_xticklabels(course_stats.index)
        ax3.legend(loc='upper left')
        ax3_twin.legend(loc='upper right')
        
        # 4. Age Distribution by Course
        ax4 = fig.add_subplot(334)
        age_data = students_df['age'].dropna()
        if len(age_data) > 0:
            for course in students_df['course'].dropna().unique():
                course_ages = students_df[students_df['course'] == course]['age'].dropna()
                if len(course_ages) > 0:
                    ax4.hist(course_ages, alpha=0.7, label=course, bins=15)
            ax4.legend()
        else:
            ax4.text(0.5, 0.5, 'No age data available', ha='center', va='center', transform=ax4.transAxes)
        ax4.set_xlabel('Age')
        ax4.set_ylabel('Number of Students')
        ax4.set_title('Age Distribution by Course')

        # 5. Gender Distribution by Course
        ax5 = fig.add_subplot(335)
        gender_data = students_df['gender'].dropna()
        course_data = students_df['course'].dropna()
        if len(gender_data) > 0 and len(course_data) > 0:
            gender_course = pd.crosstab(students_df['course'].fillna('Unknown'), students_df['gender'].fillna('Unknown'))
            gender_course.plot(kind='bar', ax=ax5, color=CONFIG['colors'])
            ax5.legend(title='Gender')
        else:
            ax5.text(0.5, 0.5, 'Insufficient data', ha='center', va='center', transform=ax5.transAxes)
        ax5.set_xlabel('Course')
        ax5.set_ylabel('Number of Students')
        ax5.set_title('Gender Distribution by Course')
        ax5.tick_params(axis='x', rotation=45)

        # 6. Course Completion Rates
        ax6 = fig.add_subplot(336)
        if 'completion_status' in students_df.columns:
            completion_rates = students_df.groupby('course').apply(
                lambda x: (x['completion_status'] == 'Completed').mean() * 100
            ).dropna()
            if not completion_rates.empty:
                ax6.bar(completion_rates.index, completion_rates.values, color='green', alpha=0.7)
            else:
                ax6.text(0.5, 0.5, 'No completion data', ha='center', va='center', transform=ax6.transAxes)
        else:
            ax6.text(0.5, 0.5, 'No completion data available', ha='center', va='center', transform=ax6.transAxes)
        ax6.set_xlabel('Course')
        ax6.set_ylabel('Completion Rate (%)')
        ax6.set_title('Course Completion Rates')

        # 7. Course Capacity Analysis
        ax7 = fig.add_subplot(337)
        enrollment_counts = students_df['course'].dropna().value_counts()
        if not enrollment_counts.empty:
            avg_enrollment = enrollment_counts.mean()
            bar_colors = ['red' if count < avg_enrollment * 0.7 else 'orange' if count < avg_enrollment else 'green'
                     for count in enrollment_counts.values]
            ax7.bar(enrollment_counts.index, enrollment_counts.values, color=bar_colors, alpha=0.7)
            ax7.axhline(y=avg_enrollment, color='blue', linestyle='--', label=f'Average: {avg_enrollment:.1f}')
            ax7.legend()
        else:
            ax7.text(0.5, 0.5, 'No enrollment data', ha='center', va='center', transform=ax7.transAxes)
        ax7.set_xlabel('Course')
        ax7.set_ylabel('Number of Students')
        ax7.set_title('Course Enrollment vs Average')

        # 8. Course Satisfaction (Engagement) Heatmap
        ax8 = fig.add_subplot(338)
        if 'engagement_score' in students_df.columns and len(age_data) > 0:
            try:
                engagement_by_course_age = students_df.dropna(subset=['age', 'course', 'engagement_score']).groupby(
                    ['course', pd.cut(students_df.dropna(subset=['age'])['age'], bins=[0, 25, 35, 45, 100],
                    labels=['18-25', '26-35', '36-45', '46+'])])['engagement_score'].mean().unstack()
            except (ValueError, KeyError):
                engagement_by_course_age = pd.DataFrame()
        else:
            engagement_by_course_age = pd.DataFrame()

        if not engagement_by_course_age.empty and engagement_by_course_age.values.size > 0:
            im = ax8.imshow(engagement_by_course_age.values, cmap='RdYlGn', aspect='auto')
            ax8.set_xticks(range(len(engagement_by_course_age.columns)))
            ax8.set_yticks(range(len(engagement_by_course_age.index)))
            ax8.set_xticklabels(engagement_by_course_age.columns)
            ax8.set_yticklabels(engagement_by_course_age.index)
            plt.colorbar(im, ax=ax8)
        else:
            ax8.text(0.5, 0.5, 'Insufficient data for heatmap', ha='center', va='center', transform=ax8.transAxes)
        ax8.set_xlabel('Age Group')
        ax8.set_ylabel('Course')
        ax8.set_title('Average Engagement by Course and Age')
        
        # 9. Course Enrollment Forecast
        ax9 = fig.add_subplot(339)
        if 'registration_datetime' in students_df.columns:
            monthly_total = students_df.groupby('reg_month').size()
            
            if len(monthly_total) > 3:
                # Simple linear forecast
                x_data = range(len(monthly_total))
                y_data = monthly_total.values
                
                z = np.polyfit(x_data, y_data, 1)
                p = np.poly1d(z)
                
                # Forecast next 6 months
                future_months = range(len(monthly_total), len(monthly_total) + 6)
                forecast = [p(month) for month in future_months]
                
                ax9.plot(x_data, y_data, 'o-', label='Historical', color=CONFIG['colors'][0])
                ax9.plot(future_months, forecast, 's--', label='Forecast', color='red')
                ax9.set_xlabel('Time Period')
                ax9.set_ylabel('Total Enrollments')
                ax9.set_title('Enrollment Forecast (Next 6 Months)')
                ax9.legend()
        
        plt.tight_layout(rect=[0, 0, 1, 0.95])

        # Build detailed course enrollment summary
        summary_text = "\n" + "="*60 + "\n"
        summary_text += "COURSE ENROLLMENT ANALYSIS SUMMARY\n"
        summary_text += "="*60 + "\n"

        num_courses = students_df['course'].nunique()
        summary_text += f"Total courses offered: {num_courses}\n"
        summary_text += f"Total enrolled students: {len(students_df)}\n"
        avg_per_course = len(students_df) / num_courses if num_courses > 0 else 0
        summary_text += f"Average students per course: {avg_per_course:.1f}\n"

        summary_text += f"\nCourse Enrollment Breakdown:\n"
        for course, count in course_counts.items():
            percentage = count / len(students_df) * 100
            avg_gpa = students_df[students_df['course'] == course]['gpa'].mean()
            completion_rate = (students_df[students_df['course'] == course]['completion_status'] == 'Completed').mean() * 100
            summary_text += f"  {course}: {count} students ({percentage:.1f}%), Avg GPA: {avg_gpa:.2f}, Completion: {completion_rate:.1f}%\n"

        summary_text += f"\nTop Performing Courses (by GPA):\n"
        top_courses_gpa = course_stats.nlargest(3, 'gpa')
        for course, stats in top_courses_gpa.iterrows():
            summary_text += f"  {course}: GPA {stats['gpa']:.2f}, {stats['student_id']} students\n"

        summary_text += f"\nMost Popular Courses:\n"
        for i, (course, count) in enumerate(course_counts.head(3).items()):
            summary_text += f"  {i+1}. {course}: {count} students\n"

        # In GUI mode, return data for the GUI to display
        if self.gui_mode:
            return {
                'figure': fig,
                'summary': summary_text,
                'title': 'Course Enrollment Analysis'
            }

        # In CLI mode, print and handle display
        print(summary_text)
        self.save_or_display_plot(fig, "course_enrollment_analysis")

    def analyze_registration_timeline(self):
        """Analyze student registration patterns over time"""
        students_df = self.get_all_students(self.custom_filters)
        
        if students_df.empty:
            print("No student data available for registration timeline analysis.")
            return
        
        print("\nGenerating Registration Timeline Analysis...")
        
        # Convert registration datetime
        students_df['registration_date'] = pd.to_datetime(students_df['registration_datetime'])
        students_df['reg_year'] = students_df['registration_date'].dt.year
        students_df['reg_month'] = students_df['registration_date'].dt.month
        students_df['reg_day_of_week'] = students_df['registration_date'].dt.day_name()
        students_df['reg_hour'] = students_df['registration_date'].dt.hour
        
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Student Registration Timeline Analysis', fontsize=20)
        
        # 1. Registrations Over Time
        ax1 = fig.add_subplot(331)
        monthly_registrations = students_df.groupby(students_df['registration_date'].dt.to_period('M')).size()
        ax1.plot(range(len(monthly_registrations)), monthly_registrations.values, 
                marker='o', color=CONFIG['colors'][0], linewidth=2)
        ax1.set_xlabel('Time Period')
        ax1.set_ylabel('Number of Registrations')
        ax1.set_title('Registration Trends Over Time')
        ax1.set_xticks(range(0, len(monthly_registrations), max(1, len(monthly_registrations)//5)))
        ax1.set_xticklabels([str(monthly_registrations.index[i]) for i in range(0, len(monthly_registrations), max(1, len(monthly_registrations)//5))], rotation=45)
        
        # 2. Seasonal Registration Patterns
        ax2 = fig.add_subplot(332)
        monthly_pattern = students_df.groupby('reg_month').size()
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        month_labels = [months[i-1] for i in monthly_pattern.index]
        
        ax2.bar(month_labels, monthly_pattern.values, color=CONFIG['colors'][1])
        ax2.set_xlabel('Month')
        ax2.set_ylabel('Number of Registrations')
        ax2.set_title('Seasonal Registration Patterns')
        plt.xticks(rotation=45)
        
        # 3. Day of Week Registration Patterns
        ax3 = fig.add_subplot(333)
        day_pattern = students_df['reg_day_of_week'].value_counts()
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_pattern = day_pattern.reindex(day_order, fill_value=0)
        
        ax3.bar(day_pattern.index, day_pattern.values, color=CONFIG['colors'][2])
        ax3.set_xlabel('Day of Week')
        ax3.set_ylabel('Number of Registrations')
        ax3.set_title('Registration by Day of Week')
        plt.xticks(rotation=45)
        
        # 4. Hourly Registration Patterns
        ax4 = fig.add_subplot(334)
        hourly_pattern = students_df.groupby('reg_hour').size()
        ax4.bar(hourly_pattern.index, hourly_pattern.values, color=CONFIG['colors'][3])
        ax4.set_xlabel('Hour of Day')
        ax4.set_ylabel('Number of Registrations')
        ax4.set_title('Registration by Hour of Day')
        
        # 5. Registration Growth Rate
        ax5 = fig.add_subplot(335)
        cumulative_registrations = monthly_registrations.cumsum()
        ax5.plot(range(len(cumulative_registrations)), cumulative_registrations.values, 
                marker='s', color='green', linewidth=2)
        ax5.set_xlabel('Time Period')
        ax5.set_ylabel('Cumulative Registrations')
        ax5.set_title('Cumulative Registration Growth')
        
        # 6. Course Registration Timeline
        ax6 = fig.add_subplot(336)
        course_timeline = students_df.groupby([students_df['registration_date'].dt.to_period('M'), 'course']).size().unstack(fill_value=0)
        
        for course in course_timeline.columns:
            ax6.plot(range(len(course_timeline)), course_timeline[course], 
                    marker='o', label=course, linewidth=2)
        
        ax6.set_xlabel('Time Period')
        ax6.set_ylabel('Number of Registrations')
        ax6.set_title('Course Registration Timeline')
        ax6.legend()
        
        # 7. Registration Volume Heatmap
        ax7 = fig.add_subplot(337)
        students_df['reg_week'] = students_df['registration_date'].dt.isocalendar().week
        week_hour_heatmap = students_df.groupby(['reg_week', 'reg_hour']).size().unstack(fill_value=0)
        
        if len(week_hour_heatmap) > 1:
            im = ax7.imshow(week_hour_heatmap.values, cmap='YlOrRd', aspect='auto')
            ax7.set_xlabel('Hour of Day')
            ax7.set_ylabel('Week of Year')
            ax7.set_title('Registration Volume Heatmap')
            plt.colorbar(im, ax=ax7)
        
        # 8. Peak Registration Periods
        ax8 = fig.add_subplot(338)
        peak_periods = monthly_registrations.nlargest(10)
        ax8.bar(range(len(peak_periods)), peak_periods.values, color='red', alpha=0.7)
        ax8.set_xticks(range(len(peak_periods)))
        ax8.set_xticklabels([str(period) for period in peak_periods.index], rotation=45, ha='right')
        ax8.set_xlabel('Period')
        ax8.set_ylabel('Number of Registrations')
        ax8.set_title('Top 10 Peak Registration Periods')
        
        # 9. Registration Forecast
        ax9 = fig.add_subplot(339)
        if len(monthly_registrations) > 3:
            # Simple moving average forecast
            window = min(3, len(monthly_registrations))
            moving_avg = monthly_registrations.rolling(window=window).mean()
            
            # Simple trend extrapolation
            recent_trend = monthly_registrations.tail(3).mean()
            forecast_periods = 6
            forecast_values = [recent_trend] * forecast_periods
            
            ax9.plot(range(len(monthly_registrations)), monthly_registrations.values, 
                    'o-', label='Actual', color=CONFIG['colors'][0])
            ax9.plot(range(len(monthly_registrations), len(monthly_registrations) + forecast_periods), 
                    forecast_values, 's--', label='Forecast', color='red')
            ax9.set_xlabel('Time Period')
            ax9.set_ylabel('Number of Registrations')
            ax9.set_title('Registration Forecast (Next 6 Months)')
            ax9.legend()
        
        plt.tight_layout(rect=[0, 0, 1, 0.95])

        # Build detailed registration timeline summary
        summary_text = "\n" + "="*60 + "\n"
        summary_text += "REGISTRATION TIMELINE ANALYSIS SUMMARY\n"
        summary_text += "="*60 + "\n"

        min_date = students_df['registration_date'].min()
        max_date = students_df['registration_date'].max()
        if pd.notna(min_date) and pd.notna(max_date):
            summary_text += f"Analysis period: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}\n"
        else:
            summary_text += f"Analysis period: No valid date range available\n"
        summary_text += f"Total registrations: {len(students_df)}\n"
        summary_text += f"Average registrations per month: {monthly_registrations.mean():.1f}\n"

        summary_text += f"\nPeak Registration Periods:\n"
        for period, count in peak_periods.head(3).items():
            summary_text += f"  {period}: {count} registrations\n"

        summary_text += f"\nSeasonal Patterns:\n"
        peak_month = monthly_pattern.idxmax()
        low_month = monthly_pattern.idxmin()
        summary_text += f"  Peak month: {months[peak_month-1]} ({monthly_pattern[peak_month]} registrations)\n"
        summary_text += f"  Lowest month: {months[low_month-1]} ({monthly_pattern[low_month]} registrations)\n"

        summary_text += f"\nDaily Patterns:\n"
        peak_day = day_pattern.idxmax()
        low_day = day_pattern.idxmin()
        summary_text += f"  Most popular day: {peak_day} ({day_pattern[peak_day]} registrations)\n"
        summary_text += f"  Least popular day: {low_day} ({day_pattern[low_day]} registrations)\n"

        if len(hourly_pattern) > 0:
            peak_hour = hourly_pattern.idxmax()
            summary_text += f"  Peak hour: {peak_hour}:00 ({hourly_pattern[peak_hour]} registrations)\n"

        summary_text += f"\nGrowth Analysis:\n"
        if len(monthly_registrations) > 1:
            recent_growth = ((monthly_registrations.iloc[-1] - monthly_registrations.iloc[-2]) / monthly_registrations.iloc[-2] * 100)
            summary_text += f"  Month-over-month growth: {recent_growth:+.1f}%\n"

        total_growth = ((monthly_registrations.iloc[-1] - monthly_registrations.iloc[0]) / len(monthly_registrations))
        summary_text += f"  Average monthly growth: {total_growth:.1f} registrations\n"

        # In GUI mode, return data for the GUI to display
        if self.gui_mode:
            return {
                'figure': fig,
                'summary': summary_text,
                'title': 'Registration Timeline Analysis'
            }

        # In CLI mode, print and handle display
        print(summary_text)
        self.save_or_display_plot(fig, "registration_timeline_analysis")

    def analyze_academic_risk(self):
        """Analyze students at academic risk"""
        students_df = self.get_all_students(self.custom_filters)
        modules_df = self.get_all_modules(self.custom_filters)
        
        if students_df.empty:
            print("No student data available for risk analysis.")
            return
        
        # Clean data and handle missing values
        students_df = students_df.dropna(subset=['gpa'])
        
        if students_df.empty:
            print("No valid GPA data available for risk analysis.")
            return
        
        print("\nGenerating Academic Risk Assessment...")
        
        # Define risk factors with null checks
        students_df['low_gpa'] = students_df['gpa'] < 2.0
        
        # Handle engagement score - use 0 if missing
        if 'engagement_score' in students_df.columns:
            students_df['engagement_score'] = students_df['engagement_score'].fillna(0)
            students_df['low_engagement'] = students_df['engagement_score'] < 30
        else:
            students_df['engagement_score'] = 0
            students_df['low_engagement'] = False
        
        students_df['at_risk'] = students_df['low_gpa'] | students_df['low_engagement']
        
        # Create age groups if age column exists
        if 'age' in students_df.columns and not students_df['age'].isna().all():
            students_df['age_group'] = pd.cut(students_df['age'], bins=[0, 25, 35, 45, 100], 
                                             labels=['18-25', '26-35', '36-45', '46+'])
        else:
            students_df['age_group'] = 'Unknown'
        
        # Calculate module-specific risks
        if not modules_df.empty and 'student_id' in modules_df.columns:
            try:
                module_risk = modules_df.groupby('student_id').agg({
                    'module_grade': lambda x: (x == 'F').sum() if 'module_grade' in modules_df.columns else 0,
                    'attendance_rate': 'mean' if 'attendance_rate' in modules_df.columns else lambda x: 100,
                    'module_completion': lambda x: (x == 'Failed').sum() if 'module_completion' in modules_df.columns else 0
                }).reset_index()
                
                module_risk['failing_modules'] = module_risk['module_grade'] > 0
                module_risk['low_attendance'] = module_risk['attendance_rate'] < 70
                
                # Merge with student data
                students_df = students_df.merge(module_risk, on='student_id', how='left')
                students_df['failing_modules'] = students_df['failing_modules'].fillna(False)
                students_df['low_attendance'] = students_df['low_attendance'].fillna(False)
            except Exception as e:
                print(f"Warning: Could not process module data: {e}")
                students_df['failing_modules'] = False
                students_df['low_attendance'] = False
        else:
            students_df['failing_modules'] = False
            students_df['low_attendance'] = False
        
        # Handle registration month for trend analysis
        if 'registration_datetime' in students_df.columns:
            try:
                students_df['registration_date'] = pd.to_datetime(students_df['registration_datetime'])
                students_df['registration_month'] = students_df['registration_date'].dt.to_period('M')
            except (ValueError, TypeError, KeyError):
                students_df['registration_month'] = None
        else:
            students_df['registration_month'] = None
        
        fig = plt.figure(figsize=(20, 12))
        fig.suptitle('Academic Risk Assessment Dashboard', fontsize=20)
        
        # 1. Risk Factor Distribution
        ax1 = fig.add_subplot(331)
        risk_factors = ['low_gpa', 'low_engagement', 'at_risk']
        if not modules_df.empty:
            risk_factors.extend(['failing_modules', 'low_attendance'])
        
        risk_counts = [students_df[factor].sum() for factor in risk_factors]
        risk_labels = ['Low GPA\n(<2.0)', 'Low Engagement\n(<30)', 'Overall\nAt Risk', 
                      'Failing\nModules', 'Low Attendance\n(<70%)'][:len(risk_factors)]
        
        bars = ax1.bar(risk_labels, risk_counts, color=['red' if count > len(students_df)*0.2 else 'orange' 
                                                       for count in risk_counts])
        ax1.set_ylabel('Number of Students')
        ax1.set_title('Risk Factor Distribution')
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Add percentage labels with finite check
        for bar, count in zip(bars, risk_counts):
            if len(students_df) > 0:
                percentage = count / len(students_df) * 100
                if not (np.isnan(percentage) or np.isinf(percentage)):
                    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, 
                            f'{percentage:.1f}%', ha='center', va='bottom')
        
        # 2. Risk by Course
        ax2 = fig.add_subplot(332)
        if 'course' in students_df.columns and not students_df['course'].isna().all():
            course_risk = students_df.groupby('course')['at_risk'].mean() * 100
            course_risk = course_risk.dropna()
            if not course_risk.empty:
                ax2.bar(course_risk.index, course_risk.values, color=CONFIG['colors'])
                ax2.set_xlabel('Course')
                ax2.set_ylabel('% Students at Risk')
                ax2.set_title('Risk Rate by Course')
            else:
                ax2.text(0.5, 0.5, 'No valid course data', ha='center', va='center', transform=ax2.transAxes)
        else:
            ax2.text(0.5, 0.5, 'Course data not available', ha='center', va='center', transform=ax2.transAxes)
            ax2.set_title('Risk Rate by Course (No Data)')
        
        # 3. Risk by Age Group
        ax3 = fig.add_subplot(333)
        if 'age' in students_df.columns and not students_df['age'].isna().all():
            age_risk = students_df.groupby('age_group')['at_risk'].mean() * 100
            age_risk = age_risk.dropna()
            if not age_risk.empty:
                ax3.bar(age_risk.index, age_risk.values, color=CONFIG['colors'])
                ax3.set_xlabel('Age Group')
                ax3.set_ylabel('% Students at Risk')
                ax3.set_title('Risk Rate by Age Group')
            else:
                ax3.text(0.5, 0.5, 'No valid age data', ha='center', va='center', transform=ax3.transAxes)
        else:
            ax3.text(0.5, 0.5, 'Age data not available', ha='center', va='center', transform=ax3.transAxes)
            ax3.set_title('Risk Rate by Age Group (No Data)')
        
        # 4. GPA Distribution for At-Risk Students
        ax4 = fig.add_subplot(334)
        at_risk_gpa = students_df[students_df['at_risk']]['gpa'].dropna()
        not_at_risk_gpa = students_df[~students_df['at_risk']]['gpa'].dropna()
        
        if len(at_risk_gpa) > 0 or len(not_at_risk_gpa) > 0:
            data_to_plot = []
            labels = []
            colors = []
            
            if len(not_at_risk_gpa) > 0:
                data_to_plot.append(not_at_risk_gpa)
                labels.append('Not at Risk')
                colors.append('green')
            
            if len(at_risk_gpa) > 0:
                data_to_plot.append(at_risk_gpa)
                labels.append('At Risk')
                colors.append('red')
            
            ax4.hist(data_to_plot, bins=20, alpha=0.7, label=labels, color=colors)
            ax4.set_xlabel('GPA')
            ax4.set_ylabel('Number of Students')
            ax4.set_title('GPA Distribution: At-Risk vs Not At-Risk')
            ax4.legend()
        else:
            ax4.text(0.5, 0.5, 'No valid GPA data for comparison', ha='center', va='center', transform=ax4.transAxes)
            ax4.set_title('GPA Distribution (No Data)')
        
        # 5. Engagement vs GPA Risk Matrix
        ax5 = fig.add_subplot(335)
        valid_data = students_df.dropna(subset=['engagement_score', 'gpa'])
        if len(valid_data) > 0:
            scatter = ax5.scatter(valid_data['engagement_score'], valid_data['gpa'], 
                                 c=valid_data['at_risk'], cmap='RdYlGn_r', alpha=0.7, s=50)
            ax5.set_xlabel('Engagement Score')
            ax5.set_ylabel('GPA')
            ax5.set_title('Risk Matrix: Engagement vs GPA')
            ax5.axhline(y=2.0, color='red', linestyle='--', alpha=0.5, label='GPA Risk Threshold')
            ax5.axvline(x=30, color='red', linestyle='--', alpha=0.5, label='Engagement Risk Threshold')
            ax5.legend()
        else:
            ax5.text(0.5, 0.5, 'No valid engagement/GPA data', ha='center', va='center', transform=ax5.transAxes)
            ax5.set_title('Risk Matrix (No Data)')
        
        # 6. Early Warning Indicators
        ax6 = fig.add_subplot(336)
        warning_indicators = {
            'Low GPA': students_df['low_gpa'].sum(),
            'Low Engagement': students_df['low_engagement'].sum()
        }
        
        # Add completion status indicators if available
        if 'completion_status' in students_df.columns:
            warning_indicators['Inactive Status'] = (students_df['completion_status'] == 'On Hold').sum()
            warning_indicators['Dropped'] = (students_df['completion_status'] == 'Dropped').sum()
        
        # Filter out zero values for pie chart
        warning_indicators = {k: v for k, v in warning_indicators.items() if v > 0}
        
        if warning_indicators:
            ax6.pie(warning_indicators.values(), labels=warning_indicators.keys(), 
                   autopct='%1.1f%%', startangle=90, colors=['red', 'orange', 'yellow', 'darkred'][:len(warning_indicators)])
            ax6.set_title('Early Warning Indicators')
        else:
            ax6.text(0.5, 0.5, 'No warning indicators detected', ha='center', va='center', transform=ax6.transAxes)
            ax6.set_title('Early Warning Indicators (None)')
        
        # 7. Risk Trend Analysis
        ax7 = fig.add_subplot(337)
        if 'registration_month' in students_df.columns and students_df['registration_month'].notna().any():
            try:
                monthly_risk = students_df.groupby('registration_month')['at_risk'].mean() * 100
                monthly_risk = monthly_risk.dropna()
                
                if len(monthly_risk) > 0:
                    ax7.plot(range(len(monthly_risk)), monthly_risk.values, marker='o', 
                            color='red', linewidth=2)
                    ax7.set_xlabel('Registration Period')
                    ax7.set_ylabel('% Students at Risk')
                    ax7.set_title('Risk Rate Trend Over Time')
                    
                    if len(monthly_risk) > 1:
                        step = max(1, len(monthly_risk) // 5)
                        tick_positions = list(range(0, len(monthly_risk), step))
                        if tick_positions[-1] != len(monthly_risk) - 1:
                            tick_positions.append(len(monthly_risk) - 1)
                        ax7.set_xticks(tick_positions)
                        ax7.set_xticklabels([str(monthly_risk.index[i]) for i in tick_positions], rotation=45)
                else:
                    ax7.text(0.5, 0.5, 'No valid trend data', ha='center', va='center', transform=ax7.transAxes)
            except Exception as e:
                ax7.text(0.5, 0.5, 'Error processing trend data', ha='center', va='center', transform=ax7.transAxes)
        else:
            ax7.text(0.5, 0.5, 'Registration date not available', ha='center', va='center', transform=ax7.transAxes)
            ax7.set_title('Risk Rate Trend Over Time (No Data)')
        
        # 8. Intervention Priority Matrix
        ax8 = fig.add_subplot(338)
        # Create priority levels based on multiple risk factors
        students_df['risk_score'] = (students_df['low_gpa'].astype(int) + 
                                   students_df['low_engagement'].astype(int))
        if not modules_df.empty:
            students_df['risk_score'] += (students_df['failing_modules'].astype(int) + 
                                        students_df['low_attendance'].astype(int))
        
        priority_counts = students_df['risk_score'].value_counts().sort_index()
        if not priority_counts.empty:
            priority_labels = [f'Level {i}' for i in priority_counts.index]
            colors = ['green', 'yellow', 'orange', 'red', 'darkred'][:len(priority_counts)]
            
            ax8.bar(priority_labels, priority_counts.values, color=colors)
            ax8.set_xlabel('Risk Level')
            ax8.set_ylabel('Number of Students')
            ax8.set_title('Intervention Priority Levels')
        else:
            ax8.text(0.5, 0.5, 'No risk level data', ha='center', va='center', transform=ax8.transAxes)
            ax8.set_title('Intervention Priority Levels (No Data)')
        
        # 9. Risk Factors Correlation Heatmap
        ax9 = fig.add_subplot(339)
        risk_cols = ['low_gpa', 'low_engagement', 'at_risk']
        if not modules_df.empty:
            risk_cols.extend(['failing_modules', 'low_attendance'])
        
        try:
            risk_corr = students_df[risk_cols].astype(int).corr()
            if not risk_corr.empty:
                im = ax9.imshow(risk_corr, cmap='RdBu_r', aspect='auto', vmin=-1, vmax=1)
                ax9.set_xticks(range(len(risk_cols)))
                ax9.set_yticks(range(len(risk_cols)))
                
                risk_labels_full = ['Low GPA', 'Low Engagement', 'At Risk', 'Failing Modules', 'Low Attendance'][:len(risk_cols)]
                ax9.set_xticklabels(risk_labels_full, rotation=45, ha='right')
                ax9.set_yticklabels(risk_labels_full)
                ax9.set_title('Risk Factors Correlation')
                plt.colorbar(im, ax=ax9)
            else:
                ax9.text(0.5, 0.5, 'No correlation data', ha='center', va='center', transform=ax9.transAxes)
        except Exception as e:
            ax9.text(0.5, 0.5, 'Error calculating correlations', ha='center', va='center', transform=ax9.transAxes)
            ax9.set_title('Risk Factors Correlation (Error)')
        
        plt.tight_layout(rect=[0, 0, 1, 0.95])

        # Build detailed risk assessment summary
        summary_text = "\n" + "="*60 + "\n"
        summary_text += "ACADEMIC RISK ASSESSMENT SUMMARY\n"
        summary_text += "="*60 + "\n"

        at_risk_count = students_df['at_risk'].sum()
        total_students = len(students_df)

        if total_students > 0:
            summary_text += f"Students at academic risk: {at_risk_count} ({at_risk_count/total_students*100:.1f}%)\n"

            summary_text += f"\nRisk Factor Breakdown:\n"
            summary_text += f"  Low GPA (<2.0): {students_df['low_gpa'].sum()} students\n"
            summary_text += f"  Low Engagement (<30): {students_df['low_engagement'].sum()} students\n"
            if not modules_df.empty:
                summary_text += f"  Failing Modules: {students_df['failing_modules'].sum()} students\n"
                summary_text += f"  Low Attendance (<70%): {students_df['low_attendance'].sum()} students\n"

            summary_text += f"\nHigh Priority Students (Multiple Risk Factors):\n"
            high_priority = students_df[students_df['risk_score'] >= 2]
            summary_text += f"  {len(high_priority)} students require immediate intervention\n"

            if len(high_priority) > 0:
                summary_text += f"\nTop Risk Indicators for High Priority Students:\n"
                avg_gpa = high_priority['gpa'].mean()
                avg_engagement = high_priority['engagement_score'].mean()
                summary_text += f"  Average GPA: {avg_gpa:.2f}\n" if not np.isnan(avg_gpa) else "  Average GPA: N/A\n"
                summary_text += f"  Average Engagement: {avg_engagement:.1f}\n" if not np.isnan(avg_engagement) else "  Average Engagement: N/A\n"

            summary_text += f"\nRecommended Actions:\n"
            summary_text += f"  - Contact {students_df['low_gpa'].sum()} students with academic support\n"
            summary_text += f"  - Implement engagement programs for {students_df['low_engagement'].sum()} students\n"
            summary_text += f"  - Prioritize intervention for {len(high_priority)} high-risk students\n"
        else:
            summary_text += "No student data available for risk assessment.\n"

        # In GUI mode, return data for the GUI to display
        if self.gui_mode:
            return {
                'figure': fig,
                'summary': summary_text,
                'title': 'Academic Risk Assessment'
            }

        # In CLI mode, print and handle display
        print(summary_text)
        self.save_or_display_plot(fig, "academic_risk_assessment")    

    def analyze_module_difficulty(self):
        """Analyze module difficulty and performance metrics"""
        modules_df = self.get_all_modules(self.custom_filters)
        
        if modules_df.empty:
            print("No module data available for difficulty analysis.")
            return
        
        print("\nGenerating Module Difficulty Analysis...")
        
        # Calculate difficulty metrics
        module_stats = modules_df.groupby('module_name').agg({
            'module_grade': lambda x: (x.isin(['A', 'B'])).mean() * 100,  # Pass rate
            'difficulty_rating': 'mean',
            'attendance_rate': 'mean',
            'module_completion': lambda x: (x == 'Completed').mean() * 100,
            'student_id': 'count'  # Enrollment count
        }).round(2)
        
        module_stats.columns = ['Pass_Rate', 'Avg_Difficulty', 'Avg_Attendance', 'Completion_Rate', 'Enrollment']
        
        # Calculate overall difficulty score
        module_stats['Difficulty_Score'] = (
            (5 - module_stats['Avg_Difficulty']) * 0.3 +  # Lower difficulty rating = higher score
            module_stats['Pass_Rate'] * 0.4 +  # Higher pass rate = higher score
            module_stats['Completion_Rate'] * 0.3  # Higher completion rate = higher score
        ) / 100 * 5  # Normalize to 1-5 scale
        
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Module Difficulty Analysis', fontsize=20)
        
        # 1. Module Difficulty vs Pass Rate
        ax1 = fig.add_subplot(331)
        scatter = ax1.scatter(module_stats['Avg_Difficulty'], module_stats['Pass_Rate'], 
                             s=module_stats['Enrollment']*10, alpha=0.6, c=module_stats['Completion_Rate'], 
                             cmap='RdYlBu_r')
        ax1.set_xlabel('Average Difficulty Rating')
        ax1.set_ylabel('Pass Rate (%)')
        ax1.set_title('Difficulty vs Pass Rate (sized by enrollment)')
        plt.colorbar(scatter, ax=ax1, label='Completion Rate (%)')
        
        # 2. Most Challenging Modules
        ax2 = fig.add_subplot(332)
        challenging = module_stats.nsmallest(10, 'Pass_Rate')
        ax2.barh(range(len(challenging)), challenging['Pass_Rate'], color='red', alpha=0.7)
        ax2.set_yticks(range(len(challenging)))
        ax2.set_yticklabels(challenging.index, fontsize=8)
        ax2.set_xlabel('Pass Rate (%)')
        ax2.set_title('Most Challenging Modules (Lowest Pass Rate)')
        
        # 3. Easiest Modules
        ax3 = fig.add_subplot(333)
        easiest = module_stats.nlargest(10, 'Pass_Rate')
        ax3.barh(range(len(easiest)), easiest['Pass_Rate'], color='green', alpha=0.7)
        ax3.set_yticks(range(len(easiest)))
        ax3.set_yticklabels(easiest.index, fontsize=8)
        ax3.set_xlabel('Pass Rate (%)')
        ax3.set_title('Easiest Modules (Highest Pass Rate)')
        
        # 4. Difficulty Rating Distribution
        ax4 = fig.add_subplot(334)
        difficulty_dist = modules_df['difficulty_rating'].value_counts().sort_index()
        ax4.bar(difficulty_dist.index, difficulty_dist.values, color=CONFIG['colors'])
        ax4.set_xlabel('Difficulty Rating (1-5)')
        ax4.set_ylabel('Number of Student Ratings')
        ax4.set_title('Student Difficulty Rating Distribution')
        
        # 5. Attendance vs Pass Rate
        ax5 = fig.add_subplot(335)
        ax5.scatter(module_stats['Avg_Attendance'], module_stats['Pass_Rate'], 
                   s=module_stats['Enrollment']*5, alpha=0.6, color=CONFIG['colors'][1])
        ax5.set_xlabel('Average Attendance Rate (%)')
        ax5.set_ylabel('Pass Rate (%)')
        ax5.set_title('Attendance vs Pass Rate')
        
        # Add correlation
        correlation = module_stats['Avg_Attendance'].corr(module_stats['Pass_Rate'])
        ax5.text(0.05, 0.95, f'Correlation: {correlation:.3f}', transform=ax5.transAxes, 
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
        
        # 6. Module Type Difficulty Comparison
        ax6 = fig.add_subplot(336)
        type_difficulty = modules_df.groupby('module_type').agg({
            'difficulty_rating': 'mean',
            'module_grade': lambda x: (x.isin(['A', 'B'])).mean() * 100
        })
        
        x = range(len(type_difficulty))
        width = 0.35
        ax6.bar([i - width/2 for i in x], type_difficulty['difficulty_rating'], 
               width, label='Avg Difficulty', color=CONFIG['colors'][0])
        ax6_twin = ax6.twinx()
        ax6_twin.bar([i + width/2 for i in x], type_difficulty['module_grade'], 
                    width, label='Pass Rate (%)', color=CONFIG['colors'][1], alpha=0.7)
        
        ax6.set_xlabel('Module Type')
        ax6.set_ylabel('Average Difficulty Rating')
        ax6_twin.set_ylabel('Pass Rate (%)')
        ax6.set_title('Difficulty and Pass Rate by Module Type')
        ax6.set_xticks(x)
        ax6.set_xticklabels(type_difficulty.index)
        ax6.legend(loc='upper left')
        ax6_twin.legend(loc='upper right')
        
        # 7. Completion Rate vs Enrollment
        ax7 = fig.add_subplot(337)
        ax7.scatter(module_stats['Enrollment'], module_stats['Completion_Rate'], 
                   s=50, alpha=0.6, color=CONFIG['colors'][2])
        ax7.set_xlabel('Module Enrollment')
        ax7.set_ylabel('Completion Rate (%)')
        ax7.set_title('Enrollment vs Completion Rate')
        
        # 8. Overall Difficulty Score Ranking
        ax8 = fig.add_subplot(338)
        top_difficult = module_stats.nsmallest(15, 'Difficulty_Score')
        ax8.barh(range(len(top_difficult)), top_difficult['Difficulty_Score'], 
                color='red', alpha=0.7)
        ax8.set_yticks(range(len(top_difficult)))
        ax8.set_yticklabels(top_difficult.index, fontsize=8)
        ax8.set_xlabel('Difficulty Score (1-5, lower = more difficult)')
        ax8.set_title('Most Difficult Modules (Composite Score)')
        
        # 9. Grade Distribution Heatmap
        ax9 = fig.add_subplot(339)
        grade_by_module = pd.crosstab(modules_df['module_name'], modules_df['module_grade'])
        grade_by_module_pct = grade_by_module.div(grade_by_module.sum(axis=1), axis=0) * 100
        
        # Select top 15 modules by enrollment for readability
        top_modules = module_stats.nlargest(15, 'Enrollment').index
        grade_subset = grade_by_module_pct.loc[top_modules]
        
        im = ax9.imshow(grade_subset.values, cmap='RdYlGn', aspect='auto')
        ax9.set_xticks(range(len(grade_subset.columns)))
        ax9.set_yticks(range(len(grade_subset.index)))
        ax9.set_xticklabels(grade_subset.columns)
        ax9.set_yticklabels(grade_subset.index, fontsize=8)
        ax9.set_xlabel('Grade')
        ax9.set_title('Grade Distribution by Module (%)')
        plt.colorbar(im, ax=ax9)
        
        plt.tight_layout(rect=[0, 0, 1, 0.95])

        # Build detailed analysis summary
        summary_text = "\n" + "="*60 + "\n"
        summary_text += "MODULE DIFFICULTY ANALYSIS SUMMARY\n"
        summary_text += "="*60 + "\n"

        summary_text += f"Total modules analyzed: {len(module_stats)}\n"
        summary_text += f"Average pass rate across all modules: {module_stats['Pass_Rate'].mean():.1f}%\n"
        summary_text += f"Average difficulty rating: {module_stats['Avg_Difficulty'].mean():.1f}/5\n"
        summary_text += f"Average completion rate: {module_stats['Completion_Rate'].mean():.1f}%\n"

        summary_text += f"\nMost Challenging Modules (Lowest Pass Rate):\n"
        for i, (module, stats) in enumerate(challenging.head(5).iterrows()):
            summary_text += f"  {i+1}. {module}: {stats['Pass_Rate']:.1f}% pass rate, {stats['Avg_Difficulty']:.1f}/5 difficulty\n"

        summary_text += f"\nEasiest Modules (Highest Pass Rate):\n"
        for i, (module, stats) in enumerate(easiest.head(5).iterrows()):
            summary_text += f"  {i+1}. {module}: {stats['Pass_Rate']:.1f}% pass rate, {stats['Avg_Difficulty']:.1f}/5 difficulty\n"

        summary_text += f"\nModule Type Analysis:\n"
        for module_type, stats in type_difficulty.iterrows():
            summary_text += f"  {module_type}: Avg Difficulty {stats['difficulty_rating']:.1f}/5, Pass Rate {stats['module_grade']:.1f}%\n"

        summary_text += f"\nRecommendations:\n"
        critical_modules = module_stats[module_stats['Pass_Rate'] < 60]
        if len(critical_modules) > 0:
            summary_text += f"  - Review {len(critical_modules)} modules with pass rates below 60%\n"
            summary_text += f"  - Consider curriculum adjustments for low-performing modules\n"

        high_difficulty = module_stats[module_stats['Avg_Difficulty'] > 4]
        if len(high_difficulty) > 0:
            summary_text += f"  - Provide additional support for {len(high_difficulty)} high-difficulty modules\n"

        # In GUI mode, return data for the GUI to display
        if self.gui_mode:
            return {
                'figure': fig,
                'summary': summary_text,
                'title': 'Module Difficulty Analysis'
            }

        # In CLI mode, print and handle display
        print(summary_text)
        self.save_or_display_plot(fig, "module_difficulty_analysis")

    def analyze_correlations(self):
        """Perform comprehensive correlation analysis"""
        students_df = self.get_all_students(self.custom_filters)
        
        if students_df.empty:
            print("No student data available for correlation analysis.")
            return
        
        # Clean data and ensure we have enough data points
        students_df = students_df.dropna(subset=['gpa'])
        
        if len(students_df) < 2:
            print("Insufficient data for correlation analysis (need at least 2 data points).")
            return
        
        print("\nGenerating Correlation Analysis...")
        
        # Prepare numerical data for correlation with validation
        numeric_cols = []
        if 'age' in students_df.columns and not students_df['age'].isna().all():
            numeric_cols.append('age')
        if 'gpa' in students_df.columns and not students_df['gpa'].isna().all():
            numeric_cols.append('gpa')
        if 'engagement_score' in students_df.columns and not students_df['engagement_score'].isna().all():
            numeric_cols.append('engagement_score')
        if 'attendance_rate' in students_df.columns and not students_df['attendance_rate'].isna().all():
            numeric_cols.append('attendance_rate')
        
        if len(numeric_cols) < 2:
            print("Insufficient numerical columns for correlation analysis.")
            return
        
        # Create categorical encodings with validation
        encoded_cols = []
        
        if 'gender' in students_df.columns and not students_df['gender'].isna().all():
            students_df['gender_encoded'] = pd.Categorical(students_df['gender']).codes
            encoded_cols.append('gender_encoded')
        
        if 'course' in students_df.columns and not students_df['course'].isna().all():
            students_df['course_encoded'] = pd.Categorical(students_df['course']).codes
            encoded_cols.append('course_encoded')
        
        if 'completion_status' in students_df.columns and not students_df['completion_status'].isna().all():
            students_df['completion_encoded'] = pd.Categorical(students_df['completion_status']).codes
            encoded_cols.append('completion_encoded')
        
        if 'previous_education' in students_df.columns and not students_df['previous_education'].isna().all():
            students_df['education_encoded'] = pd.Categorical(students_df['previous_education']).codes
            encoded_cols.append('education_encoded')
        
        # Combine available columns
        analysis_cols = numeric_cols + encoded_cols
        
        if len(analysis_cols) < 2:
            print("Insufficient columns for correlation analysis.")
            return
        
        # Calculate correlation matrix with cleaned data
        correlation_data = students_df[analysis_cols].dropna()
        
        if len(correlation_data) < 2:
            print("Insufficient valid data points for correlation analysis.")
            return
        
        correlation_matrix = correlation_data.corr()
        
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Comprehensive Correlation Analysis', fontsize=20)
        
        # 1. Main Correlation Heatmap
        ax1 = fig.add_subplot(331)
        im1 = ax1.imshow(correlation_matrix, cmap='RdBu_r', aspect='auto', vmin=-1, vmax=1)
        ax1.set_xticks(range(len(analysis_cols)))
        ax1.set_yticks(range(len(analysis_cols)))
        
        # Create labels based on available columns
        label_map = {
            'age': 'Age', 'gpa': 'GPA', 'engagement_score': 'Engagement', 
            'attendance_rate': 'Attendance', 'gender_encoded': 'Gender', 
            'course_encoded': 'Course', 'completion_encoded': 'Completion', 
            'education_encoded': 'Education'
        }
        labels = [label_map.get(col, col) for col in analysis_cols]
        
        ax1.set_xticklabels(labels, rotation=45, ha='right')
        ax1.set_yticklabels(labels)
        ax1.set_title('Correlation Matrix')
        
        # Add correlation values to heatmap
        for i in range(len(analysis_cols)):
            for j in range(len(analysis_cols)):
                value = correlation_matrix.iloc[i, j]
                if not (np.isnan(value) or np.isinf(value)):
                    color = 'white' if abs(value) > 0.5 else 'black'
                    ax1.text(j, i, f'{value:.2f}', ha='center', va='center', color=color, fontsize=8)
        
        plt.colorbar(im1, ax=ax1)
        
        # 2. Age vs GPA Correlation
        ax2 = fig.add_subplot(332)
        if 'age' in analysis_cols and 'gpa' in analysis_cols:
            valid_data = students_df.dropna(subset=['age', 'gpa'])
            if len(valid_data) >= 2:
                ax2.scatter(valid_data['age'], valid_data['gpa'], alpha=0.6, color=CONFIG['colors'][0])
                try:
                    z = np.polyfit(valid_data['age'], valid_data['gpa'], 1)
                    p = np.poly1d(z)
                    ax2.plot(valid_data['age'], p(valid_data['age']), "r--", alpha=0.8)
                    corr_val = correlation_matrix.loc['age', 'gpa']
                    ax2.set_title(f'Age vs GPA (r={corr_val:.3f})')
                except (KeyError, ValueError, np.linalg.LinAlgError):
                    ax2.set_title('Age vs GPA (trend unavailable)')
                ax2.set_xlabel('Age')
                ax2.set_ylabel('GPA')
            else:
                ax2.text(0.5, 0.5, 'Insufficient age/GPA data', ha='center', va='center', transform=ax2.transAxes)
        else:
            ax2.text(0.5, 0.5, 'Age or GPA data not available', ha='center', va='center', transform=ax2.transAxes)
            ax2.set_title('Age vs GPA (No Data)')
        
        # 3. Engagement vs GPA Correlation
        ax3 = fig.add_subplot(333)
        if 'engagement_score' in analysis_cols and 'gpa' in analysis_cols:
            valid_data = students_df.dropna(subset=['engagement_score', 'gpa'])
            if len(valid_data) >= 2:
                ax3.scatter(valid_data['engagement_score'], valid_data['gpa'], alpha=0.6, color=CONFIG['colors'][1])
                try:
                    z = np.polyfit(valid_data['engagement_score'], valid_data['gpa'], 1)
                    p = np.poly1d(z)
                    ax3.plot(valid_data['engagement_score'], p(valid_data['engagement_score']), "r--", alpha=0.8)
                    corr_val = correlation_matrix.loc['engagement_score', 'gpa']
                    ax3.set_title(f'Engagement vs GPA (r={corr_val:.3f})')
                except (KeyError, ValueError, np.linalg.LinAlgError):
                    ax3.set_title('Engagement vs GPA (trend unavailable)')
                ax3.set_xlabel('Engagement Score')
                ax3.set_ylabel('GPA')
            else:
                ax3.text(0.5, 0.5, 'Insufficient engagement/GPA data', ha='center', va='center', transform=ax3.transAxes)
        else:
            ax3.text(0.5, 0.5, 'Engagement or GPA data not available', ha='center', va='center', transform=ax3.transAxes)
            ax3.set_title('Engagement vs GPA (No Data)')
        
        # 4. Statistical Significance Tests
        ax4 = fig.add_subplot(334)
        
        # Perform statistical tests only on numeric columns
        correlations = []
        p_values = []
        pairs = []
        
        for i, col1 in enumerate(numeric_cols):
            for j, col2 in enumerate(numeric_cols):
                if i < j:  # Avoid duplicates
                    valid_data = students_df.dropna(subset=[col1, col2])
                    if len(valid_data) >= 3:  # Need at least 3 points for meaningful correlation
                        try:
                            corr, p_val = stats.pearsonr(valid_data[col1], valid_data[col2])
                            correlations.append(abs(corr))
                            p_values.append(p_val)
                            pairs.append(f'{col1}-{col2}')
                        except (ValueError, KeyError):
                            pass  # Skip if correlation calculation fails
        
        if correlations:
            colors = ['green' if p < 0.05 else 'red' for p in p_values]
            bars = ax4.bar(range(len(correlations)), correlations, color=colors, alpha=0.7)
            ax4.set_xlabel('Variable Pairs')
            ax4.set_ylabel('|Correlation Coefficient|')
            ax4.set_title('Correlation Significance (Green: p<0.05)')
            ax4.set_xticks(range(len(pairs)))
            ax4.set_xticklabels([pair.replace('_', '\n') for pair in pairs], rotation=45, ha='right', fontsize=8)
            ax4.axhline(y=0.3, color='orange', linestyle='--', alpha=0.5, label='Moderate Correlation')
            ax4.axhline(y=0.7, color='red', linestyle='--', alpha=0.5, label='Strong Correlation')
            ax4.legend()
        else:
            ax4.text(0.5, 0.5, 'No valid correlations to test', ha='center', va='center', transform=ax4.transAxes)
            ax4.set_title('Correlation Significance (No Data)')
        
        # 5. Course Performance Comparison
        ax5 = fig.add_subplot(335)
        if 'course' in students_df.columns and not students_df['course'].isna().all():
            try:
                course_stats = students_df.groupby('course').agg({
                    'gpa': 'mean'
                }).dropna()
                
                # Add other metrics if available
                if 'engagement_score' in students_df.columns:
                    course_stats['engagement_score'] = students_df.groupby('course')['engagement_score'].mean()
                if 'age' in students_df.columns:
                    course_stats['age'] = students_df.groupby('course')['age'].mean()
                
                if not course_stats.empty:
                    x = range(len(course_stats))
                    width = 0.25
                    ax5.bar([i - width for i in x], course_stats['gpa'], width, label='Avg GPA', color=CONFIG['colors'][0])
                    
                    if 'engagement_score' in course_stats.columns:
                        ax5.bar(x, course_stats['engagement_score']/25, width, label='Avg Engagement/25', color=CONFIG['colors'][1])
                    if 'age' in course_stats.columns:
                        ax5.bar([i + width for i in x], course_stats['age']/10, width, label='Avg Age/10', color=CONFIG['colors'][2])
                    
                    ax5.set_xlabel('Course')
                    ax5.set_ylabel('Scaled Values')
                    ax5.set_title('Course Performance Metrics')
                    ax5.set_xticks(x)
                    ax5.set_xticklabels(course_stats.index, rotation=45, ha='right')
                    ax5.legend()
                else:
                    ax5.text(0.5, 0.5, 'No valid course data', ha='center', va='center', transform=ax5.transAxes)
            except Exception as e:
                ax5.text(0.5, 0.5, 'Error processing course data', ha='center', va='center', transform=ax5.transAxes)
        else:
            ax5.text(0.5, 0.5, 'Course data not available', ha='center', va='center', transform=ax5.transAxes)
            ax5.set_title('Course Performance Metrics (No Data)')
        
        # 6. Gender Performance Analysis
        ax6 = fig.add_subplot(336)
        if 'gender' in students_df.columns and not students_df['gender'].isna().all():
            try:
                gender_stats = students_df.groupby('gender').agg({
                    'gpa': ['mean', 'std']
                }).dropna()
                
                if not gender_stats.empty and len(gender_stats) > 0:
                    genders = gender_stats.index
                    gpa_means = gender_stats[('gpa', 'mean')]
                    gpa_stds = gender_stats[('gpa', 'std')].fillna(0)  # Fill NaN std with 0
                    
                    x_pos = range(len(genders))
                    ax6.bar(x_pos, gpa_means, yerr=gpa_stds, capsize=5, color=CONFIG['colors'], alpha=0.7)
                    ax6.set_xlabel('Gender')
                    ax6.set_ylabel('Average GPA')
                    ax6.set_title('GPA by Gender (with std dev)')
                    ax6.set_xticks(x_pos)
                    ax6.set_xticklabels(genders)
                else:
                    ax6.text(0.5, 0.5, 'No valid gender data', ha='center', va='center', transform=ax6.transAxes)
            except Exception as e:
                ax6.text(0.5, 0.5, 'Error processing gender data', ha='center', va='center', transform=ax6.transAxes)
        else:
            ax6.text(0.5, 0.5, 'Gender data not available', ha='center', va='center', transform=ax6.transAxes)
            ax6.set_title('GPA by Gender (No Data)')
        
        # 7. Education Level Impact
        ax7 = fig.add_subplot(337)
        if 'previous_education' in students_df.columns and not students_df['previous_education'].isna().all():
            try:
                education_gpa = students_df.groupby('previous_education')['gpa'].mean().dropna().sort_values(ascending=False)
                if not education_gpa.empty:
                    ax7.bar(range(len(education_gpa)), education_gpa.values, color=CONFIG['colors'])
                    ax7.set_xlabel('Previous Education Level')
                    ax7.set_ylabel('Average GPA')
                    ax7.set_title('GPA by Previous Education Level')
                    ax7.set_xticks(range(len(education_gpa)))
                    ax7.set_xticklabels(education_gpa.index, rotation=45, ha='right')
                else:
                    ax7.text(0.5, 0.5, 'No valid education data', ha='center', va='center', transform=ax7.transAxes)
            except Exception as e:
                ax7.text(0.5, 0.5, 'Error processing education data', ha='center', va='center', transform=ax7.transAxes)
        else:
            ax7.text(0.5, 0.5, 'Education data not available', ha='center', va='center', transform=ax7.transAxes)
            ax7.set_title('GPA by Previous Education Level (No Data)')
        
        # 8. Multi-variable Correlation Network
        ax8 = fig.add_subplot(338)
        
        try:
            # Create a simplified network visualization
            strong_correlations = []
            for i in range(len(analysis_cols)):
                for j in range(i+1, len(analysis_cols)):
                    corr_val = abs(correlation_matrix.iloc[i, j])
                    if not (np.isnan(corr_val) or np.isinf(corr_val)) and corr_val > 0.3:
                        strong_correlations.append((i, j, corr_val))
            
            if strong_correlations and len(analysis_cols) > 1:
                # Simple network plot
                pos = {}
                n_vars = len(analysis_cols)
                for i, var in enumerate(analysis_cols):
                    angle = 2 * np.pi * i / n_vars
                    pos[i] = (np.cos(angle), np.sin(angle))
                
                # Draw nodes
                for i, (x, y) in pos.items():
                    ax8.scatter(x, y, s=500, color=CONFIG['colors'][i % len(CONFIG['colors'])], alpha=0.7)
                    ax8.text(x, y, labels[i], ha='center', va='center', fontsize=8, weight='bold')
                
                # Draw edges for strong correlations
                for i, j, corr in strong_correlations:
                    x1, y1 = pos[i]
                    x2, y2 = pos[j]
                    width = corr * 3  # Scale line width by correlation strength
                    ax8.plot([x1, x2], [y1, y2], 'k-', alpha=0.6, linewidth=width)
                
                ax8.set_xlim(-1.5, 1.5)
                ax8.set_ylim(-1.5, 1.5)
                ax8.set_aspect('equal')
                ax8.set_title('Correlation Network (>0.3)')
                ax8.axis('off')
            else:
                ax8.text(0.5, 0.5, 'No strong correlations found', ha='center', va='center', transform=ax8.transAxes)
                ax8.set_title('Correlation Network (No Strong Correlations)')
        except Exception as e:
            ax8.text(0.5, 0.5, 'Error creating network', ha='center', va='center', transform=ax8.transAxes)
            ax8.set_title('Correlation Network (Error)')
        
        # 9. Predictive Model Feature Importance
        ax9 = fig.add_subplot(339)
        
        if 'gpa' in correlation_matrix.columns:
            try:
                feature_importance = abs(correlation_matrix['gpa']).drop('gpa').dropna().sort_values(ascending=True)
                
                if not feature_importance.empty:
                    ax9.barh(range(len(feature_importance)), feature_importance.values, color=CONFIG['colors'])
                    ax9.set_yticks(range(len(feature_importance)))
                    ax9.set_yticklabels([label_map.get(col, col) for col in feature_importance.index])
                    ax9.set_xlabel('|Correlation with GPA|')
                    ax9.set_title('Feature Importance for GPA Prediction')
                else:
                    ax9.text(0.5, 0.5, 'No features to analyze', ha='center', va='center', transform=ax9.transAxes)
            except Exception as e:
                ax9.text(0.5, 0.5, 'Error calculating importance', ha='center', va='center', transform=ax9.transAxes)
        else:
            ax9.text(0.5, 0.5, 'GPA data not available', ha='center', va='center', transform=ax9.transAxes)
            ax9.set_title('Feature Importance (No GPA Data)')
        
        plt.tight_layout(rect=[0, 0, 1, 0.95])

        # Build detailed correlation analysis summary
        summary_text = "\n" + "="*60 + "\n"
        summary_text += "CORRELATION ANALYSIS SUMMARY\n"
        summary_text += "="*60 + "\n"

        if 'gpa' in correlation_matrix.columns:
            summary_text += f"Strongest Correlations with GPA:\n"
            gpa_correlations = correlation_matrix['gpa'].abs().dropna().sort_values(ascending=False)
            for var, corr in gpa_correlations.head(5).items():
                if var != 'gpa':
                    direction = "positive" if correlation_matrix.loc['gpa', var] > 0 else "negative"
                    var_label = label_map.get(var, var)
                    summary_text += f"  {var_label}: {corr:.3f} ({direction})\n"
        else:
            summary_text += "GPA data not available for correlation analysis.\n"

        if correlations:
            summary_text += f"\nStatistical Significance Tests:\n"
            for i, (pair, p_val) in enumerate(zip(pairs, p_values)):
                significance = "significant" if p_val < 0.05 else "not significant"
                summary_text += f"  {pair}: p={p_val:.4f} ({significance})\n"
        else:
            summary_text += "\nNo statistical significance tests could be performed.\n"

        summary_text += f"\nKey Findings:\n"
        strong_corrs = []
        for i in range(len(analysis_cols)):
            for j in range(i+1, len(analysis_cols)):
                corr_val = correlation_matrix.iloc[i, j]
                if not (np.isnan(corr_val) or np.isinf(corr_val)) and abs(corr_val) > 0.5:
                    strong_corrs.append((i, j, corr_val))

        if strong_corrs:
            summary_text += f"  Strong correlations found:\n"
            for i, j, corr in strong_corrs:
                summary_text += f"    {labels[i]} - {labels[j]}: {corr:.3f}\n"
        else:
            summary_text += f"  No strong correlations (>0.5) found between variables\n"

        # In GUI mode, return data for the GUI to display
        if self.gui_mode:
            return {
                'figure': fig,
                'summary': summary_text,
                'title': 'Correlation Analysis'
            }

        # In CLI mode, print and handle display
        print(summary_text)
        self.save_or_display_plot(fig, "correlation_analysis")
        
    def analyze_engagement(self):
        """Comprehensive student engagement analysis"""
        students_df = self.get_all_students(self.custom_filters)
        modules_df = self.get_all_modules(self.custom_filters)
        
        if students_df.empty:
            print("No student data available for engagement analysis.")
            return
        
        print("\nGenerating Student Engagement Analysis...")
        
        # Create engagement categories
        students_df['engagement_category'] = pd.cut(students_df['engagement_score'], 
                                                   bins=[0, 25, 50, 75, 100], 
                                                   labels=['Low', 'Medium', 'High', 'Very High'])
        
        # Calculate engagement metrics
        if not modules_df.empty:
            student_module_counts = modules_df.groupby('student_id').size().reset_index(name='module_count')
            students_df = students_df.merge(student_module_counts, on='student_id', how='left')
            students_df['module_count'] = students_df['module_count'].fillna(0)
            
            avg_attendance = modules_df.groupby('student_id')['attendance_rate'].mean().reset_index()
            students_df = students_df.merge(avg_attendance, on='student_id', how='left')
            students_df['attendance_rate'] = students_df['attendance_rate'].fillna(0)
        
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Student Engagement Analysis Dashboard', fontsize=20)
        
        # 1. Engagement Score Distribution
        ax1 = fig.add_subplot(331)
        ax1.hist(students_df['engagement_score'], bins=20, edgecolor='black', alpha=0.7, color=CONFIG['colors'][0])
        ax1.axvline(students_df['engagement_score'].mean(), color='red', linestyle='--', 
                   label=f'Mean: {students_df["engagement_score"].mean():.1f}')
        ax1.axvline(students_df['engagement_score'].median(), color='green', linestyle='--', 
                   label=f'Median: {students_df["engagement_score"].median():.1f}')
        ax1.set_xlabel('Engagement Score')
        ax1.set_ylabel('Number of Students')
        ax1.set_title('Engagement Score Distribution')
        ax1.legend()
        
        # 2. Engagement Categories
        ax2 = fig.add_subplot(332)
        engagement_counts = students_df['engagement_category'].value_counts()
        colors = ['red', 'orange', 'lightgreen', 'green']
        ax2.pie(engagement_counts.values, labels=engagement_counts.index, autopct='%1.1f%%', 
               colors=colors, startangle=90)
        ax2.set_title('Engagement Level Distribution')
        
        # 3. Engagement by Course
        ax3 = fig.add_subplot(333)
        course_engagement = students_df.groupby('course')['engagement_score'].mean()
        ax3.bar(course_engagement.index, course_engagement.values, color=CONFIG['colors'])
        ax3.set_xlabel('Course')
        ax3.set_ylabel('Average Engagement Score')
        ax3.set_title('Average Engagement by Course')
        
        # 4. Engagement vs GPA
        ax4 = fig.add_subplot(334)
        scatter = ax4.scatter(students_df['engagement_score'], students_df['gpa'], 
                             c=students_df['age'], cmap='viridis', alpha=0.6, s=50)
        ax4.set_xlabel('Engagement Score')
        ax4.set_ylabel('GPA')
        ax4.set_title('Engagement vs Academic Performance')
        plt.colorbar(scatter, ax=ax4, label='Age')
        
        # Add correlation
        correlation = students_df['engagement_score'].corr(students_df['gpa'])
        ax4.text(0.05, 0.95, f'Correlation: {correlation:.3f}', transform=ax4.transAxes, 
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
        
        # 5. Engagement vs Module Enrollment
        if not modules_df.empty:
            ax5 = fig.add_subplot(335)
            ax5.scatter(students_df['module_count'], students_df['engagement_score'], 
                       alpha=0.6, color=CONFIG['colors'][2])
            ax5.set_xlabel('Number of Modules Enrolled')
            ax5.set_ylabel('Engagement Score')
            ax5.set_title('Module Load vs Engagement')
            
            correlation = students_df['module_count'].corr(students_df['engagement_score'])
            ax5.text(0.05, 0.95, f'Correlation: {correlation:.3f}', transform=ax5.transAxes, 
                    bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
        
        # 6. Engagement Trends by Age Group
        ax6 = fig.add_subplot(336)
        # Filter out None/NaN age values before using pd.cut
        students_with_age = students_df[students_df['age'].notna()].copy()
        if not students_with_age.empty:
            age_groups = pd.cut(students_with_age['age'], bins=[0, 25, 35, 45, 100],
                               labels=['18-25', '26-35', '36-45', '46+'])
            age_engagement = students_with_age.groupby(age_groups)['engagement_score'].agg(['mean', 'std'])

            if not age_engagement.empty:
                x_pos = range(len(age_engagement))
                ax6.bar(x_pos, age_engagement['mean'], yerr=age_engagement['std'].fillna(0),
                       capsize=5, color=CONFIG['colors'], alpha=0.7)
                ax6.set_xlabel('Age Group')
                ax6.set_ylabel('Average Engagement Score')
                ax6.set_title('Engagement by Age Group')
                ax6.set_xticks(x_pos)
                ax6.set_xticklabels(age_engagement.index)
            else:
                ax6.text(0.5, 0.5, 'No engagement data by age group',
                        ha='center', va='center', transform=ax6.transAxes)
                ax6.set_title('Engagement by Age Group')
        else:
            ax6.text(0.5, 0.5, 'No valid age data available',
                    ha='center', va='center', transform=ax6.transAxes)
            ax6.set_title('Engagement by Age Group')
        
        # 7. High vs Low Engagement Comparison
        ax7 = fig.add_subplot(337)
        high_engagement = students_df[students_df['engagement_score'] >= 75]
        low_engagement = students_df[students_df['engagement_score'] <= 25]
        
        metrics = ['gpa', 'age']
        if not modules_df.empty:
            metrics.extend(['module_count', 'attendance_rate'])
        
        high_means = [high_engagement[metric].mean() for metric in metrics if metric in high_engagement.columns]
        low_means = [low_engagement[metric].mean() for metric in metrics if metric in low_engagement.columns]
        
        x = range(len(high_means))
        width = 0.35
        ax7.bar([i - width/2 for i in x], high_means, width, label='High Engagement (≥75)', 
               color='green', alpha=0.7)
        ax7.bar([i + width/2 for i in x], low_means, width, label='Low Engagement (≤25)', 
               color='red', alpha=0.7)
        
        ax7.set_xlabel('Metrics')
        ax7.set_ylabel('Average Values')
        ax7.set_title('High vs Low Engagement Comparison')
        ax7.set_xticks(x)
        ax7.set_xticklabels([m.replace('_', ' ').title() for m in metrics[:len(high_means)]])
        ax7.legend()
        
        # 8. Engagement Heatmap by Demographics
        ax8 = fig.add_subplot(338)
        engagement_heatmap = students_df.groupby(['course', 'gender'])['engagement_score'].mean().unstack()
        
        im = ax8.imshow(engagement_heatmap.values, cmap='RdYlGn', aspect='auto')
        ax8.set_xticks(range(len(engagement_heatmap.columns)))
        ax8.set_yticks(range(len(engagement_heatmap.index)))
        ax8.set_xticklabels(engagement_heatmap.columns)
        ax8.set_yticklabels(engagement_heatmap.index)
        ax8.set_xlabel('Gender')
        ax8.set_ylabel('Course')
        ax8.set_title('Average Engagement by Course and Gender')
        
        # Add values to heatmap
        for i in range(len(engagement_heatmap.index)):
            for j in range(len(engagement_heatmap.columns)):
                value = engagement_heatmap.iloc[i, j]
                if not np.isnan(value):
                    ax8.text(j, i, f'{value:.1f}', ha='center', va='center', 
                            color='white' if value < 50 else 'black')
        
        plt.colorbar(im, ax=ax8)
        
        # 9. Engagement Improvement Opportunities
        ax9 = fig.add_subplot(339)
        
        # Identify students with potential for improvement
        students_df['improvement_potential'] = 0
        
        # Low engagement but high academic ability
        low_eng_high_gpa = (students_df['engagement_score'] < 50) & (students_df['gpa'] > 3.0)
        students_df.loc[low_eng_high_gpa, 'improvement_potential'] += 3
        
        # Medium engagement with room to grow
        medium_engagement = (students_df['engagement_score'] >= 50) & (students_df['engagement_score'] < 75)
        students_df.loc[medium_engagement, 'improvement_potential'] += 2
        
        # High attendance but low engagement
        if 'attendance_rate' in students_df.columns:
            high_att_low_eng = (students_df['attendance_rate'] > 80) & (students_df['engagement_score'] < 60)
            students_df.loc[high_att_low_eng, 'improvement_potential'] += 2
        
        improvement_counts = students_df['improvement_potential'].value_counts().sort_index()
        labels = ['No Potential', 'Low Potential', 'Medium Potential', 'High Potential'][:len(improvement_counts)]
        colors = ['gray', 'yellow', 'orange', 'red'][:len(improvement_counts)]
        
        ax9.bar(labels, improvement_counts.values, color=colors, alpha=0.7)
        ax9.set_xlabel('Improvement Potential')
        ax9.set_ylabel('Number of Students')
        ax9.set_title('Engagement Improvement Opportunities')
        plt.xticks(rotation=45, ha='right')
        
        plt.tight_layout(rect=[0, 0, 1, 0.95])

        # Build detailed engagement analysis summary
        summary_text = "\n" + "="*60 + "\n"
        summary_text += "STUDENT ENGAGEMENT ANALYSIS SUMMARY\n"
        summary_text += "="*60 + "\n"

        summary_text += f"Engagement Statistics:\n"
        summary_text += f"  Average engagement score: {students_df['engagement_score'].mean():.1f}\n"
        summary_text += f"  Median engagement score: {students_df['engagement_score'].median():.1f}\n"
        summary_text += f"  Standard deviation: {students_df['engagement_score'].std():.1f}\n"

        summary_text += f"\nEngagement Distribution:\n"
        for category, count in engagement_counts.items():
            percentage = count / len(students_df) * 100
            summary_text += f"  {category} engagement: {count} students ({percentage:.1f}%)\n"

        summary_text += f"\nCourse Engagement Comparison:\n"
        for course, avg_engagement in course_engagement.items():
            summary_text += f"  {course}: {avg_engagement:.1f} average score\n"

        summary_text += f"\nEngagement-Performance Insights:\n"
        correlation = students_df['engagement_score'].corr(students_df['gpa'])
        summary_text += f"  Engagement-GPA correlation: {correlation:.3f}\n"

        high_eng_students = students_df[students_df['engagement_score'] >= 75]
        low_eng_students = students_df[students_df['engagement_score'] <= 25]

        if len(high_eng_students) > 0 and len(low_eng_students) > 0:
            summary_text += f"  High engagement students avg GPA: {high_eng_students['gpa'].mean():.2f}\n"
            summary_text += f"  Low engagement students avg GPA: {low_eng_students['gpa'].mean():.2f}\n"

        summary_text += f"\nImprovement Opportunities:\n"
        high_potential = students_df[students_df['improvement_potential'] >= 3]
        summary_text += f"  {len(high_potential)} students with high improvement potential\n"

        if len(high_potential) > 0:
            summary_text += f"  Focus areas: Students with low engagement but high academic ability\n"

        # In GUI mode, return data for the GUI to display
        if self.gui_mode:
            return {
                'figure': fig,
                'summary': summary_text,
                'title': 'Student Engagement Analysis'
            }

        # In CLI mode, print and handle display
        print(summary_text)
        self.save_or_display_plot(fig, "engagement_analysis")

    def predictive_analytics(self):
        """Perform predictive analytics using machine learning"""
        students_df = self.get_all_students(self.custom_filters)
        
        if students_df.empty or len(students_df) < 50:  # Need sufficient data for ML
            print("Insufficient data for predictive analytics (minimum 50 students required).")
            return
        
        print("\nGenerating Predictive Analytics...")
        
        # Prepare data for machine learning
        # Create target variables
        students_df['high_performer'] = (students_df['gpa'] >= 3.5).astype(int)
        students_df['at_risk'] = ((students_df['gpa'] < 2.0) | (students_df['engagement_score'] < 30)).astype(int)
        students_df['will_complete'] = (students_df['completion_status'] == 'Completed').astype(int)
        
        # Prepare features
        feature_columns = ['age', 'engagement_score']
        students_df['gender_encoded'] = pd.Categorical(students_df['gender']).codes
        students_df['course_encoded'] = pd.Categorical(students_df['course']).codes
        students_df['education_encoded'] = pd.Categorical(students_df['previous_education']).codes
        
        feature_columns.extend(['gender_encoded', 'course_encoded', 'education_encoded'])
        
        X = students_df[feature_columns].fillna(0)
        
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Predictive Analytics Dashboard', fontsize=20)
        
        # 1. High Performer Prediction
        ax1 = fig.add_subplot(331)
        y_performance = students_df['high_performer']
        
        if len(y_performance.unique()) > 1:  # Ensure we have both classes
            X_train, X_test, y_train, y_test = train_test_split(X, y_performance, test_size=0.3, random_state=42)
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Train Random Forest
            rf_performance = RandomForestClassifier(n_estimators=100, random_state=42)
            rf_performance.fit(X_train_scaled, y_train)
            
            # Feature importance
            importance = rf_performance.feature_importances_
            feature_names = ['Age', 'Engagement', 'Gender', 'Course', 'Education']
            
            ax1.barh(range(len(importance)), importance, color=CONFIG['colors'])
            ax1.set_yticks(range(len(importance)))
            ax1.set_yticklabels(feature_names)
            ax1.set_xlabel('Feature Importance')
            ax1.set_title('High Performer Prediction - Feature Importance')
            
            # Calculate accuracy
            accuracy = rf_performance.score(X_test_scaled, y_test)
            ax1.text(0.02, 0.98, f'Accuracy: {accuracy:.3f}', transform=ax1.transAxes, 
                    bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
        
        # 2. At-Risk Student Prediction
        ax2 = fig.add_subplot(332)
        y_risk = students_df['at_risk']
        
        if len(y_risk.unique()) > 1:
            X_train, X_test, y_train, y_test = train_test_split(X, y_risk, test_size=0.3, random_state=42)
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            rf_risk = RandomForestClassifier(n_estimators=100, random_state=42)
            rf_risk.fit(X_train_scaled, y_train)
            
            importance_risk = rf_risk.feature_importances_
            ax2.barh(range(len(importance_risk)), importance_risk, color='red', alpha=0.7)
            ax2.set_yticks(range(len(importance_risk)))
            ax2.set_yticklabels(feature_names)
            ax2.set_xlabel('Feature Importance')
            ax2.set_title('At-Risk Prediction - Feature Importance')
            
            accuracy_risk = rf_risk.score(X_test_scaled, y_test)
            ax2.text(0.02, 0.98, f'Accuracy: {accuracy_risk:.3f}', transform=ax2.transAxes, 
                    bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
        
        # 3. GPA Prediction Distribution
        ax3 = fig.add_subplot(333)
        
        # Create GPA prediction model
        from sklearn.ensemble import RandomForestRegressor
        rf_gpa = RandomForestRegressor(n_estimators=100, random_state=42)
        
        y_gpa = students_df['gpa']
        X_train, X_test, y_train, y_test = train_test_split(X, y_gpa, test_size=0.3, random_state=42)
        
        scaler_gpa = StandardScaler()
        X_train_scaled = scaler_gpa.fit_transform(X_train)
        X_test_scaled = scaler_gpa.transform(X_test)
        
        rf_gpa.fit(X_train_scaled, y_train)
        y_pred = rf_gpa.predict(X_test_scaled)
        
        ax3.scatter(y_test, y_pred, alpha=0.6, color=CONFIG['colors'][0])
        ax3.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'r--', lw=2)
        ax3.set_xlabel('Actual GPA')
        ax3.set_ylabel('Predicted GPA')
        ax3.set_title('GPA Prediction Accuracy')
        
        # Calculate R²
        from sklearn.metrics import r2_score
        r2 = r2_score(y_test, y_pred)
        ax3.text(0.05, 0.95, f'R² Score: {r2:.3f}', transform=ax3.transAxes, 
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
        
        # 4. Student Clustering
        ax4 = fig.add_subplot(334)
        
        # K-means clustering
        kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(X)
        students_df['cluster'] = clusters
        
        # Visualize clusters using first two principal components
        from sklearn.decomposition import PCA
        pca = PCA(n_components=2)
        X_pca = pca.fit_transform(X)
        
        colors = ['red', 'blue', 'green', 'orange']
        for i in range(4):
            cluster_data = X_pca[clusters == i]
            ax4.scatter(cluster_data[:, 0], cluster_data[:, 1], 
                       c=colors[i], alpha=0.6, label=f'Cluster {i+1}')
        
        ax4.set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0]:.1%} variance)')
        ax4.set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1]:.1%} variance)')
        ax4.set_title('Student Clustering (PCA Visualization)')
        ax4.legend()
        
        # 5. Cluster Characteristics
        ax5 = fig.add_subplot(335)
        
        cluster_stats = students_df.groupby('cluster').agg({
            'gpa': 'mean',
            'engagement_score': 'mean',
            'age': 'mean'
        })
        
        x = range(len(cluster_stats))
        width = 0.25
        ax5.bar([i - width for i in x], cluster_stats['gpa'], width, label='Avg GPA', alpha=0.7)
        ax5.bar(x, cluster_stats['engagement_score']/25, width, label='Avg Engagement/25', alpha=0.7)
        ax5.bar([i + width for i in x], cluster_stats['age']/10, width, label='Avg Age/10', alpha=0.7)
        
        ax5.set_xlabel('Cluster')
        ax5.set_ylabel('Scaled Values')
        ax5.set_title('Cluster Characteristics')
        ax5.set_xticks(x)
        ax5.set_xticklabels([f'Cluster {i+1}' for i in range(len(cluster_stats))])
        ax5.legend()
        
        # 6. Enrollment Forecasting
        ax6 = fig.add_subplot(336)
        
        # Simple time series forecasting based on registration patterns
        if 'registration_datetime' in students_df.columns:
            students_df['reg_date'] = pd.to_datetime(students_df['registration_datetime'])
            monthly_enrollments = students_df.groupby(students_df['reg_date'].dt.to_period('M')).size()
            
            # Simple linear trend for forecasting
            if len(monthly_enrollments) > 3:
                x_months = range(len(monthly_enrollments))
                y_enrollments = monthly_enrollments.values
                
                # Fit trend line
                z = np.polyfit(x_months, y_enrollments, 1)
                p = np.poly1d(z)
                
                # Forecast next 6 months
                future_months = range(len(monthly_enrollments), len(monthly_enrollments) + 6)
                future_enrollments = [p(month) for month in future_months]
                
                # Plot historical and forecasted data
                ax6.plot(x_months, y_enrollments, 'o-', label='Historical', color=CONFIG['colors'][0])
                ax6.plot(future_months, future_enrollments, 's--', label='Forecast', color='red')
                ax6.set_xlabel('Month')
                ax6.set_ylabel('Enrollments')
                ax6.set_title('Enrollment Forecasting')
                ax6.legend()
                
                # Add trend line
                all_months = list(x_months) + list(future_months)
                trend_line = [p(month) for month in all_months]
                ax6.plot(all_months, trend_line, ':', alpha=0.5, color='gray', label='Trend')
        
        # 7. Risk Score Distribution
        ax7 = fig.add_subplot(337)
        
        # Calculate comprehensive risk score
        students_df['risk_score'] = (
            (students_df['gpa'] < 2.5).astype(int) * 2 +
            (students_df['engagement_score'] < 40).astype(int) * 2 +
            (students_df['age'] > 40).astype(int) * 1  # Older students might need different support
        )
        
        risk_dist = students_df['risk_score'].value_counts().sort_index()
        risk_colors = ['green', 'yellow', 'orange', 'red', 'darkred', 'purple']
        
        ax7.bar(risk_dist.index, risk_dist.values, color=risk_colors[:len(risk_dist)], alpha=0.7)
        ax7.set_xlabel('Risk Score')
        ax7.set_ylabel('Number of Students')
        ax7.set_title('Comprehensive Risk Score Distribution')
        
        # 8. Predictive Model Comparison
        ax8 = fig.add_subplot(338)
        
        # Compare different models for at-risk prediction
        from sklearn.linear_model import LogisticRegression
        from sklearn.svm import SVC
        from sklearn.naive_bayes import GaussianNB
        
        models = {
            'Random Forest': RandomForestClassifier(n_estimators=100, random_state=42),
            'Logistic Regression': LogisticRegression(random_state=42, max_iter=1000),
            'SVM': SVC(random_state=42),
            'Naive Bayes': GaussianNB()
        }
        
        model_scores = []
        model_names = []
        
        if len(y_risk.unique()) > 1:
            X_train, X_test, y_train, y_test = train_test_split(X, y_risk, test_size=0.3, random_state=42)
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            for name, model in models.items():
                try:
                    model.fit(X_train_scaled, y_train)
                    score = model.score(X_test_scaled, y_test)
                    model_scores.append(score)
                    model_names.append(name)
                except Exception:
                    continue  # Skip models that fail
            
            ax8.bar(range(len(model_scores)), model_scores, color=CONFIG['colors'], alpha=0.7)
            ax8.set_xticks(range(len(model_names)))
            ax8.set_xticklabels(model_names, rotation=45, ha='right')
            ax8.set_ylabel('Accuracy Score')
            ax8.set_title('Model Performance Comparison')
            ax8.set_ylim(0, 1)
        
        # 9. Feature Correlation with Predictions
        ax9 = fig.add_subplot(339)
        
        # Show how well individual features predict outcomes
        feature_predictive_power = []
        for i, feature in enumerate(feature_columns):
            if len(students_df[feature].unique()) > 1:
                corr_performance = abs(students_df[feature].corr(students_df['high_performer']))
                corr_risk = abs(students_df[feature].corr(students_df['at_risk']))
                avg_predictive_power = (corr_performance + corr_risk) / 2
                feature_predictive_power.append(avg_predictive_power)
            else:
                feature_predictive_power.append(0)
        
        ax9.barh(range(len(feature_names)), feature_predictive_power, color=CONFIG['colors'])
        ax9.set_yticks(range(len(feature_names)))
        ax9.set_yticklabels(feature_names)
        ax9.set_xlabel('Average Predictive Power')
        ax9.set_title('Feature Predictive Power Analysis')
        
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        
        # Print detailed predictive analytics summary
        print("\n" + "="*60)
        print("PREDICTIVE ANALYTICS SUMMARY")
        print("="*60)
        
        print(f"Model Performance:")
        if len(y_performance.unique()) > 1:
            print(f"  High Performer Prediction Accuracy: {accuracy:.3f}")
        if len(y_risk.unique()) > 1:
            print(f"  At-Risk Student Prediction Accuracy: {accuracy_risk:.3f}")
        print(f"  GPA Prediction R² Score: {r2:.3f}")
        
        print(f"\nStudent Clusters Identified: {len(cluster_stats)}")
        for i, (cluster, stats) in enumerate(cluster_stats.iterrows()):
            print(f"  Cluster {cluster+1}: Avg GPA {stats['gpa']:.2f}, Avg Engagement {stats['engagement_score']:.1f}")
        
        print(f"\nRisk Score Distribution:")
        for score, count in risk_dist.items():
            risk_level = ['Very Low', 'Low', 'Medium', 'High', 'Very High', 'Critical'][min(score, 5)]
            print(f"  Score {score} ({risk_level}): {count} students ({count/len(students_df)*100:.1f}%)")
        
        print(f"\nTop Predictive Features:")
        feature_importance_sorted = sorted(zip(feature_names, feature_predictive_power), 
                                         key=lambda x: x[1], reverse=True)
        for feature, power in feature_importance_sorted[:3]:
            print(f"  {feature}: {power:.3f}")
        
        if len(model_scores) > 0:
            best_model = model_names[np.argmax(model_scores)]
            print(f"\nBest Performing Model: {best_model} (Accuracy: {max(model_scores):.3f})")
        
        self.save_or_display_plot(fig, "predictive_analytics")

    def analyze_cohorts(self):
        """Analyze student cohorts and retention patterns"""
        students_df = self.get_all_students(self.custom_filters)
        
        if students_df.empty:
            print("No student data available for cohort analysis.")
            return
        
        print("\nGenerating Cohort Analysis...")
        
        # Create cohorts based on registration date
        students_df['registration_date'] = pd.to_datetime(students_df['registration_datetime'])
        students_df['cohort_month'] = students_df['registration_date'].dt.to_period('M')
        
        # Define current date for analysis
        current_date = students_df['registration_date'].max()
        students_df['months_since_registration'] = (
            (current_date - students_df['registration_date']).dt.days / 30.44
        ).fillna(0).round().astype(int)
        
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Student Cohort Analysis', fontsize=20)
        
        # 1. Cohort Size Over Time
        ax1 = fig.add_subplot(331)
        cohort_sizes = students_df.groupby('cohort_month').size()
        ax1.plot(range(len(cohort_sizes)), cohort_sizes.values, marker='o', color=CONFIG['colors'][0])
        ax1.set_xlabel('Cohort Period')
        ax1.set_ylabel('Number of Students')
        ax1.set_title('Cohort Size Over Time')
        ax1.set_xticks(range(0, len(cohort_sizes), max(1, len(cohort_sizes)//5)))
        ax1.set_xticklabels([str(cohort_sizes.index[i]) for i in range(0, len(cohort_sizes), max(1, len(cohort_sizes)//5))], rotation=45)
        
        # 2. Retention Rate by Cohort
        ax2 = fig.add_subplot(332)
        cohort_retention = students_df.groupby('cohort_month').apply(
            lambda x: (x['completion_status'].isin(['Active', 'Completed'])).mean() * 100
        )
        ax2.bar(range(len(cohort_retention)), cohort_retention.values, color=CONFIG['colors'][1], alpha=0.7)
        ax2.set_xlabel('Cohort Period')
        ax2.set_ylabel('Retention Rate (%)')
        ax2.set_title('Retention Rate by Cohort')
        ax2.set_xticks(range(0, len(cohort_retention), max(1, len(cohort_retention)//5)))
        ax2.set_xticklabels([str(cohort_retention.index[i]) for i in range(0, len(cohort_retention), max(1, len(cohort_retention)//5))], rotation=45)
        
        # 3. Completion Rate by Cohort
        ax3 = fig.add_subplot(333)
        cohort_completion = students_df.groupby('cohort_month').apply(
            lambda x: (x['completion_status'] == 'Completed').mean() * 100
        )
        ax3.bar(range(len(cohort_completion)), cohort_completion.values, color='green', alpha=0.7)
        ax3.set_xlabel('Cohort Period')
        ax3.set_ylabel('Completion Rate (%)')
        ax3.set_title('Completion Rate by Cohort')
        ax3.set_xticks(range(0, len(cohort_completion), max(1, len(cohort_completion)//5)))
        ax3.set_xticklabels([str(cohort_completion.index[i]) for i in range(0, len(cohort_completion), max(1, len(cohort_completion)//5))], rotation=45)
        
        # 4. Cohort Performance Comparison
        ax4 = fig.add_subplot(334)
        cohort_performance = students_df.groupby('cohort_month').agg({
            'gpa': 'mean',
            'engagement_score': 'mean'
        })
        
        x = range(len(cohort_performance))
        width = 0.35
        ax4.bar([i - width/2 for i in x], cohort_performance['gpa'], width, 
               label='Avg GPA', color=CONFIG['colors'][0])
        ax4_twin = ax4.twinx()
        ax4_twin.bar([i + width/2 for i in x], cohort_performance['engagement_score'], width, 
                    label='Avg Engagement', color=CONFIG['colors'][1], alpha=0.7)
        
        ax4.set_xlabel('Cohort Period')
        ax4.set_ylabel('Average GPA')
        ax4_twin.set_ylabel('Average Engagement Score')
        ax4.set_title('Cohort Performance Metrics')
        ax4.legend(loc='upper left')
        ax4_twin.legend(loc='upper right')
        
        # 5. Student Journey Funnel
        ax5 = fig.add_subplot(335)
        journey_stages = ['Registered', 'Active', 'Completed', 'Dropped']
        stage_counts = [
            len(students_df),
            len(students_df[students_df['completion_status'] == 'Active']),
            len(students_df[students_df['completion_status'] == 'Completed']),
            len(students_df[students_df['completion_status'] == 'Dropped'])
        ]
        
        colors = ['blue', 'green', 'gold', 'red']
        ax5.bar(journey_stages, stage_counts, color=colors, alpha=0.7)
        ax5.set_ylabel('Number of Students')
        ax5.set_title('Student Journey Funnel')
        
        # Add percentage labels
        for i, count in enumerate(stage_counts):
            percentage = count / stage_counts[0] * 100
            ax5.text(i, count + max(stage_counts)*0.01, f'{percentage:.1f}%', 
                    ha='center', va='bottom')
        
        # 6. Time to Completion Analysis
        ax6 = fig.add_subplot(336)
        completed_students = students_df[students_df['completion_status'] == 'Completed']
        if not completed_students.empty:
            ax6.hist(completed_students['months_since_registration'], bins=15, 
                    edgecolor='black', alpha=0.7, color=CONFIG['colors'][2])
            ax6.set_xlabel('Months to Completion')
            ax6.set_ylabel('Number of Students')
            ax6.set_title('Time to Completion Distribution')
            
            avg_completion_time = completed_students['months_since_registration'].mean()
            ax6.axvline(avg_completion_time, color='red', linestyle='--', 
                       label=f'Avg: {avg_completion_time:.1f} months')
            ax6.legend()
        
        # 7. Cohort Heatmap
        ax7 = fig.add_subplot(337)
        
        # Create cohort table for heatmap
        cohort_table = students_df.groupby(['cohort_month', 'completion_status']).size().unstack(fill_value=0)
        cohort_table_pct = cohort_table.div(cohort_table.sum(axis=1), axis=0) * 100
        
        if len(cohort_table_pct) > 1:
            im = ax7.imshow(cohort_table_pct.T.values, cmap='RdYlGn', aspect='auto')
            ax7.set_xticks(range(len(cohort_table_pct.index)))
            ax7.set_yticks(range(len(cohort_table_pct.columns)))
            ax7.set_xticklabels([str(idx) for idx in cohort_table_pct.index], rotation=45, ha='right', fontsize=8)
            ax7.set_yticklabels(cohort_table_pct.columns)
            ax7.set_xlabel('Cohort Period')
            ax7.set_ylabel('Completion Status')
            ax7.set_title('Cohort Status Distribution (%)')
            plt.colorbar(im, ax=ax7)
        
        # 8. Age Group Cohort Analysis
        ax8 = fig.add_subplot(338)
        # Filter out None/NaN age values before using pd.cut
        students_with_age = students_df[students_df['age'].notna()].copy()
        if not students_with_age.empty:
            students_with_age['age_group'] = pd.cut(students_with_age['age'], bins=[0, 25, 35, 45, 100],
                                             labels=['18-25', '26-35', '36-45', '46+'])
            age_cohort_completion = students_with_age.groupby(['age_group', 'cohort_month']).apply(
                lambda x: (x['completion_status'] == 'Completed').mean() * 100
            ).unstack(fill_value=0)

            if len(age_cohort_completion.columns) > 1:
                age_cohort_completion.plot(kind='line', marker='o', ax=ax8, color=CONFIG['colors'])
                ax8.set_xlabel('Age Group')
                ax8.set_ylabel('Completion Rate (%)')
                ax8.set_title('Completion Rate by Age Group and Cohort')
                ax8.legend(title='Cohort', bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
            else:
                ax8.text(0.5, 0.5, 'Insufficient cohort data for age group analysis',
                        ha='center', va='center', transform=ax8.transAxes)
                ax8.set_title('Completion Rate by Age Group and Cohort')
        else:
            ax8.text(0.5, 0.5, 'No valid age data available',
                    ha='center', va='center', transform=ax8.transAxes)
            ax8.set_title('Completion Rate by Age Group and Cohort')
        
        # 9. Course-wise Cohort Performance
        ax9 = fig.add_subplot(339)
        course_cohort_gpa = students_df.groupby(['course', 'cohort_month'])['gpa'].mean().unstack(fill_value=0)
        
        if len(course_cohort_gpa.columns) > 1:
            course_cohort_gpa.plot(kind='bar', ax=ax9, color=CONFIG['colors'])
            ax9.set_xlabel('Course')
            ax9.set_ylabel('Average GPA')
            ax9.set_title('Average GPA by Course and Cohort')
            ax9.legend(title='Cohort', bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
            plt.xticks(rotation=45)
        
        plt.tight_layout(rect=[0, 0, 1, 0.95])

        # Build detailed cohort analysis summary
        summary_text = "\n" + "="*60 + "\n"
        summary_text += "COHORT ANALYSIS SUMMARY\n"
        summary_text += "="*60 + "\n"

        summary_text += f"Total cohorts analyzed: {len(cohort_sizes)}\n"
        summary_text += f"Average cohort size: {cohort_sizes.mean():.1f} students\n"
        summary_text += f"Largest cohort: {cohort_sizes.max()} students\n"
        summary_text += f"Smallest cohort: {cohort_sizes.min()} students\n"

        summary_text += f"\nOverall Metrics:\n"
        overall_retention = (students_df['completion_status'].isin(['Active', 'Completed'])).mean() * 100
        overall_completion = (students_df['completion_status'] == 'Completed').mean() * 100
        overall_dropout = (students_df['completion_status'] == 'Dropped').mean() * 100

        summary_text += f"  Retention rate: {overall_retention:.1f}%\n"
        summary_text += f"  Completion rate: {overall_completion:.1f}%\n"
        summary_text += f"  Dropout rate: {overall_dropout:.1f}%\n"

        if not completed_students.empty:
            summary_text += f"  Average time to completion: {completed_students['months_since_registration'].mean():.1f} months\n"

        summary_text += f"\nBest Performing Cohorts (by completion rate):\n"
        top_cohorts = cohort_completion.nlargest(3)
        for cohort, rate in top_cohorts.items():
            summary_text += f"  {cohort}: {rate:.1f}% completion rate\n"

        summary_text += f"\nCohorts Needing Attention (lowest retention):\n"
        low_retention_cohorts = cohort_retention.nsmallest(3)
        for cohort, rate in low_retention_cohorts.items():
            summary_text += f"  {cohort}: {rate:.1f}% retention rate\n"

        # In GUI mode, return data for the GUI to display
        if self.gui_mode:
            return {
                'figure': fig,
                'summary': summary_text,
                'title': 'Cohort Analysis'
            }

        # In CLI mode, print and handle display
        print(summary_text)
        self.save_or_display_plot(fig, "cohort_analysis")

    def analyze_performance_trends(self):
        """Analyze student performance trends over time"""
        students_df = self.get_all_students(self.custom_filters)
        modules_df = self.get_all_modules(self.custom_filters)
        
        if students_df.empty:
            print("No student data available for performance trend analysis.")
            return
        
        # Clean data and handle missing values
        students_df = students_df.dropna(subset=['registration_datetime', 'gpa'])
        
        if students_df.empty:
            print("No valid registration or GPA data available for trend analysis.")
            return
        
        print("\nGenerating Performance Trends Analysis...")
        
        # Prepare time-based data with error handling
        try:
            students_df['registration_date'] = pd.to_datetime(students_df['registration_datetime'])
            students_df['year_month'] = students_df['registration_date'].dt.to_period('M')
        except Exception as e:
            print(f"Error processing dates: {e}")
            return
        
        # Remove any rows with invalid dates
        students_df = students_df.dropna(subset=['year_month'])
        
        if students_df.empty:
            print("No valid date data available for trend analysis.")
            return
        
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Student Performance Trends Analysis', fontsize=20)
        
        # 1. GPA Trends Over Time
        ax1 = fig.add_subplot(331)
        monthly_gpa = students_df.groupby('year_month')['gpa'].mean().dropna()
        
        if len(monthly_gpa) > 0:
            ax1.plot(range(len(monthly_gpa)), monthly_gpa.values, marker='o', 
                    color=CONFIG['colors'][0], linewidth=2)
            ax1.set_xlabel('Time Period')
            ax1.set_ylabel('Average GPA')
            ax1.set_title('GPA Trends Over Time')
            
            # Set x-axis labels with proper bounds checking
            if len(monthly_gpa) > 1:
                step = max(1, len(monthly_gpa) // 5)
                tick_positions = list(range(0, len(monthly_gpa), step))
                if tick_positions[-1] != len(monthly_gpa) - 1:
                    tick_positions.append(len(monthly_gpa) - 1)
                ax1.set_xticks(tick_positions)
                ax1.set_xticklabels([str(monthly_gpa.index[i]) for i in tick_positions], rotation=45)
            
            # Add trend line only if we have enough data points
            if len(monthly_gpa) > 2:
                try:
                    z = np.polyfit(range(len(monthly_gpa)), monthly_gpa.values, 1)
                    p = np.poly1d(z)
                    ax1.plot(range(len(monthly_gpa)), p(range(len(monthly_gpa))),
                            "r--", alpha=0.8, label=f'Trend: {z[0]:.4f}/month')
                    ax1.legend()
                except (ValueError, np.linalg.LinAlgError):
                    pass  # Skip trend line if fitting fails
        else:
            ax1.text(0.5, 0.5, 'No valid GPA data', ha='center', va='center', transform=ax1.transAxes)
            ax1.set_title('GPA Trends Over Time (No Data)')
        
        # 2. Engagement Trends
        ax2 = fig.add_subplot(332)
        if 'engagement_score' in students_df.columns and not students_df['engagement_score'].isna().all():
            monthly_engagement = students_df.groupby('year_month')['engagement_score'].mean().dropna()
            if len(monthly_engagement) > 0:
                ax2.plot(range(len(monthly_engagement)), monthly_engagement.values, marker='s', 
                        color=CONFIG['colors'][1], linewidth=2)
                ax2.set_xlabel('Time Period')
                ax2.set_ylabel('Average Engagement Score')
                ax2.set_title('Engagement Trends Over Time')
                
                if len(monthly_engagement) > 1:
                    step = max(1, len(monthly_engagement) // 5)
                    tick_positions = list(range(0, len(monthly_engagement), step))
                    if tick_positions[-1] != len(monthly_engagement) - 1:
                        tick_positions.append(len(monthly_engagement) - 1)
                    ax2.set_xticks(tick_positions)
                    ax2.set_xticklabels([str(monthly_engagement.index[i]) for i in tick_positions], rotation=45)
            else:
                ax2.text(0.5, 0.5, 'No valid engagement data', ha='center', va='center', transform=ax2.transAxes)
        else:
            ax2.text(0.5, 0.5, 'Engagement score not available', ha='center', va='center', transform=ax2.transAxes)
            ax2.set_title('Engagement Trends Over Time (No Data)')
        
        # 3. Pass Rate Trends
        ax3 = fig.add_subplot(333)
        monthly_pass_rate = students_df.groupby('year_month').apply(
            lambda x: (x['overall_grade'] != 'F').mean() * 100
        ).dropna()
        
        if len(monthly_pass_rate) > 0:
            ax3.plot(range(len(monthly_pass_rate)), monthly_pass_rate.values, marker='^', 
                    color='green', linewidth=2)
            ax3.set_xlabel('Time Period')
            ax3.set_ylabel('Pass Rate (%)')
            ax3.set_title('Pass Rate Trends Over Time')
            ax3.set_ylim(0, 100)
            
            if len(monthly_pass_rate) > 1:
                step = max(1, len(monthly_pass_rate) // 5)
                tick_positions = list(range(0, len(monthly_pass_rate), step))
                if tick_positions[-1] != len(monthly_pass_rate) - 1:
                    tick_positions.append(len(monthly_pass_rate) - 1)
                ax3.set_xticks(tick_positions)
                ax3.set_xticklabels([str(monthly_pass_rate.index[i]) for i in tick_positions], rotation=45)
        else:
            ax3.text(0.5, 0.5, 'No valid pass rate data', ha='center', va='center', transform=ax3.transAxes)
            ax3.set_title('Pass Rate Trends Over Time (No Data)')
        
        # 4. Course Performance Comparison Over Time
        ax4 = fig.add_subplot(334)
        if 'course' in students_df.columns:
            courses_plotted = 0
            for course in students_df['course'].unique():
                if pd.notna(course):
                    course_data = students_df[students_df['course'] == course]
                    course_monthly_gpa = course_data.groupby('year_month')['gpa'].mean().dropna()
                    if len(course_monthly_gpa) > 0:
                        ax4.plot(range(len(course_monthly_gpa)), course_monthly_gpa.values, 
                                marker='o', label=course, linewidth=2)
                        courses_plotted += 1
            
            if courses_plotted > 0:
                ax4.set_xlabel('Time Period')
                ax4.set_ylabel('Average GPA')
                ax4.set_title('GPA Trends by Course')
                ax4.legend()
            else:
                ax4.text(0.5, 0.5, 'No valid course data', ha='center', va='center', transform=ax4.transAxes)
        else:
            ax4.text(0.5, 0.5, 'Course column not available', ha='center', va='center', transform=ax4.transAxes)
            ax4.set_title('GPA Trends by Course (No Data)')
        
        # 5. Grade Distribution Evolution
        ax5 = fig.add_subplot(335)
        if len(monthly_gpa) >= 3:  # Need at least 3 periods for comparison
            # Calculate grade distribution for recent vs older cohorts
            recent_cutoff = monthly_gpa.index[max(0, len(monthly_gpa) - 3)]
            students_df['cohort_type'] = students_df['year_month'].apply(
                lambda x: 'Recent' if x >= recent_cutoff else 'Older'
            )
            
            try:
                grade_evolution = pd.crosstab(students_df['cohort_type'], students_df['overall_grade'], normalize='index') * 100
                if not grade_evolution.empty:
                    grade_evolution.plot(kind='bar', ax=ax5, color=CONFIG['colors'])
                    ax5.set_xlabel('Cohort Type')
                    ax5.set_ylabel('Percentage of Students')
                    ax5.set_title('Grade Distribution: Recent vs Older Cohorts')
                    ax5.legend(title='Grade')
                    plt.setp(ax5.xaxis.get_majorticklabels(), rotation=0)
                else:
                    ax5.text(0.5, 0.5, 'No valid grade data', ha='center', va='center', transform=ax5.transAxes)
            except (ValueError, KeyError, TypeError):
                ax5.text(0.5, 0.5, 'Error processing grade data', ha='center', va='center', transform=ax5.transAxes)
        else:
            ax5.text(0.5, 0.5, 'Insufficient data for cohort comparison', ha='center', va='center', transform=ax5.transAxes)
            ax5.set_title('Grade Distribution: Recent vs Older Cohorts (Insufficient Data)')
        
        # 6. Performance Variability
        ax6 = fig.add_subplot(336)
        monthly_gpa_std = students_df.groupby('year_month')['gpa'].std().dropna()
        if len(monthly_gpa_std) > 0:
            ax6.plot(range(len(monthly_gpa_std)), monthly_gpa_std.values, marker='d', 
                    color='red', linewidth=2)
            ax6.set_xlabel('Time Period')
            ax6.set_ylabel('GPA Standard Deviation')
            ax6.set_title('Performance Variability Over Time')
            
            if len(monthly_gpa_std) > 1:
                step = max(1, len(monthly_gpa_std) // 5)
                tick_positions = list(range(0, len(monthly_gpa_std), step))
                if tick_positions[-1] != len(monthly_gpa_std) - 1:
                    tick_positions.append(len(monthly_gpa_std) - 1)
                ax6.set_xticks(tick_positions)
                ax6.set_xticklabels([str(monthly_gpa_std.index[i]) for i in tick_positions], rotation=45)
        else:
            ax6.text(0.5, 0.5, 'No valid variability data', ha='center', va='center', transform=ax6.transAxes)
            ax6.set_title('Performance Variability Over Time (No Data)')
        
        # 7. Age Group Performance Trends
        ax7 = fig.add_subplot(337)
        if 'age' in students_df.columns and not students_df['age'].isna().all():
            students_df['age_group'] = pd.cut(students_df['age'], bins=[0, 25, 35, 45, 100], 
                                             labels=['18-25', '26-35', '36-45', '46+'])
            
            age_groups_plotted = 0
            for age_group in students_df['age_group'].unique():
                if pd.notna(age_group):
                    age_data = students_df[students_df['age_group'] == age_group]
                    age_monthly_gpa = age_data.groupby('year_month')['gpa'].mean().dropna()
                    if len(age_monthly_gpa) > 0:
                        ax7.plot(range(len(age_monthly_gpa)), age_monthly_gpa.values, 
                                marker='o', label=age_group, linewidth=2)
                        age_groups_plotted += 1
            
            if age_groups_plotted > 0:
                ax7.set_xlabel('Time Period')
                ax7.set_ylabel('Average GPA')
                ax7.set_title('GPA Trends by Age Group')
                ax7.legend()
            else:
                ax7.text(0.5, 0.5, 'No valid age group data', ha='center', va='center', transform=ax7.transAxes)
        else:
            ax7.text(0.5, 0.5, 'Age column not available', ha='center', va='center', transform=ax7.transAxes)
            ax7.set_title('GPA Trends by Age Group (No Data)')
        
        # 8. Seasonal Performance Patterns
        ax8 = fig.add_subplot(338)
        try:
            students_df['registration_month'] = students_df['registration_date'].dt.month
            monthly_performance = students_df.groupby('registration_month').agg({
                'gpa': 'mean'
            }).dropna()
            
            if 'engagement_score' in students_df.columns:
                monthly_performance['engagement_score'] = students_df.groupby('registration_month')['engagement_score'].mean()
            
            if not monthly_performance.empty:
                months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                month_labels = [months[i-1] for i in monthly_performance.index]
                
                x = range(len(monthly_performance))
                width = 0.35
                ax8.bar([i - width/2 for i in x], monthly_performance['gpa'], width, 
                       label='Avg GPA', color=CONFIG['colors'][0])
                
                if 'engagement_score' in monthly_performance.columns:
                    ax8_twin = ax8.twinx()
                    ax8_twin.bar([i + width/2 for i in x], monthly_performance['engagement_score'], width, 
                                label='Avg Engagement', color=CONFIG['colors'][1], alpha=0.7)
                    ax8_twin.set_ylabel('Average Engagement Score')
                    ax8_twin.legend(loc='upper right')
                
                ax8.set_xlabel('Registration Month')
                ax8.set_ylabel('Average GPA')
                ax8.set_title('Seasonal Performance Patterns')
                ax8.set_xticks(x)
                ax8.set_xticklabels(month_labels)
                ax8.legend(loc='upper left')
            else:
                ax8.text(0.5, 0.5, 'No seasonal data available', ha='center', va='center', transform=ax8.transAxes)
        except Exception as e:
            ax8.text(0.5, 0.5, f'Error processing seasonal data', ha='center', va='center', transform=ax8.transAxes)
            ax8.set_title('Seasonal Performance Patterns (Error)')
        
        # 9. Performance Improvement/Decline Analysis
        ax9 = fig.add_subplot(339)
        
        # Calculate performance changes only if we have sufficient data
        if len(monthly_gpa) >= 6:  # Need at least 6 months of data
            try:
                recent_avg = monthly_gpa.tail(3).mean()
                earlier_avg = monthly_gpa.head(3).mean()
                improvement = recent_avg - earlier_avg
                
                # Create performance trajectory visualization
                categories = {
                    'Significantly Improved': (improvement > 0.3),
                    'Slightly Improved': (improvement > 0.1) and (improvement <= 0.3),
                    'Stable': abs(improvement) <= 0.1,
                    'Slightly Declined': (improvement < -0.1) and (improvement >= -0.3),
                    'Significantly Declined': (improvement < -0.3)
                }
                
                colors = ['darkgreen', 'lightgreen', 'yellow', 'orange', 'red']
                values = [1 if condition else 0 for condition in categories.values()]
                
                ax9.bar(range(len(categories)), values, color=colors, alpha=0.7)
                ax9.set_xticks(range(len(categories)))
                ax9.set_xticklabels(list(categories.keys()), rotation=45, ha='right')
                ax9.set_ylabel('Performance Status')
                ax9.set_title('Overall Performance Trajectory')
                ax9.set_ylim(0, 1.2)
                
                # Add improvement value as text
                if not (np.isnan(improvement) or np.isinf(improvement)):
                    ax9.text(0.5, 0.8, f'Overall Change: {improvement:+.3f} GPA points', 
                            transform=ax9.transAxes, ha='center', fontsize=12, 
                            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
            except Exception as e:
                ax9.text(0.5, 0.5, 'Error calculating trajectory', ha='center', va='center', transform=ax9.transAxes)
        else:
            ax9.text(0.5, 0.5, 'Insufficient data for trajectory analysis\n(Need at least 6 months)', 
                    ha='center', va='center', transform=ax9.transAxes)
            ax9.set_title('Performance Trajectory (Insufficient Data)')
        
        plt.tight_layout(rect=[0, 0, 1, 0.95])

        # Build detailed performance trends summary
        summary_text = "\n" + "="*60 + "\n"
        summary_text += "PERFORMANCE TRENDS SUMMARY\n"
        summary_text += "="*60 + "\n"

        if len(monthly_gpa) > 0:
            summary_text += f"Analysis Period: {monthly_gpa.index[0]} to {monthly_gpa.index[-1]}\n"
            summary_text += f"Number of periods analyzed: {len(monthly_gpa)}\n"

            summary_text += f"\nOverall Trends:\n"
            if len(monthly_gpa) > 1:
                gpa_change = monthly_gpa.iloc[-1] - monthly_gpa.iloc[0]
                summary_text += f"  GPA change over period: {gpa_change:+.3f}\n"

                if 'engagement_score' in students_df.columns and len(monthly_engagement) > 1:
                    engagement_change = monthly_engagement.iloc[-1] - monthly_engagement.iloc[0]
                    summary_text += f"  Engagement change over period: {engagement_change:+.1f}\n"
                    engagement_trend = "improving" if engagement_change > 2 else "declining" if engagement_change < -2 else "stable"
                    summary_text += f"  Engagement trend: {engagement_trend}\n"

                gpa_trend = "improving" if gpa_change > 0.05 else "declining" if gpa_change < -0.05 else "stable"
                summary_text += f"  GPA trend: {gpa_trend}\n"

            summary_text += f"\nPerformance Statistics:\n"
            summary_text += f"  Highest monthly GPA: {monthly_gpa.max():.3f}\n"
            summary_text += f"  Lowest monthly GPA: {monthly_gpa.min():.3f}\n"
            summary_text += f"  Current GPA: {monthly_gpa.iloc[-1]:.3f}\n"
            summary_text += f"  GPA volatility (std dev): {monthly_gpa.std():.3f}\n"

            summary_text += f"\nCourse Performance Comparison:\n"
            current_period = monthly_gpa.index[-1]
            current_students = students_df[students_df['year_month'] == current_period]
            if not current_students.empty and 'course' in current_students.columns:
                current_course_performance = current_students.groupby('course')['gpa'].mean().dropna()
                for course, gpa in current_course_performance.items():
                    summary_text += f"  {course}: {gpa:.3f} current GPA\n"
            else:
                summary_text += "  No current course performance data available\n"
        else:
            summary_text += "No valid data available for trend analysis.\n"

        # In GUI mode, return data for the GUI to display
        if self.gui_mode:
            return {
                'figure': fig,
                'summary': summary_text,
                'title': 'Performance Trends Analysis'
            }

        # In CLI mode, print and handle display
        print(summary_text)
        self.save_or_display_plot(fig, "performance_trends")
    
    def analyze_module_popularity(self):
        """Enhanced module popularity analysis"""
        modules_df = self.get_all_modules(self.custom_filters)
        
        if modules_df.empty:
            print("No module data available for analysis.")
            return
        
        print("\nGenerating Enhanced Module Popularity Analysis...")
        
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Enhanced Module Popularity Analysis', fontsize=20)
        
        # 1. Top Popular Modules
        ax1 = fig.add_subplot(331)
        valid_module_names = modules_df[modules_df['module_name'].notna()]
        if not valid_module_names.empty:
            module_counts = valid_module_names['module_name'].value_counts().head(15)
            if not module_counts.empty:
                ax1.barh(range(len(module_counts)), module_counts.values, color=CONFIG['colors'][0])
                ax1.set_yticks(range(len(module_counts)))
                ax1.set_yticklabels(module_counts.index, fontsize=8)
                ax1.set_xlabel('Number of Students')
                ax1.set_title('Top 15 Most Popular Modules')
            else:
                ax1.text(0.5, 0.5, 'No module data available',
                        ha='center', va='center', transform=ax1.transAxes)
                ax1.set_title('Top 15 Most Popular Modules')
        else:
            ax1.text(0.5, 0.5, 'No valid module names',
                    ha='center', va='center', transform=ax1.transAxes)
            ax1.set_title('Top 15 Most Popular Modules')
        
        # 2. Module Type Distribution with Performance
        ax2 = fig.add_subplot(332)
        # Filter out rows with missing module_type before grouping
        modules_with_type = modules_df[modules_df['module_type'].notna()]
        if not modules_with_type.empty:
            type_stats = modules_with_type.groupby('module_type').agg({
                'student_id': 'count',
                'module_grade': lambda x: (x.isin(['A', 'B'])).mean() * 100
            })
            type_stats.columns = ['Enrollment', 'Success_Rate']

            if not type_stats.empty:
                x = range(len(type_stats))
                width = 0.35
                ax2.bar([i - width/2 for i in x], type_stats['Enrollment'], width,
                       label='Enrollment', color=CONFIG['colors'][0])
                ax2_twin = ax2.twinx()
                ax2_twin.bar([i + width/2 for i in x], type_stats['Success_Rate'], width,
                            label='Success Rate (%)', color=CONFIG['colors'][1], alpha=0.7)

                ax2.set_xlabel('Module Type')
                ax2.set_ylabel('Number of Enrollments')
                ax2_twin.set_ylabel('Success Rate (%)')
                ax2.set_title('Module Type: Enrollment vs Success Rate')
                ax2.set_xticks(x)
                ax2.set_xticklabels(type_stats.index)
                ax2.legend(loc='upper left')
                ax2_twin.legend(loc='upper right')
            else:
                ax2.text(0.5, 0.5, 'No module type statistics available',
                        ha='center', va='center', transform=ax2.transAxes)
                ax2.set_title('Module Type: Enrollment vs Success Rate')
        else:
            ax2.text(0.5, 0.5, 'No module type data available',
                    ha='center', va='center', transform=ax2.transAxes)
            ax2.set_title('Module Type: Enrollment vs Success Rate')
        
        # 3. Module Popularity Trends
        ax3 = fig.add_subplot(333)
        if 'registration_datetime' in modules_df.columns:
            modules_df['reg_month'] = pd.to_datetime(modules_df['registration_datetime']).dt.to_period('M')
            monthly_enrollments = modules_df.groupby('reg_month').size()
            ax3.plot(range(len(monthly_enrollments)), monthly_enrollments.values, 
                    marker='o', color=CONFIG['colors'][2], linewidth=2)
            ax3.set_xlabel('Time Period')
            ax3.set_ylabel('Total Module Enrollments')
            ax3.set_title('Module Enrollment Trends')
            ax3.set_xticks(range(0, len(monthly_enrollments), max(1, len(monthly_enrollments)//5)))
            ax3.set_xticklabels([str(monthly_enrollments.index[i]) for i in range(0, len(monthly_enrollments), max(1, len(monthly_enrollments)//5))], rotation=45)
        
        # 4. Course-specific Module Preferences
        ax4 = fig.add_subplot(334)
        # Filter out rows with missing course or module_type before grouping
        valid_modules = modules_df[modules_df['course'].notna() & modules_df['module_type'].notna()]
        if not valid_modules.empty:
            course_module_prefs = valid_modules.groupby(['course', 'module_type']).size().unstack(fill_value=0)
            # Check for numeric data and non-empty DataFrame
            if not course_module_prefs.empty and len(course_module_prefs.columns) > 0 and course_module_prefs.select_dtypes(include='number').shape[1] > 0:
                course_module_prefs.plot(kind='bar', stacked=True, ax=ax4, color=CONFIG['colors'])
                ax4.set_xlabel('Course')
                ax4.set_ylabel('Number of Module Enrollments')
                ax4.set_title('Module Type Preferences by Course')
                ax4.legend(title='Module Type')
                plt.xticks(rotation=45)
            else:
                ax4.text(0.5, 0.5, 'No module preference data available',
                        ha='center', va='center', transform=ax4.transAxes)
                ax4.set_title('Module Type Preferences by Course')
        else:
            ax4.text(0.5, 0.5, 'No valid course/module data available',
                    ha='center', va='center', transform=ax4.transAxes)
            ax4.set_title('Module Type Preferences by Course')
        
        # 5. Module Difficulty vs Popularity
        ax5 = fig.add_subplot(335)
        # Filter modules with valid module_name and difficulty_rating
        valid_for_difficulty = modules_df[modules_df['module_name'].notna() & modules_df['difficulty_rating'].notna()]
        if not valid_for_difficulty.empty:
            module_analysis = valid_for_difficulty.groupby('module_name').agg({
                'student_id': 'count',
                'difficulty_rating': 'mean',
                'module_grade': lambda x: (x.isin(['A', 'B'])).mean() * 100
            })
            module_analysis.columns = ['Enrollment', 'Avg_Difficulty', 'Success_Rate']
            # Drop rows with NaN values for scatter plot
            module_analysis = module_analysis.dropna()

            if not module_analysis.empty:
                scatter = ax5.scatter(module_analysis['Avg_Difficulty'], module_analysis['Enrollment'],
                                     s=module_analysis['Success_Rate']*3 + 1, alpha=0.6,
                                     c=module_analysis['Success_Rate'], cmap='RdYlGn')
                ax5.set_xlabel('Average Difficulty Rating')
                ax5.set_ylabel('Enrollment Count')
                ax5.set_title('Module Difficulty vs Popularity (sized by success rate)')
                plt.colorbar(scatter, ax=ax5, label='Success Rate (%)')
            else:
                ax5.text(0.5, 0.5, 'No valid difficulty/enrollment data',
                        ha='center', va='center', transform=ax5.transAxes)
                ax5.set_title('Module Difficulty vs Popularity')
        else:
            ax5.text(0.5, 0.5, 'No module difficulty data available',
                    ha='center', va='center', transform=ax5.transAxes)
            ax5.set_title('Module Difficulty vs Popularity')
        
        # 6. Attendance Impact on Module Choice
        ax6 = fig.add_subplot(336)
        # Filter for valid module_type and attendance_rate
        valid_attendance = modules_df[modules_df['module_type'].notna() & modules_df['attendance_rate'].notna()]
        if not valid_attendance.empty:
            attendance_module = valid_attendance.groupby('module_type')['attendance_rate'].mean()
            if not attendance_module.empty:
                ax6.bar(attendance_module.index, attendance_module.values, color=CONFIG['colors'], alpha=0.7)
                ax6.set_xlabel('Module Type')
                ax6.set_ylabel('Average Attendance Rate (%)')
                ax6.set_title('Average Attendance by Module Type')
            else:
                ax6.text(0.5, 0.5, 'No attendance data by module type',
                        ha='center', va='center', transform=ax6.transAxes)
                ax6.set_title('Average Attendance by Module Type')
        else:
            ax6.text(0.5, 0.5, 'No valid attendance data available',
                    ha='center', va='center', transform=ax6.transAxes)
            ax6.set_title('Average Attendance by Module Type')

        # 7. Module Completion Rates
        ax7 = fig.add_subplot(337)
        # Filter for valid module_name and module_completion
        valid_completion = modules_df[modules_df['module_name'].notna() & modules_df['module_completion'].notna()]
        if not valid_completion.empty:
            completion_rates = valid_completion.groupby('module_name').apply(
                lambda x: (x['module_completion'] == 'Completed').mean() * 100
            ).sort_values(ascending=False).head(10)

            if not completion_rates.empty:
                ax7.barh(range(len(completion_rates)), completion_rates.values, color='green', alpha=0.7)
                ax7.set_yticks(range(len(completion_rates)))
                ax7.set_yticklabels(completion_rates.index, fontsize=8)
                ax7.set_xlabel('Completion Rate (%)')
                ax7.set_title('Top 10 Modules by Completion Rate')
            else:
                ax7.text(0.5, 0.5, 'No completion rate data available',
                        ha='center', va='center', transform=ax7.transAxes)
                ax7.set_title('Top 10 Modules by Completion Rate')
        else:
            ax7.text(0.5, 0.5, 'No valid completion data available',
                    ha='center', va='center', transform=ax7.transAxes)
            ax7.set_title('Top 10 Modules by Completion Rate')
        
        # 8. Module Co-enrollment Analysis
        ax8 = fig.add_subplot(338)
        
        # Find most common module combinations
        student_modules = modules_df.groupby('student_id')['module_name'].apply(list)
        module_pairs = {}
        
        for modules_list in student_modules:
            if len(modules_list) > 1:
                for i in range(len(modules_list)):
                    for j in range(i+1, len(modules_list)):
                        pair = tuple(sorted([modules_list[i], modules_list[j]]))
                        module_pairs[pair] = module_pairs.get(pair, 0) + 1
        
        if module_pairs:
            top_pairs = sorted(module_pairs.items(), key=lambda x: x[1], reverse=True)[:10]
            pair_names = [f"{pair[0][:10]}+\n{pair[1][:10]}" for pair, count in top_pairs]
            pair_counts = [count for pair, count in top_pairs]
            
            ax8.bar(range(len(pair_counts)), pair_counts, color=CONFIG['colors'][3], alpha=0.7)
            ax8.set_xticks(range(len(pair_names)))
            ax8.set_xticklabels(pair_names, rotation=45, ha='right', fontsize=8)
            ax8.set_ylabel('Co-enrollment Count')
            ax8.set_title('Most Common Module Combinations')
        
        # 9. Module Recommendation Matrix
        ax9 = fig.add_subplot(339)

        # Filter for valid module data
        valid_for_recommendation = modules_df[modules_df['module_name'].notna()]
        if not valid_for_recommendation.empty:
            # Create a simple recommendation score based on multiple factors
            module_scores = valid_for_recommendation.groupby('module_name').agg({
                'student_id': 'count',  # Popularity
                'module_grade': lambda x: (x.isin(['A', 'B'])).mean(),  # Success rate
                'attendance_rate': 'mean',  # Engagement
                'difficulty_rating': lambda x: 5 - x.mean() if x.notna().any() else 2.5  # Inverse difficulty
            })

            if not module_scores.empty:
                # Normalize scores with division-by-zero protection
                for col in module_scores.columns:
                    col_min = module_scores[col].min()
                    col_max = module_scores[col].max()
                    col_range = col_max - col_min
                    if col_range != 0:
                        module_scores[col] = (module_scores[col] - col_min) / col_range
                    else:
                        module_scores[col] = 0.5  # Default to middle value if all same

                # Fill NaN values before calculating composite score
                module_scores = module_scores.fillna(0.5)

                # Calculate composite recommendation score
                module_scores['recommendation_score'] = (
                    module_scores['student_id'] * 0.3 +
                    module_scores['module_grade'] * 0.4 +
                    module_scores['attendance_rate'] * 0.2 +
                    module_scores['difficulty_rating'] * 0.1
                )

                top_recommended = module_scores.nlargest(15, 'recommendation_score')

                if not top_recommended.empty:
                    ax9.barh(range(len(top_recommended)), top_recommended['recommendation_score'],
                            color='gold', alpha=0.7)
                    ax9.set_yticks(range(len(top_recommended)))
                    ax9.set_yticklabels(top_recommended.index, fontsize=8)
                    ax9.set_xlabel('Recommendation Score')
                    ax9.set_title('Top Recommended Modules (Composite Score)')
                else:
                    ax9.text(0.5, 0.5, 'No recommendation data available',
                            ha='center', va='center', transform=ax9.transAxes)
                    ax9.set_title('Top Recommended Modules')
            else:
                ax9.text(0.5, 0.5, 'No module scores available',
                        ha='center', va='center', transform=ax9.transAxes)
                ax9.set_title('Top Recommended Modules')
        else:
            ax9.text(0.5, 0.5, 'No valid module data for recommendations',
                    ha='center', va='center', transform=ax9.transAxes)
            ax9.set_title('Top Recommended Modules')
        
        plt.tight_layout(rect=[0, 0, 1, 0.95])

        # Build detailed module popularity summary
        summary_text = "\n" + "="*60 + "\n"
        summary_text += "ENHANCED MODULE POPULARITY SUMMARY\n"
        summary_text += "="*60 + "\n"

        summary_text += f"Total unique modules: {modules_df['module_name'].nunique()}\n"
        summary_text += f"Total module enrollments: {len(modules_df)}\n"
        summary_text += f"Average enrollments per module: {len(modules_df) / modules_df['module_name'].nunique():.1f}\n"

        summary_text += f"\nTop 5 Most Popular Modules:\n"
        for i, (module, count) in enumerate(module_counts.head(5).items()):
            success_rate = (modules_df[modules_df['module_name'] == module]['module_grade'].isin(['A', 'B'])).mean() * 100
            summary_text += f"  {i+1}. {module}: {count} students, {success_rate:.1f}% success rate\n"

        summary_text += f"\nModule Type Performance:\n"
        for module_type, stats in type_stats.iterrows():
            summary_text += f"  {module_type}: {stats['Enrollment']} enrollments, {stats['Success_Rate']:.1f}% success rate\n"

        summary_text += f"\nTop Recommended Modules:\n"
        for i, (module, score) in enumerate(top_recommended.head(5)['recommendation_score'].items()):
            enrollment = modules_df[modules_df['module_name'] == module]['student_id'].count()
            summary_text += f"  {i+1}. {module}: Score {score:.3f}, {enrollment} students\n"

        if module_pairs:
            summary_text += f"\nMost Common Module Combinations:\n"
            for i, (pair, count) in enumerate(top_pairs[:3]):
                summary_text += f"  {i+1}. {pair[0]} + {pair[1]}: {count} students\n"

        # In GUI mode, return data for the GUI to display
        if self.gui_mode:
            return {
                'figure': fig,
                'summary': summary_text,
                'title': 'Enhanced Module Popularity Analysis'
            }

        # In CLI mode, print and handle display
        print(summary_text)
        self.save_or_display_plot(fig, "enhanced_module_popularity")

    def custom_report_builder(self):
        """Interactive custom report builder"""
        print("\n" + "="*60)
        print("CUSTOM REPORT BUILDER")
        print("="*60)
        
        print("Available report components:")
        components = {
            '1': 'Student Demographics',
            '2': 'Grade Distribution',
            '3': 'Module Popularity',
            '4': 'Performance Trends',
            '5': 'Engagement Analysis',
            '6': 'Risk Assessment',
            '7': 'Cohort Analysis',
            '8': 'Correlation Analysis'
        }
        
        for key, value in components.items():
            print(f"  {key}. {value}")
        
        selected = input("\nSelect components (comma-separated, e.g., 1,3,5): ").split(',')
        
        # Get report parameters
        report_name = input("Enter report name: ") or "Custom_Report"
        include_summary = input("Include executive summary? (y/n): ").lower() == 'y'
        
        print(f"\nGenerating custom report: {report_name}...")
        
        # Create custom report
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.reports_dir}/{report_name}_{timestamp}.pdf"
        
        with PdfPages(filename) as pdf:
            # Title page
            plt.figure(figsize=(12, 8))
            plt.axis('off')
            plt.text(0.5, 0.6, f'Custom Analytics Report: {report_name}', 
                    horizontalalignment='center', verticalalignment='center', fontsize=24)
            plt.text(0.5, 0.5, f'Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 
                    horizontalalignment='center', verticalalignment='center', fontsize=14)
            plt.text(0.5, 0.4, f'Components: {", ".join([components[s.strip()] for s in selected if s.strip() in components])}', 
                    horizontalalignment='center', verticalalignment='center', fontsize=12)
            pdf.savefig()
            plt.close()
            
            # Generate selected components
            for component in selected:
                component = component.strip()
                if component in components:
                    print(f"Adding {components[component]}...")
                    
                    if component == '1':
                        self.analyze_student_demographics()
                    elif component == '2':
                        self.analyze_grade_distribution()
                    elif component == '3':
                        self.analyze_module_popularity()
                    elif component == '4':
                        self.analyze_performance_trends()
                    elif component == '5':
                        self.analyze_engagement()
                    elif component == '6':
                        self.analyze_academic_risk()
                    elif component == '7':
                        self.analyze_cohorts()
                    elif component == '8':
                        self.analyze_correlations()
                    
                    # Save current figure to PDF
                    pdf.savefig()
                    plt.close()
        
        print(f"\nCustom report generated: {filename}")

    def export_data(self):
        """Enhanced data export functionality"""
        print("\n" + "="*60)
        print("DATA EXPORT OPTIONS")
        print("="*60)
        
        print("Available export formats:")
        print("1. Excel (with multiple sheets)")
        print("2. CSV (separate files)")
        print("3. JSON")
        print("4. Statistical Summary Report")
        
        choice = input("Select export format (1-4): ")
        
        students_df = self.get_all_students(self.custom_filters)
        modules_df = self.get_all_modules(self.custom_filters)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if choice == '1':
            # Excel export with multiple sheets
            filename = f"{self.reports_dir}/student_data_export_{timestamp}.xlsx"
            
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                # Student data
                students_df.to_excel(writer, sheet_name='Students', index=False)
                
                # Module data
                if not modules_df.empty:
                    modules_df.to_excel(writer, sheet_name='Modules', index=False)
                
                # Summary statistics
                summary_data = {
                    'Metric': ['Total Students', 'Average GPA', 'Average Engagement', 'Completion Rate'],
                    'Value': [
                        len(students_df),
                        students_df['gpa'].mean(),
                        students_df['engagement_score'].mean(),
                        (students_df['completion_status'] == 'Completed').mean() * 100
                    ]
                }
                pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
                
                # Course breakdown
                course_summary = students_df.groupby('course').agg({
                    'student_id': 'count',
                    'gpa': 'mean',
                    'engagement_score': 'mean'
                }).round(2)
                course_summary.to_excel(writer, sheet_name='Course_Summary')
            
            print(f"Excel export completed: {filename}")
            
        elif choice == '2':
            # CSV export
            students_filename = f"{self.reports_dir}/students_{timestamp}.csv"
            students_df.to_csv(students_filename, index=False)
            print(f"Students CSV exported: {students_filename}")
            
            if not modules_df.empty:
                modules_filename = f"{self.reports_dir}/modules_{timestamp}.csv"
                modules_df.to_csv(modules_filename, index=False)
                print(f"Modules CSV exported: {modules_filename}")
            
        elif choice == '3':
            # JSON export
            filename = f"{self.reports_dir}/student_data_{timestamp}.json"
            export_data = {
                'students': students_df.to_dict('records'),
                'modules': modules_df.to_dict('records') if not modules_df.empty else [],
                'export_metadata': {
                    'timestamp': timestamp,
                    'total_students': len(students_df),
                    'total_modules': len(modules_df)
                }
            }
            
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            print(f"JSON export completed: {filename}")
            
        elif choice == '4':
            # Statistical summary report
            self.generate_statistical_summary_report(students_df, modules_df, timestamp)

    def generate_statistical_summary_report(self, students_df, modules_df, timestamp):
        """Generate comprehensive statistical summary report"""
        filename = f"{self.reports_dir}/statistical_summary_{timestamp}.txt"
        
        with open(filename, 'w') as f:
            f.write("COMPREHENSIVE STATISTICAL SUMMARY REPORT\n")
            f.write("="*60 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Student Statistics
            f.write("STUDENT DEMOGRAPHICS STATISTICS\n")
            f.write("-"*40 + "\n")
            f.write(f"Total Students: {len(students_df)}\n")
            f.write(f"Age - Mean: {students_df['age'].mean():.2f}, Median: {students_df['age'].median():.2f}, Std: {students_df['age'].std():.2f}\n")
            f.write(f"GPA - Mean: {students_df['gpa'].mean():.3f}, Median: {students_df['gpa'].median():.3f}, Std: {students_df['gpa'].std():.3f}\n")
            f.write(f"Engagement - Mean: {students_df['engagement_score'].mean():.2f}, Median: {students_df['engagement_score'].median():.2f}, Std: {students_df['engagement_score'].std():.2f}\n\n")
            
            # Gender distribution
            f.write("Gender Distribution:\n")
            gender_counts = students_df['gender'].value_counts()
            for gender, count in gender_counts.items():
                f.write(f"  {gender}: {count} ({count/len(students_df)*100:.1f}%)\n")
            f.write("\n")
            
            # Course distribution
            f.write("Course Distribution:\n")
            course_counts = students_df['course'].value_counts()
            for course, count in course_counts.items():
                f.write(f"  {course}: {count} ({count/len(students_df)*100:.1f}%)\n")
            f.write("\n")
            
            # Performance statistics
            f.write("PERFORMANCE STATISTICS\n")
            f.write("-"*40 + "\n")
            grade_counts = students_df['overall_grade'].value_counts()
            for grade in ['A', 'B', 'C', 'D', 'F']:
                if grade in grade_counts:
                    count = grade_counts[grade]
                    f.write(f"Grade {grade}: {count} ({count/len(students_df)*100:.1f}%)\n")
            
            pass_rate = (students_df['overall_grade'] != 'F').mean() * 100
            f.write(f"Overall Pass Rate: {pass_rate:.1f}%\n\n")
            
            # Module statistics
            if not modules_df.empty:
                f.write("MODULE STATISTICS\n")
                f.write("-"*40 + "\n")
                f.write(f"Total Module Enrollments: {len(modules_df)}\n")
                f.write(f"Unique Modules: {modules_df['module_name'].nunique()}\n")
                f.write(f"Average Modules per Student: {len(modules_df) / modules_df['student_id'].nunique():.1f}\n")
                
                module_type_counts = modules_df['module_type'].value_counts()
                f.write("Module Type Distribution:\n")
                for module_type, count in module_type_counts.items():
                    f.write(f"  {module_type}: {count} ({count/len(modules_df)*100:.1f}%)\n")
                f.write("\n")
            
            # Correlation analysis
            f.write("CORRELATION ANALYSIS\n")
            f.write("-"*40 + "\n")
            correlations = [
                ('Age vs GPA', students_df['age'].corr(students_df['gpa'])),
                ('Engagement vs GPA', students_df['engagement_score'].corr(students_df['gpa'])),
                ('Age vs Engagement', students_df['age'].corr(students_df['engagement_score']))
            ]
            
            for desc, corr in correlations:
                f.write(f"{desc}: {corr:.3f}\n")
        
        print(f"Statistical summary report generated: {filename}")

    def email_reports(self):
        """Email report functionality"""
        print("\n" + "="*60)
        print("EMAIL REPORTS")
        print("="*60)
        
        # Check if email configuration is set
        if not CONFIG['email_config']['sender_email']:
            print("Email configuration not set. Please configure email settings first.")
            print("Go to Configuration Settings to set up email.")
            return
        
        recipient = input("Enter recipient email address: ")
        subject = input("Enter email subject: ") or "Student Analytics Report"
        
        print("\nAvailable reports to send:")
        print("1. Latest complete analytics report")
        print("2. Summary statistics only")
        print("3. Generate and send custom report")
        
        choice = input("Select option (1-3): ")
        
        if choice == '1':
            self.send_email_with_attachment(recipient, subject, "complete_report")
        elif choice == '2':
            self.send_email_with_attachment(recipient, subject, "summary_only")
        elif choice == '3':
            self.custom_report_builder()
            self.send_email_with_attachment(recipient, subject, "custom_report")

    def send_email_with_attachment(self, recipient, subject, report_type):
        """Send email with report attachment"""
        try:
            from university_system.infrastructure.email.smtp import send_email_via_smtp
            from university_system.infrastructure.email.template_utils import render_template

            # Email body from template
            _, body = render_template("student_analytics_report", {
                "subject": subject,
                "report_type": report_type.replace('_', ' ').title(),
                "generated_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            if not body:
                body = "Please find attached the requested student analytics report."

            # Find latest report file
            report_files = []
            for file in os.listdir(self.reports_dir):
                if file.endswith('.pdf'):
                    report_files.append(os.path.join(self.reports_dir, file))

            attachments = None
            if report_files:
                latest_report = max(report_files, key=os.path.getctime)
                attachments = [latest_report]

            # Send email using centralized system
            current_time = datetime.now().isoformat()
            success = send_email_via_smtp(
                recipient_email=recipient,
                subject=subject,
                body=body,
                cc=None,
                bcc=None,
                attachments=attachments,
                current_time=current_time
            )

            if success:
                print(f"Email sent successfully to {recipient}")
            else:
                print(f"Failed to send email to {recipient}")

        except Exception as e:
            print(f"Failed to send email: {e}")
            print("Please check your email configuration and internet connection.")

    def data_quality_check(self):
        """Comprehensive data quality assessment"""
        print("\n" + "="*60)
        print("DATA QUALITY ASSESSMENT")
        print("="*60)
        
        students_df = self.get_all_students()
        modules_df = self.get_all_modules()
        
        print("Analyzing data quality...")
        
        # Student data quality checks
        print("\nSTUDENT DATA QUALITY:")
        print("-" * 30)
        
        total_students = len(students_df)
        print(f"Total student records: {total_students}")
        
        # Missing data analysis
        missing_data = students_df.isnull().sum()
        print("\nMissing data by field:")
        for field, count in missing_data.items():
            if count > 0:
                percentage = (count / total_students) * 100
                print(f"  {field}: {count} ({percentage:.1f}%)")
        
        # Data type validation
        print("\nData type validation:")
        expected_types = {
            'age': 'numeric',
            'gpa': 'numeric',
            'engagement_score': 'numeric'
        }
        
        for field, expected_type in expected_types.items():
            if field in students_df.columns:
                if expected_type == 'numeric':
                    non_numeric = pd.to_numeric(students_df[field], errors='coerce').isnull().sum()
                    if non_numeric > 0:
                        print(f"  {field}: {non_numeric} non-numeric values found")
                    else:
                        print(f"  {field}: All values are numeric ✓")
        
        # Range validation
        print("\nRange validation:")
        validations = [
            ('age', 16, 100),
            ('gpa', 0.0, 4.0),
            ('engagement_score', 0, 100)
        ]
        
        for field, min_val, max_val in validations:
            if field in students_df.columns:
                out_of_range = ((students_df[field] < min_val) | (students_df[field] > max_val)).sum()
                if out_of_range > 0:
                    print(f"  {field}: {out_of_range} values outside range [{min_val}, {max_val}]")
                else:
                    print(f"  {field}: All values within expected range ✓")
        
        # Duplicate detection
        duplicates = students_df.duplicated().sum()
        print(f"\nDuplicate records: {duplicates}")
        
        if duplicates > 0:
            print("  Action needed: Remove duplicate records")
        else:
            print("  No duplicates found ✓")
        
        # Module data quality (if available)
        if not modules_df.empty:
            print("\nMODULE DATA QUALITY:")
            print("-" * 30)
            
            total_modules = len(modules_df)
            print(f"Total module records: {total_modules}")
            
            # Check for orphaned modules (students not in student table)
            if 'student_id' in modules_df.columns and 'student_id' in students_df.columns:
                orphaned = ~modules_df['student_id'].isin(students_df['student_id'])
                orphaned_count = orphaned.sum()
                
                if orphaned_count > 0:
                    print(f"Orphaned module records: {orphaned_count}")
                    print("  Action needed: Clean up module records with invalid student IDs")
                else:
                    print("All module records have valid student IDs ✓")
        
        # Generate data quality score
        total_issues = missing_data.sum() + duplicates
        if not modules_df.empty and 'student_id' in modules_df.columns:
            orphaned_count = (~modules_df['student_id'].isin(students_df['student_id'])).sum()
            total_issues += orphaned_count
        
        quality_score = max(0, 100 - (total_issues / total_students * 10))
        
        print(f"\nOVERALL DATA QUALITY SCORE: {quality_score:.1f}/100")
        
        if quality_score >= 90:
            print("Status: Excellent data quality ✓")
        elif quality_score >= 75:
            print("Status: Good data quality - minor issues to address")
        elif quality_score >= 60:
            print("Status: Fair data quality - several issues need attention")
        else:
            print("Status: Poor data quality - significant cleanup required")
        
        print("\nRecommendations:")
        if missing_data.sum() > 0:
            print("- Address missing data in critical fields")
        if duplicates > 0:
            print("- Remove duplicate student records")
        if total_issues == 0:
            print("- Data quality is excellent, no immediate action required")

    def advanced_filtering(self):
        """Advanced filtering interface"""
        print("\n" + "="*60)
        print("ADVANCED FILTERING OPTIONS")
        print("="*60)
        
        students_df = self.get_all_students()
        
        print("Available filter criteria:")
        print("1. Age range")
        print("2. GPA range")
        print("3. Engagement score range")
        print("4. Course selection")
        print("5. Gender")
        print("6. Completion status")
        print("7. Registration date range")
        print("8. Clear all filters")
        print("9. Apply current filters and return")
        
        while True:
            choice = input("\nSelect filter option (1-9): ")
            
            if choice == '1':
                min_age = int(input("Minimum age: "))
                max_age = int(input("Maximum age: "))
                self.custom_filters['age_range'] = [min_age, max_age]
                print(f"Age filter applied: {min_age}-{max_age}")
                
            elif choice == '2':
                min_gpa = float(input("Minimum GPA: "))
                max_gpa = float(input("Maximum GPA: "))
                self.custom_filters['gpa_range'] = [min_gpa, max_gpa]
                print(f"GPA filter applied: {min_gpa}-{max_gpa}")
                
            elif choice == '3':
                min_engagement = float(input("Minimum engagement score: "))
                max_engagement = float(input("Maximum engagement score: "))
                self.custom_filters['engagement_range'] = [min_engagement, max_engagement]
                print(f"Engagement filter applied: {min_engagement}-{max_engagement}")
                
            elif choice == '4':
                courses = students_df['course'].unique()
                print("Available courses:", ', '.join(courses))
                selected_courses = input("Enter courses (comma-separated): ").split(',')
                selected_courses = [c.strip() for c in selected_courses if c.strip() in courses]
                if selected_courses:
                    self.custom_filters['course'] = selected_courses
                    print(f"Course filter applied: {', '.join(selected_courses)}")
                
            elif choice == '5':
                genders = students_df['gender'].unique()
                print("Available genders:", ', '.join(genders))
                selected_gender = input("Select gender: ")
                if selected_gender in genders:
                    self.custom_filters['gender'] = selected_gender
                    print(f"Gender filter applied: {selected_gender}")
                
            elif choice == '6':
                statuses = students_df['completion_status'].unique()
                print("Available statuses:", ', '.join(statuses))
                selected_status = input("Select completion status: ")
                if selected_status in statuses:
                    self.custom_filters['completion_status'] = selected_status
                    print(f"Completion status filter applied: {selected_status}")
                
            elif choice == '7':
                start_date = input("Start date (YYYY-MM-DD): ")
                end_date = input("End date (YYYY-MM-DD): ")
                try:
                    self.custom_filters['date_range'] = [start_date, end_date]
                    print(f"Date range filter applied: {start_date} to {end_date}")
                except (ValueError, KeyError):
                    print("Invalid date format")
                
            elif choice == '8':
                self.custom_filters.clear()
                print("All filters cleared")
                
            elif choice == '9':
                filtered_count = len(self.get_all_students(self.custom_filters))
                print(f"Filters applied. {filtered_count} students match criteria.")
                break
                
            else:
                print("Invalid choice")

    def configuration_settings(self):
        """Configuration settings management"""
        print("\n" + "="*60)
        print("CONFIGURATION SETTINGS")
        print("="*60)
        
        print("Current settings:")
        print("1. Color scheme")
        print("2. Export formats")
        print("3. Email configuration")
        print("4. Display preferences")
        print("5. Reset to defaults")
        print("6. Return to main menu")
        
        choice = input("Select option (1-6): ")
        
        if choice == '1':
            print("\nColor scheme options:")
            print("1. Default blue theme")
            print("2. Green theme")
            print("3. Red theme")
            print("4. Custom colors")
            
            color_choice = input("Select color scheme (1-4): ")
            
            if color_choice == '1':
                CONFIG['colors'] = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
            elif color_choice == '2':
                CONFIG['colors'] = ['#2ca02c', '#98df8a', '#1f77b4', '#aec7e8', '#ff7f0e', '#ffbb78']
            elif color_choice == '3':
                CONFIG['colors'] = ['#d62728', '#ff9896', '#1f77b4', '#aec7e8', '#ff7f0e', '#ffbb78']
            elif color_choice == '4':
                print("Enter 6 hex color codes (e.g., #1f77b4):")
                custom_colors = []
                for i in range(6):
                    color = input(f"Color {i+1}: ")
                    custom_colors.append(color)
                CONFIG['colors'] = custom_colors
            
            print("Color scheme updated!")
            
        elif choice == '2':
            print("\nCurrent export formats:", CONFIG['export_formats'])
            print("Available formats: png, pdf, svg, excel")
            
            formats = input("Enter desired formats (comma-separated): ").split(',')
            CONFIG['export_formats'] = [f.strip() for f in formats if f.strip()]
            print("Export formats updated!")
            
        elif choice == '3':
            print("\nEmail Configuration:")
            CONFIG['email_config']['sender_email'] = input("Sender email address: ")
            CONFIG['email_config']['sender_password'] = input("Email password: ")
            CONFIG['email_config']['smtp_server'] = input("SMTP server (default: smtp.gmail.com): ") or 'smtp.gmail.com'
            CONFIG['email_config']['smtp_port'] = int(input("SMTP port (default: 587): ") or 587)
            print("Email configuration updated!")
            
        elif choice == '4':
            print("\nDisplay Preferences:")
            CONFIG['figure_size'] = tuple(map(int, input("Figure size (width,height): ").split(',')))
            CONFIG['dpi'] = int(input("DPI for saved plots: ") or 300)
            print("Display preferences updated!")
            
        elif choice == '5':
            CONFIG['colors'] = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
            CONFIG['figure_size'] = (15, 10)
            CONFIG['dpi'] = 300
            CONFIG['export_formats'] = ['png', 'pdf', 'svg', 'excel']
            print("Settings reset to defaults!")
            
        elif choice == '6':
            return

    def generate_complete_report(self):
        """Generate the most comprehensive analytics report possible"""
        students_df = self.get_all_students(self.custom_filters)
        modules_df = self.get_all_modules(self.custom_filters)
        
        if students_df.empty:
            print("No data available for generating the report.")
            return
        
        print("\nGenerating comprehensive analytics report...")
        print("This may take a few minutes...")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.reports_dir}/comprehensive_analytics_report_{timestamp}.pdf"
        
        with PdfPages(filename) as pdf:
            # Title Page
            plt.figure(figsize=(12, 8))
            plt.axis('off')
            plt.text(0.5, 0.7, 'Comprehensive Student Analytics Report', 
                    horizontalalignment='center', verticalalignment='center', fontsize=28, weight='bold')
            plt.text(0.5, 0.6, f'Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 
                    horizontalalignment='center', verticalalignment='center', fontsize=16)
            plt.text(0.5, 0.5, f'Total Students Analyzed: {len(students_df)}', 
                    horizontalalignment='center', verticalalignment='center', fontsize=16)
            if not modules_df.empty:
                plt.text(0.5, 0.45, f'Total Module Enrollments: {len(modules_df)}', 
                        horizontalalignment='center', verticalalignment='center', fontsize=16)
            plt.text(0.5, 0.3, 'Enhanced Student Analytics System', 
                    horizontalalignment='center', verticalalignment='center', fontsize=14, style='italic')
            pdf.savefig()
            plt.close()
            
            # Executive Summary Page
            plt.figure(figsize=(12, 10))
            plt.axis('off')
            plt.text(0.5, 0.95, 'Executive Summary', horizontalalignment='center', fontsize=20, weight='bold')
            
            # Key metrics
            avg_gpa = students_df['gpa'].mean()
            avg_engagement = students_df['engagement_score'].mean()
            completion_rate = (students_df['completion_status'] == 'Completed').mean() * 100
            pass_rate = (students_df['overall_grade'] != 'F').mean() * 100
            
            y_pos = 0.85
            key_metrics = [
                f"Average GPA: {avg_gpa:.2f}",
                f"Average Engagement Score: {avg_engagement:.1f}",
                f"Overall Pass Rate: {pass_rate:.1f}%",
                f"Completion Rate: {completion_rate:.1f}%",
                f"Total Active Students: {len(students_df[students_df['completion_status'] == 'Active'])}",
                f"Students at Risk: {(students_df['gpa'] < 2.0).sum()}"
            ]
            
            for metric in key_metrics:
                plt.text(0.1, y_pos, f"• {metric}", fontsize=14, weight='bold')
                y_pos -= 0.06
            
            # Key insights
            y_pos -= 0.05
            plt.text(0.1, y_pos, 'Key Insights:', fontsize=16, weight='bold')
            y_pos -= 0.05
            
            # Safely compute insights with fallbacks for empty/invalid data
            course_gpa = students_df.groupby('course')['gpa'].mean()
            highest_course = course_gpa.idxmax() if not course_gpa.empty else 'N/A'

            # Handle None/NaN age values for age group analysis
            students_with_age = students_df[students_df['age'].notna()]
            if not students_with_age.empty:
                age_groups = pd.cut(students_with_age['age'], bins=[0, 25, 35, 45, 100],
                                   labels=['18-25', '26-35', '36-45', '46+'])
                mode_result = age_groups.mode()
                popular_age_group = mode_result.iloc[0] if not mode_result.empty else 'N/A'
            else:
                popular_age_group = 'N/A'

            correlation = students_df['engagement_score'].corr(students_df['gpa'])
            correlation_str = f"{correlation:.3f}" if pd.notna(correlation) else 'N/A'

            insights = [
                f"Highest performing course: {highest_course}",
                f"Most popular age group: {popular_age_group}",
                f"Engagement-GPA correlation: {correlation_str}",
                "Recommended actions: Focus on low-engagement students and academic support"
            ]
            
            for insight in insights:
                plt.text(0.1, y_pos, f"• {insight}", fontsize=12)
                y_pos -= 0.05
            
            pdf.savefig()
            plt.close()
            
            # Generate all analysis components
            analyses = [
                ('Student Demographics', self.analyze_student_demographics),
                ('Grade Distribution', self.analyze_grade_distribution),
                ('Module Popularity', self.analyze_module_popularity),
                ('Academic Risk Assessment', self.analyze_academic_risk),
                ('Module Difficulty', self.analyze_module_difficulty),
                ('Performance Trends', self.analyze_performance_trends),
                ('Correlation Analysis', self.analyze_correlations),
                ('Engagement Analysis', self.analyze_engagement),
                ('Cohort Analysis', self.analyze_cohorts),
                ('Predictive Analytics', self.predictive_analytics)
            ]
            
            for name, analysis_func in analyses:
                print(f"Generating {name}...")
                try:
                    analysis_func()
                    pdf.savefig()
                    plt.close()
                except Exception as e:
                    print(f"Error generating {name}: {e}")
                    continue
        
        print(f"\nComprehensive analytics report generated successfully!")
        print(f"Report saved as: {filename}")
        print(f"File size: {os.path.getsize(filename) / (1024*1024):.1f} MB")

# Main execution
if __name__ == "__main__":
    analytics = StudentAnalytics()
    analytics.display_main_menu()