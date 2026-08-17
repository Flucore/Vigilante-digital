"""Geometría de zonas M0 — intersección bbox ∩ polígono + persistencia temporal.

Memoria geométrica (calibrar ≠ entrenar): las zonas viven en config, no en pesos .pt.
SAM/SAM2 no se usan aquí; solo polígonos ya calibrados.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import cv2
import numpy as np

LOG = logging.getLogger(__name__)

# Tipos de zona M0 (SiteZoneMask en config)
M0_ZONE_TYPES = frozenset({
    "polygon",
    "geofence",
    "pool",
    "wall",
    "coop",
    "machine_yard",
    "custom",
})

# Aqua (C4): solo ocupación piscina — sin demografía / edad / “niño”
AQUA_ZONE_TYPES = frozenset({"pool"})

_COLOR_ZONE = (0, 200, 255)
_COLOR_POOL = (255, 180, 0)  # BGR cian-ámbar: piscina
_COLOR_ALERT = (0, 0, 255)


def bbox_dict_to_xyxy(bbox: Dict[str, Any]) -> Tuple[int, int, int, int]:
    """Normaliza bbox dict a (xmin, ymin, xmax, ymax) enteros."""
    if all(k in bbox for k in ("xmin", "ymin", "xmax", "ymax")):
        return (
            int(bbox["xmin"]),
            int(bbox["ymin"]),
            int(bbox["xmax"]),
            int(bbox["ymax"]),
        )
    if "bbox" in bbox and isinstance(bbox["bbox"], (list, tuple)) and len(bbox["bbox"]) == 4:
        x1, y1, x2, y2 = bbox["bbox"]
        return int(x1), int(y1), int(x2), int(y2)
    raise ValueError("bbox debe incluir xmin/ymin/xmax/ymax")


def points_to_contour(
    points: Sequence[Sequence[float]],
    width: int,
    height: int,
    *,
    normalized: bool = True,
) -> np.ndarray:
    """Convierte puntos de zona a contorno cv2 (Nx1x2 int32)."""
    if len(points) < 3:
        raise ValueError("Una zona M0 requiere al menos 3 puntos")
    if normalized:
        pts = [[int(p[0] * width), int(p[1] * height)] for p in points]
    else:
        pts = [[int(p[0]), int(p[1])] for p in points]
    return np.array(pts, dtype=np.int32).reshape((-1, 1, 2))


def bbox_zone_iou(
    bbox: Dict[str, Any],
    zone_points: Sequence[Sequence[float]],
    frame_width: int,
    frame_height: int,
    *,
    normalized: bool = True,
) -> float:
    """IoU entre el rectángulo del bbox y el polígono de zona (máscaras binarias).

    Returns:
        Valor en [0.0, 1.0]. 0.0 si no hay intersección o inputs inválidos.
    """
    try:
        x1, y1, x2, y2 = bbox_dict_to_xyxy(bbox)
        contour = points_to_contour(
            zone_points, frame_width, frame_height, normalized=normalized
        )
    except (ValueError, TypeError, IndexError) as exc:
        LOG.debug("bbox_zone_iou: input inválido — %s", exc)
        return 0.0

    if frame_width <= 0 or frame_height <= 0:
        return 0.0
    if x2 <= x1 or y2 <= y1:
        return 0.0

    h, w = frame_height, frame_width
    zone_mask = np.zeros((h, w), dtype=np.uint8)
    bbox_mask = np.zeros((h, w), dtype=np.uint8)

    cv2.fillPoly(zone_mask, [contour], 1)
    cv2.rectangle(bbox_mask, (x1, y1), (x2, y2), 1, thickness=-1)

    inter = int(np.count_nonzero((zone_mask > 0) & (bbox_mask > 0)))
    if inter == 0:
        return 0.0
    union = int(np.count_nonzero((zone_mask > 0) | (bbox_mask > 0)))
    if union <= 0:
        return 0.0
    return float(inter) / float(union)


def draw_zones(
    frame: np.ndarray,
    zones: Iterable[Any],
    *,
    active_zone_ids: Optional[Iterable[str]] = None,
) -> np.ndarray:
    """Dibuja polígonos M0 sobre el frame. `zones` con .points, .type, .id, .label, .normalized."""
    h, w = frame.shape[:2]
    active = set(active_zone_ids or [])
    for zone in zones:
        ztype = getattr(zone, "type", "polygon")
        if ztype not in M0_ZONE_TYPES and ztype != "polygon":
            continue
        points = getattr(zone, "points", None) or []
        if len(points) < 3:
            continue
        normalized = bool(getattr(zone, "normalized", True))
        try:
            contour = points_to_contour(points, w, h, normalized=normalized)
        except ValueError:
            continue
        idle = _COLOR_POOL if ztype == "pool" else _COLOR_ZONE
        color = _COLOR_ALERT if getattr(zone, "id", "") in active else idle
        cv2.polylines(frame, [contour], isClosed=True, color=color, thickness=2)
        label = f"{getattr(zone, 'label', zone.id)} [{ztype}]"
        x0, y0 = int(contour[0, 0, 0]), int(contour[0, 0, 1])
        cv2.putText(
            frame, label, (x0, max(20, y0 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA,
        )
    return frame


@dataclass
class ZoneHit:
    """Resultado de ocupación de una zona en un frame."""

    zone_id: str
    zone_type: str
    zone_label: str
    iou: float
    critical: bool


class ZoneOccupancyMonitor:
    """Persiste ocupación bbox∩zona y emite un evento canónico al confirmarse.

    No entrena modelos. Solo aplica geometría + umbrales de config.
    """

    def __init__(
        self,
        zones: List[Any],
        *,
        min_iou: float = 0.15,
        min_persistence_frames: int = 8,
        cooldown_sec: float = 5.0,
        allowed_types: Optional[Iterable[str]] = None,
    ) -> None:
        type_filter: Optional[Set[str]] = None
        if allowed_types is not None:
            type_filter = {str(t) for t in allowed_types}
        self.allowed_types = type_filter
        self.zones = [
            z for z in zones
            if getattr(z, "type", "polygon") in M0_ZONE_TYPES
            and len(getattr(z, "points", []) or []) >= 3
            and (type_filter is None or getattr(z, "type", "polygon") in type_filter)
        ]
        self.min_iou = float(min_iou)
        self.min_persistence_frames = max(1, int(min_persistence_frames))
        self.cooldown_sec = float(cooldown_sec)
        self._streak: Dict[str, int] = defaultdict(int)
        self._last_emit: Dict[str, float] = {}

    def evaluate_frame(
        self,
        bbox: Dict[str, Any],
        frame_width: int,
        frame_height: int,
    ) -> List[ZoneHit]:
        """Calcula IoU contra todas las zonas M0 configuradas."""
        hits: List[ZoneHit] = []
        for zone in self.zones:
            iou = bbox_zone_iou(
                bbox,
                zone.points,
                frame_width,
                frame_height,
                normalized=bool(getattr(zone, "normalized", True)),
            )
            if iou >= self.min_iou:
                hits.append(ZoneHit(
                    zone_id=str(zone.id),
                    zone_type=str(getattr(zone, "type", "polygon")),
                    zone_label=str(getattr(zone, "label", zone.id)),
                    iou=iou,
                    critical=bool(getattr(zone, "critical", False)),
                ))
        return hits

    def update(
        self,
        bbox: Optional[Dict[str, Any]],
        frame_width: int,
        frame_height: int,
        *,
        frame_idx: int = 0,
        camera_id: str = "",
        site_zone: str = "",
        track_id: Any = None,
        now_ts: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Actualiza rachas de ocupación. Retorna evento o None.

        Emite como máximo un evento por llamada (la zona de mayor IoU que cruce umbral).
        """
        import time as _time

        now = now_ts if now_ts is not None else _time.time()
        if not bbox or not self.zones:
            self._streak.clear()
            return None

        hits = self.evaluate_frame(bbox, frame_width, frame_height)
        hit_ids = {h.zone_id for h in hits}

        for zid in list(self._streak.keys()):
            if zid not in hit_ids:
                self._streak[zid] = 0

        best: Optional[ZoneHit] = None
        for hit in hits:
            self._streak[hit.zone_id] += 1
            if self._streak[hit.zone_id] < self.min_persistence_frames:
                continue
            last = self._last_emit.get(hit.zone_id, 0.0)
            if now - last < self.cooldown_sec:
                continue
            if best is None or hit.iou > best.iou:
                best = hit

        if best is None:
            return None

        self._last_emit[best.zone_id] = now
        self._streak[best.zone_id] = 0
        ts = datetime.now(timezone.utc).isoformat()
        is_pool = best.zone_type == "pool"
        event_type = "pool_occupancy" if is_pool else "zone_occupancy"
        # Aqua: Notify (2). Sin clasificación demográfica / edad.
        alert_level = 2 if is_pool else 1
        product = "aqua" if is_pool else "geofence"

        return {
            "event_type": event_type,
            "event_schema_version": "2.0",
            "timestamp": ts,
            "start_time": ts,
            "end_time": ts,
            "duration_seconds": 0.0,
            "camera_id": camera_id,
            "zone": site_zone or best.zone_label,
            "alert_level": alert_level,
            "photo_path": None,
            "metadata": {
                "zone_id": best.zone_id,
                "zone_type": best.zone_type,
                "zone_label": best.zone_label,
                "zone_iou": round(best.iou, 4),
                "frame_idx": frame_idx,
                "track_id": track_id,
                "min_iou": self.min_iou,
                "min_persistence_frames": self.min_persistence_frames,
                "memory": "M0",
                "product": product,
                "demographics": False,
            },
            "compliance": {
                "retention_days": 30,
                "consent_basis": "security_monitoring",
            },
        }
