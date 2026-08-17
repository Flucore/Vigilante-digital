"""Detector de vehículos con conteo y atributos de color — Vigilante Digital v2.0.

Detecta vehículos (auto, camión, moto, bus) y extrae:
  - Clase del vehículo (car / truck / motorcycle / bus)
  - Color dominante (white / black / gray / red / blue / green / yellow / etc.)
  - Tiempo de intersección con el polígono de entrada

Los VehicleEvent se pueden persistir en MetadataIndexer o ForensicDB para
ser consultados vía la UI forense: "camioneta blanca, últimas 48 h".

Compatibilidad con detector_factory:
    find_pose()     → (frame_anotado, lista_de_resultados)
    find_position() → ([], bbox_principal)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

LOG = logging.getLogger(__name__)

# Clases YOLO que se consideran vehículos
VEHICLE_CLASSES = {"car", "truck", "motorcycle", "bus"}

# Tabla de etiquetas de color por rango HSV
#  (nombre, h_min, h_max, s_min, v_min)
_COLOR_RANGES = [
    ("red",     0,  10, 80,  60),
    ("red",   170, 180, 80,  60),   # rojo envuelve 0°
    ("orange", 11,  22, 80,  60),
    ("yellow", 23,  35, 80,  60),
    ("green",  36,  85, 50,  40),
    ("cyan",   86, 100, 50,  40),
    ("blue",  101, 130, 50,  40),
    ("purple",131, 155, 40,  40),
    ("pink",  156, 169, 40,  60),
]


# ──────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class VehicleEvent:
    """Evento de vehículo al cruzar el polígono de entrada.

    Atributos:
        vehicle_class:    Clase YOLO (car / truck / motorcycle / bus).
        color_label:      Color dominante (white / black / gray / red / …).
        entry_time:       Unix timestamp de entrada al polígono.
        exit_time:        Unix timestamp de salida (None si aún dentro).
        duration_seconds: Segundos dentro del polígono (0 si aún activo).
        plate_roi:        Reservado para OCR de patente (None por ahora).
        bbox:             [xmin, ymin, xmax, ymax] del último frame.
        track_id:         ID interno del objeto.
        camera_id:        Identificador de la cámara fuente.
        confidence:       Confianza media de las detecciones.
    """
    vehicle_class:    str
    color_label:      str
    entry_time:       float
    exit_time:        Optional[float]
    duration_seconds: float
    plate_roi:        Optional[Any]
    bbox:             List[int]
    track_id:         int
    camera_id:        str   = "unknown"
    confidence:       float = 0.0


# ──────────────────────────────────────────────────────────────────────────────
# VehicleDetector
# ──────────────────────────────────────────────────────────────────────────────

class VehicleDetector:
    """Detecta y rastrea vehículos que intersectan con un polígono de entrada.

    Args:
        entry_polygon:       Lista de [x, y] (normalizados 0–1 o píxeles absolutos).
        min_intersection_sec: Segundos mínimos dentro del polígono para registrar
                              un VehicleEvent (filtro de falsos positivos).
        device:              "cuda" | "cpu" | "auto".
        camera_id:           Identificador de la cámara fuente.
        normalized:          True si el polígono está normalizado.

    Ejemplo::

        detector = VehicleDetector(entry_polygon=[[0.3,0.4],[0.7,0.4],[0.7,0.8],[0.3,0.8]])
        for frame in frames:
            events = detector.update(frame, detections, frame_ts=time.time())
    """

    def __init__(
        self,
        entry_polygon: List[List[float]],
        min_intersection_sec: float = 2.0,
        device: str = "auto",
        camera_id: str = "unknown",
        normalized: bool = True,
    ) -> None:
        self.entry_polygon       = entry_polygon
        self.min_intersection_sec = min_intersection_sec
        self.device              = device
        self.camera_id           = camera_id
        self.normalized          = normalized

        # track_id → estado activo
        self._active: Dict[int, _TrackState] = {}
        # Eventos cerrados listos para persistir
        self._completed: List[VehicleEvent]  = []
        self._frame_shape: Optional[Tuple[int, int]] = None

    # ── Interfaz pública ─────────────────────────────────────────────────────

    def update(
        self,
        frame: np.ndarray,
        detections: List[Dict[str, Any]],
        frame_ts: Optional[float] = None,
    ) -> List[VehicleEvent]:
        """Evalúa detecciones de vehículos en el frame actual.

        Args:
            frame:      Frame BGR (necesario para extracción de color).
            detections: Lista de dicts con:
                          "bbox"       [xmin, ymin, xmax, ymax],
                          "label"      str (clase YOLO),
                          "confidence" float,
                          "track_id"   int (opcional).
            frame_ts:   Timestamp del frame; si None usa time.time().

        Returns:
            Lista de VehicleEvent recién cerrados en este frame.
        """
        ts = frame_ts or time.time()
        self._frame_shape = frame.shape[:2]
        h, w = self._frame_shape
        contour = self._polygon_contour(w, h)

        # IDs vistos en este frame
        seen_ids: set = set()

        for det in detections:
            label = det.get("label", "")
            if label not in VEHICLE_CLASSES:
                continue

            bbox     = det.get("bbox", [0, 0, 0, 0])
            conf     = det.get("confidence", 0.0)
            track_id = det.get("track_id", id(det))  # ID externo o fallback único
            cx, cy   = (bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2

            inside = cv2.pointPolygonTest(contour, (float(cx), float(cy)), False) >= 0
            seen_ids.add(track_id)

            if inside:
                if track_id not in self._active:
                    crop_color = _dominant_color(frame, bbox)
                    self._active[track_id] = _TrackState(
                        vehicle_class = label,
                        color_label   = crop_color,
                        entry_time    = ts,
                        last_seen     = ts,
                        bbox          = bbox,
                        confidence    = conf,
                    )
                    LOG.debug("[VehicleDetector] entrada track=%d clase=%s color=%s", track_id, label, crop_color)
                else:
                    state             = self._active[track_id]
                    state.last_seen   = ts
                    state.bbox        = bbox
                    state.confidence  = (state.confidence + conf) / 2.0

        # Cerrar tracks que ya no se ven
        new_events: List[VehicleEvent] = []
        for tid in list(self._active.keys()):
            if tid not in seen_ids:
                state = self._active.pop(tid)
                duration = state.last_seen - state.entry_time
                if duration >= self.min_intersection_sec:
                    evt = VehicleEvent(
                        vehicle_class    = state.vehicle_class,
                        color_label      = state.color_label,
                        entry_time       = state.entry_time,
                        exit_time        = state.last_seen,
                        duration_seconds = round(duration, 2),
                        plate_roi        = None,
                        bbox             = state.bbox,
                        track_id         = tid,
                        camera_id        = self.camera_id,
                        confidence       = state.confidence,
                    )
                    new_events.append(evt)
                    self._completed.append(evt)
                    LOG.info(
                        "[VehicleDetector] VehicleEvent: %s %s %.1fs track=%d",
                        state.color_label, state.vehicle_class, duration, tid,
                    )

        return new_events

    def flush_completed(self) -> List[VehicleEvent]:
        """Retorna y limpia todos los VehicleEvents completados."""
        events, self._completed = self._completed, []
        return events

    def draw(
        self,
        frame: np.ndarray,
        show_polygon: bool = True,
    ) -> np.ndarray:
        """Dibuja el polígono de entrada y los tracks activos."""
        h, w = frame.shape[:2]
        if show_polygon:
            contour = self._polygon_contour(w, h)
            cv2.polylines(frame, [contour], True, (0, 200, 255), 2)
            cv2.fillPoly(frame.copy(), [contour], (0, 200, 255))

        for tid, state in self._active.items():
            b = state.bbox
            cv2.rectangle(frame, (b[0], b[1]), (b[2], b[3]), (0, 200, 255), 2)
            elapsed = time.time() - state.entry_time
            label   = f"{state.color_label} {state.vehicle_class} [{elapsed:.1f}s]"
            cv2.putText(
                frame, label, (b[0], max(b[1] - 6, 14)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 200, 255), 1, cv2.LINE_AA,
            )
        return frame

    # ── Compatibilidad detector_factory ──────────────────────────────────────

    def find_pose(
        self,
        img: np.ndarray,
        draw: bool = True,
    ) -> Tuple[np.ndarray, List]:
        if draw:
            img = self.draw(img)
        return img, []

    def find_position(
        self,
        img: np.ndarray,
        results: Any,
        draw: bool = True,
    ) -> Tuple[List, Dict]:
        return [], {}

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def close(self) -> None:
        self._active.clear()

    def __enter__(self) -> "VehicleDetector":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ── Utilidades privadas ───────────────────────────────────────────────────

    def _polygon_contour(self, w: int, h: int) -> np.ndarray:
        if self.normalized:
            pts = [[int(p[0] * w), int(p[1] * h)] for p in self.entry_polygon]
        else:
            pts = [[int(p[0]), int(p[1])] for p in self.entry_polygon]
        return np.array(pts, dtype=np.int32)


# ──────────────────────────────────────────────────────────────────────────────
# Estado interno de un track
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class _TrackState:
    vehicle_class: str
    color_label:   str
    entry_time:    float
    last_seen:     float
    bbox:          List[int]
    confidence:    float


# ──────────────────────────────────────────────────────────────────────────────
# Detección de color por histograma HSV
# ──────────────────────────────────────────────────────────────────────────────

def _dominant_color(frame: np.ndarray, bbox: List[int]) -> str:
    """Determina el color dominante del crop del vehículo usando histograma HSV.

    Returns:
        Etiqueta de color en inglés (white / black / gray / red / blue / …).
    """
    xmin, ymin, xmax, ymax = [max(0, v) for v in bbox]
    crop = frame[ymin:ymax, xmin:xmax]
    if crop.size == 0:
        return "unknown"

    hsv  = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    h_ch = hsv[:, :, 0].flatten()
    s_ch = hsv[:, :, 1].flatten()
    v_ch = hsv[:, :, 2].flatten()

    # Clasificar píxeles por brillo/saturación primero
    n_total  = len(v_ch)
    n_white  = np.sum((v_ch > 200) & (s_ch < 60))
    n_black  = np.sum(v_ch < 50)
    n_gray   = np.sum((s_ch < 45) & (v_ch >= 50) & (v_ch <= 200))

    if n_white / n_total > 0.40:
        return "white"
    if n_black / n_total > 0.35:
        return "black"
    if n_gray  / n_total > 0.45:
        return "gray"

    # Contar píxeles por rango de matiz
    color_counts: Dict[str, int] = {}
    for name, h_lo, h_hi, s_lo, v_lo in _COLOR_RANGES:
        mask  = (h_ch >= h_lo) & (h_ch <= h_hi) & (s_ch >= s_lo) & (v_ch >= v_lo)
        color_counts[name] = color_counts.get(name, 0) + int(np.sum(mask))

    if not color_counts:
        return "unknown"

    dominant = max(color_counts, key=lambda k: color_counts[k])
    ratio    = color_counts[dominant] / n_total
    return dominant if ratio > 0.10 else "mixed"
