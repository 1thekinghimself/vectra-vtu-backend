#!/usr/bin/env python3
"""
Test script to verify Vectra setup
"""
import sys
print(f"Python version: {sys.version}")

try:
    import sqlalchemy
    print(f"✓ SQLAlchemy: {sqlalchemy.__version__}")
except ImportError as e:
    print(f"✗ SQLAlchemy import failed: {e}")

try:
    import flask
    print(f"✓ Flask: {flask.__version__}")
except ImportError as e:
    print(f"✗ Flask import failed: {e}")

try:
    from database import init_db, Base
    from models import Transaction
    print("✓ Database modules imported")
    
    # Test database initialization
    from sqlalchemy import create_engine
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    print("✓ Database schema created")
    
except Exception as e:
    print(f"✗ Database setup failed: {e}")
    import traceback
    traceback.print_exc()

print("\n✓ All tests completed")