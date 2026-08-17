"""Cargador de modelos personalizados para Transfer Learning — Vigilante Digital v2.0.

Permite cargar pesos entrenados por el cliente (.pt o .onnx) manteniendo
la interfaz compatible con el resto del sistema.

Tareas soportadas:
    detect   → detección de objetos (YOLOv8 det)
    segment  → segmentación de instancias (YOLOv8 seg)
    classify → clasificación de imagen (YOLOv8 cls)
    pose     → estimación de pose (YOLOv8 pose)

Flujo de Transfer Learning:
    1. Cliente provee pesos .pt (fine-tuned sobre su entorno específico)
    2. load_custom_model(weights_path, task, device) retorna modelo cargado
    3. El modelo se pasa al detector correspondiente como model_path
    4. detector_factory puede instanciar con module_type="custom"

Seguridad: verifica extensión y existencia del archivo antes de cargar.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

LOG = logging.getLogger(__name__)

# Extensiones permitidas (evita carga de archivos arbitrarios)
_ALLOWED_EXTENSIONS = {".pt", ".pth", ".onnx"}

# Intentar cargar ultralytics (opcional)
try:
    from ultralytics import YOLO
    _YOLO_AVAILABLE = True
except ImportError:
    _YOLO_AVAILABLE = False


# ──────────────────────────────────────────────────────────────────────────────
# Función pública principal
# ──────────────────────────────────────────────────────────────────────────────

def load_custom_model(
    weights_path: str,
    task: str = "detect",
    device: str = "auto",
) -> Optional[Any]:
    """Carga un modelo YOLO con pesos personalizados del cliente.

    Args:
        weights_path: Ruta al archivo de pesos (.pt o .onnx).
        task:         Tipo de tarea: "detect" | "segment" | "classify" | "pose".
        device:       "cuda" | "cpu" | "auto".

    Returns:
        Modelo YOLO cargado, compatible con YoloFallDetector/SegmentationDetector.
        Retorna None si el archivo no existe o hay un error de carga.

    Raises:
        ValueError: Si `task` o la extensión del archivo no son válidos.
    """
    valid_tasks = {"detect", "segment", "classify", "pose"}
    if task not in valid_tasks:
        raise ValueError(
            f"task debe ser uno de {valid_tasks}. Recibido: '{task}'"
        )

    path = Path(weights_path)

    if not path.exists():
        LOG.warning(
            "[CustomModelLoader] Archivo de pesos no encontrado: %s — "
            "se continuará sin modelo custom.",
            weights_path,
        )
        return None

    if path.suffix.lower() not in _ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Extensión '{path.suffix}' no permitida. "
            f"Usar: {_ALLOWED_EXTENSIONS}"
        )

    if not _YOLO_AVAILABLE:
        LOG.error(
            "[CustomModelLoader] ultralytics no está instalado. "
            "Ejecutar: pip install ultralytics"
        )
        return None

    resolved_device = _resolve_device(device)

    try:
        model = YOLO(str(path), task=task)

        # Detectar número de clases
        n_classes = (
            len(model.names)
            if hasattr(model, "names") and model.names
            else "desconocido"
        )

        LOG.info(
            "[CustomModelLoader] Modelo cargado OK | archivo=%s | task=%s | "
            "device=%s | clases=%s",
            path.name, task, resolved_device, n_classes,
        )
        return model

    except Exception as exc:
        LOG.error(
            "[CustomModelLoader] Error al cargar '%s': %s",
            weights_path, exc,
        )
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Utilidades
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_device(device: str) -> str:
    """Resuelve 'auto' al dispositivo óptimo disponible."""
    if device != "auto":
        return device
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def model_info(model: Any) -> dict:
    """Retorna metadatos del modelo para logging / HUD.

    Args:
        model: Objeto YOLO cargado.

    Returns:
        Dict con name, task, n_classes, names.
    """
    if model is None:
        return {"name": None, "task": None, "n_classes": 0, "names": {}}

    try:
        return {
            "name":      getattr(model, "model_name", str(type(model).__name__)),
            "task":      getattr(model, "task", "unknown"),
            "n_classes": len(model.names) if hasattr(model, "names") else 0,
            "names":     model.names if hasattr(model, "names") else {},
        }
    except Exception:
        return {"name": "unknown", "task": "unknown", "n_classes": 0, "names": {}}
