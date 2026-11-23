"""Notificación por correo para las demos (cámara IP simulada y análisis de clips).

Módulo aislado: se engancha al receptor público de eventos del runner
(runner.set_event_sink) y NO usa TriggerManager ni toca runner.py.

Qué resuelve frente al camino de triggers existente (ver
docs/DEUDA_TECNICA_CORREO.md):
- Agrupa los fragmentos de una misma caída. El detector suele cerrar y
  reabrir el episodio en menos de un segundo; sin agrupar, una caída
  generaba 2-3 correos.
- Exige una duración mínima acumulada antes de avisar: un fragmento suelto
  de 0,2 s (alguien que entra agachado al cuadro) no dispara correo.
- Pone un tope de correos por sesión (protege contra --loop).
- Lee las credenciales del .env aceptando los nombres de .env.example
  (SMTP_USER, SMTP_PASSWORD, EMAIL_RECIPIENTS) y los de EmailSender
  (GMAIL_SENDER_EMAIL, GMAIL_APP_PASSWORD).
- Envía a varios destinatarios un correo HTML con la imagen de la caída
  dentro del mensaje, la hora del análisis, la ubicación y el PDF adjunto.
- Modo simulado: genera PDF e imagen y registra el correo sin conectarse a SMTP.

El envío corre en un hilo propio (un solo trabajador, en orden): nunca
bloquea el hilo que procesa el video.
"""
from __future__ import annotations

import html
import logging
import os
import smtplib
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

LOG = logging.getLogger(__name__)


# ── Credenciales ──────────────────────────────────────────────────────────────

PREFIJOS_CORREO = ("SMTP_", "GMAIL_", "EMAIL_")


def cargar_env(path: Path, prefijos: tuple[str, ...] = PREFIJOS_CORREO) -> bool:
    """Carga las variables de CORREO de un .env simple (CLAVE=valor) en os.environ.

    Solo toma las claves que empiezan con `prefijos`: el notificador no debe
    cambiar la configuración del resto del sistema (p. ej. API_SECRET_KEY de
    ejemplo activaba la autenticación del panel y cortaba el video).
    Si una clave se repite en el archivo, gana la última (como python-dotenv):
    es habitual agregar los datos reales al final sin borrar los de ejemplo.
    No pisa variables ya definidas en el entorno. Sin dependencias externas.
    Retorna True si el archivo existía.
    """
    if not path.is_file():
        return False
    valores: Dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        else:
            # Comentario al final de la línea (solo si va precedido de espacio).
            value = value.split(" #", 1)[0].strip()
        valores[key] = value
    for key, value in valores.items():
        if key.startswith(prefijos):
            os.environ.setdefault(key, value)
    return True


def _es_placeholder(valor: str) -> bool:
    """Valores de ejemplo de .env.example que no son credenciales reales."""
    v = valor.lower()
    return not v or "ejemplo.com" in v or v in {"app_password_gmail", "xxxx xxxx xxxx xxxx"}


def _primera_variable(*nombres: str) -> str:
    """Primer valor real entre los nombres dados (salta vacíos y de ejemplo)."""
    for nombre in nombres:
        valor = os.getenv(nombre, "").strip()
        if valor and not _es_placeholder(valor):
            return valor
    return ""


@dataclass
class CredencialesCorreo:
    remitente: str
    clave_aplicacion: str
    destinatarios: List[str]
    servidor: str = "smtp.gmail.com"
    puerto: int = 587

    @property
    def completas(self) -> bool:
        return bool(
            not _es_placeholder(self.remitente)
            and not _es_placeholder(self.clave_aplicacion)
            and self.destinatarios
        )

    def faltantes(self) -> List[str]:
        out = []
        if _es_placeholder(self.remitente):
            out.append("SMTP_USER (correo remitente)")
        if _es_placeholder(self.clave_aplicacion):
            out.append("SMTP_PASSWORD (contraseña de aplicación de Gmail)")
        if not self.destinatarios:
            out.append("EMAIL_RECIPIENTS (destinatarios, separados por coma)")
        return out


def credenciales_desde_entorno(destinatarios_extra: Optional[List[str]] = None) -> CredencialesCorreo:
    """Arma las credenciales desde el entorno (ya cargado con cargar_env)."""
    destinatarios = [
        d.strip() for d in _primera_variable("EMAIL_RECIPIENTS").split(",")
        if d.strip() and not _es_placeholder(d.strip())
    ]
    for d in destinatarios_extra or []:
        if d and d not in destinatarios:
            destinatarios.append(d)
    puerto_txt = _primera_variable("SMTP_PORT") or "587"
    return CredencialesCorreo(
        remitente=_primera_variable("SMTP_USER", "GMAIL_SENDER_EMAIL"),
        # Google muestra la clave de aplicación con espacios; SMTP la acepta igual.
        clave_aplicacion=_primera_variable("SMTP_PASSWORD", "GMAIL_APP_PASSWORD"),
        destinatarios=destinatarios,
        servidor=_primera_variable("SMTP_HOST") or "smtp.gmail.com",
        puerto=int(puerto_txt) if puerto_txt.isdigit() else 587,
    )


def enmascarar(correo: str) -> str:
    """d***@gmail.com — para logs y pantalla sin exponer direcciones completas."""
    usuario, arroba, dominio = correo.partition("@")
    if not arroba:
        return "***"
    return f"{usuario[:1]}***@{dominio}"


# ── Agrupación de fragmentos ──────────────────────────────────────────────────

@dataclass
class _Grupo:
    ultimo_fin: float
    acumulado: float
    notificado: bool


class AgrupadorCaidas:
    """Decide cuándo un episodio cerrado amerita aviso.

    Usa el tiempo del video (inicio_video_s / fin_video_s del evento), no el
    reloj: el resultado no depende de la velocidad de la CPU.

    - Un episodio que empieza a menos de `ventana_s` del fin del anterior de
      la misma cámara es la misma caída (se suma a su grupo).
    - Si el tiempo retrocede (otro clip o --loop), es un grupo nuevo.
    - El grupo avisa UNA vez, cuando su duración acumulada alcanza
      `duracion_minima_s`.
    """

    def __init__(self, ventana_s: float = 3.0, duracion_minima_s: float = 0.0) -> None:
        self.ventana_s = float(ventana_s)
        self.duracion_minima_s = float(duracion_minima_s)
        self._grupos: Dict[str, _Grupo] = {}
        self._lock = threading.Lock()

    def reiniciar(self, camara: Optional[str] = None) -> None:
        """Olvida los grupos (de una cámara o de todas): p. ej. al empezar otro clip."""
        with self._lock:
            if camara is None:
                self._grupos.clear()
            else:
                self._grupos.pop(camara, None)

    def evaluar(self, event: Dict[str, Any]) -> bool:
        """True si este episodio dispara el aviso de su caída."""
        cam = str(event.get("camera_id", ""))
        inicio = event.get("inicio_video_s")
        if inicio is None:
            return True  # sin tiempo de video no se puede agrupar: no se descarta
        inicio = float(inicio)
        fin = event.get("fin_video_s")
        fin = float(fin) if fin is not None else inicio
        dur = max(0.0, fin - inicio)
        if dur == 0.0 and event.get("duration_seconds") is not None:
            dur = float(event["duration_seconds"])

        with self._lock:
            g = self._grupos.get(cam)
            nuevo = g is None or inicio < g.ultimo_fin - 0.5 or (inicio - g.ultimo_fin) >= self.ventana_s
            if nuevo:
                g = _Grupo(ultimo_fin=fin, acumulado=dur, notificado=False)
                self._grupos[cam] = g
            else:
                g.ultimo_fin = max(g.ultimo_fin, fin)
                g.acumulado += dur
            if not g.notificado and g.acumulado >= self.duracion_minima_s:
                g.notificado = True
                return True
            return False


# ── Notificador ───────────────────────────────────────────────────────────────

@dataclass
class ResultadoEnvio:
    numero: int                 # caída n° en la sesión
    enviado: bool
    simulado: bool
    texto: str                  # resumen para el panel y la consola
    pdf_path: Optional[str] = None
    imagen_path: Optional[str] = None
    destinatarios: List[str] = field(default_factory=list)


class NotificadorCorreo:
    """Recibe caídas agrupadas y envía un correo (imagen + PDF) por cada una."""

    def __init__(
        self,
        credenciales: CredencialesCorreo,
        *,
        report_dir: Path,
        camaras: Optional[List[str]] = None,
        ventana_agrupacion_s: float = 3.0,
        duracion_minima_s: float = 0.5,
        max_correos: int = 10,
        simulado: bool = False,
        instalacion: str = "Instalación",
        zona_horaria: str = "America/Santiago",
        asunto_prefijo: str = "[Vigía Digital]",
    ) -> None:
        self.credenciales = credenciales
        self.report_dir = Path(report_dir)
        self.camaras = set(camaras) if camaras else None
        self.agrupador = AgrupadorCaidas(ventana_agrupacion_s, duracion_minima_s)
        self.max_correos = max(0, int(max_correos))
        # Sin credenciales completas se trabaja en simulado (nunca se intenta SMTP).
        self.simulado = bool(simulado or not credenciales.completas)
        self.instalacion = instalacion
        self.zona_horaria = zona_horaria
        self.asunto_prefijo = asunto_prefijo
        self._contador = 0
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="correo-demo")

    # API usada por los lanzadores ---------------------------------------------

    def reiniciar_sesion(self) -> None:
        """Nueva tanda de análisis: numeración, tope y grupos desde cero."""
        with self._lock:
            self._contador = 0
        self.agrupador.reiniciar()

    def registrar(self, event: Dict[str, Any]) -> Optional[int]:
        """Clasifica el episodio. Retorna el n° de caída si hay que avisar, o None.

        Rápido y sin E/S: se llama desde el hilo que procesa el video. Si avisa,
        anota en el evento la hora del análisis (hora_analisis, ISO local).
        """
        if self.camaras is not None and event.get("camera_id") not in self.camaras:
            return None
        if not self.agrupador.evaluar(event):
            LOG.info("Episodio corto o fragmento de una caída ya avisada (cámara %s): sin correo.",
                     event.get("camera_id"))
            return None
        event.setdefault("hora_analisis", self._ahora_local())
        with self._lock:
            self._contador += 1
            return self._contador

    def enviar_async(
        self,
        event: Dict[str, Any],
        numero: int,
        al_terminar: Optional[Callable[[ResultadoEnvio], None]] = None,
    ) -> None:
        """Encola imagen + PDF + correo. No bloquea."""
        def _job() -> None:
            resultado = self._procesar(dict(event), numero)
            if al_terminar is not None:
                try:
                    al_terminar(resultado)
                except Exception:
                    LOG.exception("Error en el callback de correo")
        try:
            self._executor.submit(_job)
        except RuntimeError:
            LOG.warning("Notificador cerrado: caída %d sin correo.", numero)

    def preparar_imagen(self, event: Dict[str, Any], numero: int) -> Optional[str]:
        """Imagen de la caída para mostrarla fuera del correo (p. ej. en el panel).

        Es la misma imagen del correo, en un archivo propio (sufijo _panel) para
        no pisar el que escribe el envío en paralelo. Bloquea: leer el cuadro
        del video es E/S, no llamar desde el hilo que procesa el video.
        """
        return self._preparar_imagen(event, numero, sufijo="_panel")

    def cerrar(self, esperar: bool = True) -> None:
        self._executor.shutdown(wait=esperar, cancel_futures=not esperar)

    # Internos -----------------------------------------------------------------

    def _procesar(self, event: Dict[str, Any], numero: int) -> ResultadoEnvio:
        event.setdefault("hora_analisis", self._ahora_local())
        if numero > self.max_correos:
            texto = f"Correo omitido: tope de {self.max_correos} por sesión"
            LOG.warning("Caída %d: %s.", numero, texto)
            return ResultadoEnvio(numero, False, self.simulado, texto)

        imagen = self._preparar_imagen(event, numero)
        pdf_path = self._generar_pdf(event)
        destinatarios = list(self.credenciales.destinatarios)
        cuantos = f"{len(destinatarios)} destinatario{'s' if len(destinatarios) != 1 else ''}"

        if self.simulado:
            texto = f"Correo simulado (sin envío) · {cuantos or 'sin destinatarios'}"
            LOG.info("📧 Caída %d: %s · PDF: %s", numero, texto, pdf_path or "—")
            return ResultadoEnvio(numero, False, True, texto, pdf_path, imagen, destinatarios)

        try:
            mensaje = self._armar_mensaje(event, numero, imagen, pdf_path)
            with smtplib.SMTP(self.credenciales.servidor, self.credenciales.puerto, timeout=30) as smtp:
                smtp.starttls()
                smtp.login(self.credenciales.remitente, self.credenciales.clave_aplicacion)
                smtp.send_message(mensaje)
            ok, detalle = True, ""
        except smtplib.SMTPAuthenticationError:
            ok, detalle = False, "Gmail rechazó la clave de aplicación"
        except Exception as exc:  # red, SMTP, archivo
            ok, detalle = False, f"{type(exc).__name__}: {exc}"

        hora = datetime.now().strftime("%H:%M:%S")
        destinos = ", ".join(enmascarar(d) for d in destinatarios)
        if ok:
            texto = f"Correo enviado {hora} · {cuantos}"
            LOG.info("📧 Caída %d: correo enviado a %s", numero, destinos)
        else:
            texto = f"Correo NO enviado: {detalle}"
            LOG.error("Caída %d: falló el envío a %s — %s", numero, destinos, detalle)
        return ResultadoEnvio(numero, ok, False, texto, pdf_path, imagen, destinatarios)

    def _preparar_imagen(self, event: Dict[str, Any], numero: int,
                         sufijo: str = "") -> Optional[str]:
        """Imagen del correo (960 px de ancho): el cuadro de la caída, marcado.

        Si el evento trae el video (video_path) y el cuadro (end_frame), se toma
        el cuadro LIMPIO del momento en que se confirmó la caída, se enmarca a la
        persona (metadata.bbox) y se agrega una franja con hora y ubicación. La
        foto del runner no sirve tal cual: se toma al cerrar el episodio y su HUD
        puede decir "Sin caída" con la persona en el suelo (DEUDA D8).
        Sin video, se usa esa foto como respaldo.
        """
        try:
            import cv2
            img = self._cuadro_del_video(event)
            marcada = img is not None
            if img is None:
                photo = event.get("photo_path") or event.get("photo_start")
                if not photo or not Path(str(photo)).exists():
                    return None
                img = cv2.imread(str(photo))
                if img is None:
                    return None
            if marcada:
                img = self._marcar(img, event)
            h, w = img.shape[:2]
            if w > 960:
                img = cv2.resize(img, (960, int(h * 960 / w)), interpolation=cv2.INTER_AREA)
            if marcada:
                img = self._franja(img, event)
            self.report_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out = self.report_dir / f"caida_{numero:02d}_{stamp}{sufijo}.jpg"
            cv2.imwrite(str(out), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
            return str(out)
        except Exception:
            LOG.exception("No se pudo preparar la imagen de la caída")
            return None

    @staticmethod
    def _cuadro_del_video(event: Dict[str, Any]):
        import cv2
        video, idx = event.get("video_path"), event.get("end_frame")
        if not video or idx is None or not Path(str(video)).exists():
            return None
        cap = cv2.VideoCapture(str(video))
        try:
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            idx = max(0, int(idx) - 1)
            if total:
                idx = min(idx, total - 1)
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            return frame if ok else None
        finally:
            cap.release()

    @staticmethod
    def _marcar(img, event: Dict[str, Any]):
        import cv2
        bbox = (event.get("metadata") or {}).get("bbox") or {}
        try:
            x1, y1, x2, y2 = (int(bbox[k]) for k in ("xmin", "ymin", "xmax", "ymax"))
        except (KeyError, TypeError, ValueError):
            return img
        h, w = img.shape[:2]
        pad = int(0.04 * max(w, h))
        x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
        x2, y2 = min(w - 1, x2 + pad), min(h - 1, y2 + pad)
        grosor = max(3, w // 320)
        cv2.rectangle(img, (x1, y1), (x2, y2), (24, 35, 180), grosor + 2)   # borde oscuro
        cv2.rectangle(img, (x1, y1), (x2, y2), (60, 70, 238), grosor)      # rojo alerta
        return img

    def _franja(self, img, event: Dict[str, Any]):
        """Franja superior: «CAÍDA DETECTADA · hora» y la ubicación (con acentos, vía Pillow)."""
        import numpy as np
        h, w = img.shape[:2]
        alto = max(56, h // 9)
        titulo = f"CAÍDA DETECTADA · {self._hora_local(event)}"
        lugar = str(event.get("ubicacion") or event.get("zone") or "")
        try:
            from PIL import Image, ImageDraw, ImageFont
            lienzo = Image.fromarray(img[:, :, ::-1].copy())
            draw = ImageDraw.Draw(lienzo, "RGBA")
            draw.rectangle([0, 0, w, alto], fill=(180, 35, 24, 235))

            def _fuente(nombres, tam):
                for n in nombres:
                    try:
                        return ImageFont.truetype(n, tam)
                    except OSError:
                        continue
                return ImageFont.load_default()

            f1 = _fuente(["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], int(alto * 0.36))
            f2 = _fuente(["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"], int(alto * 0.27))
            draw.text((14, int(alto * 0.08)), titulo, font=f1, fill=(255, 255, 255))
            draw.text((14, int(alto * 0.56)), lugar, font=f2, fill=(255, 235, 230))
            return np.asarray(lienzo)[:, :, ::-1].copy()
        except Exception:
            import cv2
            img[:alto] = (img[:alto] * 0.2 + np.array([24, 35, 180]) * 0.8).astype(img.dtype)
            cv2.putText(img, "CAIDA DETECTADA " + self._hora_local(event), (14, int(alto * 0.45)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
            return img

    def _generar_pdf(self, event: Dict[str, Any]) -> Optional[str]:
        try:
            import cv2
            from outputs.report_generator import ReportGenerator

            photo = event.get("photo_path") or event.get("photo_start")
            frame = cv2.imread(str(photo)) if photo and Path(str(photo)).exists() else None
            generator = ReportGenerator(
                camera_name=str(event.get("camera_name") or event.get("camera_id", "CAM")),
                sector=str(event.get("ubicacion") or event.get("zone") or event.get("sector") or ""),
                facility=self.instalacion,
            )
            # ReportGenerator imprime la hora tal como viene: se le entrega la
            # hora del análisis, ya en la zona horaria local del config.
            event_local = dict(event)
            hora = event.get("hora_analisis")
            if hora:
                event_local["start_time"] = hora
            else:
                for key in ("start_time", "end_time", "timestamp"):
                    if event_local.get(key):
                        event_local[key] = self._a_local(event_local[key]) or event_local[key]
            result = generator.generate_report(
                event=event_local, frame_image=frame, output_dir=str(self.report_dir),
            )
            return result if isinstance(result, str) and result else None
        except Exception:
            LOG.exception("Error generando el PDF de la caída")
            return None

    # Contenido del correo -----------------------------------------------------

    def _ahora_local(self) -> str:
        try:
            from zoneinfo import ZoneInfo
            return datetime.now(ZoneInfo(self.zona_horaria)).isoformat()
        except Exception:
            return datetime.now().astimezone().isoformat()

    def _a_local(self, valor: Any) -> Optional[str]:
        """ISO 8601 en la zona horaria local del config (None si no se puede leer)."""
        try:
            dt = datetime.fromisoformat(str(valor))
        except (TypeError, ValueError):
            return None
        try:
            from zoneinfo import ZoneInfo
            dt = dt.astimezone(ZoneInfo(self.zona_horaria))
        except Exception:
            dt = dt.astimezone()
        return dt.isoformat()

    def _hora_local(self, event: Dict[str, Any]) -> str:
        local = event.get("hora_analisis") or self._a_local(
            event.get("start_time") or event.get("timestamp"))
        if local is None:
            return datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        return datetime.fromisoformat(local).strftime("%d-%m-%Y %H:%M:%S")

    def _datos(self, event: Dict[str, Any], numero: int) -> List[tuple[str, str]]:
        filas = [
            ("Ubicación", str(event.get("ubicacion") or event.get("zone") or "-")),
            ("Cámara", str(event.get("camera_name") or event.get("camera_id") or "-")),
            ("Fecha y hora", self._hora_local(event)),
            ("Instalación", self.instalacion),
        ]
        if event.get("clip"):
            filas.append(("Clip analizado", str(event["clip"])))
        if numero > 0:  # 0 = correo de prueba
            filas.append(("Caída n°", f"{numero} de esta sesión"))
        return filas

    def _asunto(self, event: Dict[str, Any], numero: int) -> str:
        lugar = event.get("ubicacion") or event.get("camera_name") or event.get("zone") or ""
        return f"{self.asunto_prefijo} Caída detectada · {lugar} · {self._hora_local(event)[-8:-3]}"

    def _cuerpo(self, event: Dict[str, Any], numero: int) -> str:
        filas = "\n".join(f"{k + ':':<16}{v}" for k, v in self._datos(event, numero))
        return (
            "ALERTA: se detectó una posible caída.\n\n"
            f"{filas}\n\n"
            "Se adjunta la imagen del momento de la detección y el reporte PDF.\n"
            "Verifique el estado de la persona y confirme la atención en el panel de operador.\n\n"
            "— Vigía Digital · aviso automático, no responder."
        )

    def _cuerpo_html(self, event: Dict[str, Any], numero: int, cid_imagen: Optional[str]) -> str:
        e = html.escape
        filas = "".join(
            f'<tr><td style="padding:6px 12px 6px 0;color:#5b6470;white-space:nowrap">{e(k)}</td>'
            f'<td style="padding:6px 0;color:#111;font-weight:600">{e(v)}</td></tr>'
            for k, v in self._datos(event, numero)
        )
        imagen = (
            f'<img src="cid:{cid_imagen[1:-1]}" alt="Cuadro de la caída detectada" '
            'style="display:block;width:100%;max-width:640px;border-radius:6px;border:1px solid #d9dde3">'
            if cid_imagen else
            '<p style="color:#5b6470">(Sin imagen del momento de la detección.)</p>'
        )
        return f"""<!doctype html>
<html lang="es"><body style="margin:0;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif">
<div style="max-width:680px;margin:0 auto;padding:16px">
  <div style="background:#b42318;color:#fff;padding:14px 18px;border-radius:8px 8px 0 0">
    <div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;opacity:.85">Vigía Digital · alerta automática</div>
    <div style="font-size:22px;font-weight:700;margin-top:2px">Caída detectada</div>
  </div>
  <div style="background:#fff;padding:18px;border-radius:0 0 8px 8px;border:1px solid #e5e7eb;border-top:0">
    <table style="border-collapse:collapse;font-size:15px;margin-bottom:16px">{filas}</table>
    {imagen}
    <p style="font-size:14px;color:#111;margin:16px 0 4px">Verifique el estado de la persona y confirme
    la atención en el panel de operador. Se adjunta el reporte PDF.</p>
    <p style="font-size:12px;color:#8a919c;margin:14px 0 0">Aviso automático de un prototipo académico
    (INACAP 2026). No responder este correo.</p>
  </div>
</div></body></html>"""

    def _armar_mensaje(self, event: Dict[str, Any], numero: int,
                       imagen: Optional[str], pdf_path: Optional[str]) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = f"Vigía Digital <{self.credenciales.remitente}>"
        msg["To"] = ", ".join(self.credenciales.destinatarios)
        msg["Subject"] = self._asunto(event, numero)
        msg.set_content(self._cuerpo(event, numero))
        cid = make_msgid(domain="vigia.local") if imagen else None
        msg.add_alternative(self._cuerpo_html(event, numero, cid), subtype="html")
        if imagen and cid:
            # La imagen va relacionada a la parte HTML (se ve dentro del mensaje)…
            data = Path(imagen).read_bytes()
            msg.get_payload()[1].add_related(data, maintype="image", subtype="jpeg", cid=cid,
                                             filename=Path(imagen).name)
        if pdf_path and Path(pdf_path).exists():
            msg.add_attachment(Path(pdf_path).read_bytes(), maintype="application",
                               subtype="pdf", filename=Path(pdf_path).name)
        return msg
