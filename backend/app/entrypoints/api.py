from __future__ import annotations

import logging
import os

import uvicorn

from backend.app.runtime.bootstrap import bootstrap_service_paths, configure_logging


logger = logging.getLogger("backend.entrypoints.api")


def main() -> None:
    bootstrap_service_paths()
    configure_logging()

    from backend.app.persistence.database import init_db
    from backend.app.api.app import app as api_app

    logger.info("Starting Video Transcriber API")
    os.makedirs("data/videos", exist_ok=True)

    logger.info("Initializing database...")
    init_db()

    logger.info("Starting API server...")
    uvicorn.run(api_app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
