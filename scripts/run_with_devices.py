"""Demo runner that integrates devices (IP speaker, ESP32, USB) with the
fall-detection pipeline and lets you switch between MP4 and IP camera on the fly.

Usage examples:
  # Show an MP4 file
  python scripts/run_with_devices.py --file tests/test_videos/fall_sample_01.mp4

  # Use IP camera
  python scripts/run_with_devices.py --ip "http://10.139.192.20:8080/video"

  # Both: allow toggle between file and ip with the 't' key
  python scripts/run_with_devices.py --file tests/test_videos/fall_sample_01.mp4 --ip "http://10.139.192.20:8080/video"

When an event is completed, the demo will:
 - save event to local EventLogger
 - attempt to sync via FirebaseConnector (if credentials configured)
 - play an alert via IpSpeaker (if provided)
 - publish a message to ESP32 (MQTT or TCP if configured)
 - write a message to USB serial (if provided)

This script is intended for demo/presentation (v7 demo).
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2

from core.pose_detector import PoseDetector
from inputs.video_stream import VideoStream
from outputs.event_logger import EventLogger
from outputs.firebase_connector import FirebaseConnector
from inputs.ip_speaker import IpSpeaker
from inputs.esp32_client import MQTTClient, TcpClient
from inputs.usb_reader import SerialReader
from outputs.report_generator import ReportGenerator
import config

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("run_with_devices")


def open_file_cap(path: str):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video file: {path}")
    return cap


def main(
    file: Optional[str],
    ip: Optional[str],
    speaker: Optional[str],
    mqtt: Optional[str],
    mqtt_topic: Optional[str],
    tcp: Optional[str],
    tcp_port: Optional[int],
    serial_port: Optional[str],
    no_firebase: bool,
    frame_scale: float = 0.6,
    detection_skip: int = 2,
    complexity: int = 0,
):
    # Crear detector con parámetros optimizados para streaming.
    detector = PoseDetector(complexity=complexity, frame_scale=frame_scale)
    event_logger = EventLogger()
    report_gen = ReportGenerator(camera_name="Demo Cam", sector="Sector Demo")

    connector = None
    if not no_firebase:
        try:
            connector = FirebaseConnector(json_log_path=str(event_logger.path), collection=None)
        except Exception as exc:
            LOG.warning("FirebaseConnector init failed (continuing without Firebase): %s", exc)

    speaker_ctl = None
    if speaker:
        speaker_ctl = IpSpeaker(speaker)

    mqtt_client = None
    tcp_client = None
    if mqtt:
        try:
            broker = mqtt
            topic = mqtt_topic or "esp32/alerts"
            mqtt_client = MQTTClient(broker=broker, port=1883, topic=topic)
            mqtt_client.start(on_message=lambda p: LOG.info("MQTT msg: %s", p))
        except Exception as exc:
            LOG.warning("Failed to start MQTTClient: %s", exc)

    if tcp:
        try:
            tcp_client = TcpClient(host=tcp, port=int(tcp_port or 9000))
            tcp_client.start(on_message=lambda p: LOG.info("TCP msg: %s", p))
        except Exception as exc:
            LOG.warning("Failed to start TcpClient: %s", exc)

    serial_writer = None
    serial_reader = None
    if serial_port:
        try:
            # Start reader for incoming serial lines
            serial_reader = SerialReader(port=serial_port)
            serial_reader.start(callback=lambda line: LOG.info("USB IN: %s", line))
            # Open a writer for sending (pyserial used inside SerialReader module)
            try:
                import serial as _pyserial
                serial_writer = _pyserial.Serial(serial_port, 115200, timeout=0.1)
            except Exception:
                serial_writer = None
        except Exception as exc:
            LOG.warning("Serial port init failed: %s", exc)

    # Capture sources
    file_cap = None
    ip_stream = None
    using_file = False

    # Prefer IP camera if provided and reachable. Try to open IP stream first
    # and only fall back to file if IP is not available. This avoids always
    # showing the local MP4 when user expects the phone stream.
    if ip:
        ip_stream = VideoStream(ip)
        if ip_stream.open():
            LOG.info("IP stream opened successfully; using IP camera as source")
            using_file = False
        else:
            LOG.warning("IP stream unavailable; will try local file if provided")
            ip_stream.close()

    if file and (ip_stream is None or not ip_stream._opened):
        # Only open file if IP is not available or not provided
        file_cap = open_file_cap(file)
        using_file = True

    LOG.info("Demo ready. Press 'q' to quit, 't' to toggle source (file<->ip), 'p' to force play alert")

    p_time = time.time()
    frame_idx = 0

    try:
        while True:
            # Read frame from current source
            if using_file and file_cap:
                ok, frame = file_cap.read()
                if not ok:
                    LOG.info("End of file reached")
                    break
            elif ip_stream:
                ok, frame = ip_stream.read()
                if not ok:
                    LOG.warning("No frame from IP stream")
                    time.sleep(0.2)
                    continue
            else:
                LOG.error("No video source available")
                break

            frame_idx += 1

            # Procesamiento optimizado: solo ejecutamos MediaPipe cada N frames
            # (configurable con --detection-skip). Entre detecciones reutilizamos
            # el último bbox para dibujar y mantenemos la carga de CPU baja.
            do_detection = (detection_skip <= 1) or (frame_idx % detection_skip == 0)
            if do_detection:
                proc_frame, results = detector.find_pose(frame, draw=True)
                lm_list, bbox = detector.find_position(proc_frame, results, draw=True)
                last_bbox = bbox
            else:
                proc_frame = frame.copy()
                bbox = locals().get('last_bbox', None)

            is_falling = False
            aspect_ratio = None
            if bbox:
                aspect_ratio = bbox.get("height", 0) / max(1, bbox.get("width", 1))
                is_falling = aspect_ratio < 0.8

            # Actualizar logger de eventos solo cuando hicimos detección
            completed_event = None
            if do_detection:
                completed_event = event_logger.update(is_falling=is_falling, frame_idx=frame_idx, photo_path=None, metadata={"aspect_ratio": aspect_ratio})
            
            # Visual feedback on screen
            if bbox:
                if is_falling:
                    # Red box + CAYENDO text when falling
                    cv2.rectangle(proc_frame, (bbox["xmin"], bbox["ymin"]), (bbox["xmax"], bbox["ymax"]), (0, 0, 255), 3)
                    cv2.putText(proc_frame, "CAYENDO...", (bbox["xmin"], bbox["ymin"] - 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                else:
                    # Green box when standing normally
                    cv2.rectangle(proc_frame, (bbox["xmin"], bbox["ymin"]), (bbox["xmax"], bbox["ymax"]), (0, 255, 0), 2)
            
            if completed_event:
                LOG.info("Event completed: %s", completed_event)
                # Draw event completion notification (yellow text at top)
                cv2.putText(proc_frame, f"EVENTO COMPLETADO - Duracion: {completed_event.get('duration_seconds', 0):.1f}s", 
                           (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
                # Guardar último evento y frame para generación de reporte bajo demanda
                last_completed_event = completed_event
                try:
                    last_event_frame = proc_frame.copy()
                except Exception:
                    last_event_frame = None

                # Local save (EventLogger handles writing to history/log)
                event_logger.log_event(completed_event)
                # Firebase: connector is responsible to sync new events from
                # the JSON history. We do NOT call a non-existent
                # `log_event` method on the connector.
                if connector:
                    try:
                        # Attempt a sync of any pending events
                        uploaded = connector.sync_new_events()
                        LOG.info("Firebase sync: %d events uploaded", uploaded)
                    except Exception:
                        LOG.exception("Failed to sync event to Firebase")
                # Speaker
                if speaker_ctl:
                    try:
                        # If speaker configured with an URL to an alert MP3, use it
                        speaker_ctl.play_url(speaker)
                    except Exception:
                        LOG.exception("Speaker action failed")
                # MQTT/TCP
                if mqtt_client:
                    try:
                        mqtt_client.publish(str(completed_event))
                    except Exception:
                        LOG.exception("MQTT publish failed")
                if tcp_client:
                    try:
                        tcp_client.send(str(completed_event))
                    except Exception:
                        LOG.exception("TCP send failed")
                # Serial write
                if serial_writer:
                    try:
                        serial_writer.write((str(completed_event) + "\n").encode())
                        serial_writer.flush()
                    except Exception:
                        LOG.exception("Serial write failed")

            # Overlay FPS and show
            c_time = time.time()
            fps = 1.0 / max(1e-6, (c_time - p_time))
            p_time = c_time
            cv2.putText(proc_frame, f'FPS: {int(fps)}', (20, 70), cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 0), 3)

            # Mostrar el frame original (evitar redimensionado constante que consume CPU)
            frame_show = proc_frame

            if config.HEADLESS_MODE:
                key = -1
            else:
                cv2.imshow("Vigilante Demo - Devices", frame_show)
                key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('t') and file and ip:
                using_file = not using_file
                LOG.info("Toggled source. Now using_file=%s", using_file)
            elif key == ord('p'):
                LOG.info("Manual alert trigger")
                # Trigger a manual event effect
                fake_event = {"event_type": "manual_alert", "time": time.time()}
                if speaker_ctl:
                    try:
                        speaker_ctl.play_url(speaker)
                    except Exception:
                        LOG.exception("Speaker play failed")
            elif key == ord('d'):
                # Generar reporte PDF del último evento (si existe)
                if 'last_completed_event' in locals() and last_completed_event:
                    LOG.info("Generando reporte PDF del último evento...")
                    pdf_path = report_gen.generate_report(event=last_completed_event, frame_image=locals().get('last_event_frame', None), output_dir="reports")
                    if pdf_path:
                        LOG.info("Reporte guardado: %s", pdf_path)
                    else:
                        LOG.error("Fallo al generar reporte PDF")
                else:
                    LOG.warning("No hay evento disponible para generar reporte")

    finally:
        if not config.HEADLESS_MODE:
            cv2.destroyAllWindows()
        if file_cap:
            file_cap.release()
        if ip_stream:
            ip_stream.close()
        if mqtt_client:
            mqtt_client.stop()
        if tcp_client:
            tcp_client.stop()
        if serial_reader:
            serial_reader.stop()
        if serial_writer:
            try:
                serial_writer.close()
            except Exception:
                pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run demo with devices and switchable video source")
    parser.add_argument('--file', help='Path to local MP4 file')
    parser.add_argument('--ip', help='IP camera URL (e.g. http://10.0.0.2:8080/video)')
    parser.add_argument('--speaker', help='IpSpeaker host (e.g. http://10.0.0.50:5000). Also used as default mp3 play url if you pass a full mp3 url here')
    parser.add_argument('--mqtt', help='MQTT broker address for ESP32')
    parser.add_argument('--mqtt-topic', help='MQTT topic (default esp32/alerts)')
    parser.add_argument('--tcp', help='ESP32 TCP host (IP)')
    parser.add_argument('--tcp-port', type=int, help='ESP32 TCP port (default 9000)')
    parser.add_argument('--serial', help='Serial port (COMx) for USB device')
    parser.add_argument('--no-firebase', action='store_true', help='Do not initialize FirebaseConnector')
    parser.add_argument('--frame-scale', type=float, default=0.6, help='Frame scale for processing (0.5 = half resolution)')
    parser.add_argument('--detection-skip', type=int, default=2, help='Process every Nth frame with MediaPipe (>=1)')
    parser.add_argument('--complexity', type=int, default=0, help='MediaPipe model complexity (0,1,2)')
    args = parser.parse_args()

    main(
        file=args.file,
        ip=args.ip,
        speaker=args.speaker,
        mqtt=args.mqtt,
        mqtt_topic=args.mqtt_topic,
        tcp=args.tcp,
        tcp_port=args.tcp_port,
        serial_port=args.serial,
        no_firebase=args.no_firebase,
        frame_scale=args.frame_scale,
        detection_skip=args.detection_skip,
        complexity=args.complexity,
    )
