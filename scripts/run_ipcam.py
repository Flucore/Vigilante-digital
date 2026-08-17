"""Run the main pose detector against an IP camera stream (mobile phone).

Usage:
    python scripts/run_ipcam.py --source http://10.139.192.20:8080/video

If `--source` is omitted, uses `config.VIDEO_SOURCE`.
"""
from __future__ import annotations

import argparse
import logging
import time
from typing import Optional

import cv2
import sys
from pathlib import Path

# Ensure project root is on sys.path when running script directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.pose_detector import PoseDetector
from inputs.video_stream import VideoStream
import config


logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)


def main(source: Optional[str] = None) -> None:
    src = source or config.VIDEO_SOURCE
    LOG.info("Starting IP camera stream from: %s", src)

    detector = PoseDetector(complexity=1)

    stream = VideoStream(src, reconnect_attempts=5, reconnect_delay=1.0)

    with stream:
        p_time = time.time()
        frame_idx = 0
        while True:
            ok, frame = stream.read()
            if not ok:
                LOG.warning("No frame received. Waiting before retrying...")
                time.sleep(0.5)
                continue

            frame_idx += 1
            proc_frame, results = detector.find_pose(frame, draw=True)
            lm_list, bbox = detector.find_position(proc_frame, results, draw=True)

            # Overlay info
            c_time = time.time()
            fps = 1.0 / max(1e-6, (c_time - p_time))
            p_time = c_time
            cv2.putText(proc_frame, f'FPS: {int(fps)}', (20, 70), cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 0), 3)

            try:
                frame_show = cv2.resize(proc_frame, (1280, 720))
            except Exception:
                frame_show = proc_frame

            if not config.HEADLESS_MODE:
                cv2.imshow("Vigilante IA - IP Cam", frame_show)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    LOG.info("User requested exit")
                    break

    if not config.HEADLESS_MODE:
        cv2.destroyAllWindows()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run VigilanteDigital against IP camera stream")
    parser.add_argument('--source', help='Video source (URL or index). Overrides config.VIDEO_SOURCE')
    args = parser.parse_args()
    main(args.source)
