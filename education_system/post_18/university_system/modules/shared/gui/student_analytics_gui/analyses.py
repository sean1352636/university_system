"""Analysis methods mixin for the Student Analytics GUI."""
from education_system.post_18.university_system.modules.shared.gui.student_analytics_gui._imports import (
    pd, np, plt, CONFIG, _t,
)


class AnalysesMixin:
    """Mixin providing all heavy analysis methods with matplotlib visualisations."""

    def analyze_module_difficulty(self):
        """Analyze module difficulty and performance metrics - GUI compatible"""
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

        # Continue with other subplots...
        plt.tight_layout(rect=[0, 0, 1, 0.95])

        # Print detailed analysis
        print("\n" + "="*60)
        print("MODULE DIFFICULTY ANALYSIS SUMMARY")
        print("="*60)

        print(f"Total modules analyzed: {len(module_stats)}")
        print(f"Average pass rate across all modules: {module_stats['Pass_Rate'].mean():.1f}%")
        print(f"Average difficulty rating: {module_stats['Avg_Difficulty'].mean():.1f}/5")
        print(f"Average completion rate: {module_stats['Completion_Rate'].mean():.1f}%")

        self.save_or_display_plot(fig, "module_difficulty_analysis")

    def analyze_performance_trends(self):
        """Analyze student performance trends over time - GUI compatible"""
        students_df = self.get_all_students(self.custom_filters)

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
                except Exception:
                    pass  # Skip trend line if fitting fails
        else:
            ax1.text(0.5, 0.5, 'No valid GPA data', ha='center', va='center', transform=ax1.transAxes)
            ax1.set_title('GPA Trends Over Time (No Data)')

        # Continue with other trend analyses...
        plt.tight_layout(rect=[0, 0, 1, 0.95])

        # Print detailed performance trends summary
        print("\n" + "="*60)
        print("PERFORMANCE TRENDS SUMMARY")
        print("="*60)

        if len(monthly_gpa) > 0:
            print(f"Analysis Period: {monthly_gpa.index[0]} to {monthly_gpa.index[-1]}")
            print(f"Number of periods analyzed: {len(monthly_gpa)}")

        self.save_or_display_plot(fig, "performance_trends")

    def analyze_cohorts(self):
        """Analyze student cohorts and retention patterns - GUI compatible"""
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
        ).round().astype(int)

        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Student Cohort Analysis', fontsize=20)

        # 1. Cohort Size Over Time
        ax1 = fig.add_subplot(331)
        cohort_sizes = students_df.groupby('cohort_month').size()
        ax1.plot(range(len(cohort_sizes)), cohort_sizes.values, marker='o', color=CONFIG['colors'][0])
        ax1.set_xlabel('Cohort Period')
        ax1.set_ylabel('Number of Students')
        ax1.set_title('Cohort Size Over Time')

        # Continue with other cohort analyses...
        plt.tight_layout(rect=[0, 0, 1, 0.95])

        # Print detailed cohort analysis
        print("\n" + "="*60)
        print("COHORT ANALYSIS SUMMARY")
        print("="*60)

        print(f"Total cohorts analyzed: {len(cohort_sizes)}")
        print(f"Average cohort size: {cohort_sizes.mean():.1f} students")

        self.save_or_display_plot(fig, "cohort_analysis")

    def analyze_correlations(self):
        """Perform comprehensive correlation analysis - GUI compatible"""
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

        if len(numeric_cols) < 2:
            print("Insufficient numerical columns for correlation analysis.")
            return

        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Comprehensive Correlation Analysis', fontsize=20)

        # Create correlation matrix
        correlation_data = students_df[numeric_cols].dropna()
        correlation_matrix = correlation_data.corr()

        # 1. Main Correlation Heatmap
        ax1 = fig.add_subplot(331)
        im1 = ax1.imshow(correlation_matrix, cmap='RdBu_r', aspect='auto', vmin=-1, vmax=1)
        ax1.set_xticks(range(len(numeric_cols)))
        ax1.set_yticks(range(len(numeric_cols)))
        ax1.set_xticklabels(numeric_cols, rotation=45, ha='right')
        ax1.set_yticklabels(numeric_cols)
        ax1.set_title('Correlation Matrix')
        plt.colorbar(im1, ax=ax1)

        # Continue with other correlation analyses...
        plt.tight_layout(rect=[0, 0, 1, 0.95])

        print("\n" + "="*60)
        print("CORRELATION ANALYSIS SUMMARY")
        print("="*60)

        self.save_or_display_plot(fig, "correlation_analysis")

    def predictive_analytics(self):
        """Perform predictive analytics using machine learning - GUI compatible"""
        students_df = self.get_all_students(self.custom_filters)

        if students_df.empty or len(students_df) < 50:  # Need sufficient data for ML
            print("Insufficient data for predictive analytics (minimum 50 students required).")
            return

        print("\nGenerating Predictive Analytics...")

        # Prepare data for machine learning
        students_df['high_performer'] = (students_df['gpa'] >= 3.5).astype(int)
        students_df['at_risk'] = ((students_df['gpa'] < 2.0) | (students_df['engagement_score'] < 30)).astype(int)

        # Prepare features
        feature_columns = ['age', 'engagement_score']
        students_df['gender_encoded'] = pd.Categorical(students_df['gender']).codes
        students_df['course_encoded'] = pd.Categorical(students_df['course']).codes
        feature_columns.extend(['gender_encoded', 'course_encoded'])

        X = students_df[feature_columns].fillna(0)

        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Predictive Analytics Dashboard', fontsize=20)

        # Machine learning models and visualizations here...
        plt.tight_layout(rect=[0, 0, 1, 0.95])

        print("\n" + "="*60)
        print("PREDICTIVE ANALYTICS SUMMARY")
        print("="*60)

        self.save_or_display_plot(fig, "predictive_analytics")

    def analyze_student_demographics(self):
        """Enhanced student demographics analysis - GUI compatible version"""
        students_df = self.get_all_students(self.custom_filters)

        if students_df.empty:
            print("No student data available for analysis.")
            return

        print("\nGenerating Enhanced Student Demographics Analysis...")

        # Create comprehensive demographics analysis
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Enhanced Student Demographics Analysis', fontsize=20)

        # 1. Gender Distribution
        ax1 = fig.add_subplot(331)
        gender_counts = students_df['gender'].value_counts()
        colors = CONFIG['colors'][:len(gender_counts)]
        ax1.pie(gender_counts, labels=gender_counts.index, autopct='%1.1f%%',
                startangle=90, colors=colors)
        ax1.set_title('Gender Distribution')

        # 2. Age Distribution with statistics
        ax2 = fig.add_subplot(332)
        ax2.hist(students_df['age'], bins=range(int(min(students_df['age'])), int(max(students_df['age']))+2),
                edgecolor='black', alpha=0.7)
        ax2.axvline(students_df['age'].mean(), color='red', linestyle='--', label=f'Mean: {students_df["age"].mean():.1f}')
        ax2.axvline(students_df['age'].median(), color='green', linestyle='--', label=f'Median: {students_df["age"].median():.1f}')
        ax2.set_xlabel('Age')
        ax2.set_ylabel('Number of Students')
        ax2.set_title('Age Distribution')
        ax2.legend()

        # 3. Course Distribution
        ax3 = fig.add_subplot(333)
        course_counts = students_df['course'].value_counts()
        ax3.bar(course_counts.index, course_counts.values, color=colors)
        ax3.set_xlabel('Course')
        ax3.set_ylabel('Number of Students')
        ax3.set_title('Course Distribution')

        # 4. GPA Distribution
        ax4 = fig.add_subplot(334)
        ax4.hist(students_df['gpa'], bins=20, edgecolor='black', alpha=0.7)
        ax4.axvline(students_df['gpa'].mean(), color='red', linestyle='--', label=f'Mean GPA: {students_df["gpa"].mean():.2f}')
        ax4.set_xlabel('GPA')
        ax4.set_ylabel('Number of Students')
        ax4.set_title('GPA Distribution')
        ax4.legend()

        # 5. Location Distribution
        ax5 = fig.add_subplot(335)
        location_counts = students_df['location'].value_counts()
        ax5.bar(location_counts.index, location_counts.values, color=colors)
        plt.xticks(rotation=45, ha='right')
        ax5.set_xlabel('Location')
        ax5.set_ylabel('Number of Students')
        ax5.set_title('Geographic Distribution')

        # 6. Previous Education
        ax6 = fig.add_subplot(336)
        edu_counts = students_df['previous_education'].value_counts()
        ax6.pie(edu_counts, labels=edu_counts.index, autopct='%1.1f%%', startangle=90)
        ax6.set_title('Previous Education Level')

        # 7. Completion Status
        ax7 = fig.add_subplot(337)
        status_counts = students_df['completion_status'].value_counts()
        ax7.bar(status_counts.index, status_counts.values, color=colors)
        plt.xticks(rotation=45, ha='right')
        ax7.set_xlabel('Status')
        ax7.set_ylabel('Number of Students')
        ax7.set_title('Completion Status')

        # 8. Engagement Score Distribution
        ax8 = fig.add_subplot(338)
        ax8.hist(students_df['engagement_score'], bins=20, edgecolor='black', alpha=0.7)
        ax8.axvline(students_df['engagement_score'].mean(), color='red', linestyle='--',
                   label=f'Mean: {students_df["engagement_score"].mean():.1f}')
        ax8.set_xlabel('Engagement Score')
        ax8.set_ylabel('Number of Students')
        ax8.set_title('Student Engagement Distribution')
        ax8.legend()

        # 9. Age vs GPA Scatter
        ax9 = fig.add_subplot(339)
        scatter = ax9.scatter(students_df['age'], students_df['gpa'],
                             c=students_df['engagement_score'], cmap='viridis', alpha=0.6)
        ax9.set_xlabel('Age')
        ax9.set_ylabel('GPA')
        ax9.set_title('Age vs GPA (colored by Engagement)')
        plt.colorbar(scatter, ax=ax9, label='Engagement Score')

        plt.tight_layout(rect=[0, 0, 1, 0.95])

        # Build enhanced summary statistics for GUI display
        summary_text = "="*60 + "\n"
        summary_text += "ENHANCED DEMOGRAPHICS SUMMARY\n"
        summary_text += "="*60 + "\n"
        summary_text += f"Total students: {len(students_df)}\n"
        summary_text += f"Active students: {len(students_df[students_df['completion_status'] == 'Active'])}\n"
        summary_text += f"Completion rate: {len(students_df[students_df['completion_status'] == 'Completed']) / len(students_df) * 100:.1f}%\n"

        summary_text += "\n📊 Statistical Summary:\n"
        summary_text += f"Average age: {students_df['age'].mean():.1f} (±{students_df['age'].std():.1f})\n"
        summary_text += f"Average GPA: {students_df['gpa'].mean():.2f} (±{students_df['gpa'].std():.2f})\n"
        summary_text += f"Average engagement: {students_df['engagement_score'].mean():.1f} (±{students_df['engagement_score'].std():.1f})\n"

        summary_text += "\n🎯 Top Performing Segments:\n"
        high_performers = students_df[students_df['gpa'] >= 3.5]
        if not high_performers.empty:
            summary_text += f"High performers (GPA ≥ 3.5): {len(high_performers)} ({len(high_performers)/len(students_df)*100:.1f}%)\n"
            summary_text += f"Most common course among high performers: {high_performers['course'].mode().iloc[0]}\n"
            summary_text += f"Average age of high performers: {high_performers['age'].mean():.1f}\n"

        # Display results in GUI window
        self.display_results_window("Student Demographics Analysis", summary_text, fig)

        self.save_or_display_plot(fig, "enhanced_student_demographics")

    def analyze_grade_distribution(self):
        """Analyze grade distributions across modules and courses - GUI compatible"""
        students_df = self.get_all_students(self.custom_filters)
        modules_df = self.get_all_modules(self.custom_filters)

        if students_df.empty:
            print("Insufficient data for grade analysis.")
            return

        # Clean data and handle NaN values
        students_df = students_df.dropna(subset=['overall_grade', 'gpa'])

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
                ax3.legend(title=_t("analytics.labels.grade"))
                plt.setp(ax3.xaxis.get_majorticklabels(), rotation=0)
            else:
                ax3.text(0.5, 0.5, 'No gender data', ha='center', va='center', transform=ax3.transAxes)
        else:
            ax3.text(0.5, 0.5, 'Gender column not available', ha='center', va='center', transform=ax3.transAxes)
            ax3.set_title('Grade Distribution by Gender (No Data)')

        # 4. Module Grade Distribution
        ax4 = fig.add_subplot(334)
        if not modules_df.empty and 'module_grade' in modules_df.columns:
            module_grades = modules_df['module_grade'].value_counts().reindex(['A', 'B', 'C', 'D', 'F'], fill_value=0)
            ax4.bar(module_grades.index, module_grades.values, color=CONFIG['colors'])
            ax4.set_xlabel('Module Grade')
            ax4.set_ylabel('Number of Module Enrollments')
            ax4.set_title('Module Grade Distribution')
        else:
            ax4.text(0.5, 0.5, 'No module grade data', ha='center', va='center', transform=ax4.transAxes)
            ax4.set_title('Module Grade Distribution (No Data)')

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
        if not modules_df.empty and 'module_name' in modules_df.columns:
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

        # Print detailed statistics
        print("\n" + "="*60)
        print("GRADE DISTRIBUTION SUMMARY")
        print("="*60)

        if len(students_df) > 0:
            avg_gpa = students_df['gpa'].mean()
            median_gpa = students_df['gpa'].median()
            std_gpa = students_df['gpa'].std()
            pass_rate_val = (students_df['overall_grade'] != 'F').mean() * 100

            print("Overall Statistics:")
            print(f"  Average GPA: {avg_gpa:.2f}" if not np.isnan(avg_gpa) else "  Average GPA: N/A")
            print(f"  Median GPA: {median_gpa:.2f}" if not np.isnan(median_gpa) else "  Median GPA: N/A")
            print(f"  GPA Standard Deviation: {std_gpa:.2f}" if not np.isnan(std_gpa) else "  GPA Standard Deviation: N/A")
            print(f"  Pass Rate: {pass_rate_val:.1f}%" if not np.isnan(pass_rate_val) else "  Pass Rate: N/A")

        self.save_or_display_plot(fig, "grade_distribution_analysis")

    def analyze_course_enrollments(self):
        """Analyze course enrollment patterns and statistics - GUI compatible"""
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
        else:
            ax2.text(0.5, 0.5, 'Registration datetime not available', ha='center', va='center', transform=ax2.transAxes)
            ax2.set_title('Course Enrollment Trends (No Data)')

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
        for course in students_df['course'].unique():
            course_ages = students_df[students_df['course'] == course]['age']
            ax4.hist(course_ages, alpha=0.7, label=course, bins=15)
        ax4.set_xlabel('Age')
        ax4.set_ylabel('Number of Students')
        ax4.set_title('Age Distribution by Course')
        ax4.legend()

        # 5. Gender Distribution by Course
        ax5 = fig.add_subplot(335)
        gender_course = pd.crosstab(students_df['course'], students_df['gender'])
        gender_course.plot(kind='bar', ax=ax5, color=CONFIG['colors'])
        ax5.set_xlabel('Course')
        ax5.set_ylabel('Number of Students')
        ax5.set_title('Gender Distribution by Course')
        ax5.legend(title=_t("analytics.filters.gender"))
        plt.xticks(rotation=45)

        # 6. Course Completion Rates
        ax6 = fig.add_subplot(336)
        completion_rates = students_df.groupby('course').apply(
            lambda x: (x['completion_status'] == 'Completed').mean() * 100
        )
        ax6.bar(completion_rates.index, completion_rates.values, color='green', alpha=0.7)
        ax6.set_xlabel('Course')
        ax6.set_ylabel('Completion Rate (%)')
        ax6.set_title('Course Completion Rates')

        # 7. Course Capacity Analysis
        ax7 = fig.add_subplot(337)
        enrollment_counts = students_df['course'].value_counts()
        avg_enrollment = enrollment_counts.mean()

        colors = ['red' if count < avg_enrollment * 0.7 else 'orange' if count < avg_enrollment else 'green'
                 for count in enrollment_counts.values]

        ax7.bar(enrollment_counts.index, enrollment_counts.values, color=colors, alpha=0.7)
        ax7.axhline(y=avg_enrollment, color='blue', linestyle='--', label=f'Average: {avg_enrollment:.1f}')
        ax7.set_xlabel('Course')
        ax7.set_ylabel('Number of Students')
        ax7.set_title('Course Enrollment vs Average')
        ax7.legend()

        # 8. Course Satisfaction (Engagement) Heatmap
        ax8 = fig.add_subplot(338)
        engagement_by_course_age = students_df.groupby(['course', pd.cut(students_df['age'], bins=[0, 25, 35, 45, 100],
                                                       labels=['18-25', '26-35', '36-45', '46+'])])['engagement_score'].mean().unstack()

        im = ax8.imshow(engagement_by_course_age.values, cmap='RdYlGn', aspect='auto')
        ax8.set_xticks(range(len(engagement_by_course_age.columns)))
        ax8.set_yticks(range(len(engagement_by_course_age.index)))
        ax8.set_xticklabels(engagement_by_course_age.columns)
        ax8.set_yticklabels(engagement_by_course_age.index)
        ax8.set_xlabel('Age Group')
        ax8.set_ylabel('Course')
        ax8.set_title('Average Engagement by Course and Age')
        plt.colorbar(im, ax=ax8)

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
            else:
                ax9.text(0.5, 0.5, 'Insufficient data for forecast', ha='center', va='center', transform=ax9.transAxes)
                ax9.set_title('Enrollment Forecast (Insufficient Data)')
        else:
            ax9.text(0.5, 0.5, 'Registration datetime not available', ha='center', va='center', transform=ax9.transAxes)
            ax9.set_title('Enrollment Forecast (No Data)')
        plt.tight_layout(rect=[0, 0, 1, 0.95])

        self.save_or_display_plot(fig, "course_enrollment_analysis")

    def analyze_registration_timeline(self):
        """Analyze student registration patterns over time - GUI compatible"""
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

        # Continue with other timeline analysis plots...
        plt.tight_layout(rect=[0, 0, 1, 0.95])

        self.save_or_display_plot(fig, "registration_timeline_analysis")
