"""Pruebas de outputs/notificador_correo.py (sin red ni SMTP)."""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
import pytest

from outputs import notificador_correo as nc


def _evt(inicio: float, fin: float, cam: str = "CAM_IP_01") -> dict:
    return {"event_type": "fall", "camera_id": cam,
            "inicio_video_s": inicio, "fin_video_s": fin,
            "start_time": "2026-11-22T21:00:00+00:00", "duration_seconds": fin - inicio}


# ── Agrupación ────────────────────────────────────────────────────────────────

def test_fragmentos_de_una_caida_avisan_una_vez():
    # Patrón real del video de demo: 3 fragmentos en < 1 s.
    a = nc.AgrupadorCaidas(ventana_s=3.0)
    assert a.evaluar(_evt(17.97, 18.40)) is True
    assert a.evaluar(_evt(18.47, 18.50)) is False
    assert a.evaluar(_evt(18.53, 19.43)) is False


def test_caidas_separadas_son_distintas():
    a = nc.AgrupadorCaidas(ventana_s=3.0)
    inicios = [(4.6, 5.5), (11.9, 12.8), (17.97, 19.4), (24.6, 25.8), (30.1, 32.0)]
    assert [a.evaluar(_evt(i, f)) for i, f in inicios] == [True] * 5


def test_duracion_minima_ignora_fragmento_suelto_y_avisa_al_acumular():
    # Clip 12 propio: fragmento falso de 0,17 s al entrar, caída real a los 2,7 s.
    a = nc.AgrupadorCaidas(ventana_s=3.0, duracion_minima_s=0.5)
    assert a.evaluar(_evt(0.27, 0.44)) is False
    assert a.evaluar(_evt(2.70, 5.60)) is True
    # Clip 05 propio: 0,13 s + 0,61 s + 0,50 s → avisa en el segundo.
    a.reiniciar()
    assert a.evaluar(_evt(4.30, 4.43)) is False
    assert a.evaluar(_evt(4.53, 5.14)) is True
    assert a.evaluar(_evt(5.24, 5.74)) is False


def test_fragmento_corto_aislado_nunca_avisa():
    a = nc.AgrupadorCaidas(ventana_s=3.0, duracion_minima_s=0.5)
    assert a.evaluar(_evt(0.17, 0.24)) is False


def test_loop_o_clip_nuevo_reinicia_el_tiempo():
    a = nc.AgrupadorCaidas(ventana_s=3.0)
    assert a.evaluar(_evt(30.0, 32.0)) is True
    assert a.evaluar(_evt(4.6, 5.5)) is True


def test_reiniciar_evita_unir_caidas_de_clips_distintos():
    # Clip A termina con caída en 5,5 s; el clip B cae a los 6,0 s.
    a = nc.AgrupadorCaidas(ventana_s=3.0)
    assert a.evaluar(_evt(4.0, 5.5)) is True
    a.reiniciar("CAM_IP_01")
    assert a.evaluar(_evt(6.0, 7.0)) is True


def test_camaras_independientes():
    a = nc.AgrupadorCaidas(ventana_s=3.0)
    assert a.evaluar(_evt(10.0, 11.0, "A")) is True
    assert a.evaluar(_evt(10.2, 11.0, "B")) is True


def test_evento_sin_tiempo_de_video_no_se_descarta():
    a = nc.AgrupadorCaidas()
    assert a.evaluar({"camera_id": "X"}) is True
    assert a.evaluar({"camera_id": "X"}) is True


# ── .env y credenciales ───────────────────────────────────────────────────────

_VARS = ["SMTP_USER", "SMTP_PASSWORD", "EMAIL_RECIPIENTS", "SMTP_HOST", "SMTP_PORT",
         "GMAIL_SENDER_EMAIL", "GMAIL_APP_PASSWORD"]


@pytest.fixture
def entorno_limpio(monkeypatch):
    for v in _VARS:
        monkeypatch.delenv(v, raising=False)
    return monkeypatch


def test_cargar_env_y_nombres_de_env_example(tmp_path: Path, entorno_limpio):
    env = tmp_path / ".env"
    env.write_text(
        "# comentario\n"
        "SMTP_USER=alertas@gmail.com\n"
        'SMTP_PASSWORD="abcd efgh ijkl mnop"\n'
        "EMAIL_RECIPIENTS=uno@x.cl, dos@y.cl  # dos destinos\n",
        encoding="utf-8",
    )
    assert nc.cargar_env(env) is True
    cred = nc.credenciales_desde_entorno()
    assert cred.remitente == "alertas@gmail.com"
    assert cred.clave_aplicacion == "abcd efgh ijkl mnop"
    assert cred.destinatarios == ["uno@x.cl", "dos@y.cl"]
    assert cred.completas


def test_clave_repetida_gana_la_ultima(tmp_path: Path, entorno_limpio):
    # Caso real: datos verdaderos agregados al final sin borrar los de ejemplo.
    env = tmp_path / ".env"
    env.write_text(
        "SMTP_USER=tu-correo@ejemplo.com\nSMTP_PASSWORD=APP_PASSWORD_GMAIL\n"
        "EMAIL_RECIPIENTS=operador@ejemplo.com\n\n"
        "SMTP_USER=real@gmail.com\nSMTP_PASSWORD=abcd efgh ijkl mnop\n"
        "EMAIL_RECIPIENTS=a@gmail.com\n",
        encoding="utf-8",
    )
    nc.cargar_env(env)
    cred = nc.credenciales_desde_entorno()
    assert (cred.remitente, cred.destinatarios) == ("real@gmail.com", ["a@gmail.com"])
    assert cred.completas


def test_acepta_nombres_gmail_de_email_sender(entorno_limpio):
    entorno_limpio.setenv("GMAIL_SENDER_EMAIL", "a@gmail.com")
    entorno_limpio.setenv("GMAIL_APP_PASSWORD", "clave")
    cred = nc.credenciales_desde_entorno(["extra@z.cl"])
    assert cred.remitente == "a@gmail.com" and cred.destinatarios == ["extra@z.cl"]
    assert cred.completas


def test_valores_de_ejemplo_no_cuentan_como_credenciales(entorno_limpio):
    entorno_limpio.setenv("SMTP_USER", "tu-correo@ejemplo.com")
    entorno_limpio.setenv("SMTP_PASSWORD", "APP_PASSWORD_GMAIL")
    entorno_limpio.setenv("EMAIL_RECIPIENTS", "operador@ejemplo.com")
    cred = nc.credenciales_desde_entorno()
    assert not cred.completas
    assert len(cred.faltantes()) == 3


def test_enmascarar():
    assert nc.enmascarar("usuario@gmail.com") == "u***@gmail.com"
    assert nc.enmascarar("sin-arroba") == "***"


# ── Notificador (simulado, sin SMTP) ──────────────────────────────────────────

def _notificador(tmp_path, cred=None, **kw) -> nc.NotificadorCorreo:
    cred = cred or nc.CredencialesCorreo("", "", ["a@x.cl"])  # incompletas → simulado
    return nc.NotificadorCorreo(cred, report_dir=tmp_path, **kw)


def _foto(tmp_path) -> str:
    import cv2
    path = tmp_path / "foto.jpg"
    cv2.imwrite(str(path), np.full((1080, 1920, 3), 120, np.uint8))
    return str(path)


def test_sin_credenciales_queda_en_simulado_y_genera_pdf_e_imagen(tmp_path):
    n = _notificador(tmp_path)
    assert n.simulado
    evento = dict(_evt(4.6, 5.5), photo_path=_foto(tmp_path))
    numero = n.registrar(evento)
    assert numero == 1 and "hora_analisis" in evento
    listo = threading.Event()
    res: list = []
    n.enviar_async(evento, numero, lambda r: (res.append(r), listo.set()))
    assert listo.wait(30)
    n.cerrar()
    assert res[0].simulado and not res[0].enviado
    assert res[0].pdf_path and Path(res[0].pdf_path).exists()
    import cv2
    assert cv2.imread(res[0].imagen_path).shape[1] == 960   # reducida para el correo


def test_filtro_de_camaras_numeracion_y_reinicio(tmp_path):
    n = _notificador(tmp_path, camaras=["CAM_IP_01"], duracion_minima_s=0.0)
    assert n.registrar(_evt(1.0, 2.0, "OTRA")) is None
    assert n.registrar(_evt(1.0, 2.0)) == 1
    assert n.registrar(_evt(2.2, 2.5)) is None      # fragmento
    assert n.registrar(_evt(9.0, 10.0)) == 2
    n.reiniciar_sesion()
    assert n.registrar(_evt(1.0, 2.0)) == 1
    n.cerrar()


def test_tope_de_correos(tmp_path):
    n = _notificador(tmp_path, max_correos=1)
    listo = threading.Event()
    res: list = []
    n.enviar_async(_evt(1, 2), 2, lambda r: (res.append(r), listo.set()))
    assert listo.wait(10)
    n.cerrar()
    assert "tope" in res[0].texto and not res[0].pdf_path


def test_mensaje_html_con_imagen_en_linea_ubicacion_y_pdf(tmp_path):
    cred = nc.CredencialesCorreo("vigia@gmail.com", "clave", ["a@x.cl", "b@y.cl"])
    n = _notificador(tmp_path, cred=cred)
    evento = dict(_evt(2.7, 5.6), ubicacion="Balcón de acceso", clip="clip_12.mp4",
                  camera_name="Cámara IP 01", hora_analisis="2026-11-22T19:45:10-03:00")
    imagen = n._preparar_imagen(dict(evento, photo_path=_foto(tmp_path)), 1)
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(b"%PDF-1.4 prueba")
    msg = n._armar_mensaje(evento, 1, imagen, str(pdf))
    n.cerrar()
    assert msg["To"] == "a@x.cl, b@y.cl"
    assert "Balcón de acceso" in msg["Subject"] and "19:45" in msg["Subject"]
    tipos = [p.get_content_type() for p in msg.walk()]
    assert {"text/plain", "text/html", "image/jpeg", "application/pdf"} <= set(tipos)
    html_part = next(p for p in msg.walk() if p.get_content_type() == "text/html")
    cuerpo = html_part.get_content()
    assert "cid:" in cuerpo and "22-11-2026 19:45:10" in cuerpo and "Balcón de acceso" in cuerpo


def test_hora_local_para_pdf_y_correo(tmp_path):
    n = _notificador(tmp_path, zona_horaria="America/Santiago")
    # 21:58 UTC = 18:58 en Santiago (UTC-3 en noviembre)
    assert n._a_local("2026-11-22T21:58:12+00:00").startswith("2026-11-22T18:58:12")
    assert n._hora_local({"start_time": "2026-11-22T21:58:12+00:00"}) == "22-11-2026 18:58:12"
    assert n._a_local("no-es-fecha") is None
    n.cerrar()


def test_cargar_env_no_toca_variables_ajenas_al_correo(tmp_path: Path, entorno_limpio):
    # API_SECRET_KEY de ejemplo activaba la autenticación del panel y cortaba el video.
    entorno_limpio.delenv("API_SECRET_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("API_SECRET_KEY=cambiar\nSMTP_USER=a@gmail.com\n", encoding="utf-8")
    nc.cargar_env(env)
    import os
    assert "API_SECRET_KEY" not in os.environ
    assert os.environ["SMTP_USER"] == "a@gmail.com"
