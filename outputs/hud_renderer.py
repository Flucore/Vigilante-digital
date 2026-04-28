"""Renderizador del HUD (Heads-Up Display) para el demo de Vigilante Digital.

Dibuja overlays informativos sobre los frames de cada cámara:
- Barra de estado superior con nombre de zona, FPS, estado y timestamp
- Indicador de alerta con fondo rojo cuando hay evento activo
- Contador de eventos detectados en la sesión
- Información del motor de IA activo

Diseño: sobrio, legible en proyector, sin decoraciones innecesarias.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Optional, Tuple

import cv2
import numpy as np

# Paleta de colores (BGR)
_C_BG_NORMAL  = (30, 30, 30)         # Fondo barra estado normal
_C_BG_ALERT   = (0, 0, 180)          # Fondo barra estado alerta
_C_TEXT_WHITE = (255, 255, 255)
_C_TEXT_GREEN = (50, 220, 50)
_C_TEXT_RED   = (50, 50, 255)
_C_TEXT_AMBER = (40, 165, 255)
_C_ACCENT     = (0, 165, 255)        # Naranja (marca Vigilante)


def draw_hud(
    frame: np.ndarray,
    cam_name: str,
    zone: str,
    fps: float,
    state: str,
    events_count: int = 0,
    engine: str = "MediaPipe",
    device: str = "CPU",
    sector: str = "",
) -> np.ndarray:
    """Dibuja el HUD completo sobre el frame.

    Args:
        frame: Frame BGR de OpenCV (modificado in-place y retornado).
        cam_name: Nombre de la cámara (ej: "CAM_1").
        zone: Nombre de la zona (ej: "Bodega A").
        fps: FPS actuales del procesamiento.
        state: Estado actual ("NORMAL" | "ALERTA" | "INTRUSIÓN" | "SIN SEÑAL").
        events_count: Número de eventos detectados en la sesión.
        engine: Motor de detección activo.
        device: Dispositivo de cómputo ("CPU" | "GPU").
        sector: Nombre del sector opcional.

    Returns:
        El mismo frame con el HUD dibujado.
    """
    h, w = frame.shape[:2]
    bar_h = 38
    alert = state not in ("NORMAL", "SIN SEÑAL", "OBSERVANDO")

    # ── Barra superior ──────────────────────────────────────────────────────
    bar_color = _C_BG_ALERT if alert else _C_BG_NORMAL
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, bar_h), bar_color, -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    # Nombre cámara + zona (izquierda)
    zone_text = f"{cam_name}  |  {zone}"
    if sector:
        zone_text += f"  [{sector}]"
    cv2.putText(frame, zone_text, (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, _C_TEXT_WHITE, 1, cv2.LINE_AA)

    # Estado (centro)
    state_color = _C_TEXT_RED if alert else _C_TEXT_GREEN
    state_label = f"[ {state} ]"
    state_size = cv2.getTextSize(state_label, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)[0]
    state_x = (w - state_size[0]) // 2
    cv2.putText(frame, state_label, (state_x, 26),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, state_color, 2, cv2.LINE_AA)

    # FPS + timestamp (derecha)
    ts = datetime.now().strftime("%H:%M:%S")
    right_text = f"FPS: {fps:4.1f}  |  {ts}"
    right_size = cv2.getTextSize(right_text, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)[0]
    cv2.putText(frame, right_text, (w - right_size[0] - 10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, _C_TEXT_WHITE, 1, cv2.LINE_AA)

    # ── Barra inferior ──────────────────────────────────────────────────────
    footer_y = h - 6
    engine_text = f"Motor: {engine} / {device}"
    cv2.putText(frame, engine_text, (10, footer_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, _C_ACCENT, 1, cv2.LINE_AA)

    events_text = f"Eventos sesion: {events_count}"
    ev_size = cv2.getTextSize(events_text, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)[0]
    cv2.putText(frame, events_text, (w - ev_size[0] - 10, footer_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, _C_TEXT_AMBER, 1, cv2.LINE_AA)

    # ── Flash de alerta (borde rojo parpadeante) ─────────────────────────────
    if alert:
        blink = int(time.time() * 2) % 2 == 0
        if blink:
            cv2.rectangle(frame, (0, 0), (w - 1, h - 1), _C_TEXT_RED, 4)

    return frame


def draw_no_signal(frame_size: Tuple[int, int], cam_name: str) -> np.ndarray:
    """Genera un frame negro con mensaje 'SIN SEÑAL' para cuando la cámara no conecta."""
    h, w = frame_size
    frame = np.zeros((h, w, 3), dtype=np.uint8)

    # Texto centrado
    msg1 = "SIN SEÑAL"
    msg2 = cam_name
    for i, (msg, scale) in enumerate([(msg1, 1.2), (msg2, 0.7)]):
        size = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)[0]
        x = (w - size[0]) // 2
        y = h // 2 + (i * 50) - 20
        cv2.putText(frame, msg, (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX, scale, _C_TEXT_AMBER, 2, cv2.LINE_AA)
    return frame


def compose_split_view(
    frame_left: np.ndarray,
    frame_right: np.ndarray,
    target_width: int = 1920,
    target_height: int = 540,
) -> np.ndarray:
    """Compone dos frames en una vista dividida horizontalmente.

    Args:
        frame_left: Frame de la cámara izquierda.
        frame_right: Frame de la cámara derecha.
        target_width: Ancho total de la vista compuesta.
        target_height: Alto de la vista compuesta.

    Returns:
        Frame compuesto (numpy array BGR).
    """
    half_w = target_width // 2

    def _resize(f: np.ndarray) -> np.ndarray:
        try:
            return cv2.resize(f, (half_w, target_height))
        except Exception:
            return np.zeros((target_height, half_w, 3), dtype=np.uint8)

    left  = _resize(frame_left)
    right = _resize(frame_right)

    # Separador vertical delgado
    sep = np.zeros((target_height, 4, 3), dtype=np.uint8)
    sep[:] = (60, 60, 60)

    return np.hstack([left, sep, right])
