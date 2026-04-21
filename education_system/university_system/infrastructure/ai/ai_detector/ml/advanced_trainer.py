"""Advanced ML training with multiple algorithms and techniques."""

import re
from typing import Dict, List, Tuple, Any

from education_system.university_system.infrastructure.ai.ai_detector.core.constants import logger, ML_AVAILABLE
from education_system.university_system.infrastructure.ai.ai_detector.core.exceptions import AIDetectionError

# Import ML libraries conditionally
try:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.ensemble import RandomForestClassifier, IsolationForest
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score
except ImportError:
    pass

try:
    import transformers
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


class AdvancedMLTrainer:
    """Advanced ML training with multiple algorithms and techniques"""

    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.models = {}
        self.ensemble_model = None
        self.feature_importance = {}

    def train_ensemble_model(self, use_advanced_features: bool = True):
        """Train ensemble model with multiple algorithms"""
        if not ML_AVAILABLE:
            raise AIDetectionError("scikit-learn not available for ML training")

        try:
            # Prepare training data
            X, y, feature_names = self._prepare_advanced_training_data(use_advanced_features)

            if len(X) < 100:
                raise AIDetectionError("Insufficient training data")

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

            # Train multiple models
            models_to_train = {
                'random_forest': RandomForestClassifier(n_estimators=200, random_state=42),
                'isolation_forest': IsolationForest(contamination=0.1, random_state=42),
            }

            if TRANSFORMERS_AVAILABLE:
                models_to_train['neural_network'] = self._create_neural_model()

            trained_models = {}
            model_scores = {}

            for name, model in models_to_train.items():
                if name == 'isolation_forest':
                    # Unsupervised model
                    model.fit(X_train)
                    predictions = model.predict(X_test)
                    # Convert to binary classification
                    predictions = (predictions == -1).astype(int)
                else:
                    # Supervised model
                    model.fit(X_train, y_train)
                    predictions = model.predict(X_test)

                accuracy = accuracy_score(y_test, predictions)
                trained_models[name] = model
                model_scores[name] = accuracy

                logger.info(f"{name} accuracy: {accuracy:.3f}")

            self.models = trained_models

            # Create ensemble
            self._create_ensemble_predictor(trained_models, model_scores)

            # Calculate feature importance
            if 'random_forest' in trained_models:
                rf_model = trained_models['random_forest']
                self.feature_importance = dict(zip(feature_names, rf_model.feature_importances_))

            return {
                'models_trained': list(trained_models.keys()),
                'model_scores': model_scores,
                'feature_importance': self.feature_importance
            }

        except Exception as e:
            logger.error(f"Error training ensemble model: {e}")
            raise AIDetectionError(f"Ensemble training failed: {e}")

    def _prepare_advanced_training_data(self, use_advanced_features: bool) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Prepare advanced training data with multiple feature types"""
        conn = self.detector._safe_db_connect()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT s.submission_text, r.ai_score, s.word_count, s.character_count,
               r.style_deviation, r.detailed_results
        FROM ai_detector_submissions s
        JOIN ai_detector_results r ON s.id = r.submission_id
        WHERE length(s.submission_text) > 200
        ''')

        data = cursor.fetchall()
        conn.close()

        if len(data) < 50:
            raise AIDetectionError("Insufficient training data")

        features = []
        labels = []
        feature_names = []

        for row in data:
            text = row['submission_text']
            label = 1 if row['ai_score'] >= 0.7 else 0

            # Basic features
            feature_vector = [
                row['word_count'],
                row['character_count'],
                row['style_deviation'] or 0
            ]

            if not feature_names:  # First iteration
                feature_names.extend(['word_count', 'character_count', 'style_deviation'])

            if use_advanced_features:
                # Advanced linguistic features
                linguistic_features = self._extract_linguistic_features(text)
                feature_vector.extend(linguistic_features.values())

                if not any('linguistic' in name for name in feature_names):
                    feature_names.extend([f'linguistic_{name}' for name in linguistic_features.keys()])

                # TF-IDF features (limited set)
                tfidf_features = self._extract_tfidf_features(text)
                feature_vector.extend(tfidf_features)

                if not any('tfidf' in name for name in feature_names):
                    feature_names.extend([f'tfidf_{i}' for i in range(len(tfidf_features))])

            features.append(feature_vector)
            labels.append(label)

        return np.array(features), np.array(labels), feature_names

    def _extract_linguistic_features(self, text: str) -> Dict[str, float]:
        """Extract advanced linguistic features"""
        features = {}

        # Sentence complexity
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if sentences:
            sentence_lengths = [len(s.split()) for s in sentences]
            features['avg_sentence_length'] = np.mean(sentence_lengths)
            features['sentence_length_std'] = np.std(sentence_lengths)
            features['max_sentence_length'] = np.max(sentence_lengths)
        else:
            features.update({'avg_sentence_length': 0, 'sentence_length_std': 0, 'max_sentence_length': 0})

        # Lexical diversity
        words = text.lower().split()
        unique_words = set(words)
        features['lexical_diversity'] = len(unique_words) / max(1, len(words))

        # Function word ratio
        function_words = {'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i', 'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at'}
        function_word_count = sum(1 for word in words if word in function_words)
        features['function_word_ratio'] = function_word_count / max(1, len(words))

        # Punctuation density
        punctuation_count = len(re.findall(r'[.,;:!?]', text))
        features['punctuation_density'] = punctuation_count / max(1, len(text))

        return features

    def _extract_tfidf_features(self, text: str, max_features: int = 50) -> List[float]:
        """Extract TF-IDF features"""
        try:
            # Simple TF-IDF on character n-grams
            vectorizer = TfidfVectorizer(
                max_features=max_features,
                ngram_range=(2, 4),
                analyzer='char_wb',
                lowercase=True
            )

            # Fit on single text (not ideal, but works for feature extraction)
            tfidf_matrix = vectorizer.fit_transform([text])
            return tfidf_matrix.toarray()[0].tolist()

        except Exception:
            return [0.0] * max_features

    def _create_neural_model(self):
        """Create neural network model using transformers"""
        # Placeholder for transformer-based model
        # In practice, would use BERT, RoBERTa, or similar
        return None

    def _create_ensemble_predictor(self, models: Dict, scores: Dict):
        """Create ensemble predictor from trained models"""
        # Weight models by their performance
        total_score = sum(scores.values())
        weights = {name: score/total_score for name, score in scores.items()}

        self.ensemble_model = {
            'models': models,
            'weights': weights
        }

    def predict_ensemble(self, text: str) -> Dict[str, Any]:
        """Make prediction using ensemble model"""
        if not self.ensemble_model:
            return None

        try:
            # Extract features
            features = self._extract_features_for_prediction(text)

            # Get predictions from each model
            predictions = {}
            weighted_sum = 0
            total_weight = 0

            for name, model in self.ensemble_model['models'].items():
                weight = self.ensemble_model['weights'][name]

                if name == 'isolation_forest':
                    pred = model.predict([features])[0]
                    prob = 1.0 if pred == -1 else 0.0  # Anomaly detection
                else:
                    if hasattr(model, 'predict_proba'):
                        prob = model.predict_proba([features])[0][1]
                    else:
                        prob = float(model.predict([features])[0])

                predictions[name] = prob
                weighted_sum += prob * weight
                total_weight += weight

            ensemble_score = weighted_sum / total_weight if total_weight > 0 else 0

            return {
                'ensemble_score': ensemble_score,
                'individual_predictions': predictions,
                'confidence': self._calculate_ensemble_confidence(predictions)
            }

        except Exception as e:
            logger.error(f"Error in ensemble prediction: {e}")
            return None

    def _extract_features_for_prediction(self, text: str) -> List[float]:
        """Extract features for prediction"""
        # This should match the feature extraction used in training
        word_count = len(text.split())
        char_count = len(text)

        features = [word_count, char_count, 0]  # style_deviation placeholder

        # Add linguistic features
        linguistic_features = self._extract_linguistic_features(text)
        features.extend(linguistic_features.values())

        # Add TF-IDF features
        tfidf_features = self._extract_tfidf_features(text)
        features.extend(tfidf_features)

        return features

    def _calculate_ensemble_confidence(self, predictions: Dict[str, float]) -> float:
        """Calculate confidence in ensemble prediction"""
        pred_values = list(predictions.values())

        if len(pred_values) < 2:
            return 0.5

        # Confidence based on agreement between models
        variance = np.var(pred_values)
        confidence = max(0.1, 1.0 - variance)

        return confidence
