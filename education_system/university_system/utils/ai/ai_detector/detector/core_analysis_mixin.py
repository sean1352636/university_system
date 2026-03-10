"""Core text analysis mixin for AIDetector."""

import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from education_system.university_system.utils.ai.ai_detector.core.constants import logger, OCR_AVAILABLE
from education_system.university_system.utils.ai.ai_detector.core.enums import RiskLevel
from education_system.university_system.utils.ai.ai_detector.core.dataclasses import SubmissionMetadata
from education_system.university_system.utils.ai.ai_detector.core.exceptions import (
    AIDetectionError, DatabaseError, PrivacyError,
)


class CoreAnalysisMixin:
    """Mixin providing text analysis, scoring, and reporting methods."""

    def analyze_text(self, text: str, title: str = None, student_id: str = None,
                    course_code: str = None, assignment_id: str = None) -> Dict[str, Any]:
        """
        Basic text analysis method - wrapper for enhanced analysis
        This method provides backward compatibility and serves as the main entry point
        """
        try:
            # Call the enhanced analysis method
            result = self.analyze_text_enhanced(
                text=text,
                title=title,
                student_id=student_id,
                course_code=course_code,
                assignment_id=assignment_id
            )

            logger.info(f"Text analysis completed for {len(text)} characters")
            return result

        except Exception as e:
            logger.error(f"Error in text analysis: {e}")
            raise AIDetectionError(f"Analysis failed: {e}")

    def analyze_text_ultimate(self, text: str, title: str = None, student_id: str = None,
                             course_code: str = None, assignment_id: str = None,
                             metadata: SubmissionMetadata = None, images: List[bytes] = None,
                             code_content: str = None, programming_language: str = None) -> Dict[str, Any]:
        """Ultimate text analysis with all advanced features"""

        # Check privacy compliance first
        if student_id:
            compliance_check = self.compliance_manager.check_compliance_before_processing(
                student_id, 'ai_detection'
            )
            if not compliance_check['can_process']:
                raise PrivacyError(f"Cannot process due to compliance requirements: {compliance_check['requirements']}")

        # Record data access for audit
        self.privacy_manager.record_data_access('analyze_text', student_id, 'submission_text')

        # Start with base analysis
        base_results = super().analyze_text_enhanced(text, title, student_id, course_code, assignment_id)

        # Initialize ultimate results
        ultimate_results = base_results.copy()
        ultimate_results['advanced_analyses'] = {}
        ultimate_results['risk_factors'] = []
        ultimate_results['recommendations'] = []

        # Temporal Analysis
        if metadata and metadata.time_taken:
            temporal_result = self.temporal_analyzer.analyze_writing_speed(text, metadata.time_taken)
            ultimate_results['advanced_analyses']['temporal'] = temporal_result.__dict__
            if temporal_result.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                ultimate_results['risk_factors'].append('unusual_writing_speed')

        # Citation Verification
        citation_result = self.citation_verifier.verify_citations(text)
        ultimate_results['advanced_analyses']['citations'] = citation_result.__dict__
        if citation_result.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            ultimate_results['risk_factors'].append('suspicious_citations')

        # Behavioral Analysis
        if metadata:
            behavioral_result = self.behavioral_analyzer.analyze_submission_behavior(metadata, text)
            ultimate_results['advanced_analyses']['behavioral'] = behavioral_result.__dict__
            if behavioral_result.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                ultimate_results['risk_factors'].append('suspicious_behavior')

        # Multi-Modal Analysis
        if images:
            multimodal_result = self.multimodal_analyzer.analyze_image_text_consistency(text, images)
            ultimate_results['advanced_analyses']['multimodal'] = multimodal_result.__dict__
            if multimodal_result.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                ultimate_results['risk_factors'].append('image_text_inconsistency')

        # Code Analysis
        if code_content and programming_language:
            code_result = self.multimodal_analyzer.analyze_code_submission(code_content, programming_language)
            ultimate_results['advanced_analyses']['code'] = code_result.__dict__
            if code_result.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                ultimate_results['risk_factors'].append('ai_generated_code')

        # Adversarial Detection
        adversarial_result = self.adversarial_detector.detect_evasion_attempts(text)
        ultimate_results['advanced_analyses']['adversarial'] = adversarial_result.__dict__
        if adversarial_result.risk_level == RiskLevel.CRITICAL:
            ultimate_results['risk_factors'].append('evasion_attempt')

        # Advanced ML Prediction
        ensemble_prediction = self.advanced_ml_trainer.predict_ensemble(text)
        if ensemble_prediction:
            ultimate_results['advanced_analyses']['ensemble_ml'] = ensemble_prediction
            # Update overall score with ensemble prediction
            ensemble_weight = 0.3
            ultimate_results['ai_score'] = (
                ultimate_results['ai_score'] * (1 - ensemble_weight) +
                ensemble_prediction['ensemble_score'] * ensemble_weight
            )

        # Bias Detection and Correction
        if student_id:
            # Get student demographics for bias analysis
            student_demographics = self._get_student_demographics(student_id)
            if student_demographics:
                bias_adjusted_score = self.bias_detector.apply_bias_correction(
                    ultimate_results['ai_score'], student_demographics
                )
                ultimate_results['bias_adjusted_score'] = bias_adjusted_score

        # Predictive Risk Analysis
        if student_id:
            risk_prediction = self.predictive_analytics.predict_student_risk(student_id)
            ultimate_results['advanced_analyses']['risk_prediction'] = risk_prediction
            if risk_prediction['risk_level'] == 'high':
                ultimate_results['risk_factors'].append('high_risk_student_profile')

        # Visual Analysis Data
        if ultimate_results.get('sentence_analysis'):
            sentence_scores = [s['ai_score'] for s in ultimate_results['sentence_analysis']['sentences']]
            heatmap_data = self.visual_analyzer.generate_text_heatmap(text, sentence_scores)
            ultimate_results['visual_analysis'] = {
                'heatmap': heatmap_data,
                'writing_flow': self.visual_analyzer.generate_writing_flow_visualization(text)
            }

        # Generate comprehensive recommendations
        ultimate_results['recommendations'] = self._generate_ultimate_recommendations(ultimate_results)

        # Calculate final risk level
        ultimate_results['final_risk_level'] = self._calculate_final_risk_level(ultimate_results)

        # Create blockchain record for audit trail
        blockchain_hash = self.blockchain_audit.create_detection_record(
            ultimate_results['submission_id'], ultimate_results
        )
        ultimate_results['blockchain_hash'] = blockchain_hash

        # Store advanced results
        self._store_advanced_results(ultimate_results, metadata)

        return ultimate_results

    def _get_student_demographics(self, student_id: str) -> Optional[Dict[str, str]]:
        """Get student demographics for bias analysis"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM student_demographics WHERE student_id = ?', (student_id,))
            result = cursor.fetchone()
            conn.close()

            return dict(result) if result else None

        except Exception as e:
            logger.debug(f"Error getting student demographics: {e}")
            return None

    def _generate_ultimate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate comprehensive recommendations based on all analyses"""
        recommendations = []

        # Risk-based recommendations
        risk_factors = results.get('risk_factors', [])

        if 'unusual_writing_speed' in risk_factors:
            recommendations.append("Consider reviewing the submission timeline and interviewing the student about their writing process")

        if 'suspicious_citations' in risk_factors:
            recommendations.append("Verify citations manually and discuss proper citation practices with the student")

        if 'suspicious_behavior' in risk_factors:
            recommendations.append("Review submission metadata and consider requiring supervised completion of future assignments")

        if 'evasion_attempt' in risk_factors:
            recommendations.append("CRITICAL: Evidence of deliberate evasion detected. Immediate review recommended")

        if 'ai_generated_code' in risk_factors:
            recommendations.append("Review code for originality and consider requiring explanation of implementation choices")

        # Score-based recommendations
        final_score = results.get('ai_score', 0)

        if final_score > 0.9:
            recommendations.append("High confidence AI detection. Consider academic integrity proceedings")
        elif final_score > 0.7:
            recommendations.append("Probable AI usage. Follow up with student interview recommended")
        elif final_score > 0.5:
            recommendations.append("Some AI indicators present. Educational intervention may be beneficial")

        # Predictive recommendations
        risk_prediction = results.get('advanced_analyses', {}).get('risk_prediction', {})
        if risk_prediction.get('risk_level') == 'high':
            recommendations.append("Student profile indicates elevated risk. Consider additional support and monitoring")

        return recommendations

    def _calculate_final_risk_level(self, results: Dict[str, Any]) -> str:
        """Calculate final risk level based on all factors"""
        risk_factors = results.get('risk_factors', [])
        ai_score = results.get('ai_score', 0)

        # Critical factors
        if 'evasion_attempt' in risk_factors:
            return 'critical'

        # High risk factors
        high_risk_count = sum(1 for factor in risk_factors if factor in [
            'suspicious_citations', 'ai_generated_code', 'high_risk_student_profile'
        ])

        if ai_score > 0.9 or high_risk_count >= 2:
            return 'high'
        elif ai_score > 0.7 or high_risk_count >= 1:
            return 'medium'
        else:
            return 'low'

    def _store_advanced_results(self, results: Dict[str, Any], metadata: SubmissionMetadata):
        """Store advanced analysis results"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            submission_id = results['submission_id']

            # Store metadata if provided
            if metadata:
                cursor.execute('''
                INSERT OR REPLACE INTO ai_detector_metadata
                (submission_id, time_taken, browser_info, device_fingerprint, ip_address, location_data)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    submission_id,
                    metadata.time_taken,
                    json.dumps(metadata.browser_info) if metadata.browser_info else None,
                    metadata.device_fingerprint,
                    metadata.ip_address,
                    json.dumps(metadata.location) if metadata.location else None
                ))

            # Store advanced results
            advanced_analyses = results.get('advanced_analyses', {})

            cursor.execute('''
            INSERT INTO advanced_detection_results
            (submission_id, temporal_analysis, citation_analysis, behavioral_analysis,
             multimodal_analysis, adversarial_analysis, ensemble_prediction, risk_prediction,
             bias_adjusted_score, blockchain_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                submission_id,
                json.dumps(advanced_analyses.get('temporal')),
                json.dumps(advanced_analyses.get('citations')),
                json.dumps(advanced_analyses.get('behavioral')),
                json.dumps(advanced_analyses.get('multimodal')),
                json.dumps(advanced_analyses.get('adversarial')),
                json.dumps(advanced_analyses.get('ensemble_ml')),
                json.dumps(advanced_analyses.get('risk_prediction')),
                results.get('bias_adjusted_score'),
                results.get('blockchain_hash')
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error storing advanced results: {e}")

    def start_real_time_monitoring(self, num_workers: int = 3):
        """Start real-time submission monitoring"""
        self.realtime_processor.start_real_time_processing(num_workers)
        logger.info("Real-time monitoring started")

    def stop_real_time_monitoring(self):
        """Stop real-time submission monitoring"""
        self.realtime_processor.stop_real_time_processing()
        logger.info("Real-time monitoring stopped")

    def configure_federated_learning(self, institution_id: str, federation_config: Dict):
        """Configure federated learning"""
        self.federated_learning.initialize_federation(institution_id, federation_config)
        logger.info(f"Federated learning configured for institution {institution_id}")

    def train_advanced_models(self):
        """Train all advanced ML models"""
        try:
            # Train ensemble model
            ensemble_results = self.advanced_ml_trainer.train_ensemble_model()
            logger.info(f"Ensemble model trained: {ensemble_results}")

            # Train risk prediction model
            self.predictive_analytics.train_risk_prediction_model()
            logger.info("Risk prediction model trained")

            return {
                'ensemble_training': ensemble_results,
                'risk_model_trained': True
            }

        except Exception as e:
            logger.error(f"Error training advanced models: {e}")
            return {'error': str(e)}

    def analyze_institutional_bias(self, institution_id: str) -> Dict[str, Any]:
        """Analyze bias in AI detection for an institution"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            # Get demographic data for institution
            cursor.execute('''
            SELECT sd.gender, sd.ethnicity, sd.native_language, sd.academic_level
            FROM student_demographics sd
            JOIN ai_detector_submissions s ON sd.student_id = s.student_id
            WHERE s.institution_id = ?
            ''', (institution_id,))

            demographic_data = {}
            for row in cursor.fetchall():
                for field, value in row.items():
                    if value:
                        if field not in demographic_data:
                            demographic_data[field] = []
                        demographic_data[field].append(value)

            conn.close()

            # Analyze bias across demographic groups
            bias_analysis = self.bias_detector.analyze_detection_bias(demographic_data)

            return {
                'institution_id': institution_id,
                'bias_analysis': bias_analysis,
                'generated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error analyzing institutional bias: {e}")
            return {'error': str(e)}

    def generate_comprehensive_report(self, report_type: str, **kwargs) -> Dict[str, Any]:
        """Generate comprehensive reports with all new features"""
        if report_type == 'institution_dashboard':
            return self._generate_institution_dashboard(**kwargs)
        elif report_type == 'student_risk_profile':
            return self._generate_student_risk_profile(**kwargs)
        elif report_type == 'compliance_audit':
            return self.compliance_manager.generate_compliance_report()
        elif report_type == 'bias_analysis':
            return self.analyze_institutional_bias(kwargs.get('institution_id'))
        elif report_type == 'benchmark_comparison':
            return self.institution_benchmarking.generate_benchmark_report(**kwargs)
        else:
            return super().generate_report(report_type, **kwargs)

    def _generate_institution_dashboard(self, institution_id: str, period: str = '1_month') -> Dict[str, Any]:
        """Generate comprehensive institution dashboard"""
        try:
            # Calculate period
            if period == '1_month':
                start_date = datetime.now() - timedelta(days=30)
            elif period == '3_months':
                start_date = datetime.now() - timedelta(days=90)
            elif period == '1_year':
                start_date = datetime.now() - timedelta(days=365)
            else:
                start_date = datetime.now() - timedelta(days=30)

            conn = self._safe_db_connect()
            cursor = conn.cursor()

            # Basic metrics
            cursor.execute('''
            SELECT
                COUNT(*) as total_submissions,
                COUNT(DISTINCT s.student_id) as unique_students,
                COUNT(DISTINCT s.course_code) as courses,
                AVG(r.ai_score) as avg_ai_score,
                COUNT(CASE WHEN r.ai_score >= 0.7 THEN 1 END) as flagged_submissions
            FROM ai_detector_submissions s
            JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE s.institution_id = ? AND s.submission_date >= ?
            ''', (institution_id, start_date.isoformat()))

            basic_metrics = cursor.fetchone()

            # Trend analysis
            cursor.execute('''
            SELECT
                DATE(s.submission_date) as date,
                COUNT(*) as daily_submissions,
                AVG(r.ai_score) as daily_avg_score
            FROM ai_detector_submissions s
            JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE s.institution_id = ? AND s.submission_date >= ?
            GROUP BY DATE(s.submission_date)
            ORDER BY date
            ''', (institution_id, start_date.isoformat()))

            trend_data = cursor.fetchall()

            # Risk distribution
            cursor.execute('''
            SELECT
                CASE
                    WHEN r.ai_score >= 0.9 THEN 'critical'
                    WHEN r.ai_score >= 0.7 THEN 'high'
                    WHEN r.ai_score >= 0.5 THEN 'medium'
                    ELSE 'low'
                END as risk_level,
                COUNT(*) as count
            FROM ai_detector_submissions s
            JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE s.institution_id = ? AND s.submission_date >= ?
            GROUP BY risk_level
            ''', (institution_id, start_date.isoformat()))

            risk_distribution = {row['risk_level']: row['count'] for row in cursor.fetchall()}

            conn.close()

            # Get benchmarking data
            benchmark_data = self.institution_benchmarking.generate_benchmark_report(institution_id, period)

            # Get compliance status
            compliance_data = self.compliance_manager.generate_compliance_report()

            dashboard = {
                'institution_id': institution_id,
                'period': period,
                'basic_metrics': dict(basic_metrics),
                'trend_analysis': [dict(row) for row in trend_data],
                'risk_distribution': risk_distribution,
                'benchmark_comparison': benchmark_data,
                'compliance_status': compliance_data,
                'generated_at': datetime.now().isoformat()
            }

            return dashboard

        except Exception as e:
            logger.error(f"Error generating institution dashboard: {e}")
            return {'error': str(e)}

    def _generate_student_risk_profile(self, student_id: str) -> Dict[str, Any]:
        """Generate comprehensive student risk profile"""
        try:
            # Get submission history
            submissions = self.list_submissions(student_id=student_id, limit=50)

            # Get predictive risk analysis
            risk_prediction = self.predictive_analytics.predict_student_risk(student_id)

            # Get temporal patterns
            temporal_patterns = self.temporal_analyzer.analyze_submission_patterns(student_id)

            # Calculate trend
            submission_scores = [s['ai_score'] for s in submissions['submissions'] if s['ai_score']]

            trend = 'stable'
            if len(submission_scores) >= 3:
                recent_avg = sum(submission_scores[:3]) / 3
                older_avg = sum(submission_scores[3:6]) / max(1, len(submission_scores[3:6]))

                if recent_avg > older_avg + 0.2:
                    trend = 'increasing_risk'
                elif recent_avg < older_avg - 0.2:
                    trend = 'decreasing_risk'

            profile = {
                'student_id': student_id,
                'submission_history': submissions,
                'risk_prediction': risk_prediction,
                'temporal_patterns': temporal_patterns,
                'trend_analysis': {
                    'trend': trend,
                    'recent_submissions': len(submission_scores[:5]),
                    'avg_recent_score': sum(submission_scores[:5]) / len(submission_scores[:5]) if submission_scores else 0
                },
                'recommendations': self._generate_student_recommendations(risk_prediction, temporal_patterns, trend),
                'generated_at': datetime.now().isoformat()
            }

            return profile

        except Exception as e:
            logger.error(f"Error generating student risk profile: {e}")
            return {'error': str(e)}

    def _generate_student_recommendations(self, risk_prediction: Dict, temporal_patterns: Dict, trend: str) -> List[str]:
        """Generate recommendations for student"""
        recommendations = []

        if risk_prediction.get('risk_level') == 'high':
            recommendations.append("High-risk profile detected. Consider academic integrity education and increased monitoring")

        if temporal_patterns.get('suspicious_hour_ratio', 0) > 0.5:
            recommendations.append("Unusual submission timing patterns. Consider discussing time management and study habits")

        if trend == 'increasing_risk':
            recommendations.append("Risk trend increasing. Early intervention recommended")
        elif trend == 'decreasing_risk':
            recommendations.append("Positive trend observed. Continue current support strategies")

        return recommendations

    def enable_student_self_check(self) -> str:
        """Enable student self-check functionality"""
        # In a real implementation, this would set up web endpoints or API access
        logger.info("Student self-check tool enabled")
        return "Self-check tool available at /student/self-check"

    def get_ultimate_statistics(self) -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        try:
            basic_stats = super().get_enhanced_statistics()

            # Add advanced statistics
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            # Advanced ML statistics
            cursor.execute('''
            SELECT
                COUNT(CASE WHEN ensemble_prediction IS NOT NULL THEN 1 END) as ensemble_predictions,
                AVG(bias_adjusted_score) as avg_bias_adjusted_score
            FROM advanced_detection_results
            WHERE ensemble_prediction IS NOT NULL
            ''')

            advanced_stats = cursor.fetchone()

            # Real-time processing stats
            queue_status = {
                'queued_tasks': len(self.realtime_processor.processing_queue),
                'active_workers': len(self.realtime_processor.workers),
                'is_running': self.realtime_processor.is_running
            }

            # Compliance stats
            cursor.execute('''
            SELECT
                COUNT(DISTINCT student_id) as students_with_consent
            FROM privacy_consent
            WHERE granted = 1
            ''')

            consent_stats = cursor.fetchone()

            conn.close()

            ultimate_stats = {
                **basic_stats,
                'advanced_ml': {
                    'ensemble_predictions': advanced_stats['ensemble_predictions'] if advanced_stats else 0,
                    'avg_bias_adjusted_score': advanced_stats['avg_bias_adjusted_score'] if advanced_stats else 0,
                    'models_available': len(self.advanced_ml_trainer.models)
                },
                'real_time_processing': queue_status,
                'privacy_compliance': {
                    'students_with_consent': consent_stats['students_with_consent'] if consent_stats else 0
                },
                'features_active': {
                    'federated_learning': bool(self.federated_learning.institution_id),
                    'blockchain_audit': len(self.blockchain_audit.blockchain) > 0,
                    'bias_detection': True,
                    'predictive_analytics': self.predictive_analytics.risk_model is not None,
                    'adversarial_detection': True,
                    'citation_verification': True,
                    'temporal_analysis': True,
                    'multimodal_analysis': OCR_AVAILABLE,
                    'behavioral_analysis': True
                }
            }

            return ultimate_stats

        except Exception as e:
            logger.error(f"Error getting ultimate statistics: {e}")
            return {'error': str(e)}

    def analyze_text_enhanced(self, text, title=None, student_id=None, course_code=None, assignment_id=None):
        """Enhanced text analysis (base method)"""
        # Basic AI detection logic
        ai_score = self._calculate_basic_ai_score(text)
        confidence = 0.8  # Default confidence

        # Store submission
        submission_id = self._store_submission(text, title, student_id, course_code, assignment_id)

        # Store results
        self._store_results(submission_id, ai_score, confidence, {})

        return {
            'submission_id': submission_id,
            'ai_score': ai_score,
            'confidence': confidence,
            'is_ai_generated': ai_score >= self.detection_threshold,
            'detailed_results': {}
        }

    def _calculate_basic_ai_score(self, text):
        """Calculate basic AI score"""
        # Simple pattern-based scoring
        score = 0.0

        # Check for AI patterns
        ai_patterns = [
            r'\bhowever\b.*\bfurthermore\b',
            r'\bon one hand\b.*\bon the other hand\b',
            r'\bit is important to note\b',
            r'\bgenerally speaking\b',
            r'\bit appears that\b'
        ]

        for pattern in ai_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                score += 0.2

        return min(1.0, score)

    def _store_submission(self, text, title, student_id, course_code, assignment_id):
        """Store submission in database"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO ai_detector_submissions
            (student_id, submission_text, title, course_code, assignment_id,
             submission_date, word_count, character_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                student_id or 'UNKNOWN',
                text,
                title,
                course_code,
                assignment_id,
                datetime.now().isoformat(),
                len(text.split()),
                len(text)
            ))

            submission_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return submission_id

        except Exception as e:
            logger.error(f"Error storing submission: {e}")
            raise DatabaseError(f"Failed to store submission: {e}")

    def _store_results(self, submission_id, ai_score, confidence, detailed_results):
        """Store analysis results"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO ai_detector_results
            (submission_id, ai_score, confidence, detailed_results, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (
                submission_id,
                ai_score,
                confidence,
                json.dumps(detailed_results),
                datetime.now().isoformat()
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error storing results: {e}")

    def _detect_ai_patterns(self, text):
        """Detect AI patterns in text"""
        patterns = {
            'hedging': [
                r'\bit seems\b', r'\bit appears\b', r'\bperhaps\b', r'\bmight be\b'
            ],
            'transitions': [
                r'\bhowever\b', r'\bfurthermore\b', r'\bmoreover\b', r'\btherefore\b'
            ],
            'formality': [
                r'\bgenerally speaking\b', r'\bit is important to note\b'
            ]
        }

        results = {'indicators': [], 'overall_score': 0, 'confidence': 0.8}
        total_score = 0

        for pattern_type, pattern_list in patterns.items():
            matches = 0
            for pattern in pattern_list:
                matches += len(re.findall(pattern, text, re.IGNORECASE))

            if matches > 0:
                score = min(1.0, matches / 5)  # Normalize
                total_score += score
                results['indicators'].append({
                    'name': pattern_type,
                    'score': score,
                    'matches': matches
                })

        results['overall_score'] = min(1.0, total_score / len(patterns))
        return results

    def set_auth(self, auth):
        """Set authentication handler"""
        self.auth = auth
        self.current_user = getattr(auth, 'current_user', None)
