"""Detector de movimiento con BackgroundSubtractorMOG2 — Vigilante Digital v2.0.

Solo emite MotionEvent cuando is_after_hours == True, lo que lo convierte
en un guardián de horario no hábil de costo computacional mínimo.

Dependencias: solo OpenCV (incluido en el stack base del proyecto).

Compatibilidad con detector_factory:
    find_pose()     → (frame_anotado, Optional[MotionEvent])
    find_position() → ([], {})
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

LOG = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class MotionEvent:
    """Evento emitido cuando se detecta movimiento fuera de horario.

    Atributos:
        timestamp:   Unix timestamp del evento.
        camera_id:   Identificador de la cámara.
        area_pixels: Área total de movimiento en píxeles.
        centroid:    (x, y) del centroide del área de movimiento.
        frame_idx:   Número del frame donde se detectó.
        contours_n:  Número de contornos de movimiento detectados.
    """
    timestamp:   float
    camera_id:   str
    area_pixels: int
    centroid:    Tuple[int, int]
    frame_idx:   int
    contours_n:  int = 0


# ──────────────────────────────────────────────────────────────────────────────
# MotionDetector
# ──────────────────────────────────────────────────────────────────────────────

class MotionDetector:
    """Detecta movimiento usando BackgroundSubtractorMOG2 de OpenCV.

    Solo genera MotionEvent cuando `is_after_hours == True`. Durante horario
    hábil, el detector sigue actualizando su modelo de fondo en silencio para
    mantener la calibración.

    Args:
        sensitivity:  Factor de sensibilidad [0.1 – 1.0]. Valores altos
                      detectan movimientos más sutiles.
        min_area_px:  Área mínima de contorno (píxeles) para generar evento.
        camera_id:    Identificador de la cámara fuente.
        history:      Número de frames usados para el modelo de fondo (MOG2).
        blur_ksize:   Kernel de desenfoque Gaussiano antes de sustracción.

    Ejemplo::

        detector = MotionDetector(sensitivity=0.6, min_area_px=800)
        event = detector.update(frame, is_after_hours=True, frame_idx=n)
        if event:
            # enviar alerta
    """

    def __init__(
        self,
        sensitivity: float = 0.50,
        min_area_px: int   = 500,
        camera_id:   str   = "unknown",
        history:     int   = 300,
        blur_ksize:  int   = 21,
    ) -> None:
        if not (0.0 < sensitivity <= 1.0):
            raise ValueError(f"sensitivity debe estar en (0, 1]. Recibido: {sensitivity}")

        self.sensitivity  = sensitivity
        self.min_area_px  = min_area_px
        self.camera_id    = camera_id
        self.blur_ksize   = blur_ksize if blur_ksize % 2 == 1 else blur_ksize + 1

        # Umbral de detección: sensibilidad alta → umbral bajo → más sensible
        threshold = max(8, int(80 * (1.0 - sensitivity)))

        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history       = history,
            varThreshold  = threshold,
            detectShadows = True,
        )
        self._frame_count = 0

        LOG.info(
            "[MotionDetector] cam=%s sensitivity=%.2f min_area=%d threshold=%d",
            camera_id, sensitivity, min_area_px, threshold,
        )

    # ── Interfaz pública ─────────────────────────────────────────────────────

    def update(
        self,
        frame: np.ndarray,
        is_after_hours: bool = False,
        frame_idx: int = 0,
    ) -> Optional[MotionEvent]:
        """Procesa un frame y emite un MotionEvent si corresponde.

        Siempre actualiza el modelo de fondo, independientemente del horario.

        Args:
            frame:          Frame BGR de entrada.
            is_after_hours: Si True, emite MotionEvent al detectar movimiento.
            frame_idx:      Número de frame para trazabilidad.

        Returns:
            MotionEvent si hay movimiento y is_after_hours es True; None en otro caso.
        """
        self._frame_count += 1
        fg_mask = self._compute_fg_mask(frame)

        # Encontrar contornos de movimiento
        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        valid = [c for c in contours if cv2.contourArea(c) >= self.min_area_px]

        if not valid or not is_after_hours:
            return None

        # Calcular área total y centroide
        total_area = sum(int(cv2.contourArea(c)) for c in valid)
        all_pts    = np.vstack(valid).reshape(-1, 2)
        cx, cy     = int(all_pts[:, 0].mean()), int(all_pts[:, 1].mean())

        event = MotionEvent(
            timestamp   = time.time(),
            camera_id   = self.camera_id,
            area_pixels = total_area,
            centroid    = (cx, cy),
            frame_idx   = frame_idx,
            contours_n  = len(valid),
        )
        LOG.info(
            "[MotionDetector] ALERTA cam=%s area=%d contours=%d frame=%d",
            self.camera_id, total_area, len(valid), frame_idx,
        )
        return event

    def draw(
        self,
        frame: np.ndarray,
        event: Optional[MotionEvent] = None,
        show_mask: bool = False,
    ) -> np.ndarray:
        """Dibuja indicadores de movimiento sobre el frame.

        Args:
            frame:     Frame BGR a anotar.
            event:     MotionEvent activo (si existe).
            show_mask: Si True, superpone la máscara de movimiento.

        Returns:
            Frame anotado.
        """
        if event is None:
            return frame

        # Círculo en el centroide
        cv2.circle(frame, event.centroid, 12, (0, 0, 255), 3)

        # Etiqueta de alerta
        cv2.putText(
            frame,
            f"MOVIMIENTO DETECTADO — {event.area_pixels}px",
            (10, 35),
            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2, cv2.LINE_AA,
        )
        return frame

    def get_fg_mask(self, frame: np.ndarray) -> np.ndarray:
        """Retorna la máscara de primer plano (útil para depuración)."""
        return self._compute_fg_mask(frame)

    # ── Compatibilidad detector_factory ──────────────────────────────────────

    def find_pose(
        self,
        img: np.ndarray,
        draw: bool = True,
    ) -> Tuple[np.ndarray, Optional[MotionEvent]]:
        """Procesa el frame sin lógica de horario (siempre emite si hay movimiento)."""
        event = self.update(img, is_after_hours=True, frame_idx=self._frame_count)
        if draw and event:
            img = self.draw(img, event)
        return img, event

    def find_position(
        self,
        img: np.ndarray,
        results: Any,
        draw: bool = True,
    ) -> Tuple[List, Dict]:
        if not isinstance(results, MotionEvent) or results is None:
            return [], {}
        return [], {
            "centroid": results.centroid,
            "area_pixels": results.area_pixels,
        }

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def reset_background(self) -> None:
        """Reinicia el modelo de fondo (útil tras cambios bruscos de iluminación)."""
        self._subtractor.clear()
        LOG.info("[MotionDetector] Modelo de fondo reiniciado (cam=%s)", self.camera_id)

    def close(self) -> None:
        pass

    def __enter__(self) -> "MotionDetector":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ── Utilidades privadas ───────────────────────────────────────────────────

    def _compute_fg_mask(self, frame: np.ndarray) -> np.ndarray:
        """Aplica desenfoque + sustracción de fondo + morfología."""
        blurred = cv2.GaussianBlur(frame, (self.blur_ksize, self.blur_ksize), 0)
        fg_mask = self._subtractor.apply(blurred)

        # Eliminar sombras (valor 127 en MOG2 con detectShadows=True)
        _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

        # Morfología para reducir ruido y llenar huecos
        kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN,  kernel, iterations=1)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        return fg_mask
