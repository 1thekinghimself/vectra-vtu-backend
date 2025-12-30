"""
Database connection for Render.com (PostgreSQL) with SQLite fallback
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm import declarative_base
import logging

logger = logging.getLogger(__name__)

# Check if we're on Render (PostgreSQL) or local (SQLite)
if os.environ.get('RENDER'):
    # Render PostgreSQL database
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    print(f"🔧 Using PostgreSQL on Render: {DATABASE_URL[:50]}...")
else:
    # Local SQLite database
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE_URL = f'sqlite:///{os.path.join(BASE_DIR, "vectra.db")}'
    print(f"🔧 Using SQLite locally: {DATABASE_URL}")

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    connect_args={'check_same_thread': False} if 'sqlite' in DATABASE_URL else {}
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
    """Get database session"""
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
    from models import Transaction
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully")
    print("✅ Database tables created")