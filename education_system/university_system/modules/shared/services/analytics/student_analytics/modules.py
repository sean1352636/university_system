"""Module difficulty and popularity analysis mixin for StudentAnalytics."""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from education_system.university_system.modules.shared.services.analytics.student_analytics.config import CONFIG


class ModulesMixin:
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
