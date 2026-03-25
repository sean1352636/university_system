"""API server package for University Management System."""

from education_system.shared.api.university.api_server import create_app, run_api_server

__all__ = ["create_app", "run_api_server"]
