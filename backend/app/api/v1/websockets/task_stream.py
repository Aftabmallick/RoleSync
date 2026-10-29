import asyncio
import logging
from typing import Dict, Set, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("rolesync.websockets")

router = APIRouter(tags=["WebSockets"])


class TaskStreamManager:
    """
    Manages active WebSocket client connections for streaming
    asynchronous task progression in real time.
    """
    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, task_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if task_id not in self._connections:
            self._connections[task_id] = set()
        self._connections[task_id].add(websocket)
        logger.info(f"WebSocket client connected to task '{task_id}'. Active listeners: {len(self._connections[task_id])}")

    def disconnect(self, task_id: str, websocket: WebSocket) -> None:
        if task_id in self._connections:
            self._connections[task_id].discard(websocket)
            if not self._connections[task_id]:
                del self._connections[task_id]
        logger.info(f"WebSocket client disconnected from task '{task_id}'.")

    async def broadcast_progress(self, task_id: str, payload: Dict[str, Any]) -> None:
        if task_id not in self._connections:
            return

        dead_sockets = set()
        for ws in list(self._connections[task_id]):
            try:
                await ws.send_json(payload)
            except Exception:
                dead_sockets.add(ws)

        for ws in dead_sockets:
            self.disconnect(task_id, ws)


task_stream_manager = TaskStreamManager()


@router.websocket("/ws/v1/tasks/{task_id}")
async def task_stream_endpoint(websocket: WebSocket, task_id: str):
    """
    Real-time WebSocket progress channel for asynchronous resume tailoring tasks.
    Streams states: QUEUED -> PARSING_JD -> SYNTHESIZING_TAILORED_DRAFT -> SCORING_ATS -> COMPILING_TYPST_PDF -> COMPLETED
    """
    from app.tasks.tailor_tasks import task_store
    await task_stream_manager.connect(task_id, websocket)

    # Immediately emit current checkpoint state if task already exists
    current_state = task_store.get(task_id)
    if current_state:
        try:
            await websocket.send_json({"task_id": task_id, **current_state})
        except Exception:
            pass

    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "PING":
                await websocket.send_text("PONG")
    except WebSocketDisconnect:
        task_stream_manager.disconnect(task_id, websocket)
    except Exception as e:
        logger.warning(f"WebSocket closed for task '{task_id}': {e}")
        task_stream_manager.disconnect(task_id, websocket)

