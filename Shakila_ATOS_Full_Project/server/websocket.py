"""WebSocket hub: pushes incident / agent / alert events to every dashboard client."""
import asyncio
from typing import List, Optional

from fastapi import WebSocket


class Hub:
    def __init__(self):
        self.clients: List[WebSocket] = []
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.clients.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.clients:
            self.clients.remove(ws)

    async def _broadcast(self, event: dict):
        for ws in list(self.clients):
            try:
                await ws.send_json(event)
            except Exception:
                self.disconnect(ws)

    def publish(self, event: dict):
        """Thread-safe: called from worker threads (agents, video pipeline)."""
        if self.loop and self.clients:
            asyncio.run_coroutine_threadsafe(self._broadcast(event), self.loop)


hub = Hub()
