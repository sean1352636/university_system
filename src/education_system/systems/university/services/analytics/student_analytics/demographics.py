"""Demographics analysis mixin for StudentAnalytics."""

import numpy as np

from education_system.systems.university.services.analytics.student_analytics.config import CONFIG


class DemographicsMixin:
    def analyze_student_demographics(self):
        """Enhanced student demographics analysis"""
        import pandas as pd
        import matplotlib.pyplot as plt
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

        summary_text += "\n📊 Statistical Summary:\n"
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

        summary_text += "\n🎯 Top Performing Segments:\n"
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
