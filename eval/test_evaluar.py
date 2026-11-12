"""Tests de eval/evaluar.py (puntos 3 a 7 de ESPECIFICACIONES.md), sin YOLO."""
from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval import evaluar
from eval.evaluar import BRAZOS, ErrorEvaluacion

CONFIG = str(ROOT / "eval" / "config_eval.json")
CABECERA = "archivo,etiqueta,inicio_caida_s,escenario,locacion\n"


def _video(path: Path, frames: int, fps: float = 30.0) -> None:
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (32, 24))
    for _ in range(frames):
        w.write(np.zeros((24, 32, 3), np.uint8))
    w.release()


def _labels(path: Path, filas: str) -> Path:
    path.write_text(CABECERA + filas, encoding="utf-8")
    return path


def _evento(inicio: float, metodo: str, ventana, tipo: str = "fall") -> Dict:
    return {"event_type": tipo, "inicio_video_s": inicio,
            "metadata": {"metodo": metodo, "ventana": ventana}}


def _leer(path: Path) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture
def goldset(tmp_path: Path):
    clips = tmp_path / "goldset"
    clips.mkdir()
    _video(clips / "caida_01.avi", 90)       # 3 s
    _video(clips / "caida_02.avi", 60)       # 2 s, sin inicio_caida_s
    _video(clips / "sentarse_01.avi", 150)   # 5 s
    _video(clips / "caminar_01.avi", 150)    # 5 s
    (clips / ".gitkeep").write_text("")
    labels = _labels(tmp_path / "labels.csv", (
        "caida_01.avi,caida,1.0,caida frontal,pasillo\n"
        "caida_02.avi,caida,,caida lateral,sala\n"
        "sentarse_01.avi,no_caida,,sentarse en el suelo,sala\n"
        "caminar_01.avi,no_caida,,caminar,pasillo\n"
    ))
    return clips, labels


def _ejecutor_falso(clip: Path, brazo) -> List[Dict]:
    """bbox: alarma en todo (incluye falsa en sentarse); pose_v1: igual salvo caminar;
    pose_v8: solo caídas reales y más tarde."""
    m, v = brazo.metodo, brazo.ventana
    nombre = clip.name
    if brazo.nombre == "bbox":
        return {"caida_01.avi": [_evento(1.2, m, v), _evento(2.0, m, v)],
                "caida_02.avi": [],
                "sentarse_01.avi": [_evento(0.5, m, v)],
                "caminar_01.avi": [_evento(3.0, m, v)]}[nombre]
    if brazo.nombre == "pose_v1":
        return {"caida_01.avi": [_evento(1.1, m, v)],
                "caida_02.avi": [_evento(0.4, m, v)],
                "sentarse_01.avi": [_evento(0.7, m, v)],
                "caminar_01.avi": []}[nombre]
    return {"caida_01.avi": [_evento(1.4, m, v)],
            "caida_02.avi": [_evento(0.9, m, v)],
            "sentarse_01.avi": [],
            "caminar_01.avi": []}[nombre]


def _correr(goldset, tmp_path, ejecutar=_ejecutor_falso, config=CONFIG):
    clips, labels = goldset
    salida = tmp_path / "resultados"
    code = evaluar.main(
        ["--clips", str(clips), "--labels", str(labels), "--salida", str(salida), "--config", config],
        ejecutar=ejecutar,
    )
    return code, salida


# ── Punto 3: etiquetas ────────────────────────────────────────────────────────

def test_falla_si_clip_listado_no_existe(goldset, tmp_path):
    clips, labels = goldset
    (clips / "caminar_01.avi").unlink()
    with pytest.raises(ErrorEvaluacion, match="caminar_01.avi"):
        evaluar.validar_carpeta(clips, evaluar.cargar_etiquetas(labels))


def test_falla_si_clip_no_esta_listado(goldset):
    clips, labels = goldset
    _video(clips / "extra.mp4", 10)
    with pytest.raises(ErrorEvaluacion, match="no están en las etiquetas:\n    extra.mp4"):
        evaluar.validar_carpeta(clips, evaluar.cargar_etiquetas(labels))


def test_main_aborta_con_codigo_2_si_falta_clip(goldset, tmp_path, capsys):
    clips, _ = goldset
    _video(clips / "extra.mp4", 10)
    code, salida = _correr(goldset, tmp_path)
    assert code == 2
    assert "extra.mp4" in capsys.readouterr().err
    assert not salida.exists()


@pytest.mark.parametrize("fila, error", [
    ("a.mp4,caida_fuerte,,x,y\n", "etiqueta 'caida_fuerte' inválida"),
    ("a.mp4,caida,tres,x,y\n", "no es un número"),
    ("a.mp4,no_caida,2.0,x,y\n", "es no_caida pero tiene inicio_caida_s"),
    ("a.mp4,caida,1,x,y\na.mp4,caida,1,x,y\n", "más de una vez"),
    ("sub/a.mp4,caida,1,x,y\n", "sin carpetas"),
])
def test_etiquetas_invalidas(tmp_path, fila, error):
    with pytest.raises(ErrorEvaluacion, match=error):
        evaluar.cargar_etiquetas(_labels(tmp_path / "l.csv", fila))


def test_etiquetas_con_bom_y_coma_decimal(tmp_path):
    p = tmp_path / "l.csv"
    p.write_text(CABECERA + 'a.mp4,caida,"3,4",caída frontal,pasillo\n', encoding="utf-8-sig")
    (et,) = evaluar.cargar_etiquetas(p)
    assert et.inicio_caida_s == 3.4 and et.escenario == "caída frontal"


# ── Módulo activo ─────────────────────────────────────────────────────────────

def test_aborta_si_modulo_no_es_fall_detection(goldset, tmp_path, capsys):
    cfg = tmp_path / "geo.json"
    cfg.write_text(
        Path(CONFIG).read_text(encoding="utf-8").replace('["fall_detection"]', '["geofence"]'),
        encoding="utf-8",
    )
    code, salida = _correr(goldset, tmp_path, config=str(cfg))
    err = capsys.readouterr().err
    assert code == 2
    assert "Módulo activo 'geofence' en cámara CAM_EVAL" in err
    assert "exige fall_detection" in err
    assert not salida.exists()


# ── Puntos 4 a 6: corrida, métricas y salidas ─────────────────────────────────

def test_corrida_completa_detalle_y_resumen(goldset, tmp_path, capsys):
    code, salida = _correr(goldset, tmp_path)
    assert code == 0

    detalle = _leer(salida / "detalle.csv")
    assert list(detalle[0].keys()) == evaluar.COLUMNAS_DETALLE
    assert len(detalle) == 4 * len(BRAZOS)
    fila = next(r for r in detalle if r["brazo"] == "bbox" and r["archivo"] == "caida_01.avi")
    assert fila == {
        "brazo": "bbox", "metodo": "bbox", "ventana": "", "archivo": "caida_01.avi",
        "etiqueta": "caida", "escenario": "caida frontal", "alarma": "1",
        "segundo_alarma": "1.200", "duracion_s": "3.000", "resultado": "VP",
    }

    resumen = {r["brazo"]: r for r in _leer(salida / "resumen.csv")}
    assert list(resumen) == ["bbox", "pose_v1", "pose_v8"]

    b = resumen["bbox"]   # VP=1 FN=1 FP=2 VN=0
    assert (b["VP"], b["FN"], b["FP"], b["VN"], b["clips"]) == ("1", "1", "2", "0", "4")
    assert b["sensibilidad"] == "0.50"
    assert b["especificidad"] == "0.00"
    assert b["tasa_falsos_positivos"] == "1.00"
    assert b["falsas_alarmas_camara_hora"] == "720.00"   # 2 alarmas / (10 s = 1/360 h)
    assert b["denominador_min"] == "0.2"
    assert b["latencia_mediana_s"] == "0.2"              # 1.2 - 1.0
    assert b["n_latencia"] == "1"

    v1 = resumen["pose_v1"]  # VP=2 FN=0 FP=1 VN=1
    assert (v1["sensibilidad"], v1["especificidad"], v1["tasa_falsos_positivos"]) == ("1.00", "0.50", "0.50")
    assert v1["ventana"] == "1"

    v8 = resumen["pose_v8"]  # VP=2 FP=0
    assert (v8["sensibilidad"], v8["especificidad"], v8["falsas_alarmas_camara_hora"]) == ("1.00", "1.00", "0.00")
    assert v8["latencia_mediana_s"] == "0.4"
    assert v8["clips_con_error"] == "0"

    out = capsys.readouterr().out
    assert "(denominador: 0,2 min)" in out
    for nombre in ("bbox", "pose_v1", "pose_v8"):
        assert nombre in out


def test_determinista_y_sin_rutas_absolutas(goldset, tmp_path):
    _, salida = _correr(goldset, tmp_path)
    primero = {n: (salida / n).read_bytes() for n in ("detalle.csv", "resumen.csv")}
    _correr(goldset, tmp_path)
    for n, contenido in primero.items():
        assert (salida / n).read_bytes() == contenido
        assert str(tmp_path).encode() not in contenido


def test_sin_denominador_y_sin_latencia(tmp_path, capsys):
    clips = tmp_path / "g"
    clips.mkdir()
    _video(clips / "c.avi", 30)
    labels = _labels(tmp_path / "l.csv", "c.avi,caida,,x,y\n")
    code = evaluar.main(
        ["--clips", str(clips), "--labels", str(labels), "--salida", str(tmp_path / "r"), "--config", CONFIG],
        ejecutar=lambda clip, b: [],
    )
    assert code == 0
    r = _leer(tmp_path / "r" / "resumen.csv")[0]
    assert r["especificidad"] == "" and r["falsas_alarmas_camara_hora"] == "" and r["latencia_mediana_s"] == ""
    assert "n/d (denominador: 0,0 min)" in capsys.readouterr().out


# ── Punto 7: un clip que falla no aborta la corrida ──────────────────────────

def test_clip_con_error_se_reporta_y_sigue(goldset, tmp_path, capsys):
    def ejecutar(clip, brazo):
        if clip.name == "caida_02.avi" and brazo.nombre == "pose_v8":
            raise RuntimeError("explotó")
        return _ejecutor_falso(clip, brazo)

    code, salida = _correr(goldset, tmp_path, ejecutar=ejecutar)
    assert code == 1
    assert "caida_02.avi [pose_v8]: RuntimeError: explotó" in capsys.readouterr().err
    resumen = {r["brazo"]: r for r in _leer(salida / "resumen.csv")}
    assert resumen["pose_v8"]["clips"] == "3" and resumen["pose_v8"]["clips_con_error"] == "1"
    assert resumen["bbox"]["clips"] == "4"


def test_fallo_silencioso_del_runner_cuenta_como_error(goldset, tmp_path, capsys):
    """run_file loggea y devuelve [] si el detector no carga: no debe contarse como 'sin alarma'."""
    def ejecutar(clip, brazo):
        logging.getLogger("vigilante.runner").warning(
            "Detector no disponible (x) — procesando sin inferencia.")
        return []

    code, salida = _correr(goldset, tmp_path, ejecutar=ejecutar)
    assert code == 1
    assert "Detector no disponible" in capsys.readouterr().err
    assert len(_leer(salida / "detalle.csv")) == 0


def test_video_ilegible_se_reporta_y_sigue(goldset, tmp_path, capsys):
    clips, _ = goldset
    (clips / "caminar_01.avi").write_bytes(b"no es un video")
    code, salida = _correr(goldset, tmp_path)
    assert code == 1
    assert "caminar_01.avi [todos los brazos]" in capsys.readouterr().err
    assert len(_leer(salida / "detalle.csv")) == 3 * len(BRAZOS)


def test_eventos_que_no_son_fall_se_descartan_y_reportan(goldset, tmp_path, capsys):
    def ejecutar(clip, brazo):
        if clip.name == "caminar_01.avi":
            return [_evento(1.0, brazo.metodo, brazo.ventana, tipo="zone_occupancy")]
        return _ejecutor_falso(clip, brazo)

    code, salida = _correr(goldset, tmp_path, ejecutar=ejecutar)
    assert code == 1
    assert "zone_occupancy" in capsys.readouterr().err
    fila = next(r for r in _leer(salida / "detalle.csv")
                if r["brazo"] == "bbox" and r["archivo"] == "caminar_01.avi")
    assert fila["alarma"] == "0" and fila["resultado"] == "VN"


# ── Barrido de ventanas ───────────────────────────────────────────────────────

def test_default_son_los_tres_brazos_de_la_spec():
    assert [b.nombre for b in BRAZOS] == ["bbox", "pose_v1", "pose_v8"]
    assert evaluar.construir_brazos(evaluar.VENTANAS_POR_DEFECTO) == BRAZOS


def test_barrido_una_fila_por_ventana_y_bbox_una_vez(goldset, tmp_path, capsys):
    llamadas: List[str] = []

    def ejecutar(clip, brazo):
        llamadas.append(brazo.nombre)
        return [_evento(1.5, brazo.metodo, brazo.ventana)] if brazo.ventana and brazo.ventana <= 3 else []

    clips, labels = goldset
    salida = tmp_path / "barrido"
    code = evaluar.main(
        ["--clips", str(clips), "--labels", str(labels), "--salida", str(salida),
         "--config", CONFIG, "--ventanas", "10,1,2,3,4,5,6,8"],
        ejecutar=ejecutar,
    )
    assert code == 0
    esperados = ["bbox"] + [f"pose_v{v}" for v in (1, 2, 3, 4, 5, 6, 8, 10)]
    assert llamadas.count("bbox") == 4                     # una vez por clip
    resumen = _leer(salida / "resumen.csv")
    assert [r["brazo"] for r in resumen] == esperados
    assert [r["ventana"] for r in resumen] == ["", "1", "2", "3", "4", "5", "6", "8", "10"]
    assert {r["sensibilidad"] for r in resumen if r["brazo"] in ("pose_v1", "pose_v3")} == {"1.00"}
    assert resumen[-1]["sensibilidad"] == "0.00"
    assert len(_leer(salida / "detalle.csv")) == 4 * len(esperados)
    out = capsys.readouterr().out
    assert "4 clips x 9 brazos" in out
    assert "denominador: 0,2 min" in out
    for nombre in esperados:
        assert nombre in out


@pytest.mark.parametrize("texto, error", [
    ("1,0", ">= 1"), ("1,a", "no es un entero"), ("1,,2", "mal formada"),
    ("", "mal formada"), ("2,2", "repetida"),
])
def test_ventanas_invalidas(texto, error):
    import argparse
    with pytest.raises(argparse.ArgumentTypeError, match=error):
        evaluar.parsear_ventanas(texto)
