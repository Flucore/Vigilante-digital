"""Evaluación comparativa de detección de caídas (eval/ESPECIFICACIONES.md).

Uso:
    python -m eval.evaluar --clips data/goldset --labels data/labels.csv --salida eval/resultados

Corre bbox y un brazo pose por ventana (default: pose_v1, pose_v8) sobre los
mismos clips etiquetados, y escribe detalle.csv y resumen.csv en --salida.
Cada clip es una unidad de evaluación: hay alarma si el brazo emitió al menos
un evento de caída.

Barrido de ventanas:
    python -m eval.evaluar ... --ventanas 1,2,3,4,5,6,8,10
"""
from __future__ import annotations

import argparse
import csv
import logging
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FPS_POR_DEFECTO = 30.0  # mismo valor que usa runner.run_file si el video no reporta fps
EXTENSIONES_VIDEO = {".mp4", ".avi", ".mov", ".mkv", ".m4v"}
CONFIG_POR_DEFECTO = "eval/config_eval.json"
COLUMNAS_ETIQUETAS = ["archivo", "etiqueta", "inicio_caida_s", "escenario", "locacion"]
ETIQUETAS_VALIDAS = {"caida", "no_caida"}


@dataclass(frozen=True)
class Brazo:
    nombre: str
    metodo: str
    ventana: Optional[int]  # None = no aplica (bbox)


VENTANAS_POR_DEFECTO: Tuple[int, ...] = (1, 8)


def construir_brazos(ventanas: Sequence[int]) -> Tuple[Brazo, ...]:
    """bbox una sola vez + un brazo pose por ventana (en orden ascendente)."""
    return (Brazo("bbox", "bbox", None),) + tuple(
        Brazo(f"pose_v{v}", "pose", v) for v in sorted(ventanas)
    )


# Brazos de la evaluación estándar (sección 2 de ESPECIFICACIONES.md).
BRAZOS: Tuple[Brazo, ...] = construir_brazos(VENTANAS_POR_DEFECTO)


def parsear_ventanas(texto: str) -> Tuple[int, ...]:
    """'1,2,8' → (1, 2, 8). Exige enteros >= 1 y sin repetidos."""
    partes = [p.strip() for p in texto.split(",")]
    if not texto.strip() or any(not p for p in partes):
        raise argparse.ArgumentTypeError(f"lista de ventanas vacía o mal formada: '{texto}'")
    ventanas: List[int] = []
    for p in partes:
        try:
            v = int(p)
        except ValueError:
            raise argparse.ArgumentTypeError(f"ventana '{p}' no es un entero") from None
        if v < 1:
            raise argparse.ArgumentTypeError(f"ventana {v} inválida: debe ser >= 1")
        if v in ventanas:
            raise argparse.ArgumentTypeError(f"ventana {v} repetida")
        ventanas.append(v)
    return tuple(sorted(ventanas))


@dataclass(frozen=True)
class Etiqueta:
    archivo: str
    etiqueta: str
    inicio_caida_s: Optional[float]
    escenario: str
    locacion: str


@dataclass
class ResultadoClip:
    brazo: Brazo
    etiqueta: Etiqueta
    alarma: bool
    segundo_alarma: Optional[float]
    duracion_s: float

    @property
    def resultado(self) -> str:
        if self.etiqueta.etiqueta == "caida":
            return "VP" if self.alarma else "FN"
        return "FP" if self.alarma else "VN"


class ErrorEvaluacion(Exception):
    """Error que impide correr la evaluación (se aborta la corrida completa)."""


class ErrorClip(Exception):
    """Error al procesar un clip (se reporta y se sigue con los demás)."""


# ══════════════════════════════════════════════════════════════════════════════
# 3. Etiquetas y carpeta de clips
# ══════════════════════════════════════════════════════════════════════════════

def cargar_etiquetas(path: Path) -> List[Etiqueta]:
    """Lee labels.csv (UTF-8) y valida su contenido. Lanza ErrorEvaluacion."""
    if not path.is_file():
        raise ErrorEvaluacion(f"No existe el archivo de etiquetas: {path}")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            lector = csv.DictReader(fh)
            columnas = [c.strip() for c in (lector.fieldnames or [])]
            filas = list(lector)
    except UnicodeDecodeError as exc:
        raise ErrorEvaluacion(f"{path} no está en UTF-8: {exc}") from exc

    if not columnas:
        raise ErrorEvaluacion(
            f"{path} está vacío. Primera línea esperada: {','.join(COLUMNAS_ETIQUETAS)}"
        )
    faltan = [c for c in COLUMNAS_ETIQUETAS if c not in columnas]
    if faltan:
        raise ErrorEvaluacion(
            f"{path}: faltan columnas {', '.join(faltan)}. "
            f"Se esperaba: {','.join(COLUMNAS_ETIQUETAS)}"
        )

    errores: List[str] = []
    etiquetas: List[Etiqueta] = []
    vistos: set = set()
    for n, fila in enumerate(filas, start=2):  # línea 1 = encabezado
        fila = {(k or "").strip(): (v or "").strip() for k, v in fila.items()}
        archivo = fila["archivo"]
        etiqueta = fila["etiqueta"]
        inicio_txt = fila["inicio_caida_s"]
        if not archivo:
            errores.append(f"línea {n}: 'archivo' vacío")
            continue
        if Path(archivo).name != archivo:
            errores.append(f"línea {n}: '{archivo}' debe ser solo el nombre del clip, sin carpetas")
        if archivo in vistos:
            errores.append(f"línea {n}: '{archivo}' aparece más de una vez")
        vistos.add(archivo)
        if etiqueta not in ETIQUETAS_VALIDAS:
            errores.append(f"línea {n}: etiqueta '{etiqueta}' inválida (válidas: caida, no_caida)")
        inicio: Optional[float] = None
        if inicio_txt:
            if etiqueta == "no_caida":
                errores.append(f"línea {n}: '{archivo}' es no_caida pero tiene inicio_caida_s")
            try:
                inicio = float(inicio_txt.replace(",", "."))
                if inicio < 0:
                    errores.append(f"línea {n}: inicio_caida_s negativo ({inicio_txt})")
            except ValueError:
                errores.append(f"línea {n}: inicio_caida_s no es un número ('{inicio_txt}')")
        etiquetas.append(Etiqueta(archivo, etiqueta, inicio, fila["escenario"], fila["locacion"]))

    if errores:
        raise ErrorEvaluacion(f"Errores en {path}:\n  " + "\n  ".join(errores))
    if not etiquetas:
        raise ErrorEvaluacion(f"{path} no tiene filas de etiquetas.")
    return sorted(etiquetas, key=lambda e: e.archivo)


def validar_carpeta(clips_dir: Path, etiquetas: Sequence[Etiqueta]) -> None:
    """Exige correspondencia exacta entre los clips de la carpeta y labels.csv."""
    if not clips_dir.is_dir():
        raise ErrorEvaluacion(f"No existe la carpeta de clips: {clips_dir}")
    en_carpeta = {
        p.name for p in clips_dir.iterdir()
        if p.is_file() and p.suffix.lower() in EXTENSIONES_VIDEO
    }
    listados = {e.archivo for e in etiquetas}
    faltan = sorted(listados - en_carpeta)
    sin_etiqueta = sorted(en_carpeta - listados)
    mensajes: List[str] = []
    if faltan:
        mensajes.append(
            f"Listados en las etiquetas pero no existen en {clips_dir}:\n    " + "\n    ".join(faltan)
        )
    if sin_etiqueta:
        mensajes.append(
            f"Clips en {clips_dir} que no están en las etiquetas:\n    " + "\n    ".join(sin_etiqueta)
        )
    if mensajes:
        raise ErrorEvaluacion("\n  ".join(mensajes))


# ══════════════════════════════════════════════════════════════════════════════
# Configuración, módulo y detector
# ══════════════════════════════════════════════════════════════════════════════

def verificar_modulo(loader, config_path: Path, cam_id: Optional[str]) -> str:
    """Retorna el id de la cámara a usar; aborta si su módulo no es fall_detection."""
    camaras = loader.get_cameras()
    if not camaras:
        raise ErrorEvaluacion(f"{config_path} no tiene cámaras habilitadas.")
    cam = camaras[0]
    if cam_id:
        cam = next((c for c in camaras if c.id == cam_id), None)
        if cam is None:
            raise ErrorEvaluacion(
                f"La cámara '{cam_id}' no existe o no está habilitada en {config_path}."
            )
    modulo = cam.modules_active[0] if cam.modules_active else "fall_detection"
    if modulo != "fall_detection":
        raise ErrorEvaluacion(
            f"Módulo activo '{modulo}' en cámara {cam.id} de {config_path}; "
            f"la evaluación exige fall_detection."
        )
    return cam.id


def verificar_detector(loader) -> str:
    """Comprueba que el detector sea YOLOv8-pose (no el fallback MediaPipe)."""
    from core.detector_factory import get_detector

    det_cfg = loader.get_section("detection", {})
    try:
        detector = get_detector(
            use_gpu=det_cfg.get("use_gpu", True),
            min_fall_frames=8,
            fall_angle_deg=det_cfg.get("fall_angle_threshold_deg", 55.0),
        )
    except Exception as exc:
        raise ErrorEvaluacion(f"No se pudo crear el detector de pose: {exc}") from exc
    nombre = type(detector).__name__
    dispositivo = str(getattr(detector, "device", "?"))
    try:
        detector.close()
    except Exception:
        pass
    if nombre != "YoloFallDetector":
        raise ErrorEvaluacion(
            f"El detector disponible es {nombre}, no YoloFallDetector (YOLOv8-pose). "
            f"Revisa que ultralytics esté instalado (requirements-academico.txt)."
        )
    return dispositivo


# ══════════════════════════════════════════════════════════════════════════════
# 4. Procesamiento de un clip
# ══════════════════════════════════════════════════════════════════════════════

def duracion_video_s(path: Path) -> float:
    """Duración en segundos de video: frames contados / fps (30 si no se reporta)."""
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise ErrorClip(f"OpenCV no puede abrir el video: {path.name}")
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps <= 0:
            fps = FPS_POR_DEFECTO
        n = 0
        while cap.grab():
            n += 1
    finally:
        cap.release()
    if n == 0:
        raise ErrorClip(f"El video no tiene frames legibles: {path.name}")
    return n / fps


class _CapturaFallos(logging.Handler):
    """Junta los logs que indican que run_file procesó mal un clip sin lanzar excepción."""

    _AVISOS = ("Detector no disponible", "YoloFallDetector no disponible")

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.fallos: List[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        if record.levelno >= logging.ERROR or any(a in msg for a in self._AVISOS):
            self.fallos.append(f"{record.name}: {msg.splitlines()[0]}")


EjecutarBrazo = Callable[[Path, Brazo], List[Dict]]


def ejecutor_runner(loader, cam_id: str) -> EjecutarBrazo:
    """Procesa un clip con runner.run_file, sin triggers ni snapshots."""
    import runner

    def _ejecutar(clip: Path, brazo: Brazo) -> List[Dict]:
        return runner.run_file(
            loader,
            str(clip),
            headless=True,
            cam_id_override=cam_id,
            dispatch_triggers=False,
            save_snapshots=False,
            metodo=brazo.metodo,
            ventana=brazo.ventana,
            modulo="fall_detection",
        )

    return _ejecutar


def procesar_clip(
    clip: Path,
    brazo: Brazo,
    ejecutar: EjecutarBrazo,
) -> Tuple[bool, Optional[float], List[str]]:
    """Retorna (alarma, segundo de la primera alarma, avisos). Lanza ErrorClip."""
    captura = _CapturaFallos()
    raiz = logging.getLogger()
    raiz.addHandler(captura)
    try:
        eventos = ejecutar(clip, brazo)
    except Exception as exc:
        raise ErrorClip(f"{type(exc).__name__}: {exc}") from exc
    finally:
        raiz.removeHandler(captura)
    if captura.fallos:
        raise ErrorClip("; ".join(captura.fallos[:3]))

    avisos: List[str] = []
    inicios: List[float] = []
    for ev in eventos or []:
        tipo = ev.get("event_type")
        if tipo != "fall":
            avisos.append(f"evento descartado de tipo '{tipo}' (no es fall)")
            continue
        meta = ev.get("metadata") or {}
        if meta.get("metodo") not in (None, brazo.metodo):
            raise ErrorClip(f"evento con metodo '{meta.get('metodo')}', se esperaba '{brazo.metodo}'")
        if brazo.ventana is not None and meta.get("ventana") not in (None, brazo.ventana):
            raise ErrorClip(f"evento con ventana {meta.get('ventana')}, se esperaba {brazo.ventana}")
        inicio = ev.get("inicio_video_s")
        if inicio is None:
            raise ErrorClip("evento de caída sin inicio_video_s (tiempo de video)")
        inicios.append(float(inicio))
    if not inicios:
        return False, None, avisos
    return True, min(inicios), avisos


# ══════════════════════════════════════════════════════════════════════════════
# 5. Métricas
# ══════════════════════════════════════════════════════════════════════════════

def _razon(num: float, den: float) -> Optional[float]:
    return num / den if den else None


def calcular_metricas(resultados: Sequence[ResultadoClip]) -> Dict[str, Optional[float]]:
    """Métricas de un brazo según ESPECIFICACIONES.md §5 (valores sin redondear)."""
    cuenta = {k: 0 for k in ("VP", "FN", "FP", "VN")}
    for r in resultados:
        cuenta[r.resultado] += 1
    vp, fn, fp, vn = cuenta["VP"], cuenta["FN"], cuenta["FP"], cuenta["VN"]

    no_caida = [r for r in resultados if r.etiqueta.etiqueta == "no_caida"]
    alarmas_no_caida = sum(1 for r in no_caida if r.alarma)
    horas_no_caida = sum(r.duracion_s for r in no_caida) / 3600.0

    latencias = [
        r.segundo_alarma - r.etiqueta.inicio_caida_s
        for r in resultados
        if r.etiqueta.etiqueta == "caida"
        and r.alarma
        and r.etiqueta.inicio_caida_s is not None
        and r.segundo_alarma is not None
    ]
    return {
        "clips": len(resultados),
        "VP": vp, "FN": fn, "FP": fp, "VN": vn,
        "sensibilidad": _razon(vp, vp + fn),
        "especificidad": _razon(vn, vn + fp),
        "tasa_falsos_positivos": _razon(fp, vn + fp),
        "falsas_alarmas_camara_hora": _razon(alarmas_no_caida, horas_no_caida),
        "denominador_min": horas_no_caida * 60.0,
        "latencia_mediana_s": statistics.median(latencias) if latencias else None,
        "n_latencia": len(latencias),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 6. Salidas
# ══════════════════════════════════════════════════════════════════════════════

def _num(valor: Optional[float], decimales: int, coma: bool = False) -> str:
    if valor is None:
        return "" if not coma else "n/d"
    txt = f"{valor:.{decimales}f}"
    return txt.replace(".", ",") if coma else txt


COLUMNAS_DETALLE = [
    "brazo", "metodo", "ventana", "archivo", "etiqueta", "escenario",
    "alarma", "segundo_alarma", "duracion_s", "resultado",
]
COLUMNAS_RESUMEN = [
    "brazo", "metodo", "ventana", "clips", "VP", "FN", "FP", "VN",
    "sensibilidad", "especificidad", "tasa_falsos_positivos",
    "falsas_alarmas_camara_hora", "denominador_min",
    "latencia_mediana_s", "n_latencia", "clips_con_error",
]


def escribir_detalle(path: Path, resultados: Sequence[ResultadoClip]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(COLUMNAS_DETALLE)
        for r in resultados:
            w.writerow([
                r.brazo.nombre,
                r.brazo.metodo,
                "" if r.brazo.ventana is None else r.brazo.ventana,
                r.etiqueta.archivo,
                r.etiqueta.etiqueta,
                r.etiqueta.escenario,
                1 if r.alarma else 0,
                _num(r.segundo_alarma, 3),
                _num(r.duracion_s, 3),
                r.resultado,
            ])


def escribir_resumen(
    path: Path,
    metricas: Dict[str, Dict[str, Optional[float]]],
    errores_por_brazo: Dict[str, int],
    brazos: Sequence[Brazo] = BRAZOS,
) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(COLUMNAS_RESUMEN)
        for brazo in brazos:
            m = metricas[brazo.nombre]
            w.writerow([
                brazo.nombre,
                brazo.metodo,
                "" if brazo.ventana is None else brazo.ventana,
                m["clips"], m["VP"], m["FN"], m["FP"], m["VN"],
                _num(m["sensibilidad"], 2),
                _num(m["especificidad"], 2),
                _num(m["tasa_falsos_positivos"], 2),
                _num(m["falsas_alarmas_camara_hora"], 2),
                _num(m["denominador_min"], 1),
                _num(m["latencia_mediana_s"], 1),
                m["n_latencia"],
                errores_por_brazo.get(brazo.nombre, 0),
            ])


def _alinear(filas: List[List[str]]) -> str:
    anchos = [max(len(f[i]) for f in filas) for i in range(len(filas[0]))]
    lineas = []
    for i, f in enumerate(filas):
        celdas = [f[0].ljust(anchos[0])] + [c.rjust(anchos[j]) for j, c in enumerate(f) if j > 0]
        lineas.append(" | ".join(celdas))
        if i == 0:
            lineas.append("-+-".join("-" * a for a in anchos))
    return "\n".join(lineas)


def tabla_barrido(
    metricas: Dict[str, Dict[str, Optional[float]]],
    errores_por_brazo: Dict[str, int],
    brazos: Sequence[Brazo],
) -> str:
    """Barrido: una fila por brazo (con muchas ventanas no caben lado a lado)."""
    filas = [["Brazo", "Ventana", "VP/FN", "FP/VN", "Sens.", "Espec.", "TFP",
              "FA/cám-h", "Lat. med. (s)", "Errores"]]
    for b in brazos:
        m = metricas[b.nombre]
        filas.append([
            b.nombre,
            "-" if b.ventana is None else str(b.ventana),
            f"{m['VP']}/{m['FN']}",
            f"{m['FP']}/{m['VN']}",
            _num(m["sensibilidad"], 2, coma=True),
            _num(m["especificidad"], 2, coma=True),
            _num(m["tasa_falsos_positivos"], 2, coma=True),
            _num(m["falsas_alarmas_camara_hora"], 2, coma=True),
            f"{_num(m['latencia_mediana_s'], 1, coma=True)} (n={m['n_latencia']})",
            str(errores_por_brazo.get(b.nombre, 0)),
        ])
    denominadores = sorted({_num(metricas[b.nombre]["denominador_min"], 1, coma=True) for b in brazos})
    return (
        _alinear(filas)
        + "\nFA/cám-h = falsas alarmas por cámara-hora "
        + f"(denominador: {' / '.join(denominadores)} min)"
    )


def tabla_comparativa(
    metricas: Dict[str, Dict[str, Optional[float]]],
    errores_por_brazo: Dict[str, int],
    brazos: Sequence[Brazo] = BRAZOS,
) -> str:
    """Tabla legible de los brazos lado a lado (barrido: una fila por brazo)."""
    if len(brazos) > 3:
        return tabla_barrido(metricas, errores_por_brazo, brazos)

    def fila(nombre: str, fn: Callable[[Dict[str, Optional[float]]], str]) -> List[str]:
        return [nombre] + [fn(metricas[b.nombre]) for b in brazos]

    filas = [
        ["", *(b.nombre for b in brazos)],
        fila("Clips evaluados", lambda m: str(m["clips"])),
        fila("VP / FN", lambda m: f"{m['VP']} / {m['FN']}"),
        fila("FP / VN", lambda m: f"{m['FP']} / {m['VN']}"),
        fila("Sensibilidad", lambda m: _num(m["sensibilidad"], 2, coma=True)),
        fila("Especificidad", lambda m: _num(m["especificidad"], 2, coma=True)),
        fila("Tasa falsos positivos", lambda m: _num(m["tasa_falsos_positivos"], 2, coma=True)),
        fila(
            "Falsas alarmas / cám-hora",
            lambda m: f"{_num(m['falsas_alarmas_camara_hora'], 2, coma=True)} "
                      f"(denominador: {_num(m['denominador_min'], 1, coma=True)} min)",
        ),
        fila(
            "Latencia mediana (s)",
            lambda m: f"{_num(m['latencia_mediana_s'], 1, coma=True)} (n={m['n_latencia']})",
        ),
        ["Clips con error", *(str(errores_por_brazo.get(b.nombre, 0)) for b in brazos)],
    ]
    return _alinear(filas)


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m eval.evaluar",
        description="Evaluación comparativa bbox / pose_v1 / pose_v8 (eval/ESPECIFICACIONES.md)",
    )
    p.add_argument("--clips", required=True, help="Carpeta con los clips (p. ej. data/goldset)")
    p.add_argument("--labels", required=True, help="CSV de etiquetas (p. ej. data/labels.csv)")
    p.add_argument("--salida", required=True, help="Carpeta de resultados (p. ej. eval/resultados)")
    p.add_argument("--config", default=CONFIG_POR_DEFECTO,
                   help=f"Config del runner (default: {CONFIG_POR_DEFECTO})")
    p.add_argument("--cam", default=None, help="Cámara del config (default: primera habilitada)")
    p.add_argument(
        "--ventanas",
        type=parsear_ventanas,
        default=VENTANAS_POR_DEFECTO,
        metavar="N1,N2,...",
        help="Barrido: corre el brazo pose con cada ventana (p. ej. 1,2,3,4,5,6,8,10) "
             "y bbox una sola vez (default: 1,8 → bbox, pose_v1, pose_v8)",
    )
    return p


def _silenciar_logs() -> None:
    """El runner loggea cada clip en INFO; aquí solo interesan advertencias y errores."""
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("outputs.email_sender").setLevel(logging.ERROR)


def main(argv: Optional[Sequence[str]] = None, ejecutar: Optional[EjecutarBrazo] = None) -> int:
    """Corre la evaluación. Retorna 0 si todo OK, 1 si hubo clips con error, 2 si se abortó.

    `ejecutar` permite reemplazar el procesamiento real (tests); si se entrega,
    no se verifica el detector.
    """
    args = _parser().parse_args(argv)
    clips_dir, labels_path, salida = Path(args.clips), Path(args.labels), Path(args.salida)
    config_path = Path(args.config)
    brazos = construir_brazos(args.ventanas)

    try:
        etiquetas = cargar_etiquetas(labels_path)
        validar_carpeta(clips_dir, etiquetas)

        import runner  # noqa: F401  — su basicConfig(INFO) debe correr antes de _silenciar_logs
        from core.config_loader import ConfigLoader
        try:
            loader = ConfigLoader(config_path)
        except (FileNotFoundError, ValueError) as exc:
            raise ErrorEvaluacion(str(exc).strip()) from exc
        _silenciar_logs()
        cam_id = verificar_modulo(loader, config_path, args.cam)

        if ejecutar is None:
            dispositivo = verificar_detector(loader)
            print(f"Detector: YOLOv8-pose ({dispositivo}) | cámara {cam_id} | config {config_path.as_posix()}")
            ejecutar = ejecutor_runner(loader, cam_id)
    except ErrorEvaluacion as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    print(f"{len(etiquetas)} clips x {len(brazos)} brazos\n")
    resultados: Dict[str, List[ResultadoClip]] = {b.nombre: [] for b in brazos}
    errores: List[str] = []
    errores_por_brazo: Dict[str, int] = {}

    for i, et in enumerate(etiquetas, start=1):
        clip = clips_dir / et.archivo
        try:
            duracion = duracion_video_s(clip)
        except ErrorClip as exc:
            errores.append(f"{et.archivo} [todos los brazos]: {exc}")
            for b in brazos:
                errores_por_brazo[b.nombre] = errores_por_brazo.get(b.nombre, 0) + 1
            print(f"[{i}/{len(etiquetas)}] {et.archivo}: ERROR — {exc}")
            continue

        estado: List[str] = []
        for brazo in brazos:
            try:
                alarma, segundo, avisos = procesar_clip(clip, brazo, ejecutar)
            except ErrorClip as exc:
                errores.append(f"{et.archivo} [{brazo.nombre}]: {exc}")
                errores_por_brazo[brazo.nombre] = errores_por_brazo.get(brazo.nombre, 0) + 1
                estado.append(f"{brazo.nombre}=ERROR")
                continue
            for aviso in avisos:
                errores.append(f"{et.archivo} [{brazo.nombre}]: {aviso}")
            r = ResultadoClip(brazo, et, alarma, segundo, duracion)
            resultados[brazo.nombre].append(r)
            estado.append(f"{brazo.nombre}={r.resultado}")
        print(f"[{i}/{len(etiquetas)}] {et.archivo} ({et.etiqueta}): {' '.join(estado)}")

    metricas = {b.nombre: calcular_metricas(resultados[b.nombre]) for b in brazos}

    salida.mkdir(parents=True, exist_ok=True)
    escribir_detalle(salida / "detalle.csv", [r for b in brazos for r in resultados[b.nombre]])
    escribir_resumen(salida / "resumen.csv", metricas, errores_por_brazo, brazos)

    print()
    print(tabla_comparativa(metricas, errores_por_brazo, brazos))
    print(f"\nResultados en {(salida / 'detalle.csv').as_posix()} y {(salida / 'resumen.csv').as_posix()}")

    if errores:
        print(f"\n{len(errores)} problema(s) durante la corrida:", file=sys.stderr)
        for e in errores:
            print(f"  - {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
