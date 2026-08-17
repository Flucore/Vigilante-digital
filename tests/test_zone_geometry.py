"""Tests unitarios M0 — IoU bbox ∩ zona (sin cámara ni GPU)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.zone_geometry import ZoneOccupancyMonitor, bbox_zone_iou


class _Z:
    def __init__(self, zid: str, ztype: str, points: list) -> None:
        self.id = zid
        self.label = zid
        self.type = ztype
        self.critical = False
        self.points = points
        self.normalized = True


def test_iou_inside_high() -> None:
    """Bbox centrado dentro del polígono → IoU > 0."""
    bbox = {"xmin": 40, "ymin": 40, "xmax": 60, "ymax": 60}
    # Zona que cubre casi todo el frame 100x100
    zone = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
    iou = bbox_zone_iou(bbox, zone, 100, 100, normalized=True)
    assert iou > 0.0
    assert iou <= 1.0


def test_iou_outside_zero() -> None:
    """Bbox fuera de la zona → IoU == 0."""
    bbox = {"xmin": 80, "ymin": 80, "xmax": 95, "ymax": 95}
    zone = [[0.0, 0.0], [0.3, 0.0], [0.3, 0.3], [0.0, 0.3]]
    iou = bbox_zone_iou(bbox, zone, 100, 100, normalized=True)
    assert iou == 0.0


def test_iou_edge_partial() -> None:
    """Bbox parcialmente sobre el borde → 0 < IoU < 1."""
    bbox = {"xmin": 20, "ymin": 20, "xmax": 50, "ymax": 50}
    zone = [[0.0, 0.0], [0.4, 0.0], [0.4, 0.4], [0.0, 0.4]]
    iou = bbox_zone_iou(bbox, zone, 100, 100, normalized=True)
    assert 0.0 < iou < 1.0


def test_monitor_emits_after_persistence() -> None:
    zone = _Z("pool_1", "pool", [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]])
    monitor = ZoneOccupancyMonitor(
        [zone],
        min_iou=0.1,
        min_persistence_frames=3,
        cooldown_sec=0.0,
    )
    bbox = {"xmin": 30, "ymin": 30, "xmax": 70, "ymax": 70}
    assert monitor.update(bbox, 100, 100, frame_idx=1, camera_id="CAM_T") is None
    assert monitor.update(bbox, 100, 100, frame_idx=2, camera_id="CAM_T") is None
    evt = monitor.update(bbox, 100, 100, frame_idx=3, camera_id="CAM_T")
    assert evt is not None
    assert evt["event_type"] == "pool_occupancy"
    assert evt["event_schema_version"] == "2.0"
    assert evt["camera_id"] == "CAM_T"
    assert "zone_iou" in evt["metadata"]
    assert evt["metadata"]["memory"] == "M0"


def test_monitor_empty_zone_no_event() -> None:
    zone = _Z("pool_1", "pool", [[0.0, 0.0], [0.2, 0.0], [0.2, 0.2], [0.0, 0.2]])
    monitor = ZoneOccupancyMonitor(
        [zone], min_iou=0.2, min_persistence_frames=2, cooldown_sec=0.0
    )
    bbox = {"xmin": 80, "ymin": 80, "xmax": 99, "ymax": 99}
    assert monitor.update(bbox, 100, 100, frame_idx=1) is None
    assert monitor.update(bbox, 100, 100, frame_idx=2) is None
