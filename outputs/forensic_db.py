"""Conector de base de datos forense — Vigilante Digital v2.0.

Soporta dos modos de operación transparentes:
  - postgres : PostgreSQL 14+ (+ TimescaleDB opcional). Máximo rendimiento.
  - jsonl    : Fallback de solo lectura desde metadata_index.jsonl.
               El sistema corre sin base de datos configurada.

Selección automática: si la variable de entorno AUDIT_DB_URL está definida
→ modo postgres; de lo contrario → modo jsonl.

Uso::

    db = ForensicDB.from_env(jsonl_path="outputs/metadata_index.jsonl")

    # Insertar detecciones (modo postgres)
    db.insert_detection({...})
    db.flush()

    # Buscar
    filters = SearchFilters(object_class="car", color_label="white", limit=50)
    results = db.search_detections(filters)
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union

LOG = logging.getLogger(__name__)

# psycopg2 es opcional; se captura la excepción de importación
try:
    import psycopg2
    import psycopg2.extras
    _PSYCOPG2_AVAILABLE = True
except ImportError:
    _PSYCOPG2_AVAILABLE = False

_BATCH_SIZE = 100  # filas por INSERT batch


# ──────────────────────────────────────────────────────────────────────────────
# Dataclasses de filtros
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SearchFilters:
    """Filtros de búsqueda para detecciones y eventos.

    Todos los campos son opcionales; los campos None se ignoran en la consulta.
    """
    camera_id:      Optional[str] = None
    object_class:   Optional[str] = None
    color_label:    Optional[str] = None
    date_from:      Optional[str] = None   # ISO 8601 string o None
    date_to:        Optional[str] = None   # ISO 8601 string o None
    event_type:     Optional[str] = None   # para búsqueda de eventos
    alert_level_min: Optional[int] = None
    limit:          int = 100
    offset:         int = 0


# ──────────────────────────────────────────────────────────────────────────────
# ForensicDB
# ──────────────────────────────────────────────────────────────────────────────

class ForensicDB:
    """Capa de persistencia forense con modo postgres y fallback JSONL.

    Args:
        db_url: URL de conexión PostgreSQL (ej: postgresql://user:pass@host/db).
                Si es None o vacío se usa modo JSONL.
        jsonl_path: Ruta al archivo de metadatos JSONL (fallback y origen de datos batch).
        events_dir: Directorio donde EventLogger escribe los archivos events_*.jsonl.
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        jsonl_path: Union[str, Path] = "outputs/metadata_index.jsonl",
        events_dir: Union[str, Path] = "outputs",
    ) -> None:
        self._db_url = db_url or ""
        self._jsonl_path = Path(jsonl_path)
        self._events_dir = Path(events_dir)
        self._mode = "postgres" if (self._db_url and _PSYCOPG2_AVAILABLE) else "jsonl"
        self._conn: Any = None
        self._lock = threading.Lock()
        self._insert_buffer: List[Dict] = []

        if self._mode == "postgres":
            LOG.info("[ForensicDB] Modo: PostgreSQL | %s", self._db_url[:30] + "...")
        else:
            if self._db_url and not _PSYCOPG2_AVAILABLE:
                LOG.warning(
                    "[ForensicDB] psycopg2 no instalado. Usando modo JSONL. "
                    "Instalar con: pip install psycopg2-binary"
                )
            else:
                LOG.info("[ForensicDB] Modo: JSONL fallback | %s", self._jsonl_path)

    @classmethod
    def from_env(
        cls,
        jsonl_path: Union[str, Path] = "outputs/metadata_index.jsonl",
        events_dir: Union[str, Path] = "outputs",
    ) -> "ForensicDB":
        """Crea instancia leyendo AUDIT_DB_URL desde el entorno."""
        db_url = os.getenv("AUDIT_DB_URL", "")
        return cls(db_url=db_url, jsonl_path=jsonl_path, events_dir=events_dir)

    # ── Conexión lazy ─────────────────────────────────────────────────────────

    def _ensure_connected(self) -> bool:
        """Conecta a PostgreSQL si aún no está conectado. Retorna True si ok."""
        if self._mode != "postgres":
            return False
        if self._conn is not None:
            try:
                self._conn.isolation_level  # ping ligero
                return True
            except Exception:
                self._conn = None

        try:
            self._conn = psycopg2.connect(self._db_url)
            self._conn.autocommit = False
            LOG.info("[ForensicDB] Conectado a PostgreSQL.")
            return True
        except Exception as exc:
            LOG.warning(
                "[ForensicDB] No se pudo conectar a PostgreSQL (%s). "
                "Degradando a modo JSONL.", exc,
            )
            self._mode = "jsonl"
            return False

    # ── Inserción (modo postgres) ─────────────────────────────────────────────

    def insert_detection(self, detection: Dict[str, Any]) -> None:
        """Encola una detección para inserción batch. Llama flush() para escribir."""
        with self._lock:
            self._insert_buffer.append(detection)
            if len(self._insert_buffer) >= _BATCH_SIZE:
                self._flush_locked()

    def insert_event(self, event: Dict[str, Any]) -> None:
        """Inserta un evento confirmado directamente (sin buffer)."""
        if not self._ensure_connected():
            return
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO events (
                        id, camera_id, event_type, start_time, end_time,
                        duration_seconds, alert_level, photo_path, photo_hash,
                        compliance, schema_version, metadata
                    ) VALUES (
                        %(id)s, %(camera_id)s, %(event_type)s, %(start_time)s, %(end_time)s,
                        %(duration_seconds)s, %(alert_level)s, %(photo_path)s, %(photo_hash)s,
                        %(compliance)s, %(schema_version)s, %(metadata)s
                    )
                    ON CONFLICT (id) DO NOTHING
                    """,
                    {
                        "id": event.get("id") or str(uuid.uuid4()),
                        "camera_id": event.get("camera_id", "UNKNOWN"),
                        "event_type": event.get("event_type", "unknown"),
                        "start_time": event.get("start_time") or event.get("timestamp"),
                        "end_time": event.get("end_time"),
                        "duration_seconds": event.get("duration_seconds"),
                        "alert_level": int(event.get("alert_level", 1)),
                        "photo_path": event.get("photo_path"),
                        "photo_hash": _file_hash(event.get("photo_path")),
                        "compliance": json.dumps(event.get("compliance", {})),
                        "schema_version": event.get("event_schema_version", "2.0"),
                        "metadata": json.dumps({
                            k: v for k, v in event.items()
                            if k not in {"id", "camera_id", "event_type", "start_time",
                                        "end_time", "duration_seconds", "alert_level",
                                        "photo_path", "compliance", "event_schema_version"}
                        }),
                    },
                )
            self._conn.commit()
        except Exception:
            LOG.exception("[ForensicDB] Error insertando evento.")
            try:
                self._conn.rollback()
            except Exception:
                pass

    def flush(self) -> int:
        """Escribe el buffer de detecciones pendientes. Retorna cantidad insertada."""
        with self._lock:
            return self._flush_locked()

    def _flush_locked(self) -> int:
        """Escribe el buffer. Requiere el lock."""
        if not self._insert_buffer:
            return 0
        if not self._ensure_connected():
            LOG.debug("[ForensicDB] flush ignorado — modo JSONL.")
            count = len(self._insert_buffer)
            self._insert_buffer.clear()
            return count

        batch = list(self._insert_buffer)
        self._insert_buffer.clear()

        try:
            with self._conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO detections (
                        id, camera_id, timestamp, frame_idx,
                        object_class, confidence,
                        bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax,
                        color_label, track_id, schema_version, metadata
                    ) VALUES %s
                    ON CONFLICT DO NOTHING
                    """,
                    [
                        (
                            str(uuid.uuid4()),
                            d.get("camera_id", "UNKNOWN"),
                            d.get("timestamp"),
                            int(d.get("frame_idx", 0)),
                            d.get("object_class", "unknown"),
                            float(d.get("confidence", 0)),
                            int(d.get("bbox", {}).get("xmin", 0)),
                            int(d.get("bbox", {}).get("ymin", 0)),
                            int(d.get("bbox", {}).get("xmax", 0)),
                            int(d.get("bbox", {}).get("ymax", 0)),
                            d.get("color_label", "unknown"),
                            d.get("track_id"),
                            d.get("schema_version", "2.0"),
                            json.dumps(d.get("metadata", {})),
                        )
                        for d in batch
                    ],
                    page_size=_BATCH_SIZE,
                )
            self._conn.commit()
            return len(batch)
        except Exception:
            LOG.exception("[ForensicDB] Error en flush batch.")
            try:
                self._conn.rollback()
            except Exception:
                pass
            return 0

    # ── Búsqueda ──────────────────────────────────────────────────────────────

    def search_detections(self, filters: SearchFilters) -> List[Dict[str, Any]]:
        """Busca detecciones aplicando los filtros dados.

        Funciona en ambos modos (postgres y jsonl).
        """
        if self._mode == "postgres" and self._ensure_connected():
            return self._search_postgres(filters)
        return self._search_jsonl(filters)

    def search_events(self, filters: SearchFilters) -> List[Dict[str, Any]]:
        """Busca eventos confirmados aplicando los filtros dados."""
        if self._mode == "postgres" and self._ensure_connected():
            return self._search_events_postgres(filters)
        return self._search_events_jsonl(filters)

    def _search_postgres(self, f: SearchFilters) -> List[Dict[str, Any]]:
        """Búsqueda de detecciones en PostgreSQL con WHERE dinámico."""
        clauses = []
        params: Dict[str, Any] = {}

        if f.camera_id:
            clauses.append("camera_id = %(camera_id)s")
            params["camera_id"] = f.camera_id
        if f.object_class:
            clauses.append("object_class ILIKE %(object_class)s")
            params["object_class"] = f"%{f.object_class}%"
        if f.color_label:
            clauses.append("color_label ILIKE %(color_label)s")
            params["color_label"] = f"%{f.color_label}%"
        if f.date_from:
            clauses.append("timestamp >= %(date_from)s")
            params["date_from"] = f.date_from
        if f.date_to:
            clauses.append("timestamp <= %(date_to)s")
            params["date_to"] = f.date_to

        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        params["limit"] = f.limit
        params["offset"] = f.offset

        sql = f"""
            SELECT id::text, camera_id, timestamp::text, frame_idx,
                   object_class, confidence::float,
                   bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax,
                   color_label, track_id, schema_version
            FROM detections
            {where}
            ORDER BY timestamp DESC
            LIMIT %(limit)s OFFSET %(offset)s
        """
        try:
            with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                return [dict(r) for r in cur.fetchall()]
        except Exception:
            LOG.exception("[ForensicDB] Error en búsqueda postgres.")
            return []

    def _search_events_postgres(self, f: SearchFilters) -> List[Dict[str, Any]]:
        """Búsqueda de eventos en PostgreSQL."""
        clauses = []
        params: Dict[str, Any] = {}

        if f.camera_id:
            clauses.append("camera_id = %(camera_id)s")
            params["camera_id"] = f.camera_id
        if f.event_type:
            clauses.append("event_type ILIKE %(event_type)s")
            params["event_type"] = f"%{f.event_type}%"
        if f.date_from:
            clauses.append("start_time >= %(date_from)s")
            params["date_from"] = f.date_from
        if f.date_to:
            clauses.append("start_time <= %(date_to)s")
            params["date_to"] = f.date_to
        if f.alert_level_min:
            clauses.append("alert_level >= %(alert_level_min)s")
            params["alert_level_min"] = f.alert_level_min

        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        params["limit"] = f.limit
        params["offset"] = f.offset

        sql = f"""
            SELECT id::text, camera_id, event_type, start_time::text, end_time::text,
                   duration_seconds::float, alert_level, photo_path, acknowledged,
                   schema_version
            FROM events
            {where}
            ORDER BY start_time DESC
            LIMIT %(limit)s OFFSET %(offset)s
        """
        try:
            with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                return [dict(r) for r in cur.fetchall()]
        except Exception:
            LOG.exception("[ForensicDB] Error en búsqueda eventos postgres.")
            return []

    def _search_jsonl(self, f: SearchFilters) -> List[Dict[str, Any]]:
        """Búsqueda en JSONL — filtrado en memoria. Para uso en demo/dev."""
        if not self._jsonl_path.exists():
            LOG.debug("[ForensicDB] JSONL no encontrado: %s", self._jsonl_path)
            return []

        results: List[Dict] = []
        for record in _iter_jsonl(self._jsonl_path):
            if f.camera_id and record.get("camera_id") != f.camera_id:
                continue
            if f.object_class and f.object_class.lower() not in record.get("object_class", "").lower():
                continue
            if f.color_label and f.color_label.lower() not in record.get("color_label", "").lower():
                continue
            if f.date_from and record.get("timestamp", "") < f.date_from:
                continue
            if f.date_to and record.get("timestamp", "") > f.date_to:
                continue
            results.append(record)
            if len(results) >= f.limit + f.offset:
                break

        return results[f.offset: f.offset + f.limit]

    def _search_events_jsonl(self, f: SearchFilters) -> List[Dict[str, Any]]:
        """Busca en todos los archivos events_*.jsonl del directorio de outputs."""
        results: List[Dict] = []
        if not self._events_dir.exists():
            return results

        for path in sorted(self._events_dir.glob("events_*.jsonl"), reverse=True):
            for record in _iter_jsonl(path):
                if f.camera_id and record.get("camera_id") != f.camera_id:
                    continue
                if f.event_type and f.event_type.lower() not in record.get("event_type", "").lower():
                    continue
                if f.date_from:
                    ts = record.get("start_time") or record.get("timestamp", "")
                    if ts < f.date_from:
                        continue
                if f.date_to:
                    ts = record.get("start_time") or record.get("timestamp", "")
                    if ts > f.date_to:
                        continue
                if f.alert_level_min:
                    if int(record.get("alert_level", 1)) < f.alert_level_min:
                        continue
                results.append(record)
                if len(results) >= f.limit + f.offset:
                    break
            if len(results) >= f.limit + f.offset:
                break

        return results[f.offset: f.offset + f.limit]

    # ── Exportación CSV ───────────────────────────────────────────────────────

    def export_to_csv(self, filters: SearchFilters, output_path: str) -> str:
        """Exporta detecciones a CSV. Retorna el path del archivo generado."""
        records = self.search_detections(SearchFilters(
            camera_id=filters.camera_id,
            object_class=filters.object_class,
            color_label=filters.color_label,
            date_from=filters.date_from,
            date_to=filters.date_to,
            limit=10000,
        ))

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "timestamp", "camera_id", "object_class", "color_label",
            "confidence", "bbox_xmin", "bbox_ymin", "bbox_xmax", "bbox_ymax",
            "track_id", "frame_idx",
        ]
        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in records:
                row = {k: r.get(k) or r.get("bbox", {}).get(k.replace("bbox_", ""), "") for k in fieldnames}
                writer.writerow(row)

        LOG.info("[ForensicDB] CSV exportado: %s (%d filas)", out, len(records))
        return str(out)

    def export_to_csv_stream(self, filters: SearchFilters) -> str:
        """Retorna el contenido CSV como string (para FastAPI StreamingResponse)."""
        records = self.search_detections(filters)
        output = io.StringIO()
        fieldnames = [
            "timestamp", "camera_id", "object_class", "color_label",
            "confidence", "track_id", "frame_idx",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            writer.writerow({k: r.get(k, "") for k in fieldnames})
        return output.getvalue()

    # ── Estadísticas ──────────────────────────────────────────────────────────

    def get_summary_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas generales del sistema."""
        if self._mode == "postgres" and self._ensure_connected():
            return self._stats_postgres()
        return self._stats_jsonl()

    def _stats_postgres(self) -> Dict[str, Any]:
        try:
            with self._conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM detections")
                total_det = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM events")
                total_evt = cur.fetchone()[0]
                cur.execute("SELECT COUNT(DISTINCT camera_id) FROM detections")
                total_cams = cur.fetchone()[0]
                cur.execute("SELECT MAX(timestamp) FROM detections")
                last_ts = cur.fetchone()[0]
            return {
                "total_detections": total_det,
                "total_events": total_evt,
                "active_cameras": total_cams,
                "last_detection": str(last_ts) if last_ts else None,
                "mode": "postgres",
            }
        except Exception:
            LOG.exception("[ForensicDB] Error en stats postgres.")
            return {"mode": "postgres", "error": "query failed"}

    def _stats_jsonl(self) -> Dict[str, Any]:
        total = 0
        cameras: set = set()
        last_ts = ""
        if self._jsonl_path.exists():
            for r in _iter_jsonl(self._jsonl_path):
                total += 1
                cameras.add(r.get("camera_id", ""))
                ts = r.get("timestamp", "")
                if ts > last_ts:
                    last_ts = ts

        total_events = sum(
            1 for p in self._events_dir.glob("events_*.jsonl")
            for _ in _iter_jsonl(p)
        )
        return {
            "total_detections": total,
            "total_events": total_events,
            "active_cameras": len(cameras),
            "last_detection": last_ts or None,
            "mode": "jsonl",
        }

    # ── Cadena de custodia ────────────────────────────────────────────────────

    def log_audit_query(
        self,
        endpoint: str,
        query_params: Dict[str, Any],
        result_count: int,
        user_id: str = "anonymous",
        user_ip: str = "",
    ) -> None:
        """Registra una consulta en audit_queries (ISO 27001)."""
        if self._mode != "postgres" or not self._ensure_connected():
            return
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_queries
                        (user_id, user_ip, endpoint, query_params, result_count)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (user_id, user_ip, endpoint, json.dumps(query_params), result_count),
                )
            self._conn.commit()
        except Exception:
            LOG.exception("[ForensicDB] Error registrando audit_query.")
            try:
                self._conn.rollback()
            except Exception:
                pass

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def close(self) -> None:
        """Escribe buffer pendiente y cierra conexión."""
        flushed = self.flush()
        if flushed:
            LOG.info("[ForensicDB] Cerrado: %d detecciones adicionales escritas.", flushed)
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def __enter__(self) -> "ForensicDB":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


# ──────────────────────────────────────────────────────────────────────────────
# Utilidades privadas
# ──────────────────────────────────────────────────────────────────────────────

def _iter_jsonl(path: Path) -> Generator[Dict[str, Any], None, None]:
    """Itera líneas válidas de un archivo JSONL sin cargar todo en memoria."""
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        LOG.warning("[ForensicDB] No se pudo leer: %s", path)


def _file_hash(path: Optional[str]) -> Optional[str]:
    """Calcula SHA-256 de un archivo de evidencia (cadena de custodia)."""
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None
