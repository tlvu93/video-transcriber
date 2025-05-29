import logging
import os
import sys
from pathlib import Path

import uvicorn

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.database import init_db
from api.routes.api import app as api_app

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("main")


def main():
    """Main entry point."""
    try:
        logger.info("Starting Video Transcriber API")

        # Create necessary directories
        os.makedirs("data/videos", exist_ok=True)

        # Initialize database
        logger.info("Initializing database...")
        init_db()

        # Start API server
        logger.info("Starting API server...")
        uvicorn.run(api_app, host="0.0.0.0", port=8000)

    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")
        raise


if __name__ == "__main__":
    main()
