"""Shared API module for all education system Flask apps.

Structure:
    shared/api/
    ├── async_adapter.py    # Async Flask wrapper
    ├── health.py           # Health check blueprint
    ├── jwt_utils.py        # JWT token management
    ├── middleware.py        # Request ID, timing, logging
    ├── rate_limiter.py     # Per-IP rate limiting
    ├── college/            # Sixth Form College API
    ├── secondary/          # Secondary School API
    ├── primary/            # Primary School API
    └── university/         # University API
"""
