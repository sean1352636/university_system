"""Academic risk assessment analysis mixin for StudentAnalytics."""

import numpy as np

from education_system.post_18.university_system.modules.shared.services.analytics.student_analytics.config import CONFIG


class RiskMixin:
    def analyze_academic_risk(self):
        """Analyze students at academic risk"""
        import pandas as pd
        import matplotlib.pyplot as plt
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
            except Exception:
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
        except Exception:
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

            summary_text += "\nRisk Factor Breakdown:\n"
            summary_text += f"  Low GPA (<2.0): {students_df['low_gpa'].sum()} students\n"
            summary_text += f"  Low Engagement (<30): {students_df['low_engagement'].sum()} students\n"
            if not modules_df.empty:
                summary_text += f"  Failing Modules: {students_df['failing_modules'].sum()} students\n"
                summary_text += f"  Low Attendance (<70%): {students_df['low_attendance'].sum()} students\n"

            summary_text += "\nHigh Priority Students (Multiple Risk Factors):\n"
            high_priority = students_df[students_df['risk_score'] >= 2]
            summary_text += f"  {len(high_priority)} students require immediate intervention\n"

            if len(high_priority) > 0:
                summary_text += "\nTop Risk Indicators for High Priority Students:\n"
                avg_gpa = high_priority['gpa'].mean()
                avg_engagement = high_priority['engagement_score'].mean()
                summary_text += f"  Average GPA: {avg_gpa:.2f}\n" if not np.isnan(avg_gpa) else "  Average GPA: N/A\n"
                summary_text += f"  Average Engagement: {avg_engagement:.1f}\n" if not np.isnan(avg_engagement) else "  Average Engagement: N/A\n"

            summary_text += "\nRecommended Actions:\n"
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
