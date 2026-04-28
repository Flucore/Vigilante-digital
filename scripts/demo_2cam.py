"""Demo de 2 cámaras IP para presentación ejecutiva — Vigilante Digital IA.

Lee demo_config.json, lanza un hilo por cámara con detección en tiempo real,
y compone una vista split en pantalla completa.

Uso:
    python scripts/demo_2cam.py
    python scripts/demo_2cam.py --config mi_config.json
    python scripts/demo_2cam.py --cam1 http://192.168.1.5:8080/video --cam2 http://192.168.1.6:8080/video

Teclas durante el demo:
    q / ESC  → Salir
    p        → Generar PDF del último evento
    s        → Screenshot manual
    r        → Reset visual de alertas
    f        → Fullscreen toggle
    ESPACIO  → Pausar/Reanudar
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

# Asegurar que el root del proyecto esté en sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.detector_factory import get_detector, detector_info
from core.color_detectors import RedShirtDetector, TrafficLightDetector
from core.perimeter_detector import PerimeterDetector
from inputs.video_stream import VideoStream
from outputs.event_logger import EventLogger
from outputs.hud_renderer import compose_split_view, draw_hud, draw_no_signal
from outputs.report_generator import ReportGenerator
from outputs.trigger_manager import TriggerManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
LOG = logging.getLogger("demo_2cam")

# ─── Intentar cargar Firebase (opcional) ──────────────────────────────────────
try:
    from outputs.firebase_connector import FirebaseConnector
    _FIREBASE_AVAILABLE = True
except Exception:
    _FIREBASE_AVAILABLE = False
    LOG.warning("Firebase no disponible — el demo funciona sin él")

# ─── Intentar cargar audio (opcional) ─────────────────────────────────────────
try:
    from playsound import playsound as _playsound
    _AUDIO_AVAILABLE = True
except ImportError:
    _AUDIO_AVAILABLE = False


# ==============================================================================
# Configuración
# ==============================================================================

DEFAULT_CONFIG = ROOT / "demo_config.json"

_BEEP_ASSET = ROOT / "assets" / "alert.wav"

_FALLBACK_BEEP_FREQ = 1000  # Hz — beep de Windows como fallback


def load_config(path: Path) -> Dict[str, Any]:
    """Carga y valida demo_config.json."""
    if not path.exists():
        LOG.warning("Config no encontrada en %s — usando defaults", path)
        return _default_config()
    with path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)
    LOG.info("Config cargada: %s", path)
    return cfg


def _default_config() -> Dict[str, Any]:
    return {
        "demo": {"title": "Vigilante Digital IA", "window_width": 1920,
                 "window_height": 540, "alert_sound": False, "auto_pdf_on_event": False,
                 "snapshot_dir": "test_outputs/snapshots", "report_dir": "test_outputs"},
        "detection": {"use_gpu": True, "min_fall_frames": 8, "fall_angle_threshold_deg": 55.0,
                      "frame_scale": 1.0, "min_detection_confidence": 0.5},
        "cameras": [],
        "firebase": {"enabled": False},
    }


# ==============================================================================
# Estado compartido de una cámara
# ==============================================================================

class CameraState:
    """Estado mutable de una cámara, accedido por hilos de forma thread-safe."""

    def __init__(self, cam_cfg: Dict[str, Any]) -> None:
        self.id: str = cam_cfg.get("id", "CAM")
        self.name: str = cam_cfg.get("name", self.id)
        self.zone: str = cam_cfg.get("zone", "")
        self.sector: str = cam_cfg.get("sector", "")
        self.module: str = cam_cfg.get("module", "fall_detection")

        self.frame: Optional[np.ndarray] = None
        self.fps: float = 0.0
        self.state: str = "SIN SEÑAL"
        self.events_count: int = 0
        self.last_event: Optional[Dict] = None

        self._lock = threading.Lock()

    def update_frame(self, frame: np.ndarray, fps: float, state: str) -> None:
        with self._lock:
            self.frame = frame.copy()
            self.fps = fps
            self.state = state

    def register_event(self, event: Dict) -> None:
        with self._lock:
            self.events_count += 1
            self.last_event = event

    def get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return self.frame.copy() if self.frame is not None else None


# ==============================================================================
# Hilo de procesamiento por cámara
# ==============================================================================

class CameraWorker(threading.Thread):
    """Hilo que lee frames de una cámara, ejecuta detección y actualiza CameraState."""

    def __init__(
        self,
        cam_cfg: Dict[str, Any],
        detection_cfg: Dict[str, Any],
        state: CameraState,
        event_queue: queue.Queue,
        stop_event: threading.Event,
        snapshot_dir: Path,
    ) -> None:
        super().__init__(daemon=True, name=f"worker-{cam_cfg.get('id', 'CAM')}")
        self.cam_cfg = cam_cfg
        self.detection_cfg = detection_cfg
        self.state = state
        self.event_queue = event_queue
        self.stop_event = stop_event
        self.snapshot_dir = snapshot_dir

        self.event_logger = EventLogger(
            ROOT / "outputs" / f"events_{state.id}.json"
        )

    def run(self) -> None:
        url = self.cam_cfg.get("url", "0")
        det_cfg = self.detection_cfg

        detector = None
        engine_info = {"engine": "Color/Rule", "device": "CPU"}
        needs_pose = self.state.module in ("fall_detection", "perimeter")
        if needs_pose:
            try:
                detector = get_detector(
                    use_gpu=det_cfg.get("use_gpu", True),
                    min_fall_frames=det_cfg.get("min_fall_frames", 8),
                    fall_angle_deg=det_cfg.get("fall_angle_threshold_deg", 55.0),
                )
                engine_info = detector_info(detector)
            except Exception as exc:
                LOG.error("[%s] Error al crear detector: %s", self.state.id, exc)
                self.state.update_frame(
                    draw_no_signal((540, 960), self.state.name), 0.0, "ERROR"
                )
                return

        stream = VideoStream(
            url,
            reconnect_attempts=self.cam_cfg.get("reconnect_attempts", 10),
            reconnect_delay=self.cam_cfg.get("reconnect_delay_sec", 2.0),
        )

        perimeter: Optional[PerimeterDetector] = None
        if self.state.module == "perimeter" and "perimeter_line" in self.cam_cfg:
            perimeter = PerimeterDetector.from_config(self.cam_cfg["perimeter_line"])

        red_shirt: Optional[RedShirtDetector] = None
        if self.state.module == "red_shirt":
            red_shirt = RedShirtDetector(
                min_presence_sec=self.cam_cfg.get("min_presence_sec", 1.0),
                min_area_ratio=self.cam_cfg.get("min_area_ratio", 0.025),
                cooldown_sec=self.cam_cfg.get("cooldown_sec", 5.0),
                roi=_roi_from_cfg(self.cam_cfg.get("roi")),
            )

        traffic_light: Optional[TrafficLightDetector] = None
        if self.state.module == "traffic_light":
            traffic_light = TrafficLightDetector(
                roi=_roi_from_cfg(self.cam_cfg.get("roi")),
                min_stable_sec=self.cam_cfg.get("min_stable_sec", 0.4),
                min_color_ratio=self.cam_cfg.get("min_color_ratio", 0.015),
            )

        p_time = time.time()
        frame_idx = 0

        with stream:
            while not self.stop_event.is_set():
                ok, frame = stream.read()
                if not ok:
                    self.state.update_frame(
                        draw_no_signal((540, 960), self.state.name), 0.0, "SIN SEÑAL"
                    )
                    time.sleep(0.1)
                    continue

                frame_idx += 1
                current_state = "NORMAL"

                # ── Detección principal ──────────────────────────────────────
                proc_frame = frame.copy()
                bbox = {}
                if detector is not None:
                    try:
                        proc_frame, results = detector.find_pose(frame, draw=True)
                        lm_list, bbox = detector.find_position(proc_frame, results, draw=True)
                    except Exception:
                        LOG.exception("[%s] Error en detección frame %d", self.state.id, frame_idx)
                        proc_frame = frame.copy()
                        bbox = {}

                # ── Evaluación de caída ──────────────────────────────────────
                if self.state.module == "fall_detection" and bbox:
                    is_falling = bbox.get("is_falling") or (
                        bbox.get("height", 0) / max(1, bbox.get("width", 1)) < 0.75
                    )
                    completed = self.event_logger.update(
                        is_falling=is_falling,
                        frame_idx=frame_idx,
                        metadata={"bbox": bbox, "cam_id": self.state.id},
                    )
                    if completed:
                        current_state = "ALERTA"
                        snap_path = self._save_snapshot(proc_frame, "fall")
                        completed["camera_id"] = self.state.id
                        completed["zone"] = self.state.zone
                        completed["photo_path"] = snap_path
                        self.event_logger.log_event(completed)
                        self.state.register_event(completed)
                        self.event_queue.put(completed)
                    elif is_falling:
                        current_state = "ALERTA"

                # ── Evaluación de perímetro ──────────────────────────────────
                elif self.state.module == "perimeter" and perimeter and bbox:
                    perimeter.draw(proc_frame)
                    breach = perimeter.update(bbox, track_id=bbox.get("track_id", 0))
                    if breach:
                        current_state = "INTRUSION"
                        snap_path = self._save_snapshot(proc_frame, "perimeter")
                        breach["camera_id"] = self.state.id
                        breach["zone"] = self.state.zone
                        breach["photo_path"] = snap_path
                        self.state.register_event(breach)
                        self.event_queue.put(breach)
                elif perimeter:
                    perimeter.draw(proc_frame)

                # ── Polera roja por 1 segundo ────────────────────────────────
                elif self.state.module == "red_shirt" and red_shirt:
                    result = red_shirt.update(proc_frame, camera_id=self.state.id, zone=self.state.zone)
                    red_shirt.draw(proc_frame, result)
                    if result.event:
                        current_state = "ALERTA"
                        result.event["photo_path"] = self._save_snapshot(proc_frame, "red_shirt")
                        self.event_logger.log_event(result.event)
                        self.state.register_event(result.event)
                        self.event_queue.put(result.event)
                    elif result.detected:
                        current_state = "OBSERVANDO"

                # ── Cambio de color de luz / semáforo ────────────────────────
                elif self.state.module == "traffic_light" and traffic_light:
                    result = traffic_light.update(proc_frame, camera_id=self.state.id, zone=self.state.zone)
                    traffic_light.draw(proc_frame, result)
                    if result.event:
                        current_state = "ALERTA"
                        result.event["photo_path"] = self._save_snapshot(proc_frame, "traffic_light")
                        self.event_logger.log_event(result.event)
                        self.state.register_event(result.event)
                        self.event_queue.put(result.event)

                # ── FPS ──────────────────────────────────────────────────────
                c_time = time.time()
                fps = 1.0 / max(1e-6, c_time - p_time)
                p_time = c_time

                # ── HUD overlay ──────────────────────────────────────────────
                from outputs.hud_renderer import draw_hud
                draw_hud(
                    proc_frame,
                    cam_name=self.state.id,
                    zone=self.state.zone,
                    fps=fps,
                    state=current_state,
                    events_count=self.state.events_count,
                    engine=engine_info.get("engine", "?"),
                    device=engine_info.get("device", "?"),
                    sector=self.state.sector,
                )

                self.state.update_frame(proc_frame, fps, current_state)

        try:
            if detector is not None:
                detector.close()
        except Exception:
            pass

    def _save_snapshot(self, frame: np.ndarray, event_type: str) -> str:
        """Guarda un snapshot JPG del frame actual."""
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.snapshot_dir / f"{self.state.id}_{event_type}_{ts}.jpg"
        try:
            cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        except Exception:
            LOG.exception("Error guardando snapshot")
            return ""
        return str(path)


# ==============================================================================
# Orquestador principal
# ==============================================================================

def run_demo(config: Dict[str, Any], cam_overrides: Dict[str, str]) -> None:
    demo_cfg = config.get("demo", {})
    det_cfg = config.get("detection", {})
    fb_cfg = config.get("firebase", {})

    win_w = demo_cfg.get("window_width", 1920)
    win_h = demo_cfg.get("window_height", 540)
    title = demo_cfg.get("title", "Vigilante Digital IA")
    alert_sound = demo_cfg.get("alert_sound", False)
    auto_pdf_on_event = demo_cfg.get("auto_pdf_on_event", False)
    snapshot_dir = ROOT / demo_cfg.get("snapshot_dir", "test_outputs/snapshots")
    report_dir = ROOT / demo_cfg.get("report_dir", "test_outputs")
    trigger_manager = TriggerManager(config.get("triggers", {}))

    cameras_cfg: List[Dict] = config.get("cameras", [])

    # Aplicar overrides de URL desde CLI
    for i, cam in enumerate(cameras_cfg):
        key = f"cam{i+1}"
        if key in cam_overrides and cam_overrides[key]:
            cam["url"] = cam_overrides[key]
            LOG.info("URL %s sobreescrita desde CLI: %s", cam.get("id"), cam["url"])

    if not cameras_cfg:
        LOG.error("No hay cámaras configuradas en demo_config.json")
        return

    # ── Inicializar Firebase (opcional) ──────────────────────────────────────
    firebase_enabled = bool(_FIREBASE_AVAILABLE and fb_cfg.get("enabled", False))
    firebase_collection = fb_cfg.get("collection", "Demo_Alertas")
    if _FIREBASE_AVAILABLE and fb_cfg.get("enabled", False):
        try:
            FirebaseConnector(collection=firebase_collection)
            LOG.info("Firebase disponible: colección=%s", firebase_collection)
        except Exception as exc:
            LOG.warning("Firebase deshabilitado: %s", exc)
            firebase_enabled = False

    # ── Crear estado y workers por cámara ────────────────────────────────────
    stop_event = threading.Event()
    event_queue: queue.Queue = queue.Queue()
    states: List[CameraState] = []
    workers: List[CameraWorker] = []

    for cam_cfg in cameras_cfg:
        if not cam_cfg.get("enabled", True):
            continue
        st = CameraState(cam_cfg)
        wk = CameraWorker(cam_cfg, det_cfg, st, event_queue, stop_event, snapshot_dir)
        states.append(st)
        workers.append(wk)

    if not workers:
        LOG.error("No hay cámaras habilitadas")
        return

    LOG.info("Iniciando %d cámara(s): %s",
             len(workers), [s.id for s in states])

    for wk in workers:
        wk.start()

    # ── Ventana principal ─────────────────────────────────────────────────────
    cv2.namedWindow(title, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(title, win_w, win_h)

    paused = False
    fullscreen = False
    last_event: Optional[Dict] = None

    LOG.info("Demo activo — Teclas: q=salir | p=PDF | s=screenshot | r=reset | f=fullscreen | ESPACIO=pausa")
    print("\n" + "="*60)
    print(f"  {title}")
    print("  Teclas: q=salir | p=PDF | s=screenshot | r=reset | f=fullscreen | ESPACIO=pausa")
    print("="*60 + "\n")

    while True:
        # ── Recoger eventos de alert queue ────────────────────────────────────
        while not event_queue.empty():
            try:
                ev = event_queue.get_nowait()
                last_event = ev
                LOG.warning("[EVENTO] %s — cámara=%s zona=%s",
                            ev.get("event_type"), ev.get("camera_id"), ev.get("zone"))
                if alert_sound:
                    _play_alert()
                pdf_path = _generate_pdf(ev, report_dir, config) if auto_pdf_on_event else None
                trigger_manager.handle_event(ev, pdf_path=pdf_path)
                if firebase_enabled:
                    threading.Thread(
                        target=_sync_camera_events_to_firebase,
                        args=(ev.get("camera_id"), firebase_collection),
                        daemon=True,
                    ).start()
            except queue.Empty:
                break

        # ── Componer vista ────────────────────────────────────────────────────
        if not paused:
            frames = [st.get_frame() for st in states]
            valid = [f for f in frames if f is not None]

            if len(valid) == 0:
                canvas = draw_no_signal((win_h, win_w), "Conectando cámaras...")
            elif len(valid) == 1:
                canvas = cv2.resize(valid[0], (win_w, win_h))
            else:
                canvas = compose_split_view(valid[0], valid[1], win_w, win_h)

            cv2.imshow(title, canvas)

        # ── Teclas ────────────────────────────────────────────────────────────
        key = cv2.waitKey(30) & 0xFF

        if key in (ord("q"), 27):  # q o ESC
            LOG.info("Saliendo por tecla")
            break

        elif key == ord(" "):
            paused = not paused
            LOG.info("Demo %s", "PAUSADO" if paused else "REANUDADO")

        elif key == ord("f"):
            fullscreen = not fullscreen
            prop = cv2.WND_PROP_FULLSCREEN
            val = cv2.WINDOW_FULLSCREEN if fullscreen else cv2.WINDOW_NORMAL
            cv2.setWindowProperty(title, prop, val)

        elif key == ord("s"):
            _save_manual_screenshot(canvas if "canvas" in dir() else None, report_dir)

        elif key == ord("r"):
            for st in states:
                st.state = "NORMAL"
            LOG.info("Alertas reseteadas manualmente")

        elif key == ord("p"):
            _generate_pdf(last_event, report_dir, config)

    # ── Cierre limpio ─────────────────────────────────────────────────────────
    stop_event.set()
    LOG.info("Esperando cierre de workers...")
    for wk in workers:
        wk.join(timeout=4)

    cv2.destroyAllWindows()

    total_events = sum(s.events_count for s in states)
    LOG.info("Demo finalizado — Total eventos detectados: %d", total_events)
    print(f"\n  Total eventos detectados: {total_events}")
    print(f"  Snapshots guardados en: {snapshot_dir}")


# ==============================================================================
# Helpers
# ==============================================================================

def _play_alert() -> None:
    """Reproduce sonido de alerta en hilo daemon (non-blocking)."""
    def _play():
        try:
            if _AUDIO_AVAILABLE and _BEEP_ASSET.exists():
                _playsound(str(_BEEP_ASSET))
            else:
                # Beep nativo de Windows como fallback
                import winsound
                winsound.Beep(_FALLBACK_BEEP_FREQ, 400)
        except Exception:
            pass
    threading.Thread(target=_play, daemon=True).start()


def _sync_camera_events_to_firebase(camera_id: Optional[str], collection: str) -> None:
    """Sincroniza el archivo JSON de la cámara que originó el evento."""
    if not camera_id:
        LOG.warning("No se puede sincronizar Firebase sin camera_id")
        return
    try:
        log_path = ROOT / "outputs" / f"events_{camera_id}.json"
        connector = FirebaseConnector(
            json_log_path=log_path,
            collection=collection,
        )
        uploaded = connector.sync_new_events()
        if uploaded:
            LOG.info("Firebase: %d evento(s) subidos desde %s", uploaded, log_path)
    except Exception:
        LOG.exception("Error sincronizando eventos de %s a Firebase", camera_id)


def _roi_from_cfg(value: Any) -> Optional[tuple[int, int, int, int]]:
    """Convierte una ROI de config `[x, y, width, height]` a tupla válida."""
    if not value:
        return None
    if isinstance(value, dict):
        value = [value.get("x"), value.get("y"), value.get("width"), value.get("height")]
    if isinstance(value, list) and len(value) == 4 and all(v is not None for v in value):
        return tuple(int(v) for v in value)  # type: ignore[return-value]
    LOG.warning("ROI inválida ignorada: %s", value)
    return None


def _save_manual_screenshot(frame: Optional[np.ndarray], report_dir: Path) -> None:
    """Guarda screenshot manual del frame compuesto actual."""
    if frame is None:
        LOG.warning("No hay frame para capturar")
        return
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"screenshot_manual_{ts}.jpg"
    try:
        cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        LOG.info("Screenshot guardado: %s", path)
        print(f"  Screenshot: {path}")
    except Exception:
        LOG.exception("Error guardando screenshot")


def _generate_pdf(
    event: Optional[Dict],
    report_dir: Path,
    config: Dict,
) -> Optional[str]:
    """Genera PDF del último evento registrado."""
    if event is None:
        LOG.warning("No hay evento para generar PDF — simula una caída primero")
        print("  Sin evento reciente para PDF. Espera que se detecte un evento.")
        return None

    pdf_cfg = config.get("pdf_report", {})
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = report_dir / f"reporte_{event.get('event_type', 'evento')}_{ts}.pdf"

    try:
        gen = ReportGenerator(
            camera_name=event.get("camera_id", pdf_cfg.get("camera_label", "CAM")),
            sector=event.get("zone", pdf_cfg.get("sector_label", "Zona Demo")),
            facility=pdf_cfg.get("facility_name", "Instalaciones Demo"),
        )
        result = gen.generate_report(
            event=event,
            frame_image=None,
            output_dir=str(report_dir),
        )
        if result:
            LOG.info("PDF generado: %s", result)
            print(f"  PDF generado: {result}")
            return str(result)
    except Exception:
        LOG.exception("Error generando PDF")
    return None


# ==============================================================================
# Entry point
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Vigilante Digital IA — Demo 2 cámaras IP"
    )
    parser.add_argument(
        "--config", default=str(DEFAULT_CONFIG),
        help="Ruta al archivo de configuración (default: demo_config.json)"
    )
    parser.add_argument("--cam1", default="", help="URL override cámara 1")
    parser.add_argument("--cam2", default="", help="URL override cámara 2")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    cam_overrides = {"cam1": args.cam1, "cam2": args.cam2}

    run_demo(config, cam_overrides)


if __name__ == "__main__":
    main()
