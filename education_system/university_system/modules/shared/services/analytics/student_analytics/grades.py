"""Grade distribution and performance trends analysis mixin for StudentAnalytics."""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from .config import CONFIG


class GradesMixin:
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
