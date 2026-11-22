# Vigía Digital

Experimento comparativo de criterios de detección de caídas de pacientes
mediante visión computacional, para unidades de hospitalización de salud
mental. El sistema procesa video de cámaras IP ya instaladas en un nodo local.

Proyecto de título de Ingeniería en Informática, INACAP 2026.
Equipo: Víctor Bonta, Víctor Sepúlveda, Damián Fierro.

| Campo | Valor |
|---|---|
| Rama de trabajo | `academico` |
| Experimento | [`eval/evaluar.py`](eval/evaluar.py) · especificación en [`eval/ESPECIFICACIONES.md`](eval/ESPECIFICACIONES.md) |
| Punto de entrada del pipeline | `runner.py` |
| Panel de demostración | `demo_panel.py` |
| Demo de aviso por correo | `demo_analisis.py` · guía en [`docs/DEMO_CORREO.md`](docs/DEMO_CORREO.md) |

---

## Pregunta de investigación

> ¿En qué medida un criterio sobre pose con confirmación temporal reduce la
> tasa de falsas alarmas frente a un criterio geométrico instantáneo,
> manteniendo la sensibilidad?

Los dos criterios reciben exactamente la misma entrada: los mismos frames, el
mismo detector de pose (YOLOv8-pose) y el mismo umbral de confianza. Lo único
que cambia es la regla de decisión.

| Criterio | Qué mira | Rol |
|---|---|---|
| `bbox` | Solo la proporción alto/ancho del rectángulo delimitador, frame a frame, sin puntos clave ni ventana temporal | Línea base. Su lógica no se modifica. |
| `pose` con ventana N | Proporción de la caja, inclinación del torso y altura de caderas sobre los puntos clave, y exige N frames consecutivos para confirmar la caída | Método propuesto |

La evaluación estándar corre tres brazos:

| Brazo | Parámetros | Qué aísla |
|---|---|---|
| `bbox` | `--metodo bbox` | Línea base |
| `pose_v1` | `--metodo pose --ventana 1` | Aporte de los puntos clave, sin confirmación temporal |
| `pose_v8` | `--metodo pose --ventana 8` | Método propuesto completo |

`pose_v1` frente a `bbox` mide lo que aportan los puntos clave; `pose_v8`
frente a `pose_v1` mide lo que aporta la ventana temporal.

**Métricas** (un clip es una unidad de evaluación; hay alarma si el brazo
emitió al menos un evento de caída): sensibilidad, especificidad, tasa de
falsos positivos, falsas alarmas por cámara-hora y latencia mediana. Las
definiciones exactas están en [`eval/ESPECIFICACIONES.md`](eval/ESPECIFICACIONES.md) §5.

---

## Conjunto de validación

70 clips de la cámara 0 del [UR Fall Detection Dataset](http://fenix.ur.edu.pl/~mkepski/ds/uf.html):
30 caídas (`fall-XX-cam0`) y 40 actividades de la vida diaria (`adl-XX-cam0`).

Cómo se preparó y etiquetó:

1. **Clips.** `scripts/preparar_clips.py` recorta la mitad RGB de los videos
   compuestos (profundidad + RGB lado a lado) y escala todo a 640×480. Los
   clips resultantes quedan en `data/goldset/` con prefijo `rgb-`.
2. **Etiqueta.** `scripts/generar_labels.py` genera `data/labels.csv` y deduce
   la etiqueta del nombre del archivo: `fall` → `caida`, `adl` → `no_caida`.
3. **Inicio de la caída.** `scripts/anotar_desde_urfall.py` completa
   `inicio_caida_s` a partir de las etiquetas por frame que publica UR Fall
   (`data/urfall-cam0-falls.csv`): toma el primer frame marcado como pose
   transitoria (etiqueta 0) o, si no lo hay, el primer frame en el suelo
   (etiqueta 1), y lo convierte a segundos con los fps del clip. Los 30 clips
   de caída tienen inicio anotado.

```powershell
python scripts/preparar_clips.py data/urfall_original data/goldset
python scripts/generar_labels.py data/goldset data/labels.csv
python scripts/anotar_desde_urfall.py data/urfall-cam0-falls.csv data/labels.csv data/goldset
```

`data/labels.csv` y `data/urfall-cam0-falls.csv` están versionados. Los videos no:
hay que descargarlos de UR Fall y dejarlos en `data/urfall_original/`.

---

## Reproducir el experimento

Con los 70 clips en `data/goldset/`:

```powershell
python -m eval.evaluar --clips data/goldset --labels data/labels.csv --salida eval/resultados
```

Usa por defecto `eval/config_eval.json` (versionado, sin secretos, una cámara
en `fall_detection`) y no `client_config.json`. Aborta si el módulo activo no
es `fall_detection`. La corrida es determinista: los tiempos se miden en
segundos de video, no con el reloj del sistema.

Resultados:

| Archivo | Contenido |
|---|---|
| `eval/resultados/resumen.csv` | Una fila por brazo con VP, FN, FP, VN y todas las métricas |
| `eval/resultados/detalle.csv` | Una fila por clip y brazo, con alarma, segundo de la primera alarma y resultado |

Además se imprime por pantalla una tabla comparativa, con el denominador real
de la tasa por cámara-hora en minutos.

**Barrido de ventanas** (corre `bbox` una vez y un brazo `pose_vN` por valor):

```powershell
python -m eval.evaluar --clips data/goldset --labels data/labels.csv --salida eval/resultados_barrido --ventanas 1,2,3,4,5,6,8,10
```

Si la ventana se elige mirando el barrido, la elección se hizo con los mismos
clips con que se mide: las métricas de esa ventana son exploratorias.

Ambas carpetas de resultados están versionadas como evidencia de la corrida.
Tests del evaluador: `python -m pytest eval`.

---

## Panel de demostración

`demo_panel.py` levanta el panel de operador (`api/operator_panel.py`) y el
pipeline en un mismo proceso: los frames anotados y los eventos de caída
llegan al panel en vivo. Usa `config_demo.json`, con los mismos umbrales de
`eval/config_eval.json`.

```powershell
# Un video (con ventana de OpenCV)
python demo_panel.py --source data/goldset/rgb-fall-01-cam0.mp4

# Varios videos, uno por cámara del config, en bucle
python demo_panel.py --source a.mp4 b.mp4 c.mp4 --loop

# Elegir criterio y ventana
python demo_panel.py --source clip.mp4 --metodo pose --ventana 8
```

Abrir en el navegador: <http://127.0.0.1:8000/operator/>

Otras opciones: `--cam` (cámaras del config, una por video), `--headless`,
`--esperar` (espera Enter antes de procesar), `--host`, `--port`. El panel
escucha solo en `127.0.0.1` por defecto. Requiere `fastapi` y `uvicorn`,
incluidos en `requirements.txt`.

### Aviso por correo

`demo_analisis.py` agrega una página (`/analisis/`) para elegir clips, analizarlos
como una cámara IP y enviar un correo por cada caída (imagen, fecha y hora, ubicación
y PDF). Instalación, credenciales, videos y dónde modificar:
[`docs/DEMO_CORREO.md`](docs/DEMO_CORREO.md).

---

## Instalación

```powershell
git clone https://github.com/Flucore/Vigilante-digital.git
cd Vigilante-digital
py -3.12 -m venv .venv          # Python 3.12: PyTorch no es compatible con 3.13+
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Completar placeholders locales — NUNCA subir .env ni client_config.json real
copy client_config.example.json client_config.json   # plantilla con fall_detection
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

## Fuera de alcance

El entregable es la comparación medida, no un producto. Todo lo que no
contribuye a responder la pregunta de investigación o a mostrarla en la
demostración queda fuera, por dos razones: el tiempo hasta la defensa y el
riesgo de alterar, sin querer, las condiciones bajo las que se midió.

- **No se implementa:** zonas configurables, gestión de usuarios,
  autenticación del panel forense ni persistencia en Postgres. Son
  necesidades de un despliegue real, no del experimento.
- **Congelados hasta después de la defensa:** `runner.py`,
  `core/yolo_fall_detector.py`, `outputs/event_logger.py` y todo `eval/`.
  Cambiarlos invalidaría los resultados ya versionados.
- **El criterio `bbox` no se ajusta:** es la referencia contra la que se
  compara; mejorarlo cambiaría la pregunta.
- **Descartado:** el prototipo `agente/`, ya eliminado del repositorio.
- **Los otros módulos** (`perimeter`, `geofence`, `aqua`) y las integraciones
  opcionales (Firebase, email, reportes PDF) vienen de una etapa anterior del
  proyecto y no forman parte del experimento.
- **Validez:** 70 clips de un solo dataset, grabado con actores y no en
  una unidad de salud mental. La tasa por cámara-hora
  se extrapola desde pocos minutos de video sin caídas.

---

## Seguridad

- Sin credenciales en el repo: claves en variables de entorno (`.env`, no versionado).
- No se versionan videos, modelos `.pt`, `.venv` ni direcciones IP de cámaras (`.gitignore`).
- Ejemplos públicos: `client_config.example.json`, `client_config.aqua.example.json`.

---

## Documentación histórica

Los documentos de [`docs/`](docs/README.md) registran la etapa anterior del
proyecto (plan comercial Dual-Track de FluCore, arquitectura de producto,
compliance, demos). Se conservan como histórico; no describen el alcance
actual. Índice: [docs/README.md](docs/README.md).
