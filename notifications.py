import asyncio
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

from file_mapping import load_mapping

event_loop: Optional[asyncio.AbstractEventLoop] = None
update_queue: Optional[asyncio.Queue] = None
connected_clients: Set[WebSocket] = set()
pending_updates: List[List[Dict[str, Any]]] = []
factor_getter: Callable[[str], float] = lambda job_type: 0


def setup_notifier(loop: asyncio.AbstractEventLoop) -> None:
    global event_loop, update_queue
    if event_loop is None:
        event_loop = loop
    if update_queue is None:
        update_queue = asyncio.Queue()
        asyncio.create_task(notification_worker())
        for pending in pending_updates:
            asyncio.run_coroutine_threadsafe(update_queue.put(pending), event_loop)
        pending_updates.clear()


def set_factor_getter(fn: Callable[[str], float]) -> None:
    global factor_getter
    factor_getter = fn


async def notification_worker() -> None:
    if not update_queue:
        return
    while True:
        updates = await update_queue.get()
        await broadcast_updates(updates)
        update_queue.task_done()


async def broadcast_updates(updates: Iterable[Dict[str, Any]]) -> None:
    stale = []
    for ws in list(connected_clients):
        try:
            await ws.send_json(updates)
        except Exception:
            stale.append(ws)
    for ws in stale:
        connected_clients.discard(ws)


def emit_batch(updates: List[Dict[str, Any]]) -> None:
    if not updates:
        return
    if event_loop and update_queue:
        asyncio.run_coroutine_threadsafe(update_queue.put(updates), event_loop)
    else:
        pending_updates.append(updates)


def build_update_payload(
    file_ids: Iterable[str],
    mapping: Optional[Dict[str, Any]] = None,
    job_info: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    if mapping is None:
        mapping = load_mapping()
    metadata = mapping.get("metadata", {})
    id_to_path = mapping.get("id_to_path", {})
    updates: List[Dict[str, Any]] = []
    seen = set()

    for file_id in file_ids:
        if file_id in seen:
            continue
        seen.add(file_id)
        entry = metadata.get(file_id, {})
        filename = entry.get("filename") or id_to_path.get(file_id)
        if not filename:
            continue
        duration = int(entry.get("duration") or 0)
        updates.append({
            "id": file_id,
            "filename": filename,
            "duration": duration,
            "transcribed": bool(entry.get("transcribed")),
            "censored": bool(entry.get("censored")),
            "is_out_of_date": bool(entry.get("is_out_of_date")),
            "est_transcribe_duration": int(duration * factor_getter("transcribe")),
            "est_censor_duration": int(duration * factor_getter("censor")),
            **({"job": job_info} if job_info else {})
        })
    return updates


def emit_metadata_updates(
    file_ids: Iterable[str],
    mapping: Optional[Dict[str, Any]] = None
) -> None:
    updates = build_update_payload(file_ids, mapping=mapping)
    emit_batch(updates)


def emit_job_update(
    file_id: str,
    job_info: Dict[str, Any],
    mapping: Optional[Dict[str, Any]] = None
) -> None:
    updates = build_update_payload([file_id], mapping=mapping, job_info=job_info)
    emit_batch(updates)


async def websocket_handler(ws: WebSocket) -> None:
    await ws.accept()
    connected_clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.discard(ws)
