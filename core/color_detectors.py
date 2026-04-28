"""Detectores visuales basados en color para maqueta funcional.

Estos detectores son deliberadamente simples y explicables para demo:
- RedShirtDetector: detecta una prenda roja persistente por N segundos.
- TrafficLightDetector: detecta cambios de color tipo semáforo en una ROI.

No reemplazan un modelo entrenado. Sirven como módulos rápidos para probar
triggers, reportes y flujos de evento antes de entrenar modelos específicos.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

LOG = logging.getLogger(__name__)

Point = Tuple[int, int]
ROI = Tuple[int, int, int, int]


@dataclass
class ColorDetection:
    """Resultado estándar de una detección basada en color."""

    detected: bool
    confidence: float
    event: Optional[Dict]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_roi(frame: np.ndarray, roi: Optional[ROI]) -> Tuple[np.ndarray, ROI]:
    """Retorna subframe y ROI válida dentro de límites del frame."""
    h, w = frame.shape[:2]
    if roi is None:
        return frame, (0, 0, w, h)

    x, y, rw, rh = roi
    x = max(0, min(w - 1, int(x)))
    y = max(0, min(h - 1, int(y)))
    rw = max(1, min(w - x, int(rw)))
    rh = max(1, min(h - y, int(rh)))
    return frame[y : y + rh, x : x + rw], (x, y, rw, rh)


def _red_mask_hsv(frame: np.ndarray) -> np.ndarray:
    """Crea máscara HSV para rojo, cubriendo ambos extremos del hue."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower1 = np.array([0, 80, 50], dtype=np.uint8)
    upper1 = np.array([10, 255, 255], dtype=np.uint8)
    lower2 = np.array([170, 80, 50], dtype=np.uint8)
    upper2 = np.array([180, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower1, upper1) | cv2.inRange(hsv, lower2, upper2)
    kernel = np.ones((5, 5), np.uint8)
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)


class RedShirtDetector:
    """Detecta ingreso/presencia de persona con polera roja por tiempo mínimo.

    Para la maqueta se usa segmentación HSV de rojo en una región opcional.
    La detección dispara evento solo si el área roja supera `min_area_ratio`
    durante `min_presence_sec`.
    """

    def __init__(
        self,
        min_presence_sec: float = 1.0,
        min_area_ratio: float = 0.025,
        cooldown_sec: float = 5.0,
        roi: Optional[ROI] = None,
    ) -> None:
        self.min_presence_sec = float(min_presence_sec)
        self.min_area_ratio = float(min_area_ratio)
        self.cooldown_sec = float(cooldown_sec)
        self.roi = roi
        self._first_seen_at: Optional[float] = None
        self._last_event_at: float = 0.0

    def update(self, frame: np.ndarray, camera_id: str = "", zone: str = "") -> ColorDetection:
        """Procesa frame y retorna evento si la polera roja persiste."""
        roi_frame, roi = _parse_roi(frame, self.roi)
        mask = _red_mask_hsv(roi_frame)
        red_pixels = int(cv2.countNonZero(mask))
        total_pixels = max(1, mask.shape[0] * mask.shape[1])
        ratio = red_pixels / total_pixels

        now = time.time()
        visible = ratio >= self.min_area_ratio
        if visible and self._first_seen_at is None:
            self._first_seen_at = now
        elif not visible:
            self._first_seen_at = None

        duration = (now - self._first_seen_at) if self._first_seen_at else 0.0
        ready = visible and duration >= self.min_presence_sec
        cooling_down = now - self._last_event_at < self.cooldown_sec

        event = None
        if ready and not cooling_down:
            self._last_event_at = now
            event = {
                "event_type": "red_shirt_entry",
                "timestamp": _iso_now(),
                "camera_id": camera_id,
                "zone": zone,
                "duration_seconds": round(duration, 3),
                "metadata": {
                    "red_area_ratio": round(ratio, 5),
                    "roi": roi,
                    "min_presence_sec": self.min_presence_sec,
                },
            }
            LOG.warning("[RED_SHIRT] Evento confirmado camera=%s ratio=%.4f", camera_id, ratio)

        return ColorDetection(detected=visible, confidence=min(1.0, ratio / self.min_area_ratio), event=event)

    def draw(self, frame: np.ndarray, result: ColorDetection) -> np.ndarray:
        """Dibuja ROI y estado sobre el frame."""
        _, roi = _parse_roi(frame, self.roi)
        x, y, w, h = roi
        color = (0, 0, 255) if result.detected else (80, 80, 80)
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        label = "POLERA ROJA" if result.detected else "ROI ROJO"
        cv2.putText(frame, label, (x + 8, max(20, y + 24)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        return frame


class TrafficLightDetector:
    """Lee cambios de color en una luz/semaforo dentro de una ROI.

    Clasifica el color dominante entre rojo, amarillo y verde. Dispara evento
    cuando el color confirmado cambia y se mantiene por `min_stable_sec`.
    """

    COLOR_RANGES = {
        "red": [
            (np.array([0, 80, 80], dtype=np.uint8), np.array([10, 255, 255], dtype=np.uint8)),
            (np.array([170, 80, 80], dtype=np.uint8), np.array([180, 255, 255], dtype=np.uint8)),
        ],
        "yellow": [
            (np.array([18, 80, 80], dtype=np.uint8), np.array([38, 255, 255], dtype=np.uint8)),
        ],
        "green": [
            (np.array([40, 60, 60], dtype=np.uint8), np.array([90, 255, 255], dtype=np.uint8)),
        ],
    }

    def __init__(
        self,
        roi: Optional[ROI] = None,
        min_stable_sec: float = 0.4,
        min_color_ratio: float = 0.015,
    ) -> None:
        self.roi = roi
        self.min_stable_sec = float(min_stable_sec)
        self.min_color_ratio = float(min_color_ratio)
        self._candidate_color: Optional[str] = None
        self._candidate_since: Optional[float] = None
        self._confirmed_color: Optional[str] = None

    def update(self, frame: np.ndarray, camera_id: str = "", zone: str = "") -> ColorDetection:
        """Procesa frame y retorna evento al confirmar cambio de color."""
        roi_frame, roi = _parse_roi(frame, self.roi)
        hsv = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2HSV)
        total_pixels = max(1, hsv.shape[0] * hsv.shape[1])

        scores: Dict[str, float] = {}
        for color_name, ranges in self.COLOR_RANGES.items():
            mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
            for lower, upper in ranges:
                mask |= cv2.inRange(hsv, lower, upper)
            scores[color_name] = cv2.countNonZero(mask) / total_pixels

        dominant = max(scores, key=scores.get)
        ratio = scores[dominant]
        if ratio < self.min_color_ratio:
            return ColorDetection(detected=False, confidence=0.0, event=None)

        now = time.time()
        if dominant != self._candidate_color:
            self._candidate_color = dominant
            self._candidate_since = now
            return ColorDetection(detected=True, confidence=ratio, event=None)

        stable_for = now - (self._candidate_since or now)
        event = None
        if stable_for >= self.min_stable_sec and dominant != self._confirmed_color:
            previous = self._confirmed_color
            self._confirmed_color = dominant
            event = {
                "event_type": "traffic_light_change",
                "timestamp": _iso_now(),
                "camera_id": camera_id,
                "zone": zone,
                "metadata": {
                    "previous_color": previous,
                    "current_color": dominant,
                    "confidence": round(ratio, 5),
                    "roi": roi,
                    "stable_for_sec": round(stable_for, 3),
                    "scores": {k: round(v, 5) for k, v in scores.items()},
                },
            }
            LOG.warning("[TRAFFIC_LIGHT] Cambio %s -> %s camera=%s", previous, dominant, camera_id)

        return ColorDetection(detected=True, confidence=ratio, event=event)

    def draw(self, frame: np.ndarray, result: ColorDetection) -> np.ndarray:
        """Dibuja ROI y color confirmado/candidato sobre el frame."""
        _, roi = _parse_roi(frame, self.roi)
        x, y, w, h = roi
        label_color = self._confirmed_color or self._candidate_color or "unknown"
        bgr = {
            "red": (0, 0, 255),
            "yellow": (0, 255, 255),
            "green": (0, 255, 0),
            "unknown": (80, 80, 80),
        }.get(label_color, (80, 80, 80))
        cv2.rectangle(frame, (x, y), (x + w, y + h), bgr, 2)
        cv2.putText(frame, f"LUZ: {label_color.upper()}", (x + 8, max(20, y + 24)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, bgr, 2)
        return frame
