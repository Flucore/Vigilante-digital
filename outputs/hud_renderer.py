"""Renderizador del HUD (Heads-Up Display) para el demo de Vigilante Digital.

Dibuja overlays informativos sobre los frames de cada cámara:
- Barra de estado superior con nombre de zona, FPS, estado y timestamp
- Indicador de alerta con fondo rojo cuando hay evento activo
- Contador de eventos detectados en la sesión
- Información del motor de IA activo
- Overlay de HARDWARE TRIGGER para demo sin hardware físico

Diseño: sobrio, legible en proyector, sin decoraciones innecesarias.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

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

_FONT = cv2.FONT_HERSHEY_SIMPLEX

# Alto de la franja inferior del HUD. FileVideoReader.draw_progress dibuja su
# barra justo encima para que no se superpongan.
FOOTER_H = 20

# Columnas como fracción del ancho del cuadro: (inicio, fin). El estado va
# levemente a la derecha del centro: la columna izquierda (cámara, zona,
# sector) es la que más texto lleva.
_TOP_LEFT    = (0.015, 0.45)
_TOP_CENTER  = (0.45, 0.65)
_TOP_RIGHT   = (0.65, 0.985)
_FOOT_LEFT   = (0.015, 0.49)
_FOOT_RIGHT  = (0.51, 0.985)


def fit_text(
    text: str,
    max_width: int,
    scale: float,
    thickness: int = 1,
    min_scale: float = 0.35,
) -> Tuple[str, float, int]:
    """Ajusta un texto a un ancho máximo en píxeles.

    Primero reduce la escala de la fuente hasta min_scale; si aun así no
    cabe, recorta el texto y agrega "..".

    Returns:
        (texto, escala, ancho_en_pixeles)
    """
    width = cv2.getTextSize(text, _FONT, scale, thickness)[0][0]
    if width > max_width > 0:
        scale = max(min_scale, scale * max_width / width)
        width = cv2.getTextSize(text, _FONT, scale, thickness)[0][0]
    while width > max_width and len(text) > 1:
        text = text[:-3] + ".." if len(text) > 3 else text[:-1]
        width = cv2.getTextSize(text, _FONT, scale, thickness)[0][0]
    return text, scale, width


def put_text_in_column(
    frame: np.ndarray,
    text: str,
    column: Tuple[float, float],
    y: int,
    scale: float,
    color: Tuple[int, int, int],
    thickness: int = 1,
    align: str = "left",
) -> None:
    """Escribe un texto dentro de una columna definida en fracciones del ancho.

    align: "left" | "center" | "right" dentro de la columna.
    """
    w = frame.shape[1]
    x0, x1 = int(column[0] * w), int(column[1] * w)
    text, scale, width = fit_text(text, x1 - x0, scale, thickness)
    if align == "center":
        x = x0 + (x1 - x0 - width) // 2
    elif align == "right":
        x = x1 - width
    else:
        x = x0
    cv2.putText(frame, text, (x, y), _FONT, scale, color, thickness, cv2.LINE_AA)


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

    # Las tres zonas de la barra superior son columnas proporcionales al
    # ancho; cada texto se ajusta a la suya para no montarse sobre otro.

    # Nombre cámara + zona (izquierda)
    zone_text = f"{cam_name}  |  {zone}"
    if sector:
        zone_text += f"  [{sector}]"
    put_text_in_column(frame, zone_text, _TOP_LEFT, 25, 0.6, _C_TEXT_WHITE)

    # Estado (centro)
    state_color = _C_TEXT_RED if alert else _C_TEXT_GREEN
    put_text_in_column(
        frame, f"[ {state} ]", _TOP_CENTER, 26, 0.65, state_color, 2, align="center"
    )

    # FPS + timestamp (derecha)
    ts = datetime.now().strftime("%H:%M:%S")
    right_text = f"FPS: {fps:4.1f}  |  {ts}"
    put_text_in_column(frame, right_text, _TOP_RIGHT, 25, 0.52, _C_TEXT_WHITE, align="right")

    # ── Barra inferior ──────────────────────────────────────────────────────
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h - FOOTER_H), (w, h), _C_BG_NORMAL, -1)
    cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)
    footer_y = h - 6
    put_text_in_column(
        frame, f"Motor: {engine} / {device}", _FOOT_LEFT, footer_y, 0.42, _C_ACCENT
    )
    put_text_in_column(
        frame, f"Eventos sesion: {events_count}", _FOOT_RIGHT, footer_y, 0.42,
        _C_TEXT_AMBER, align="right",
    )

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


def draw_hardware_trigger_overlay(
    frame: np.ndarray,
    trigger_data: Dict[str, Any],
    display_seconds: float = 3.0,
    activated_at: Optional[float] = None,
) -> Tuple[np.ndarray, bool]:
    """Dibuja el overlay de HARDWARE TRIGGER para demo sin hardware físico.

    El overlay aparece en la esquina superior derecha del frame durante
    ``display_seconds`` segundos desde ``activated_at``. No requiere hardware
    real: se activa cuando TriggerManager dispararía la bocina (Nivel 3).

    Args:
        frame: Frame BGR a anotar (modificado in-place y retornado).
        trigger_data: Dict con información del trigger:
            - trigger_type (str): "SIRENA" | "RELAY" | "MQTT"
            - mqtt_topic (str): topic MQTT o identificador del hardware
            - timestamp (str): ISO 8601 del evento
            - camera_id (str): ID de la cámara que disparó
        display_seconds: Duración del overlay en segundos.
        activated_at: time.time() del momento de activación.
                      Si None, se usa el momento actual (primer frame).

    Returns:
        (frame_anotado, still_active): frame con overlay; bool que indica
        si el overlay sigue activo (para controlar en el loop principal).

    Ejemplo::

        # En el loop de la cámara, al detectar trigger Nivel 3:
        trigger_ts = time.time()
        trigger_data = {
            "trigger_type": "SIRENA",
            "mqtt_topic": "vigilante/relay/horn",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "camera_id": "CAM_PATIO_1",
        }

        # En cada frame siguiente:
        frame, active = draw_hardware_trigger_overlay(
            frame, trigger_data, activated_at=trigger_ts
        )
        if not active:
            trigger_ts = None  # apagar overlay
    """
    now = time.time()
    t0 = activated_at if activated_at is not None else now
    elapsed = now - t0

    if elapsed > display_seconds:
        return frame, False

    h, w = frame.shape[:2]

    # Dimensiones del panel
    panel_w = min(380, w - 20)
    panel_h = 100
    margin = 12
    x1 = w - panel_w - margin
    y1 = margin
    x2 = w - margin
    y2 = y1 + panel_h

    # Fondo rojo semitransparente
    overlay = frame.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 0, 180), -1)
    alpha = 0.82
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    # Borde rojo sólido
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 230), 2)

    # Textos
    t_type    = str(trigger_data.get("trigger_type", "SIRENA"))
    t_topic   = str(trigger_data.get("mqtt_topic",   "vigilante/relay/horn"))
    t_ts      = str(trigger_data.get("timestamp",    ""))[:19]  # solo hasta segundos
    t_cam     = str(trigger_data.get("camera_id",    ""))

    # Línea 1: título
    cv2.putText(
        frame, "HARDWARE TRIGGER ACTIVADO",
        (x1 + 8, y1 + 22),
        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA,
    )

    # Línea 2: tipo y cámara
    cv2.putText(
        frame, f"{t_type}  |  {t_cam}",
        (x1 + 8, y1 + 44),
        cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 210, 210), 1, cv2.LINE_AA,
    )

    # Línea 3: topic MQTT
    topic_txt = t_topic if len(t_topic) <= 38 else t_topic[:35] + "..."
    cv2.putText(
        frame, f"Topic: {topic_txt}",
        (x1 + 8, y1 + 63),
        cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 200, 200), 1, cv2.LINE_AA,
    )

    # Línea 4: timestamp
    cv2.putText(
        frame, t_ts,
        (x1 + 8, y1 + 82),
        cv2.FONT_HERSHEY_SIMPLEX, 0.40, (220, 220, 220), 1, cv2.LINE_AA,
    )

    # Barra de tiempo restante (fade visual)
    remaining_ratio = max(0.0, 1.0 - elapsed / display_seconds)
    bar_w = int((panel_w - 16) * remaining_ratio)
    if bar_w > 0:
        cv2.rectangle(
            frame,
            (x1 + 8, y2 - 7),
            (x1 + 8 + bar_w, y2 - 3),
            (255, 100, 100), -1,
        )

    return frame, True


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
