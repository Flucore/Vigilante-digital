"""Vigilante Digital — Runner Unificado v2.0

Orquestador principal con tres modos de operación:

  realtime  — Procesa streams en vivo (cámaras IP / webcam)
  file      — Procesa un archivo MP4/AVI con progreso visual (ideal para demo)
  batch     — Procesa archivo(s) sin UI, a máxima velocidad GPU, para indexación

Uso:
    python runner.py --mode file --source video_demo.mp4
    python runner.py --mode realtime --config client_config.json
    python runner.py --mode batch --source video.mp4 --headless

Teclas en modo realtime / file con ventana:
    q / ESC  → Salir
    p        → Generar PDF del último evento
    s        → Screenshot manual
    ESPACIO  → Pausar/Reanudar (solo modo file)
"""
from __future__ import annotations

import argparse
import logging
import os
import queue
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

# ── Asegurar root en sys.path ──────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Imports del proyecto ───────────────────────────────────────────────────────
from core.config_loader import ConfigLoader, CameraConfig, is_after_hours
from core.detector_factory import get_detector, detector_info
from core.perimeter_detector import PerimeterDetector
from core.zone_geometry import AQUA_ZONE_TYPES, ZoneOccupancyMonitor, draw_zones
from inputs.video_stream import VideoStream
from inputs.file_reader import FileVideoReader
from outputs.event_logger import EventLogger, enrich_canonical_event, resolve_is_falling
from outputs.hud_renderer import draw_hud, draw_no_signal, draw_hardware_trigger_overlay
from outputs.metadata_indexer import MetadataIndexer
from outputs.trigger_manager import TriggerManager
from outputs.report_generator import ReportGenerator
import config as app_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
LOG = logging.getLogger("vigilante.runner")

# Firebase opcional
try:
    from outputs.firebase_connector import FirebaseConnector
    _FIREBASE_AVAILABLE = True
except Exception:
    _FIREBASE_AVAILABLE = False

# Color detectors
try:
    from core.color_detectors import RedShirtDetector
    _COLOR_DETECTORS_AVAILABLE = True
except Exception:
    _COLOR_DETECTORS_AVAILABLE = False


def _m0_module_flags(modules_active: List[str], primary_module: str) -> tuple[bool, bool]:
    """Retorna (use_m0, use_aqua). Aqua (C4) restringe zonas a type=pool."""
    mods = modules_active or []
    use_aqua = primary_module == "aqua" or "aqua" in mods
    use_geofence = primary_module == "geofence" or "geofence" in mods
    return (use_aqua or use_geofence), use_aqua


def _dispatch_event_triggers(
    event: Dict[str, Any],
    trigger_manager: TriggerManager,
    *,
    report_dir: Path,
    pdf_cfg: Optional[Dict[str, Any]] = None,
    auto_pdf: bool = False,
) -> None:
    """Genera PDF (si aplica) y dispara triggers fuera del hilo de captura."""
    pdf_cfg = pdf_cfg or {}
    event_type = str(event.get("event_type", "event"))
    routes_by_event = trigger_manager.config.get("routes_by_event", {})
    routes = routes_by_event.get(event_type)
    if routes is None:
        routes = trigger_manager.config.get("default_routes", [])
    routes = list(routes or [])
    needs_pdf = bool(auto_pdf or ("email" in routes and trigger_manager.enabled))

    def _job() -> None:
        pdf_path: Optional[str] = None
        try:
            if needs_pdf:
                photo = event.get("photo_path") or event.get("photo_start")
                frame_img = None
                if photo and Path(str(photo)).exists():
                    frame_img = cv2.imread(str(photo))
                generator = ReportGenerator(
                    camera_name=str(event.get("camera_id", "CAM")),
                    sector=str(event.get("sector") or pdf_cfg.get("sector_label", "")),
                    facility=str(pdf_cfg.get("facility_name", "Instalación")),
                )
                result = generator.generate_report(
                    event=event,
                    frame_image=frame_img,
                    output_dir=str(report_dir),
                )
                if isinstance(result, str) and result:
                    pdf_path = result
                    event["pdf_path"] = pdf_path
        except Exception:
            LOG.exception("Error generando PDF para event_type=%s", event_type)
        try:
            trigger_manager.handle_event(event, pdf_path)
        except Exception:
            LOG.exception("Error despachando triggers")

    threading.Thread(target=_job, daemon=True, name="care-trigger").start()


# ══════════════════════════════════════════════════════════════════════════════
# Estado compartido de una cámara (thread-safe)
# ══════════════════════════════════════════════════════════════════════════════

class CameraState:
    """Estado compartido de una cámara, accedido por múltiples hilos."""

    def __init__(self, cam: CameraConfig) -> None:
        self.id = cam.id
        self.name = cam.name
        self.zone = cam.zone
        self.sector = cam.sector
        self.modules_active = cam.modules_active
        self.alert_level_after_hours = cam.alert_level_after_hours
        self.has_critical_zone = any(z.critical for z in cam.zones)

        self.frame: Optional[np.ndarray] = None
        self.fps: float = 0.0
        self.state: str = "SIN SEÑAL"
        self.events_count: int = 0
        self.last_event: Optional[Dict] = None

        # Control del overlay de hardware trigger
        self.trigger_overlay_data: Optional[Dict] = None
        self.trigger_overlay_ts: Optional[float] = None

        self._lock = threading.Lock()

    def update_frame(self, frame: np.ndarray, fps: float, state: str) -> None:
        with self._lock:
            self.frame = frame.copy()
            self.fps = fps
            self.state = state

    def get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return self.frame.copy() if self.frame is not None else None

    def register_event(self, event: Dict) -> None:
        with self._lock:
            self.events_count += 1
            self.last_event = event

    def activate_trigger_overlay(self, trigger_type: str, mqtt_topic: str) -> None:
        """Activa el overlay visual de hardware trigger."""
        with self._lock:
            self.trigger_overlay_data = {
                "trigger_type": trigger_type,
                "mqtt_topic": mqtt_topic,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "camera_id": self.id,
            }
            self.trigger_overlay_ts = time.time()

    def clear_trigger_overlay(self) -> None:
        with self._lock:
            self.trigger_overlay_data = None
            self.trigger_overlay_ts = None


# ══════════════════════════════════════════════════════════════════════════════
# Hilo de procesamiento por cámara (modo realtime)
# ══════════════════════════════════════════════════════════════════════════════

class CameraWorker(threading.Thread):
    """Hilo que lee frames, ejecuta detección, evalúa horario y encola eventos."""

    def __init__(
        self,
        cam: CameraConfig,
        detection_cfg: Dict[str, Any],
        schedule_cfg: Any,
        state: CameraState,
        event_queue: queue.Queue,
        stop_event: threading.Event,
        snapshot_dir: Path,
        metadata_indexer: Optional[MetadataIndexer],
    ) -> None:
        super().__init__(daemon=True, name=f"worker-{cam.id}")
        self.cam = cam
        self.detection_cfg = detection_cfg
        self.schedule_cfg = schedule_cfg
        self.state = state
        self.event_queue = event_queue
        self.stop_event = stop_event
        self.snapshot_dir = snapshot_dir
        self.metadata_indexer = metadata_indexer

        self.event_logger = EventLogger(
            ROOT / "outputs" / f"events_{cam.id}.jsonl"
        )

    def run(self) -> None:
        det_cfg = self.detection_cfg
        primary_module = self.cam.modules_active[0] if self.cam.modules_active else "fall_detection"
        use_m0, use_aqua = _m0_module_flags(self.cam.modules_active, primary_module)

        # Crear detector según módulo
        detector = None
        engine_info: Dict[str, str] = {"engine": "Rule-based", "device": "CPU"}
        if primary_module in ("fall_detection", "perimeter") or use_m0:
            try:
                detector = get_detector(
                    use_gpu=det_cfg.get("use_gpu", True),
                    min_fall_frames=det_cfg.get("min_fall_frames", 8),
                    fall_angle_deg=det_cfg.get("fall_angle_threshold_deg", 55.0),
                )
                engine_info = detector_info(detector)
            except Exception as exc:
                LOG.error("[%s] Error al crear detector: %s", self.cam.id, exc)

        # Módulo perímetro
        perimeter: Optional[PerimeterDetector] = None
        if primary_module == "perimeter" and "perimeter_line" in self.cam.raw:
            try:
                perimeter = PerimeterDetector.from_config(self.cam.raw["perimeter_line"])
            except Exception as exc:
                LOG.warning("[%s] PerimeterDetector no creado: %s", self.cam.id, exc)

        # M0 — geofence / Aqua (pool)
        zone_monitor: Optional[ZoneOccupancyMonitor] = None
        if use_m0:
            zone_monitor = ZoneOccupancyMonitor(
                self.cam.zones,
                min_iou=float(det_cfg.get("zone_min_iou", app_config.ZONE_MIN_IOU)),
                min_persistence_frames=int(
                    det_cfg.get("zone_min_persistence_frames", app_config.ZONE_MIN_PERSISTENCE_FRAMES)
                ),
                cooldown_sec=float(
                    det_cfg.get("zone_event_cooldown_sec", app_config.ZONE_EVENT_COOLDOWN_SEC)
                ),
                allowed_types=AQUA_ZONE_TYPES if use_aqua else None,
            )
            if not zone_monitor.zones:
                LOG.warning(
                    "[%s] %s activo pero sin zonas M0 válidas (points>=3%s).",
                    self.cam.id,
                    "aqua" if use_aqua else "geofence",
                    ", type=pool" if use_aqua else "",
                )

        stream = VideoStream(
            self.cam.stream_url or "0",
            reconnect_attempts=self.cam.raw.get("reconnect_attempts", 10),
            reconnect_delay=self.cam.raw.get("reconnect_delay_sec", 2.0),
        )

        p_time = time.time()
        frame_idx = 0

        with stream:
            while not self.stop_event.is_set():
                ok, frame = stream.read()
                if not ok or frame is None:
                    self.state.update_frame(
                        draw_no_signal((540, 960), self.state.name), 0.0, "SIN SEÑAL"
                    )
                    time.sleep(0.1)
                    continue

                frame_idx += 1
                current_state = "NORMAL"
                detections_this_frame: List[Dict] = []

                proc_frame = frame.copy()
                bbox: Dict = {}

                # ── Inferencia ─────────────────────────────────────────────
                if detector is not None:
                    try:
                        proc_frame, results = detector.find_pose(frame, draw=True)
                        lm_list, bbox = detector.find_position(proc_frame, results, draw=True)
                    except Exception:
                        LOG.exception("[%s] Error en detección frame %d", self.cam.id, frame_idx)
                        bbox = {}

                # ── Lógica de módulo ───────────────────────────────────────
                if primary_module == "fall_detection" and bbox:
                    is_falling, fall_source = resolve_is_falling(bbox)
                    detections_this_frame.append({
                        "object_class": "person",
                        "confidence": float(bbox.get("confidence", 0.8)),
                        "bbox": {k: bbox.get(k, 0) for k in ("xmin", "ymin", "xmax", "ymax")},
                        "track_id": bbox.get("track_id"),
                        "metadata": {"is_falling": is_falling, "fall_signal": fall_source},
                    })
                    start_snap = ""
                    if is_falling and self.event_logger.state == "NORMAL":
                        start_snap = self._save_snapshot(proc_frame, "fall")
                    completed = self.event_logger.update(
                        is_falling=is_falling,
                        frame_idx=frame_idx,
                        photo_path=start_snap,
                        metadata={
                            "bbox": {k: bbox.get(k) for k in ("xmin", "ymin", "xmax", "ymax", "width", "height", "confidence", "is_falling")},
                            "cam_id": self.cam.id,
                            "fall_signal": fall_source,
                        },
                    )
                    if completed:
                        current_state = "ALERTA"
                        if not completed.get("photo_path"):
                            snap = self._save_snapshot(proc_frame, "fall")
                        else:
                            snap = completed.get("photo_path")
                        completed = enrich_canonical_event(
                            completed,
                            camera_id=self.cam.id,
                            zone=self.cam.zone,
                            sector=self.cam.sector,
                            alert_level=2 if not (
                                is_after_hours(self.schedule_cfg)
                                and self.state.alert_level_after_hours >= 3
                            ) else 3,
                            photo_path=snap,
                            retention_days=int(getattr(app_config, "DATA_RETENTION_DAYS", 30)),
                        )
                        self.event_logger.log_event(completed)
                        self.state.register_event(completed)
                        self.event_queue.put(completed)
                        self._maybe_trigger_hardware(completed)
                    elif is_falling:
                        current_state = "ALERTA"

                elif primary_module == "perimeter" and perimeter:
                    perimeter.draw(proc_frame)
                    if bbox:
                        breach = perimeter.update(bbox, track_id=bbox.get("track_id", 0))
                        if breach:
                            current_state = "INTRUSION"
                            snap = self._save_snapshot(proc_frame, "perimeter")
                            after_hours = is_after_hours(self.schedule_cfg)
                            # Breach confirmado → Notify (2); Critical (3) si after_hours y config ≥3
                            alert_level = 2
                            if after_hours and self.state.alert_level_after_hours >= 3:
                                alert_level = 3
                            elif after_hours:
                                alert_level = max(2, min(3, self.state.alert_level_after_hours))
                            breach = enrich_canonical_event(
                                breach,
                                camera_id=self.cam.id,
                                zone=self.cam.zone,
                                sector=self.cam.sector,
                                alert_level=alert_level,
                                photo_path=snap,
                                retention_days=app_config.DATA_RETENTION_DAYS,
                            )
                            breach["metadata"] = {
                                **(breach.get("metadata") or {}),
                                "after_hours": after_hours,
                            }
                            self.state.register_event(breach)
                            self.event_queue.put(breach)
                            self._maybe_trigger_hardware(breach)

                elif use_m0 and zone_monitor is not None:
                    active_ids: List[str] = []
                    if bbox:
                        h, w = proc_frame.shape[:2]
                        hits = zone_monitor.evaluate_frame(bbox, w, h)
                        active_ids = [h.zone_id for h in hits]
                        zone_evt = zone_monitor.update(
                            bbox,
                            w,
                            h,
                            frame_idx=frame_idx,
                            camera_id=self.cam.id,
                            site_zone=self.cam.zone,
                            track_id=bbox.get("track_id"),
                        )
                        if zone_evt:
                            is_aqua = zone_evt.get("event_type") == "pool_occupancy"
                            current_state = "AQUA" if (use_aqua or is_aqua) else "ZONA"
                            snap = self._save_snapshot(proc_frame, zone_evt["event_type"])
                            alert_level = int(zone_evt.get("alert_level") or (2 if is_aqua else 1))
                            zone_evt = enrich_canonical_event(
                                zone_evt,
                                camera_id=self.cam.id,
                                zone=self.cam.zone,
                                sector=self.cam.sector,
                                alert_level=alert_level,
                                photo_path=snap,
                                retention_days=app_config.DATA_RETENTION_DAYS,
                            )
                            self.event_logger.log_event(zone_evt)
                            self.state.register_event(zone_evt)
                            self.event_queue.put(zone_evt)
                            self._maybe_trigger_hardware(zone_evt)
                        elif active_ids:
                            current_state = "AQUA" if use_aqua else "ZONA"
                    draw_zones(proc_frame, zone_monitor.zones, active_zone_ids=active_ids)

                # ── Indexación de metadata ─────────────────────────────────
                if self.metadata_indexer and detections_this_frame:
                    self.metadata_indexer.index_frame(
                        frame_idx=frame_idx,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        camera_id=self.cam.id,
                        detections=detections_this_frame,
                        frame=frame,
                    )

                # ── FPS ────────────────────────────────────────────────────
                c_time = time.time()
                fps = 1.0 / max(1e-6, c_time - p_time)
                p_time = c_time

                # ── HUD ────────────────────────────────────────────────────
                draw_hud(
                    proc_frame,
                    cam_name=self.cam.id,
                    zone=self.cam.zone,
                    fps=fps,
                    state=current_state,
                    events_count=self.state.events_count,
                    engine=engine_info.get("engine", "?"),
                    device=engine_info.get("device", "?"),
                    sector=self.cam.sector,
                )

                # ── Trigger overlay ────────────────────────────────────────
                with self.state._lock:
                    tdata = self.state.trigger_overlay_data
                    tts   = self.state.trigger_overlay_ts
                if tdata and tts:
                    proc_frame, still = draw_hardware_trigger_overlay(
                        proc_frame, tdata, activated_at=tts
                    )
                    if not still:
                        self.state.clear_trigger_overlay()

                self.state.update_frame(proc_frame, fps, current_state)

        if detector is not None:
            try:
                detector.close()
            except Exception:
                pass

    def _maybe_trigger_hardware(self, event: Dict) -> None:
        """Activa overlay de bocina si el nivel de alerta lo requiere."""
        after_hours = is_after_hours(self.schedule_cfg)
        if after_hours and self.state.alert_level_after_hours >= 3:
            mqtt_topic = "vigilante/relay/horn"
            self.state.activate_trigger_overlay("SIRENA", mqtt_topic)
            LOG.info(
                "[%s] HARDWARE TRIGGER — Nivel 3 fuera de horario. Topic: %s",
                self.cam.id, mqtt_topic,
            )

    def _save_snapshot(self, frame: np.ndarray, event_type: str) -> str:
        """Guarda snapshot JPG del frame del evento."""
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        path = self.snapshot_dir / f"{self.cam.id}_{event_type}_{ts}.jpg"
        try:
            cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        except Exception:
            LOG.exception("Error guardando snapshot")
            return ""
        return str(path)


# ══════════════════════════════════════════════════════════════════════════════
# Modos de ejecución
# ══════════════════════════════════════════════════════════════════════════════

def run_realtime(loader: ConfigLoader, headless: bool) -> None:
    """Procesa streams en tiempo real — un hilo por cámara."""
    cameras = loader.get_cameras()
    if not cameras:
        LOG.error("No hay cámaras habilitadas en la configuración.")
        return

    schedule_cfg = loader.get_schedule()
    det_cfg = loader.get_section("detection", {})
    demo_cfg = loader.get_section("demo", {})
    forensic_cfg = loader.get_section("forensic_audit", {})

    snapshot_dir = ROOT / demo_cfg.get("snapshot_dir", "test_outputs/snapshots")
    win_w = int(demo_cfg.get("window_width", 1280))
    win_h = int(demo_cfg.get("window_height", 720))

    # MetadataIndexer global
    indexer: Optional[MetadataIndexer] = None
    if forensic_cfg.get("enabled", False):
        idx_path = ROOT / forensic_cfg.get("output_jsonl", "outputs/metadata_index.jsonl")
        indexer = MetadataIndexer(
            idx_path,
            index_every_n_frames=int(forensic_cfg.get("index_every_n_frames", 5)),
        )

    trigger_manager = TriggerManager(loader.get_section("triggers", {}))
    pdf_cfg = loader.get_section("pdf_report", {})
    report_dir = ROOT / demo_cfg.get("report_dir", demo_cfg.get("snapshot_dir", "test_outputs"))
    auto_pdf = bool(demo_cfg.get("auto_pdf_on_event", False))

    stop_event = threading.Event()
    event_queue: queue.Queue = queue.Queue()
    states: List[CameraState] = []
    workers: List[CameraWorker] = []

    for cam in cameras:
        state = CameraState(cam)
        worker = CameraWorker(
            cam=cam,
            detection_cfg=det_cfg,
            schedule_cfg=schedule_cfg,
            state=state,
            event_queue=event_queue,
            stop_event=stop_event,
            snapshot_dir=snapshot_dir,
            metadata_indexer=indexer,
        )
        states.append(state)
        workers.append(worker)
        worker.start()
        LOG.info("Worker lanzado: %s (%s)", cam.id, cam.stream_url or "sin URL")

    LOG.info("Sistema activo — %d cámaras | Presiona 'q' para salir", len(cameras))

    try:
        while True:
            # Despachar eventos de la cola (PDF/email fuera del hilo de captura)
            while not event_queue.empty():
                try:
                    ev = event_queue.get_nowait()
                    _dispatch_event_triggers(
                        ev,
                        trigger_manager,
                        report_dir=report_dir,
                        pdf_cfg=pdf_cfg,
                        auto_pdf=auto_pdf,
                    )
                except queue.Empty:
                    break

            if headless:
                time.sleep(0.1)
                continue

            # Componer vista (primera cámara por ahora; extender para grid)
            frames = [s.get_frame() for s in states]
            valid = [f for f in frames if f is not None]
            if not valid:
                time.sleep(0.05)
                continue

            # Layout: hasta 2 cámaras side-by-side; resto debajo
            if len(valid) == 1:
                composite = cv2.resize(valid[0], (win_w, win_h))
            elif len(valid) == 2:
                half_w = win_w // 2
                l = cv2.resize(valid[0], (half_w, win_h))
                r = cv2.resize(valid[1], (half_w, win_h))
                composite = np.hstack([l, r])
            else:
                half_w = win_w // 2
                half_h = win_h // 2
                row1 = np.hstack([
                    cv2.resize(valid[0], (half_w, half_h)),
                    cv2.resize(valid[1], (half_w, half_h)),
                ])
                others = valid[2:4]
                while len(others) < 2:
                    others.append(np.zeros((half_h, half_w, 3), dtype=np.uint8))
                row2 = np.hstack([
                    cv2.resize(others[0], (half_w, half_h)),
                    cv2.resize(others[1], (half_w, half_h)),
                ])
                composite = np.vstack([row1, row2])

            cv2.imshow("Vigilante Digital — Real Time", composite)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break

    except KeyboardInterrupt:
        LOG.info("Interrupción de teclado — cerrando...")
    finally:
        stop_event.set()
        for w in workers:
            w.join(timeout=3.0)
        if indexer:
            indexer.close()
        trigger_manager.shutdown(wait=False)
        if not headless:
            cv2.destroyAllWindows()
        LOG.info("Sistema detenido.")


def run_file(
    loader: ConfigLoader,
    source: str,
    headless: bool,
    cam_id_override: Optional[str] = None,
    *,
    dispatch_triggers: bool = True,
    save_snapshots: bool = True,
) -> List[Dict[str, Any]]:
    """Procesa un archivo de video MP4 con barra de progreso.

    Si hay múltiples cámaras en el config, usa la primera habilitada
    (o la especificada por cam_id_override) para aplicar sus módulos.

    Retorna la lista de eventos generados. Con dispatch_triggers=False no se
    disparan triggers/PDF; con save_snapshots=False no se guardan JPG.
    """
    events: List[Dict[str, Any]] = []
    cameras = loader.get_cameras()
    if not cameras:
        LOG.error("No hay cámaras habilitadas. Revisa client_config.json.")
        return events

    # Seleccionar cámara para el módulo
    cam = cameras[0]
    if cam_id_override:
        found = next((c for c in cameras if c.id == cam_id_override), None)
        if found:
            cam = found
        else:
            LOG.warning("Cámara '%s' no encontrada; usando '%s'.", cam_id_override, cam.id)

    schedule_cfg = loader.get_schedule()
    det_cfg = loader.get_section("detection", {})
    demo_cfg = loader.get_section("demo", {})
    forensic_cfg = loader.get_section("forensic_audit", {})

    snapshot_dir = ROOT / demo_cfg.get("snapshot_dir", "test_outputs/snapshots")
    primary_module = cam.modules_active[0] if cam.modules_active else "fall_detection"
    use_m0, use_aqua = _m0_module_flags(cam.modules_active, primary_module)

    def _snap(img: np.ndarray, event_type: str) -> str:
        if not save_snapshots:
            return ""
        return _save_snapshot(img, cam.id, event_type, snapshot_dir)

    LOG.info("Modo FILE | Archivo: %s | Módulo: %s | Cámara: %s", source, primary_module, cam.id)

    # Crear detector
    detector = None
    engine_info: Dict[str, str] = {"engine": "Rule-based", "device": "CPU"}
    try:
        detector = get_detector(
            use_gpu=det_cfg.get("use_gpu", True),
            min_fall_frames=det_cfg.get("min_fall_frames", 8),
            fall_angle_deg=det_cfg.get("fall_angle_threshold_deg", 55.0),
        )
        engine_info = detector_info(detector)
    except Exception as exc:
        LOG.warning("Detector no disponible (%s) — procesando sin inferencia.", exc)

    perimeter: Optional[PerimeterDetector] = None
    if primary_module == "perimeter" and "perimeter_line" in cam.raw:
        try:
            perimeter = PerimeterDetector.from_config(cam.raw["perimeter_line"])
        except Exception as exc:
            LOG.warning("PerimeterDetector no creado: %s", exc)

    zone_monitor: Optional[ZoneOccupancyMonitor] = None
    if use_m0:
        zone_monitor = ZoneOccupancyMonitor(
            cam.zones,
            min_iou=float(det_cfg.get("zone_min_iou", app_config.ZONE_MIN_IOU)),
            min_persistence_frames=int(
                det_cfg.get("zone_min_persistence_frames", app_config.ZONE_MIN_PERSISTENCE_FRAMES)
            ),
            cooldown_sec=float(
                det_cfg.get("zone_event_cooldown_sec", app_config.ZONE_EVENT_COOLDOWN_SEC)
            ),
            allowed_types=AQUA_ZONE_TYPES if use_aqua else None,
        )
        if not zone_monitor.zones:
            LOG.warning(
                "%s activo pero sin zonas M0 válidas (points>=3%s).",
                "aqua" if use_aqua else "geofence",
                ", type=pool" if use_aqua else "",
            )

    # Indexador de metadatos
    indexer: Optional[MetadataIndexer] = None
    if forensic_cfg.get("enabled", False):
        idx_path = ROOT / forensic_cfg.get("output_jsonl", "outputs/metadata_index.jsonl")
        indexer = MetadataIndexer(
            idx_path,
            index_every_n_frames=int(forensic_cfg.get("index_every_n_frames", 5)),
        )

    event_logger = EventLogger(ROOT / "outputs" / f"events_{cam.id}.jsonl")
    trigger_manager = TriggerManager(loader.get_section("triggers", {}))

    reader = FileVideoReader(source, loop=False, module_name=primary_module)
    if not reader.open():
        LOG.error("No se pudo abrir el archivo: %s", source)
        return events

    p_time = time.time()
    frame_idx = 0
    events_count = 0
    paused = False

    # Estado del trigger overlay
    trigger_overlay_data: Optional[Dict] = None
    trigger_overlay_ts: Optional[float] = None

    LOG.info(
        "Video abierto: %d frames @ %.1f FPS — Procesando...",
        reader.total_frames, reader.fps,
    )

    try:
        while True:
            if paused:
                key = cv2.waitKey(30) & 0xFF
                if key == ord(" "):
                    paused = False
                elif key in (ord("q"), 27):
                    break
                continue

            ok, frame = reader.read()
            if not ok or frame is None:
                LOG.info("Fin del archivo. Frames procesados: %d", frame_idx)
                break

            frame_idx += 1
            current_state = "NORMAL"
            detections_this_frame: List[Dict] = []

            proc_frame = frame.copy()
            bbox: Dict = {}

            # ── Inferencia ─────────────────────────────────────────────────
            if detector is not None:
                try:
                    proc_frame, results = detector.find_pose(frame, draw=True)
                    _, bbox = detector.find_position(proc_frame, results, draw=True)
                except Exception:
                    LOG.exception("Error en detección frame %d", frame_idx)
                    bbox = {}

            # ── Lógica ─────────────────────────────────────────────────────
            if primary_module == "fall_detection" and bbox:
                is_falling, fall_source = resolve_is_falling(bbox)
                detections_this_frame.append({
                    "object_class": "person",
                    "confidence": float(bbox.get("confidence", 0.8)),
                    "bbox": {k: bbox.get(k, 0) for k in ("xmin", "ymin", "xmax", "ymax")},
                    "metadata": {"is_falling": is_falling, "fall_signal": fall_source},
                })
                start_snap = ""
                if is_falling and event_logger.state == "NORMAL":
                    start_snap = _snap(proc_frame, "fall")
                completed = event_logger.update(
                    is_falling=is_falling,
                    frame_idx=frame_idx,
                    photo_path=start_snap,
                    metadata={
                        "bbox": {
                            k: bbox.get(k)
                            for k in ("xmin", "ymin", "xmax", "ymax", "width", "height", "confidence", "is_falling")
                        },
                        "cam_id": cam.id,
                        "fall_signal": fall_source,
                    },
                )
                if completed:
                    current_state = "ALERTA"
                    events_count += 1
                    snap = completed.get("photo_path") or _snap(proc_frame, "fall")
                    after_hours = is_after_hours(schedule_cfg)
                    alert_level = 3 if after_hours and cam.alert_level_after_hours >= 3 else 2
                    completed = enrich_canonical_event(
                        completed,
                        camera_id=cam.id,
                        zone=cam.zone,
                        sector=cam.sector,
                        alert_level=alert_level,
                        photo_path=snap,
                        retention_days=app_config.DATA_RETENTION_DAYS,
                    )
                    event_logger.log_event(completed)
                    events.append(completed)
                    if dispatch_triggers:
                        _dispatch_event_triggers(
                            completed,
                            trigger_manager,
                            report_dir=ROOT / demo_cfg.get("report_dir", "test_outputs"),
                            pdf_cfg=loader.get_section("pdf_report", {}),
                            auto_pdf=bool(demo_cfg.get("auto_pdf_on_event", False)),
                        )
                    if alert_level >= 3:
                        trigger_overlay_data = {
                            "trigger_type": "SIRENA",
                            "mqtt_topic": "vigilante/relay/horn",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "camera_id": cam.id,
                        }
                        trigger_overlay_ts = time.time()
                        LOG.info("HARDWARE TRIGGER — Nivel 3 activado (fuera de horario)")
                elif is_falling:
                    current_state = "ALERTA"

            elif primary_module == "perimeter" and perimeter:
                perimeter.draw(proc_frame)
                if bbox:
                    breach = perimeter.update(bbox, track_id=bbox.get("track_id", 0))
                    if breach:
                        current_state = "INTRUSION"
                        events_count += 1
                        snap = _snap(proc_frame, "perimeter")
                        after_hours = is_after_hours(schedule_cfg)
                        alert_level = 1
                        if after_hours:
                            alert_level = max(2, min(3, cam.alert_level_after_hours))
                        breach = enrich_canonical_event(
                            breach,
                            camera_id=cam.id,
                            zone=cam.zone,
                            sector=cam.sector,
                            alert_level=alert_level,
                            photo_path=snap,
                            retention_days=app_config.DATA_RETENTION_DAYS,
                        )
                        breach["metadata"] = {
                            **(breach.get("metadata") or {}),
                            "after_hours": after_hours,
                        }
                        events.append(breach)
                        if dispatch_triggers:
                            _dispatch_event_triggers(
                                breach,
                                trigger_manager,
                                report_dir=ROOT / demo_cfg.get("report_dir", "test_outputs"),
                                pdf_cfg=loader.get_section("pdf_report", {}),
                                auto_pdf=bool(demo_cfg.get("auto_pdf_on_event", False)),
                            )
                        if alert_level >= 3:
                            trigger_overlay_data = {
                                "trigger_type": "SIRENA",
                                "mqtt_topic": "vigilante/relay/horn",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "camera_id": cam.id,
                            }
                            trigger_overlay_ts = time.time()
                            LOG.info("HARDWARE TRIGGER — Perimeter nivel 3 (fuera de horario)")

            elif use_m0 and zone_monitor is not None:
                active_ids: List[str] = []
                if bbox:
                    h, w = proc_frame.shape[:2]
                    hits = zone_monitor.evaluate_frame(bbox, w, h)
                    active_ids = [hit.zone_id for hit in hits]
                    zone_evt = zone_monitor.update(
                        bbox,
                        w,
                        h,
                        frame_idx=frame_idx,
                        camera_id=cam.id,
                        site_zone=cam.zone,
                        track_id=bbox.get("track_id"),
                    )
                    if zone_evt:
                        is_aqua = zone_evt.get("event_type") == "pool_occupancy"
                        current_state = "AQUA" if (use_aqua or is_aqua) else "ZONA"
                        events_count += 1
                        snap = _snap(proc_frame, zone_evt["event_type"])
                        alert_level = int(zone_evt.get("alert_level") or (2 if is_aqua else 1))
                        zone_evt = enrich_canonical_event(
                            zone_evt,
                            camera_id=cam.id,
                            zone=cam.zone,
                            sector=cam.sector,
                            alert_level=alert_level,
                            photo_path=snap,
                            retention_days=app_config.DATA_RETENTION_DAYS,
                        )
                        event_logger.log_event(zone_evt)
                        events.append(zone_evt)
                        if dispatch_triggers:
                            _dispatch_event_triggers(
                                zone_evt,
                                trigger_manager,
                                report_dir=ROOT / demo_cfg.get("report_dir", "test_outputs"),
                                pdf_cfg=loader.get_section("pdf_report", {}),
                                auto_pdf=bool(demo_cfg.get("auto_pdf_on_event", False)),
                            )
                    elif active_ids:
                        current_state = "AQUA" if use_aqua else "ZONA"
                draw_zones(proc_frame, zone_monitor.zones, active_zone_ids=active_ids)

            # ── Indexación ─────────────────────────────────────────────────
            if indexer and detections_this_frame:
                indexer.index_frame(
                    frame_idx=frame_idx,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    camera_id=cam.id,
                    detections=detections_this_frame,
                    frame=frame,
                )

            # ── FPS ────────────────────────────────────────────────────────
            c_time = time.time()
            fps = 1.0 / max(1e-6, c_time - p_time)
            p_time = c_time

            # ── HUD ────────────────────────────────────────────────────────
            draw_hud(
                proc_frame,
                cam_name=cam.id,
                zone=cam.zone,
                fps=fps,
                state=current_state,
                events_count=events_count,
                engine=engine_info.get("engine", "?"),
                device=engine_info.get("device", "?"),
                sector=cam.sector,
            )

            # ── Barra de progreso ───────────────────────────────────────────
            reader.draw_progress(proc_frame)

            # ── Trigger overlay ─────────────────────────────────────────────
            if trigger_overlay_data and trigger_overlay_ts:
                proc_frame, still = draw_hardware_trigger_overlay(
                    proc_frame, trigger_overlay_data, activated_at=trigger_overlay_ts
                )
                if not still:
                    trigger_overlay_data = None
                    trigger_overlay_ts = None

            # ── Ventana ────────────────────────────────────────────────────
            if not headless:
                try:
                    display = cv2.resize(proc_frame, (1280, 720))
                except Exception:
                    display = proc_frame
                cv2.imshow("Vigilante Digital — Demo File", display)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                elif key == ord(" "):
                    paused = True
                    LOG.info("Pausado en frame %d / %d", frame_idx, reader.total_frames)

    except KeyboardInterrupt:
        LOG.info("Interrupción de teclado.")
    finally:
        reader.close()
        final_ev = event_logger.finalize()
        if final_ev:
            final_ev = enrich_canonical_event(
                final_ev,
                camera_id=cam.id,
                zone=cam.zone,
                sector=cam.sector,
                alert_level=2,
                retention_days=app_config.DATA_RETENTION_DAYS,
            )
            event_logger.log_event(final_ev)
            events.append(final_ev)
            if dispatch_triggers:
                _dispatch_event_triggers(
                    final_ev,
                    trigger_manager,
                    report_dir=ROOT / demo_cfg.get("report_dir", "test_outputs"),
                    pdf_cfg=loader.get_section("pdf_report", {}),
                    auto_pdf=bool(demo_cfg.get("auto_pdf_on_event", False)),
                )
        if indexer:
            stats = indexer.get_stats()
            LOG.info("Metadatos indexados: %s", stats)
            indexer.close()
        trigger_manager.shutdown(wait=False)
        if not headless:
            cv2.destroyAllWindows()

        LOG.info(
            "Procesamiento finalizado | frames=%d | eventos=%d",
            frame_idx, events_count,
        )

    return events


def run_batch(
    loader: ConfigLoader,
    source: str,
    *,
    dispatch_triggers: bool = True,
    save_snapshots: bool = True,
) -> None:
    """Procesa archivo(s) sin UI a máxima velocidad. Ideal para indexar video histórico."""
    LOG.info("Modo BATCH iniciado — headless, máxima velocidad.")
    run_file(
        loader,
        source,
        headless=True,
        dispatch_triggers=dispatch_triggers,
        save_snapshots=save_snapshots,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Utilidades
# ══════════════════════════════════════════════════════════════════════════════

def _save_snapshot(
    frame: np.ndarray,
    cam_id: str,
    event_type: str,
    snapshot_dir: Path,
) -> str:
    """Guarda snapshot JPG. Retorna path o '' en error."""
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
    path = snapshot_dir / f"{cam_id}_{event_type}_{ts}.jpg"
    try:
        cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return str(path)
    except Exception:
        LOG.exception("Error guardando snapshot")
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="runner.py",
        description="Vigilante Digital v2.0 — Runner Unificado",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python runner.py --mode file --source video_demo.mp4
  python runner.py --mode realtime --config client_config.json
  python runner.py --mode batch --source grabacion_historica.mp4
        """,
    )
    p.add_argument(
        "--mode",
        choices=["realtime", "file", "batch"],
        default="realtime",
        help="Modo de operación (default: realtime)",
    )
    p.add_argument(
        "--config",
        default="client_config.json",
        help="Ruta al JSON de configuración del cliente (default: client_config.json)",
    )
    p.add_argument(
        "--source",
        default=None,
        help="Ruta al archivo MP4 (requerido en modos file y batch)",
    )
    p.add_argument(
        "--cam",
        default=None,
        help="ID de la cámara a usar en modo file (default: primera habilitada)",
    )
    p.add_argument(
        "--headless",
        action="store_true",
        help="Sin ventana de visualización (útil en servidores sin GUI)",
    )
    p.add_argument(
        "--eval",
        action="store_true",
        help="Modo evaluación (file/batch): no dispara triggers ni guarda snapshots JPG",
    )
    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Cargar configuración con mensajes de error claros
    try:
        loader = ConfigLoader(Path(args.config))
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    headless = args.headless or app_config.HEADLESS_MODE

    if args.mode == "realtime":
        run_realtime(loader, headless=headless)

    elif args.mode == "file":
        if not args.source:
            print(
                "[ERROR] --source es requerido en modo file.\n"
                "  Ejemplo: python runner.py --mode file --source video.mp4",
                file=sys.stderr,
            )
            sys.exit(1)
        run_file(
            loader,
            args.source,
            headless=headless,
            cam_id_override=args.cam,
            dispatch_triggers=not args.eval,
            save_snapshots=not args.eval,
        )

    elif args.mode == "batch":
        if not args.source:
            print(
                "[ERROR] --source es requerido en modo batch.\n"
                "  Ejemplo: python runner.py --mode batch --source grabacion.mp4",
                file=sys.stderr,
            )
            sys.exit(1)
        run_batch(
            loader,
            args.source,
            dispatch_triggers=not args.eval,
            save_snapshots=not args.eval,
        )


if __name__ == "__main__":
    main()
