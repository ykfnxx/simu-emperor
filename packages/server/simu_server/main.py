"""Entry point for the Server process."""

from __future__ import annotations

import logging

import uvicorn

from simu_server.app import create_app
from simu_server.config import settings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    app = create_app()
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
