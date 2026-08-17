"""Detector de intrusión con polígonos de zona — Vigilante Digital v2.0.

Detecta cuando un objeto (persona, vehículo, etc.) entra o sale de una zona
definida como polígono. Incluye tracking mínimo por distancia de centroide
cuando DeepSORT no está disponible.

Flujo típico:
    1. Construir zonas desde client_config.json → ZoneConfig
    2. Por cada frame, llamar update(detections, track_ids, frame_idx)
    3. Si retorna IntrusionEvent, pasar a EventLogger / TriggerManager

Compatibilidad con detector_factory:
    find_pose()     → (frame, [])
    find_position() → ([], {})
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

LOG = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ZoneConfig:
    """Define una zona de monitoreo como polígono.

    Atributos:
        id:       Identificador único de la zona (ej: "zone_patio_1").
        label:    Nombre legible (ej: "Patio Trasero").
        points:   Lista de [x, y] relativas a la imagen (0–1 normalizados
                  o píxeles absolutos; se normaliza al primer frame).
        critical: Si True, activa bocina cuando is_after_hours==True.
        classes:  Clases YOLO que disparan esta zona ("" = todas).
        normalized: True si points están en [0, 1]; False si son píxeles.
    """
    id:         str
    label:      str
    points:     List[List[float]]
    critical:   bool               = False
    classes:    List[str]          = field(default_factory=list)
    normalized: bool               = True

    def to_pixel_contour(
        self, width: int, height: int
    ) -> np.ndarray:
        """Convierte los puntos a píxeles absolutos como contorno cv2."""
        if self.normalized:
            pts = [[int(p[0] * width), int(p[1] * height)] for p in self.points]
        else:
            pts = [[int(p[0]), int(p[1])] for p in self.points]
        return np.array(pts, dtype=np.int32)


@dataclass
class IntrusionEvent:
    """Evento generado cuando un objeto cruza una zona.

    Atributos:
        zone_id:    ID de la zona afectada.
        track_id:   ID del objeto detectado.
        label:      Clase del objeto (ej: "person").
        timestamp:  Unix timestamp del evento.
        direction:  "in" o "out".
        confidence: Confianza de la detección original.
        centroid:   (x, y) píxeles del centroide.
        bbox:       [xmin, ymin, xmax, ymax].
        is_critical: True si la zona es crítica.
    """
    zone_id:     str
    track_id:    int
    label:       str
    timestamp:   float
    direction:   str               # "in" | "out"
    confidence:  float
    centroid:    Tuple[int, int]
    bbox:        List[int]
    is_critical: bool              = False


# ──────────────────────────────────────────────────────────────────────────────
# Tracker mínimo por distancia de centroide
# ──────────────────────────────────────────────────────────────────────────────

class _CentroidTracker:
    """Asigna track_id simples por distancia euclidiana entre frames."""

    def __init__(
        self,
        max_distance: float = 80.0,
        max_lost_frames: int = 15,
    ) -> None:
        self._next_id  = 0
        self._tracks:  Dict[int, Tuple[int, int]] = {}   # id → último centroide
        self._lost:    Dict[int, int]             = {}   # id → frames sin ver
        self._max_dist = max_distance
        self._max_lost = max_lost_frames

    def update(
        self,
        centroids: List[Tuple[int, int]],
    ) -> List[int]:
        """Actualiza el tracker con los centroides del frame actual.

        Returns:
            Lista de track_ids con el mismo orden que `centroids`.
        """
        if not centroids:
            for tid in list(self._tracks):
                self._lost[tid] = self._lost.get(tid, 0) + 1
                if self._lost[tid] > self._max_lost:
                    del self._tracks[tid]
                    del self._lost[tid]
            return []

        if not self._tracks:
            ids = []
            for c in centroids:
                ids.append(self._next_id)
                self._tracks[self._next_id] = c
                self._next_id += 1
            return ids

        track_ids  = list(self._tracks.keys())
        track_pts  = list(self._tracks.values())
        assigned   = set()
        result_ids: List[Optional[int]] = [None] * len(centroids)

        for i, c in enumerate(centroids):
            dists = [
                np.hypot(c[0] - t[0], c[1] - t[1]) for t in track_pts
            ]
            min_j = int(np.argmin(dists))
            if dists[min_j] < self._max_dist and min_j not in assigned:
                result_ids[i] = track_ids[min_j]
                self._tracks[track_ids[min_j]] = c
                self._lost.pop(track_ids[min_j], None)
                assigned.add(min_j)

        for i, c in enumerate(centroids):
            if result_ids[i] is None:
                result_ids[i] = self._next_id
                self._tracks[self._next_id] = c
                self._next_id += 1

        for j, tid in enumerate(track_ids):
            if j not in assigned:
                self._lost[tid] = self._lost.get(tid, 0) + 1
                if self._lost[tid] > self._max_lost:
                    del self._tracks[tid]
                    self._lost.pop(tid, None)

        return [tid for tid in result_ids]  # type: ignore[return-value]


# ──────────────────────────────────────────────────────────────────────────────
# IntrusionDetector
# ──────────────────────────────────────────────────────────────────────────────

class IntrusionDetector:
    """Detecta intrusión en polígonos usando detecciones de YOLO.

    Args:
        zones:        Lista de ZoneConfig.
        cooldown_sec: Tiempo mínimo en segundos entre eventos del mismo
                      objeto en la misma zona.

    Ejemplo::

        zones = [ZoneConfig(id="z1", label="Patio", points=[[0.1,0.1],[0.9,0.1],[0.9,0.9],[0.1,0.9]])]
        detector = IntrusionDetector(zones=zones)
        events = detector.update(detections=bboxes, track_ids=ids, frame_idx=n, frame=frame)
    """

    def __init__(
        self,
        zones: List[ZoneConfig],
        cooldown_sec: float = 5.0,
    ) -> None:
        self.zones        = zones
        self.cooldown_sec = cooldown_sec
        self._tracker     = _CentroidTracker()
        # (track_id, zone_id) → last event timestamp
        self._last_event: Dict[Tuple[int, str], float] = {}
        # (track_id, zone_id) → was inside in previous frame
        self._was_inside: Dict[Tuple[int, str], bool]  = {}
        self._frame_shape: Optional[Tuple[int, int]] = None

    # ── Interfaz pública ─────────────────────────────────────────────────────

    def update(
        self,
        detections: List[Dict[str, Any]],
        track_ids: Optional[List[int]] = None,
        frame_idx: int = 0,
        frame: Optional[np.ndarray] = None,
    ) -> List[IntrusionEvent]:
        """Evalúa si alguna detección viola una zona definida.

        Args:
            detections: Lista de dicts con claves:
                          "bbox" [xmin,ymin,xmax,ymax],
                          "label" str,
                          "confidence" float.
            track_ids:  IDs de tracking externos (ej: ByteTrack).
                        Si None, el tracker interno asigna IDs.
            frame_idx:  Número del frame actual.
            frame:      Frame BGR para determinar dimensiones de zona.

        Returns:
            Lista (posiblemente vacía) de IntrusionEvent.
        """
        if not detections:
            return []

        if frame is not None:
            self._frame_shape = frame.shape[:2]

        h, w = self._frame_shape or (1080, 1920)

        # Centroides de las detecciones
        centroids = [
            _centroid(d["bbox"]) for d in detections if "bbox" in d
        ]

        # Obtener/asignar track IDs
        if track_ids is None or len(track_ids) != len(centroids):
            track_ids = self._tracker.update(centroids)

        events: List[IntrusionEvent] = []
        now = time.time()

        for det, c, tid in zip(detections, centroids, track_ids):
            if tid is None:
                continue
            bbox  = det.get("bbox", [0, 0, 0, 0])
            label = det.get("label", "unknown")
            conf  = det.get("confidence", 0.0)

            for zone in self.zones:
                # Filtrar por clases si la zona las especifica
                if zone.classes and label not in zone.classes:
                    continue

                contour = zone.to_pixel_contour(w, h)
                inside  = cv2.pointPolygonTest(contour, (float(c[0]), float(c[1])), False) >= 0

                key        = (tid, zone.id)
                was_inside = self._was_inside.get(key, False)
                self._was_inside[key] = inside

                # Solo emitir cuando cambia el estado Y se respeta cooldown
                if inside != was_inside:
                    last = self._last_event.get(key, 0.0)
                    if now - last >= self.cooldown_sec:
                        self._last_event[key] = now
                        direction = "in" if inside else "out"
                        events.append(IntrusionEvent(
                            zone_id     = zone.id,
                            track_id    = tid,
                            label       = label,
                            timestamp   = now,
                            direction   = direction,
                            confidence  = conf,
                            centroid    = c,
                            bbox        = bbox,
                            is_critical = zone.critical,
                        ))
                        LOG.info(
                            "[IntrusionDetector] %s track=%d zone=%s dir=%s",
                            label, tid, zone.id, direction,
                        )

        return events

    def draw_zones(
        self,
        frame: np.ndarray,
        color: Tuple[int, int, int] = (0, 255, 120),
        thickness: int = 2,
        alpha: float = 0.15,
    ) -> np.ndarray:
        """Dibuja todos los polígonos de zona sobre el frame.

        Args:
            frame:     Frame BGR.
            color:     Color de la línea del polígono.
            thickness: Grosor de línea.
            alpha:     Transparencia del relleno.

        Returns:
            Frame anotado.
        """
        h, w = frame.shape[:2]
        overlay = frame.copy()
        for zone in self.zones:
            pts     = zone.to_pixel_contour(w, h)
            fill_c  = (0, 60, 200) if zone.critical else color
            cv2.fillPoly(overlay, [pts], fill_c)
            cv2.polylines(frame, [pts], True, fill_c, thickness)
            # Etiqueta de la zona
            cx, cy = pts.mean(axis=0).astype(int)
            cv2.putText(
                frame, zone.label,
                (cx - 30, cy),
                cv2.FONT_HERSHEY_SIMPLEX, 0.50,
                fill_c, 1, cv2.LINE_AA,
            )
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame

    # ── Compatibilidad detector_factory ──────────────────────────────────────

    def find_pose(
        self,
        img: np.ndarray,
        draw: bool = True,
    ) -> Tuple[np.ndarray, List]:
        """Dibuja zonas en el frame; no ejecuta inferencia propia."""
        if draw:
            img = self.draw_zones(img)
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
        self._last_event.clear()
        self._was_inside.clear()

    def __enter__(self) -> "IntrusionDetector":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


# ──────────────────────────────────────────────────────────────────────────────
# Utilidades privadas
# ──────────────────────────────────────────────────────────────────────────────

def _centroid(bbox: List[int]) -> Tuple[int, int]:
    return (
        (bbox[0] + bbox[2]) // 2,
        (bbox[1] + bbox[3]) // 2,
    )
