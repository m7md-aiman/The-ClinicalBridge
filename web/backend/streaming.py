"""Server-Sent Events streaming of a live pipeline run.

Runs ``Orchestrator.process_alert`` in a worker thread and streams each agent step to the browser as
it happens (via the orchestrator's ``on_event`` hook), then a final ``result`` event with the full
brief. Lets the web UI animate a *real* run, not just a cached replay.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from clinicalbridge.orchestrator import Orchestrator
from clinicalbridge.schemas import RPMAlert

_SENTINEL = object()


async def run_event_stream(alert: RPMAlert) -> AsyncIterator[dict]:
    """Yield SSE-shaped dicts: {"event": "step"|"result"|"error", "data": <json string>}."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def on_event(step: str, summary: str, data: dict) -> None:
        loop.call_soon_threadsafe(
            queue.put_nowait, {"type": "step", "step": step, "summary": summary, "data": data}
        )

    async def runner() -> None:
        try:
            orch = Orchestrator()
            result = await asyncio.to_thread(orch.process_alert, alert, on_event=on_event)
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "result", "result": result.to_dict()})
        except Exception as exc:  # noqa: BLE001
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "message": str(exc)})
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)

    task = asyncio.create_task(runner())
    try:
        while True:
            item = await queue.get()
            if item is _SENTINEL:
                break
            yield {"event": item["type"], "data": json.dumps(item)}
    finally:
        await task
