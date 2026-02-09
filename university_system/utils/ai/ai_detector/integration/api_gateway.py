"""Gateway for external AI detection APIs."""

from datetime import datetime
from typing import Dict, Optional, Any

from university_system.utils.ai.ai_detector.core.constants import logger, REQUESTS_AVAILABLE

# Import requests conditionally
try:
    import requests
except ImportError:
    pass


class APIGateway:
    """Gateway for external AI detection APIs"""

    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.api_configs = {}
        self.rate_limits = {}
        self.circuit_breakers = {}

    def register_api(self, name: str, config: Dict[str, Any]):
        """Register an external AI detection API"""
        self.api_configs[name] = {
            'url': config['url'],
            'api_key': config['api_key'],
            'timeout': config.get('timeout', 10),
            'max_requests_per_minute': config.get('max_requests_per_minute', 60),
            'weight': config.get('weight', 1.0)
        }

        self.rate_limits[name] = {
            'requests': [],
            'max_per_minute': config.get('max_requests_per_minute', 60)
        }

        self.circuit_breakers[name] = {
            'failures': 0,
            'last_failure': None,
            'is_open': False,
            'failure_threshold': 5,
            'recovery_timeout': 300  # 5 minutes
        }

    def call_api(self, api_name: str, text: str) -> Optional[Dict[str, Any]]:
        """Call external API with circuit breaker and rate limiting"""
        if not REQUESTS_AVAILABLE:
            return None

        if api_name not in self.api_configs:
            logger.error(f"API {api_name} not registered")
            return None

        # Check circuit breaker
        if self._is_circuit_open(api_name):
            logger.warning(f"Circuit breaker open for API {api_name}")
            return None

        # Check rate limit
        if not self._check_rate_limit(api_name):
            logger.warning(f"Rate limit exceeded for API {api_name}")
            return None

        try:
            config = self.api_configs[api_name]

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {config["api_key"]}'
            }

            data = {
                'text': text[:5000],  # Limit text length
                'model': 'general'
            }

            response = requests.post(
                config['url'],
                headers=headers,
                json=data,
                timeout=config['timeout']
            )

            if response.status_code == 200:
                result = response.json()
                self._record_success(api_name)
                return {
                    'api_name': api_name,
                    'score': result.get('score', 0),
                    'confidence': result.get('confidence', 0),
                    'details': result.get('details', {}),
                    'response_time': response.elapsed.total_seconds()
                }
            else:
                self._record_failure(api_name)
                logger.warning(f"API {api_name} returned status {response.status_code}")
                return None

        except Exception as e:
            self._record_failure(api_name)
            logger.error(f"Error calling API {api_name}: {e}")
            return None

    def _check_rate_limit(self, api_name: str) -> bool:
        """Check if API call is within rate limit"""
        now = datetime.now()
        rate_limit = self.rate_limits[api_name]

        # Remove requests older than 1 minute
        rate_limit['requests'] = [
            req_time for req_time in rate_limit['requests']
            if (now - req_time).total_seconds() < 60
        ]

        # Check if under limit
        if len(rate_limit['requests']) < rate_limit['max_per_minute']:
            rate_limit['requests'].append(now)
            return True

        return False

    def _is_circuit_open(self, api_name: str) -> bool:
        """Check if circuit breaker is open"""
        circuit = self.circuit_breakers[api_name]

        if not circuit['is_open']:
            return False

        # Check if recovery timeout has passed
        if circuit['last_failure']:
            time_since_failure = (datetime.now() - circuit['last_failure']).total_seconds()
            if time_since_failure > circuit['recovery_timeout']:
                circuit['is_open'] = False
                circuit['failures'] = 0
                return False

        return True

    def _record_success(self, api_name: str):
        """Record successful API call"""
        circuit = self.circuit_breakers[api_name]
        circuit['failures'] = 0
        circuit['is_open'] = False

    def _record_failure(self, api_name: str):
        """Record failed API call"""
        circuit = self.circuit_breakers[api_name]
        circuit['failures'] += 1
        circuit['last_failure'] = datetime.now()

        if circuit['failures'] >= circuit['failure_threshold']:
            circuit['is_open'] = True
            logger.warning(f"Circuit breaker opened for API {api_name}")
