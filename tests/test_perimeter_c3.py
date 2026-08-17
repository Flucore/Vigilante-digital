"""Tests Perimeter Guard (C3)."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.perimeter_detector import PerimeterDetector
from outputs.event_logger import enrich_canonical_event


def test_perimeter_crossing_emits_event() -> None:
    det = PerimeterDetector(line_start=(50, 0), line_end=(50, 100), label="Test", cooldown_sec=0.0)
    assert det.update({"xmin": 10, "ymin": 40, "xmax": 30, "ymax": 60}, track_id=1) is None
    evt = det.update({"xmin": 70, "ymin": 40, "xmax": 90, "ymax": 60}, track_id=1)
    assert evt is not None
    assert evt["event_type"] == "perimeter_breach"
    assert evt["event_schema_version"] == "2.0"
    assert "timestamp" in evt


def test_perimeter_enrich_canonical() -> None:
    det = PerimeterDetector(line_start=(0, 50), line_end=(100, 50), cooldown_sec=0.0)
    det.update({"xmin": 40, "ymin": 10, "xmax": 60, "ymax": 30}, track_id=2)
    raw = det.update({"xmin": 40, "ymin": 70, "xmax": 60, "ymax": 90}, track_id=2)
    assert raw is not None
    enriched = enrich_canonical_event(
        raw, camera_id="CAM_P", zone="Patio", sector="Norte", alert_level=3, photo_path="x.jpg"
    )
    assert enriched["camera_id"] == "CAM_P"
    assert enriched["alert_level"] == 3
    assert enriched["compliance"]["retention_days"] >= 1


def test_trigger_manager_does_not_import_inputs() -> None:
    """Regla de capas: outputs/ no importa inputs/."""
    path = ROOT / "outputs" / "trigger_manager.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("inputs"), (
                f"Import prohibido en trigger_manager: from {node.module}"
            )
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("inputs"), (
                    f"Import prohibido en trigger_manager: import {alias.name}"
                )
