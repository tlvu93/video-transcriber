"""
This module provides database access functions for the video transcriber application.
Database-related functionality has been moved to the API service.
This module re-exports the database functions from the API service.
"""

import sys
from pathlib import Path

# Add the API service to the Python path
api_path = str(Path(__file__).parent.parent.parent / "api-service")
if api_path not in sys.path:
    sys.path.insert(0, api_path)

# Re-export database functions from the API service
from api.database import engine, SessionLocal, Base, init_db, get_db, migrate_from_json_to_db
