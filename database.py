"""
Database connection and session management for Vectra
Uses SQLAlchemy with synchronous engine for PythonAnywhere compatibility
Updated for Python 3.13 compatibility
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm import declarative_base
import logging

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine with connection pooling
engine = create_engine(
    'sqlite:///vectra.db',
    echo=False,  # Set to True for SQL query logging in development
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before using them
    connect_args={'check_same_thread': False}  # Required for SQLite with multiple threads
)

# Create scoped session factory
SessionLocal = scoped_session(
    sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
)

# Create declarative base
Base = declarative_base()

def get_db():
    """
    Get database session for dependency injection
    Yields a session and ensures proper cleanup
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {str(e)}")
        raise
    finally:
        db.close()

def init_db():
    """Initialize database and create tables"""
    try:
        # Import models here to avoid circular imports
        import sys
        from models import Transaction  # This will register the model with Base
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
        print("✓ Database tables created")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise