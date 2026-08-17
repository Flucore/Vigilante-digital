"""Detector de cruce de perímetro virtual.

Dibuja una línea virtual configurable sobre el frame y detecta cuando
una persona (bounding box) cruza de un lado al otro.

Uso en demo:
    detector = PerimeterDetector(line_start=(100, 400), line_end=(1180, 400),
                                  label="Línea de Seguridad")
    event = detector.update(bbox, track_id=track_id)
    if event:
        print("INTRUSIÓN DETECTADA")
    detector.draw(frame)
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Colores
_COLOR_LINE_NORMAL = (0, 165, 255)   # Naranja
_COLOR_LINE_ALERT  = (0, 0, 255)     # Rojo
_COLOR_TEXT        = (255, 255, 255)


class PerimeterDetector:
    """Detecta cruce de una línea virtual configurable.

    Usa el signo del producto cruzado para determinar de qué lado de la línea
    está el centroide de la persona, y dispara un evento al cambiar de lado.

    Atributos:
        line_start: Punto inicial de la línea (x, y) en píxeles.
        line_end:   Punto final de la línea (x, y) en píxeles.
        label:      Texto mostrado sobre la línea en el frame.
        cooldown_sec: Segundos mínimos entre alertas del mismo track_id.
    """

    def __init__(
        self,
        line_start: Tuple[int, int],
        line_end: Tuple[int, int],
        label: str = "Perímetro",
        cooldown_sec: float = 3.0,
    ) -> None:
        self.line_start = tuple(line_start)
        self.line_end = tuple(line_end)
        self.label = label
        self.cooldown_sec = cooldown_sec

        self._last_side: Dict[int, int] = {}
        self._last_alert: Dict[int, float] = {}
        self._alert_active: bool = False

    # ------------------------------------------------------------------
    # Detección
    # ------------------------------------------------------------------

    def update(
        self,
        bbox: Dict[str, int],
        track_id: int = 0,
    ) -> Optional[Dict]:
        """Evalúa si el centroide del bbox cruzó la línea.

        Args:
            bbox: Dict con xmin, ymin, xmax, ymax (formato de find_position).
            track_id: ID de tracking de la persona.

        Returns:
            Dict con datos del evento si hubo cruce, None si no.
        """
        if not bbox:
            return None

        cx = (bbox.get("xmin", 0) + bbox.get("xmax", 0)) // 2
        cy = (bbox.get("ymin", 0) + bbox.get("ymax", 0)) // 2

        current_side = self._get_side(cx, cy)
        last_side = self._last_side.get(track_id)
        self._last_side[track_id] = current_side

        if last_side is None or last_side == current_side:
            return None

        # Verificar cooldown
        last_time = self._last_alert.get(track_id, 0.0)
        now = time.time()
        if now - last_time < self.cooldown_sec:
            return None

        self._last_alert[track_id] = now
        self._alert_active = True

        event = {
            "event_type": "perimeter_breach",
            "event_schema_version": "2.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": 0.0,
            "metadata": {
                "track_id": track_id,
                "line_label": self.label,
                "centroid": (cx, cy),
                "from_side": last_side,
                "to_side": current_side,
            },
            # Compat campos legacy leídos por demos antiguos
            "track_id": track_id,
            "line_label": self.label,
            "centroid": (cx, cy),
            "from_side": last_side,
            "to_side": current_side,
        }
        logger.warning("[PERIMETER] Cruce detectado — track_id=%d", track_id)
        return event

    def reset_alert(self) -> None:
        """Resetea el estado visual de alerta."""
        self._alert_active = False

    # ------------------------------------------------------------------
    # Visualización
    # ------------------------------------------------------------------

    def draw(self, frame: np.ndarray) -> np.ndarray:
        """Dibuja la línea de perímetro sobre el frame."""
        color = _COLOR_LINE_ALERT if self._alert_active else _COLOR_LINE_NORMAL
        thickness = 3 if self._alert_active else 2

        cv2.line(frame, self.line_start, self.line_end, color, thickness)

        # Etiqueta centrada sobre la línea
        mid_x = (self.line_start[0] + self.line_end[0]) // 2
        mid_y = (self.line_start[1] + self.line_end[1]) // 2
        text = f"[{self.label}]" if not self._alert_active else f"[{self.label} - ALERTA]"
        cv2.putText(frame, text, (mid_x - 80, mid_y - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        # Indicadores de dirección (flechas cortas)
        self._draw_direction_indicators(frame, color)
        return frame

    def _draw_direction_indicators(self, frame: np.ndarray, color: Tuple) -> None:
        """Dibuja pequeñas marcas perpendiculares en los extremos."""
        dx = self.line_end[0] - self.line_start[0]
        dy = self.line_end[1] - self.line_start[1]
        length = max(1, int((dx**2 + dy**2) ** 0.5))
        perp = (-dy / length * 10, dx / length * 10)

        for pt in [self.line_start, self.line_end]:
            p1 = (int(pt[0] + perp[0]), int(pt[1] + perp[1]))
            p2 = (int(pt[0] - perp[0]), int(pt[1] - perp[1]))
            cv2.line(frame, p1, p2, color, 2)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_side(self, x: int, y: int) -> int:
        """Retorna 1 o -1 según el lado de la línea en que está el punto."""
        x1, y1 = self.line_start
        x2, y2 = self.line_end
        cross = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
        return 1 if cross >= 0 else -1

    @classmethod
    def from_config(cls, cfg: Dict) -> "PerimeterDetector":
        """Crea instancia desde el bloque perimeter_line de config JSON."""
        start = tuple(cfg.get("start", [0, 300]))
        end = tuple(cfg.get("end", [1280, 300]))
        label = cfg.get("label", "Perímetro")
        cooldown = float(cfg.get("cooldown_sec", 3.0))
        return cls(line_start=start, line_end=end, label=label, cooldown_sec=cooldown)
