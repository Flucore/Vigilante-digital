"""Demo del panel de operador conectado al pipeline.

Levanta la API de api/operator_panel.py (uvicorn) en un hilo secundario y
corre runner.run_file en el hilo principal, de modo que ambos compartan
proceso y memoria: los frames anotados llegan al panel por push_frame.

Con un solo video, el hilo principal queda para run_file porque cv2.imshow
lo necesita. Con varios, cada video corre en su propio hilo con su propio
detector y como una cámara distinta del config (en el orden del config, o
el de --cam); en ese caso no hay ventana de OpenCV.

Uso:
    python demo_panel.py --source clip.mp4
    python demo_panel.py --source clip.mp4 --headless --port 8000
    python demo_panel.py --source clip.mp4 --loop --modulo fall_detection
    python demo_panel.py --source a.mp4 b.mp4 c.mp4 --loop
    python demo_panel.py --source a.mp4 b.mp4 --cam CAM_SALA_COMUN CAM_PASILLO
    python demo_panel.py --source a.mp4 b.mp4 c.mp4 d.mp4 --correo --sin-envio

Con --correo, cada caída agrupada se avisa por correo (outputs/notificador_correo.py,
credenciales en .env como en demo_camara_ip.py) y el panel muestra una tarjeta
por caída agrupada, con el estado del correo y la captura del momento de la caída.
Los episodios crudos siguen quedando en el JSONL.

Panel en el navegador: http://127.0.0.1:8000/operator/

Requiere fastapi y uvicorn (no forman parte de requirements-academico.txt).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time
from pathlib import Path

import runner
from core.config_loader import ConfigLoader
import config as app_config

LOG = logging.getLogger("vigilante.demo_panel")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Pipeline + panel de operador en un proceso.")
    p.add_argument(
        "--source", required=True, nargs="+",
        help="Archivo(s) de video a procesar; cada uno es una cámara del panel.",
    )
    p.add_argument("--config", default="config_demo.json", help="Archivo de configuración.")
    p.add_argument(
        "--cam", default=None, nargs="+",
        help="ID(s) de cámara del config, uno por video y en el mismo orden "
             "(default: las primeras cámaras habilitadas).",
    )
    p.add_argument("--headless", action="store_true", help="Sin ventana de OpenCV.")
    p.add_argument("--metodo", choices=["bbox", "pose"], default="pose")
    p.add_argument("--ventana", type=int, default=None)
    p.add_argument(
        "--modulo",
        choices=["fall_detection", "perimeter", "geofence", "aqua"],
        default=None,
        help="Reemplaza modules_active de la cámara del config.",
    )
    p.add_argument(
        "--loop",
        action="store_true",
        help="Repite el video indefinidamente (para narrar sobre el panel).",
    )
    p.add_argument(
        "--esperar",
        action="store_true",
        help="Levanta el panel y espera Enter en la terminal antes de procesar.",
    )
    p.add_argument(
        "--correo",
        action="store_true",
        help="Avisa cada caída agrupada por correo y muestra su captura en el panel.",
    )
    p.add_argument("--env", default=".env", help="Archivo con credenciales SMTP (con --correo).")
    p.add_argument(
        "--para", default="",
        help="Destinatario(s) extra, separados por coma (con --correo).",
    )
    p.add_argument(
        "--sin-envio", action="store_true",
        help="Con --correo: genera imagen y PDF pero no se conecta a SMTP.",
    )
    p.add_argument("--host", default="127.0.0.1", help="Interfaz del panel (default: solo local).")
    p.add_argument("--port", type=int, default=8000)
    return p


def _start_panel(host: str, port: int):
    """Arranca uvicorn en un hilo daemon y espera a que acepte conexiones."""
    try:
        import uvicorn
        from fastapi import FastAPI
        from api import operator_panel
    except ImportError as exc:
        print(
            f"[ERROR] Falta una dependencia del panel ({exc}).\n"
            "  Instala: pip install fastapi uvicorn",
            file=sys.stderr,
        )
        sys.exit(1)

    # operator.html espera el panel bajo /operator
    root_app = FastAPI(title="Vigilante Digital — Demo panel")
    root_app.mount("/operator", operator_panel.operator_app)

    server = uvicorn.Server(uvicorn.Config(root_app, host=host, port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, name="operator-panel", daemon=True)
    thread.start()

    deadline = time.time() + 10.0
    while not server.started:
        if not thread.is_alive() or time.time() > deadline:
            print(f"[ERROR] El panel no pudo iniciar en {host}:{port}.", file=sys.stderr)
            sys.exit(1)
        time.sleep(0.05)

    LOG.info("Panel de operador en http://%s:%d/operator/", host, port)
    return server, thread, operator_panel


def _assign_cameras(loader: ConfigLoader, sources: list[str], cam_ids: list[str] | None):
    """Asocia cada video a una cámara del config.

    Con --cam se usan esos ids, en orden; sin él, las primeras cámaras
    habilitadas. Termina con error si no alcanzan o si un id no existe.
    """
    cameras = loader.get_cameras()
    by_id = {c.id: c for c in cameras}
    if cam_ids:
        if len(cam_ids) != len(sources):
            sys.exit(f"[ERROR] --cam trae {len(cam_ids)} id(s) para {len(sources)} video(s).")
        missing = [c for c in cam_ids if c not in by_id]
        if missing:
            sys.exit(f"[ERROR] Cámara(s) no encontradas o deshabilitadas en el config: {missing}")
        if len(set(cam_ids)) != len(cam_ids):
            sys.exit("[ERROR] --cam repite una cámara: cada video necesita una distinta.")
        chosen = [by_id[c] for c in cam_ids]
    else:
        if len(cameras) < len(sources):
            sys.exit(
                f"[ERROR] {len(sources)} video(s) y solo {len(cameras)} cámara(s) "
                "habilitada(s) en el config."
            )
        chosen = cameras[:len(sources)]
    return list(zip(sources, chosen))


def _frame_count(source: str) -> int:
    """Cuadros del archivo según su cabecera (0 si no lo informa)."""
    import cv2
    cap = cv2.VideoCapture(source)
    try:
        return int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    finally:
        cap.release()


class _VideoWorker(threading.Thread):
    """Procesa un video como una cámara, con su propio detector (run_file)."""

    def __init__(self, loader: ConfigLoader, source: str, cam_id: str,
                 args: argparse.Namespace, stop_event: threading.Event,
                 torch_threads: int | None = None) -> None:
        super().__init__(daemon=True, name=f"demo-{cam_id}")
        self.loader = loader
        self.source = source
        self.cam_id = cam_id
        self.args = args
        self.stop_event = stop_event
        self.torch_threads = torch_threads
        self.applied_threads: int | None = None
        self.end_ts: float = 0.0
        self.error: Exception | None = None

    def run(self) -> None:
        if self.torch_threads:
            # Con el backend OpenMP de PyTorch el límite es por hilo: se fija
            # aquí, en el hilo de esta cámara, antes de crear su detector.
            import torch
            torch.set_num_threads(self.torch_threads)
            self.applied_threads = torch.get_num_threads()
        try:
            runner.run_file(
                self.loader,
                self.source,
                headless=True,  # cv2.imshow solo funciona en el hilo principal
                cam_id_override=self.cam_id,
                metodo=self.args.metodo,
                ventana=self.args.ventana,
                modulo=self.args.modulo,
                loop=self.args.loop,
                show_progress=False,
                stop_event=self.stop_event,
                # Con --correo el aviso lo maneja el notificador, no TriggerManager.
                dispatch_triggers=not self.args.correo,
            )
        except Exception as exc:
            self.error = exc
            LOG.exception("[%s] Falló el procesamiento de %s", self.cam_id, self.source)
        finally:
            self.end_ts = time.perf_counter()


# Instante del primer cuadro procesado por cámara: la medición de fps parte
# ahí y no incluye la carga del modelo.
_first_frame_ts: dict[str, float] = {}


def _timed_sink(sink):
    """Envuelve el receptor de frames para anotar el primer cuadro de cada cámara."""
    def _sink(camera_id, frame):
        _first_frame_ts.setdefault(camera_id, time.perf_counter())
        sink(camera_id, frame)
    return _sink


def _mail_event_sink(notifier, operator_panel, assignments):
    """Receptor de eventos con --correo: encadena el panel y el notificador.

    runner.set_event_sink admite un solo receptor, así que este lo ocupa y
    reparte: el notificador agrupa los fragmentos de una misma caída (D4) y
    solo la caída agrupada llega al panel, como una tarjeta. El correo y la
    captura se anotan en esa tarjeta cuando el envío termina.
    """
    import uuid

    cams = {cam.id: cam for _, cam in assignments}
    sources = {cam.id: src for src, cam in assignments}

    def _on_done(event_id: str):
        def _cb(result) -> None:
            operator_panel.annotate_event(
                event_id, correo=result.texto, captura=result.imagen_path,
            )
        return _cb

    def _sink(event: dict) -> None:
        cam_id = event.get("camera_id")
        cam = cams.get(cam_id)
        if cam is not None:
            event.setdefault("camera_name", cam.name)
        if cam_id in sources:
            # Cuadro limpio de la caída para la imagen del correo.
            event["video_path"] = str(sources[cam_id])
        number = notifier.registrar(event)
        if number is None:
            return
        event["id"] = uuid.uuid4().hex
        event["correo"] = "Correo en preparación…"
        operator_panel.push_event(event)
        LOG.info("Caída %d detectada en %s — preparando correo.", number, cam_id)
        notifier.enviar_async(event, number, _on_done(event["id"]))

    return _sink


def _report_throughput(workers: list[_VideoWorker]) -> None:
    """Imprime los cuadros por segundo procesados por cada cámara (sin --loop).

    Desde el primer cuadro hasta el fin del archivo; excluye la carga del modelo.
    """
    print("\nRendimiento por cámara (sin contar la carga del modelo):")
    for w in workers:
        frames = _frame_count(w.source)
        first = _first_frame_ts.get(w.cam_id)
        elapsed = w.end_ts - first if first else 0.0
        if w.error or frames < 2 or elapsed <= 0:
            print(f"  {w.cam_id:<20} sin medición ({'error' if w.error else 'sin datos'})")
            continue
        threads = w.applied_threads if w.applied_threads else "default"
        print(f"  {w.cam_id:<20} {frames:>5} cuadros en {elapsed:6.1f} s "
              f"-> {(frames - 1) / elapsed:5.1f} fps   hilos torch: {threads}   "
              f"({Path(w.source).name})")
    print(flush=True)


def _torch_threads_per_camera(demo_cfg: dict, n_cameras: int) -> int:
    """Hilos de PyTorch para el detector de cada cámara (solo con varios videos).

    demo.torch_threads_per_camera del config; si es null o falta, se reparten
    los núcleos lógicos del equipo entre las cámaras (12 lógicos, 4 cámaras → 3).
    """
    configured = demo_cfg.get("torch_threads_per_camera")
    if configured:
        return max(1, int(configured))
    return max(1, (os.cpu_count() or 1) // max(1, n_cameras))


def main() -> None:
    args = _build_parser().parse_args()

    try:
        loader = ConfigLoader(Path(args.config))
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    assignments = _assign_cameras(loader, args.source, args.cam)
    multi = len(assignments) > 1
    if multi and not args.headless:
        LOG.info("Varios videos: sin ventana de OpenCV (solo el panel).")

    demo_cfg = loader.get_section("demo", {})
    max_fps = float(demo_cfg.get("panel_max_fps", 12.0))

    notifier = None
    if args.correo:
        # Import diferido: demo_camara_ip importa este módulo.
        from demo_camara_ip import _crear_notificador
        notifier = _crear_notificador(args, loader)

    server, thread, operator_panel = _start_panel(args.host, args.port)
    runner.set_frame_sink(_timed_sink(operator_panel.push_frame), max_fps=max_fps)
    if notifier is None:
        runner.set_event_sink(operator_panel.push_event)
    else:
        runner.set_event_sink(_mail_event_sink(notifier, operator_panel, assignments))
    runner.set_status_sink(operator_panel.push_status)

    # El panel muestra id, nombre y zona del config desde el inicio.
    for _, cam in assignments:
        operator_panel.register_camera(cam.id, name=cam.name, zone=cam.zone)

    stop_event = threading.Event()
    workers: list[_VideoWorker] = []
    try:
        if args.esperar:
            # El panel ya sirve en su hilo: se muestran las cámaras, aún sin feed.
            url = f"http://{args.host}:{args.port}/operator/"
            print(f"Panel listo en {url}. Presiona Enter para iniciar el procesamiento.",
                  flush=True)
            try:
                input()
            except EOFError:
                LOG.warning("Sin entrada estándar: se inicia el procesamiento sin esperar.")

        if not multi:
            source, cam = assignments[0]
            runner.run_file(
                loader,
                source,
                headless=args.headless or app_config.HEADLESS_MODE,
                cam_id_override=cam.id,
                metodo=args.metodo,
                ventana=args.ventana,
                modulo=args.modulo,
                loop=args.loop,
                # Sin barra de progreso: tapa imagen y delata que es un archivo.
                show_progress=False,
                dispatch_triggers=not args.correo,
            )
        else:
            threads = _torch_threads_per_camera(demo_cfg, len(assignments))
            LOG.info("Hilos de PyTorch por cámara: %d (%d cámaras)", threads, len(assignments))
            workers = [_VideoWorker(loader, src, cam.id, args, stop_event, threads)
                       for src, cam in assignments]
            for w in workers:
                w.start()
            while any(w.is_alive() for w in workers):
                for w in workers:
                    w.join(timeout=0.5)
            if not args.loop:
                _report_throughput(workers)

        # Sin --loop, el panel sigue mostrando el último frame hasta Ctrl+C.
        # Con --loop, run_file solo vuelve porque el operador cortó: se sale.
        if not args.loop:
            if notifier is not None:
                LOG.info("Esperando correos pendientes…")
                notifier.cerrar(esperar=True)
            LOG.info("Video(s) terminado(s). Panel sigue activo — Ctrl+C para salir.")
            while thread.is_alive():
                thread.join(timeout=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        # Los hilos de video cierran su episodio abierto antes de salir.
        stop_event.set()
        for w in workers:
            w.join(timeout=10.0)
        if notifier is not None:
            notifier.cerrar(esperar=False)
        runner.set_frame_sink(None)
        runner.set_event_sink(None)
        runner.set_status_sink(None)
        server.should_exit = True
        thread.join(timeout=5.0)


if __name__ == "__main__":
    main()
