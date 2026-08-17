"""API REST de Auditoría Forense — Vigilante Digital v2.0.

Sirve los endpoints de búsqueda, exportación y estadísticas del módulo forense.
Además sirve la UI estática desde api/static/ y monta el Panel de Operador.

Seguridad (Sprint 4):
  - Bearer token (API_SECRET_KEY) en todos los endpoints /api/v1/
  - Validación HMAC-SHA256 en webhook de triggers (X-Vigilante-Signature)
  - Rate limiting: 60 req/min por IP en endpoints de búsqueda (via slowapi)
  - No se loguean frames ni imágenes en los logs del servidor

Uso:
    python -m uvicorn api.forensic_api:app --port 8000 --host 0.0.0.0

Endpoints:
    GET  /                          → UI de búsqueda forense (forensic_ui.html)
    GET  /operator/                 → Panel de Operador en tiempo real
    GET  /api/v1/health             → Health check (público)
    GET  /api/v1/search             → Buscar detecciones (auth requerida)
    GET  /api/v1/events             → Buscar eventos confirmados (auth requerida)
    GET  /api/v1/export/csv         → Exportar detecciones en CSV (auth requerida)
    GET  /api/v1/stats/summary      → Estadísticas generales (auth requerida)
    POST /api/v1/audit/log          → Registro manual de consulta (auth requerida)
    POST /api/v1/webhook/trigger    → Webhook de trigger con HMAC-SHA256
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Asegurar root en sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from fastapi import (
        FastAPI, Query, Request, HTTPException,
        Depends, status,
    )
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    _SLOWAPI_AVAILABLE = True
except ImportError:
    _SLOWAPI_AVAILABLE = False

from outputs.forensic_db import ForensicDB, SearchFilters
from core.config_loader import ConfigLoader

LOG = logging.getLogger(__name__)

if not _FASTAPI_AVAILABLE:
    print(
        "[ERROR] FastAPI no instalado. Instalar con:\n"
        "  pip install fastapi uvicorn[standard]\n",
        file=sys.stderr,
    )
    sys.exit(1)

# ── Seguridad: Bearer token ───────────────────────────────────────────────────
_SECRET_KEY   = os.getenv("API_SECRET_KEY", "")
_WEBHOOK_KEY  = os.getenv("WEBHOOK_SECRET", "")
_BEARER       = HTTPBearer(auto_error=False)


async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_BEARER),
) -> None:
    """Dependencia: valida Bearer token en todos los endpoints /api/v1/."""
    if not _SECRET_KEY:
        # Modo desarrollo sin token configurado
        LOG.warning("[ForensicAPI] API_SECRET_KEY no definida — acceso abierto (dev mode)")
        return
    if credentials is None or credentials.credentials != _SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Bearer inválido o ausente.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _verify_hmac(body: bytes, signature_header: str) -> bool:
    """Valida HMAC-SHA256 del body contra X-Vigilante-Signature."""
    if not _WEBHOOK_KEY:
        return True  # sin clave configurada, acepta todo (dev mode)
    expected = "sha256=" + hmac.new(
        _WEBHOOK_KEY.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


# ── Rate limiter ──────────────────────────────────────────────────────────────
if _SLOWAPI_AVAILABLE:
    limiter = Limiter(key_func=get_remote_address)
else:
    limiter = None  # type: ignore[assignment]


def _rate_limit(limit_str: str = "60/minute"):
    """Decorador de rate limiting condicional (no-op si slowapi no disponible)."""
    if _SLOWAPI_AVAILABLE and limiter is not None:
        return limiter.limit(limit_str)
    def noop(f: Any) -> Any:
        return f
    return noop


# ── Carga de configuración ────────────────────────────────────────────────────
_CONFIG_PATH = ROOT / os.getenv("VIGILANTE_CONFIG", "client_config.json")
try:
    _loader = ConfigLoader(_CONFIG_PATH)
    _forensic_cfg = _loader.get_section("forensic_audit", {})
except Exception as exc:
    LOG.warning("No se cargó client_config.json (%s) — usando defaults.", exc)
    _loader = None
    _forensic_cfg = {}

_JSONL_PATH = ROOT / _forensic_cfg.get("output_jsonl", "outputs/metadata_index.jsonl")
_EVENTS_DIR = ROOT / "outputs"

db = ForensicDB.from_env(jsonl_path=str(_JSONL_PATH), events_dir=str(_EVENTS_DIR))

# ── Aplicación FastAPI ────────────────────────────────────────────────────────
app = FastAPI(
    title="Vigilante Digital — Forensic API",
    version="2.0",
    description=(
        "API de Auditoría Forense + Panel de Operador para Vigilante Digital. "
        "Requiere Bearer token (API_SECRET_KEY) en todos los endpoints /api/v1/."
    ),
    docs_url="/docs" if os.getenv("ENABLE_DOCS", "false").lower() == "true" else None,
    redoc_url=None,
)

# Rate limiter handler
if _SLOWAPI_AVAILABLE and limiter is not None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Vigilante-Signature"],
)

# Archivos estáticos
_STATIC_DIR = Path(__file__).parent / "static"
_STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# Panel de Operador (sub-aplicación)
try:
    from api.operator_panel import operator_app
    app.mount("/operator", operator_app)
    LOG.info("[ForensicAPI] Panel de Operador montado en /operator")
except Exception as _op_exc:
    LOG.warning("[ForensicAPI] Panel de Operador no disponible: %s", _op_exc)


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def _log_audit(
    request: Request,
    endpoint: str,
    params: Dict[str, Any],
    result_count: int,
) -> None:
    """Registra la consulta en la cadena de custodia (ISO 27001)."""
    ip = _get_client_ip(request)
    db.log_audit_query(
        endpoint=endpoint,
        query_params=params,
        result_count=result_count,
        user_id="anonymous",
        user_ip=ip,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    """Sirve la UI de búsqueda forense."""
    ui_path = _STATIC_DIR / "forensic_ui.html"
    if not ui_path.exists():
        raise HTTPException(status_code=404, detail="forensic_ui.html no encontrado en api/static/")
    return FileResponse(str(ui_path))


@app.get("/api/v1/health")
async def health() -> Dict[str, Any]:  # público — no requiere auth
    """Health check del servicio."""
    stats = db.get_summary_stats()
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "db_mode": stats.get("mode", "unknown"),
        "total_detections": stats.get("total_detections", 0),
    }


@app.get("/api/v1/search", dependencies=[Depends(require_auth)])
@_rate_limit("60/minute")
async def search_detections(
    request: Request,
    camera_id:    Optional[str] = Query(None, description="ID de cámara (exacto)"),
    object_class: Optional[str] = Query(None, description="Clase del objeto (parcial)"),
    color:        Optional[str] = Query(None, description="Color del objeto (parcial)"),
    from_:        Optional[str] = Query(None, alias="from", description="Fecha inicio ISO 8601"),
    to:           Optional[str] = Query(None, description="Fecha fin ISO 8601"),
    limit:        int           = Query(100, ge=1, le=1000, description="Máximo de resultados"),
    offset:       int           = Query(0, ge=0, description="Offset para paginación"),
) -> Dict[str, Any]:
    """Busca detecciones con filtros opcionales.

    Ejemplo: /api/v1/search?object_class=car&color=white&limit=50
    """
    filters = SearchFilters(
        camera_id=camera_id,
        object_class=object_class,
        color_label=color,
        date_from=from_,
        date_to=to,
        limit=limit,
        offset=offset,
    )
    results = db.search_detections(filters)

    params = {k: v for k, v in {
        "camera_id": camera_id, "object_class": object_class,
        "color": color, "from": from_, "to": to, "limit": limit,
    }.items() if v is not None}
    _log_audit(request, "/api/v1/search", params, len(results))

    return {
        "total": len(results),
        "offset": offset,
        "filters": params,
        "results": results,
    }


@app.get("/api/v1/events", dependencies=[Depends(require_auth)])
@_rate_limit("60/minute")
async def search_events(
    request: Request,
    camera_id:   Optional[str] = Query(None),
    event_type:  Optional[str] = Query(None),
    from_:       Optional[str] = Query(None, alias="from"),
    to:          Optional[str] = Query(None),
    alert_level: Optional[int] = Query(None, ge=1, le=3),
    limit:       int           = Query(50, ge=1, le=500),
    offset:      int           = Query(0, ge=0),
) -> Dict[str, Any]:
    """Busca eventos de seguridad confirmados (caídas, intrusiones, etc.)."""
    filters = SearchFilters(
        camera_id=camera_id,
        event_type=event_type,
        date_from=from_,
        date_to=to,
        alert_level_min=alert_level,
        limit=limit,
        offset=offset,
    )
    results = db.search_events(filters)

    params = {k: v for k, v in {
        "camera_id": camera_id, "event_type": event_type,
        "from": from_, "to": to, "alert_level": alert_level,
    }.items() if v is not None}
    _log_audit(request, "/api/v1/events", params, len(results))

    return {"total": len(results), "offset": offset, "results": results}


@app.get("/api/v1/export/csv", dependencies=[Depends(require_auth)])
@_rate_limit("10/minute")
async def export_csv(
    request: Request,
    camera_id:    Optional[str] = Query(None),
    object_class: Optional[str] = Query(None),
    color:        Optional[str] = Query(None),
    from_:        Optional[str] = Query(None, alias="from"),
    to:           Optional[str] = Query(None),
    limit:        int           = Query(5000, ge=1, le=50000),
) -> StreamingResponse:
    """Exporta detecciones en formato CSV para descarga directa."""
    filters = SearchFilters(
        camera_id=camera_id,
        object_class=object_class,
        color_label=color,
        date_from=from_,
        date_to=to,
        limit=limit,
    )
    csv_content = db.export_to_csv_stream(filters)

    _log_audit(request, "/api/v1/export/csv", {"limit": limit}, 1)

    filename = f"vigilante_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/v1/stats/summary", dependencies=[Depends(require_auth)])
async def stats_summary(request: Request) -> Dict[str, Any]:
    """Retorna estadísticas generales del sistema forense."""
    stats = db.get_summary_stats()
    _log_audit(request, "/api/v1/stats/summary", {}, 1)
    return stats


@app.post("/api/v1/audit/log", dependencies=[Depends(require_auth)])
async def manual_audit_log(
    request: Request,
    body: Dict[str, Any],
) -> Dict[str, str]:
    """Registra manualmente una consulta en la cadena de custodia."""
    db.log_audit_query(
        endpoint=body.get("endpoint", "manual"),
        query_params=body.get("params", {}),
        result_count=int(body.get("result_count", 0)),
        user_id=body.get("user_id", "anonymous"),
        user_ip=_get_client_ip(request),
    )
    return {"status": "logged", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/api/v1/webhook/trigger")
async def webhook_trigger(request: Request) -> Dict[str, Any]:
    """Recibe eventos de trigger desde el TriggerManager externo.

    Valida la firma HMAC-SHA256 en el header X-Vigilante-Signature.
    El secreto se configura en la variable de entorno WEBHOOK_SECRET.

    Header requerido: X-Vigilante-Signature: sha256=<hex_digest>
    """
    body      = await request.body()
    signature = request.headers.get("X-Vigilante-Signature", "")

    if not _verify_hmac(body, signature):
        LOG.warning(
            "[ForensicAPI] Webhook rechazado — firma HMAC inválida desde %s",
            _get_client_ip(request),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Firma HMAC-SHA256 inválida.",
        )

    try:
        import json as _json
        payload = _json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Body no es JSON válido.")

    # Persistir como evento en ForensicDB
    db.insert_event(
        camera_id=payload.get("camera_id", "webhook"),
        event_type=payload.get("event_type", "trigger"),
        alert_level=int(payload.get("alert_level", 2)),
        metadata=payload,
    )

    LOG.info(
        "[ForensicAPI] Webhook trigger recibido: type=%s cam=%s",
        payload.get("event_type"), payload.get("camera_id"),
    )
    return {"status": "accepted", "timestamp": datetime.now(timezone.utc).isoformat()}


# ══════════════════════════════════════════════════════════════════════════════
# Punto de entrada directo
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8000"))
    LOG.info("Iniciando Forensic API en http://localhost:%d", port)
    uvicorn.run(
        "api.forensic_api:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )
