# Revisión Técnica del Código

## Estado General

El proyecto ya tiene una arquitectura correcta para escalar: `inputs/`, `core/`, `outputs/` y `scripts/`. La separación permite agregar módulos de visión sin reescribir el demo. La fase anterior dejó un demo de 2 cámaras, YOLOv8-pose, perímetro y HUD.

Esta revisión incorpora la siguiente capa: módulos configurables de visión, triggers y preparación para aprendizaje supervisado.

## Hallazgos Críticos Corregidos

### 1. `main.py` usaba un método inexistente

`FirebaseConnector` no tiene `log_event()`. El flujo correcto es:

1. `EventLogger.log_event(event)`
2. `FirebaseConnector.sync_new_events()`

Estado: corregido.

### 2. `FirebaseConnector` no entendía eventos de `EventLogger`

`EventLogger` genera `start_time`, mientras el conector buscaba `timestamp`. Ahora normaliza `timestamp = start_time` si no existe.

Estado: corregido.

### 3. `demo_2cam.py` mezclaba visión y acciones

La detección ahora produce eventos. `TriggerManager` ejecuta acciones externas: email, WhatsApp/webhook y bocina.

Estado: corregido.

## Riesgos Actuales

### YOLOv8-pose puede ser pesado para múltiples cámaras

Para 2 cámaras en PC gamer con GPU está bien. Para 8+ cámaras se necesitará:

- microservicio de inferencia centralizado,
- batching,
- colas por cámara,
- degradación por prioridad,
- detección por movimiento antes de IA pesada.

### Red shirt detector usa segmentación por color

Funciona para maqueta controlada, pero puede fallar con:

- luz roja ambiental,
- carteles rojos,
- ropa parcialmente visible,
- cámaras con balance de blancos distinto.

Para producción debe evolucionar a:

- segmentación de persona + clasificación de torso,
- modelo YOLO/CLIP entrenado con dataset propio,
- calibración de color por cámara.

### Traffic light detector depende de ROI bien configurada

Funciona si el semáforo/luz está fijo dentro de una región. Para producción:

- detectar primero objeto "semáforo",
- leer color dentro de la máscara/ROI del objeto,
- registrar cambio de estado con timestamp.

### Triggers externos deben desacoplarse

`TriggerManager` es suficiente para maqueta. Para producción debe convertirse en microservicio de notificación con cola, reintentos y auditoría.

## Recomendaciones Técnicas

1. Mantener `scripts/demo_2cam.py` como orquestador de demo, no como producto final.
2. Crear un `vigilante-agent` por cámara y un `event-bus` central.
3. Convertir triggers en servicios independientes: `notification-service`, `speaker-service`, `report-service`.
4. Agregar `dataset-service` para cargar imágenes y etiquetas.
5. Medir cada demo con métricas: latencia, FPS, falsos positivos, falsos negativos.

## Estado de Archivos Nuevos

- `core/color_detectors.py`: polera roja y semáforo por HSV.
- `core/learning_dataset.py`: base para dataset human-in-the-loop.
- `outputs/trigger_manager.py`: email, WhatsApp/webhook, speaker.
- `tests/test_color_detectors.py`: pruebas sintéticas de color.
- `demo_config.json`: nuevos módulos y triggers.

