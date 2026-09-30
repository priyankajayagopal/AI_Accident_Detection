import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import path
from server.api_routes import router
from server.db import init_db
from server.websocket import hub


@asynccontextmanager
async def lifespan(app):
    init_db()
    hub.loop = asyncio.get_running_loop()
    yield


app = FastAPI(title="ATOS - Accident detection & Traffic clearance", version="1.0", lifespan=lifespan)
app.include_router(router)


@app.websocket("/ws")
async def ws(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(ws)


_pub = path("dashboard", "atos_dashboard", "public")
app.mount("/static", StaticFiles(directory=str(_pub.parent / "src")), name="static")


@app.get("/")
def index():
    return FileResponse(_pub / "index.html")
