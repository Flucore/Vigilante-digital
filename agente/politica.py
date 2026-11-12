"""Respaldo determinista por reglas del agente de triaje.

Es la decisión que se aplica cuando no hay modelo (falta la clave, no
hay red) o cuando el modelo devuelve algo fuera de la lista cerrada.
En la etapa 1 es la única vía de decisión.

Los umbrales vienen de config.json; aquí no hay números incrustados.
"""

import re

ESCALAMIENTO = "escalamiento_inmediato"
RUTINA = "reporte_rutina"
FALSO_POSITIVO = "probable_falso_positivo"

# Lista cerrada de tres vías. Cualquier otra cosa no es una decisión válida.
VIAS = (ESCALAMIENTO, RUTINA, FALSO_POSITIVO)

# Acciones que cada vía ejecutará cuando existan las herramientas de
# escritura y el punto de aprobación. En la etapa 1 solo se anotan.
ACCIONES_POR_VIA = {
    ESCALAMIENTO: {
        "herramientas": ["registrar_incidente", "enviar_notificacion"],
        "destinatarios": ["turno", "coordinacion"],
        "prioridad": "alta",
    },
    RUTINA: {
        "herramientas": ["registrar_incidente", "enviar_notificacion"],
        "destinatarios": ["turno"],
        "prioridad": "normal",
    },
    FALSO_POSITIVO: {
        "herramientas": ["registrar_incidente"],
        "destinatarios": [],
        "prioridad": "revision",
    },
}

# Patrones de texto con forma de instrucción dirigida a un modelo.
# Detectarlos no cambia la decisión: solo se registran en la traza.
_PATRONES_INSTRUCCION = [
    r"\bignor[ae]\w*\b.*\binstrucci",
    r"\bignore\b.*\binstruction",
    r"\bolvida\w*\b",
    r"\b(sistema|system)\s*:",
    r"\beres un\b",
    r"\byou are\b",
    r"\bact[uú]a como\b",
    r"\bact as\b",
    r"\bsin (pedir )?aprobaci[oó]n\b",
    r"\bclasifica\w*\b.*\bcomo\b",
    r"\b(no )?notifiques\b",
    r"\benv[ií]a\b",
    r"\bprompt\b",
    r"<\s*/?\s*\w+[^>]*>",
]
_REGEX_INSTRUCCION = [
    re.compile(patron, re.IGNORECASE | re.DOTALL)
    for patron in _PATRONES_INSTRUCCION
]


def es_via_valida(via: object) -> bool:
    """Indica si un valor pertenece a la lista cerrada de vías."""
    return isinstance(via, str) and via in VIAS


def _evaluar_reglas(evento: dict, turno: dict | None,
                    historial: dict | None, umbrales: dict) -> list[dict]:
    """Evalúa cada regla en orden de prioridad.

    Devuelve una entrada por regla con su vía, si se cumplió y el
    motivo. Una regla cuyo dato de contexto falta no se cumple.
    """
    duracion = evento["duracion_s"]
    se_levanto = evento["se_levanto"]
    umbral_largo = umbrales["duracion_escalamiento_s"]
    umbral_corto = umbrales["duracion_falso_positivo_s"]
    turno_riesgo = umbrales["turno_riesgo"]
    max_funcionarios = umbrales["max_funcionarios_turno_riesgo"]
    umbral_incidentes = umbrales["incidentes_escalamiento"]

    reglas = [{
        "regla": "episodio_largo_sin_levantarse",
        "via": ESCALAMIENTO,
        "cumple": duracion >= umbral_largo and not se_levanto,
        "motivo": (f"duracion_s={duracion} (umbral {umbral_largo}), "
                   f"se_levanto={se_levanto}"),
    }]

    if turno and turno.get("encontrado"):
        cumple = (turno["turno"] == turno_riesgo
                  and turno["cantidad"] <= max_funcionarios)
        motivo = (f"turno={turno['turno']}, funcionarios={turno['cantidad']} "
                  f"(riesgo: {turno_riesgo} con <= {max_funcionarios})")
    else:
        cumple = False
        motivo = "sin dato de turno: la regla no se pudo evaluar"
    reglas.append({"regla": "turno_noche_un_funcionario",
                   "via": ESCALAMIENTO, "cumple": cumple, "motivo": motivo})

    if historial and "cantidad" in historial:
        # Los previos más el evento actual.
        total = historial["cantidad"] + 1
        cumple = total >= umbral_incidentes
        motivo = (f"{total} incidentes en la zona en {historial['dias']} "
                  f"días contando este (umbral {umbral_incidentes})")
    else:
        cumple = False
        motivo = "sin dato de historial: la regla no se pudo evaluar"
    reglas.append({"regla": "incidentes_repetidos_zona",
                   "via": ESCALAMIENTO, "cumple": cumple, "motivo": motivo})

    reglas.append({
        "regla": "episodio_corto_se_levanto",
        "via": FALSO_POSITIVO,
        "cumple": duracion < umbral_corto and se_levanto,
        "motivo": (f"duracion_s={duracion} (umbral {umbral_corto}), "
                   f"se_levanto={se_levanto}"),
    })
    return reglas


def decidir(evento: dict, turno: dict | None, historial: dict | None,
            umbrales: dict) -> dict:
    """Aplica las reglas deterministas sobre un evento ya validado.

    'turno' e 'historial' son los resultados de consultar_turno y
    consultar_historial (None o con 'error' si no respondieron). Los
    campos de texto del evento no influyen en la decisión. Gana la
    primera regla que se cumple; si ninguna, reporte_rutina. Siempre
    devuelve una vía.
    """
    reglas = _evaluar_reglas(evento, turno, historial, umbrales)
    disparada = next((regla for regla in reglas if regla["cumple"]), None)

    if disparada is None:
        via = RUTINA
        nombre_regla = "resto"
        justificacion = "ninguna regla de escalamiento ni de falso positivo"
    else:
        via = disparada["via"]
        nombre_regla = disparada["regla"]
        justificacion = disparada["motivo"]

    return {
        "via": via,
        "regla": nombre_regla,
        "justificacion": justificacion,
        "origen": "reglas",
        "reglas_evaluadas": reglas,
        "acciones_previstas": ACCIONES_POR_VIA[via],
    }


def detectar_instrucciones(campos: dict) -> list[dict]:
    """Busca texto con forma de instrucción en los campos de texto.

    Devuelve una lista con el campo, el patrón que coincidió y un
    extracto, para registrarlo en la traza.
    """
    hallazgos = []
    for nombre, valor in campos.items():
        if not isinstance(valor, str):
            continue
        for regex in _REGEX_INSTRUCCION:
            coincidencia = regex.search(valor)
            if coincidencia:
                hallazgos.append({
                    "campo": nombre,
                    "patron": regex.pattern,
                    "extracto": coincidencia.group(0)[:120],
                })
    return hallazgos
