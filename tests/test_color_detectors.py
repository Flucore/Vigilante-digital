from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.color_detectors import RedShirtDetector, TrafficLightDetector


def test_red_shirt_detector_triggers_after_presence_window() -> None:
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    cv2.rectangle(frame, (80, 60), (240, 190), (0, 0, 255), -1)

    detector = RedShirtDetector(
        min_presence_sec=0.05,
        min_area_ratio=0.02,
        cooldown_sec=1.0,
    )

    first = detector.update(frame, camera_id="CAM_TEST", zone="Lab")
    assert first.detected
    assert first.event is None

    time.sleep(0.06)
    second = detector.update(frame, camera_id="CAM_TEST", zone="Lab")
    assert second.event is not None
    assert second.event["event_type"] == "red_shirt_entry"
    assert second.event["camera_id"] == "CAM_TEST"


def test_traffic_light_detector_reports_color_change() -> None:
    detector = TrafficLightDetector(
        roi=(0, 0, 120, 120),
        min_stable_sec=0.01,
        min_color_ratio=0.02,
    )

    red = np.zeros((120, 120, 3), dtype=np.uint8)
    cv2.circle(red, (60, 60), 35, (0, 0, 255), -1)
    detector.update(red, camera_id="SEM", zone="Lab")
    time.sleep(0.02)
    first_event = detector.update(red, camera_id="SEM", zone="Lab")
    assert first_event.event is not None
    assert first_event.event["metadata"]["current_color"] == "red"

    green = np.zeros((120, 120, 3), dtype=np.uint8)
    cv2.circle(green, (60, 60), 35, (0, 255, 0), -1)
    detector.update(green, camera_id="SEM", zone="Lab")
    time.sleep(0.02)
    change_event = detector.update(green, camera_id="SEM", zone="Lab")

    assert change_event.event is not None
    assert change_event.event["event_type"] == "traffic_light_change"
    assert change_event.event["metadata"]["previous_color"] == "red"
    assert change_event.event["metadata"]["current_color"] == "green"
