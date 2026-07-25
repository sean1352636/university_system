"""
Search analytics and tracking
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


class SearchAnalytics:
    """
    Search analytics and performance tracking

    Tracks:
    - Search queries and results
    - Click-through rates
    - Popular searches
    - Zero-result searches
    - Search performance metrics
    """

    def __init__(self):
        """Initialize search analytics"""
        self._create_tables()

    def _create_tables(self):
        """Create analytics tables"""
        from education_system.systems.university.infrastructure.database.db import transaction

        with transaction() as conn:
            # Search metrics
            conn.execute('''
                CREATE TABLE IF NOT EXISTS search_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    entity_type TEXT,
                    user_id TEXT,
                    results_count INTEGER,
                    response_time_ms INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Click tracking
            conn.execute('''
                CREATE TABLE IF NOT EXISTS search_clicks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    entity_type TEXT,
                    clicked_id TEXT NOT NULL,
                    click_position INTEGER,
                    user_id TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_search_metrics_timestamp
                ON search_metrics(timestamp DESC)
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_search_clicks_query
                ON search_clicks(query, timestamp DESC)
            ''')

    def track_search(
        self,
        query: str,
        entity_type: str,
        results_count: int,
        response_time_ms: int,
        user_id: Optional[str] = None
    ) -> None:
        """
        Track a search query

        Args:
            query: Search query
            entity_type: Entity type searched
            results_count: Number of results returned
            response_time_ms: Response time in milliseconds
            user_id: User ID (optional)
        """
        try:
            from education_system.systems.university.infrastructure.database.db import transaction

            with transaction() as conn:
                conn.execute('''
                    INSERT INTO search_metrics (
                        query, entity_type, user_id, results_count, response_time_ms
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (query, entity_type, user_id, results_count, response_time_ms))

        except Exception as e:
            logger.error(f"Error tracking search: {e}")

    def track_click(
        self,
        query: str,
        entity_type: str,
        clicked_id: str,
        position: int,
        user_id: Optional[str] = None
    ) -> None:
        """
        Track a search result click

        Args:
            query: Original search query
            entity_type: Entity type
            clicked_id: ID of clicked result
            position: Position in search results (1-indexed)
            user_id: User ID (optional)
        """
        try:
            from education_system.systems.university.infrastructure.database.db import transaction

            with transaction() as conn:
                conn.execute('''
                    INSERT INTO search_clicks (
                        query, entity_type, clicked_id, click_position, user_id
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (query, entity_type, clicked_id, position, user_id))

        except Exception as e:
            logger.error(f"Error tracking click: {e}")

    def get_zero_result_searches(self, days: int = 7, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get searches that returned no results

        Args:
            days: Number of days to look back
            limit: Maximum number of results

        Returns:
            List of zero-result queries with counts
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT query, entity_type, COUNT(*) as count
                    FROM search_metrics
                    WHERE results_count = 0
                      AND timestamp >= ?
                    GROUP BY query, entity_type
                    ORDER BY count DESC
                    LIMIT ?
                ''', (start_date, limit))

                results = []
                for row in cursor.fetchall():
                    results.append({
                        'query': row[0],
                        'entity_type': row[1],
                        'count': row[2]
                    })

                return results

        except Exception as e:
            logger.error(f"Error getting zero-result searches: {e}")
            return []

    def get_click_through_rate(
        self,
        query: Optional[str] = None,
        days: int = 7
    ) -> float:
        """
        Calculate click-through rate

        Args:
            query: Specific query (None for overall CTR)
            days: Number of days to analyze

        Returns:
            Click-through rate as percentage
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            with get_connection() as conn:
                # Count searches
                if query:
                    cursor = conn.execute('''
                        SELECT COUNT(*) FROM search_metrics
                        WHERE query = ? AND timestamp >= ?
                    ''', (query, start_date))
                else:
                    cursor = conn.execute('''
                        SELECT COUNT(*) FROM search_metrics
                        WHERE timestamp >= ?
                    ''', (start_date,))

                total_searches = cursor.fetchone()[0]

                if total_searches == 0:
                    return 0.0

                # Count clicks
                if query:
                    cursor = conn.execute('''
                        SELECT COUNT(DISTINCT user_id || timestamp) FROM search_clicks
                        WHERE query = ? AND timestamp >= ?
                    ''', (query, start_date))
                else:
                    cursor = conn.execute('''
                        SELECT COUNT(DISTINCT user_id || timestamp) FROM search_clicks
                        WHERE timestamp >= ?
                    ''', (start_date,))

                total_clicks = cursor.fetchone()[0]

                return (total_clicks / total_searches) * 100

        except Exception as e:
            logger.error(f"Error calculating CTR: {e}")
            return 0.0

    def get_average_response_time(self, days: int = 7) -> float:
        """
        Get average search response time

        Args:
            days: Number of days to analyze

        Returns:
            Average response time in milliseconds
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT AVG(response_time_ms)
                    FROM search_metrics
                    WHERE timestamp >= ?
                ''', (start_date,))

                result = cursor.fetchone()[0]
                return result if result else 0.0

        except Exception as e:
            logger.error(f"Error calculating average response time: {e}")
            return 0.0

    def get_search_volume(self, days: int = 30) -> Dict[str, int]:
        """
        Get search volume over time

        Args:
            days: Number of days to analyze

        Returns:
            Dict mapping dates to search counts
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT DATE(timestamp) as date, COUNT(*) as count
                    FROM search_metrics
                    WHERE timestamp >= ?
                    GROUP BY DATE(timestamp)
                    ORDER BY date
                ''', (start_date,))

                volume = {}
                for row in cursor.fetchall():
                    volume[row[0]] = row[1]

                return volume

        except Exception as e:
            logger.error(f"Error getting search volume: {e}")
            return {}

    def get_top_queries(
        self,
        entity_type: Optional[str] = None,
        days: int = 7,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get top search queries

        Args:
            entity_type: Entity type filter
            days: Number of days to analyze
            limit: Number of results

        Returns:
            List of top queries with counts
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            with get_connection() as conn:
                if entity_type:
                    cursor = conn.execute('''
                        SELECT query, entity_type, COUNT(*) as count,
                               AVG(results_count) as avg_results
                        FROM search_metrics
                        WHERE entity_type = ? AND timestamp >= ?
                        GROUP BY query, entity_type
                        ORDER BY count DESC
                        LIMIT ?
                    ''', (entity_type, start_date, limit))
                else:
                    cursor = conn.execute('''
                        SELECT query, entity_type, COUNT(*) as count,
                               AVG(results_count) as avg_results
                        FROM search_metrics
                        WHERE timestamp >= ?
                        GROUP BY query, entity_type
                        ORDER BY count DESC
                        LIMIT ?
                    ''', (start_date, limit))

                results = []
                for row in cursor.fetchall():
                    results.append({
                        'query': row[0],
                        'entity_type': row[1],
                        'count': row[2],
                        'avg_results': row[3]
                    })

                return results

        except Exception as e:
            logger.error(f"Error getting top queries: {e}")
            return []

    def get_analytics_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get comprehensive analytics summary

        Args:
            days: Number of days to analyze

        Returns:
            Analytics summary with key metrics
        """
        return {
            'total_searches': self._count_searches(days),
            'zero_result_searches': len(self.get_zero_result_searches(days)),
            'click_through_rate': self.get_click_through_rate(days=days),
            'average_response_time_ms': self.get_average_response_time(days),
            'top_queries': self.get_top_queries(days=days, limit=5),
            'search_volume': self.get_search_volume(days),
            'period_days': days
        }

    def _count_searches(self, days: int) -> int:
        """Count total searches in period"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM search_metrics
                    WHERE timestamp >= ?
                ''', (start_date,))

                return cursor.fetchone()[0]

        except Exception as e:
            logger.error(f"Error counting searches: {e}")
            return 0


# Singleton instance
_search_analytics: Optional[SearchAnalytics] = None


def get_search_analytics() -> SearchAnalytics:
    """Get the global search analytics instance"""
    global _search_analytics
    if _search_analytics is None:
        _search_analytics = SearchAnalytics()
    return _search_analytics
