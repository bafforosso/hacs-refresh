from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def hacs() -> MagicMock:
    """Return a fake HACS instance."""
    hacs = MagicMock()

    hacs.system.disabled = False

    hacs.queue.running = False
    hacs.queue.pending_tasks = 0

    queued_tasks = []

    def add_to_queue(task):
        queued_tasks.append(task)

    async def process_queue():
        for task in queued_tasks:
            await task

    hacs.queue.add = MagicMock(side_effect=add_to_queue)
    hacs.async_process_queue = AsyncMock(side_effect=process_queue)

    hacs.repositories.list_downloaded = []

    hacs.coordinators = {}

    hacs.data.async_write = AsyncMock()

    return hacs
