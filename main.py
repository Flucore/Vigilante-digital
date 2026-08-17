import cv2
import time
import threading
import logging
from typing import Optional

from core.pose_detector import PoseDetector
from outputs.firebase_connector import FirebaseConnector
from outputs.event_logger import EventLogger
import config

# --- CONFIGURACIÓN RÁPIDA PARA PRUEBAS ---
# Reemplaza esto con el nombre del video que descargaste o pasar por línea de comandos
VIDEO_PATH = "tu_video_de_caida.mp4"
# -----------------------------------------

LOG = logging.getLogger(__name__)


def _start_periodic_sync(conn: FirebaseConnector, interval: int, stop_evt: threading.Event) -> threading.Thread:
    """Inicia un hilo daemon que llama a conn.sync_new_events() cada `interval` segundos."""

    def _worker() -> None:
        while stop_evt.is_set():
            try:
                uploaded = conn.sync_new_events()
                if uploaded:
                    LOG.info("Firebase: %d events uploaded", uploaded)
            except Exception:
                LOG.exception("Periodic sync failed")
            # Esperar `interval` segundos, pero permitir salida rápida
            for _ in range(max(1, int(interval))):
                if not stop_evt.is_set():
                    break
                time.sleep(1)

    t = threading.Thread(target=_worker, daemon=True, name="firebase-sync")
    t.start()
    return t


def main(video_path: Optional[str] = None) -> None:
    video_path = video_path or VIDEO_PATH
    headless = config.HEADLESS_MODE

    # 1. Inicializar Entrada de Video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        LOG.error("Error: No se pudo abrir el video: %s", video_path)
        return

    # 2. Inicializar el Cerebro (Detector de Pose)
    detector = PoseDetector(complexity=1)

    # 3. Inicializar FirebaseConnector (no incluye credenciales; use GOOGLE_APPLICATION_CREDENTIALS)
    connector = FirebaseConnector(
        json_log_path=config.EVENT_LOG_PATH if config.USE_EVENT_LOGGER else config.JSON_LOG_PATH,
        collection=config.FIRESTORE_COLLECTION
    )

    # 4. Inicializar EventLogger si está habilitado (v2.0)
    event_logger = EventLogger(config.EVENT_LOG_PATH) if config.USE_EVENT_LOGGER else None

    # 5. Hilo daemon de sincronización periódica (no bloquea bucle principal)
    stop_event = threading.Event()
    stop_event.set()
    sync_thread = _start_periodic_sync(connector, config.SYNC_INTERVAL, stop_event)

    p_time = time.time()
    frame_idx = 0

    LOG.info("Iniciando Sistema Modular Vigilante IA (v2.0 - EventLogger: %s)...", config.USE_EVENT_LOGGER)

    try:
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                LOG.info("Fin del video.")
                break

            frame_idx += 1

            # Procesar frame (find_pose ahora devuelve (img, results))
            proc_frame, results = detector.find_pose(frame, draw=True)

            # Extraer posición
            lm_list, bbox = detector.find_position(proc_frame, results, draw=True)

            # Detección preliminar de caída
            is_falling = False
            if bbox:
                aspect_ratio = bbox["height"] / max(1, bbox["width"])
                is_falling = aspect_ratio < 0.8
                
                if config.USE_EVENT_LOGGER and event_logger:
                    # v2.0: Usar máquina de estados para agrupar frames en eventos
                    metadata = {"aspect_ratio": aspect_ratio, "frame_idx": frame_idx}
                    completed_event = event_logger.update(
                        is_falling=is_falling,
                        frame_idx=frame_idx,
                        photo_path=None,  # Opcional: guardar frame si necesarias
                        metadata=metadata
                    )
                    
                    # Si se completó un evento (transición FALLING→NORMAL), guardar y subir
                    if completed_event:
                        LOG.info("Event completed: %s (duration %.2fs)", completed_event.get("event_type"), completed_event.get("duration_seconds"))
                        event_logger.log_event(completed_event)
                        threading.Thread(target=connector.sync_new_events, daemon=True).start()
                    
                    if is_falling:
                        cv2.putText(proc_frame, "CAIDA DETECTADA", (bbox["xmin"], bbox["ymin"] - 20),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    cv2.rectangle(proc_frame, (bbox["xmin"], bbox["ymin"]), (bbox["xmax"], bbox["ymax"]), 
                                  (0, 0, 255) if is_falling else (0, 255, 0), 3)
                else:
                    # v1.0: Compatibilidad - registrar cada frame (LEGACY)
                    if is_falling:
                        cv2.putText(proc_frame, "POSIBLE CAIDA (Ratio)", (bbox["xmin"], bbox["ymin"] - 20),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                        cv2.rectangle(proc_frame, (bbox["xmin"], bbox["ymin"]), (bbox["xmax"], bbox["ymax"]), (0, 0, 255), 3)
                        threading.Thread(target=connector.sync_new_events, daemon=True).start()
                    else:
                        cv2.putText(proc_frame, "Persona Detectada", (bbox["xmin"], bbox["ymin"] - 20),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Cálculo de FPS
            c_time = time.time()
            fps = 1.0 / max(1e-6, (c_time - p_time))
            p_time = c_time
            cv2.putText(proc_frame, f'FPS: {int(fps)}', (20, 70), cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 0), 3)

            # Mostrar resultado (escalar para pantalla si es necesario)
            try:
                frame_show = cv2.resize(proc_frame, (1280, 720))
            except Exception:
                frame_show = proc_frame

            if not headless:
                cv2.imshow("Vigilante IA - Modular Test", frame_show)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
    finally:
        # Forzar cierre de evento pendiente al terminar
        if config.USE_EVENT_LOGGER and event_logger:
            final_event = event_logger.finalize()
            if final_event:
                LOG.info("Final event (forced): %s", final_event.get("event_type"))
                event_logger.log_event(final_event)
                connector.sync_new_events()
        
        # Señalar al hilo que debe parar y esperar un poco
        stop_event.clear()
        sync_thread.join(timeout=3)
        cap.release()
        if not headless:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

