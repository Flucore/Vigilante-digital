# Estrategia de Segmentación

## Por qué Segmentación

La detección por bounding box dice "hay algo aquí". La segmentación dice "estos píxeles pertenecen a ese objeto". Para seguridad inteligente esto importa porque muchas decisiones dependen de región exacta:

- ¿La persona cruzó una línea?
- ¿La polera es realmente roja o solo hay un cartel rojo detrás?
- ¿La luz cambió o cambió el fondo?
- ¿La persona usa EPP?
- ¿El objeto es arma, herramienta o sombra?

## Segmentación para la Demo

### 1. Segmentación HSV por color

Usada en:

- polera roja,
- semáforo/luz.

Ventajas:

- rápida,
- explicable,
- no requiere entrenamiento,
- ideal para maqueta.

Limitaciones:

- sensible a iluminación,
- falsos positivos con objetos del mismo color,
- requiere ROI o escena controlada.

### 2. Segmentación por ROI

Usada en:

- semáforo,
- zonas de interés,
- perímetro.

Ventajas:

- reduce ruido,
- mejora velocidad,
- fácil de explicar comercialmente.

Limitaciones:

- si la cámara se mueve, hay que recalibrar.

## Segmentación para Piloto

### 3. YOLOv8-seg

Uso propuesto:

- personas,
- vehículos,
- armas,
- EPP,
- objetos abandonados,
- intrusión en zonas.

Ventajas:

- segmenta instancias,
- rápido con GPU,
- entrenable con dataset propio.

Limitaciones:

- necesita anotaciones tipo máscara o polígonos,
- requiere entrenamiento y evaluación.

### 4. Segment Anything Model (SAM/SAM2)

Uso propuesto:

- etiquetado asistido por humano,
- generación inicial de máscaras,
- creación rápida de dataset.

Ventajas:

- acelera anotación,
- funciona con prompts visuales,
- muy útil en fase de dataset.

Limitaciones:

- pesado para inferencia continua,
- no clasifica por sí mismo.

### 5. Segmentación térmica

Uso propuesto:

- altas/bajas temperaturas,
- presencia humana en oscuridad,
- puntos calientes,
- maquinaria anómala.

Técnica:

- umbrales por temperatura,
- blobs térmicos,
- calibración por cámara,
- fusión RGB + térmica si hay doble sensor.

## Recomendación de Ruta

### Demo inmediata

- HSV + ROI.
- YOLOv8-pose para caída.
- Perímetro por línea virtual.

### Piloto 90 días

- YOLOv8-seg para persona/objeto.
- Dataset propio por cliente.
- SAM para asistencia de etiquetado.
- Evaluación por módulo.

### Producto

- Segmentación por instancia para personas/objetos.
- Segmentación térmica para cámaras FLIR/Lepton.
- Fusión de sensores: RGB + térmico + audio + IoT.

## Criterio de Selección

| Caso | Técnica inicial | Técnica final |
|---|---|---|
| Caída | YOLOv8-pose | Modelo entrenado con secuencias |
| Polera roja | HSV + ROI | Segmentación persona + clasificador torso |
| Semáforo/luz | HSV + ROI | Detector de luz + lectura color |
| Perímetro | bbox + línea | máscara persona + geofencing |
| Armas | YOLO detect | YOLOv8-seg custom |
| Temperatura | umbral térmico | fusión térmica + reglas por activo |

