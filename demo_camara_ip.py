"""Demo: cámara IP simulada + panel de operador + aviso por correo.

Variante de demo_panel.py para mostrar el envío automático de correo en la
presentación. Procesa UN video como si fuera una cámara IP del hospital
(por defecto data/demo/caidas_demo_30s.mp4: 5 caídas en ~34 s) y, por cada
caída, envía un correo con el reporte PDF adjunto.

No modifica runner.py ni el detector: se engancha a runner.set_event_sink
(el mismo receptor que usa el panel) y delega el correo en
outputs/notificador_correo.py, que agrupa los fragmentos de una misma caída
(una caída = un correo) y pone un tope por sesión.

Credenciales y destinatarios: archivo .env en la raíz (ver .env.example):
    SMTP_USER=cuenta.remitente@gmail.com
    SMTP_PASSWORD=xxxx xxxx xxxx xxxx      (contraseña de aplicación de Gmail)
    EMAIL_RECIPIENTS=uno@dominio.cl, otro@dominio.cl
Sin .env completo corre en modo simulado: genera los PDF, no envía.

Uso:
    python demo_camara_ip.py                       # video de demo, envío real si hay .env
    python demo_camara_ip.py --sin-envio           # ensayo: PDF sí, correo no
    python demo_camara_ip.py --esperar             # panel listo, parte con Enter (para grabar)
    python demo_camara_ip.py --probar-correo       # un correo de prueba y termina
    python demo_camara_ip.py --source otro.mp4 --para jefe@dominio.cl

Panel en el navegador: http://127.0.0.1:8000/operator/
"""
from __future__ import annotations

import argparse
import logging
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

# La consola de Windows usa cp1252: sin esto, los acentos y el ícono de correo
# de los logs se rompen o lanzan errores de codificación.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import runner  # noqa: E402  (configura logging al importarse)
from core.config_loader import ConfigLoader  # noqa: E402
from demo_panel import _start_panel  # noqa: E402
from outputs.notificador_correo import (  # noqa: E402
    NotificadorCorreo,
    ResultadoEnvio,
    cargar_env,
    credenciales_desde_entorno,
    enmascarar,
)

LOG = logging.getLogger("vigilante.demo_camara_ip")
ROOT = Path(__file__).resolve().parent
DEFAULT_VIDEO = ROOT / "data" / "demo" / "caidas_demo_30s.mp4"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Cámara IP simulada + panel + correo por caída.")
    p.add_argument("--source", default=str(DEFAULT_VIDEO),
                   help="Video que hace de cámara IP (default: montaje de 5 caídas).")
    p.add_argument("--config", default="config_demo_correo.json")
    p.add_argument("--cam", default=None, help="ID de cámara del config (default: la primera).")
    p.add_argument("--metodo", choices=["bbox", "pose"], default="bbox",
                   help="Criterio de caída (default bbox: mayor sensibilidad en el experimento).")
    p.add_argument("--ventana", type=int, default=None)
    p.add_argument("--env", default=".env", help="Archivo con credenciales SMTP.")
    p.add_argument("--para", default="",
                   help="Destinatario(s) extra, separados por coma (se suman a EMAIL_RECIPIENTS).")
    p.add_argument("--sin-envio", action="store_true",
                   help="Modo ensayo: genera los PDF pero no se conecta a SMTP.")
    p.add_argument("--probar-correo", action="store_true",
                   help="Envía un correo de prueba con un evento ficticio y termina.")
    p.add_argument("--esperar", action="store_true",
                   help="Levanta el panel y espera Enter antes de iniciar el video.")
    p.add_argument("--loop", action="store_true",
                   help="Repite el video (el tope de correos por sesión sigue aplicando).")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    return p


def _crear_notificador(args: argparse.Namespace, loader: ConfigLoader) -> NotificadorCorreo:
    env_path = Path(args.env)
    if not env_path.is_absolute():
        env_path = ROOT / env_path
    hay_env = cargar_env(env_path)
    extra = [d.strip() for d in args.para.split(",") if d.strip()]
    cred = credenciales_desde_entorno(extra)

    cfg = loader.get_section("correo", {}) or {}
    demo_cfg = loader.get_section("demo", {}) or {}
    schedule = loader.get_section("schedule", {}) or {}
    notificador = NotificadorCorreo(
        cred,
        report_dir=ROOT / demo_cfg.get("report_dir", "test_outputs/demo_correo/reportes"),
        camaras=cfg.get("camaras"),
        ventana_agrupacion_s=float(cfg.get("ventana_agrupacion_s", 3.0)),
        duracion_minima_s=float(cfg.get("duracion_minima_s", 0.5)),
        max_correos=int(cfg.get("max_correos_por_sesion", 10)),
        simulado=args.sin_envio,
        instalacion=str(cfg.get("instalacion", "Instalación")),
        zona_horaria=str(schedule.get("timezone", "America/Santiago")),
        asunto_prefijo=str(cfg.get("asunto_prefijo", "[Vigía Digital]")),
    )

    print("\n── Correo ─────────────────────────────────────────────")
    if notificador.simulado:
        motivo = "--sin-envio" if args.sin_envio else (
            f"faltan en {env_path.name}: " + ", ".join(cred.faltantes())
            if hay_env else f"no existe {env_path.name} (copiar .env.example)")
        print(f"  Modo: SIMULADO ({motivo})")
    else:
        print(f"  Modo: ENVÍO REAL vía {cred.servidor}:{cred.puerto}")
        print(f"  Remitente: {enmascarar(cred.remitente)}")
    if cred.destinatarios:
        print("  Destinatarios: " + ", ".join(enmascarar(d) for d in cred.destinatarios))
    print(f"  Una caída = un correo · tope {notificador.max_correos} por sesión")
    print("───────────────────────────────────────────────────────\n", flush=True)
    return notificador


def _probar_correo_resultado(notificador: NotificadorCorreo) -> ResultadoEnvio | None:
    """Envía un correo con un evento ficticio y espera el resultado (máx. 60 s)."""
    ahora = datetime.now(timezone.utc).isoformat()
    evento = {
        "event_type": "fall", "event_schema_version": "2.0",
        "timestamp": ahora, "start_time": ahora, "end_time": ahora,
        "duration_seconds": 1.0, "camera_id": "PRUEBA",
        "camera_name": "Correo de prueba (no es una caída real)",
        "ubicacion": "Prueba de configuración", "zone": "Prueba de configuración",
        "sector": "-", "alert_level": 1,
    }
    terminado = threading.Event()
    resultado: list[ResultadoEnvio] = []

    def _fin(r: ResultadoEnvio) -> None:
        resultado.append(r)
        terminado.set()

    notificador.enviar_async(evento, 0, _fin)
    terminado.wait(timeout=60)
    return resultado[0] if resultado else None


def _probar_correo(notificador: NotificadorCorreo) -> int:
    """--probar-correo: un correo de prueba, informe en consola y salida."""
    r = _probar_correo_resultado(notificador)
    notificador.cerrar()
    if r is None:
        print("[ERROR] El envío de prueba no terminó en 60 s.", file=sys.stderr)
        return 1
    print(f"Resultado: {r.texto}")
    return 0 if (r.enviado or r.simulado) else 1


def main() -> None:
    args = _build_parser().parse_args()

    try:
        loader = ConfigLoader(Path(args.config))
    except (FileNotFoundError, ValueError) as exc:
        sys.exit(str(exc))

    notificador = _crear_notificador(args, loader)
    if args.probar_correo:
        sys.exit(_probar_correo(notificador))

    source = Path(args.source)
    if not source.exists() and source.resolve() == DEFAULT_VIDEO.resolve():
        LOG.info("No existe el video de demo: se arma desde data/goldset.")
        from scripts.armar_video_demo import build
        build(DEFAULT_VIDEO)
    if not source.exists():
        sys.exit(f"[ERROR] No existe el video: {source}")

    cameras = {c.id: c for c in loader.get_cameras()}
    if not cameras:
        sys.exit("[ERROR] El config no tiene cámaras habilitadas.")
    cam = cameras.get(args.cam) if args.cam else next(iter(cameras.values()))
    if cam is None:
        sys.exit(f"[ERROR] Cámara no encontrada o deshabilitada: {args.cam}")

    demo_cfg = loader.get_section("demo", {}) or {}
    server, thread, operator_panel = _start_panel(args.host, args.port)
    runner.set_frame_sink(operator_panel.push_frame,
                          max_fps=float(demo_cfg.get("panel_max_fps", 12.0)))
    runner.set_status_sink(operator_panel.push_status)
    operator_panel.register_camera(cam.id, name=cam.name, zone=cam.zone)

    def _al_terminar(event_id: str):
        def _cb(r: ResultadoEnvio) -> None:
            operator_panel.annotate_event(event_id, correo=r.texto)
        return _cb

    def _receptor(event: dict) -> None:
        """Una caída nueva va al panel y al correo; un fragmento se descarta."""
        event.setdefault("camera_name", cam.name)
        event["video_path"] = str(source)   # cuadro limpio de la caída para el correo
        numero = notificador.registrar(event)
        if numero is None:
            return
        event["id"] = uuid.uuid4().hex
        event["correo"] = "Correo en preparación…"
        operator_panel.push_event(event)
        LOG.info("⚠ Caída %d detectada en %s — preparando correo.", numero, cam.name)
        notificador.enviar_async(event, numero, _al_terminar(event["id"]))

    runner.set_event_sink(_receptor)

    try:
        if args.esperar:
            print(f"Panel listo en http://{args.host}:{args.port}/operator/ — "
                  "Enter para conectar la cámara.", flush=True)
            try:
                input()
            except EOFError:
                pass
        runner.run_file(
            loader,
            str(source),
            headless=True,
            cam_id_override=cam.id,
            metodo=args.metodo,
            ventana=args.ventana,
            loop=args.loop,
            show_progress=False,
            # El correo lo maneja el notificador, no TriggerManager.
            dispatch_triggers=False,
        )
        LOG.info("Video terminado. Esperando correos pendientes…")
        notificador.cerrar(esperar=True)
        LOG.info("Listo. El panel sigue activo — Ctrl+C para salir.")
        while thread.is_alive():
            thread.join(timeout=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        notificador.cerrar(esperar=False)
        runner.set_frame_sink(None)
        runner.set_event_sink(None)
        runner.set_status_sink(None)
        server.should_exit = True
        thread.join(timeout=5.0)


if __name__ == "__main__":
    main()
