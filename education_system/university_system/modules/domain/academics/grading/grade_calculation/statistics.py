import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from datetime import datetime

matplotlib.use('Agg')

from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.domain.academics.grading.grade_calculation.conversions import (
    percentage_to_letter,
    letter_to_percentage,
)
from education_system.university_system.modules.domain.academics.grading.grade_calculation.utils import select_assessment
from education_system.university_system.modules.domain.academics.grading.grade_calculation.grade_entry import update_module_grade


def calculate_assessment_statistics():
    """Calculate statistical measures for an assessment's grades"""
    print("\nCalculate Assessment Statistics")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get assessment to analyze
        assessment_id = select_assessment(cursor)
        if not assessment_id:
            conn.close()
            return

        # Get the assessment details
        cursor.execute('''
        SELECT assessment_name, module_code, max_points
        FROM assessments
        WHERE assessment_id = ?
        ''', (assessment_id,))

        assessment = cursor.fetchone()
        if not assessment:
            print("Assessment not found.")
            conn.close()
            return

        assessment_name, module_code, max_points = assessment

        # Get all grades for this assessment
        cursor.execute('''
        SELECT score
        FROM grades
        WHERE assessment_id = ?
        ''', (assessment_id,))

        grades = cursor.fetchall()

        if not grades:
            print(f"No grades found for assessment {assessment_name}.")
            conn.close()
            return

        # Convert to a numpy array for statistical calculations
        scores = np.array([g[0] for g in grades])

        # Calculate statistics
        mean = np.mean(scores)
        median = np.median(scores)
        std_dev = np.std(scores)
        min_score = np.min(scores)
        max_score = np.max(scores)
        q1 = np.percentile(scores, 25)
        q3 = np.percentile(scores, 75)

        # Calculate skewness and kurtosis if there are enough samples
        if len(scores) >= 3:
            skewness = stats.skew(scores)
            kurtosis = stats.kurtosis(scores)
        else:
            skewness = 0
            kurtosis = 0

        # Insert or update the statistics in the database
        date_calculated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Check if statistics already exist for this assessment
        cursor.execute('''
        SELECT stat_id
        FROM grade_statistics
        WHERE assessment_id = ?
        ''', (assessment_id,))

        existing_stat = cursor.fetchone()

        if existing_stat:
            cursor.execute('''
            UPDATE grade_statistics
            SET mean = ?, median = ?, std_dev = ?, min_score = ?, max_score = ?,
                q1 = ?, q3 = ?, skewness = ?, kurtosis = ?, date_calculated = ?
            WHERE assessment_id = ?
            ''', (mean, median, std_dev, min_score, max_score, q1, q3, skewness, kurtosis, date_calculated, assessment_id))
        else:
            cursor.execute('''
            INSERT INTO grade_statistics
            (assessment_id, mean, median, std_dev, min_score, max_score, q1, q3, skewness, kurtosis, date_calculated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (assessment_id, mean, median, std_dev, min_score, max_score, q1, q3, skewness, kurtosis, date_calculated))

        conn.commit()

        # Display the statistics
        print("\nStatistical Analysis Results:")
        print(f"Assessment: {assessment_name} [{module_code}]")
        print(f"Number of grades: {len(scores)}")
        print(f"Mean score: {mean:.2f} / {max_points} ({(mean/max_points)*100:.1f}%)")
        print(f"Median score: {median:.2f} / {max_points} ({(median/max_points)*100:.1f}%)")
        print(f"Standard deviation: {std_dev:.2f}")
        print(f"Range: {min_score:.2f} - {max_score:.2f}")
        print(f"1st quartile (Q1): {q1:.2f}")
        print(f"3rd quartile (Q3): {q3:.2f}")
        print(f"Interquartile range (IQR): {(q3-q1):.2f}")
        print(f"Skewness: {skewness:.2f}")
        print(f"Kurtosis: {kurtosis:.2f}")

        # Interpret the statistics
        print("\nInterpretation:")

        # Interpret distribution shape
        if abs(skewness) < 0.5:
            print("- The grade distribution is approximately symmetric.")
        elif skewness < -0.5:
            print("- The grade distribution is skewed to the left (more high scores).")
        else:
            print("- The grade distribution is skewed to the right (more low scores).")

        if kurtosis < -0.5:
            print("- The distribution is platykurtic (flatter than normal, with fewer extreme scores).")
        elif kurtosis > 0.5:
            print("- The distribution is leptokurtic (more peaked than normal, with more extreme scores).")
        else:
            print("- The distribution has a normal-like kurtosis.")

        # Interpret performance
        if mean > 0.7 * max_points:
            print("- Overall performance is good, with an average above 70%.")
        elif mean < 0.5 * max_points:
            print("- Overall performance is concerning, with an average below 50%.")

        if std_dev > 0.2 * max_points:
            print("- There is high variability in student performance.")
        elif std_dev < 0.1 * max_points:
            print("- Student performance is relatively consistent.")

        # Would the user like to visualize the distribution?
        visualize = input("\nWould you like to visualize the grade distribution? (y/n): ").strip().lower()

        if visualize == 'y':
            # Create a directory for the plots if it doesn't exist
            plots_dir = 'statistics_plots'
            if not os.path.exists(plots_dir):
                os.makedirs(plots_dir)

            # Generate a histogram and save it
            plt.figure(figsize=(12, 6))

            # Create histogram with KDE
            sns.histplot(scores, kde=True, color='skyblue')

            # Add vertical lines for key statistics
            plt.axvline(mean, color='r', linestyle='--', label=f'Mean: {mean:.2f}')
            plt.axvline(median, color='g', linestyle='-.', label=f'Median: {median:.2f}')
            plt.axvline(q1, color='orange', linestyle=':', label=f'Q1: {q1:.2f}')
            plt.axvline(q3, color='orange', linestyle=':', label=f'Q3: {q3:.2f}')

            # Add title and labels
            plt.title(f'Grade Distribution for {assessment_name}')
            plt.xlabel('Score')
            plt.ylabel('Frequency')
            plt.legend()

            # Add statistical annotations
            stats_text = f"Mean: {mean:.2f}\nMedian: {median:.2f}\nStd Dev: {std_dev:.2f}\nMin: {min_score:.2f}\nMax: {max_score:.2f}"
            plt.annotate(stats_text, xy=(0.02, 0.95), xycoords='axes fraction',
                       bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", alpha=0.8))

            # Ensure the x-axis covers the full range of possible scores
            plt.xlim(0, max_points)

            # Save the plot
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            plot_filename = f"{plots_dir}/grade_distribution_{assessment_id}_{timestamp}.png"
            plt.savefig(plot_filename)
            plt.close()

            print(f"\nVisualization saved to {plot_filename}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")


def normalize_assessment_grades():
    """Normalize grades for an assessment using z-scores and percentiles"""
    print("\nNormalize Assessment Grades")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get assessment to normalize
        assessment_id = select_assessment(cursor)
        if not assessment_id:
            conn.close()
            return

        # Get the assessment details
        cursor.execute('''
        SELECT assessment_name, module_code, max_points
        FROM assessments
        WHERE assessment_id = ?
        ''', (assessment_id,))

        assessment = cursor.fetchone()
        if not assessment:
            print("Assessment not found.")
            conn.close()
            return

        assessment_name, module_code, max_points = assessment

        # Get all grades for this assessment
        cursor.execute('''
        SELECT g.grade_id, g.student_id, s.first_name, s.last_name, g.score, g.letter_grade
        FROM grades g
        JOIN students s ON g.student_id = s.student_id
        WHERE g.assessment_id = ?
        ''', (assessment_id,))

        grades = cursor.fetchall()

        if not grades:
            print(f"No grades found for assessment {assessment_name}.")
            conn.close()
            return

        # Extract scores for statistical calculations
        grade_ids = [g[0] for g in grades]
        student_ids = [g[1] for g in grades]
        student_names = [f"{g[2]} {g[3]}" for g in grades]
        scores = np.array([g[4] for g in grades])
        letter_grades = [g[5] for g in grades]

        # Calculate mean and standard deviation
        mean = np.mean(scores)
        std_dev = np.std(scores)

        if std_dev == 0:  # Handle case where all scores are the same
            print("Cannot normalize grades: all scores are identical.")
            conn.close()
            return

        # Calculate z-scores
        z_scores = [(score - mean) / std_dev for score in scores]

        # Calculate percentiles
        percentiles = [stats.percentileofscore(scores, score) for score in scores]

        # Ask about curve method
        print("\nCurve Methods:")
        print("1. Z-score to percentage (mean becomes target %, maintain spread)")
        print("2. Linear scaling (stretch to fill range)")
        print("3. Bell curve (redistribute based on normal distribution)")
        curve_method = input("Select curve method (1-3), or 0 to skip curving: ")

        curved_scores = []
        curved_letters = []

        if curve_method == "1":
            # Z-score to percentage
            target_mean = float(input("Enter target mean percentage (e.g., 75): "))
            target_mean = min(max(target_mean, 0), 100)  # Constrain between 0 and 100
            target_std = float(input("Enter target standard deviation (e.g., 10): "))

            curved_scores = [(z * target_std + target_mean) * max_points / 100 for z in z_scores]
            # Constrain to valid range
            curved_scores = [min(max(score, 0), max_points) for score in curved_scores]
            # Calculate letter grades
            curved_letters = [percentage_to_letter((score / max_points) * 100) for score in curved_scores]

        elif curve_method == "2":
            # Linear scaling
            min_score = min(scores)
            max_score = max(scores)

            if max_score == min_score:
                print("Cannot apply linear scaling: all scores are identical.")
                conn.close()
                return

            target_min = float(input("Enter target minimum percentage (e.g., 50): "))
            target_min = min(max(target_min, 0), 100)  # Constrain between 0 and 100
            target_max = float(input("Enter target maximum percentage (e.g., 100): "))
            target_max = min(max(target_max, target_min), 100)  # Constrain between target_min and 100

            # Linear transformation
            curved_scores = []
            for score in scores:
                normalized = (score - min_score) / (max_score - min_score)  # 0 to 1
                scaled = normalized * (target_max - target_min) + target_min  # target_min to target_max
                curved_scores.append(scaled * max_points / 100)

            # Calculate letter grades
            curved_letters = [percentage_to_letter((score / max_points) * 100) for score in curved_scores]

        elif curve_method == "3":
            # Bell curve
            target_mean = float(input("Enter target mean grade (e.g., 75): "))
            target_mean = min(max(target_mean, 0), 100)  # Constrain between 0 and 100
            target_std = float(input("Enter target standard deviation (e.g., 10): "))

            # Select grade distribution
            print("\nGrade Distribution:")
            print("1. Custom percentages for each grade")
            print("2. Normal distribution based on target mean and std dev")
            dist_method = input("Select distribution method (1-2): ")

            if dist_method == "1":
                # Custom percentages
                percentages = {}
                grade_names = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"]
                total = 0

                print("\nEnter percentage for each grade (total must equal 100%):")
                for grade in grade_names:
                    while True:
                        try:
                            pct = float(input(f"{grade}: "))
                            if pct < 0:
                                print("Percentage cannot be negative.")
                                continue
                            percentages[grade] = pct
                            total += pct
                            break
                        except ValueError:
                            print("Please enter a valid number.")

                if abs(total - 100) > 0.01:
                    print(f"Error: Percentages sum to {total}%, not 100%.")
                    conn.close()
                    return

                # Sort scores and assign grades based on percentiles
                sorted_indices = np.argsort(scores)
                curved_letters = [""] * len(scores)

                current_percentile = 0
                for grade in reversed(grade_names):  # Start with highest grade
                    grade_percentile = percentages[grade]
                    count = int(round(len(scores) * grade_percentile / 100))

                    # Assign this grade to the next 'count' students in sorted order
                    for i in range(count):
                        if current_percentile + i < len(sorted_indices):
                            idx = sorted_indices[-(current_percentile + i + 1)]  # Reverse to get highest scores first
                            curved_letters[idx] = grade

                    current_percentile += count

                # Fill any unassigned (due to rounding) with F
                for i in range(len(curved_letters)):
                    if curved_letters[i] == "":
                        curved_letters[i] = "F"

                # Back-calculate scores from letters (midpoint of letter range)
                curved_scores = []
                for letter in curved_letters:
                    percentage = letter_to_percentage(letter)
                    curved_scores.append(percentage * max_points / 100)

            else:
                # Normal distribution
                # Compute the z-scores needed for the desired grade cutoffs
                grade_cutoffs = {
                    "A+": 97,
                    "A": 93,
                    "A-": 90,
                    "B+": 87,
                    "B": 83,
                    "B-": 80,
                    "C+": 77,
                    "C": 73,
                    "C-": 70,
                    "D+": 67,
                    "D": 63,
                    "D-": 60,
                    "F": 0
                }

                # Adjust cutoffs based on target mean and std dev
                adjusted_cutoffs = {}
                for grade, cutoff in grade_cutoffs.items():
                    z = (cutoff - target_mean) / target_std
                    adjusted_cutoffs[grade] = z

                # Assign grades based on z-scores
                curved_letters = []
                for z in z_scores:
                    assigned_grade = "F"
                    for grade, cutoff in sorted(adjusted_cutoffs.items(), key=lambda x: x[1], reverse=True):
                        if z >= cutoff:
                            assigned_grade = grade
                            break
                    curved_letters.append(assigned_grade)

                # Back-calculate scores from letters (midpoint of letter range)
                curved_scores = []
                for letter in curved_letters:
                    percentage = letter_to_percentage(letter)
                    curved_scores.append(percentage * max_points / 100)

        # Display the results
        if curve_method in ["1", "2", "3"]:
            print("\nNormalization Results:")
            print(f"{'Student':<30} {'Original Score':<15} {'Original Grade':<15} {'Z-Score':<10} {'Percentile':<12} {'Curved Score':<15} {'Curved Grade':<15}")
            print("-" * 100)

            for i in range(len(grades)):
                print(f"{student_names[i]:<30} {scores[i]:<15.2f} {letter_grades[i]:<15} {z_scores[i]:<10.2f} {percentiles[i]:<12.2f} {curved_scores[i]:<15.2f} {curved_letters[i]:<15}")

            # Save to database?
            save = input("\nSave these normalized grades to the database? (y/n): ").strip().lower()

            if save == 'y':
                # Clear any existing normalized grades for this assessment
                cursor.execute('''
                DELETE FROM normalized_grades WHERE grade_id IN (
                    SELECT grade_id FROM grades WHERE assessment_id = ?
                )
                ''', (assessment_id,))

                # Insert new normalized grades
                for i in range(len(grades)):
                    cursor.execute('''
                    INSERT INTO normalized_grades
                    (grade_id, z_score, percentile, curved_score, curved_letter)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (grade_ids[i], z_scores[i], percentiles[i], curved_scores[i], curved_letters[i]))

                # Update the actual grades?
                update_actual = input("Update the actual grades with the curved values? (y/n): ").strip().lower()

                if update_actual == 'y':
                    for i in range(len(grades)):
                        cursor.execute('''
                        UPDATE grades
                        SET score = ?, letter_grade = ?
                        WHERE grade_id = ?
                        ''', (curved_scores[i], curved_letters[i], grade_ids[i]))

                    print("Actual grades updated with curved values.")

                    # Update module grades for affected students
                    for student_id in set(student_ids):
                        # Get the module code for this assessment
                        cursor.execute('''
                        SELECT module_code FROM assessments WHERE assessment_id = ?
                        ''', (assessment_id,))
                        module_code = cursor.fetchone()[0]

                        # Update the module grade
                        update_module_grade(cursor, student_id, module_code)

                conn.commit()
                print("Normalized grades saved to database.")
        else:
            # Just display z-scores and percentiles without curving
            print("\nNormalization Results (no curving applied):")
            print(f"{'Student':<30} {'Original Score':<15} {'Original Grade':<15} {'Z-Score':<10} {'Percentile':<12}")
            print("-" * 85)

            for i in range(len(grades)):
                print(f"{student_names[i]:<30} {scores[i]:<15.2f} {letter_grades[i]:<15} {z_scores[i]:<10.2f} {percentiles[i]:<12.2f}")

            # Save to database?
            save = input("\nSave these normalization statistics to the database? (y/n): ").strip().lower()

            if save == 'y':
                # Clear any existing normalized grades for this assessment
                cursor.execute('''
                DELETE FROM normalized_grades WHERE grade_id IN (
                    SELECT grade_id FROM grades WHERE assessment_id = ?
                )
                ''', (assessment_id,))

                # Insert new normalized grades (without curved values)
                for i in range(len(grades)):
                    cursor.execute('''
                    INSERT INTO normalized_grades
                    (grade_id, z_score, percentile, curved_score, curved_letter)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (grade_ids[i], z_scores[i], percentiles[i], scores[i], letter_grades[i]))

                conn.commit()
                print("Normalization statistics saved to database.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")


def validate_grade_data_integrity(cursor):
    """Validate the integrity of grade data in the system"""
    print("\nValidating Grade Data Integrity...")

    issues_found = []

    # Check for grades without corresponding assessments
    cursor.execute('''
    SELECT COUNT(*) FROM grades g
    LEFT JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE a.assessment_id IS NULL
    ''')

    orphaned_grades = cursor.fetchone()[0]
    if orphaned_grades > 0:
        issues_found.append(f"Found {orphaned_grades} grades without corresponding assessments")

    # Check for students without any grades
    cursor.execute('''
    SELECT COUNT(*) FROM students s
    LEFT JOIN grades g ON s.student_id = g.student_id
    WHERE g.student_id IS NULL
    ''')

    students_no_grades = cursor.fetchone()[0]
    if students_no_grades > 0:
        issues_found.append(f"Found {students_no_grades} students without any grades")

    # Check for invalid grade ranges
    cursor.execute('''
    SELECT COUNT(*) FROM grades g
    JOIN assessments a ON g.assessment_id = a.assessment_id
    WHERE g.score < 0 OR g.score > a.max_points
    ''')

    invalid_scores = cursor.fetchone()[0]
    if invalid_scores > 0:
        issues_found.append(f"Found {invalid_scores} grades with invalid score ranges")

    # Display results
    if issues_found:
        print("Data integrity issues found:")
        for issue in issues_found:
            print(f"  - {issue}")
    else:
        print("No data integrity issues found")

    return len(issues_found) == 0
