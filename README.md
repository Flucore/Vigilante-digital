# Vigilante Digital (FluCore)

Sistema edge de visión: **criterio de sitio**, no solo “cámaras con IA”.

> Una cámara con IA ve clases universales. Vigilante Digital acumula criterio de este sitio.

| Campo | Valor |
|---|---|
| Versión documental | 3.0 · 2026-08-16 |
| Orquestador | `runner.py` (`main.py` = legado) |
| Track activo | **Comercial · C1** |

## Documentos canónicos (leer en este orden)

| # | Documento | Para qué |
|---|---|---|
| 1 | [AI_CONTEXT.md](AI_CONTEXT.md) | Contexto permanente para humanos e IA |
| 2 | [MASTER_DEVELOPMENT_PLAN.md](MASTER_DEVELOPMENT_PLAN.md) | Mapa ejecutivo Dual-Track |
| 3 | [DESARROLLO_EJECUTABLE.md](DESARROLLO_EJECUTABLE.md) | **Sprints, tareas y prompts** (empezar código aquí) |
| 4 | [GLOSARIO.md](GLOSARIO.md) | Términos y anti-patrones |
| 5 | [CODE_INDEX.md](CODE_INDEX.md) | Índice técnico / APIs / capas |
| 6 | [docs/REFORMULACION/](docs/REFORMULACION/README.md) | Charter, auditoría, comercial, arquitectura, título |

## Inicio rápido

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # completar sin commitear secretos
python runner.py --mode file --source TU_VIDEO.mp4
```

Firebase y email son **opcionales**. Ver `.env.example`.

## Dual-Track (resumen)

- **F1 Comercial:** Care · Perimeter · Aqua (M0) · empaque edge — Verano 2026.  
- **F2 Académico:** HITL · gold-set · promote — Proyecto de Título.  
- **No** auto-deploy de pesos ni Guerrilla (biometría / menores / seguridad crítica).

## Capas

`inputs/` → `core/` → `outputs/` · `api/` · `scripts/` · `config.py`

## Siguiente acción de desarrollo

```text
TRACK=COMERCIAL · C1
Lee DESARROLLO_EJECUTABLE.md §3 C1 y ejecuta solo esa unidad.
```
