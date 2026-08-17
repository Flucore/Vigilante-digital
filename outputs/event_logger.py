"""Event-based logger para caídas (detección de inicio/fin).

Reemplaza el logging frame-a-frame con un sistema basado en eventos.
Reduce >99% de registros (miles de frames → 1–2 eventos por episodio).
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

EVENT_SCHEMA_VERSION = "2.0"
DEFAULT_RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "30"))


def resolve_is_falling(
    bbox: Dict[str, Any],
    *,
    ratio_threshold: float = 0.75,
) -> Tuple[bool, str]:
    """Decide caída priorizando la señal del detector.

    Si el bbox trae ``is_falling`` (p. ej. YoloFallDetector), se usa tal cual.
    Solo si falta esa clave se aplica el fallback de aspect-ratio (MediaPipe legacy).
    """
    if "is_falling" in bbox and bbox.get("is_falling") is not None:
        return bool(bbox["is_falling"]), "detector"

    width = bbox.get("width")
    height = bbox.get("height")
    if width is None or height is None:
        xmin = int(bbox.get("xmin", 0))
        ymin = int(bbox.get("ymin", 0))
        xmax = int(bbox.get("xmax", 0))
        ymax = int(bbox.get("ymax", 0))
        width = max(1, xmax - xmin)
        height = max(0, ymax - ymin)
    ratio = float(height) / max(1.0, float(width))
    return ratio < ratio_threshold, "aspect_ratio_fallback"


def enrich_canonical_event(
    event: Dict[str, Any],
    *,
    camera_id: str = "",
    zone: str = "",
    sector: str = "",
    alert_level: int = 2,
    photo_path: Optional[str] = None,
    retention_days: Optional[int] = None,
) -> Dict[str, Any]:
    """Completa campos canónicos event_schema_version 2.0 sin borrar metadata existente."""
    out = dict(event)
    ts = out.get("timestamp") or out.get("end_time") or out.get("start_time")
    if not ts:
        ts = datetime.now(timezone.utc).isoformat()
    out["event_schema_version"] = out.get("event_schema_version") or EVENT_SCHEMA_VERSION
    out["timestamp"] = ts
    if camera_id:
        out["camera_id"] = camera_id
    elif "camera_id" not in out:
        out["camera_id"] = "unknown"
    if zone:
        out["zone"] = zone
    if sector:
        out["sector"] = sector
    out.setdefault("alert_level", int(alert_level))
    if photo_path:
        out["photo_path"] = photo_path
    elif "photo_path" not in out and out.get("photo_start"):
        out["photo_path"] = out.get("photo_start")
    retention = retention_days if retention_days is not None else DEFAULT_RETENTION_DAYS
    compliance = dict(out.get("compliance") or {})
    compliance.setdefault("retention_days", retention)
    compliance.setdefault("consent_basis", "security_monitoring")
    out["compliance"] = compliance
    out.setdefault("pdf_path", None)
    return out


def _build_fall_episode(
    *,
    start_time: datetime,
    end_time: datetime,
    start_frame: Optional[int],
    end_frame: Optional[int],
    photo_start: Optional[str],
    metadata: Optional[Dict[str, Any]],
    finalized_forced: bool = False,
) -> Dict[str, Any]:
    duration = (end_time - start_time).total_seconds()
    total_frames = None
    if start_frame is not None and end_frame is not None:
        total_frames = max(0, end_frame - start_frame)
    event: Dict[str, Any] = {
        "event_type": "fall",
        "event_schema_version": EVENT_SCHEMA_VERSION,
        "timestamp": end_time.isoformat(),
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": duration,
        "start_frame": start_frame,
        "end_frame": end_frame,
        "total_frames": total_frames,
        "photo_start": photo_start,
        "photo_path": photo_start,
        "metadata": metadata or {},
        "compliance": {
            "retention_days": DEFAULT_RETENTION_DAYS,
            "consent_basis": "security_monitoring",
        },
        "pdf_path": None,
    }
    if finalized_forced:
        event["finalized_forced"] = True
    return event


class EventLogger:
    """Registra eventos de caída (inicio/fin) en lugar de frames individuales.

    Máquina de estados:
    - NORMAL: sin detección de caída
    - FALLING: caída en progreso

    Cuando transiciona de FALLING → NORMAL, emite un evento completado.
    """

    def __init__(self, file_path: Optional[Union[str, Path]] = None) -> None:
        env_path = os.getenv("EVENT_LOG_PATH")
        self.path: Path = Path(file_path or env_path or "events_log.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()

        self.state: str = "NORMAL"
        self.fall_start_time: Optional[datetime] = None
        self.fall_start_frame: Optional[int] = None
        self.fall_photo_path: Optional[str] = None
        self.fall_metadata: Optional[Dict[str, Any]] = None

    def update(
        self,
        is_falling: bool,
        frame_idx: int,
        photo_path: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Actualiza el estado y retorna un evento canónico si FALLING → NORMAL."""
        with self._lock:
            now = datetime.now(timezone.utc)
            completed_event = None

            if is_falling and self.state == "NORMAL":
                self.state = "FALLING"
                self.fall_start_time = now
                self.fall_start_frame = frame_idx
                self.fall_photo_path = photo_path or None
                self.fall_metadata = dict(metadata or {})
                logger.info("[FALL_DETECTED] Caída iniciada en frame %s", frame_idx)

            elif not is_falling and self.state == "FALLING":
                if self.fall_start_time is not None:
                    completed_event = _build_fall_episode(
                        start_time=self.fall_start_time,
                        end_time=now,
                        start_frame=self.fall_start_frame,
                        end_frame=frame_idx - 1,
                        photo_start=self.fall_photo_path,
                        metadata=self.fall_metadata,
                    )
                    logger.info(
                        "[FALL_ENDED] Caída finalizada. Duración: %.2fs",
                        completed_event["duration_seconds"],
                    )

                self.state = "NORMAL"
                self.fall_start_time = None
                self.fall_start_frame = None
                self.fall_photo_path = None
                self.fall_metadata = None

            return completed_event

    def log_event(self, event: Dict[str, Any]) -> bool:
        """Guarda un evento completado como una línea JSONL."""
        try:
            with self._lock:
                self._append_event(event)
            return True
        except Exception as exc:
            logger.exception("Error guardando evento: %s", exc)
            return False

    def _read_history(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []

        try:
            with self.path.open("r", encoding="utf-8") as fh:
                first = fh.read(1)
                fh.seek(0)
                if first == "[":
                    data = json.load(fh)
                    return data if isinstance(data, list) else []
                return list(_iter_jsonl(fh, self.path))
        except Exception:
            logger.exception("Error leyendo %s", self.path)
            return []

    def _append_event(self, event: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def _write_history(self, history: List[Dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=str(self.path.parent))
        os.close(fd)
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                for event in history:
                    fh.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, str(self.path))
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def get_events(self) -> List[Dict[str, Any]]:
        return self._read_history()

    def clear(self) -> None:
        with self._lock:
            self._write_history([])

    def finalize(self) -> Optional[Dict[str, Any]]:
        """Fuerza cierre de un evento en progreso (p. ej. fin de archivo)."""
        with self._lock:
            if self.state != "FALLING":
                return None

            now = datetime.now(timezone.utc)
            if self.fall_start_time is None:
                self.state = "NORMAL"
                return None

            event = _build_fall_episode(
                start_time=self.fall_start_time,
                end_time=now,
                start_frame=self.fall_start_frame,
                end_frame=None,
                photo_start=self.fall_photo_path,
                metadata=self.fall_metadata,
                finalized_forced=True,
            )

            self.state = "NORMAL"
            self.fall_start_time = None
            self.fall_start_frame = None
            self.fall_photo_path = None
            self.fall_metadata = None

            logger.info(
                "[FALL_FINALIZE] Evento finalizado forzadamente. Duración: %.2fs",
                event["duration_seconds"],
            )
            return event


def _iter_jsonl(lines: Iterable[str], path: Path) -> Iterable[Dict[str, Any]]:
    for line_no, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Línea JSONL inválida en %s:%d; se omite", path, line_no)
            continue
        if isinstance(item, dict):
            yield item
