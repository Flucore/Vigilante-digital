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
