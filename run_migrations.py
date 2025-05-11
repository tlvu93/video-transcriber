#!/usr/bin/env python3
"""
Script to run database migrations using Alembic.
"""
import os
import sys
import logging
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('migrations')

def run_migrations():
    """Run database migrations using Alembic."""
    try:
        logger.info("Running database migrations...")
        
        # Check if alembic is installed
        try:
            subprocess.run(["alembic", "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("Alembic is not installed. Please install it with 'pip install alembic'.")
            return False
        
        # Run migrations
        result = subprocess.run(["alembic", "upgrade", "head"], check=False)
        
        if result.returncode == 0:
            logger.info("Migrations completed successfully.")
            return True
        else:
            logger.error(f"Migration failed with return code {result.returncode}")
            return False
            
    except Exception as e:
        logger.error(f"Error running migrations: {str(e)}")
        return False

if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)
