"""Factory de detectores: selecciona el motor óptimo según hardware disponible.

Jerarquía de selección:
  1. YoloFallDetector con GPU  (CUDA disponible + ultralytics instalado)
  2. YoloFallDetector con CPU  (ultralytics instalado, sin GPU)
  3. PoseDetector MediaPipe    (fallback universal, sin dependencias adicionales)

Uso:
    detector = get_detector()
    frame, results = detector.find_pose(frame)
    lm_list, bbox = detector.find_position(frame, results)
    is_falling = bbox.get("is_falling", False)
"""
from __future__ import annotations

import logging
from typing import Any, Union

logger = logging.getLogger(__name__)

# Tipos de unión para type hints
_AnyDetector = Any  # YoloFallDetector | PoseDetector


def get_detector(
    use_gpu: bool = True,
    min_fall_frames: int = 8,
    fall_angle_deg: float = 55.0,
    mediapipe_complexity: int = 1,
) -> _AnyDetector:
    """Retorna el mejor detector disponible para el hardware actual.

    Args:
        use_gpu: Si True, intenta usar CUDA.
        min_fall_frames: Frames mínimos para confirmar caída (solo YOLO).
        fall_angle_deg: Ángulo torso umbral de caída en grados (solo YOLO).
        mediapipe_complexity: Complejidad del modelo MediaPipe (0/1/2).

    Returns:
        Instancia de YoloFallDetector o PoseDetector, con API compatible.
    """
    # Intentar YOLO primero
    try:
        from core.yolo_fall_detector import YoloFallDetector
        detector = YoloFallDetector(
            min_fall_frames=min_fall_frames,
            fall_angle_deg=fall_angle_deg,
            use_gpu=use_gpu,
        )
        engine = f"YOLOv8-pose ({'GPU/CUDA' if detector.device == 'cuda' else 'CPU'})"
        logger.info("Motor de detección: %s", engine)
        return detector
    except Exception as exc:
        logger.warning("YoloFallDetector no disponible (%s) — usando MediaPipe", exc)

    # Fallback a MediaPipe
    from core.pose_detector import PoseDetector
    detector = PoseDetector(complexity=mediapipe_complexity)
    logger.info("Motor de detección: MediaPipe Pose (complexity=%d)", mediapipe_complexity)
    return detector


def detector_info(detector: _AnyDetector) -> dict:
    """Retorna información del motor activo para mostrar en HUD."""
    name = type(detector).__name__
    if name == "YoloFallDetector":
        return {
            "engine": "YOLOv8-pose",
            "device": getattr(detector, "device", "cpu").upper(),
            "temporal_validation": True,
        }
    return {
        "engine": "MediaPipe",
        "device": "CPU",
        "temporal_validation": False,
    }
