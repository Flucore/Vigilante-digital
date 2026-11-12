"""Punto de entrada del agente de triaje (etapa 1).

Procesa un evento JSON de punta a punta: valida la entrada, revisa si
trae texto con forma de instrucción, consulta turno e historial, y
decide con el respaldo determinista por reglas.

Etapa 1: sin llamadas al modelo, sin herramientas de escritura y sin
punto de aprobación. Las acciones de cada vía solo quedan anotadas.

Uso:
    python agente/main.py datos_ficticios/evento_normal.json
"""

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import herramientas
import politica
from traza import Traza

DIR_AGENTE = Path(__file__).resolve().parent
ARCHIVO_CONFIG = DIR_AGENTE / "config.json"

# Formato del identificador: también protege la ruta del archivo de traza.
_REGEX_EVENTO_ID = re.compile(r"^EV-\d{4}-\d{4}$")
_LARGO_MAX_TEXTO = 500
_CAMPOS_TEXTO = ("camara", "zona", "senal")
_CAMPOS_ESPERADOS = ("evento_id", "hora_local", "duracion_s",
                     "se_levanto") + _CAMPOS_TEXTO


class EventoInvalido(ValueError):
    """El evento de entrada no cumple el formato esperado."""


def cargar_config() -> dict:
    """Lee los umbrales y topes desde config.json."""
    with open(ARCHIVO_CONFIG, encoding="utf-8") as archivo:
        return json.load(archivo)


def validar_evento(crudo: dict) -> tuple[dict, list[str]]:
    """Valida tipos y formato del evento.

    Devuelve el evento limpio (solo campos esperados) y la lista de
    campos desconocidos que se descartaron.
    """
    if not isinstance(crudo, dict):
        raise EventoInvalido("El evento debe ser un objeto JSON")
    faltantes = [campo for campo in _CAMPOS_ESPERADOS if campo not in crudo]
    if faltantes:
        raise EventoInvalido(f"Faltan campos: {faltantes}")

    evento_id = crudo["evento_id"]
    if not isinstance(evento_id, str) or not _REGEX_EVENTO_ID.match(evento_id):
        raise EventoInvalido(f"evento_id con formato inválido: {evento_id!r}")

    duracion = crudo["duracion_s"]
    # bool es subclase de int: se excluye explícitamente.
    if isinstance(duracion, bool) or not isinstance(duracion, (int, float)):
        raise EventoInvalido("duracion_s debe ser numérico")
    if duracion < 0:
        raise EventoInvalido("duracion_s no puede ser negativo")

    if not isinstance(crudo["se_levanto"], bool):
        raise EventoInvalido("se_levanto debe ser true o false")

    try:
        hora = datetime.fromisoformat(crudo["hora_local"])
    except (TypeError, ValueError) as error:
        raise EventoInvalido(f"hora_local inválida: {error}") from error
    if hora.tzinfo is None:
        raise EventoInvalido("hora_local debe incluir zona horaria")

    for campo in _CAMPOS_TEXTO:
        valor = crudo[campo]
        if not isinstance(valor, str) or not valor.strip():
            raise EventoInvalido(f"{campo} debe ser texto no vacío")
        if len(valor) > _LARGO_MAX_TEXTO:
            raise EventoInvalido(f"{campo} excede {_LARGO_MAX_TEXTO} caracteres")

    evento = {campo: crudo[campo] for campo in _CAMPOS_ESPERADOS}
    descartados = sorted(set(crudo) - set(_CAMPOS_ESPERADOS))
    return evento, descartados


def procesar_evento(crudo: dict, config: dict) -> dict:
    """Ejecuta el agente sobre un evento y devuelve la decisión final."""
    inicio = time.monotonic()
    topes = config["topes"]

    evento_id = crudo.get("evento_id") if isinstance(crudo, dict) else None
    if not isinstance(evento_id, str) or not _REGEX_EVENTO_ID.match(evento_id):
        # Sin un identificador válido no se puede nombrar la traza.
        raise EventoInvalido(f"evento_id con formato inválido: {evento_id!r}")

    traza = Traza(evento_id, DIR_AGENTE / config["dir_traza"],
                  topes["max_pasos"])

    try:
        evento, descartados = validar_evento(crudo)
    except EventoInvalido as error:
        traza.registrar("validacion", entrada=crudo,
                        resultado={"valido": False, "error": str(error)})
        raise
    traza.registrar("validacion",
                    resultado={"valido": True,
                               "campos_descartados": descartados})

    # Se revisan todos los campos de texto, incluidos los descartados.
    campos_texto = {campo: valor for campo, valor in crudo.items()
                    if isinstance(valor, str) and campo != "evento_id"}
    hallazgos = politica.detectar_instrucciones(campos_texto)
    if hallazgos:
        traza.registrar("deteccion_instrucciones", resultado=hallazgos,
                        justificacion="Texto con forma de instrucción en la "
                                      "entrada; se trata como dato, no como "
                                      "orden. No influye en la decisión.")

    def hay_presupuesto() -> bool:
        """Deja siempre un paso libre para la decisión y respeta el timeout."""
        transcurrido = time.monotonic() - inicio
        return traza.pasos_restantes > 1 and transcurrido < topes["timeout_s"]

    llamadas = [
        ("consultar_turno", herramientas.consultar_turno,
         {"hora": evento["hora_local"]}),
        ("consultar_historial", herramientas.consultar_historial,
         {"zona": evento["zona"], "dias": config["historial_dias"],
          "hasta": evento["hora_local"]}),
    ]
    contexto = {}
    for nombre, funcion, argumentos in llamadas:
        if not hay_presupuesto():
            break
        try:
            resultado = funcion(**argumentos)
        except (OSError, ValueError, KeyError) as error:
            resultado = {"error": f"{type(error).__name__}: {error}"}
        contexto[nombre] = resultado
        traza.registrar("herramienta", herramienta=nombre,
                        entrada=argumentos, resultado=resultado)

    # Etapa 1: no hay modelo, la decisión viene siempre de las reglas.
    decision = politica.decidir(evento, contexto.get("consultar_turno"),
                                contexto.get("consultar_historial"),
                                config["politica"])
    traza.registrar("decision", decision=decision["via"],
                    justificacion=decision["justificacion"],
                    origen=decision["origen"],
                    regla=decision["regla"],
                    resultado={
                        "reglas_evaluadas": decision["reglas_evaluadas"],
                        "acciones_previstas": decision["acciones_previstas"],
                        "nota": "Etapa 1: acciones no ejecutadas "
                                "(sin herramientas de escritura ni "
                                "punto de aprobación).",
                        "motivo_reglas": "sin modelo en la etapa 1",
                    })

    return {
        "evento_id": evento_id,
        **decision,
        "instrucciones_detectadas": len(hallazgos),
        "contexto": contexto,
        "pasos": traza.pasos,
        "traza": str(traza.ruta),
    }


def main(argv: list[str]) -> int:
    """Lee el evento desde la ruta dada e imprime la decisión."""
    if len(argv) != 2:
        print("Uso: python agente/main.py <evento.json>", file=sys.stderr)
        return 2
    sys.stdout.reconfigure(encoding="utf-8")

    with open(argv[1], encoding="utf-8") as archivo:
        crudo = json.load(archivo)
    try:
        salida = procesar_evento(crudo, cargar_config())
    except EventoInvalido as error:
        print(f"Evento rechazado: {error}", file=sys.stderr)
        return 2

    print(json.dumps(salida, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
