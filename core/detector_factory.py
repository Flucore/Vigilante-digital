"""Factory de detectores — Vigilante Digital v2.0.

Selecciona e instancia el detector correcto según el módulo solicitado y el
hardware disponible.

Jerarquía de selección (fall_detection, por defecto):
  1. YoloFallDetector con GPU  (CUDA disponible + ultralytics instalado)
  2. YoloFallDetector con CPU  (ultralytics instalado, sin GPU)
  3. PoseDetector MediaPipe    (fallback universal)

Módulos adicionales (Sprint 3):
  segmentation → SegmentationDetector   (YOLOv8-seg)
  intrusion    → IntrusionDetector      (polígono + tracking)
  vehicle      → VehicleDetector        (conteo + atributos de color)
  motion       → MotionDetector         (MOG2, horario no hábil)
  custom       → load_custom_model()    (pesos cliente / Transfer Learning)

Uso::

    # Módulo clásico (compatible con código existente)
    detector = get_detector()

    # Módulo de segmentación
    detector = get_detector(module_type="segmentation", mode="instance")

    # Detector de intrusión con zonas
    from core.intrusion_detector import ZoneConfig
    zones = [ZoneConfig(id="z1", label="Patio", points=[[0.1,0.1],[0.9,0.1],[0.9,0.9],[0.1,0.9]])]
    detector = get_detector(module_type="intrusion", zones=zones)

    # Modelo custom del cliente
    detector = get_detector(module_type="custom", weights_path="models/cliente_abc.pt")
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

LOG = logging.getLogger(__name__)

# Tipo genérico para retorno
_AnyDetector = Any


def get_detector(
    use_gpu: bool = True,
    min_fall_frames: int = 8,
    fall_angle_deg: float = 55.0,
    mediapipe_complexity: int = 1,
    module_type: str = "fall_detection",
    # ── Parámetros para módulos Sprint 3 ──────────────────────────────────────
    mode: str = "instance",                          # segmentation mode
    zones: Optional[List[Any]] = None,               # intrusion zones
    cooldown_sec: float = 5.0,                       # intrusion cooldown
    entry_polygon: Optional[List[List[float]]] = None,  # vehicle polygon
    min_intersection_sec: float = 2.0,               # vehicle threshold
    sensitivity: float = 0.50,                       # motion sensitivity
    min_area_px: int = 500,                          # motion min area
    camera_id: str = "unknown",                      # shared param
    weights_path: str = "",                          # custom model path
    task: str = "detect",                            # custom model task
    device: str = "auto",                            # shared device override
    confidence: float = 0.45,                        # segmentation confidence
    **kwargs: Any,
) -> _AnyDetector:
    """Retorna el detector configurado para el módulo solicitado.

    Args:
        use_gpu:              Intentar usar CUDA (módulos fall_detection).
        min_fall_frames:      Frames para confirmar caída (fall_detection).
        fall_angle_deg:       Ángulo umbral de caída (fall_detection).
        mediapipe_complexity: Complejidad MediaPipe (fall_detection fallback).
        module_type:          Módulo a instanciar (ver opciones arriba).
        mode:                 Modo de segmentación (segmentation).
        zones:                Zonas de intrusión (intrusion).
        cooldown_sec:         Cooldown entre eventos (intrusion).
        entry_polygon:        Polígono de entrada (vehicle).
        min_intersection_sec: Segundos en polígono para evento (vehicle).
        sensitivity:          Sensibilidad MOG2 (motion).
        min_area_px:          Área mínima de movimiento px (motion).
        camera_id:            ID de cámara para logging.
        weights_path:         Ruta a los pesos custom (custom).
        task:                 Tarea del modelo custom (custom).
        device:               Dispositivo override para módulos nuevos.
        confidence:           Confianza de detección (segmentation).
        **kwargs:             Ignorados, para compatibilidad futura.

    Returns:
        Instancia del detector solicitado.

    Raises:
        ValueError: Si module_type es desconocido.
    """
    resolved_device = _resolve_device(device, use_gpu)

    if module_type == "fall_detection":
        return _make_fall_detector(
            use_gpu, min_fall_frames, fall_angle_deg, mediapipe_complexity
        )

    if module_type == "segmentation":
        return _make_segmentation_detector(mode, resolved_device, confidence)

    if module_type == "intrusion":
        return _make_intrusion_detector(zones or [], cooldown_sec)

    if module_type == "vehicle":
        return _make_vehicle_detector(
            entry_polygon or [[0.1, 0.3], [0.9, 0.3], [0.9, 0.8], [0.1, 0.8]],
            min_intersection_sec,
            resolved_device,
            camera_id,
        )

    if module_type == "motion":
        return _make_motion_detector(sensitivity, min_area_px, camera_id)

    if module_type == "custom":
        return _make_custom_detector(weights_path, task, resolved_device)

    raise ValueError(
        f"module_type desconocido: '{module_type}'. "
        "Válidos: fall_detection | segmentation | intrusion | vehicle | motion | custom"
    )


def detector_info(detector: _AnyDetector) -> Dict[str, Any]:
    """Retorna metadatos del motor activo para el HUD / logs."""
    name = type(detector).__name__
    base: Dict[str, Any] = {
        "engine":  name,
        "device":  getattr(detector, "device", "cpu").upper(),
    }

    if name == "YoloFallDetector":
        base.update({
            "module":             "fall_detection",
            "temporal_validation": True,
        })
    elif name == "SegmentationDetector":
        base.update({
            "module": "segmentation",
            "mode":   getattr(detector, "mode", "instance"),
            "fallback": getattr(detector, "_fallback", False),
        })
    elif name == "IntrusionDetector":
        base.update({
            "module":    "intrusion",
            "n_zones":   len(getattr(detector, "zones", [])),
            "cooldown":  getattr(detector, "cooldown_sec", 5.0),
        })
    elif name == "VehicleDetector":
        base.update({
            "module": "vehicle",
            "camera": getattr(detector, "camera_id", "unknown"),
        })
    elif name == "MotionDetector":
        base.update({
            "module":      "motion",
            "sensitivity": getattr(detector, "sensitivity", 0.5),
            "min_area":    getattr(detector, "min_area_px", 500),
        })
    else:
        base.update({
            "module": "custom",
            "engine": "MediaPipe" if name == "PoseDetector" else name,
            "temporal_validation": False,
        })

    return base


# ──────────────────────────────────────────────────────────────────────────────
# Constructores privados
# ──────────────────────────────────────────────────────────────────────────────

def _make_fall_detector(
    use_gpu: bool,
    min_fall_frames: int,
    fall_angle_deg: float,
    mediapipe_complexity: int,
) -> _AnyDetector:
    try:
        from core.yolo_fall_detector import YoloFallDetector
        detector = YoloFallDetector(
            min_fall_frames=min_fall_frames,
            fall_angle_deg=fall_angle_deg,
            use_gpu=use_gpu,
        )
        engine = f"YOLOv8-pose ({'GPU/CUDA' if detector.device == 'cuda' else 'CPU'})"
        LOG.info("Motor de detección: %s", engine)
        return detector
    except Exception as exc:
        LOG.warning("YoloFallDetector no disponible (%s) — usando MediaPipe", exc)

    from core.pose_detector import PoseDetector
    detector = PoseDetector(complexity=mediapipe_complexity)
    LOG.info("Motor de detección: MediaPipe Pose (complexity=%d)", mediapipe_complexity)
    return detector


def _make_segmentation_detector(
    mode: str,
    device: str,
    confidence: float,
) -> _AnyDetector:
    from core.segmentation_detector import SegmentationDetector
    detector = SegmentationDetector(mode=mode, device=device, confidence=confidence)
    LOG.info("Motor de detección: SegmentationDetector mode=%s device=%s", mode, device)
    return detector


def _make_intrusion_detector(
    zones: List[Any],
    cooldown_sec: float,
) -> _AnyDetector:
    from core.intrusion_detector import IntrusionDetector
    detector = IntrusionDetector(zones=zones, cooldown_sec=cooldown_sec)
    LOG.info("Motor de detección: IntrusionDetector zones=%d", len(zones))
    return detector


def _make_vehicle_detector(
    entry_polygon: List[List[float]],
    min_intersection_sec: float,
    device: str,
    camera_id: str,
) -> _AnyDetector:
    from core.vehicle_detector import VehicleDetector
    detector = VehicleDetector(
        entry_polygon=entry_polygon,
        min_intersection_sec=min_intersection_sec,
        device=device,
        camera_id=camera_id,
    )
    LOG.info("Motor de detección: VehicleDetector cam=%s", camera_id)
    return detector


def _make_motion_detector(
    sensitivity: float,
    min_area_px: int,
    camera_id: str,
) -> _AnyDetector:
    from core.motion_detector import MotionDetector
    detector = MotionDetector(
        sensitivity=sensitivity,
        min_area_px=min_area_px,
        camera_id=camera_id,
    )
    LOG.info("Motor de detección: MotionDetector cam=%s sensitivity=%.2f", camera_id, sensitivity)
    return detector


def _make_custom_detector(
    weights_path: str,
    task: str,
    device: str,
) -> _AnyDetector:
    from core.custom_model_loader import load_custom_model
    model = load_custom_model(weights_path=weights_path, task=task, device=device)
    if model is None:
        LOG.warning(
            "custom_model_loader retornó None — "
            "usando fall_detection como fallback."
        )
        return _make_fall_detector(True, 8, 55.0, 1)

    # Envolver el modelo crudo en un adaptador compatible
    return _CustomModelAdapter(model, task=task, device=device)


# ──────────────────────────────────────────────────────────────────────────────
# Adaptador para modelo custom
# ──────────────────────────────────────────────────────────────────────────────

class _CustomModelAdapter:
    """Envuelve un modelo YOLO custom para exponer find_pose / find_position."""

    def __init__(self, model: Any, task: str, device: str) -> None:
        self._model  = model
        self.task    = task
        self.device  = device

    def find_pose(self, img: Any, draw: bool = True):
        try:
            results = self._model(img, device=self.device, verbose=False)
            return img, results
        except Exception as exc:
            LOG.error("[CustomModelAdapter] Error en inferencia: %s", exc)
            return img, []

    def find_position(self, img: Any, results: Any, draw: bool = True):
        return [], {}

    def close(self) -> None:
        self._model = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ──────────────────────────────────────────────────────────────────────────────
# Utilidades
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_device(device: str, use_gpu: bool) -> str:
    if device != "auto":
        return device
    if not use_gpu:
        return "cpu"
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"
