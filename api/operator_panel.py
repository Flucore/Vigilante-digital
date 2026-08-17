"""Panel de Operador — Vigilante Digital v2.0.

API FastAPI con WebSockets para vigilancia en tiempo real desde el browser.
Se monta como sub-aplicación sobre el mismo proceso que forensic_api.

Endpoints:
    GET  /operator/                      → UI del panel (operator.html)
    WS   /operator/ws/live/{camera_id}   → Stream JPEG via WebSocket
    GET  /operator/api/cameras/status    → Estado de todas las cámaras
    GET  /operator/api/events/recent     → Eventos recientes (últimos N min)
    POST /operator/api/events/{id}/acknowledge → Operador marca evento como visto
    POST /operator/api/shift/export      → Genera PDF del turno activo

Seguridad:
    Todos los endpoints /operator/api/ requieren Bearer token válido.
    El WebSocket autentica con token en query param ?token=...
    El token se define en la variable de entorno API_SECRET_KEY.

Uso (combinado con forensic_api)::

    from api.operator_panel import operator_app
    from api.forensic_api import app as forensic_app
    forensic_app.mount("/operator", operator_app)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from fastapi import (
        FastAPI, WebSocket, WebSocketDisconnect,
        HTTPException, Depends, Query, status,
    )
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    _FASTAPI_OK = True
except ImportError:
    _FASTAPI_OK = False

LOG = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Configuración de autenticación
# ──────────────────────────────────────────────────────────────────────────────

_SECRET_KEY = os.getenv("API_SECRET_KEY", "")
_BEARER_SCHEME = HTTPBearer(auto_error=False) if _FASTAPI_OK else None


def _verify_token(
    credentials: Optional[HTTPAuthorizationCredentials],
) -> bool:
    """Verifica el token Bearer.

    En producción, API_SECRET_KEY debe estar definida como variable de entorno.
    Si no está definida, en modo desarrollo se permite acceso libre con advertencia.
    """
    if not _SECRET_KEY:
        LOG.warning("[OperatorPanel] API_SECRET_KEY no definida — acceso abierto (dev mode)")
        return True
    if credentials is None:
        return False
    return credentials.credentials == _SECRET_KEY


async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_BEARER_SCHEME),
) -> None:
    """Dependencia FastAPI que fuerza autenticación Bearer."""
    if not _verify_token(credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Bearer inválido o ausente.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ──────────────────────────────────────────────────────────────────────────────
# Estado compartido del panel (en memoria)
# ──────────────────────────────────────────────────────────────────────────────

class _OperatorState:
    """Estado global en memoria del panel de operador."""

    def __init__(self) -> None:
        # camera_id → CameraStatus dict
        self.cameras: Dict[str, Dict[str, Any]] = {}
        # Eventos recientes (circular buffer de 500)
        self.recent_events: List[Dict[str, Any]] = []
        self._max_events = 500
        # Eventos reconocidos
        self._acknowledged: Set[str] = set()
        # Conexiones WebSocket activas por camera_id
        self.ws_clients: Dict[str, Set[WebSocket]] = {}
        # Último frame JPEG por camera_id
        self.latest_frames: Dict[str, bytes] = {}

    def update_camera(self, camera_id: str, **kwargs: Any) -> None:
        if camera_id not in self.cameras:
            self.cameras[camera_id] = {
                "id": camera_id, "status": "online",
                "fps": 0, "alerts": 0, "last_seen": None,
            }
        self.cameras[camera_id].update(kwargs)
        self.cameras[camera_id]["last_seen"] = datetime.now(timezone.utc).isoformat()

    def push_event(self, event: Dict[str, Any]) -> None:
        self.recent_events.append(event)
        if len(self.recent_events) > self._max_events:
            self.recent_events = self.recent_events[-self._max_events:]

    def acknowledge(self, event_id: str) -> bool:
        self._acknowledged.add(event_id)
        return True

    def set_frame(self, camera_id: str, jpeg_bytes: bytes) -> None:
        self.latest_frames[camera_id] = jpeg_bytes

    def is_acknowledged(self, event_id: str) -> bool:
        return event_id in self._acknowledged


_state = _OperatorState()


# ──────────────────────────────────────────────────────────────────────────────
# Aplicación FastAPI del panel
# ──────────────────────────────────────────────────────────────────────────────

operator_app = FastAPI(
    title="Vigilante Digital — Panel de Operador",
    version="2.0",
    description="Panel de vigilancia en tiempo real con WebSockets.",
)

_STATIC_DIR = Path(__file__).parent / "static"
_STATIC_DIR.mkdir(parents=True, exist_ok=True)


# ── UI principal ──────────────────────────────────────────────────────────────

@operator_app.get("/", include_in_schema=False)
async def operator_ui() -> FileResponse:
    """Sirve la UI del panel de operador."""
    html = _STATIC_DIR / "operator.html"
    if not html.exists():
        raise HTTPException(status_code=404, detail="operator.html no encontrado.")
    return FileResponse(str(html))


# ── WebSocket: stream de frames en vivo ──────────────────────────────────────

@operator_app.websocket("/ws/live/{camera_id}")
async def ws_live_feed(websocket: WebSocket, camera_id: str) -> None:
    """Stream de frames JPEG via WebSocket para una cámara.

    El cliente envía el token de autenticación como primer mensaje de texto
    o via query param ?token=...
    """
    # Autenticación por query param
    token = websocket.query_params.get("token", "")
    if _SECRET_KEY and token != _SECRET_KEY:
        await websocket.close(code=4001)
        LOG.warning("[OperatorPanel] WS rechazado para cam=%s — token inválido", camera_id)
        return

    await websocket.accept()
    LOG.info("[OperatorPanel] WS conectado: cam=%s", camera_id)

    if camera_id not in _state.ws_clients:
        _state.ws_clients[camera_id] = set()
    _state.ws_clients[camera_id].add(websocket)

    try:
        while True:
            # Enviar el último frame disponible
            jpeg = _state.latest_frames.get(camera_id)
            if jpeg:
                await websocket.send_bytes(jpeg)
            await asyncio.sleep(1 / 15)  # ~15 FPS al cliente
    except WebSocketDisconnect:
        LOG.info("[OperatorPanel] WS desconectado: cam=%s", camera_id)
    finally:
        _state.ws_clients.get(camera_id, set()).discard(websocket)


# ── Estado de cámaras ─────────────────────────────────────────────────────────

@operator_app.get("/api/cameras/status", dependencies=[Depends(require_auth)])
async def cameras_status() -> Dict[str, Any]:
    """Retorna el estado actual de todas las cámaras registradas."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total":     len(_state.cameras),
        "cameras":   list(_state.cameras.values()),
    }


# ── Eventos recientes ─────────────────────────────────────────────────────────

@operator_app.get("/api/events/recent", dependencies=[Depends(require_auth)])
async def recent_events(
    minutes: int = Query(60, ge=1, le=1440, description="Ventana temporal en minutos"),
) -> Dict[str, Any]:
    """Retorna eventos de los últimos N minutos."""
    cutoff = time.time() - (minutes * 60)
    filtered = [
        {**e, "acknowledged": _state.is_acknowledged(e.get("id", ""))}
        for e in _state.recent_events
        if e.get("timestamp", 0) >= cutoff
    ]
    return {
        "minutes":  minutes,
        "total":    len(filtered),
        "events":   filtered,
    }


# ── Reconocer evento ──────────────────────────────────────────────────────────

@operator_app.post("/api/events/{event_id}/acknowledge", dependencies=[Depends(require_auth)])
async def acknowledge_event(event_id: str) -> Dict[str, Any]:
    """Operador marca un evento como revisado (acknowledge)."""
    _state.acknowledge(event_id)
    return {
        "event_id":  event_id,
        "status":    "acknowledged",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Exportar turno PDF ────────────────────────────────────────────────────────

@operator_app.post("/api/shift/export", dependencies=[Depends(require_auth)])
async def export_shift(
    from_ts: Optional[float] = None,
    to_ts:   Optional[float] = None,
) -> Dict[str, Any]:
    """Genera un resumen JSON del turno para ser convertido en PDF por el cliente.

    (La generación de PDF real se delega al ReportGenerator existente.)
    """
    now     = time.time()
    from_ts = from_ts or (now - 8 * 3600)  # último turno de 8h por defecto
    to_ts   = to_ts   or now

    events_in_shift = [
        e for e in _state.recent_events
        if from_ts <= e.get("timestamp", 0) <= to_ts
    ]

    summary: Dict[str, Any] = {
        "node_id":      os.getenv("VIGILANTE_NODE_ID", "node_01"),
        "from":         datetime.fromtimestamp(from_ts, tz=timezone.utc).isoformat(),
        "to":           datetime.fromtimestamp(to_ts,   tz=timezone.utc).isoformat(),
        "total_events": len(events_in_shift),
        "by_camera":    {},
        "by_type":      {},
        "events":       events_in_shift,
    }

    for evt in events_in_shift:
        cam  = evt.get("camera_id", "unknown")
        etype = evt.get("event_type", "unknown")
        summary["by_camera"][cam]   = summary["by_camera"].get(cam, 0) + 1
        summary["by_type"][etype]   = summary["by_type"].get(etype, 0) + 1

    return {"status": "ok", "shift_report": summary}


# ──────────────────────────────────────────────────────────────────────────────
# API pública para inyectar frames desde runner.py
# ──────────────────────────────────────────────────────────────────────────────

def push_frame(camera_id: str, frame_bgr: Any) -> None:
    """Inyecta un frame BGR en el estado del panel (llamado desde runner.py).

    Comprime a JPEG y lo almacena para ser transmitido via WebSocket.
    """
    import cv2 as _cv2
    import numpy as _np
    try:
        quality = int(os.getenv("PANEL_JPEG_QUALITY", "60"))
        _, buf = _cv2.imencode(".jpg", frame_bgr, [_cv2.IMWRITE_JPEG_QUALITY, quality])
        _state.set_frame(camera_id, buf.tobytes())
        _state.update_camera(camera_id, status="online")
    except Exception as exc:
        LOG.debug("[OperatorPanel] Error comprimiendo frame cam=%s: %s", camera_id, exc)


def push_event(event: Dict[str, Any]) -> None:
    """Inyecta un evento en el panel (llamado desde EventLogger / TriggerManager)."""
    _state.push_event(event)
    cam = event.get("camera_id", "")
    if cam:
        alerts = _state.cameras.get(cam, {}).get("alerts", 0)
        _state.update_camera(cam, alerts=alerts + 1)


def mark_camera_offline(camera_id: str) -> None:
    """Marca una cámara como offline en el panel."""
    _state.update_camera(camera_id, status="offline", fps=0)
