import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from education_system.university_system.modules.shared.services.analytics.student_analytics.config import CONFIG


class EngagementMixin:
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
