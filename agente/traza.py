"""Registro paso a paso de una ejecución del agente.

Cada ejecución escribe salida/traza/<evento_id>.jsonl, un registro JSON
por línea. Cada paso se escribe apenas ocurre, de modo que una
ejecución interrumpida deja su traza parcial.
"""

import json
from datetime import datetime
from pathlib import Path


class TopePasosExcedido(RuntimeError):
    """Se intentó registrar más pasos que el tope por ejecución."""


class Traza:
    """Traza JSONL de una ejecución, con tope de pasos."""

    def __init__(self, evento_id: str, dir_salida: Path, max_pasos: int):
        dir_salida.mkdir(parents=True, exist_ok=True)
        self.ruta = dir_salida / f"{evento_id}.jsonl"
        self.max_pasos = max_pasos
        self.pasos = 0
        # Cada ejecución reemplaza la traza anterior del mismo evento.
        self.ruta.write_text("", encoding="utf-8")

    @property
    def pasos_restantes(self) -> int:
        """Pasos que aún se pueden registrar en esta ejecución."""
        return self.max_pasos - self.pasos

    def registrar(self, tipo: str, *, herramienta: str | None = None,
                  entrada: dict | None = None, resultado: object = None,
                  decision: str | None = None,
                  justificacion: str | None = None,
                  origen: str | None = None,
                  regla: str | None = None) -> dict:
        """Agrega un paso a la traza y lo escribe de inmediato.

        'origen' indica de dónde vino la decisión: "reglas" o "modelo".
        'regla' es la regla del respaldo que disparó la decisión.
        """
        if self.pasos >= self.max_pasos:
            raise TopePasosExcedido(
                f"Tope de {self.max_pasos} pasos alcanzado")
        self.pasos += 1
        registro = {
            "paso": self.pasos,
            "instante": datetime.now().astimezone().isoformat(),
            "tipo": tipo,
            "herramienta": herramienta,
            "entrada": entrada,
            "resultado": resultado,
            "decision": decision,
            "justificacion": justificacion,
            "origen": origen,
            "regla": regla,
        }
        with open(self.ruta, "a", encoding="utf-8") as archivo:
            archivo.write(json.dumps(registro, ensure_ascii=False) + "\n")
        return registro
