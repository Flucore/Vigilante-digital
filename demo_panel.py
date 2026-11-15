"""Demo del panel de operador conectado al pipeline.

Levanta la API de api/operator_panel.py (uvicorn) en un hilo secundario y
corre runner.run_file en el hilo principal, de modo que ambos compartan
proceso y memoria: los frames anotados llegan al panel por push_frame.

El hilo principal queda para run_file porque cv2.imshow lo necesita.

Uso:
    python demo_panel.py --source clip.mp4
    python demo_panel.py --source clip.mp4 --headless --port 8000
    python demo_panel.py --source clip.mp4 --loop --modulo fall_detection

Panel en el navegador: http://127.0.0.1:8000/operator/

Requiere fastapi y uvicorn (no forman parte de requirements-academico.txt).
"""
from __future__ import annotations

import argparse
import logging
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
    p.add_argument("--source", required=True, help="Archivo de video a procesar.")
    p.add_argument("--config", default="config_demo.json", help="Archivo de configuración.")
    p.add_argument("--cam", default=None, help="ID de cámara del config a usar.")
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


def _camera_id(loader: ConfigLoader, override: str | None) -> str | None:
    """Cámara que usará run_file: la indicada con --cam o la primera habilitada."""
    cameras = loader.get_cameras()
    if not cameras:
        return None
    if override:
        found = next((c for c in cameras if c.id == override), None)
        if found:
            return found.id
    return cameras[0].id


def main() -> None:
    args = _build_parser().parse_args()

    try:
        loader = ConfigLoader(Path(args.config))
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    demo_cfg = loader.get_section("demo", {})
    max_fps = float(demo_cfg.get("panel_max_fps", 12.0))

    server, thread, operator_panel = _start_panel(args.host, args.port)
    runner.set_frame_sink(operator_panel.push_frame, max_fps=max_fps)
    runner.set_event_sink(operator_panel.push_event)
    runner.set_status_sink(operator_panel.push_status)

    try:
        if args.esperar:
            # El panel ya sirve en su hilo: se muestra la cámara, aún sin feed.
            cam_id = _camera_id(loader, args.cam)
            if cam_id:
                operator_panel.register_camera(cam_id)
            url = f"http://{args.host}:{args.port}/operator/"
            print(f"Panel listo en {url}. Presiona Enter para iniciar el procesamiento.",
                  flush=True)
            try:
                input()
            except EOFError:
                LOG.warning("Sin entrada estándar: se inicia el procesamiento sin esperar.")

        runner.run_file(
            loader,
            args.source,
            headless=args.headless or app_config.HEADLESS_MODE,
            cam_id_override=args.cam,
            metodo=args.metodo,
            ventana=args.ventana,
            modulo=args.modulo,
            loop=args.loop,
            # Sin barra de progreso: tapa imagen y delata que es un archivo.
            show_progress=False,
        )
        # Sin --loop, el panel sigue mostrando el último frame hasta Ctrl+C.
        # Con --loop, run_file solo vuelve porque el operador cortó: se sale.
        if not args.loop:
            LOG.info("Video terminado. Panel sigue activo — Ctrl+C para salir.")
            while thread.is_alive():
                thread.join(timeout=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        runner.set_frame_sink(None)
        runner.set_event_sink(None)
        runner.set_status_sink(None)
        server.should_exit = True
        thread.join(timeout=5.0)


if __name__ == "__main__":
    main()
