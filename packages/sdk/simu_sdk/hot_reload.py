"""Hot-reload support — watches config files and reloads without restart.

Uses ``watchfiles`` for efficient filesystem monitoring.  When soul.md or
data_scope.yaml changes, the new content is parsed and swapped into the
running Agent without interrupting in-flight invocations.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable

from watchfiles import awatch, Change

logger = logging.getLogger(__name__)


async def watch_config(
    config_path: Path,
    on_change: Callable[[str], None],
) -> None:
    """Watch *config_path* directory and call *on_change* when files change.

    ``on_change`` receives the name of the changed file (e.g. ``"soul.md"``).

    This coroutine runs forever and should be launched as a background task.
    """
    watched_files = {"soul.md", "data_scope.yaml"}
    logger.info("Watching config directory: %s", config_path)

    async for changes in awatch(config_path):
        for change_type, changed_path in changes:
            if change_type != Change.modified:
                continue
            name = Path(changed_path).name
            if name in watched_files:
                logger.info("Config file changed: %s", name)
                try:
                    on_change(name)
                except Exception:
                    logger.exception("Error reloading config from %s", name)
