"""Core text analysis mixin for AIDetector.

Every analysis — ``analyze_text``, ``analyze_text_enhanced``,
``analyze_text_ultimate`` — produces the same honest reading
(``detector/reading``): the labelled indicators of
``application/integrity/ai_indicators`` (strength, level, the passages behind each)
plus informational extras (disguised characters, citation checks,
paraphrase-tool and prompt-artefact patterns, the trained model's estimate
when one is active). Extras are shown to staff and never change the
strength. A reading is an indication to review with the student, never a
verdict, and nothing recommends proceedings.

The result dict keeps the keys screens already read:

* ``ai_score`` — the indicator strength (0 when there is too little text)
* ``needs_review`` — strength at or above the integrity setting
  ``ai_review_threshold``; ``is_ai_generated`` is the same value, kept only
  for older screens
* ``confidence`` — how much text the reading rests on (0–1, full at 1,000
  words), never a fixed number
* ``level``, ``risk_level`` (low / medium / high against the threshold),
  ``indicators``, ``passages``, ``informational``, ``recommendations``,
  ``detailed_results`` (the whole stored reading), ``notice``
* ``submission_id`` (the detector's submission row) and ``result_id``
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger, OCR_AVAILABLE
from education_system.systems.university.shared.ai.ai_detector.core.dataclasses import SubmissionMetadata
from education_system.systems.university.shared.ai.ai_detector.core.exceptions import (
    AIDetectionError, DatabaseError, PrivacyError,  # noqa: F401 - re-exported for callers
)
from education_system.systems.university.shared.ai.ai_detector.detector import reading as reading_mod

NOTICE = ("These are indicators, not evidence: no tool can tell reliably whether a person or a "
          "model wrote a text. Review it with the student; the student's account matters more "
          "than any reading.")


def _send_after_commit(emails) -> None:
    if emails:
        from education_system.systems.university.infrastructure.ui.record_screens import (
            send_emails,
        )
        send_emails(emails)


class CoreAnalysisMixin:
    """Mixin providing text analysis, scoring, and reporting methods."""

    # ── analysis ────────────────────────────────────────────────────────

    def analyze_text(self, text: str, title: str = None, student_id: str = None,
                     course_code: str = None, assignment_id: str = None,
                     submission_id: int = None, file_type: str = "txt") -> Dict[str, Any]:
        """The main entry point: a full reading of ``text`` for a student on
        a module (see :meth:`analyze_text_enhanced`)."""
        return self.analyze_text_enhanced(text, title, student_id, course_code, assignment_id,
                                          submission_id=submission_id, file_type=file_type)

    def analyze_text_enhanced(self, text, title=None, student_id=None, course_code=None,
                              assignment_id=None, *, submission_id=None, file_type="txt",
                              full=True):
        """Take and store a reading. The signed-in member of staff must
        review the module; a module whose AI-writing readings are turned off
        is skipped (``{"skipped": True}``). Display labels for the student,
        module or assignment are turned back into ids."""
        from education_system.systems.university.application.integrity import (
            access as integrity_access,
        )
        if not str(text or "").strip():
            raise AIDetectionError("There is no text to read")
        conn = self._safe_db_connect()
        try:
            who = self.require_staff(conn)
            student, module, assignment = reading_mod.normalise_ids(
                conn, student_id, course_code, assignment_id)
            if module is None and assignment is not None:
                row = conn.execute("SELECT module_code FROM assignments WHERE id = ?",
                                   (assignment,)).fetchone()
                module = row[0] if row else None
            if module is None:
                if not integrity_access.is_officer(conn, who):
                    raise PermissionError("Choose the module the work belongs to")
            elif not integrity_access.can_review(conn, who, module):
                raise PermissionError(f"You do not review {module}")
            if module and not integrity_access.ai_checks_enabled(conn, module):
                logger.info("AI-writing readings are off for %s — skipped", module)
                return {"skipped": True, "course_code": module,
                        "reason": f"AI-writing readings are turned off for {module}"}
            reading = reading_mod.analyse(conn, text, file_type, full=full, detector=self)
            result_id = reading_mod.store(
                conn, reading, text=text, student_id=student, module_code=module,
                assignment_id=assignment, submission_id=submission_id,
                title=title or "Text read in the AI Content Detector", file_type=file_type,
                checked_by=who.username)
            emails = reading_mod.alert_emails(conn, result_id)
            detector_sub = conn.execute("SELECT submission_id FROM ai_detector_results WHERE "
                                        "id = ?", (result_id,)).fetchone()[0]
            limit = reading_mod.threshold(conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        _send_after_commit(emails)
        logger.info("AI-writing reading %s taken by %s", result_id, who.username)
        return self._result(reading, result_id, detector_sub, limit, student, module, assignment)

    def _result(self, reading, result_id, detector_sub, limit, student, module, assignment):
        strength = reading.get("strength")
        needs_review = strength is not None and strength >= limit
        return {
            'submission_id': detector_sub,
            'result_id': result_id,
            'student_id': student,
            'course_code': module,
            'assignment_id': assignment,
            'ai_score': 0.0 if strength is None else strength,
            'strength': strength,
            'level': reading.get('level'),
            'needs_review': needs_review,
            'is_ai_generated': needs_review,
            'confidence': reading.get('coverage', 0.0),
            'risk_level': self._risk_word(strength, limit),
            'words_checked': reading.get('words_checked'),
            'indicators': reading.get('indicators', []),
            'passages': reading.get('passages', []),
            'informational': reading.get('detector', {}).get('informational', []),
            'extras': {k: v for k, v in reading.get('detector', {}).items()
                       if k != 'informational'},
            'recommendations': self._recommendations(reading, needs_review),
            'detailed_results': reading,
            'notice': NOTICE,
        }

    @staticmethod
    def _risk_word(strength, limit) -> str:
        if strength is None or strength < limit:
            return 'low'
        return 'high' if strength >= max(limit, 0.85) else 'medium'

    @staticmethod
    def _recommendations(reading, needs_review) -> List[str]:
        if reading.get('strength') is None:
            return [reading.get('note') or "Not enough of the student's own prose to read."]
        found = []
        keys = {i['key'] for i in reading.get('indicators', [])
                if i['key'] != 'artefacts' or i.get('value')}
        if 'artefacts' in keys:
            found.append("Leftover chat text was found: ask the student how it got into their "
                         "work.")
        if needs_review:
            found.append("Several indicators point the same way. Talk to the student about "
                         "how they wrote it (drafts, notes, version history) before deciding "
                         "anything; a reading alone is never enough.")
        disguised = next((i for i in reading.get('detector', {}).get('informational', [])
                          if i.get('key') == 'disguised' and i.get('value')), None)
        if disguised:
            found.append(f"{disguised['value']} disguised character(s) found: ask about them; "
                         "they are sometimes used to get past checks.")
        if not found:
            found.append("No follow-up suggested by this reading.")
        return found

    def _full_extras(self, text) -> Dict[str, Any]:
        """The slower informational extras for a full reading."""
        extras: Dict[str, Any] = {}
        on = getattr(self, 'detection_methods', {}) or {}
        if self.citation_verifier is not None and on.get('citation_verification', True):
            extras['citations'] = self.citation_verifier.verify_citations(text).to_dict()
        if self.adversarial_detector is not None and on.get('disguised_characters', True):
            extras['adversarial'] = self.adversarial_detector.detect_evasion_attempts(text).to_dict()
        if on.get('paraphrase_tools', True):
            extras['paraphrase_tools'] = self.detect_paraphrasing_tools(text)
        if on.get('prompt_artifacts', True):
            extras['prompt_artifacts'] = self.analyze_prompt_artifacts(text)
        return extras

    def analyze_text_ultimate(self, text: str, title: str = None, student_id: str = None,
                              course_code: str = None, assignment_id: str = None,
                              metadata: SubmissionMetadata = None, images: List[bytes] = None,
                              code_content: str = None, programming_language: str = None,
                              submission_id: int = None) -> Dict[str, Any]:
        """A full reading plus the analyses that need more than text:
        writing time and editor data (``metadata``), images, code. All of
        these are informational and never change the strength."""
        if self.privacy_manager is not None:
            self.privacy_manager.record_data_access('analyze_text', student_id, 'submission_text')
        results = self.analyze_text_enhanced(text, title, student_id, course_code, assignment_id,
                                             submission_id=submission_id)
        if results.get('skipped'):
            return results
        advanced: Dict[str, Any] = {}
        on = getattr(self, 'detection_methods', {}) or {}
        if (metadata and metadata.time_taken and self.temporal_analyzer is not None
                and on.get('temporal_analysis', True)):
            advanced['temporal'] = self.temporal_analyzer.analyze_writing_speed(
                text, metadata.time_taken).to_dict()
        if metadata and self.behavioral_analyzer is not None and on.get('behavioral_analysis',
                                                                         True):
            advanced['behavioral'] = self.behavioral_analyzer.analyze_submission_behavior(
                metadata, text).to_dict()
        if images and self.multimodal_analyzer is not None:
            advanced['multimodal'] = self.multimodal_analyzer.analyze_image_text_consistency(
                text, images).to_dict()
        if code_content and programming_language and self.multimodal_analyzer is not None:
            advanced['code'] = self.multimodal_analyzer.analyze_code_submission(
                code_content, programming_language).to_dict()
        advanced.update({k: v for k, v in results['extras'].items()
                         if k in ('citations', 'adversarial')})
        results['advanced_analyses'] = advanced
        results['risk_factors'] = [name for name, found in advanced.items()
                                   if found.get('risk_level') in ('medium', 'high')]
        results['final_risk_level'] = results['risk_level']
        results['recommendations'] = self._generate_ultimate_recommendations(results)
        if self.visual_analyzer is not None:
            results['visual_analysis'] = {
                'writing_flow': self.visual_analyzer.generate_writing_flow_visualization(text)}
        self._store_advanced_results(results, metadata)
        return results

    def _get_student_demographics(self, student_id: str) -> Optional[Dict[str, str]]:
        """A student's recorded demographics (bias analysis only)."""
        conn = self._safe_db_connect()
        try:
            row = conn.execute('SELECT * FROM student_demographics WHERE student_id = ?',
                               (student_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def _generate_ultimate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """The reading's suggestions plus what the extra analyses show."""
        recommendations = list(results.get('recommendations', []))
        advanced = results.get('advanced_analyses', {})
        if advanced.get('temporal', {}).get('evidence', {}).get('anomaly'):
            recommendations.append("Ask how the work was drafted: it was written faster than "
                                   "usual (it may have been written elsewhere first).")
        citations = advanced.get('citations', {}).get('evidence', {})
        if citations.get('suspicious_citations'):
            recommendations.append(f"{citations['suspicious_citations']} citation(s) could not "
                                   "be found or are dated in the future: check them with the "
                                   "student.")
        if advanced.get('code', {}).get('evidence', {}).get('patterns_found'):
            recommendations.append("Leftover chat text in the code: ask the student to explain "
                                   "their implementation.")
        return recommendations

    def _calculate_final_risk_level(self, results: Dict[str, Any]) -> str:
        """The reading's risk word (the extras never raise it)."""
        return results.get('risk_level', 'low')

    def _store_advanced_results(self, results: Dict[str, Any], metadata: SubmissionMetadata):
        """Keep the extra analyses with the reading."""
        conn = self._safe_db_connect()
        try:
            submission_id = results['submission_id']
            if metadata:
                conn.execute('''
                INSERT INTO ai_detector_metadata
                (submission_id, time_taken, browser_info, device_fingerprint, ip_address, location_data)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (submission_id, metadata.time_taken,
                      json.dumps(metadata.browser_info) if metadata.browser_info else None,
                      metadata.device_fingerprint, metadata.ip_address,
                      json.dumps(metadata.location) if metadata.location else None))
            advanced = results.get('advanced_analyses', {})
            conn.execute('''
            INSERT INTO advanced_detection_results
            (submission_id, temporal_analysis, citation_analysis, behavioral_analysis,
             multimodal_analysis, adversarial_analysis, ensemble_prediction, risk_prediction,
             bias_adjusted_score, blockchain_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
            ''', (submission_id,
                  json.dumps(advanced.get('temporal')), json.dumps(advanced.get('citations')),
                  json.dumps(advanced.get('behavioral')),
                  json.dumps(advanced.get('multimodal') or advanced.get('code')),
                  json.dumps(advanced.get('adversarial')),
                  json.dumps(next((i for i in results.get('informational', [])
                                   if i.get('key') == 'model_estimate'), None)),
                  results.get('blockchain_hash')))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── components ──────────────────────────────────────────────────────

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
        """Train the models (``ml`` / model management)."""
        self.require_officer()
        found = {}
        if self.advanced_ml_trainer is not None:
            found['ensemble_training'] = self.advanced_ml_trainer.train_ensemble_model()
        if self.predictive_analytics is not None:
            found['predictive_training'] = self.predictive_analytics.train_risk_prediction_model()
        return found

    # ── bias ────────────────────────────────────────────────────────────

    def analyze_institutional_bias(self, institution_id: str = None) -> Dict[str, Any]:
        """How readings fall across recorded demographic groups (integrity
        officers): per group, the share of readings at the review level."""
        conn = self._safe_db_connect()
        try:
            self.require_officer(conn)
            limit = reading_mod.threshold(conn)
            sql = ('SELECT sd.gender, sd.ethnicity, sd.native_language, sd.academic_level, '
                   'r.ai_score FROM student_demographics sd JOIN ai_detector_submissions s ON '
                   'sd.student_id = s.student_id JOIN ai_detector_results r ON '
                   'r.submission_id = s.id')
            params: list = []
            if institution_id:
                sql += ' WHERE s.institution_id = ?'
                params.append(institution_id)
            demographic_data: Dict[str, List] = {}
            for row in conn.execute(sql, params).fetchall():
                for field in ('gender', 'ethnicity', 'native_language', 'academic_level'):
                    if row[field]:
                        demographic_data.setdefault(field, []).append(
                            {'group': row[field], 'score': row['ai_score'],
                             'flagged': (row['ai_score'] or 0) >= limit})
        finally:
            conn.close()
        bias_analysis = (self.bias_detector.analyze_detection_bias(demographic_data)
                         if self.bias_detector is not None else None)
        return {'institution_id': institution_id, 'bias_analysis': bias_analysis,
                'groups': {k: len(v) for k, v in demographic_data.items()},
                'generated_at': datetime.now().isoformat()}

    # ── reports ─────────────────────────────────────────────────────────

    def generate_comprehensive_report(self, report_type: str, **kwargs) -> Dict[str, Any]:
        """Reports by type."""
        if report_type == 'institution_dashboard':
            return self._generate_institution_dashboard(**kwargs)
        if report_type == 'student_risk_profile':
            return self._generate_student_risk_profile(**kwargs)
        if report_type == 'compliance_audit':
            return self.compliance_manager.generate_compliance_report()
        if report_type == 'bias_analysis':
            return self.analyze_institutional_bias(kwargs.get('institution_id'))
        if report_type == 'benchmark_comparison':
            return self.institution_benchmarking.generate_benchmark_report(**kwargs)
        raise ValueError(f"Unknown report type {report_type!r}: institution_dashboard, "
                         "student_risk_profile, compliance_audit, bias_analysis or "
                         "benchmark_comparison")

    def _generate_institution_dashboard(self, institution_id: str = None,
                                        period: str = '1_month') -> Dict[str, Any]:
        """Readings over a period on the modules the signed-in person sees."""
        days = {'1_month': 30, '3_months': 90, '1_year': 365}.get(period, 30)
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        conn = self._safe_db_connect()
        try:
            scope, params = self._scope_sql(self._module_scope(conn))
            limit = reading_mod.threshold(conn)
            high = max(limit, 0.85)
            where = " WHERE s.submission_date >= ?" + scope
            if institution_id:
                where += " AND s.institution_id = ?"
            args = [start_date] + params + ([institution_id] if institution_id else [])
            base = ("FROM ai_detector_submissions s JOIN ai_detector_results r ON "
                    "s.id = r.submission_id" + where)
            basic_metrics = conn.execute(
                "SELECT COUNT(*) AS total_submissions, COUNT(DISTINCT s.student_id) AS "
                "unique_students, COUNT(DISTINCT s.course_code) AS courses, AVG(r.ai_score) AS "
                "avg_ai_score, COUNT(CASE WHEN r.ai_score >= ? THEN 1 END) AS flagged_submissions "
                + base, [limit] + args).fetchone()
            trend_data = conn.execute(
                "SELECT DATE(s.submission_date) AS date, COUNT(*) AS daily_submissions, "
                "AVG(r.ai_score) AS daily_avg_score " + base +
                " GROUP BY DATE(s.submission_date) ORDER BY date", args).fetchall()
            risk_distribution = {row['risk_level']: row['count'] for row in conn.execute(
                "SELECT CASE WHEN r.ai_score >= ? THEN 'high' WHEN r.ai_score >= ? THEN 'medium' "
                "ELSE 'low' END AS risk_level, COUNT(*) AS count " + base +
                " GROUP BY risk_level", [high, limit] + args).fetchall()}
        finally:
            conn.close()
        return {
            'institution_id': institution_id,
            'period': period,
            'review_threshold': limit,
            'basic_metrics': dict(basic_metrics),
            'trend_analysis': [dict(row) for row in trend_data],
            'risk_distribution': risk_distribution,
            'benchmark_comparison': (self.institution_benchmarking.generate_benchmark_report(
                institution_id, period) if self.institution_benchmarking is not None else None),
            'compliance_status': self.compliance_manager.generate_compliance_report(),
            'generated_at': datetime.now().isoformat()
        }

    def _generate_student_risk_profile(self, student_id: str) -> Dict[str, Any]:
        """A student's readings over time, for a member of staff who
        reviews their modules. No prediction about the student is made from
        their history, and when they submit is not used."""
        submissions = self.get_submission_history(student_id=student_id, limit=50)
        scores = [s['ai_score'] for s in submissions['submissions'] if s['ai_score'] is not None]
        trend = 'stable'
        if len(scores) >= 4:
            recent = sum(scores[:3]) / 3
            older = sum(scores[3:6]) / len(scores[3:6])
            if recent > older + 0.2:
                trend = 'rising'
            elif recent < older - 0.2:
                trend = 'falling'
        recent5 = scores[:5]
        return {
            'student_id': student_id,
            'submission_history': submissions,
            'trend_analysis': {'trend': trend, 'recent_submissions': len(recent5),
                               'avg_recent_score': sum(recent5) / len(recent5) if recent5 else 0},
            'recommendations': self._generate_student_recommendations({}, {}, trend),
            'note': 'Readings are indicators; a trend in them is not evidence about the student.',
            'generated_at': datetime.now().isoformat()
        }

    def _generate_student_recommendations(self, risk_prediction: Dict, temporal_patterns: Dict,
                                          trend: str) -> List[str]:
        if trend == 'rising':
            return ["Readings on this student's work have risen: a conversation about how they "
                    "work, and about the support available, may help."]
        return []

    def enable_student_self_check(self) -> str:
        """Where students check their own drafts: the Academic Integrity
        window's draft check and their own AI-writing readings."""
        return ("Students check drafts and see their own AI-writing readings in the University "
                "app: Academic Integrity → Check a draft / My AI-writing readings.")

    def get_ultimate_statistics(self) -> Dict[str, Any]:
        """Statistics plus the state of each component."""
        basic_stats = self.get_enhanced_statistics()
        processor = self.realtime_processor
        return {
            **basic_stats,
            'real_time_processing': {
                'queued_tasks': len(getattr(processor, 'processing_queue', []) or []),
                'active_workers': len(getattr(processor, 'workers', []) or []),
                'is_running': bool(getattr(processor, 'is_running', False)),
            } if processor is not None else None,
            'component_errors': dict(self.component_errors),
            'features_active': {
                'federated_learning': self.federated_learning is not None,
                'blockchain_audit': self.blockchain_audit is not None,
                'bias_detection': self.bias_detector is not None,
                'predictive_analytics': self.predictive_analytics is not None,
                'adversarial_detection': self.adversarial_detector is not None,
                'citation_verification': self.citation_verifier is not None,
                'temporal_analysis': self.temporal_analyzer is not None,
                'multimodal_analysis': OCR_AVAILABLE,
                'behavioral_analysis': self.behavioral_analyzer is not None,
            }
        }

    # ── storing (kept for callers) ──────────────────────────────────────

    def _calculate_basic_ai_score(self, text):
        """The indicator strength of ``text`` (0 when too short)."""
        from education_system.systems.university.application.integrity import ai_indicators
        return ai_indicators.assess(text).get('strength') or 0.0

    def _store_submission(self, text, title, student_id, course_code, assignment_id):
        """Removed: readings are stored whole by :meth:`analyze_text_enhanced`
        (``detector/reading.store``), with real ids."""
        raise AIDetectionError("Use analyze_text: readings are stored whole with real ids")

    def _store_results(self, submission_id, ai_score, confidence, detailed_results):
        raise AIDetectionError("Use analyze_text: readings are stored whole with real ids")

    def _detect_ai_patterns(self, text):
        """The reading's indicators, in the older shape."""
        from education_system.systems.university.application.integrity import ai_indicators
        found = ai_indicators.assess(text)
        return {'indicators': [{'name': i['label'], 'score': i['value'], 'shown': i['shown']}
                               for i in found['indicators']],
                'overall_score': found.get('strength') or 0.0,
                'confidence': reading_mod.coverage(found)}
