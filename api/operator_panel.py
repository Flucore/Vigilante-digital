"""Panel de Operador — Vigilante Digital v2.0.

API FastAPI con WebSockets para vigilancia en tiempo real desde el browser.
Se monta como sub-aplicación sobre el mismo proceso que forensic_api.

Endpoints:
    GET  /operator/                      → UI del panel (operator.html)
    WS   /operator/ws/live/{camera_id}   → Stream JPEG via WebSocket (cada cuadro
                                           puede ir precedido de su estado de
                                           detección como texto JSON)
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
import mimetypes
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

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
        # Último cuadro por camera_id: (JPEG, estado de detección o None).
        # Se guarda como par en una sola asignación para que el WebSocket
        # nunca lea el cuadro de un instante con el estado de otro.
        self.latest_frames: Dict[str, Tuple[bytes, Optional[Dict[str, Any]]]] = {}
        # Estado recibido que espera a su cuadro (llega justo antes que él).
        self._pending_status: Dict[str, Dict[str, Any]] = {}
        # Medición de cuadros recibidos por camera_id: [inicio_ventana, cuenta]
        self._fps_window: Dict[str, List[float]] = {}
        # Último cuadro recibido por camera_id (reloj monotónico)
        self.last_frame_mono: Dict[str, float] = {}

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

    def set_status(self, camera_id: str, status_data: Dict[str, Any]) -> None:
        self._pending_status[camera_id] = status_data

    def set_frame(self, camera_id: str, jpeg_bytes: bytes) -> None:
        status_data = self._pending_status.pop(camera_id, None)
        self.latest_frames[camera_id] = (jpeg_bytes, status_data)

    def count_frame(self, camera_id: str) -> Optional[float]:
        """Cuenta un cuadro recibido; cada ~1 s retorna los FPS medidos."""
        now = time.monotonic()
        self.last_frame_mono[camera_id] = now
        window = self._fps_window.setdefault(camera_id, [now, 0.0])
        window[1] += 1
        elapsed = now - window[0]
        if elapsed < _FPS_WINDOW_SEC:
            return None
        fps = window[1] / elapsed
        self._fps_window[camera_id] = [now, 0.0]
        return round(fps, 1)

    def is_acknowledged(self, event_id: str) -> bool:
        return event_id in self._acknowledged


_state = _OperatorState()

# Ventana de medición de FPS y tiempo sin cuadros tras el cual se informa 0.
_FPS_WINDOW_SEC = 1.0
_FPS_STALE_SEC = 2.0

# Segundos que una alerta se considera activa (borde rojo de la tarjeta).
_ALERT_ACTIVE_SEC = 10.0

# Identificador del nodo que muestra el panel y que va en el reporte de turno.
_NODE_ID = os.getenv("VIGILANTE_NODE_ID", "edge-01")

# Cámaras cuyos eventos no se muestran en el panel (corridas del experimento).
_EXCLUDED_EVENT_CAMERAS = {"CAM_EVAL"}


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

# Fuentes del panel servidas localmente: la UI no hace peticiones a internet.
_FONTS_DIR = _STATIC_DIR / "fonts"
if _FONTS_DIR.is_dir():
    # Windows no siempre registra .woff2; sin esto se sirve como octet-stream.
    mimetypes.add_type("font/woff2", ".woff2")
    operator_app.mount("/fonts", StaticFiles(directory=str(_FONTS_DIR)), name="fonts")


# ── UI principal ──────────────────────────────────────────────────────────────

@operator_app.get("/", include_in_schema=False)
async def operator_ui() -> FileResponse:
    """Sirve la UI del panel de operador."""
    html = _STATIC_DIR / "operator.html"
    if not html.exists():
        raise HTTPException(status_code=404, detail="operator.html no encontrado.")
    # no-cache: el navegador revalida siempre y no muestra una versión vieja.
    return FileResponse(str(html), headers={"Cache-Control": "no-cache"})


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
            # Enviar el último frame disponible. Si trae estado de detección,
            # va antes como texto JSON: el cliente lo aplica al pintar el
            # cuadro binario que sigue.
            packet = _state.latest_frames.get(camera_id)
            if packet:
                jpeg, status_data = packet
                if status_data is not None:
                    await websocket.send_text(json.dumps(status_data))
                await websocket.send_bytes(jpeg)
            await asyncio.sleep(1 / 15)  # ~15 FPS al cliente
    except WebSocketDisconnect:
        LOG.info("[OperatorPanel] WS desconectado: cam=%s", camera_id)
    finally:
        _state.ws_clients.get(camera_id, set()).discard(websocket)


# ── Identificador del nodo ────────────────────────────────────────────────────

@operator_app.get("/api/node", dependencies=[Depends(require_auth)])
async def node_info() -> Dict[str, Any]:
    """Identificador del nodo (variable de entorno VIGILANTE_NODE_ID)."""
    return {"node_id": _NODE_ID}


# ── Estado de cámaras ─────────────────────────────────────────────────────────

@operator_app.get("/api/cameras/status", dependencies=[Depends(require_auth)])
async def cameras_status() -> Dict[str, Any]:
    """Retorna el estado actual de todas las cámaras registradas."""
    now = time.monotonic()
    # Cámaras con un evento de los últimos _ALERT_ACTIVE_SEC sin Ack.
    alert_cutoff = time.time() - _ALERT_ACTIVE_SEC
    alerting = {
        e.get("camera_id")
        for e in _state.recent_events
        if e.get("timestamp", 0) >= alert_cutoff and not _state.is_acknowledged(e.get("id", ""))
    }
    cameras = []
    for cam in _state.cameras.values():
        cam = dict(cam)
        last = _state.last_frame_mono.get(cam["id"])
        if last is None or now - last > _FPS_STALE_SEC:
            cam["fps"] = 0
        cam["alert_active"] = cam["id"] in alerting
        cameras.append(cam)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total":     len(cameras),
        "cameras":   cameras,
    }


# ── Eventos recientes ─────────────────────────────────────────────────────────

@operator_app.get("/api/events/recent", dependencies=[Depends(require_auth)])
async def recent_events(
    minutes: int = Query(60, ge=1, le=1440, description="Ventana temporal en minutos"),
) -> Dict[str, Any]:
    """Retorna eventos de los últimos N minutos, del más reciente al más antiguo."""
    cutoff = time.time() - (minutes * 60)
    filtered = [
        {**e, "acknowledged": _state.is_acknowledged(e.get("id", ""))}
        for e in _state.recent_events
        if e.get("timestamp", 0) >= cutoff
    ]
    filtered.sort(key=lambda e: e.get("timestamp", 0), reverse=True)
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


# ── Captura de la caída ───────────────────────────────────────────────────────

@operator_app.get("/api/events/{event_id}/captura", dependencies=[Depends(require_auth)])
async def event_capture(event_id: str) -> FileResponse:
    """Imagen del momento de la caída, si el evento la tiene anotada.

    La ruta del archivo sale del evento guardado en el panel (la anota
    demo_panel.py --correo cuando el notificador prepara la imagen); el
    cliente solo entrega el id, nunca una ruta.
    """
    for event in reversed(_state.recent_events):
        if event.get("id") == event_id:
            path = event.get("captura")
            if path and Path(str(path)).is_file():
                return FileResponse(str(path), media_type="image/jpeg")
            break
    raise HTTPException(status_code=404, detail="El evento no tiene captura.")


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
        "node_id":      _NODE_ID,
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
        fps = _state.count_frame(camera_id)
        if fps is None:
            _state.update_camera(camera_id, status="online")
        else:
            _state.update_camera(camera_id, status="online", fps=fps)
    except Exception as exc:
        LOG.debug("[OperatorPanel] Error comprimiendo frame cam=%s: %s", camera_id, exc)


def push_status(camera_id: str, status_data: Dict[str, Any]) -> None:
    """Recibe el estado de detección del cuadro (runner.py vía set_status_sink).

    Llega justo antes de su cuadro; push_frame lo empareja con él.
    """
    _state.set_status(camera_id, dict(status_data))


def _to_epoch(value: Any) -> float:
    """Convierte un timestamp ISO 8601 (formato de EventLogger) a segundos epoch.

    Acepta también números. Si no se puede interpretar, usa la hora actual
    para que el evento no quede fuera del filtro por minutos.
    """
    if isinstance(value, (int, float)):
        return float(value)
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (TypeError, ValueError):
        return time.time()


def push_event(event: Dict[str, Any]) -> None:
    """Inyecta un evento en el panel (llamado desde runner.py vía set_event_sink).

    Trabaja sobre una copia: el timestamp se convierte a epoch y se asigna
    un id solo dentro del panel. El evento original (el que EventLogger
    guarda en el JSONL) no se modifica.
    """
    cam = event.get("camera_id", "")
    if cam in _EXCLUDED_EVENT_CAMERAS:
        return
    event = dict(event)
    event["timestamp_iso"] = event.get("timestamp")
    event["timestamp"] = _to_epoch(event.get("timestamp"))
    event.setdefault("id", uuid.uuid4().hex)
    _state.push_event(event)
    if cam:
        alerts = _state.cameras.get(cam, {}).get("alerts", 0)
        _state.update_camera(cam, alerts=alerts + 1)


def annotate_event(event_id: str, **fields: Any) -> bool:
    """Agrega campos a un evento ya publicado en el panel (p. ej. estado del correo).

    Lo usa demo_camara_ip.py para mostrar "Correo enviado" en la tarjeta del
    evento cuando termina el envío, que ocurre después de la alerta.
    Retorna False si el evento ya no está en el buffer.
    """
    for event in reversed(_state.recent_events):
        if event.get("id") == event_id:
            event.update(fields)
            return True
    return False


def register_camera(
    camera_id: str,
    status: str = "esperando",
    name: str = "",
    zone: str = "",
) -> None:
    """Registra una cámara en el panel antes de que lleguen cuadros.

    name y zone vienen del config y el panel los muestra junto al id.
    Con el primer push_frame el estado pasa a "online".
    """
    _state.update_camera(camera_id, status=status, fps=0, name=name, zone=zone)


def mark_camera_offline(camera_id: str) -> None:
    """Marca una cámara como offline en el panel."""
    _state.update_camera(camera_id, status="offline", fps=0)
