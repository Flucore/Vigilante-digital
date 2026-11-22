"""API y página de "Análisis de clips" (demo de correo por caída).

Solo HTTP: no importa runner ni inputs. El lanzador (demo_analisis.py) crea
un controlador con estos métodos y lo inyecta con crear_app():

    estado() -> dict                    estado de la tanda y de cada clip
    iniciar(ids: list[str] | None)      analiza esos clips (None = todos)
    detener()                           corta la tanda en curso
    probar_correo() -> dict             envía un correo de prueba
    ruta_imagen(clip_id) -> str | None  cuadro de la caída detectada

El video en vivo lo sirve el panel de operador (/operator/ws/live/<cámara>).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional, Protocol

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

_HTML = Path(__file__).resolve().parent / "static" / "analisis.html"


class ControladorAnalisis(Protocol):
    def estado(self) -> dict: ...
    def iniciar(self, ids: Optional[List[str]]) -> None: ...
    def detener(self) -> None: ...
    def probar_correo(self) -> dict: ...
    def ruta_imagen(self, clip_id: str) -> Optional[str]: ...


class _PedidoInicio(BaseModel):
    ids: Optional[List[str]] = None


def crear_app(controlador: ControladorAnalisis) -> FastAPI:
    """App FastAPI para montar bajo /analisis."""
    app = FastAPI(title="Vigía Digital — Análisis de clips", docs_url=None, redoc_url=None)

    @app.get("/", include_in_schema=False)
    def pagina() -> FileResponse:
        # Sin caché: la página cambia entre ensayos y el navegador la retiene.
        return FileResponse(_HTML, headers={"Cache-Control": "no-store"})

    @app.get("/api/estado")
    def estado() -> dict:
        return controlador.estado()

    @app.post("/api/iniciar")
    def iniciar(pedido: _PedidoInicio) -> dict:
        try:
            controlador.iniciar(pedido.ids)
        except RuntimeError as exc:      # tanda en curso
            raise HTTPException(status_code=409, detail=str(exc))
        except ValueError as exc:        # id desconocido o sin video
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True}

    @app.post("/api/detener")
    def detener() -> dict:
        controlador.detener()
        return {"ok": True}

    @app.post("/api/probar-correo")
    def probar_correo() -> dict:
        # def síncrono: FastAPI lo corre en su pool, la espera no bloquea el servidor.
        return controlador.probar_correo()

    @app.get("/api/imagen/{clip_id}")
    def imagen(clip_id: str) -> Any:
        ruta = controlador.ruta_imagen(clip_id)
        if not ruta or not Path(ruta).exists():
            raise HTTPException(status_code=404, detail="Sin imagen para ese clip")
        return FileResponse(ruta, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    return app
