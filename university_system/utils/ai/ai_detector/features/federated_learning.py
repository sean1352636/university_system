"""Federated learning for AI detection models."""

import pickle
from datetime import datetime
from typing import Dict, Optional

from university_system.utils.ai.ai_detector.core.constants import logger, ML_AVAILABLE

try:
    import numpy as np
except ImportError:
    np = None


class FederatedLearning:
    """Implements federated learning for AI detection models"""

    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.model_updates = []
        self.institution_id = None

    def initialize_federation(self, institution_id: str, federation_config: Dict):
        """Initialize federated learning setup"""
        self.institution_id = institution_id
        self.federation_config = federation_config

        # Create federated learning table
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS federated_learning (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                institution_id TEXT NOT NULL,
                model_update BLOB NOT NULL,
                update_round INTEGER NOT NULL,
                accuracy_metric REAL,
                privacy_budget REAL,
                created_at TEXT NOT NULL
            )
            ''')

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error initializing federated learning: {e}")

    def contribute_model_update(self, local_model_weights: 'np.ndarray', privacy_budget: float = 1.0):
        """Contribute model update while preserving privacy"""
        if not ML_AVAILABLE:
            return

        # Add differential privacy noise
        noise_scale = 1.0 / privacy_budget
        noisy_weights = local_model_weights + np.random.laplace(0, noise_scale, local_model_weights.shape)

        # Serialize weights
        weights_blob = pickle.dumps(noisy_weights)

        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()

            # Get current round
            cursor.execute('SELECT MAX(update_round) FROM federated_learning WHERE institution_id = ?',
                          (self.institution_id,))
            result = cursor.fetchone()
            current_round = (result[0] or 0) + 1

            # Store update
            cursor.execute('''
            INSERT INTO federated_learning
            (institution_id, model_update, update_round, privacy_budget, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (self.institution_id, weights_blob, current_round, privacy_budget,
                  datetime.now().isoformat()))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error contributing model update: {e}")

    def aggregate_model_updates(self, round_number: int) -> Optional['np.ndarray']:
        """Aggregate model updates from different institutions"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT model_update, privacy_budget
            FROM federated_learning
            WHERE update_round = ?
            ''', (round_number,))

            updates = cursor.fetchall()
            conn.close()

            if not updates:
                return None

            # Weighted average based on privacy budget
            total_weights = None
            total_budget = 0

            for update_blob, budget in updates:
                weights = pickle.loads(update_blob)

                if total_weights is None:
                    total_weights = weights * budget
                else:
                    total_weights += weights * budget

                total_budget += budget

            if total_budget > 0:
                return total_weights / total_budget

            return None

        except Exception as e:
            logger.error(f"Error aggregating model updates: {e}")
            return None
