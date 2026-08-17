"""Módulo de Segmentación — Vigilante Digital v2.0.

Provee segmentación de instancias, semántica y panóptica usando YOLOv8-seg.
Cuando ultralytics no está disponible, el módulo degrada gracefully a bounding
boxes coloreados (modo bbox_fallback), manteniendo la interfaz intacta.

Modos disponibles:
  instance  — Una máscara por cada objeto detectado (personas, vehículos, etc.)
  semantic  — Agrupa objetos del mismo tipo en una sola máscara de color
  panoptic  — Instancias (things) + fondos semánticos (stuff)

Compatibilidad con detector_factory:
  find_pose()     → (frame_anotado, SegmentationResult)
  find_position() → ([], bbox_principal)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

LOG = logging.getLogger(__name__)

# Intentar cargar ultralytics (opcional)
try:
    from ultralytics import YOLO
    import torch
    _YOLO_AVAILABLE = True
except ImportError:
    _YOLO_AVAILABLE = False
    LOG.warning(
        "[SegmentationDetector] ultralytics no disponible — modo bbox_fallback activo. "
        "Instalar: pip install ultralytics"
    )

# Paleta de colores para máscaras (BGR, 20 colores distintos)
_PALETTE = [
    (255, 56,  56), (255, 157, 151), (255, 112,  31), (255, 178, 29),
    (207, 210,  49), (72,  249,  10), (146, 204,  23), (61,  219, 134),
    (26,  147, 52), (0,  212, 187), (44,  153, 168), (0,  194, 255),
    (52,   69, 147), (100,  115, 255), (0,   24, 236), (132,  56, 255),
    (82,   0, 133), (203,  56, 255), (255,  149, 200), (255,  55, 199),
]


# ──────────────────────────────────────────────────────────────────────────────
# Dataclasses de resultado
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SegmentationResult:
    """Resultado de una inferencia de segmentación.

    Atributos:
        masks:  Lista de máscaras binarias (np.ndarray bool H×W por objeto).
        boxes:  Lista de bboxes [xmin, ymin, xmax, ymax] por objeto.
        labels: Lista de etiquetas string por objeto (ej: "person").
        scores: Lista de confianzas float [0, 1] por objeto.
        mode:   Modo de segmentación activo.
        raw:    Resultado crudo de ultralytics (None en modo fallback).
    """
    masks:  List[Any]          = field(default_factory=list)
    boxes:  List[List[int]]    = field(default_factory=list)
    labels: List[str]          = field(default_factory=list)
    scores: List[float]        = field(default_factory=list)
    mode:   str                = "instance"
    raw:    Optional[Any]      = None

    @property
    def count(self) -> int:
        return len(self.labels)

    @property
    def is_empty(self) -> bool:
        return len(self.labels) == 0


# ──────────────────────────────────────────────────────────────────────────────
# SegmentationDetector
# ──────────────────────────────────────────────────────────────────────────────

class SegmentationDetector:
    """Detector de segmentación multi-modo basado en YOLOv8-seg.

    Args:
        model_path: Path a los pesos .pt del modelo (default: yolov8n-seg.pt).
                    Se descarga automáticamente en el primer uso si no existe.
        mode:       "instance" | "semantic" | "panoptic" (default: "instance").
        device:     "cuda" | "cpu" | "auto" (default: "auto").
        confidence: Umbral mínimo de confianza (default: 0.45).

    Ejemplo::

        detector = SegmentationDetector(mode="instance")
        frame_out, result = detector.find_pose(frame)
        lm_list, bbox = detector.find_position(frame_out, result)
    """

    # Clases semánticas que se consideran "fondo" en modo panóptico
    _STUFF_CLASSES = {"wall", "floor", "ceiling", "sky", "road", "pavement",
                       "grass", "tree", "building", "window", "door"}

    def __init__(
        self,
        model_path: str = "yolov8n-seg.pt",
        mode: str = "instance",
        device: str = "auto",
        confidence: float = 0.45,
    ) -> None:
        if mode not in ("instance", "semantic", "panoptic"):
            raise ValueError(f"mode debe ser 'instance', 'semantic' o 'panoptic'. Recibido: {mode}")

        self.model_path = model_path
        self.mode = mode
        self.confidence = confidence
        self._model: Optional[Any] = None
        self._fallback = not _YOLO_AVAILABLE

        if device == "auto":
            if _YOLO_AVAILABLE:
                import torch
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                self.device = "cpu"
        else:
            self.device = device

        if not self._fallback:
            self._load_model()

        LOG.info(
            "[SegmentationDetector] Modo=%s | Device=%s | Fallback=%s",
            self.mode, self.device, self._fallback,
        )

    def _load_model(self) -> None:
        """Carga el modelo YOLOv8-seg. Descarga automáticamente si no existe."""
        try:
            self._model = YOLO(self.model_path)
            LOG.info(
                "[SegmentationDetector] Modelo cargado: %s | Clases: %d",
                self.model_path,
                len(self._model.names) if hasattr(self._model, "names") else 0,
            )
        except Exception as exc:
            LOG.error("[SegmentationDetector] Error cargando modelo: %s", exc)
            self._fallback = True
            self._model = None

    # ── Interfaz pública (compatible con detector_factory) ────────────────────

    def find_pose(
        self,
        img: np.ndarray,
        draw: bool = True,
    ) -> Tuple[np.ndarray, SegmentationResult]:
        """Ejecuta la segmentación sobre el frame y dibuja las máscaras.

        Args:
            img:  Frame BGR de entrada.
            draw: Si True, dibuja máscaras y etiquetas sobre el frame.

        Returns:
            (frame_anotado, SegmentationResult)
        """
        result = self.segment(img)
        frame_out = img.copy()
        if draw and not result.is_empty:
            frame_out = self.draw(frame_out, result)
        return frame_out, result

    def find_position(
        self,
        img: np.ndarray,
        results: Any,
        draw: bool = True,
    ) -> Tuple[List, Dict]:
        """Retorna lista de landmarks vacía y bbox del objeto más grande.

        Compatibilidad con la interfaz de PoseDetector / YoloFallDetector.
        """
        if not isinstance(results, SegmentationResult) or results.is_empty:
            return [], {}

        # Seleccionar la detección de mayor confianza como bbox "principal"
        best_idx = int(np.argmax(results.scores)) if results.scores else 0
        boxes = results.boxes
        if best_idx < len(boxes):
            b = boxes[best_idx]
            bbox = {
                "xmin": b[0], "ymin": b[1], "xmax": b[2], "ymax": b[3],
                "width":  b[2] - b[0],
                "height": b[3] - b[1],
                "is_falling": False,
                "confidence": results.scores[best_idx] if results.scores else 0.0,
            }
        else:
            bbox = {}

        return [], bbox

    # ── Segmentación ──────────────────────────────────────────────────────────

    def segment(self, frame: np.ndarray) -> SegmentationResult:
        """Ejecuta segmentación sin dibujar.

        Returns:
            SegmentationResult con máscaras, boxes, labels y scores.
        """
        if self._fallback or self._model is None:
            return self._segment_fallback(frame)

        try:
            raw = self._model(
                frame,
                conf=self.confidence,
                device=self.device,
                verbose=False,
            )
            return self._parse_results(raw, frame.shape[:2])
        except Exception as exc:
            LOG.exception("[SegmentationDetector] Error en inferencia: %s", exc)
            return SegmentationResult(mode=self.mode)

    def _parse_results(
        self,
        raw_results: Any,
        frame_shape: Tuple[int, int],
    ) -> SegmentationResult:
        """Convierte el resultado de ultralytics a SegmentationResult."""
        masks:  List[Any]       = []
        boxes:  List[List[int]] = []
        labels: List[str]       = []
        scores: List[float]     = []

        for r in raw_results:
            names = r.names if hasattr(r, "names") else {}
            # Extraer boxes
            if r.boxes is not None:
                for i, box in enumerate(r.boxes):
                    cls_id  = int(box.cls[0])
                    label   = names.get(cls_id, str(cls_id))
                    score   = float(box.conf[0])
                    xyxy    = box.xyxy[0].cpu().numpy().astype(int).tolist()
                    boxes.append(xyxy)
                    labels.append(label)
                    scores.append(score)

                    # Máscara de segmentación
                    if r.masks is not None and i < len(r.masks.data):
                        mask_raw = r.masks.data[i].cpu().numpy()
                        mask_resized = cv2.resize(
                            mask_raw,
                            (frame_shape[1], frame_shape[0]),
                            interpolation=cv2.INTER_NEAREST,
                        )
                        masks.append(mask_resized > 0.5)
                    else:
                        masks.append(None)

        if self.mode == "semantic":
            boxes, labels, scores, masks = _merge_semantic(boxes, labels, scores, masks)

        return SegmentationResult(
            masks=masks, boxes=boxes, labels=labels,
            scores=scores, mode=self.mode, raw=raw_results,
        )

    def _segment_fallback(self, frame: np.ndarray) -> SegmentationResult:
        """Fallback sin ultralytics: retorna resultado vacío."""
        return SegmentationResult(mode=self.mode)

    # ── Dibujo ────────────────────────────────────────────────────────────────

    def draw(
        self,
        frame: np.ndarray,
        result: SegmentationResult,
        alpha: float = 0.40,
    ) -> np.ndarray:
        """Dibuja máscaras semitransparentes y etiquetas sobre el frame.

        Args:
            frame:  Frame BGR a anotar (modificado in-place).
            result: SegmentationResult de segment().
            alpha:  Transparencia de las máscaras (0=invisible, 1=opaco).

        Returns:
            Frame anotado.
        """
        overlay = frame.copy()

        for i, (mask, box, label, score) in enumerate(
            zip(result.masks, result.boxes, result.labels, result.scores)
        ):
            color = _PALETTE[i % len(_PALETTE)]

            # Máscara coloreada
            if mask is not None:
                colored = np.zeros_like(frame)
                colored[mask] = color
                cv2.addWeighted(colored, alpha, overlay, 1.0, 0, overlay)

            # Bounding box
            if box and len(box) == 4:
                cv2.rectangle(overlay, (box[0], box[1]), (box[2], box[3]), color, 2)
                # Etiqueta
                text = f"{label} {score:.0%}"
                cv2.putText(
                    overlay, text, (box[0], max(box[1] - 6, 14)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, color, 1, cv2.LINE_AA,
                )

        # En modo panóptico distinguir stuff vs things con leyenda
        if result.mode == "panoptic":
            cv2.putText(
                overlay, "PANOPTIC",
                (10, frame.shape[0] - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 200, 0), 1, cv2.LINE_AA,
            )

        frame[:] = overlay
        return frame

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def close(self) -> None:
        """Libera recursos del modelo."""
        self._model = None

    def __enter__(self) -> "SegmentationDetector":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


# ──────────────────────────────────────────────────────────────────────────────
# Utilidades privadas
# ──────────────────────────────────────────────────────────────────────────────

def _merge_semantic(
    boxes: List[List[int]],
    labels: List[str],
    scores: List[float],
    masks: List[Any],
) -> Tuple[List, List, List, List]:
    """Agrupa detecciones del mismo tipo en modo semántico."""
    merged: Dict[str, Dict] = {}
    for box, label, score, mask in zip(boxes, labels, scores, masks):
        if label not in merged:
            merged[label] = {"boxes": [], "scores": [], "masks": [], "best_score": 0.0}
        merged[label]["boxes"].append(box)
        merged[label]["scores"].append(score)
        merged[label]["masks"].append(mask)
        if score > merged[label]["best_score"]:
            merged[label]["best_score"] = score

    out_boxes, out_labels, out_scores, out_masks = [], [], [], []
    for label, data in merged.items():
        # Bbox envolvente de todos los objetos de la misma clase
        all_boxes = data["boxes"]
        xmin = min(b[0] for b in all_boxes)
        ymin = min(b[1] for b in all_boxes)
        xmax = max(b[2] for b in all_boxes)
        ymax = max(b[3] for b in all_boxes)
        out_boxes.append([xmin, ymin, xmax, ymax])
        out_labels.append(label)
        out_scores.append(data["best_score"])
        # Unión de todas las máscaras de la clase
        valid = [m for m in data["masks"] if m is not None]
        if valid:
            combined = np.zeros_like(valid[0], dtype=bool)
            for m in valid:
                combined |= m
            out_masks.append(combined)
        else:
            out_masks.append(None)

    return out_boxes, out_labels, out_scores, out_masks
