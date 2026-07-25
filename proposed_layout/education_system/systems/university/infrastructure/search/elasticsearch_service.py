"""
Elasticsearch integration for advanced search

Provides full-text search, faceted search, autocomplete, and analytics
using Elasticsearch as the backend.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import Elasticsearch
try:
    from elasticsearch import Elasticsearch
    from elasticsearch.exceptions import ConnectionError, NotFoundError
    ELASTICSEARCH_AVAILABLE = True
except ImportError:
    ELASTICSEARCH_AVAILABLE = False
    logger.warning("Elasticsearch not available. Install with: pip install elasticsearch")


class ElasticsearchService:
    """
    Elasticsearch integration for advanced search

    Features:
    - Full-text search with relevance scoring
    - Fuzzy matching for typo tolerance
    - Faceted search (filters)
    - Autocomplete suggestions
    - Real-time indexing
    - Search analytics
    """

    def __init__(self, hosts: List[str] = None, **kwargs):
        """
        Initialize Elasticsearch service

        Args:
            hosts: List of Elasticsearch hosts (default: ['localhost:9200'])
            **kwargs: Additional Elasticsearch client configuration
        """
        if not ELASTICSEARCH_AVAILABLE:
            raise ImportError("Elasticsearch package not installed")

        self.hosts = hosts or ['localhost:9200']
        self.es = None
        self.connected = False

        try:
            self.es = Elasticsearch(self.hosts, **kwargs)
            # Test connection
            self.es.info()
            self.connected = True
            logger.info(f"Connected to Elasticsearch at {self.hosts}")

            # Create indices if they don't exist
            self._create_indices()

        except Exception as e:
            logger.error(f"Failed to connect to Elasticsearch: {e}")
            self.connected = False

    def _create_indices(self):
        """Create search indices for all entity types"""
        indices = {
            'students': {
                'mappings': {
                    'properties': {
                        'student_id': {'type': 'keyword'},
                        'name': {'type': 'text', 'analyzer': 'standard'},
                        'first_name': {'type': 'text'},
                        'last_name': {'type': 'text'},
                        'email': {'type': 'keyword'},
                        'major': {'type': 'keyword'},
                        'course': {'type': 'keyword'},
                        'gpa': {'type': 'float'},
                        'enrollment_date': {'type': 'date'},
                        'status': {'type': 'keyword'},
                        'graduation_year': {'type': 'integer'},
                        'created_at': {'type': 'date'},
                    }
                }
            },
            'courses': {
                'mappings': {
                    'properties': {
                        'course_id': {'type': 'keyword'},
                        'code': {'type': 'keyword'},
                        'name': {'type': 'text', 'analyzer': 'standard'},
                        'description': {'type': 'text'},
                        'department': {'type': 'keyword'},
                        'instructor': {'type': 'text'},
                        'instructor_id': {'type': 'keyword'},
                        'credits': {'type': 'integer'},
                        'capacity': {'type': 'integer'},
                        'enrolled': {'type': 'integer'},
                        'semester': {'type': 'keyword'},
                        'year': {'type': 'integer'},
                        'created_at': {'type': 'date'},
                    }
                }
            },
            'staff': {
                'mappings': {
                    'properties': {
                        'staff_id': {'type': 'keyword'},
                        'name': {'type': 'text', 'analyzer': 'standard'},
                        'email': {'type': 'keyword'},
                        'department': {'type': 'keyword'},
                        'position': {'type': 'keyword'},
                        'hire_date': {'type': 'date'},
                        'phone': {'type': 'keyword'},
                        'created_at': {'type': 'date'},
                    }
                }
            },
            'research': {
                'mappings': {
                    'properties': {
                        'research_id': {'type': 'keyword'},
                        'title': {'type': 'text', 'analyzer': 'standard'},
                        'abstract': {'type': 'text'},
                        'authors': {'type': 'text'},
                        'department': {'type': 'keyword'},
                        'status': {'type': 'keyword'},
                        'funding': {'type': 'float'},
                        'start_date': {'type': 'date'},
                        'end_date': {'type': 'date'},
                        'keywords': {'type': 'keyword'},
                        'created_at': {'type': 'date'},
                    }
                }
            },
            'events': {
                'mappings': {
                    'properties': {
                        'event_id': {'type': 'keyword'},
                        'title': {'type': 'text', 'analyzer': 'standard'},
                        'description': {'type': 'text'},
                        'location': {'type': 'text'},
                        'category': {'type': 'keyword'},
                        'organizer': {'type': 'text'},
                        'start_date': {'type': 'date'},
                        'end_date': {'type': 'date'},
                        'capacity': {'type': 'integer'},
                        'registered': {'type': 'integer'},
                        'created_at': {'type': 'date'},
                    }
                }
            }
        }

        for index_name, index_body in indices.items():
            try:
                if not self.es.indices.exists(index=index_name):
                    self.es.indices.create(index=index_name, body=index_body)
                    logger.info(f"Created index: {index_name}")
            except Exception as e:
                logger.error(f"Error creating index {index_name}: {e}")

    def index_document(
        self,
        index: str,
        doc_id: str,
        document: Dict[str, Any]
    ) -> bool:
        """
        Index a document

        Args:
            index: Index name (students, courses, etc.)
            doc_id: Document ID
            document: Document data

        Returns:
            True if successful, False otherwise
        """
        if not self.connected:
            return False

        try:
            # Add timestamp
            document['indexed_at'] = datetime.utcnow().isoformat()

            self.es.index(index=index, id=doc_id, body=document)
            return True
        except Exception as e:
            logger.error(f"Error indexing document {doc_id} in {index}: {e}")
            return False

    def bulk_index(
        self,
        index: str,
        documents: List[Dict[str, Any]],
        id_field: str = 'id'
    ) -> Dict[str, int]:
        """
        Bulk index multiple documents

        Args:
            index: Index name
            documents: List of documents
            id_field: Field to use as document ID

        Returns:
            Dict with success and error counts
        """
        if not self.connected:
            return {'success': 0, 'errors': len(documents)}

        from elasticsearch.helpers import bulk

        actions = []
        for doc in documents:
            doc_id = doc.get(id_field)
            if not doc_id:
                continue

            action = {
                '_index': index,
                '_id': doc_id,
                '_source': {**doc, 'indexed_at': datetime.utcnow().isoformat()}
            }
            actions.append(action)

        try:
            success, errors = bulk(self.es, actions)
            return {'success': success, 'errors': len(errors) if errors else 0}
        except Exception as e:
            logger.error(f"Error bulk indexing: {e}")
            return {'success': 0, 'errors': len(actions)}

    def search(
        self,
        index: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        size: int = 10,
        from_: int = 0,
        sort: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Search documents with full-text search and filters

        Args:
            index: Index name
            query: Search query string
            filters: Filter criteria (field: value pairs)
            size: Number of results to return
            from_: Offset for pagination
            sort: Sort criteria

        Returns:
            Search results with hits, total count, and aggregations
        """
        if not self.connected:
            return {'hits': {'hits': [], 'total': {'value': 0}}}

        # Build search body
        search_body = {
            'size': size,
            'from': from_,
            'query': {
                'bool': {
                    'must': [],
                    'filter': []
                }
            }
        }

        # Add text query if provided
        if query:
            search_body['query']['bool']['must'].append({
                'multi_match': {
                    'query': query,
                    'fields': ['*'],
                    'fuzziness': 'AUTO',  # Typo tolerance
                    'operator': 'or'
                }
            })
        else:
            # Match all if no query
            search_body['query']['bool']['must'].append({'match_all': {}})

        # Add filters
        if filters:
            for field, value in filters.items():
                if isinstance(value, list):
                    # Terms filter for multiple values
                    search_body['query']['bool']['filter'].append({
                        'terms': {field: value}
                    })
                elif isinstance(value, dict):
                    # Range filter
                    search_body['query']['bool']['filter'].append({
                        'range': {field: value}
                    })
                else:
                    # Term filter for single value
                    search_body['query']['bool']['filter'].append({
                        'term': {field: value}
                    })

        # Add sorting
        if sort:
            search_body['sort'] = sort

        # Add highlight
        search_body['highlight'] = {
            'fields': {
                '*': {}
            }
        }

        try:
            return self.es.search(index=index, body=search_body)
        except Exception as e:
            logger.error(f"Error searching {index}: {e}")
            return {'hits': {'hits': [], 'total': {'value': 0}}}

    def autocomplete(
        self,
        index: str,
        field: str,
        prefix: str,
        size: int = 10
    ) -> List[str]:
        """
        Get autocomplete suggestions

        Args:
            index: Index name
            field: Field to autocomplete
            prefix: Text prefix to match
            size: Number of suggestions

        Returns:
            List of suggestions
        """
        if not self.connected:
            return []

        search_body = {
            'size': 0,
            'aggs': {
                'autocomplete': {
                    'terms': {
                        'field': f'{field}.keyword' if not field.endswith('.keyword') else field,
                        'size': size,
                        'include': f'{prefix}.*'
                    }
                }
            }
        }

        try:
            result = self.es.search(index=index, body=search_body)
            buckets = result.get('aggregations', {}).get('autocomplete', {}).get('buckets', [])
            return [bucket['key'] for bucket in buckets]
        except Exception as e:
            logger.error(f"Error getting autocomplete suggestions: {e}")
            return []

    def faceted_search(
        self,
        index: str,
        query: str,
        facets: List[str],
        filters: Optional[Dict[str, Any]] = None,
        size: int = 10
    ) -> Dict[str, Any]:
        """
        Perform faceted search with aggregations

        Args:
            index: Index name
            query: Search query
            facets: Fields to aggregate
            filters: Filter criteria
            size: Number of results

        Returns:
            Search results with facet aggregations
        """
        if not self.connected:
            return {'hits': {'hits': [], 'total': {'value': 0}}, 'aggregations': {}}

        # Build base search
        result = self.search(index, query, filters, size)

        # Add aggregations
        aggs = {}
        for facet in facets:
            aggs[f'{facet}_facet'] = {
                'terms': {
                    'field': f'{facet}.keyword' if not facet.endswith('.keyword') else facet,
                    'size': 50
                }
            }

        search_body = {
            'size': size,
            'query': result.get('query', {'match_all': {}}),
            'aggs': aggs
        }

        try:
            return self.es.search(index=index, body=search_body)
        except Exception as e:
            logger.error(f"Error in faceted search: {e}")
            return result

    def delete_document(self, index: str, doc_id: str) -> bool:
        """Delete a document from the index"""
        if not self.connected:
            return False

        try:
            self.es.delete(index=index, id=doc_id)
            return True
        except NotFoundError:
            logger.warning(f"Document {doc_id} not found in {index}")
            return False
        except Exception as e:
            logger.error(f"Error deleting document {doc_id} from {index}: {e}")
            return False

    def update_document(
        self,
        index: str,
        doc_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update a document in the index"""
        if not self.connected:
            return False

        try:
            self.es.update(
                index=index,
                id=doc_id,
                body={'doc': updates}
            )
            return True
        except Exception as e:
            logger.error(f"Error updating document {doc_id} in {index}: {e}")
            return False

    def count(self, index: str, query: Optional[str] = None) -> int:
        """Count documents matching query"""
        if not self.connected:
            return 0

        body = {}
        if query:
            body['query'] = {
                'multi_match': {
                    'query': query,
                    'fields': ['*']
                }
            }

        try:
            result = self.es.count(index=index, body=body)
            return result.get('count', 0)
        except Exception as e:
            logger.error(f"Error counting documents in {index}: {e}")
            return 0


def get_elasticsearch_service(hosts: List[str] = None) -> Optional[ElasticsearchService]:
    """
    Get Elasticsearch service instance

    Args:
        hosts: List of Elasticsearch hosts

    Returns:
        ElasticsearchService instance or None if unavailable
    """
    if not ELASTICSEARCH_AVAILABLE:
        return None

    try:
        return ElasticsearchService(hosts)
    except Exception as e:
        logger.error(f"Failed to create Elasticsearch service: {e}")
        return None
