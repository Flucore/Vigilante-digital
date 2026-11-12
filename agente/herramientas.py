"""Herramientas del agente de triaje.

Etapa 1: solo las dos herramientas de lectura. Las de escritura
(registrar_incidente, enviar_notificacion) se agregan junto con el
punto de aprobación, y recibirán credenciales solo después de él.

Todas operan sobre datos_ficticios/. Nunca sobre datos reales.
"""

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

DIR_DATOS = Path(__file__).resolve().parent.parent / "datos_ficticios"
ARCHIVO_TURNOS = DIR_DATOS / "turnos.csv"
ARCHIVO_HISTORIAL = DIR_DATOS / "historial_eventos.json"


def _parse_hora(hora: str) -> datetime:
    """Convierte una hora ISO 8601 exigiendo zona horaria explícita."""
    instante = datetime.fromisoformat(hora)
    if instante.tzinfo is None:
        raise ValueError(f"La hora debe incluir zona horaria: {hora!r}")
    return instante


def consultar_turno(hora: str) -> dict:
    """Indica quién estaba de turno a la hora dada y cuántos eran.

    Solo lectura. Devuelve encontrado=False si ningún turno cubre esa
    hora (por ejemplo, fuera del rango de la planilla ficticia).
    """
    instante = _parse_hora(hora)
    turno = None
    funcionarios = []

    with open(ARCHIVO_TURNOS, encoding="utf-8", newline="") as archivo:
        for fila in csv.DictReader(archivo):
            inicio = _parse_hora(fila["inicio"])
            fin = _parse_hora(fila["fin"])
            if inicio <= instante < fin:
                turno = {
                    "turno": fila["turno"],
                    "inicio": fila["inicio"],
                    "fin": fila["fin"],
                }
                funcionarios.append(
                    {"codigo": fila["funcionario"], "cargo": fila["cargo"]}
                )

    if turno is None:
        return {"encontrado": False, "hora": hora,
                "funcionarios": [], "cantidad": 0}
    return {"encontrado": True, "hora": hora, **turno,
            "funcionarios": funcionarios, "cantidad": len(funcionarios)}


def consultar_historial(zona: str, dias: int, hasta: str | None = None) -> dict:
    """Lista los incidentes previos en una zona dentro de los últimos días.

    Solo lectura. La ventana es [hasta - dias, hasta). Si no se entrega
    'hasta', se usa la hora actual; el agente pasa la hora del evento
    para que el resultado sea reproducible. La zona se compara de forma
    exacta: un texto manipulado no coincide con ninguna zona real.
    """
    if dias <= 0:
        raise ValueError(f"dias debe ser positivo: {dias!r}")
    fin = _parse_hora(hasta) if hasta else datetime.now().astimezone()
    inicio = fin - timedelta(days=dias)

    with open(ARCHIVO_HISTORIAL, encoding="utf-8") as archivo:
        registros = json.load(archivo)

    previos = [
        registro for registro in registros
        if registro["zona"] == zona
        and inicio <= _parse_hora(registro["hora_local"]) < fin
    ]
    previos.sort(key=lambda registro: _parse_hora(registro["hora_local"]))

    return {
        "zona": zona,
        "dias": dias,
        "desde": inicio.isoformat(),
        "hasta": fin.isoformat(),
        "incidentes": previos,
        "cantidad": len(previos),
    }
