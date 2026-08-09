from education_system.systems.university.infrastructure.database.db import get_connection

class HealthRepository:
    def connection(self):
        return get_connection()
