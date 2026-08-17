"""C4 Aqua — solo type=pool; 0 eventos fuera de agua; Notify alert_level=2."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.zone_geometry import AQUA_ZONE_TYPES, ZoneOccupancyMonitor


class _Z:
    def __init__(self, zid: str, ztype: str, points: list) -> None:
        self.id = zid
        self.label = zid
        self.type = ztype
        self.critical = ztype == "pool"
        self.points = points
        self.normalized = True


def test_aqua_filters_non_pool_zones() -> None:
    pool = _Z("pool_1", "pool", [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]])
    yard = _Z("yard_1", "geofence", [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    monitor = ZoneOccupancyMonitor(
        [pool, yard],
        min_iou=0.1,
        min_persistence_frames=2,
        cooldown_sec=0.0,
        allowed_types=AQUA_ZONE_TYPES,
    )
    assert len(monitor.zones) == 1
    assert monitor.zones[0].id == "pool_1"


def test_aqua_no_event_outside_pool() -> None:
    """Persona en patio (fuera de piscina) → 0 eventos con filtro aqua."""
    pool = _Z("pool_1", "pool", [[0.0, 0.0], [0.3, 0.0], [0.3, 0.3], [0.0, 0.3]])
    yard = _Z("yard_1", "geofence", [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    monitor = ZoneOccupancyMonitor(
        [pool, yard],
        min_iou=0.1,
        min_persistence_frames=2,
        cooldown_sec=0.0,
        allowed_types=AQUA_ZONE_TYPES,
    )
    # Bbox en esquina opuesta a la piscina
    bbox = {"xmin": 70, "ymin": 70, "xmax": 95, "ymax": 95}
    assert monitor.update(bbox, 100, 100, frame_idx=1, camera_id="CAM_AQUA") is None
    assert monitor.update(bbox, 100, 100, frame_idx=2, camera_id="CAM_AQUA") is None


def test_aqua_pool_event_notify_and_iso() -> None:
    pool = _Z("pool_1", "pool", [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]])
    monitor = ZoneOccupancyMonitor(
        [pool],
        min_iou=0.1,
        min_persistence_frames=2,
        cooldown_sec=0.0,
        allowed_types=AQUA_ZONE_TYPES,
    )
    bbox = {"xmin": 30, "ymin": 30, "xmax": 70, "ymax": 70}
    assert monitor.update(bbox, 100, 100, frame_idx=1, camera_id="CAM_AQUA") is None
    evt = monitor.update(bbox, 100, 100, frame_idx=2, camera_id="CAM_AQUA")
    assert evt is not None
    assert evt["event_type"] == "pool_occupancy"
    assert evt["alert_level"] == 2  # Notify
    assert evt["event_schema_version"] == "2.0"
    assert evt["metadata"]["product"] == "aqua"
    assert evt["metadata"]["demographics"] is False
    assert "T" in evt["timestamp"] and (
        evt["timestamp"].endswith("Z") or "+" in evt["timestamp"] or evt["timestamp"].count("-") >= 2
    )
