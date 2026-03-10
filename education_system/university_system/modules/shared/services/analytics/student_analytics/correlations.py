import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

from .config import CONFIG


class CorrelationsMixin:
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
