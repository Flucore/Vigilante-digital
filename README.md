# Vigilante Digital (FluCore)

Sistema edge de visión: **criterio de sitio**, no solo “cámaras con IA”.

> Una cámara con IA ve clases universales. Vigilante Digital acumula criterio de este sitio.

| Campo | Valor |
|---|---|
| Repo | [Flucore/Vigilante-digital](https://github.com/Flucore/Vigilante-digital) |
| Versión documental | 3.0 · 2026-08-16 |
| Punto de entrada | `runner.py` |
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
py -3.12 -m venv .venv          # Python 3.12: PyTorch no es compatible con 3.13+
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Completar placeholders locales — NUNCA subir .env ni client_config.json real
copy client_config.example.json client_config.json   # o client_config.aqua.example.json
python runner.py --mode file --source TU_VIDEO.mp4
```

Firebase y email son **opcionales**. Ver `.env.example` y [docs/PROTOCOLO_GITHUB.md](docs/PROTOCOLO_GITHUB.md) §3.

---

## Uso de `runner.py`

```text
python runner.py --mode {realtime,file,batch} [--config RUTA] [--source VIDEO]
                 [--cam ID] [--headless] [--eval]
                 [--modulo {fall_detection,perimeter,geofence,aqua}]
                 [--metodo {bbox,pose}] [--ventana N]
```

| Parámetro | Qué hace | Default |
|---|---|---|
| `--mode` | `realtime` (cámaras del config), `file` (un video con ventana) o `batch` (sin ventana, máxima velocidad) | `realtime` |
| `--config` | JSON de configuración del cliente | `client_config.json` |
| `--source` | Archivo de video; obligatorio en `file` y `batch` | — |
| `--cam` | ID de la cámara del config cuyos módulos se aplican (`file`) | primera habilitada |
| `--headless` | Sin ventana de visualización | desactivado |
| `--eval` | No dispara triggers ni guarda snapshots JPG | desactivado |
| `--modulo` | Módulo a ejecutar; reemplaza `modules_active` de la cámara | el del config |
| `--metodo` | Criterio de caída: `bbox` = proporción de la caja, instantáneo; `pose` = criterio de pose con confirmación temporal | `pose` |
| `--ventana` | Frames consecutivos que exige `pose` para confirmar la caída | `detection.min_fall_frames` del config (8) |

`--modulo`, `--metodo` y `--ventana` solo aplican en los modos `file` y `batch`.
`--metodo` y `--ventana` solo tienen efecto con el módulo `fall_detection`.

Ejemplos:

```powershell
# Video con ventana, configuración por defecto
python runner.py --mode file --source TU_VIDEO.mp4

# Brazo de referencia del experimento: criterio geométrico instantáneo
python runner.py --mode batch --source TU_VIDEO.mp4 --eval --modulo fall_detection --metodo bbox

# Brazo pose con ventana de 8 frames
python runner.py --mode batch --source TU_VIDEO.mp4 --eval --modulo fall_detection --metodo pose --ventana 8

# Cámaras en vivo definidas en el config
python runner.py --mode realtime --config client_config.json
```

Los eventos de `file` y `batch` quedan en `outputs/events_<cam_id>.jsonl`.

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
