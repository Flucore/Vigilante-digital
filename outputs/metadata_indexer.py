"""Indexador de metadatos de detección por frame — Vigilante Digital.

Por cada frame procesado extrae y persiste en JSONL:
    object_class · bbox · confidence · color_label · track_id · camera_id · timestamp

Escritura atómica (mkstemp + os.replace) para no corromper el archivo
si el proceso se interrumpe. Thread-safe.

Sprint 2: este JSONL será migrado a PostgreSQL/TimescaleDB y servirá como
base del Módulo de Auditoría Forense.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import cv2
import numpy as np

LOG = logging.getLogger(__name__)

# Umbral HSV para etiquetado de color dominante
_COLOR_LABELS: List[tuple] = [
    # (h_min, h_max, s_min, label)  — hue en [0, 180] escala OpenCV
    (0,   10,  60, "red"),
    (10,  22,  60, "orange"),
    (22,  38,  60, "yellow"),
    (38,  82,  60, "green"),
    (82, 128,  60, "blue"),
    (128, 155, 60, "purple"),
    (155, 180, 60, "red"),   # rojo alto
]


def _dominant_color_label(frame: np.ndarray, bbox: Dict[str, int]) -> str:
    """Retorna la etiqueta del color dominante del objeto recortado.

    Args:
        frame: Frame completo BGR.
        bbox: Diccionario con xmin, ymin, xmax, ymax.

    Returns:
        Etiqueta de color: "red" | "blue" | "white" | "black" | "gray" | etc.
    """
    try:
        x1 = max(0, int(bbox.get("xmin", 0)))
        y1 = max(0, int(bbox.get("ymin", 0)))
        x2 = min(frame.shape[1], int(bbox.get("xmax", frame.shape[1])))
        y2 = min(frame.shape[0], int(bbox.get("ymax", frame.shape[0])))

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return "unknown"

        # Reducir para velocidad
        small = cv2.resize(crop, (32, 32), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)

        h_mean = float(np.mean(hsv[:, :, 0]))
        s_mean = float(np.mean(hsv[:, :, 1]))
        v_mean = float(np.mean(hsv[:, :, 2]))

        # Acromático primero
        if s_mean < 40:
            if v_mean > 180:
                return "white"
            if v_mean < 60:
                return "black"
            return "gray"

        # Colores cromáticos
        for h_min, h_max, s_min, label in _COLOR_LABELS:
            if h_min <= h_mean <= h_max and s_mean >= s_min:
                return label

        return "mixed"
    except Exception:
        return "unknown"


class MetadataIndexer:
    """Indexa metadatos de detección por frame en JSONL atómico.

    Cada registro incluye:
        schema_version, frame_idx, timestamp, camera_id,
        object_class, confidence, color_label, track_id, bbox, metadata

    El parámetro ``index_every_n_frames`` permite reducir la carga de escritura:
    solo se indexan los frames cuyo índice es múltiplo del parámetro.
    Los frames con 0 detecciones no se indexan.

    Args:
        output_path: Ruta al archivo JSONL de salida.
        index_every_n_frames: Indexar 1 de cada N frames (default=5).
        schema_version: Versión del esquema para compatibilidad futura.

    Ejemplo::

        with MetadataIndexer("outputs/metadata.jsonl") as idx:
            idx.index_frame(
                frame_idx=42,
                timestamp="2026-05-12T18:00:00+00:00",
                camera_id="CAM_ENTRADA_AUTOS",
                detections=[{
                    "object_class": "car",
                    "confidence": 0.92,
                    "bbox": {"xmin": 100, "ymin": 200, "xmax": 400, "ymax": 500},
                    "track_id": 3,
                }],
                frame=frame_bgr,
            )
    """

    FLUSH_THRESHOLD = 50  # forzar escritura cada N records en buffer

    def __init__(
        self,
        output_path: Union[str, Path],
        index_every_n_frames: int = 5,
        schema_version: str = "2.0",
    ) -> None:
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_every_n_frames = max(1, index_every_n_frames)
        self.schema_version = schema_version

        self._lock = threading.Lock()
        self._buffer: List[Dict[str, Any]] = []
        self._total_indexed: int = 0

        LOG.info(
            "[MetadataIndexer] Inicializado: %s (cada %d frames)",
            self.output_path, self.index_every_n_frames,
        )

    # ── Indexación ────────────────────────────────────────────────────────────

    def index_frame(
        self,
        frame_idx: int,
        timestamp: str,
        camera_id: str,
        detections: List[Dict[str, Any]],
        frame: Optional[np.ndarray] = None,
    ) -> None:
        """Indexa las detecciones de un frame.

        Args:
            frame_idx: Índice del frame en la sesión (1-based).
            timestamp: ISO 8601 con timezone del frame.
            camera_id: ID de la cámara fuente.
            detections: Lista de detecciones. Cada dict debe incluir al menos
                        ``object_class`` y ``bbox`` (dict con xmin/ymin/xmax/ymax).
                        ``confidence``, ``track_id``, ``color_label`` son opcionales.
            frame: Frame BGR original (usado para calcular color_label si no viene
                   en la detección). Puede ser None.
        """
        if frame_idx % self.index_every_n_frames != 0:
            return

        if not detections:
            return

        records: List[Dict[str, Any]] = []
        for det in detections:
            bbox = det.get("bbox", {})
            if not isinstance(bbox, dict):
                bbox = {}

            # Calcular color_label si no viene y hay frame disponible
            color_label = det.get("color_label")
            if color_label is None and frame is not None and bbox:
                color_label = _dominant_color_label(frame, bbox)
            color_label = color_label or "unknown"

            records.append({
                "schema_version": self.schema_version,
                "frame_idx": frame_idx,
                "timestamp": timestamp,
                "camera_id": camera_id,
                "object_class": str(det.get("object_class", "unknown")),
                "confidence": round(float(det.get("confidence", 0.0)), 4),
                "color_label": color_label,
                "track_id": det.get("track_id"),
                "bbox": {
                    "xmin": int(bbox.get("xmin", 0)),
                    "ymin": int(bbox.get("ymin", 0)),
                    "xmax": int(bbox.get("xmax", 0)),
                    "ymax": int(bbox.get("ymax", 0)),
                },
                "metadata": det.get("metadata", {}),
            })

        with self._lock:
            self._buffer.extend(records)
            self._total_indexed += len(records)
            if len(self._buffer) >= self.FLUSH_THRESHOLD:
                self._flush_locked()

    # ── Escritura atómica ─────────────────────────────────────────────────────

    def flush(self) -> int:
        """Fuerza la escritura del buffer pendiente al disco.

        Returns:
            Cantidad de registros escritos en esta llamada.
        """
        with self._lock:
            return self._flush_locked()

    def _flush_locked(self) -> int:
        """Escribe el buffer al JSONL de forma atómica. Requiere el lock."""
        if not self._buffer:
            return 0

        count = len(self._buffer)
        new_lines = "\n".join(
            json.dumps(r, ensure_ascii=False) for r in self._buffer
        ) + "\n"
        self._buffer.clear()

        dir_ = self.output_path.parent
        fd, tmp_path = -1, ""
        try:
            fd, tmp_path = tempfile.mkstemp(dir=str(dir_), suffix=".jsonl.tmp")
            # Preservar contenido existente + agregar nuevas líneas
            existing = b""
            if self.output_path.exists():
                existing = self.output_path.read_bytes()
            with os.fdopen(fd, "wb") as fh:
                fh.write(existing)
                fh.write(new_lines.encode("utf-8"))
            fd = -1  # ya cerrado por fdopen
            os.replace(tmp_path, str(self.output_path))
            tmp_path = ""
        except Exception:
            LOG.exception("[MetadataIndexer] Error escribiendo JSONL")
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            return 0

        return count

    # ── Estadísticas ──────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas del indexador en esta sesión."""
        line_count = 0
        if self.output_path.exists():
            try:
                with self.output_path.open("r", encoding="utf-8") as f:
                    line_count = sum(1 for ln in f if ln.strip())
            except Exception:
                pass

        return {
            "output_path": str(self.output_path),
            "records_on_disk": line_count,
            "records_in_buffer": len(self._buffer),
            "total_indexed_session": self._total_indexed,
            "index_every_n_frames": self.index_every_n_frames,
        }

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def close(self) -> None:
        """Escribe cualquier registro pendiente y libera recursos."""
        flushed = self.flush()
        if flushed > 0:
            LOG.info(
                "[MetadataIndexer] Cerrado: %d registros adicionales guardados. "
                "Total sesión: %d",
                flushed, self._total_indexed,
            )
        else:
            LOG.debug(
                "[MetadataIndexer] Cerrado. Total sesión: %d registros.",
                self._total_indexed,
            )

    def __enter__(self) -> "MetadataIndexer":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"MetadataIndexer('{self.output_path.name}', "
            f"indexed={self._total_indexed}, "
            f"buffer={len(self._buffer)})"
        )
