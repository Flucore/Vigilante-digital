"""Demo: análisis de clips propios con aviso por correo, desde el navegador.

Levanta en un proceso:
  /analisis/  — página para elegir y analizar los clips del catálogo
                (config_demo_correo.json → "clips"), ver el video procesado,
                el resultado de cada clip y el estado de cada correo.
  /operator/  — el panel de operador de siempre (mismo video y eventos).

Cada clip se procesa como si fuera la cámara IP CAM_IP_01, uno tras otro, con
runner.run_file (sin modificarlo). Por cada caída confirmada se envía un correo
con la imagen del momento, la fecha y hora del análisis y la ubicación (la
descripción de la escena del catálogo), más el reporte PDF adjunto.

Credenciales: .env (SMTP_USER, SMTP_PASSWORD, EMAIL_RECIPIENTS). Sin ellas, o
con --sin-envio, corre en simulado: genera imagen y PDF pero no envía.

Uso:
    python demo_analisis.py               # abre http://127.0.0.1:8000/analisis/
    python demo_analisis.py --sin-envio   # ensayo sin enviar correos
    python demo_analisis.py --no-abrir    # no abre el navegador
"""
from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
import uuid
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import cv2  # noqa: E402

import runner  # noqa: E402
from core.config_loader import ConfigLoader  # noqa: E402
from demo_camara_ip import _crear_notificador  # noqa: E402
from outputs.notificador_correo import ResultadoEnvio, enmascarar  # noqa: E402

LOG = logging.getLogger("vigilante.demo_analisis")
ROOT = Path(__file__).resolve().parent
PANEL_WIDTH = 960   # ancho de los cuadros que se envían al navegador


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Análisis de clips + correo por caída, en el navegador.")
    p.add_argument("--config", default="config_demo_correo.json")
    p.add_argument("--metodo", choices=["bbox", "pose"], default="bbox")
    p.add_argument("--env", default=".env")
    p.add_argument("--para", default="", help="Destinatario(s) extra, separados por coma.")
    p.add_argument("--sin-envio", action="store_true", help="Ensayo: imagen y PDF sí, correo no.")
    p.add_argument("--no-abrir", action="store_true", help="No abrir el navegador.")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    return p


def _duracion(path: Path) -> tuple[float, int]:
    cap = cv2.VideoCapture(str(path))
    try:
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        return (frames / fps if frames else 0.0), frames
    finally:
        cap.release()


class Controlador:
    """Estado de la tanda y orquestación clip por clip (lo usa api/analisis_clips)."""

    def __init__(self, loader: ConfigLoader, notificador, operator_panel, cam, metodo: str) -> None:
        self.loader = loader
        self.notificador = notificador
        self.panel = operator_panel
        self.cam = cam
        self.metodo = metodo
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._hilo: Optional[threading.Thread] = None
        self._actual: Optional[str] = None
        self._frames_actual = 0
        self._clips: Dict[str, Dict[str, Any]] = {}
        for c in loader.get_section("clips", []) or []:
            path = ROOT / c["archivo"]
            dur, frames = _duracion(path) if path.exists() else (0.0, 0)
            self._clips[str(c["id"])] = {
                "id": str(c["id"]), "archivo": Path(c["archivo"]).name, "ruta": path,
                "ubicacion": c.get("ubicacion", ""), "nota": c.get("nota", ""),
                "esperado": c.get("esperado", ""), "duracion_s": round(dur, 1),
                "frames": frames, "existe": path.exists(),
                **self._estado_inicial(),
            }

    @staticmethod
    def _estado_inicial() -> Dict[str, Any]:
        return {"estado": "pendiente", "avance": 0.0, "caidas": 0, "hora_deteccion": None,
                "correo": None, "correo_ok": None, "imagen": None, "resultado": None,
                "error": None}

    # ── receptores del runner (hilo de procesamiento) ─────────────────────────

    def receptor_frame(self, camera_id: str, frame) -> None:
        with self._lock:
            self._frames_actual += 1
        h, w = frame.shape[:2]
        if w > PANEL_WIDTH:
            frame = cv2.resize(frame, (PANEL_WIDTH, int(h * PANEL_WIDTH / w)),
                               interpolation=cv2.INTER_AREA)
        self.panel.push_frame(camera_id, frame)

    def receptor_evento(self, event: dict) -> None:
        with self._lock:
            clip = self._clips.get(self._actual or "")
        if clip is None:
            return
        event["camera_name"] = self.cam.name
        event["ubicacion"] = clip["ubicacion"]
        event["zone"] = clip["ubicacion"]
        event["clip"] = clip["archivo"]
        event["video_path"] = str(clip["ruta"])   # para sacar el cuadro limpio de la caída
        numero = self.notificador.registrar(event)
        if numero is None:
            return
        event["id"] = uuid.uuid4().hex
        event["correo"] = "Correo en preparación…"
        self.panel.push_event(event)
        with self._lock:
            clip["caidas"] += 1
            clip["hora_deteccion"] = event["hora_analisis"][11:19]
            clip["correo"] = "Correo en preparación…"
        LOG.info("⚠ Caída detectada · clip %s · %s", clip["id"], clip["ubicacion"])
        self.notificador.enviar_async(event, numero, self._al_terminar(clip["id"], event["id"]))

    def _al_terminar(self, clip_id: str, event_id: str):
        def _cb(r: ResultadoEnvio) -> None:
            with self._lock:
                clip = self._clips[clip_id]
                clip["correo"] = r.texto
                clip["correo_ok"] = bool(r.enviado or r.simulado)
                if r.imagen_path:
                    clip["imagen"] = r.imagen_path
            self.panel.annotate_event(event_id, correo=r.texto)
        return _cb

    # ── API para api/analisis_clips ───────────────────────────────────────────

    def estado(self) -> dict:
        with self._lock:
            clips = []
            for c in self._clips.values():
                d = {k: v for k, v in c.items() if k not in ("ruta", "imagen")}
                d["tiene_imagen"] = bool(c["imagen"])
                if c["id"] == self._actual and c["frames"]:
                    d["avance"] = min(1.0, self._frames_actual / c["frames"])
                clips.append(d)
            terminados = [c for c in self._clips.values() if c["estado"] == "terminado"]
            cred = self.notificador.credenciales
            return {
                "ocupado": self._hilo is not None and self._hilo.is_alive(),
                "actual": self._actual,
                "camara": {"id": self.cam.id, "nombre": self.cam.name},
                "metodo": self.metodo,
                "correo": {
                    "modo": "simulado" if self.notificador.simulado else "real",
                    "remitente": enmascarar(cred.remitente) if cred.remitente else "",
                    "destinatarios": [enmascarar(d) for d in cred.destinatarios],
                },
                "clips": clips,
                "resumen": {
                    "analizados": len(terminados),
                    "caidas_esperadas": sum(c["esperado"] == "caida" for c in terminados),
                    "caidas_detectadas": sum(c["resultado"] == "acierto_caida" for c in terminados),
                    "falsas_alarmas": sum(c["resultado"] == "falsa_alarma" for c in terminados),
                    "correos": sum(1 for c in self._clips.values() if c["correo_ok"]),
                },
            }

    def iniciar(self, ids: Optional[List[str]]) -> None:
        with self._lock:
            if self._hilo is not None and self._hilo.is_alive():
                raise RuntimeError("Ya hay un análisis en curso.")
            seleccion = list(ids) if ids else list(self._clips)
            for i in seleccion:
                if i not in self._clips:
                    raise ValueError(f"Clip desconocido: {i}")
                if not self._clips[i]["existe"]:
                    raise ValueError(f"No está el video del clip {i}: {self._clips[i]['archivo']}")
            for i in seleccion:
                self._clips[i].update(self._estado_inicial(), estado="en_cola")
            self._stop.clear()
            self.notificador.reiniciar_sesion()
            self._hilo = threading.Thread(target=self._tanda, args=(seleccion,),
                                          name="analisis-clips", daemon=True)
            self._hilo.start()

    def detener(self) -> None:
        self._stop.set()

    def probar_correo(self) -> dict:
        from demo_camara_ip import _probar_correo_resultado
        r = _probar_correo_resultado(self.notificador)
        return {"ok": bool(r and (r.enviado or r.simulado)),
                "texto": r.texto if r else "Sin respuesta en 60 s"}

    def ruta_imagen(self, clip_id: str) -> Optional[str]:
        with self._lock:
            clip = self._clips.get(clip_id)
            return clip["imagen"] if clip else None

    # ── tanda (hilo propio) ───────────────────────────────────────────────────

    def _tanda(self, seleccion: List[str]) -> None:
        for clip_id in seleccion:
            if self._stop.is_set():
                break
            clip = self._clips[clip_id]
            with self._lock:
                self._actual = clip_id
                self._frames_actual = 0
                clip["estado"] = "analizando"
            self.notificador.agrupador.reiniciar(self.cam.id)
            # El panel de operador muestra la escena actual como zona de la cámara.
            self.panel.register_camera(self.cam.id, status="online",
                                       name=self.cam.name, zone=clip["ubicacion"])
            LOG.info("▶ Clip %s · %s · %s", clip_id, clip["archivo"], clip["ubicacion"])
            try:
                runner.run_file(
                    self.loader, str(clip["ruta"]), headless=True,
                    cam_id_override=self.cam.id, metodo=self.metodo,
                    show_progress=False, dispatch_triggers=False, stop_event=self._stop,
                )
                error = None
            except Exception as exc:  # un clip roto no corta la tanda
                LOG.exception("Falló el clip %s", clip_id)
                error = str(exc)
            # Deja terminar los correos de este clip antes de cerrar su fila.
            time.sleep(0.2)
            with self._lock:
                clip["avance"] = 1.0 if not self._stop.is_set() else clip.get("avance", 0)
                clip["estado"] = "error" if error else ("detenido" if self._stop.is_set() else "terminado")
                clip["error"] = error
                hubo = clip["caidas"] > 0
                if clip["esperado"] == "caida":
                    clip["resultado"] = "acierto_caida" if hubo else "caida_no_detectada"
                else:
                    clip["resultado"] = "falsa_alarma" if hubo else "acierto_sin_caida"
        with self._lock:
            for c in self._clips.values():
                if c["estado"] == "en_cola":
                    c["estado"] = "pendiente"
            self._actual = None


def _levantar_servidor(host: str, port: int, controlador_factory):
    import uvicorn
    from fastapi import FastAPI
    from fastapi.responses import RedirectResponse
    from api import operator_panel
    from api.analisis_clips import crear_app

    controlador = controlador_factory(operator_panel)
    root = FastAPI(title="Vigía Digital — Demo análisis", docs_url=None, redoc_url=None)
    root.mount("/operator", operator_panel.operator_app)
    root.mount("/analisis", crear_app(controlador))

    @root.get("/", include_in_schema=False)
    def _inicio():
        return RedirectResponse("/analisis/")

    server = uvicorn.Server(uvicorn.Config(root, host=host, port=port, log_level="warning"))
    hilo = threading.Thread(target=server.run, name="demo-analisis-http", daemon=True)
    hilo.start()
    limite = time.time() + 10
    while not server.started:
        if not hilo.is_alive() or time.time() > limite:
            sys.exit(f"[ERROR] No se pudo iniciar el servidor en {host}:{port} "
                     "(¿quedó otro proceso usando el puerto?).")
        time.sleep(0.05)
    return server, hilo, controlador


def main() -> None:
    args = _build_parser().parse_args()
    try:
        loader = ConfigLoader(Path(args.config))
    except (FileNotFoundError, ValueError) as exc:
        sys.exit(str(exc))
    if not loader.get_section("clips", []):
        sys.exit(f"[ERROR] {args.config} no tiene sección 'clips'.")
    cams = loader.get_cameras()
    if not cams:
        sys.exit("[ERROR] El config no tiene cámaras habilitadas.")
    cam = cams[0]

    args.probar_correo = False  # _crear_notificador lo espera en args
    notificador = _crear_notificador(args, loader)

    def _factory(panel):
        return Controlador(loader, notificador, panel, cam, args.metodo)

    server, hilo, ctl = _levantar_servidor(args.host, args.port, _factory)
    runner.set_frame_sink(ctl.receptor_frame, max_fps=0)   # 0 = todos los cuadros (avance)
    runner.set_status_sink(ctl.panel.push_status)
    runner.set_event_sink(ctl.receptor_evento)
    ctl.panel.register_camera(cam.id, status="esperando", name=cam.name, zone="")

    faltan = [c["archivo"] for c in ctl.estado()["clips"] if not c["existe"]]
    if faltan:
        LOG.warning("Faltan videos del catálogo: %s", ", ".join(faltan))
    url = f"http://{args.host}:{args.port}/analisis/"
    print(f"Interfaz de análisis: {url}\nPanel de operador:   "
          f"http://{args.host}:{args.port}/operator/\nCtrl+C para salir.", flush=True)
    if not args.no_abrir:
        webbrowser.open(url)
    try:
        while hilo.is_alive():
            hilo.join(timeout=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        ctl.detener()
        notificador.cerrar(esperar=False)
        runner.set_frame_sink(None)
        runner.set_event_sink(None)
        runner.set_status_sink(None)
        server.should_exit = True
        hilo.join(timeout=5.0)


if __name__ == "__main__":
    main()
