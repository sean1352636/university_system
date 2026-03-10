"""Analytics and visualization mixin for AIDetector - confidence distributions, timelines, correlations, etc."""

import os
import re
import json
import math
import statistics
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import Dict, List, Any

from education_system.university_system.utils.ai.ai_detector.core.constants import (
    logger,
    ML_AVAILABLE,
)

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
except ImportError:
    pass


class AnalyticsMixin:
    """Mixin providing advanced analytics and visualization functions (15-22)."""

    # =========================================================================
    # ADVANCED ANALYTICS & VISUALIZATION FUNCTIONS (15-22)
    # =========================================================================

    def show_detection_confidence_distribution(self, limit: int = 1000) -> Dict[str, Any]:
        """
        Histogram of confidence scores across all submissions.
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT ai_score, confidence FROM ai_detector_results
            WHERE ai_score IS NOT NULL
            ORDER BY created_at DESC
            LIMIT ?
            ''', (limit,))

            results = cursor.fetchall()
            conn.close()

            if not results:
                return {'error': 'No results found', 'distribution': None}

            ai_scores = [r['ai_score'] for r in results]
            confidence_scores = [r['confidence'] for r in results if r['confidence']]

            # Create histogram bins
            bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

            ai_histogram = {f"{bins[i]:.1f}-{bins[i+1]:.1f}": 0 for i in range(len(bins)-1)}
            confidence_histogram = {f"{bins[i]:.1f}-{bins[i+1]:.1f}": 0 for i in range(len(bins)-1)}

            for score in ai_scores:
                for i in range(len(bins)-1):
                    if bins[i] <= score < bins[i+1]:
                        ai_histogram[f"{bins[i]:.1f}-{bins[i+1]:.1f}"] += 1
                        break
                if score == 1.0:
                    ai_histogram["0.9-1.0"] += 1

            for score in confidence_scores:
                for i in range(len(bins)-1):
                    if bins[i] <= score < bins[i+1]:
                        confidence_histogram[f"{bins[i]:.1f}-{bins[i+1]:.1f}"] += 1
                        break
                if score == 1.0:
                    confidence_histogram["0.9-1.0"] += 1

            return {
                'total_analyzed': len(results),
                'ai_score_distribution': {
                    'histogram': ai_histogram,
                    'mean': round(sum(ai_scores)/len(ai_scores), 3),
                    'median': round(sorted(ai_scores)[len(ai_scores)//2], 3),
                    'std_dev': round(statistics.stdev(ai_scores), 3) if len(ai_scores) > 1 else 0
                },
                'confidence_distribution': {
                    'histogram': confidence_histogram,
                    'mean': round(sum(confidence_scores)/len(confidence_scores), 3) if confidence_scores else 0,
                    'median': round(sorted(confidence_scores)[len(confidence_scores)//2], 3) if confidence_scores else 0
                },
                'ascii_chart': self._generate_ascii_histogram(ai_histogram),
                'generated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generating confidence distribution: {e}")
            return {'error': str(e)}

    def _generate_ascii_histogram(self, histogram: Dict[str, int]) -> str:
        """Generate ASCII art histogram"""
        max_count = max(histogram.values()) if histogram.values() else 1
        lines = ["AI Score Distribution:", ""]

        for range_str, count in histogram.items():
            bar_length = int((count / max_count) * 40) if max_count > 0 else 0
            bar = '\u2588' * bar_length
            lines.append(f"{range_str}: {bar} ({count})")

        return '\n'.join(lines)

    def generate_word_cloud(self, flagged_only: bool = False, limit: int = 500) -> Dict[str, Any]:
        """
        Generate word frequency data for word cloud from flagged vs clean submissions.
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            if flagged_only:
                cursor.execute('''
                SELECT s.submission_text
                FROM ai_detector_submissions s
                JOIN ai_detector_results r ON s.id = r.submission_id
                WHERE r.ai_score >= 0.7
                ORDER BY s.submission_date DESC
                LIMIT ?
                ''', (limit,))
            else:
                cursor.execute('''
                SELECT s.submission_text, r.ai_score
                FROM ai_detector_submissions s
                JOIN ai_detector_results r ON s.id = r.submission_id
                ORDER BY s.submission_date DESC
                LIMIT ?
                ''', (limit,))

            results = cursor.fetchall()
            conn.close()

            if not results:
                return {'error': 'No submissions found', 'word_frequencies': None}

            # Separate flagged and clean
            flagged_text = []
            clean_text = []

            for row in results:
                text = row['submission_text']
                if flagged_only:
                    flagged_text.append(text)
                else:
                    if row['ai_score'] and row['ai_score'] >= 0.7:
                        flagged_text.append(text)
                    else:
                        clean_text.append(text)

            # Stop words to exclude
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                         'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
                         'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                         'should', 'may', 'might', 'must', 'shall', 'can', 'this', 'that',
                         'these', 'those', 'it', 'its', 'they', 'their', 'them', 'we', 'our',
                         'you', 'your', 'i', 'my', 'me', 'he', 'she', 'his', 'her', 'as', 'if'}

            def get_word_freq(texts):
                all_words = []
                for text in texts:
                    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
                    all_words.extend([w for w in words if w not in stop_words])
                return dict(Counter(all_words).most_common(100))

            flagged_freq = get_word_freq(flagged_text) if flagged_text else {}
            clean_freq = get_word_freq(clean_text) if clean_text else {}

            # Find distinguishing words
            distinguishing_flagged = {}
            for word, count in flagged_freq.items():
                clean_count = clean_freq.get(word, 0)
                if count > clean_count * 1.5:  # 50% more common in flagged
                    distinguishing_flagged[word] = count

            return {
                'flagged_submissions_count': len(flagged_text),
                'clean_submissions_count': len(clean_text),
                'flagged_word_frequencies': flagged_freq,
                'clean_word_frequencies': clean_freq,
                'distinguishing_words_in_flagged': dict(list(distinguishing_flagged.items())[:30]),
                'generated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generating word cloud data: {e}")
            return {'error': str(e)}

    def plot_submission_timeline(self, student_id: str = None, days: int = 30) -> Dict[str, Any]:
        """
        Interactive timeline of submissions with risk indicators.
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

            if student_id:
                cursor.execute('''
                SELECT s.id, s.student_id, s.title, s.submission_date, s.word_count,
                       r.ai_score, r.confidence
                FROM ai_detector_submissions s
                LEFT JOIN ai_detector_results r ON s.id = r.submission_id
                WHERE s.student_id = ? AND s.submission_date >= ?
                ORDER BY s.submission_date ASC
                ''', (student_id, cutoff_date))
            else:
                cursor.execute('''
                SELECT s.id, s.student_id, s.title, s.submission_date, s.word_count,
                       r.ai_score, r.confidence
                FROM ai_detector_submissions s
                LEFT JOIN ai_detector_results r ON s.id = r.submission_id
                WHERE s.submission_date >= ?
                ORDER BY s.submission_date ASC
                ''', (cutoff_date,))

            results = cursor.fetchall()
            conn.close()

            if not results:
                return {'error': 'No submissions in timeframe', 'timeline': None}

            # Group by date
            daily_data = defaultdict(lambda: {'count': 0, 'high_risk': 0, 'total_score': 0, 'submissions': []})

            for row in results:
                date = row['submission_date'][:10]  # YYYY-MM-DD
                daily_data[date]['count'] += 1

                ai_score = row['ai_score'] or 0
                daily_data[date]['total_score'] += ai_score

                if ai_score >= 0.7:
                    daily_data[date]['high_risk'] += 1

                risk_indicator = '\U0001f534' if ai_score >= 0.8 else '\U0001f7e1' if ai_score >= 0.5 else '\U0001f7e2'

                daily_data[date]['submissions'].append({
                    'id': row['id'],
                    'student': row['student_id'],
                    'title': row['title'],
                    'ai_score': ai_score,
                    'risk_indicator': risk_indicator
                })

            # Calculate averages
            timeline = []
            for date in sorted(daily_data.keys()):
                data = daily_data[date]
                timeline.append({
                    'date': date,
                    'submission_count': data['count'],
                    'high_risk_count': data['high_risk'],
                    'avg_ai_score': round(data['total_score'] / data['count'], 3) if data['count'] > 0 else 0,
                    'submissions': data['submissions'][:10]  # Limit per day
                })

            # Generate ASCII timeline
            ascii_timeline = self._generate_ascii_timeline(timeline)

            return {
                'student_filter': student_id,
                'days_analyzed': days,
                'total_submissions': len(results),
                'timeline': timeline,
                'ascii_visualization': ascii_timeline,
                'summary': {
                    'busiest_day': max(timeline, key=lambda x: x['submission_count'])['date'] if timeline else None,
                    'highest_risk_day': max(timeline, key=lambda x: x['avg_ai_score'])['date'] if timeline else None
                },
                'generated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generating submission timeline: {e}")
            return {'error': str(e)}

    def _generate_ascii_timeline(self, timeline: List[Dict]) -> str:
        """Generate ASCII timeline visualization"""
        if not timeline:
            return "No data to display"

        lines = ["Submission Timeline:", "Date       | Submissions | Avg Score | Risk", "-" * 50]

        for day in timeline[-14:]:  # Last 14 days
            count = day['submission_count']
            avg_score = day['avg_ai_score']
            risk = '\U0001f534' if avg_score >= 0.7 else '\U0001f7e1' if avg_score >= 0.4 else '\U0001f7e2'
            bar = '\u2593' * min(count, 20)

            lines.append(f"{day['date']} | {bar:<20} ({count:2}) | {avg_score:.2f}    | {risk}")

        return '\n'.join(lines)

    def show_correlation_matrix(self) -> Dict[str, Any]:
        """
        Show correlations between different detection metrics.
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT s.word_count, s.character_count, r.ai_score, r.confidence, r.style_deviation
            FROM ai_detector_submissions s
            JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE r.ai_score IS NOT NULL
            LIMIT 1000
            ''')

            results = cursor.fetchall()
            conn.close()

            if len(results) < 10:
                return {'error': 'Insufficient data for correlation analysis', 'correlations': None}

            # Extract metrics
            metrics = {
                'word_count': [r['word_count'] or 0 for r in results],
                'ai_score': [r['ai_score'] for r in results],
                'confidence': [r['confidence'] or 0 for r in results]
            }

            # Calculate simple correlations (Pearson)
            def pearson_correlation(x, y):
                n = len(x)
                if n == 0:
                    return 0

                mean_x = sum(x) / n
                mean_y = sum(y) / n

                numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))

                std_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x) / n)
                std_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y) / n)

                if std_x == 0 or std_y == 0:
                    return 0

                return numerator / (n * std_x * std_y)

            correlations = {}
            metric_names = list(metrics.keys())

            for i, m1 in enumerate(metric_names):
                for m2 in metric_names[i+1:]:
                    corr = pearson_correlation(metrics[m1], metrics[m2])
                    correlations[f"{m1}_vs_{m2}"] = round(corr, 3)

            # Generate ASCII matrix
            ascii_matrix = self._generate_ascii_correlation_matrix(metrics, metric_names)

            return {
                'sample_size': len(results),
                'correlations': correlations,
                'interpretation': self._interpret_correlations(correlations),
                'ascii_matrix': ascii_matrix,
                'generated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generating correlation matrix: {e}")
            return {'error': str(e)}

    def _generate_ascii_correlation_matrix(self, metrics: Dict, names: List[str]) -> str:
        """Generate ASCII correlation matrix"""
        lines = ["Correlation Matrix:", ""]

        # Header
        header = "            " + "  ".join(f"{n[:8]:<10}" for n in names)
        lines.append(header)
        lines.append("-" * len(header))

        def pearson(x, y):
            n = len(x)
            if n == 0:
                return 0
            mean_x, mean_y = sum(x)/n, sum(y)/n
            num = sum((x[i]-mean_x)*(y[i]-mean_y) for i in range(n))
            std_x = math.sqrt(sum((xi-mean_x)**2 for xi in x)/n)
            std_y = math.sqrt(sum((yi-mean_y)**2 for yi in y)/n)
            return num/(n*std_x*std_y) if std_x and std_y else 0

        for i, n1 in enumerate(names):
            row = f"{n1[:10]:<10}  "
            for j, n2 in enumerate(names):
                if i == j:
                    row += "   1.00   "
                elif j > i:
                    corr = pearson(metrics[n1], metrics[n2])
                    row += f"  {corr:+.2f}   "
                else:
                    row += "    -     "
            lines.append(row)

        return '\n'.join(lines)

    def _interpret_correlations(self, correlations: Dict) -> List[str]:
        """Interpret correlation results"""
        interpretations = []

        for pair, corr in correlations.items():
            if abs(corr) > 0.7:
                strength = "strong"
            elif abs(corr) > 0.4:
                strength = "moderate"
            else:
                strength = "weak"

            direction = "positive" if corr > 0 else "negative"
            interpretations.append(f"{pair}: {strength} {direction} correlation ({corr})")

        return interpretations

    def cluster_similar_submissions(self, min_cluster_size: int = 3, limit: int = 500) -> Dict[str, Any]:
        """
        Use ML clustering to find suspiciously similar submissions.
        """
        try:
            if not ML_AVAILABLE:
                return {
                    'error': 'ML libraries (sklearn) not available for clustering',
                    'clusters': None
                }

            conn = self._safe_db_connect()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT s.id, s.student_id, s.submission_text, s.title, r.ai_score
            FROM ai_detector_submissions s
            LEFT JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE s.submission_text IS NOT NULL AND length(s.submission_text) > 100
            ORDER BY s.submission_date DESC
            LIMIT ?
            ''', (limit,))

            submissions = cursor.fetchall()
            conn.close()

            if len(submissions) < min_cluster_size * 2:
                return {'error': 'Insufficient submissions for clustering', 'clusters': None}

            # Vectorize text
            texts = [s['submission_text'] for s in submissions]
            vectorizer = TfidfVectorizer(max_features=500, stop_words='english')
            tfidf_matrix = vectorizer.fit_transform(texts)

            # Determine optimal number of clusters
            n_clusters = min(len(submissions) // min_cluster_size, 20)

            # Perform K-means clustering
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(tfidf_matrix)

            # Group submissions by cluster
            clusters = defaultdict(list)
            for i, label in enumerate(cluster_labels):
                clusters[int(label)].append({
                    'submission_id': submissions[i]['id'],
                    'student_id': submissions[i]['student_id'],
                    'title': submissions[i]['title'],
                    'ai_score': submissions[i]['ai_score'],
                    'text_preview': texts[i][:200] + '...'
                })

            # Filter to clusters with multiple different students (potentially suspicious)
            suspicious_clusters = []
            for cluster_id, members in clusters.items():
                unique_students = set(m['student_id'] for m in members)
                if len(members) >= min_cluster_size and len(unique_students) > 1:
                    suspicious_clusters.append({
                        'cluster_id': cluster_id,
                        'size': len(members),
                        'unique_students': len(unique_students),
                        'members': members,
                        'suspicion_level': 'high' if len(unique_students) >= 3 else 'medium'
                    })

            # Sort by suspicion
            suspicious_clusters.sort(key=lambda x: x['unique_students'], reverse=True)

            return {
                'total_submissions_analyzed': len(submissions),
                'total_clusters': n_clusters,
                'suspicious_clusters': suspicious_clusters[:10],  # Top 10
                'suspicious_cluster_count': len(suspicious_clusters),
                'method': 'TF-IDF + K-means clustering',
                'analyzed_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error clustering submissions: {e}")
            return {'error': str(e)}

    def generate_department_comparison(self) -> Dict[str, Any]:
        """
        Compare AI detection rates across departments/courses.
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT s.course_code, COUNT(*) as submission_count,
                   AVG(r.ai_score) as avg_score,
                   COUNT(CASE WHEN r.ai_score >= 0.7 THEN 1 END) as high_risk_count
            FROM ai_detector_submissions s
            JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE s.course_code IS NOT NULL AND s.course_code != ''
            GROUP BY s.course_code
            HAVING submission_count >= 5
            ORDER BY avg_score DESC
            ''')

            results = cursor.fetchall()
            conn.close()

            if not results:
                return {'error': 'No course data available', 'comparison': None}

            comparison = []
            for row in results:
                high_risk_ratio = row['high_risk_count'] / row['submission_count'] if row['submission_count'] > 0 else 0
                comparison.append({
                    'course_code': row['course_code'],
                    'submission_count': row['submission_count'],
                    'avg_ai_score': round(row['avg_score'], 3),
                    'high_risk_count': row['high_risk_count'],
                    'high_risk_ratio': round(high_risk_ratio, 3),
                    'risk_level': 'high' if high_risk_ratio > 0.3 else 'medium' if high_risk_ratio > 0.1 else 'low'
                })

            # Calculate overall statistics
            all_scores = [c['avg_ai_score'] for c in comparison]

            return {
                'courses_analyzed': len(comparison),
                'comparison': comparison,
                'overall_statistics': {
                    'mean_ai_score': round(sum(all_scores) / len(all_scores), 3),
                    'highest_risk_course': comparison[0]['course_code'] if comparison else None,
                    'lowest_risk_course': comparison[-1]['course_code'] if comparison else None
                },
                'ascii_chart': self._generate_department_ascii_chart(comparison[:10]),
                'generated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generating department comparison: {e}")
            return {'error': str(e)}

    def _generate_department_ascii_chart(self, comparison: List[Dict]) -> str:
        """Generate ASCII bar chart for department comparison"""
        lines = ["Course AI Score Comparison:", ""]

        for course in comparison:
            score = course['avg_ai_score']
            bar_length = int(score * 40)
            bar = '\u2588' * bar_length
            risk = '\U0001f534' if score >= 0.7 else '\U0001f7e1' if score >= 0.4 else '\U0001f7e2'

            lines.append(f"{course['course_code']:<10} {bar:<40} {score:.2f} {risk}")

        return '\n'.join(lines)

    def show_weekly_trends(self, weeks: int = 12) -> Dict[str, Any]:
        """
        Weekly trend analysis with anomaly highlighting.
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            cutoff_date = (datetime.now() - timedelta(weeks=weeks)).isoformat()

            cursor.execute('''
            SELECT s.submission_date, r.ai_score
            FROM ai_detector_submissions s
            JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE s.submission_date >= ?
            ORDER BY s.submission_date ASC
            ''', (cutoff_date,))

            results = cursor.fetchall()
            conn.close()

            if not results:
                return {'error': 'No data in timeframe', 'trends': None}

            # Group by week
            weekly_data = defaultdict(lambda: {'scores': [], 'count': 0})

            for row in results:
                date = datetime.fromisoformat(row['submission_date'])
                week_start = (date - timedelta(days=date.weekday())).strftime('%Y-%m-%d')

                weekly_data[week_start]['count'] += 1
                if row['ai_score'] is not None:
                    weekly_data[week_start]['scores'].append(row['ai_score'])

            # Calculate weekly statistics
            trends = []
            for week in sorted(weekly_data.keys()):
                data = weekly_data[week]
                scores = data['scores']

                week_stats = {
                    'week_start': week,
                    'submission_count': data['count'],
                    'avg_ai_score': round(sum(scores)/len(scores), 3) if scores else 0,
                    'high_risk_count': len([s for s in scores if s >= 0.7]),
                    'high_risk_ratio': round(len([s for s in scores if s >= 0.7])/len(scores), 3) if scores else 0
                }
                trends.append(week_stats)

            # Detect anomalies (weeks with unusual activity)
            anomalies = []
            if len(trends) >= 3:
                avg_scores = [t['avg_ai_score'] for t in trends]
                mean_score = sum(avg_scores) / len(avg_scores)
                std_dev = statistics.stdev(avg_scores) if len(avg_scores) > 1 else 0

                for i, week in enumerate(trends):
                    # Check for score anomalies (>2 std dev from mean)
                    if std_dev > 0 and abs(week['avg_ai_score'] - mean_score) > 2 * std_dev:
                        anomalies.append({
                            'week': week['week_start'],
                            'type': 'score_anomaly',
                            'value': week['avg_ai_score'],
                            'deviation': round((week['avg_ai_score'] - mean_score) / std_dev, 2)
                        })

                    # Check for volume anomalies
                    avg_count = sum(t['submission_count'] for t in trends) / len(trends)
                    if week['submission_count'] > avg_count * 2:
                        anomalies.append({
                            'week': week['week_start'],
                            'type': 'volume_spike',
                            'value': week['submission_count'],
                            'normal_avg': round(avg_count, 1)
                        })

            return {
                'weeks_analyzed': len(trends),
                'trends': trends,
                'anomalies': anomalies,
                'overall_trend': self._calculate_overall_trend(trends),
                'ascii_chart': self._generate_weekly_ascii_chart(trends),
                'generated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generating weekly trends: {e}")
            return {'error': str(e)}

    def _calculate_overall_trend(self, trends: List[Dict]) -> str:
        """Calculate overall trend direction"""
        if len(trends) < 2:
            return 'insufficient_data'

        first_half = trends[:len(trends)//2]
        second_half = trends[len(trends)//2:]

        first_avg = sum(t['avg_ai_score'] for t in first_half) / len(first_half)
        second_avg = sum(t['avg_ai_score'] for t in second_half) / len(second_half)

        diff = second_avg - first_avg

        if diff > 0.05:
            return 'increasing (concerning)'
        elif diff < -0.05:
            return 'decreasing (improving)'
        else:
            return 'stable'

    def _generate_weekly_ascii_chart(self, trends: List[Dict]) -> str:
        """Generate ASCII chart for weekly trends"""
        lines = ["Weekly AI Score Trends:", ""]

        for week in trends[-12:]:  # Last 12 weeks
            score = week['avg_ai_score']
            count = week['submission_count']
            bar_length = int(score * 30)
            bar = '\u2593' * bar_length

            lines.append(f"{week['week_start']} | {bar:<30} {score:.2f} (n={count})")

        return '\n'.join(lines)

    def export_visualization_pack(self, output_dir: str = None) -> Dict[str, Any]:
        """
        Export all charts/graphs as data pack for reports.
        """
        try:
            if output_dir is None:
                output_dir = os.path.join(os.path.dirname(self.db_path), 'ai_detector_exports')

            os.makedirs(output_dir, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # Collect all visualizations
            visualizations = {}

            # 1. Confidence distribution
            conf_dist = self.show_detection_confidence_distribution()
            visualizations['confidence_distribution'] = conf_dist

            # 2. Weekly trends
            weekly = self.show_weekly_trends()
            visualizations['weekly_trends'] = weekly

            # 3. Department comparison
            dept = self.generate_department_comparison()
            visualizations['department_comparison'] = dept

            # 4. Correlation matrix
            corr = self.show_correlation_matrix()
            visualizations['correlation_matrix'] = corr

            # 5. Word cloud data
            word_cloud = self.generate_word_cloud()
            visualizations['word_cloud_data'] = word_cloud

            # Save to JSON file
            export_path = os.path.join(output_dir, f'visualization_pack_{timestamp}.json')
            with open(export_path, 'w') as f:
                json.dump(visualizations, f, indent=2, default=str)

            # Generate summary report
            summary_path = os.path.join(output_dir, f'summary_report_{timestamp}.txt')
            with open(summary_path, 'w') as f:
                f.write("AI DETECTOR VISUALIZATION REPORT\n")
                f.write(f"Generated: {datetime.now().isoformat()}\n")
                f.write("=" * 60 + "\n\n")

                if conf_dist.get('ascii_chart'):
                    f.write(conf_dist['ascii_chart'] + "\n\n")

                if weekly.get('ascii_chart'):
                    f.write(weekly['ascii_chart'] + "\n\n")

                if dept.get('ascii_chart'):
                    f.write(dept['ascii_chart'] + "\n\n")

                if corr.get('ascii_matrix'):
                    f.write(corr['ascii_matrix'] + "\n\n")

            return {
                'success': True,
                'export_directory': output_dir,
                'files_created': [
                    export_path,
                    summary_path
                ],
                'visualizations_included': list(visualizations.keys()),
                'exported_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error exporting visualization pack: {e}")
            return {'success': False, 'error': str(e)}
