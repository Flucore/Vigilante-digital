"""Tests Care / EventLogger canónico (C2)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from outputs.event_logger import (
    EventLogger,
    enrich_canonical_event,
    resolve_is_falling,
)


def test_resolve_prefers_detector_false_over_ratio() -> None:
    """YOLO dice no caída aunque el ratio sea 'bajo' → no forzar fallback."""
    bbox = {
        "xmin": 0, "ymin": 0, "xmax": 100, "ymax": 40,
        "width": 100, "height": 40, "is_falling": False,
    }
    flag, source = resolve_is_falling(bbox)
    assert flag is False
    assert source == "detector"


def test_resolve_prefers_detector_true() -> None:
    bbox = {
        "xmin": 0, "ymin": 0, "xmax": 50, "ymax": 100,
        "width": 50, "height": 100, "is_falling": True,
    }
    flag, source = resolve_is_falling(bbox)
    assert flag is True
    assert source == "detector"


def test_resolve_ratio_fallback_when_missing() -> None:
    bbox = {"xmin": 0, "ymin": 0, "xmax": 100, "ymax": 40, "width": 100, "height": 40}
    flag, source = resolve_is_falling(bbox)
    assert flag is True
    assert source == "aspect_ratio_fallback"


def test_event_logger_emits_canonical_fields() -> None:
    path = ROOT / "test_outputs" / "test_care_events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    logger = EventLogger(path)
    assert logger.update(True, 1, photo_path="snap.jpg", metadata={"fall_signal": "detector"}) is None
    evt = logger.update(False, 10)
    assert evt is not None
    assert evt["event_type"] == "fall"
    assert evt["event_schema_version"] == "2.0"
    assert "timestamp" in evt
    assert "compliance" in evt
    enriched = enrich_canonical_event(
        evt,
        camera_id="CAM_1",
        zone="Bodega",
        sector="Norte",
        alert_level=2,
        photo_path="snap.jpg",
    )
    assert enriched["camera_id"] == "CAM_1"
    assert enriched["zone"] == "Bodega"
    assert enriched["sector"] == "Norte"
    assert enriched["photo_path"] == "snap.jpg"
    assert enriched["compliance"]["retention_days"] >= 1
    logger.log_event(enriched)
    stored = logger.get_events()
    assert len(stored) == 1
    assert stored[0]["event_schema_version"] == "2.0"
