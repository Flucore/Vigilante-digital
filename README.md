# Vigilante Digital (FluCore)

Sistema edge de visión: **criterio de sitio**, no solo “cámaras con IA”.

> Una cámara con IA ve clases universales. Vigilante Digital acumula criterio de este sitio.

| Campo | Valor |
|---|---|
| Repo | [Flucore/Vigilante-digital](https://github.com/Flucore/Vigilante-digital) |
| Versión documental | 3.0 · 2026-08-16 |
| Orquestador | `runner.py` (`main.py` = legado) |
| Track / avance | **C0–C4 Done** · siguiente **C5** (empaque Docker) |
| Protocolo equipo | [docs/PROTOCOLO_GITHUB.md](docs/PROTOCOLO_GITHUB.md) |

---

## Para compañeros (Proyecto de Título + FluCore)

Leer **en este orden** antes de tocar código:

| # | Documento | Para qué |
|---|---|---|
| 1 | [docs/PROTOCOLO_GITHUB.md](docs/PROTOCOLO_GITHUB.md) | Cómo colaborar en GitHub **sin secretos** |
| 2 | [AI_CONTEXT.md](AI_CONTEXT.md) | Contexto permanente + **estado del proyecto** |
| 3 | [MASTER_DEVELOPMENT_PLAN.md](MASTER_DEVELOPMENT_PLAN.md) | Mapa Dual-Track (comercial ↔ académico) |
| 4 | [DESARROLLO_EJECUTABLE.md](DESARROLLO_EJECUTABLE.md) | Sprints C*/A*, DoD y prompts por unidad |
| 5 | [GLOSARIO.md](GLOSARIO.md) | M0–M3, FAR, calibrar ≠ entrenar, antipatrones |
| 6 | [docs/REFORMULACION/01_CHARTER.md](docs/REFORMULACION/01_CHARTER.md) | Charter del producto |
| 7 | [docs/REFORMULACION/04_VISION_COMERCIAL_Y_VENTAS.md](docs/REFORMULACION/04_VISION_COMERCIAL_Y_VENTAS.md) | **Alcance comercial (F1)** |
| 8 | [docs/REFORMULACION/07_PROYECTO_TITULO.md](docs/REFORMULACION/07_PROYECTO_TITULO.md) | **Alcance académico / título (F2)** |
| 9 | [CODE_INDEX.md](CODE_INDEX.md) | Capas, APIs, eventos canónicos |

Paquete completo de reformulación: [docs/REFORMULACION/README.md](docs/REFORMULACION/README.md).

### Alcances (resumen)

| Track | Enfoque | Incluye | No incluye (por defecto) |
|---|---|---|---|
| **F1 Comercial** | Liquidez Verano 2026 | Care / Fall, Perimeter, Aqua (M0 `pool`), empaque edge | Auto-deploy de pesos, Guerrilla |
| **F2 Académico** | Tesis / título | HITL, gold-set, promote, memoria M1–M3 | Mezclar con C1–C6 en la misma sesión |

### Avance actual (tablero)

```text
C0 DOCS ✓ · C1 M0 ✓ · C2 Care ✓ · C3 Perimeter ✓ · C4 Aqua ✓ · C5 Empaque ← siguiente · C6 Tests
```

Detalle vivo: `AI_CONTEXT.md` §6 y `DESARROLLO_EJECUTABLE.md` §1.

---

## Inicio rápido

```powershell
git clone https://github.com/Flucore/Vigilante-digital.git
cd Vigilante-digital
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Completar placeholders locales — NUNCA subir .env ni client_config.json real
copy client_config.example.json client_config.json   # o client_config.aqua.example.json
python runner.py --mode file --source TU_VIDEO.mp4
```

Firebase y email son **opcionales**. Ver `.env.example` y [docs/PROTOCOLO_GITHUB.md](docs/PROTOCOLO_GITHUB.md) §3.

---

## Capas

`inputs/` → `core/` → `outputs/` · `api/` · `scripts/` · `config.py`

---

## Seguridad

- Sin credenciales en el repo.  
- Ejemplos públicos: `client_config.example.json`, `client_config.aqua.example.json`.  
- Videos, fotos, pesos y service accounts quedan fuera de Git (`.gitignore`).

---

## Siguiente acción de desarrollo

```text
TRACK=COMERCIAL · C5
Lee DESARROLLO_EJECUTABLE.md §3 C5 y ejecuta solo esa unidad.
```
