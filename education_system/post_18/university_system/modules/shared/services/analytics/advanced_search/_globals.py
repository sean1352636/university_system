"""Shared global state for the advanced_search package."""
from typing import List, Optional

# Global variables
last_search_results = []
search_cache = {}
search_history = []
saved_searches = {}
current_user = "system"  # Should be set by authentication system
SEARCH_ANALYTICS_COLUMNS_CACHE: Optional[List[str]] = None
