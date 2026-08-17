# Vigilante Digital — Índice del Código
> Directorio técnico oficial del proyecto. Toda IA o desarrollador debe leer este archivo antes de modificar el sistema.
> Actualizar ante cualquier cambio de interfaz pública, nueva entidad, nuevo endpoint o nuevo módulo.
> Versión: 2.1 · Actualizado: 2026-08-16
> **Companion:** [`GLOSARIO.md`](GLOSARIO.md) · [`DESARROLLO_EJECUTABLE.md`](DESARROLLO_EJECUTABLE.md) · [`AI_CONTEXT.md`](AI_CONTEXT.md) · [`docs/REFORMULACION/`](docs/REFORMULACION/README.md)

---

## 1. Estructura de Directorios

```
VigilanteDigital_1.0/
├── runner.py                   Orquestador principal (realtime | file | batch)
├── config.py                   Valores por defecto con os.getenv() — NO editar directamente
├── client_config.json          Configuración del cliente activo (schema v2.0)
├── .env.example                Variables de entorno requeridas (no incluir credenciales reales)
│
├── core/                       Lógica de detección — NO importar de inputs/ ni outputs/
│   ├── config_loader.py        Cargador jerárquico de config + is_after_hours()
│   ├── detector_factory.py     Factory GPU/CPU: YOLO → MediaPipe
│   ├── yolo_fall_detector.py   Detector de caídas YOLOv8-pose
│   ├── pose_detector.py        Detector MediaPipe (fallback)
│   ├── perimeter_detector.py   Línea virtual de perímetro
│   ├── zone_geometry.py        M0: IoU bbox∩zona + ZoneOccupancyMonitor
│   ├── color_detectors.py      HSV: RedShirtDetector, TrafficLightDetector
│   └── learning_dataset.py     Gestión de dataset para entrenamiento
│
├── inputs/                     Fuentes de video
│   ├── video_stream.py         Stream en vivo (IP / webcam) con reconexión
│   ├── file_reader.py          Archivo MP4/AVI con barra de progreso
│   ├── usb_reader.py           Lector USB
│   ├── esp32_client.py         Cliente ESP32-CAM
│   └── ip_speaker.py           Bocina IP (activación por HTTP)
│
├── outputs/                    Persistencia, alertas y acción
│   ├── event_logger.py         Máquina de estados: frames → eventos canónicos
│   ├── metadata_indexer.py     Indexación de detecciones por frame → JSONL
│   ├── forensic_db.py          Conector PostgreSQL / JSONL fallback
│   ├── forensic_schema.sql     Esquema SQL de la BD forense
│   ├── trigger_manager.py      Dispatcher asíncrono de triggers
│   ├── http_speaker.py         Bocina IP vía HTTP (capa outputs; sin inputs/)
│   ├── firebase_connector.py   Sincronización con Firestore (opcional)
│   ├── hud_renderer.py         Overlays OpenCV sobre frames
│   ├── report_generator.py     Generador de PDF de eventos
│   ├── email_sender.py         Envío SMTP de alertas
│   └── json_logger.py          Logger JSONL legacy (compatibilidad)
│
├── api/                        API REST + UI forense
│   ├── forensic_api.py         FastAPI — endpoints de búsqueda forense
│   └── static/
│       └── forensic_ui.html    Dashboard de búsqueda forense (vanilla JS)
│
├── scripts/                    Scripts de demo, batch y utilitarios
│   ├── demo_2cam.py            Demo 2 cámaras IP con UI split-view
│   ├── batch_processor.py      Pipeline batch: MP4 → ForensicDB
│   ├── run_ipcam.py            Runner de cámara IP simple
│   ├── run_test.py             Script de prueba
│   ├── run_with_devices.py     Runner con dispositivos físicos
│   ├── test_event_storage.py   Test de EventLogger
│   └── add_dataset_image.py    Agregar imágenes al dataset
│
├── tests/                      Tests unitarios
│   └── test_color_detectors.py
│
└── docs/                       Documentación de producto y decisiones
    ├── REFORMULACION/          ★ Canónico Dual-Track + Memoria de Sitio (Ago 2026)
    ├── SEGMENTATION_STRATEGY.md
    ├── PRODUCT_VISION_AND_SCALE.md
    ├── HUMAN_OPERATOR_ROLE.md
    ├── CODE_REVIEW.md
    ├── LEARNING_WORKFLOW.md
    ├── MICROSERVICE_PROMPTS.md   (histórico / no ejecutar tal cual)
    └── TEST_PLAN_DEMO.md
```

---

## 2. Mapa de Módulos por Capa

| Capa | Módulo | Archivo | Responsabilidad |
|------|--------|---------|-----------------|
| Ingesta | `VideoStream` | `inputs/video_stream.py` | Streams vivos con reconexión automática |
| Ingesta | `FileVideoReader` | `inputs/file_reader.py` | Archivos MP4/AVI con progreso visual |
| Inferencia | `YoloFallDetector` | `core/yolo_fall_detector.py` | Detección caídas YOLOv8-pose (GPU) |
| Inferencia | `PoseDetector` | `core/pose_detector.py` | Detección pose MediaPipe (CPU fallback) |
| Inferencia | `RedShirtDetector` | `core/color_detectors.py` | Detección color rojo persistente (HSV) |
| Inferencia | `TrafficLightDetector` | `core/color_detectors.py` | Detección cambio color en ROI (HSV) |
| Inferencia | `PerimeterDetector` | `core/perimeter_detector.py` | Cruce de línea virtual |
| Inferencia | `ZoneOccupancyMonitor` | `core/zone_geometry.py` | M0: IoU bbox ∩ zona + persistencia |
| Lógica | `ConfigLoader` | `core/config_loader.py` | Config jerárquica + evaluación de horario |
| Lógica | `is_after_hours()` | `core/config_loader.py` | Evaluar si es horario no hábil |
| Lógica | `get_detector()` | `core/detector_factory.py` | Factory: elige mejor motor disponible |
| Indexación | `MetadataIndexer` | `outputs/metadata_indexer.py` | JSONL de detecciones por frame |
| Indexación | `ForensicDB` | `outputs/forensic_db.py` | Postgres / JSONL fallback |
| Indexación | `SearchFilters` | `outputs/forensic_db.py` | Dataclass de filtros de búsqueda |
| Acción | `EventLogger` | `outputs/event_logger.py` | frames → eventos canónicos (máquina estados) |
| Acción | `TriggerManager` | `outputs/trigger_manager.py` | Dispatcher asíncrono: email/MQTT/bocina |
| Acción | `ReportGenerator` | `outputs/report_generator.py` | PDF de evento |
| Acción | `EmailSender` | `outputs/email_sender.py` | SMTP con adjunto PDF |
| Acción | `FirebaseConnector` | `outputs/firebase_connector.py` | Sync a Firestore (opcional) |
| Presentación | `draw_hud()` | `outputs/hud_renderer.py` | Barra de estado sobre frame |
| Presentación | `draw_hardware_trigger_overlay()` | `outputs/hud_renderer.py` | Overlay rojo bocina activada |
| Presentación | `draw_no_signal()` | `outputs/hud_renderer.py` | Frame negro "SIN SEÑAL" |
| Presentación | `compose_split_view()` | `outputs/hud_renderer.py` | Componer 2 frames side-by-side |

---

## 3. Directorio de Clases y Funciones Públicas

### `core/config_loader.py`

```python
class ConfigLoader(config_path: Path)
  .get_cameras()                → List[CameraConfig]
  .load_camera_config(cam_id)   → Optional[CameraConfig]
  .get_schedule()               → ScheduleConfig
  .get_section(key, default)    → Any
  .get_client_id()              → str
  .get_schema_version()         → str

def is_after_hours(schedule: ScheduleConfig) → bool

@dataclass CameraConfig:
  id, name, stream_url, zone, sector, enabled,
  modules_active, alert_level_after_hours, zones, raw

@dataclass ScheduleConfig:
  timezone, work_days, start_time, end_time, holidays

@dataclass ZoneConfig:
  id, label, type, critical, points, normalized
  # type M0: polygon|geofence|pool|wall|coop|machine_yard|custom
```

### `core/zone_geometry.py` (C1 · M0 · C4 Aqua)

```python
M0_ZONE_TYPES                    # frozenset de tipos de zona geométrica
AQUA_ZONE_TYPES                  # frozenset({"pool"}) — módulo aqua

def bbox_zone_iou(bbox, zone_points, frame_width, frame_height, *, normalized=True) -> float
def points_to_contour(points, width, height, *, normalized=True) -> np.ndarray
def draw_zones(frame, zones, *, active_zone_ids=None) -> np.ndarray

class ZoneOccupancyMonitor(zones, *, min_iou, min_persistence_frames, cooldown_sec, allowed_types=None)
  .evaluate_frame(bbox, w, h) -> List[ZoneHit]
  .update(bbox, w, h, *, frame_idx, camera_id, site_zone, track_id) -> Optional[dict]
  # evento: zone_occupancy | pool_occupancy · alert_level 1|2 · metadata.product aqua|geofence
  # metadata.demographics=False (Aqua no clasifica edad/niño)
```

---

```python
def get_detector(use_gpu, min_fall_frames, fall_angle_deg, mediapipe_complexity)
  → YoloFallDetector | PoseDetector

def detector_info(detector) → dict
  # {"engine": str, "device": str, "temporal_validation": bool}
```

### Interfaz mínima de todo detector

```python
# Método obligatorio (todos los detectores)
.find_pose(img: np.ndarray, draw: bool) → Tuple[np.ndarray, Any]
.find_position(img, results, draw)       → Tuple[List, Dict]
.close()                                 → None
.__enter__() / .__exit__()              # context manager
```

### `inputs/video_stream.py`

```python
class VideoStream(source, reconnect_attempts, reconnect_delay)
  .open()  → bool
  .read()  → Tuple[bool, Optional[np.ndarray]]
  .close() → None

def create_from_config(source_env) → VideoStream
```

### `inputs/file_reader.py`

```python
class FileVideoReader(source_path, loop, module_name)
  .open()                     → bool
  .read()                     → Tuple[bool, Optional[np.ndarray]]
  .close()                    → None
  .draw_progress(frame)       → np.ndarray
  .get_frame_timestamp_str()  → str          # "HH:MM:SS.ff"
  .get_frame_iso_timestamp()  → str          # ISO 8601 UTC

  @property total_frames, current_frame, fps, progress_ratio, is_finished
```

### `outputs/event_logger.py`

```python
EVENT_SCHEMA_VERSION = "2.0"

def resolve_is_falling(bbox, *, ratio_threshold=0.75) → Tuple[bool, str]
  # Prioriza bbox["is_falling"] del detector; fallback aspect-ratio solo si falta la clave

def enrich_canonical_event(event, *, camera_id, zone, sector, alert_level, photo_path, retention_days) → dict
  # Garantiza timestamp, event_schema_version, compliance, camera_id

class EventLogger(file_path)
  .update(is_falling, frame_idx, photo_path, metadata) → Optional[Dict]  # episodio canónico
  .log_event(event: dict)                              → bool
  .finalize()                                          → Optional[Dict]
  .get_events() / .clear()
```

`runner._dispatch_event_triggers`: PDF opcional + TriggerManager en hilo daemon (no bloquea captura).

### `outputs/metadata_indexer.py`

```python
class MetadataIndexer(output_path, index_every_n_frames, schema_version)
  .index_frame(frame_idx, timestamp, camera_id, detections, frame) → None
  .flush()                                                          → int
  .get_stats()                                                      → Dict
  .close()                                                          → None
```

### `outputs/forensic_db.py`

```python
class ForensicDB(db_url, jsonl_path, events_dir)
  @classmethod .from_env(jsonl_path, events_dir)       → ForensicDB
  .insert_detection(detection: dict)                   → None
  .insert_event(event: dict)                           → None
  .flush()                                             → int
  .search_detections(filters: SearchFilters)           → List[Dict]
  .search_events(filters: SearchFilters)               → List[Dict]
  .export_to_csv(filters, output_path)                 → str
  .export_to_csv_stream(filters)                       → str
  .get_summary_stats()                                 → Dict
  .log_audit_query(endpoint, params, result_count, user_id, user_ip) → None
  .close()                                             → None

@dataclass SearchFilters:
  camera_id, object_class, color_label,
  date_from, date_to, event_type, alert_level_min,
  limit (=100), offset (=0)
```

### `outputs/trigger_manager.py`

```python
class TriggerManager(config)
  .handle_event(event, pdf_path=None) → None   # async, no bloquea
  .shutdown(wait=True) → None
# Bocina: outputs.http_speaker.activate_http_speaker (NO importa inputs/)
# alert_level >= 3 añade ruta speaker automáticamente
```

### `outputs/http_speaker.py`

```python
def activate_http_speaker(host, *, event, volume, mp3_url, timeout_sec) → bool
```

### `outputs/hud_renderer.py`

```python
def draw_hud(frame, cam_name, zone, fps, state, events_count, engine, device, sector) → np.ndarray
def draw_hardware_trigger_overlay(frame, trigger_data, display_seconds, activated_at) → Tuple[np.ndarray, bool]
def draw_no_signal(frame_size, cam_name)                                               → np.ndarray
def compose_split_view(frame_left, frame_right, target_width, target_height)          → np.ndarray
```

### `runner.py` (raíz)

```python
def run_realtime(loader: ConfigLoader, headless: bool) → None
def run_file(loader, source, headless, cam_id_override) → None
def run_batch(loader, source)                           → None
def main()                                              → None
```

---

## 4. Esquema Canónico de Eventos

Todo evento generado por cualquier módulo debe tener esta estructura:

```json
{
  "event_type":          "fall | perimeter_breach | after_hours_motion | vehicle_entry | ...",
  "event_schema_version": "2.0",
  "timestamp":           "2026-05-12T18:00:00+00:00",
  "start_time":          "2026-05-12T17:59:58+00:00",
  "end_time":            "2026-05-12T18:00:00+00:00",
  "duration_seconds":    2.3,
  "camera_id":           "CAM_PATIO_1",
  "zone":                "Patio Trasero",
  "sector":              "Norte",
  "alert_level":         3,
  "photo_path":          "test_outputs/snapshots/CAM_PATIO_1_fall_20260512_180000.jpg",
  "pdf_path":            null,
  "metadata":            { "aspect_ratio": 0.4, "is_falling": true },
  "compliance": {
    "retention_days":  30,
    "consent_basis":   "security_monitoring"
  }
}
```

**Campos obligatorios:** `event_type`, `event_schema_version`, `timestamp`, `camera_id`

### Tipos de evento definidos

| event_type | Módulo | Nivel default |
|---|---|---|
| `fall` | `yolo_fall_detector` / `pose_detector` | 2 |
| `perimeter_breach` | `perimeter_detector` | 1 |
| `zone_occupancy` | `zone_geometry` (M0 geofence) | 2 |
| `pool_occupancy` | `zone_geometry` (type=pool) | 2 |
| `red_shirt_entry` | `color_detectors.RedShirtDetector` | 1 |
| `traffic_light_change` | `color_detectors.TrafficLightDetector` | 1 |
| `after_hours_motion` | (Sprint 3) | 3 |
| `vehicle_entry` | (Sprint 3) | 1 |
| `intrusion` | (Sprint 3) | 2 |

---

## 5. Variables de Entorno

| Variable | Uso | Default | Requerida |
|---|---|---|---|
| `AUDIT_DB_URL` | URL PostgreSQL para ForensicDB | `""` (modo JSONL) | No |
| `SMTP_USER` | Email remitente (referenciado en config JSON) | — | En prod |
| `SMTP_PASSWORD` | Contraseña SMTP | — | En prod |
| `SMTP_HOST` | Servidor SMTP | — | En prod |
| `SMTP_PORT` | Puerto SMTP | `587` | No |
| `MQTT_BROKER_HOST` | Broker MQTT para bocina/relay | — | Si usa hardware |
| `CAM_PATIO_1_URL` | URL stream cámara patio norte | `0` (webcam) | En despliegue |
| `CAM_PATIO_2_URL` | URL stream cámara patio sur | `0` | En despliegue |
| `CAM_ENTRADA_AUTOS_URL` | URL stream entrada autos | `0` | En despliegue |
| `CAM_PERIMETRO_URL` | URL stream perímetro | `0` | En despliegue |
| `ZONE_MIN_IOU` | IoU mínimo bbox∩zona (M0) | `0.15` | No |
| `ZONE_MIN_PERSISTENCE_FRAMES` | Frames consecutivos para evento M0 | `8` | No |
| `ZONE_EVENT_COOLDOWN_SEC` | Cooldown entre eventos misma zona | `5.0` | No |
| `DATA_RETENTION_DAYS` | Retención compliance en eventos | `30` | No |
| `CAM_PEATONAL_URL` | URL stream entrada peatonal | `0` | En despliegue |
| `CAM_POSTE_URL` | URL stream poste general | `0` | En despliegue |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path al JSON de Firebase | — | Solo si Firebase habilitado |
| `FIRESTORE_COLLECTION` | Colección Firestore | `Prueba_Alertas` | No |
| `EVENT_LOG_PATH` | Path del JSONL de eventos | `outputs/events_log.jsonl` | No |
| `SYNC_INTERVAL` | Intervalo sync Firebase (seg) | `10` | No |
| `HEADLESS_MODE` | Sin ventana OpenCV | `false` | En servidores |
| `VIDEO_SOURCE` | Fuente de video legacy | `0` | No |
| `VIGILANTE_CONFIG` | Path al client_config.json para la API | `client_config.json` | No |
| `API_PORT` | Puerto del servidor FastAPI | `8000` | No |

---

## 6. Claves de `client_config.json` (schema v2.0)

| Clave | Tipo | Descripción |
|---|---|---|
| `_schema_version` | str | Versión del esquema (requerida: "2.0") |
| `_client_id` | str | Identificador único del cliente |
| `_client_name` | str | Nombre del cliente |
| `schedule.timezone` | str | TZ string IANA (ej: "America/Santiago") |
| `schedule.work_days` | list[int] | Días laborales (0=Lunes, 6=Domingo) |
| `schedule.start_time` | str | Hora inicio jornada "HH:MM" |
| `schedule.end_time` | str | Hora fin jornada "HH:MM" |
| `schedule.holidays` | list[str] | Feriados "YYYY-MM-DD" |
| `alerts.email_sender_env` | str | Nombre de env var para email remitente |
| `alerts.recipients` | list[str] | Destinatarios de alertas |
| `alerts.horn_mqtt_topic` | str | Topic MQTT para bocina |
| `detection.use_gpu` | bool | Usar GPU/CUDA |
| `detection.engine` | str | "auto" \| "yolo" \| "mediapipe" |
| `detection.min_fall_frames` | int | Frames para confirmar caída |
| `cameras[].id` | str | ID único de cámara |
| `cameras[].stream_url_env` | str | Nombre de env var para URL |
| `cameras[].stream_url` | str | URL fallback (solo dev) |
| `cameras[].modules_active` | list[str] | Módulos activos en esta cámara |
| `cameras[].alert_level_after_hours` | int | 1=log, 2=notify, 3=bocina |
| `cameras[].zones[].critical` | bool | Si es zona crítica (dispara nivel 3) |
| `cameras[].zones[].points` | list[list[int]] | Polígono [x,y] |
| `cameras[].perimeter_line` | dict | `{start:[x,y], end:[x,y], label, cooldown_sec}` |
| `triggers.enabled` | bool | Activar/desactivar todos los triggers |
| `triggers.routes_by_event` | dict | Rutas por tipo de evento |
| `forensic_audit.enabled` | bool | Activar indexación de metadatos |
| `forensic_audit.db_url_env` | str | Nombre de env var para URL de BD |
| `forensic_audit.index_every_n_frames` | int | Frecuencia de indexación |
| `forensic_audit.output_jsonl` | str | Path del JSONL de metadatos |
| `firebase.enabled` | bool | Usar Firestore (opcional) |

---

## 7. Mapa de Triggers

```
Detección confirmada (EventLogger)
        │
        ▼
runner.py / CameraWorker
        │
        ├─► is_after_hours() == True AND alert_level >= 3
        │       └─► draw_hardware_trigger_overlay() [HUD visual]
        │       └─► TriggerManager → MQTT (bocina/relay)
        │
        ├─► alert_level == 2
        │       └─► TriggerManager → Email (PDF adjunto)
        │
        └─► alert_level == 1 (siempre)
                └─► EventLogger.log_event() → JSONL local
                └─► MetadataIndexer.index_frame() → metadata_index.jsonl
                └─► ForensicDB.insert_detection() → PostgreSQL (si configurado)
                └─► FirebaseConnector.sync_new_events() → Firestore (si configurado)
```

### Rutas de trigger en `TriggerManager`

| Ruta | Clase | Activación |
|---|---|---|
| `email` | `EmailSender` | SMTP con PDF adjunto |
| `speaker` | `outputs.http_speaker` | HTTP POST a bocina IP (capa outputs) |
| `mqtt` | requests | Mensaje MQTT al relay |
| `webhook` | requests | HTTP POST a URL configurada |
| `whatsapp` | requests | Webhook externo (Twilio, etc.) |

---

## 8. Endpoints de la API Forense

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/` | UI de búsqueda forense |
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/search` | Buscar detecciones (filters: camera_id, object_class, color, from, to, limit, offset) |
| GET | `/api/v1/events` | Buscar eventos (filters: camera_id, event_type, from, to, alert_level, limit) |
| GET | `/api/v1/export/csv` | Descargar detecciones en CSV |
| GET | `/api/v1/stats/summary` | Estadísticas generales |
| POST | `/api/v1/audit/log` | Registro manual de consulta |

**Iniciar API:**
```bash
uvicorn api.forensic_api:app --reload --port 8000
```

---

## 9. Esquema de la Base de Datos Forense

### Tablas

| Tabla | Descripción | PK |
|---|---|---|
| `cameras` | Registro de cámaras | `id TEXT` |
| `detections` | Detecciones por frame (serie temporal) | `(id UUID, timestamp TIMESTAMPTZ)` |
| `events` | Eventos de seguridad confirmados | `id UUID` |
| `audit_queries` | Cadena de custodia de consultas | `id UUID` |

### Columnas clave de `detections`

`camera_id · timestamp · frame_idx · object_class · confidence · bbox_xmin/ymin/xmax/ymax · color_label · track_id · metadata JSONB`

### Vistas

| Vista | Descripción |
|---|---|
| `recent_events_summary` | Eventos recientes con datos de cámara (JOIN) |
| `detections_summary_by_class` | Conteos última hora por clase y color |

---

## 10. Tipos y Entidades (Dataclasses)

```python
# core/config_loader.py
CameraConfig(id, name, stream_url, zone, sector, enabled, modules_active,
             alert_level_after_hours, zones: List[ZoneConfig], raw: dict)

ScheduleConfig(timezone, work_days, start_time, end_time, holidays)

ZoneConfig(id, label, type, critical, points)

# outputs/forensic_db.py
SearchFilters(camera_id, object_class, color_label, date_from, date_to,
              event_type, alert_level_min, limit=100, offset=0)

# core/color_detectors.py
ColorDetection(detected: bool, confidence: float, event: Optional[dict])
```

### 10.1 Entidades Memoria de Sitio

| Entidad | Estado | Implementación |
|---|---|---|
| `SiteZoneMask` | **Parcial (C1)** | `ZoneConfig` + `core/zone_geometry.py` |
| `CuriositySample` | Conceptual | Dataset / cola HITL (A1) |
| `TaxonomyLabel` | Conceptual | M2 (A3) |
| `ModelCard` / `GoldSet` | Conceptual | A2–A4 |
| `CompositeEventRecipe` | Conceptual | A5 |

**Módulo activo M0:** `geofence` o `aqua` en `modules_active`.  
**Eventos:** `zone_occupancy`, `pool_occupancy` (si `type=pool`; Notify `alert_level=2`).
**Aqua (C4):** `allowed_types=pool` — 0 eventos fuera de agua; sin demografía.

---

## 11. Módulos Activos en `modules_active` (client_config.json)

| Valor | Módulo activado | Sprint |
|---|---|---|
| `fall_detection` | YoloFallDetector / PoseDetector | S0 |
| `perimeter` | PerimeterDetector (línea virtual) | S0 |
| `geofence` | ZoneOccupancyMonitor (M0 IoU bbox∩zona) | **C1** |
| `aqua` | ZoneOccupancyMonitor solo `type=pool` + Notify | **C4** |
| `red_shirt` | RedShirtDetector (HSV) | S0 |
| `traffic_light` | TrafficLightDetector (HSV) | S0 |
| `metadata_indexer` | MetadataIndexer (siempre activo si forensic_audit.enabled) | S1 |
| `vehicle_detection` | VehicleDetector (línea + polígono) | **S3** |
| `instance_segmentation` | SegmentationDetector (YOLOv8-seg) | **S3** |
| `semantic_segmentation` | SegmentationDetector (modo semántico) | **S3** |
| `motion_detection` | MotionDetector (MOG2 + reglas horario) | **S3** |
| `face_capture` | Frame HD al detectar persona (solo demo) | **S3** |

---

## 12. Convenciones de Nomenclatura

| Elemento | Convención | Ejemplo |
|---|---|---|
| Clases | PascalCase | `MetadataIndexer`, `ForensicDB` |
| Funciones públicas | snake_case | `is_after_hours()`, `search_detections()` |
| Variables privadas | `_snake_case` | `_insert_buffer`, `_mode` |
| Constantes | UPPER_SNAKE | `_BATCH_SIZE`, `_REQUIRED_KEYS` |
| IDs de cámara | UPPER_SNAKE | `CAM_PATIO_1`, `CAM_ENTRADA_AUTOS` |
| Tipos de evento | snake_case | `fall`, `perimeter_breach` |
| Variables de entorno | UPPER_SNAKE | `AUDIT_DB_URL`, `CAM_PATIO_1_URL` |
| Archivos de módulo | snake_case | `forensic_db.py`, `config_loader.py` |
| Timestamps | ISO 8601 UTC | `2026-05-12T18:00:00+00:00` |

---

## 13. Glosario de Términos del Dominio

| Término | Definición |
|---|---|
| **Detección** | Identificación de un objeto en un frame: clase + bbox + confidence |
| **Evento** | Secuencia de frames confirmada como incidente (inicio → fin) |
| **Frame** | Imagen individual extraída del stream de video |
| **BBox** | Bounding box: rectángulo delimitador del objeto detectado |
| **HUD** | Heads-Up Display: overlays informativos sobre el frame |
| **Trigger** | Acción activada por un evento (email, bocina, webhook, MQTT) |
| **Perímetro** | Línea o polígono virtual que delimita una zona de seguridad |
| **Horario no hábil** | Período fuera del rango laboral configurado en `schedule` |
| **Nivel de alerta** | 1=silencioso, 2=notificación, 3=crítico con bocina |
| **Zona crítica** | Zona marcada como `critical:true` que activa el nivel 3 |
| **MetadataIndexer** | Componente que extrae y persiste metadatos de detección por frame |
| **ForensicDB** | Capa de persistencia forense; opera en modo postgres o jsonl |
| **Auditoría forense** | Capacidad de buscar en el índice histórico sin revisar video |
| **Transfer Learning** | Ajuste fino de un modelo preentrenado con datos del cliente |
| **Edge node** | Instancia del sistema corriendo en hardware del cliente |
| **Hub / Cerebro** | Servidor centralizado (ej: Curicó) que agrega múltiples sitios |
| **ONVIF** | Protocolo estándar para cámaras IP (descubrimiento, PTZ, streams) |
| **RTSP** | Protocolo de streaming de video en tiempo real |
| **Pipeline batch** | Procesamiento de video histórico sin interfaz gráfica, máxima velocidad |
| **Cadena de custodia** | Registro de quién accedió a qué evidencia y cuándo (ISO 27001) |
| **schema_version** | Campo en eventos y detecciones para migración progresiva de datos |
| **Criterio de Sitio** | SKU: M0+M1+HITL+(opc)M2/M3 — ver `docs/REFORMULACION/03_GLOSARIO.md` |
| **M0–M3** | Memorias geométrica / percepción / taxonomía / conductual |
| **FAR** | Falsas alarmas por cámara-hora (métrica de negocio) |
| **Calibrar ≠ Entrenar** | Zona/máscara ≠ pesos `.pt` |
| **runner.py** | Orquestador **canónico**; `main.py` es legado |

---

## 14. Reglas de Importación (inamovibles)

```
runner.py → puede importar de: core/ · inputs/ · outputs/ · config.py
core/     → NO importa de inputs/ ni outputs/
inputs/   → NO importa de outputs/
outputs/  → NO importa de inputs/
config.py → NO importa de ningún módulo del proyecto
api/      → puede importar de: core/ · outputs/ · config.py
scripts/  → puede importar de todo (son orquestadores)
```

---

## 15. Comandos de Uso Rápido

```bash
# Demo con archivo de video
python runner.py --mode file --source video_demo.mp4

# Demo en tiempo real (webcam)
python runner.py --mode realtime

# Procesar video histórico (sin UI)
python runner.py --mode batch --source grabacion.mp4

# Pipeline batch completo → ForensicDB
python scripts/batch_processor.py --source grabaciones/

# Iniciar API forense
uvicorn api.forensic_api:app --reload --port 8000

# Demo 2 cámaras (modo legacy compatible)
python scripts/demo_2cam.py --config demo_config.json

# Aplicar esquema SQL
psql -U postgres -d vigilante -f outputs/forensic_schema.sql
```

---

*Mantener este índice actualizado es responsabilidad del desarrollador que modifica cualquier interfaz pública.*
*Para agentes IA: leer este archivo completo antes de cualquier modificación estructural.*
