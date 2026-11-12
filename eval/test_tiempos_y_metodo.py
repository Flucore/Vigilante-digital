"""Tests de los puntos 1 (tiempos por frame) y 2 (--metodo) de ESPECIFICACIONES.md."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from outputs.event_logger import EventLogger, resolve_is_falling


def test_evento_con_fps_usa_tiempo_de_video(tmp_path: Path) -> None:
    logger = EventLogger(tmp_path / "ev.jsonl", fps=30.0)
    assert logger.update(True, 31) is None          # frame 31 → 1.0 s
    evt = logger.update(False, 61)                   # último frame en caída: 60
    assert evt is not None
    assert evt["fps"] == 30.0
    assert evt["inicio_video_s"] == 1.0
    assert evt["fin_video_s"] == 59 / 30.0
    assert evt["duration_seconds"] == 1.0            # frames 31..60 = 30 frames
    assert evt["start_frame"] == 31 and evt["end_frame"] == 60


def test_primer_frame_es_cero_segundos(tmp_path: Path) -> None:
    logger = EventLogger(tmp_path / "ev.jsonl", fps=25.0)
    logger.update(True, 1)
    evt = logger.update(False, 2)
    assert evt["inicio_video_s"] == 0.0


def test_finalize_con_ultimo_frame(tmp_path: Path) -> None:
    logger = EventLogger(tmp_path / "ev.jsonl", fps=10.0)
    logger.update(True, 11)
    evt = logger.finalize(last_frame_idx=30)
    assert evt is not None
    assert evt["finalized_forced"] is True
    assert evt["end_frame"] == 30
    assert evt["inicio_video_s"] == 1.0
    assert evt["fin_video_s"] == 2.9
    assert evt["duration_seconds"] == 2.0


def test_sin_fps_no_cambia_el_evento(tmp_path: Path) -> None:
    logger = EventLogger(tmp_path / "ev.jsonl")
    logger.update(True, 1)
    evt = logger.update(False, 10)
    assert evt is not None
    for campo in ("fps", "inicio_video_s", "fin_video_s"):
        assert campo not in evt
    assert logger.finalize() is None


def test_metodo_bbox_usa_solo_proporcion() -> None:
    """El runner en modo bbox quita is_falling: la decisión es solo alto/ancho."""
    bbox_detector = {"xmin": 0, "ymin": 0, "xmax": 100, "ymax": 40,
                     "width": 100, "height": 40, "is_falling": False}
    bbox_metodo = {k: v for k, v in bbox_detector.items() if k != "is_falling"}
    assert resolve_is_falling(bbox_detector) == (False, "detector")
    assert resolve_is_falling(bbox_metodo) == (True, "aspect_ratio_fallback")
