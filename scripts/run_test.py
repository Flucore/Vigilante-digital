"""
Script de pruebas para Vigilante Digital IA.
Procesa un video MP4, captura métricas y registra resultados.

Uso:
    python scripts/run_test.py --video tests/test_videos/fall_sample_01.mp4 --output test_outputs
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

# Cuando ejecutamos el script directamente (python scripts/run_test.py),
# Python añade `scripts/` al sys.path. Para poder importar los paquetes del
# proyecto (p.ej. `core`, `outputs`) añadimos la raíz del proyecto al
# `sys.path` antes de las importaciones locales.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Importar módulos del proyecto
from core.pose_detector import PoseDetector
from outputs.json_logger import JSONLogger
from outputs.event_logger import EventLogger
from outputs.firebase_connector import FirebaseConnector
from outputs.report_generator import ReportGenerator
from outputs.email_sender import EmailSender
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
LOG = logging.getLogger(__name__)


class VideoTestHarness:
    """Harness para ejecutar pruebas de video con captura de métricas."""

    def __init__(self, video_path: str, output_dir: str = "test_outputs"):
        self.video_path = Path(video_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)

        # Configuración para pruebas (overrides)
        self.json_log_path = self.output_dir / "events_history.jsonl"
        self.event_log_path = self.output_dir / "events_log.jsonl"
        self.metrics_path = self.output_dir / "test_metrics.json"

        # Métricas
        self.metrics = {
            "start_time": datetime.now().isoformat(),
            "video_path": str(self.video_path),
            "total_frames": 0,
            "total_falls_detected": 0,
            "total_events_completed": 0,
            "avg_fps": 0.0,
            "min_fps": float('inf'),
            "max_fps": 0.0,
            "total_process_time": 0.0,
            "firebase_syncs": 0,
            "firebase_events_uploaded": 0,
            "errors": [],
            "end_time": None,
            "use_event_logger": config.USE_EVENT_LOGGER,
        }

        self.frame_times = []

    def run(self) -> bool:
        """Ejecuta la prueba completa."""
        try:
            # 1. Abrir video
            cap = cv2.VideoCapture(str(self.video_path))
            if not cap.isOpened():
                raise RuntimeError(f"No se pudo abrir video: {self.video_path}")

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps_video = cap.get(cv2.CAP_PROP_FPS)
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            LOG.info(f"Video abierto: {total_frames} frames @ {fps_video:.2f} fps, {w}x{h}")
            self.metrics["video_fps"] = fps_video
            self.metrics["video_resolution"] = f"{w}x{h}"

            # 2. Inicializar componentes
            # Optimized defaults for faster processing in tests
            detector = PoseDetector(complexity=0, frame_scale=0.6)
            json_logger = JSONLogger(file_path=self.json_log_path)
            event_logger = EventLogger(self.event_log_path) if config.USE_EVENT_LOGGER else None
            connector = FirebaseConnector(
                json_log_path=self.event_log_path if config.USE_EVENT_LOGGER else self.json_log_path,
                collection=config.FIRESTORE_COLLECTION
            )
            report_gen = ReportGenerator(camera_name="Prueba Video", sector="Demo")

            # 3. Procesar video
            frame_idx = 0
            fall_count = 0
            events_completed = 0
            p_time = time.time()

            detection_skip = getattr(config, 'DETECTION_SKIP', 2)
            frame_idx = 0
            last_bbox = None

            while cap.isOpened():
                success, frame = cap.read()
                if not success:
                    LOG.info("Fin del video")
                    break

                frame_start = time.time()

                frame_idx += 1

                # Procesamiento reducido: solo cada N frames para ahorrar CPU
                do_detection = (detection_skip <= 1) or (frame_idx % detection_skip == 0)
                if do_detection:
                    proc_frame, results = detector.find_pose(frame, draw=True)
                    lm_list, bbox = detector.find_position(proc_frame, results, draw=True)
                    last_bbox = bbox
                else:
                    proc_frame = frame
                    bbox = last_bbox or {}

                # Lógica de caída
                if bbox:
                    aspect_ratio = bbox["height"] / max(1, bbox["width"])
                    is_falling = aspect_ratio < 0.8
                    
                    if config.USE_EVENT_LOGGER and event_logger:
                        # v2.0: Usar máquina de estados
                        metadata = {"aspect_ratio": aspect_ratio, "frame_idx": frame_idx}
                        completed_event = event_logger.update(
                            is_falling=is_falling,
                            frame_idx=frame_idx,
                            photo_path=None,
                            metadata=metadata
                        )
                        
                        if completed_event:
                            events_completed += 1
                            event_logger.log_event(completed_event)
                            LOG.info(f"✓ Evento completado #{events_completed}: {completed_event.get('event_type')} (duración: {completed_event.get('duration_seconds'):.2f}s)")
                            cv2.putText(proc_frame, f"EVENTO #{events_completed}", (bbox["xmin"], bbox["ymin"] - 40),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                            # Generar PDF del evento inmediatamente
                            pdf_path = None
                            try:
                                pdf_path = report_gen.generate_report(event=completed_event, frame_image=proc_frame, output_dir=str(self.output_dir))
                                if pdf_path:
                                    LOG.info(f"Reporte PDF generado: {pdf_path}")
                                    # Preguntar si enviar por correo (no bloquea la visualización)
                                    self._offer_email_send(pdf_path, completed_event)
                            except Exception:
                                LOG.exception("Error generando PDF del evento")
                        
                        if is_falling:
                            fall_count += 1
                            cv2.putText(proc_frame, "CAYENDO...", (bbox["xmin"], bbox["ymin"] - 20),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                            cv2.rectangle(proc_frame, (bbox["xmin"], bbox["ymin"]), (bbox["xmax"], bbox["ymax"]), (0, 0, 255), 3)
                    else:
                        # v1.0: Compatibilidad - registrar cada frame (LEGACY)
                        if is_falling:
                            fall_count += 1
                            cv2.putText(proc_frame, f"CAIDA DETECTADA #{fall_count}", (bbox["xmin"], bbox["ymin"] - 40),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                            
                            # Log evento
                            json_logger.log_event(
                                photo_path=str(self.output_dir / f"fall_{fall_count:03d}_frame_{frame_idx:06d}.jpg"),
                                event_type="fall",
                                metadata={"aspect_ratio": aspect_ratio, "frame_idx": frame_idx}
                            )
                            LOG.info(f"✓ Caída detectada en frame {frame_idx} (ratio={aspect_ratio:.2f})")
                        else:
                            cv2.rectangle(proc_frame, (bbox["xmin"], bbox["ymin"]), (bbox["xmax"], bbox["ymax"]), (0, 255, 0), 2)

                # FPS
                c_time = time.time()
                fps = 1.0 / max(1e-6, (c_time - p_time))
                p_time = c_time
                self.frame_times.append(fps)
                self.metrics["max_fps"] = max(self.metrics["max_fps"], fps)
                self.metrics["min_fps"] = min(self.metrics["min_fps"], fps)

                cv2.putText(proc_frame, f'FPS: {int(fps)}', (20, 70), cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 0), 3)

                if not config.HEADLESS_MODE:
                    # Mostrar (sin redimensionar innecesariamente)
                    try:
                        frame_show = proc_frame
                        cv2.imshow("Test: Vigilante IA", frame_show)
                    except Exception:
                        cv2.imshow("Test: Vigilante IA", cv2.resize(proc_frame, (1280, 720)))
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break


                # Cada 100 frames, imprimir progreso
                if frame_idx % 100 == 0:
                    LOG.info(f"Procesados {frame_idx}/{total_frames} frames ({100*frame_idx/total_frames:.1f}%)")

            cap.release()
            if not config.HEADLESS_MODE:
                cv2.destroyAllWindows()

            # 4. Finalizar y sincronizar Firebase
            if config.USE_EVENT_LOGGER and event_logger:
                # Forzar cierre de evento pendiente
                final_event = event_logger.finalize()
                if final_event:
                    events_completed += 1
                    event_logger.log_event(final_event)
                    LOG.info(f"✓ Evento final forzado: {final_event.get('event_type')}")
            
            self.metrics["total_frames"] = frame_idx
            self.metrics["total_falls_detected"] = fall_count
            self.metrics["total_events_completed"] = events_completed
            self.metrics["avg_fps"] = sum(self.frame_times) / len(self.frame_times) if self.frame_times else 0
            self.metrics["total_process_time"] = time.time() - p_time

            # Firebase sync
            LOG.info("Sincronizando eventos a Firebase...")
            uploaded = connector.sync_new_events()
            self.metrics["firebase_syncs"] = 1
            self.metrics["firebase_events_uploaded"] = uploaded
            LOG.info(f"✓ {uploaded} eventos subidos a Firestore")

            self.metrics["end_time"] = datetime.now().isoformat()
            self.metrics["success"] = True

            return True

        except Exception as exc:
            LOG.exception(f"Error durante prueba: {exc}")
            self.metrics["errors"].append(str(exc))
            self.metrics["end_time"] = datetime.now().isoformat()
            self.metrics["success"] = False
            return False

        finally:
            self.save_metrics()

    def save_metrics(self) -> None:
        """Guarda las métricas en JSON."""
        try:
            with open(self.metrics_path, "w", encoding="utf-8") as fh:
                json.dump(self.metrics, fh, indent=2, ensure_ascii=False)
            LOG.info(f"✓ Métricas guardadas en: {self.metrics_path}")
            
            # Imprimir resumen
            print("\n" + "="*60)
            print("RESUMEN DE PRUEBA")
            print("="*60)
            print(f"Video: {self.metrics['video_path']}")
            print(f"Total de frames: {self.metrics['total_frames']}")
            print(f"Caídas detectadas: {self.metrics['total_falls_detected']}")
            if config.USE_EVENT_LOGGER:
                print(f"Eventos completados: {self.metrics['total_events_completed']}")
                print(f"Reducción de datos: {100 - (self.metrics['total_events_completed']*100 / max(1, self.metrics['total_falls_detected'])):.1f}%")
            print(f"FPS promedio: {self.metrics['avg_fps']:.2f}")
            print(f"FPS min/max: {self.metrics['min_fps']:.2f}/{self.metrics['max_fps']:.2f}")
            print(f"Eventos subidos a Firebase: {self.metrics['firebase_events_uploaded']}")
            print(f"Estado: {'✓ EXITOSO' if self.metrics['success'] else '✗ CON ERRORES'}")
            print("="*60 + "\n")

        except Exception as exc:
            LOG.exception(f"Error guardando métricas: {exc}")

    def _offer_email_send(self, pdf_path: str, event: dict) -> None:
        """Ofrece al usuario enviar el reporte por correo de forma no bloqueante."""
        try:
            response = input(
                f"\n¿Deseas enviar el reporte por correo? (s/n): "
            ).strip().lower()
            
            if response != 's':
                return
            
            # Obtener credenciales
            sender_email, app_password = EmailSender.get_credentials_from_env()
            if not sender_email or not app_password:
                LOG.warning("Credenciales de Gmail no configuradas. Configura GMAIL_SENDER_EMAIL y GMAIL_APP_PASSWORD")
                print("\nPara enviar por correo, configura las credenciales:")
                print("  $env:GMAIL_SENDER_EMAIL = 'tu@gmail.com'")
                print("  $env:GMAIL_APP_PASSWORD = 'xxxx xxxx xxxx xxxx'")
                return
            
            # Solicitar destinatario
            recipient = EmailSender.prompt_recipient()
            if not recipient:
                return
            
            # Enviar
            LOG.info("Enviando reporte por correo...")
            sender = EmailSender(sender_email=sender_email, app_password=app_password)
            success = sender.send_report(
                recipient_email=recipient,
                pdf_path=pdf_path,
                subject="Alerta: Caída Detectada - Sistema de Vigilancia",
                body=(
                    f"Se ha detectado una caída en el sistema de vigilancia.\n\n"
                    f"Duración: {event.get('duration_seconds', 0):.2f} segundos\n"
                    f"Fecha y hora: {event.get('start_time', 'Desconocida')}\n\n"
                    f"Por favor, revise el reporte adjunto para más detalles.\n\n"
                    f"Sistema de Vigilancia Digital IA"
                )
            )
            
            if success:
                print(f"\n✓ Reporte enviado exitosamente a {recipient}")
            
        except KeyboardInterrupt:
            LOG.info("Envío de correo cancelado por el usuario")
        except Exception as exc:
            LOG.exception(f"Error durante envío de correo: {exc}")


def main():
    parser = argparse.ArgumentParser(description="Prueba Vigilante Digital IA con video local")
    parser.add_argument("--video", required=True, help="Ruta al archivo MP4")
    parser.add_argument("--output", default="test_outputs", help="Directorio de salida para métricas")
    args = parser.parse_args()

    harness = VideoTestHarness(video_path=args.video, output_dir=args.output)
    success = harness.run()
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
