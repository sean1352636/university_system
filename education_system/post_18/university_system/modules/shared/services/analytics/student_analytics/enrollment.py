"""Enrollment and registration timeline analysis mixin for StudentAnalytics."""

import numpy as np

from education_system.post_18.university_system.modules.shared.services.analytics.student_analytics.config import CONFIG


class EnrollmentMixin:
    def analyze_course_enrollments(self):
        """Analyze course enrollment patterns and statistics"""
        import pandas as pd
        import matplotlib.pyplot as plt
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

        summary_text += "\nCourse Enrollment Breakdown:\n"
        for course, count in course_counts.items():
            percentage = count / len(students_df) * 100
            avg_gpa = students_df[students_df['course'] == course]['gpa'].mean()
            completion_rate = (students_df[students_df['course'] == course]['completion_status'] == 'Completed').mean() * 100
            summary_text += f"  {course}: {count} students ({percentage:.1f}%), Avg GPA: {avg_gpa:.2f}, Completion: {completion_rate:.1f}%\n"

        summary_text += "\nTop Performing Courses (by GPA):\n"
        top_courses_gpa = course_stats.nlargest(3, 'gpa')
        for course, stats in top_courses_gpa.iterrows():
            summary_text += f"  {course}: GPA {stats['gpa']:.2f}, {stats['student_id']} students\n"

        summary_text += "\nMost Popular Courses:\n"
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
        import pandas as pd
        import matplotlib.pyplot as plt
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
            summary_text += "Analysis period: No valid date range available\n"
        summary_text += f"Total registrations: {len(students_df)}\n"
        summary_text += f"Average registrations per month: {monthly_registrations.mean():.1f}\n"

        summary_text += "\nPeak Registration Periods:\n"
        for period, count in peak_periods.head(3).items():
            summary_text += f"  {period}: {count} registrations\n"

        summary_text += "\nSeasonal Patterns:\n"
        peak_month = monthly_pattern.idxmax()
        low_month = monthly_pattern.idxmin()
        summary_text += f"  Peak month: {months[peak_month-1]} ({monthly_pattern[peak_month]} registrations)\n"
        summary_text += f"  Lowest month: {months[low_month-1]} ({monthly_pattern[low_month]} registrations)\n"

        summary_text += "\nDaily Patterns:\n"
        peak_day = day_pattern.idxmax()
        low_day = day_pattern.idxmin()
        summary_text += f"  Most popular day: {peak_day} ({day_pattern[peak_day]} registrations)\n"
        summary_text += f"  Least popular day: {low_day} ({day_pattern[low_day]} registrations)\n"

        if len(hourly_pattern) > 0:
            peak_hour = hourly_pattern.idxmax()
            summary_text += f"  Peak hour: {peak_hour}:00 ({hourly_pattern[peak_hour]} registrations)\n"

        summary_text += "\nGrowth Analysis:\n"
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
