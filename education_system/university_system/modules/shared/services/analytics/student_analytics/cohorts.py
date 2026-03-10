import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from .config import CONFIG


class CohortsMixin:
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
