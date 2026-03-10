"""
Autocomplete and suggestion service
"""

import logging
from typing import List, Dict, Any, Optional
from collections import Counter

from education_system.university_system.infrastructure.search.search_service import get_search_service
from education_system.university_system.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


class AutocompleteService:
    """
    Autocomplete and suggestion service

    Provides:
    - Field-based autocomplete
    - Recent searches
    - Popular searches
    - Did-you-mean suggestions
    """

    def __init__(self):
        """Initialize autocomplete service"""
        self.search_service = get_search_service()
        self._create_tables()

    def _create_tables(self):
        """Create tables for tracking searches"""
        from education_system.university_system.infrastructure.database.db import transaction

        with transaction() as conn:
            # Recent searches
            conn.execute('''
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    query TEXT NOT NULL,
                    entity_type TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    results_count INTEGER
                )
            ''')

            # Popular searches
            conn.execute('''
                CREATE TABLE IF NOT EXISTS popular_searches (
                    query TEXT PRIMARY KEY,
                    entity_type TEXT,
                    search_count INTEGER DEFAULT 1,
                    last_searched TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_search_history_user
                ON search_history(user_id, timestamp DESC)
            ''')

    def autocomplete(
        self,
        entity_type: str,
        field: str,
        prefix: str,
        size: int = 10
    ) -> List[str]:
        """
        Get autocomplete suggestions for a field

        Args:
            entity_type: Entity type (students, courses, etc.)
            field: Field to autocomplete (name, email, etc.)
            prefix: Text prefix to match
            size: Number of suggestions

        Returns:
            List of suggestions
        """
        return self.search_service.autocomplete(entity_type, field, prefix, size)

    def get_recent_searches(
        self,
        user_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent searches

        Args:
            user_id: User ID (None for all users)
            limit: Number of recent searches

        Returns:
            List of recent search queries
        """
        try:
            with get_connection() as conn:
                if user_id:
                    cursor = conn.execute('''
                        SELECT DISTINCT query, entity_type, timestamp
                        FROM search_history
                        WHERE user_id = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    ''', (user_id, limit))
                else:
                    cursor = conn.execute('''
                        SELECT DISTINCT query, entity_type, timestamp
                        FROM search_history
                        ORDER BY timestamp DESC
                        LIMIT ?
                    ''', (limit,))

                results = []
                for row in cursor.fetchall():
                    results.append({
                        'query': row[0],
                        'entity_type': row[1],
                        'timestamp': row[2]
                    })

                return results

        except Exception as e:
            logger.error(f"Error getting recent searches: {e}")
            return []

    def get_popular_searches(
        self,
        entity_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get popular searches

        Args:
            entity_type: Entity type filter (None for all)
            limit: Number of popular searches

        Returns:
            List of popular queries with counts
        """
        try:
            with get_connection() as conn:
                if entity_type:
                    cursor = conn.execute('''
                        SELECT query, entity_type, search_count
                        FROM popular_searches
                        WHERE entity_type = ?
                        ORDER BY search_count DESC, last_searched DESC
                        LIMIT ?
                    ''', (entity_type, limit))
                else:
                    cursor = conn.execute('''
                        SELECT query, entity_type, search_count
                        FROM popular_searches
                        ORDER BY search_count DESC, last_searched DESC
                        LIMIT ?
                    ''', (limit,))

                results = []
                for row in cursor.fetchall():
                    results.append({
                        'query': row[0],
                        'entity_type': row[1],
                        'count': row[2]
                    })

                return results

        except Exception as e:
            logger.error(f"Error getting popular searches: {e}")
            return []

    def record_search(
        self,
        query: str,
        entity_type: str,
        user_id: Optional[str] = None,
        results_count: int = 0
    ) -> None:
        """
        Record a search for tracking

        Args:
            query: Search query
            entity_type: Entity type
            user_id: User ID (optional)
            results_count: Number of results returned
        """
        try:
            from education_system.university_system.infrastructure.database.db import transaction

            with transaction() as conn:
                # Add to search history
                conn.execute('''
                    INSERT INTO search_history (user_id, query, entity_type, results_count)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, query, entity_type, results_count))

                # Update popular searches
                conn.execute('''
                    INSERT INTO popular_searches (query, entity_type, search_count, last_searched)
                    VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT(query) DO UPDATE SET
                        search_count = search_count + 1,
                        last_searched = CURRENT_TIMESTAMP
                ''', (query, entity_type))

        except Exception as e:
            logger.error(f"Error recording search: {e}")

    def suggest_queries(
        self,
        prefix: str,
        entity_type: Optional[str] = None,
        limit: int = 5
    ) -> List[str]:
        """
        Suggest queries based on prefix and popular searches

        Args:
            prefix: Query prefix
            entity_type: Entity type filter
            limit: Number of suggestions

        Returns:
            List of suggested queries
        """
        try:
            with get_connection() as conn:
                if entity_type:
                    cursor = conn.execute('''
                        SELECT query FROM popular_searches
                        WHERE query LIKE ? AND entity_type = ?
                        ORDER BY search_count DESC
                        LIMIT ?
                    ''', (f'{prefix}%', entity_type, limit))
                else:
                    cursor = conn.execute('''
                        SELECT query FROM popular_searches
                        WHERE query LIKE ?
                        ORDER BY search_count DESC
                        LIMIT ?
                    ''', (f'{prefix}%', limit))

                return [row[0] for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error suggesting queries: {e}")
            return []

    def did_you_mean(self, query: str, entity_type: str) -> Optional[str]:
        """
        Suggest corrected query (simple implementation)

        Args:
            query: Original query
            entity_type: Entity type

        Returns:
            Suggested correction or None
        """
        # Get popular searches
        popular = self.get_popular_searches(entity_type, limit=100)

        # Simple Levenshtein distance check
        best_match = None
        best_distance = float('inf')

        for item in popular:
            distance = self._levenshtein_distance(query.lower(), item['query'].lower())
            # If very close (1-2 character difference), suggest it
            if distance < best_distance and 1 <= distance <= 2:
                best_distance = distance
                best_match = item['query']

        return best_match

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings"""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # Cost of insertions, deletions, or substitutions
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]


# Singleton instance
_autocomplete_service: Optional[AutocompleteService] = None


def get_autocomplete_service() -> AutocompleteService:
    """Get the global autocomplete service instance"""
    global _autocomplete_service
    if _autocomplete_service is None:
        _autocomplete_service = AutocompleteService()
    return _autocomplete_service
