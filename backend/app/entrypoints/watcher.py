from __future__ import annotations

from backend.app.runtime.bootstrap import bootstrap_service_paths, configure_logging


def main() -> None:
    bootstrap_service_paths()
    configure_logging()

    from backend.app.watcher.watcher import start_watching

    start_watching()


if __name__ == "__main__":
    main()
