from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

SQLALCHEMY_DATABASE_URL = "sqlite:///./db.sqlite"
# SQLALCHEMY_DATABASE_URL = "postgresql://user:password@postgresserver/db"

# SECURITY NOTE: For SQLite with multi-threaded access (like FastAPI),
# use StaticPool with check_same_thread=False. StaticPool ensures all
# threads share the same connection, which is safe when combined with
# SQLAlchemy's session scoping. This is the recommended approach for
# FastAPI + SQLite. For production, consider PostgreSQL or MySQL instead.
#
# Alternative for stricter thread safety (each request gets fresh connection):
# from sqlalchemy.pool import NullPool
# engine = create_engine(SQLALCHEMY_DATABASE_URL, poolclass=NullPool)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # Ensures single connection shared safely
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()