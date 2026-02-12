"""Model and system management mixin for AI detector."""

import io
import os
import json
import time
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from university_system.utils.ai.ai_detector.core.constants import logger, ML_AVAILABLE

if ML_AVAILABLE:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score


# Allowed modules/classes for safe model deserialization
_SAFE_ML_MODULES = {
    'numpy', 'numpy.core', 'numpy.core.multiarray', 'numpy.core.numeric',
    'numpy.random', 'numpy.ma', 'numpy.ma.core',
    'sklearn', 'sklearn.ensemble', 'sklearn.ensemble._forest',
    'sklearn.feature_extraction', 'sklearn.feature_extraction.text',
    'sklearn.tree', 'sklearn.tree._classes', 'sklearn.tree._tree',
    'sklearn.utils', 'sklearn.utils._bunch',
    'sklearn.model_selection', 'sklearn.preprocessing',
    'sklearn.preprocessing._data', 'sklearn.metrics',
    'scipy', 'scipy.sparse', 'scipy.sparse._csr', 'scipy.sparse._csc',
    'scipy.sparse.csr', 'scipy.sparse.csc',
    'builtins', 'collections', 'copyreg', '_codecs',
}

_BLOCKED_NAMES = {'exec', 'eval', 'compile', '__import__', 'system', 'popen',
                  'subprocess', 'os', 'sys', 'globals', 'locals'}


class _RestrictedModelUnpickler(pickle.Unpickler):
    """Unpickler that only allows safe sklearn/numpy types for model deserialization."""

    def find_class(self, module, name):
        if name in _BLOCKED_NAMES:
            raise pickle.UnpicklingError(
                f"Restricted unpickler refused to load blocked name '{module}.{name}'"
            )
        # Check if the module is in our allowed list
        base_module = module.split('.')[0]
        if base_module in ('numpy', 'sklearn', 'scipy', 'builtins', 'collections',
                           'copyreg', '_codecs'):
            return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"Restricted unpickler refused to load '{module}.{name}'"
        )


def _safe_model_load(file_obj):
    """Safely load a pickled ML model, only allowing sklearn/numpy types."""
    return _RestrictedModelUnpickler(file_obj).load()


class ModelManagementMixin:
    """Mixin providing model and system management methods."""

    def retrain_detection_model(self, data_source: str = 'flagged',
                               include_negative: bool = True,
                               min_samples: int = 100) -> Dict[str, Any]:
        """
        Trigger model retraining with new data.

        Args:
            data_source: Source for training data (flagged/confirmed/path)
            include_negative: Include negative (human-written) samples
            min_samples: Minimum samples required for training

        Returns:
            Dict with training results and metrics
        """
        try:
            if not ML_AVAILABLE:
                return {'success': False, 'error': 'ML libraries not available'}

            start_time = time.time()

            # Collect training data
            conn = self._get_connection()
            cursor = conn.cursor()

            if data_source == 'flagged':
                cursor.execute('''
                    SELECT text_content, 1 as label FROM ai_detector_submissions
                    WHERE ai_score >= 0.7
                ''')
            elif data_source == 'confirmed':
                cursor.execute('''
                    SELECT s.text_content, 1 as label FROM ai_detector_submissions s
                    JOIN ai_detector_alerts a ON s.id = a.submission_id
                    WHERE a.status = 'confirmed'
                ''')
            else:
                # Custom dataset - would need to parse from file
                conn.close()
                return {'success': False, 'error': 'Custom dataset not implemented'}

            positive_samples = cursor.fetchall()

            negative_samples = []
            if include_negative:
                cursor.execute('''
                    SELECT text_content, 0 as label FROM ai_detector_submissions
                    WHERE ai_score < 0.3
                ''')
                negative_samples = cursor.fetchall()

            conn.close()

            # Combine samples
            all_samples = list(positive_samples) + list(negative_samples)

            if len(all_samples) < min_samples:
                return {
                    'success': False,
                    'error': f'Insufficient samples ({len(all_samples)}/{min_samples})'
                }

            # Prepare training data
            texts = [s['text_content'] for s in all_samples]
            labels = [s['label'] for s in all_samples]

            # Vectorize
            vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
            X = vectorizer.fit_transform(texts)
            y = np.array(labels)

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            # Train model
            model = RandomForestClassifier(n_estimators=100, random_state=42)
            model.fit(X_train, y_train)

            # Evaluate
            y_pred = model.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)

            # Calculate additional metrics
            from sklearn.metrics import precision_score, recall_score, f1_score
            precision = precision_score(y_test, y_pred, zero_division=0)
            recall = recall_score(y_test, y_pred, zero_division=0)
            f1 = f1_score(y_test, y_pred, zero_division=0)

            # Save model
            model_version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            model_dir = os.path.join(os.path.dirname(self.db_path), 'models')
            os.makedirs(model_dir, exist_ok=True)

            model_path = os.path.join(model_dir, f'detector_model_{model_version}.pkl')
            with open(model_path, 'wb') as f:
                pickle.dump({'model': model, 'vectorizer': vectorizer}, f)

            # Log model version
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_detector_model_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT UNIQUE NOT NULL,
                    model_path TEXT NOT NULL,
                    accuracy REAL,
                    precision_score REAL,
                    recall_score REAL,
                    f1_score REAL,
                    training_samples INTEGER,
                    is_active INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            ''')

            cursor.execute('''
                INSERT INTO ai_detector_model_versions
                (version, model_path, accuracy, precision_score, recall_score, f1_score,
                 training_samples, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            ''', (model_version, model_path, accuracy, precision, recall, f1,
                  len(all_samples), datetime.now().isoformat()))

            # Deactivate other versions
            cursor.execute('''
                UPDATE ai_detector_model_versions SET is_active = 0
                WHERE version != ?
            ''', (model_version,))

            conn.commit()
            conn.close()

            training_time = time.time() - start_time

            logger.info(f"Model retrained: {model_version} with accuracy {accuracy:.2%}")
            return {
                'success': True,
                'model_version': model_version,
                'training_samples': len(all_samples),
                'training_time': training_time,
                'metrics': {
                    'accuracy': accuracy,
                    'precision': precision,
                    'recall': recall,
                    'f1_score': f1
                }
            }

        except Exception as e:
            logger.error(f"Error retraining model: {e}")
            return {'success': False, 'error': str(e)}

    def list_model_versions(self) -> Dict[str, Any]:
        """List all available model versions"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT version, created_at, accuracy, is_active
                FROM ai_detector_model_versions
                ORDER BY created_at DESC
            ''')
            rows = cursor.fetchall()
            conn.close()

            versions = [
                {
                    'version': row['version'],
                    'created_at': row['created_at'],
                    'accuracy': row['accuracy'],
                    'is_active': bool(row['is_active'])
                }
                for row in rows
            ]

            return {'versions': versions}

        except Exception as e:
            logger.error(f"Error listing model versions: {e}")
            return {'versions': [], 'error': str(e)}

    def rollback_model_version(self, version_id: str, reason: str = None) -> Dict[str, Any]:
        """
        Rollback to previous model version if issues detected.

        Args:
            version_id: Version ID to rollback to
            reason: Reason for rollback

        Returns:
            Dict with rollback status
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Check version exists
            cursor.execute('''
                SELECT version, model_path FROM ai_detector_model_versions
                WHERE version = ?
            ''', (version_id,))
            version_row = cursor.fetchone()

            if not version_row:
                conn.close()
                return {'success': False, 'error': 'Version not found'}

            # Get current active version
            cursor.execute('''
                SELECT version FROM ai_detector_model_versions WHERE is_active = 1
            ''')
            active_row = cursor.fetchone()
            previous_version = active_row['version'] if active_row else None

            # Deactivate all and activate requested version
            cursor.execute('UPDATE ai_detector_model_versions SET is_active = 0')
            cursor.execute('''
                UPDATE ai_detector_model_versions SET is_active = 1 WHERE version = ?
            ''', (version_id,))

            # Log rollback
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_detector_model_rollbacks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_version TEXT,
                    to_version TEXT NOT NULL,
                    reason TEXT,
                    rolled_back_by TEXT,
                    rolled_back_at TEXT NOT NULL
                )
            ''')

            cursor.execute('''
                INSERT INTO ai_detector_model_rollbacks
                (from_version, to_version, reason, rolled_back_by, rolled_back_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (previous_version, version_id, reason,
                  self.current_user.get('username') if self.current_user else None,
                  datetime.now().isoformat()))

            conn.commit()
            conn.close()

            logger.info(f"Model rolled back from {previous_version} to {version_id}")
            return {
                'success': True,
                'previous_version': previous_version,
                'active_version': version_id,
                'rollback_time': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error rolling back model: {e}")
            return {'success': False, 'error': str(e)}

    def compare_model_versions(self, version_a: str, version_b: str,
                              sample_size: int = 100) -> Dict[str, Any]:
        """
        A/B test between model versions.

        Args:
            version_a: First version ID
            version_b: Second version ID
            sample_size: Number of samples to test

        Returns:
            Dict with comparison metrics
        """
        try:
            if not ML_AVAILABLE:
                return {'success': False, 'error': 'ML libraries not available'}

            conn = self._get_connection()
            cursor = conn.cursor()

            # Get model paths
            cursor.execute('''
                SELECT version, model_path FROM ai_detector_model_versions
                WHERE version IN (?, ?)
            ''', (version_a, version_b))
            rows = cursor.fetchall()

            if len(rows) < 2:
                conn.close()
                return {'success': False, 'error': 'One or both versions not found'}

            models = {row['version']: row['model_path'] for row in rows}

            # Get test samples
            cursor.execute('''
                SELECT text_content, ai_score FROM ai_detector_submissions
                ORDER BY RANDOM() LIMIT ?
            ''', (sample_size,))
            samples = cursor.fetchall()
            conn.close()

            if len(samples) < 10:
                return {'success': False, 'error': 'Not enough samples for comparison'}

            results = {}
            for version, model_path in models.items():
                try:
                    with open(model_path, 'rb') as f:
                        model_data = _safe_model_load(f)

                    model = model_data['model']
                    vectorizer = model_data['vectorizer']

                    texts = [s['text_content'] for s in samples]
                    true_labels = [1 if s['ai_score'] >= 0.7 else 0 for s in samples]

                    X = vectorizer.transform(texts)
                    predictions = model.predict(X)

                    start_time = time.time()
                    for _ in range(10):
                        model.predict(X[:10])
                    avg_inference = (time.time() - start_time) / 10

                    accuracy = accuracy_score(true_labels, predictions)
                    from sklearn.metrics import precision_score, recall_score
                    precision = precision_score(true_labels, predictions, zero_division=0)
                    recall = recall_score(true_labels, predictions, zero_division=0)

                    results[version] = {
                        'accuracy': accuracy,
                        'precision': precision,
                        'recall': recall,
                        'avg_inference_time': avg_inference
                    }

                except Exception as e:
                    logger.error(f"Error loading model {version}: {e}")
                    results[version] = {'error': str(e)}

            # Determine recommended version
            if results.get(version_a, {}).get('accuracy', 0) > results.get(version_b, {}).get('accuracy', 0):
                recommended = version_a
            else:
                recommended = version_b

            return {
                'success': True,
                'version_a_metrics': results.get(version_a, {}),
                'version_b_metrics': results.get(version_b, {}),
                'recommended_version': recommended,
                'samples_tested': len(samples)
            }

        except Exception as e:
            logger.error(f"Error comparing model versions: {e}")
            return {'success': False, 'error': str(e)}

    def export_model_weights(self, version_id: str = None, output_path: str = None,
                            include_config: bool = True,
                            include_training_data: bool = False) -> Dict[str, Any]:
        """
        Export trained model for backup/transfer.

        Args:
            version_id: Version to export (default: current active)
            output_path: Output directory
            include_config: Include model configuration
            include_training_data: Include training data metadata

        Returns:
            Dict with export details
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if version_id:
                cursor.execute('''
                    SELECT * FROM ai_detector_model_versions WHERE version = ?
                ''', (version_id,))
            else:
                cursor.execute('''
                    SELECT * FROM ai_detector_model_versions WHERE is_active = 1
                ''')

            row = cursor.fetchone()
            conn.close()

            if not row:
                return {'success': False, 'error': 'Model version not found'}

            model_path = row['model_path']
            version = row['version']

            if not os.path.exists(model_path):
                return {'success': False, 'error': 'Model file not found'}

            # Setup output
            if output_path is None:
                output_path = os.path.join(os.path.dirname(self.db_path), 'model_export')
            os.makedirs(output_path, exist_ok=True)

            files_created = []

            # Copy model file
            export_model_path = os.path.join(output_path, f'model_{version}.pkl')
            import shutil
            shutil.copy2(model_path, export_model_path)
            files_created.append(export_model_path)

            # Export config
            if include_config:
                config = {
                    'version': version,
                    'accuracy': row['accuracy'],
                    'precision': row['precision_score'],
                    'recall': row['recall_score'],
                    'f1_score': row['f1_score'],
                    'training_samples': row['training_samples'],
                    'created_at': row['created_at'],
                    'exported_at': datetime.now().isoformat()
                }
                config_path = os.path.join(output_path, f'config_{version}.json')
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
                files_created.append(config_path)

            # Calculate file size
            file_size = os.path.getsize(export_model_path)
            file_size_str = f"{file_size / 1024 / 1024:.2f} MB" if file_size > 1024*1024 else f"{file_size / 1024:.2f} KB"

            logger.info(f"Model exported: {version} to {output_path}")
            return {
                'success': True,
                'export_path': output_path,
                'version_id': version,
                'file_size': file_size_str,
                'files_created': files_created
            }

        except Exception as e:
            logger.error(f"Error exporting model weights: {e}")
            return {'success': False, 'error': str(e)}

    def import_model_weights(self, import_path: str, set_active: bool = False,
                            validate: bool = True) -> Dict[str, Any]:
        """
        Import pre-trained model weights.

        Args:
            import_path: Path to model weights file
            set_active: Whether to set as active model
            validate: Validate model before import

        Returns:
            Dict with import status
        """
        try:
            if not os.path.exists(import_path):
                return {'success': False, 'error': 'Import file not found'}

            # Validate model
            validation_result = {'is_valid': True, 'compatibility': 'compatible'}
            if validate:
                try:
                    with open(import_path, 'rb') as f:
                        model_data = _safe_model_load(f)

                    if 'model' not in model_data or 'vectorizer' not in model_data:
                        validation_result = {'is_valid': False, 'compatibility': 'invalid_structure'}
                except Exception as e:
                    validation_result = {'is_valid': False, 'compatibility': str(e)}

            if not validation_result['is_valid']:
                return {
                    'success': False,
                    'error': 'Model validation failed',
                    'validation': validation_result
                }

            # Generate version ID
            version_id = f"imported_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Copy to models directory
            model_dir = os.path.join(os.path.dirname(self.db_path), 'models')
            os.makedirs(model_dir, exist_ok=True)

            dest_path = os.path.join(model_dir, f'detector_model_{version_id}.pkl')
            import shutil
            shutil.copy2(import_path, dest_path)

            # Register in database
            conn = self._get_connection()
            cursor = conn.cursor()

            if set_active:
                cursor.execute('UPDATE ai_detector_model_versions SET is_active = 0')

            cursor.execute('''
                INSERT INTO ai_detector_model_versions
                (version, model_path, is_active, created_at)
                VALUES (?, ?, ?, ?)
            ''', (version_id, dest_path, 1 if set_active else 0, datetime.now().isoformat()))

            conn.commit()
            conn.close()

            logger.info(f"Model imported: {version_id}")
            return {
                'success': True,
                'version_id': version_id,
                'validation': validation_result
            }

        except Exception as e:
            logger.error(f"Error importing model weights: {e}")
            return {'success': False, 'error': str(e)}

    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            cache_size = len(getattr(self, '_analysis_cache', {}))
            return {
                'total_entries': cache_size,
                'memory_usage': f"{cache_size * 1024} bytes (estimate)",
                'hit_rate': getattr(self, '_cache_hit_rate', 0),
                'oldest_entry': 'N/A'
            }
        except Exception as e:
            return {'total_entries': 0, 'error': str(e)}

    def clear_analysis_cache(self, clear_all: bool = False, older_than_days: int = None,
                            student_id: str = None) -> Dict[str, Any]:
        """
        Clear cached analysis results to free memory.

        Args:
            clear_all: Clear entire cache
            older_than_days: Clear entries older than X days
            student_id: Clear specific student's cache

        Returns:
            Dict with cache clearing results
        """
        try:
            entries_cleared = 0

            # Clear in-memory cache
            if hasattr(self, '_analysis_cache'):
                if clear_all:
                    entries_cleared = len(self._analysis_cache)
                    self._analysis_cache = {}
                elif student_id:
                    keys_to_remove = [k for k in self._analysis_cache if student_id in str(k)]
                    for k in keys_to_remove:
                        del self._analysis_cache[k]
                        entries_cleared += 1

            # Clear database cache if exists
            conn = self._get_connection()
            cursor = conn.cursor()

            # Check if cache table exists
            cursor.execute('''
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='ai_detector_cache'
            ''')

            if cursor.fetchone():
                if clear_all:
                    cursor.execute('DELETE FROM ai_detector_cache')
                    entries_cleared += cursor.rowcount
                elif older_than_days:
                    cutoff = (datetime.now() - timedelta(days=older_than_days)).isoformat()
                    cursor.execute('DELETE FROM ai_detector_cache WHERE created_at < ?', (cutoff,))
                    entries_cleared += cursor.rowcount
                elif student_id:
                    cursor.execute('DELETE FROM ai_detector_cache WHERE student_id = ?', (student_id,))
                    entries_cleared += cursor.rowcount

            conn.commit()
            conn.close()

            logger.info(f"Cache cleared: {entries_cleared} entries")
            return {
                'success': True,
                'entries_cleared': entries_cleared,
                'memory_freed': f"{entries_cleared * 1024} bytes (estimate)"
            }

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return {'success': False, 'error': str(e)}
