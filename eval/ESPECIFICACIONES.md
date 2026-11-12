# Especificación: script de evaluación comparativa

Objetivo: medir y comparar dos métodos de detección de caídas sobre el
mismo conjunto de clips etiquetados, y producir una tabla de resultados
reproducible.

Este script es el entregable central del proyecto de título. Todo lo que
no esté aquí queda fuera.

## Alcance del cambio

Se permite modificar:
- `runner.py` (selección de método y tiempos por frame)
- `core/yolo_fall_detector.py` (solo lo necesario para exponer el método)
- `outputs/event_logger.py` (solo tiempos por frame)
- Archivos nuevos dentro de `eval/`

NO modificar:
- La lógica de decisión del criterio geométrico de pose
- La lógica de `resolve_is_falling`
- Nada de `inputs/`, salvo exponer los fps si no están accesibles

No refactorizar, no renombrar, no reorganizar carpetas. Cambios chicos.

## 1. Arreglo previo: tiempos por frame

Hoy los eventos se marcan con `datetime.now()`. Eso mide tiempo de
procesamiento, no tiempo de video, y hace que las latencias no se puedan
comparar con las etiquetas.

Cambiar todo timestamp de evento por tiempo de video:

    tiempo_s = indice_frame / fps

El `fps` viene de `FileVideoReader` (`reader.fps`), que ya se lee pero no
se usa. Si un video no reporta fps, usar 30 y registrar una advertencia.

El reloj del sistema puede seguir usándose para logs operativos, nunca
para los tiempos de los eventos detectados.

## 2. Selección de método

Agregar al runner un parámetro `--metodo` con dos valores:

**`bbox`** — línea base. Criterio geométrico instantáneo sobre el
rectángulo delimitador: solo la proporción alto/ancho de la caja, sin
puntos clave y sin ventana temporal. Es la lógica que ya existe en
`resolve_is_falling` (`outputs/event_logger.py:23`). Hoy solo se usa con
MediaPipe; hay que poder seleccionarla con YOLO.

**`pose`** — método propuesto. El criterio actual de
`core/yolo_fall_detector.py` (proporción de caja, inclinación del torso,
altura de caderas) más la confirmación por ventana de 8 frames
consecutivos.

Ambos métodos reciben exactamente la misma entrada: los mismos frames,
el mismo detector de pose, el mismo umbral de confianza. Lo único que
cambia es el criterio de decisión.

**`--ventana N`** — número de frames consecutivos que exige el criterio
`pose` para confirmar una caída (default 8). No cambia la lógica de
decisión, solo ese número. No tiene efecto con `bbox`.

### Brazos del experimento

La evaluación corre tres brazos:

| Brazo | Parámetros | Qué aísla |
|---|---|---|
| `bbox` | `--metodo bbox` | línea base: solo proporción de la caja |
| `pose_v1` | `--metodo pose --ventana 1` | aporte del criterio de pose sin confirmación temporal |
| `pose_v8` | `--metodo pose --ventana 8` | método propuesto completo |

`pose_v1` frente a `bbox` mide lo que aportan los puntos clave;
`pose_v8` frente a `pose_v1` mide lo que aporta la ventana temporal.

## 3. Formato de etiquetas

Archivo `data/labels.csv`, codificación UTF-8:

    archivo,etiqueta,inicio_caida_s,escenario,locacion
    caida_frontal_01.mp4,caida,3.4,caida frontal,pasillo
    sentarse_suelo_01.mp4,no_caida,,sentarse en el suelo,sala

- `archivo`: nombre del clip dentro de `data/goldset/`
- `etiqueta`: `caida` o `no_caida`
- `inicio_caida_s`: segundos desde el inicio del clip hasta que comienza
  la caída. Solo para `caida`. Puede ir vacío: en ese caso ese clip no
  aporta a la latencia.
- `escenario` y `locacion`: descriptivos, para el análisis por categoría

El script debe fallar con un mensaje claro si un archivo listado no
existe, o si un clip de la carpeta no está listado.

## 4. Qué hace el script

Archivo nuevo: `eval/evaluar.py`

Uso:

    python -m eval.evaluar --clips data/goldset --labels data/labels.csv --salida eval/resultados

### Configuración y módulo activo

El runner toma el módulo de la cámara del config (`modules_active[0]`).
Si el módulo no es `fall_detection`, la lógica de caídas nunca se ejecuta
y los eventos que salen son de otro tipo (`zone_occupancy`,
`pool_occupancy`, etc.), sin ningún error. Para evitarlo:

- El script usa por defecto `eval/config_eval.json` (versionado, sin
  secretos, una cámara en `fall_detection`, sin triggers). Nunca el
  `client_config.json` local, que no está en el repositorio y depende
  de la máquina.
- Antes de procesar el primer clip, el script verifica que el módulo
  activo de la cámara usada sea `fall_detection`. Si no lo es, aborta
  la corrida completa (no clip por clip) con un mensaje claro, por
  ejemplo: `Módulo activo 'geofence' en cámara CAM_GEOFENCE de
  client_config.json; la evaluación exige fall_detection.`
- Además, al procesar, el script descarta y reporta como error
  cualquier evento cuyo `event_type` no sea `fall`.

Para cada brazo (`bbox`, `pose_v1`, `pose_v8`; ver sección 2) y cada clip:

1. Procesa el clip completo con ese brazo
2. Registra si hubo alarma y en qué segundo de video ocurrió la primera
3. Registra la duración del clip en segundos de video

Un clip cuenta como alarma si el brazo emitió al menos un evento de
caída durante el clip. No importa cuántos.

## 5. Métricas

Definiciones exactas. Un clip es una unidad de evaluación.

- **VP**: clip etiquetado `caida` con alarma
- **FN**: clip etiquetado `caida` sin alarma
- **FP**: clip etiquetado `no_caida` con alarma
- **VN**: clip etiquetado `no_caida` sin alarma

Calcular por brazo:

    Sensibilidad      = VP / (VP + FN)
    Especificidad     = VN / (VN + FP)
    Tasa de falsos positivos = FP / (VN + FP)

    Falsas alarmas por cámara-hora
        = total de alarmas en clips no_caida
        / (suma de duración de clips no_caida, en horas)

    Latencia mediana
        = mediana de (segundo de la primera alarma - inicio_caida_s)
          sobre los clips caida que tienen inicio_caida_s y dieron alarma

Todas las tasas con dos decimales. Latencia en segundos con un decimal.

**Importante:** junto a la tasa por cámara-hora el script debe imprimir
el denominador real en minutos, por ejemplo `(denominador: 4,2 min)`.
Con pocos clips esa tasa es una extrapolación y tiene que verse.

## 6. Salidas

**`eval/resultados/detalle.csv`** — una fila por clip y por brazo:

    brazo,metodo,ventana,archivo,etiqueta,escenario,alarma,segundo_alarma,duracion_s,resultado

donde `brazo` es `bbox`, `pose_v1` o `pose_v8`; `ventana` va vacía para
`bbox`; y `resultado` es `VP`, `FN`, `FP` o `VN`.

**`eval/resultados/resumen.csv`** — una fila por brazo (con `metodo` y
`ventana`), con todas las métricas de la sección 5, más VP, FN, FP, VN
y el total de clips.

**Salida por pantalla** — una tabla comparativa legible de los tres
brazos, lado a lado.

Ambos CSV se versionan en el repositorio: son la evidencia de que el
experimento se corrió.

## 7. Requisitos de ejecución

- Determinista: dos corridas sobre los mismos clips dan el mismo
  resultado
- Reejecutable: si se agregan clips, se vuelve a correr el mismo comando
- No depende de la máquina: nada de rutas absolutas ni de `datetime.now()`
- Si un clip falla al procesarse, lo reporta y sigue con los demás, sin
  abortar la corrida