from __future__ import annotations

from backend.app.runtime.bootstrap import bootstrap_service_paths, configure_logging


def main() -> None:
    bootstrap_service_paths()
    configure_logging()

    from backend.app.transcription.runner import main as run_main

    run_main()


if __name__ == "__main__":
    main()
