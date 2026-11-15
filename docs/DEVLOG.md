# DEVLOG — Bitácora Técnica del Código
## Vigilante Digital v2.0

> **Propósito**: Registro cronológico de desarrollos, conversiones, errores y arreglos.
> Cada entrada debe incluir: fecha, autor/agente, tipo de cambio, archivos afectados y descripción.
>
> **Formato de entrada**:
> ```
> ## [YYYY-MM-DD] TIPO: Título breve
> ```
> **Tipos**: `FEAT` (nueva funcionalidad) · `FIX` (corrección) · `REFACTOR` · `ARCH` (arquitectura) · `ERROR` · `DEPS` (dependencias) · `DOCS`

---

## Índice de Sprints

| Sprint | Objetivo | Estado |
|--------|----------|--------|
| S0 | Detección de caídas MVP + Reportes PDF | ✅ Completado |
| S1 | Runner unificado + Config jerárquica + MetadataIndexer | ✅ Completado |
| S2 | ForensicDB + API REST + UI Forense + CODE_INDEX | ✅ Completado |
| S3 | Segmentación + Intrusión + Vehículos + Motion + Transfer Learning | ✅ Completado |
| S4 | Integraciones avanzadas (MQTT, ONVIF, WhatsApp) | 🔜 Pendiente |

---

## [2026-04-XX] ARCH: Redefinición estratégica del proyecto

**Tipo**: ARCH  
**Autor**: Damián Fierro + AI Agent  
**Archivos afectados**: (conceptual — no hay archivos de código)

### Contexto
El proyecto evoluciona de un script de detección de caídas a una **plataforma modular de vigilancia industrial**. La idea fuerza cambia a: *"Convertir video en data auditable en vivo y cuando se necesite"*.

### Decisiones tomadas
- Arquitectura de capas: `inputs → core → outputs → api → scripts`
- Diferenciador técnico: **Módulo de Auditoría Forense** (video → BD searchable)
- Configuración jerárquica: `.env > client_config.json > config.py`
- Target hardware: servidores NVIDIA/CUDA industriales (sin optimizaciones consumer)
- Formato de BD: PostgreSQL / TimescaleDB (JSONL como fallback offline)

### Documentos generados
- `MASTER_DEVELOPMENT_PLAN.md` — blueprint completo con prompts de sprint
- `ANALYSIS.md` — análisis de código previo
- `EXECUTIVE_SUMMARY.md` — resumen ejecutivo para presentaciones

---

## [2026-05-XX] FEAT S1: Runner unificado (runner.py)

**Tipo**: FEAT  
**Autor**: AI Agent  
**Archivos creados**: `runner.py`, `core/config_loader.py`, `inputs/file_reader.py`, `outputs/metadata_indexer.py`, `client_config.json`

### Descripción
Reemplaza el disperso `main.py` + `demo_2cam.py` con un único orquestador que soporta tres modos de operación:

| Modo | Comando | Uso |
|------|---------|-----|
| `realtime` | `python runner.py --mode realtime` | Vigilancia activa en vivo |
| `file` | `python runner.py --mode file --source video.mp4` | Demo + pruebas |
| `batch` | `python runner.py --mode batch --source carpeta/` | Procesamiento histórico |

### Nuevos módulos
- **`core/config_loader.py`**: Carga jerárquica de configuración. Incluye `is_after_hours()` con soporte a zonas horarias (`zoneinfo`).
- **`inputs/file_reader.py`**: Interfaz `VideoStream`-compatible para archivos MP4/AVI con barra de progreso visual.
- **`outputs/metadata_indexer.py`**: Persistencia atómica de metadatos por frame (clase, bbox, color, confianza) a JSONL.
- **`client_config.json`**: Archivo maestro de configuración del cliente "Casa 6 Cámaras" con todas las zonas y módulos configurados.

### Patrón de configuración establecido
```json
{
  "schedule": { "work_days": [0,1,2,3,4], "start_time": "08:00", "end_time": "17:00" },
  "cameras": [{ "id": "cam_01", "stream_url": { "_env": "CAM_01_URL" }, "modules_active": [...] }]
}
```

---

## [2026-05-XX] FEAT S1: HUD overlay de hardware trigger

**Tipo**: FEAT  
**Autor**: AI Agent  
**Archivos afectados**: `outputs/hud_renderer.py`

### Descripción
Agregada función `draw_hardware_trigger_overlay()` para demostrar activación de hardware (bocina/relay) sin requerir hardware físico. Muestra overlay rojo parpadeante con texto "HARDWARE TRIGGER: SIRENA ACTIVADA" durante N segundos configurables.

### Parámetros
```python
draw_hardware_trigger_overlay(
    frame, trigger_data, display_seconds=3.0, activated_at=None
) -> Tuple[np.ndarray, bool]
```

---

## [2026-05-XX] FEAT S2: Módulo de Auditoría Forense

**Tipo**: FEAT  
**Autor**: AI Agent  
**Archivos creados**: `outputs/forensic_schema.sql`, `outputs/forensic_db.py`, `scripts/batch_processor.py`, `api/__init__.py`, `api/forensic_api.py`, `api/static/forensic_ui.html`

### Descripción
Implementación completa del **Módulo de Auditoría Forense**, el diferenciador técnico central del producto.

#### `outputs/forensic_schema.sql`
Schema PostgreSQL con tablas:
- `cameras` — registro de cámaras del cliente
- `detections` — cada objeto detectado con clase, bbox, color, confianza
- `events` — eventos de alto nivel (caída, intrusión, etc.)
- `audit_queries` — historial de búsquedas (trazabilidad ISO 27001)
- Vistas: `recent_events_summary`, `detections_summary_by_class`
- Compatible con TimescaleDB (hypertable comentado)

#### `outputs/forensic_db.py`
Conector dual PostgreSQL / JSONL:
- `ForensicDB.from_env()` — lee `DATABASE_URL` del entorno
- `insert_detection()` — batch con flush automático
- `search_detections(filters)` — búsqueda multi-criterio
- `export_to_csv()` — exportación para análisis externo
- `log_audit_query()` — trazabilidad de accesos (compliance)

#### `api/forensic_api.py`
FastAPI app con endpoints:
```
GET  /api/v1/health
POST /api/v1/search        — buscar detecciones
GET  /api/v1/events        — listar eventos
GET  /api/v1/export/csv    — exportar resultados
GET  /api/v1/stats/summary — estadísticas generales
POST /api/v1/audit/log     — registrar consulta
```

#### `api/static/forensic_ui.html`
Dashboard web (dark theme) con:
- Stats en tiempo real (total detecciones, eventos, cámaras activas)
- Filtros de búsqueda: cámara, clase, color, fecha, confianza
- Tabs: Detecciones | Eventos
- Tabla de resultados paginada

---

## [2026-05-XX] DOCS S2: CODE_INDEX.md + Cursor Rule 05

**Tipo**: DOCS  
**Autor**: AI Agent  
**Archivos creados**: `CODE_INDEX.md`, `.cursor/rules/05-code-index.mdc`

### Descripción
Documentación técnica completa del codebase con 15 secciones:
estructura de directorios, mapa de módulos, firmas públicas, schema de eventos canónicos, variables de entorno, claves de configuración, endpoints API, schema de BD, glosario de dominio.

Cursor Rule `05-code-index.mdc` obliga a leer y actualizar `CODE_INDEX.md` ante cualquier cambio estructural.

---

## [2026-05-12] ERROR: uvicorn no reconocido en PowerShell

**Tipo**: ERROR → FIX  
**Entorno**: Windows 10, PowerShell, Python 3.12 (user install)  
**Archivos afectados**: ninguno (problema de entorno)

### Error reportado
```
uvicorn : El término 'uvicorn' no se reconoce como nombre de un cmdlet,
función, archivo de script o programa ejecutable.
```

### Causa raíz
`pip install` en modo "user installation" instala scripts en:
```
C:\ruta\Scripts\Python
```
Este directorio **no está en el PATH del sistema** por defecto en Windows.

### Solución aplicada
Usar el módulo Python directamente en lugar del script ejecutable:
```powershell
# ❌ No funciona (script no en PATH)
uvicorn api.forensic_api:app --reload --port 8000

# ✅ Correcto (invoca via módulo Python)
python -m uvicorn api.forensic_api:app --port 8000 --host 0.0.0.0
```

### Solución permanente (opcional)
Agregar el directorio al PATH del sistema:
```powershell
$env:PATH += ";C:\ruta\Scripts\Python"
# Para hacerlo permanente, agregar al perfil de PowerShell o variables de entorno del sistema
```

### Scripts actualizados
`start_demo.bat` (si existe) debe usar `python -m uvicorn` en lugar de `uvicorn` directo.

---

## [2026-05-12] FEAT S3: Módulo de Segmentación (segmentation_detector.py)

**Tipo**: FEAT  
**Autor**: AI Agent  
**Archivo**: `core/segmentation_detector.py`

### Descripción
Detector de segmentación multi-modo basado en YOLOv8-seg con degradación graceful si `ultralytics` no está disponible.

### Modos implementados
| Modo | Descripción |
|------|-------------|
| `instance` | Una máscara por objeto (personas, vehículos, etc.) |
| `semantic` | Objetos del mismo tipo agrupados en una máscara de color |
| `panoptic` | Instancias (things) + fondos semánticos (stuff) |

### Dataclass `SegmentationResult`
```python
@dataclass
class SegmentationResult:
    masks:  List[Any]       # máscaras binarias np.ndarray bool H×W
    boxes:  List[List[int]] # [xmin, ymin, xmax, ymax]
    labels: List[str]       # clase YOLO
    scores: List[float]     # confianza [0, 1]
    mode:   str
    raw:    Optional[Any]   # resultado crudo ultralytics
```

### Compatibilidad
Expone `find_pose()` y `find_position()` para integración transparente con `detector_factory` y `runner.py`.

---

## [2026-05-12] FEAT S3: Detector de Intrusión con Polígonos (intrusion_detector.py)

**Tipo**: FEAT  
**Autor**: AI Agent  
**Archivo**: `core/intrusion_detector.py`

### Descripción
Detecta cruces de objetos en zonas poligonales con tracking por distancia de centroide (sin dependencias externas de DeepSORT).

### Dataclasses
```python
ZoneConfig:      id, label, points, critical, classes, normalized
IntrusionEvent:  zone_id, track_id, label, timestamp, direction, confidence, centroid, bbox, is_critical
```

### Algoritmo
1. Por frame: calcular centroide de cada detección
2. Asignar track_id via `_CentroidTracker` (distancia euclidiana)
3. `cv2.pointPolygonTest()` para verificar si está dentro del polígono
4. Emitir evento solo cuando cambia estado (in/out) Y cooldown cumplido
5. Zonas `critical=True` activan bocina cuando `is_after_hours()==True`

---

## [2026-05-12] FEAT S3: Detector de Vehículos (vehicle_detector.py)

**Tipo**: FEAT  
**Autor**: AI Agent  
**Archivo**: `core/vehicle_detector.py`

### Descripción
Rastrea vehículos (car / truck / motorcycle / bus) que cruzan un polígono de entrada. Extrae color dominante via histograma HSV para indexación forense.

### Dataclass `VehicleEvent`
```python
VehicleEvent:
    vehicle_class    # car / truck / motorcycle / bus
    color_label      # white / black / gray / red / blue / ...
    entry_time       # unix timestamp entrada
    exit_time        # unix timestamp salida (None si aún activo)
    duration_seconds # segundos en polígono
    plate_roi        # reservado para OCR futuro (None)
    bbox             # [xmin, ymin, xmax, ymax]
    track_id         # ID del track
    camera_id        # cámara fuente
    confidence       # confianza media
```

### Detección de color (función `_dominant_color`)
Pipeline: crop BGR → HSV → conteo por brillo/saturación → conteo por rangos de matiz
Paleta: white / black / gray / red / orange / yellow / green / cyan / blue / purple / pink / mixed

### Criterio de evento (anti-spam)
Solo genera `VehicleEvent` si el vehículo estuvo `min_intersection_sec` ≥ 2s en el polígono.

---

## [2026-05-12] FEAT S3: Detector de Movimiento (motion_detector.py)

**Tipo**: FEAT  
**Autor**: AI Agent  
**Archivo**: `core/motion_detector.py`

### Descripción
Detector de movimiento basado en `BackgroundSubtractorMOG2` de OpenCV. Sin dependencias adicionales. Solo emite eventos cuando `is_after_hours == True`.

### Pipeline de procesamiento
1. `GaussianBlur` → reduce ruido de cámara
2. `MOG2.apply()` → máscara de primer plano
3. `threshold` → eliminar sombras (valor 127)
4. Morfología (OPEN + CLOSE) → eliminar píxeles aislados
5. `findContours` → detectar áreas de movimiento
6. Filtrar por `min_area_px` → reducir falsas alarmas

### Comportamiento de horario
```python
# Horario hábil: actualiza el modelo de fondo en silencio
# Horario no hábil: emite MotionEvent al detectar movimiento
event = detector.update(frame, is_after_hours=is_after_hours())
```

---

## [2026-05-12] FEAT S3: Cargador de Modelos Custom (custom_model_loader.py)

**Tipo**: FEAT  
**Autor**: AI Agent  
**Archivo**: `core/custom_model_loader.py`

### Descripción
Pipeline de Transfer Learning: carga pesos `.pt` o `.onnx` entrenados por el cliente, devolviendo modelo compatible con la interfaz del sistema.

### Función principal
```python
model = load_custom_model(
    weights_path="models/cliente_abc.pt",
    task="detect",  # detect | segment | classify | pose
    device="auto",
)
```

### Validaciones de seguridad
- Verifica existencia del archivo antes de cargar
- Solo permite extensiones: `.pt`, `.pth`, `.onnx`
- Loguea: nombre, task, device, número de clases detectadas
- Si falla: retorna `None` + WARNING (no crash)

---

## [2026-05-12] REFACTOR S3: detector_factory.py — Soporte multi-módulo

**Tipo**: REFACTOR  
**Autor**: AI Agent  
**Archivo**: `core/detector_factory.py`

### Descripción
Reescritura completa del factory para soportar los 6 módulos de Sprint 3 manteniendo compatibilidad total con código existente.

### Nuevo parámetro `module_type`
```python
# Compatibilidad total: sin parámetro = fall_detection (comportamiento anterior)
detector = get_detector()

# Módulos nuevos
detector = get_detector(module_type="segmentation", mode="instance")
detector = get_detector(module_type="intrusion", zones=[...])
detector = get_detector(module_type="vehicle", entry_polygon=[...])
detector = get_detector(module_type="motion", sensitivity=0.6)
detector = get_detector(module_type="custom", weights_path="model.pt", task="detect")
```

### Arquitectura interna
Cada módulo tiene su propio constructor privado (`_make_*`), manteniendo el código limpio y sin condicionales anidados. El parámetro `device="auto"` resuelve automáticamente cuda/cpu via `torch.cuda.is_available()`.

---

---

## [2026-05-12] DEPS S4: Instalación de dependencias Sprint 4

**Tipo**: DEPS  
**Autor**: AI Agent

```
pip install onvif-zeep websockets slowapi python-multipart
```

| Paquete | Versión | Uso |
|---------|---------|-----|
| `onvif-zeep` | 0.2.12 | Protocolo ONVIF para cámaras IP (WS-Discovery, RTSP URI) |
| `websockets` | 16.0 | Soporte WebSocket en uvicorn para feeds en vivo |
| `slowapi` | 0.1.9 | Rate limiting por IP (60 req/min en endpoints de búsqueda) |
| `python-multipart` | 0.0.28 | Soporte form-data en endpoints de ingest de frames |

---

## [2026-05-12] FEAT S4: Conector ONVIF (onvif_connector.py)

**Tipo**: FEAT  
**Autor**: AI Agent  
**Archivo**: `inputs/onvif_connector.py`

### Descripción
Conector para cámaras IP que soportan el protocolo ONVIF Profile S/T. Permite obtener streams RTSP sin conocer la URL de antemano, obtener información del dispositivo y controlar PTZ.

### Características
- `ONVIFConnector(host, port, user, password_env)` — contraseña SIEMPRE desde variable de entorno
- `connect()` → autentica con el dispositivo
- `get_stream_uri(profile_index)` → retorna URL RTSP del stream principal
- `get_device_info()` → fabricante, modelo, firmware, número de serie
- `ptz_move(pan, tilt, zoom)` → control de cámara PTZ
- `discover()` → WS-Discovery en subred local
- Degradación graceful a RTSP directo si `onvif-zeep` no disponible
- Seguridad: extensión de contraseña solo via env var; nunca literal

### Dataclass `ONVIFCameraInfo`
```python
ONVIFCameraInfo: host, port, stream_uri, profile_token,
                 manufacturer, model, firmware, serial_number, supports_ptz
```

---

## [2026-05-12] FEAT S4: Router Edge/Hub (edge_hub_router.py)

**Tipo**: FEAT  
**Autor**: AI Agent  
**Archivo**: `core/edge_hub_router.py`

### Descripción
Componente de arquitectura para el modelo Hybrid Edge-as-a-Service. Define cómo los frames y eventos se procesan y transmiten al cerebro central de FuenApa en Curicó.

### Modos de despliegue
| Modo | Comportamiento |
|------|---------------|
| `edge` | 100% local — sin comunicación al hub (Sprint 1-3) |
| `hub` | Frames comprimidos enviados al cerebro vía HTTP POST multipart |
| `hybrid` | Alertas críticas procesadas localmente + frames al hub en paralelo |

### Arquitectura interna
- `threading.Queue` con backpressure (`maxsize=30`) — frames descartados si hub no responde
- Hilo daemon `EdgeHubSender` — no bloquea el loop principal de detección
- Reintentos con backoff exponencial (2^n segundos) para eventos críticos
- Autenticación: `Authorization: Bearer {HUB_API_KEY}` en todos los envíos
- Compresión JPEG configurable (default quality=60 para reducir ancho de banda)

### Dataclass `RouterConfig`
```python
RouterConfig: mode, hub_url, hub_api_key_env, jpeg_quality,
              max_queue_size, send_timeout_sec, retry_critical, node_id
```

---

## [2026-05-12] FEAT S4: Panel de Operador (operator_panel.py + operator.html)

**Tipo**: FEAT  
**Autor**: AI Agent  
**Archivos**: `api/operator_panel.py`, `api/static/operator.html`

### Descripción
Panel de vigilancia en tiempo real para operadores de seguridad, accesible desde el browser en `/operator/`.

### Backend (`operator_panel.py`)
FastAPI sub-aplicación montada en `/operator`:
- `WS /operator/ws/live/{camera_id}` → stream JPEG via WebSocket (~15 FPS)
- `GET /operator/api/cameras/status` → estado de cámaras (online/offline/fps/alertas)
- `GET /operator/api/events/recent?minutes=N` → bitácora de eventos recientes
- `POST /operator/api/events/{id}/acknowledge` → marcar evento como revisado
- `POST /operator/api/shift/export` → resumen JSON del turno para PDF

APIs internas para inyectar datos desde runner:
- `push_frame(camera_id, frame_bgr)` → comprime JPEG y transmite via WS
- `push_event(event_dict)` → agrega a bitácora del panel
- `mark_camera_offline(camera_id)` → actualiza estado

### Frontend (`operator.html`)
UI dark theme con:
- Grid de feeds de cámaras en vivo (canvas HTML + WebSocket binario)
- Indicador de estado por cámara (verde/amarillo/rojo)
- Bitácora lateral con alertas recientes por nivel (1/2/3)
- Botón "Acknowledge" por evento — trazabilidad del operador
- Stats en tiempo real: cámaras activas, eventos 1h, alertas críticas
- Exportar turno como JSON (para conversión a PDF)
- Tab de acciones rápidas (exportar, health check, abrir auditoría)

---

## [2026-05-12] FEAT S4: Hardening de seguridad (forensic_api.py)

**Tipo**: FEAT  
**Autor**: AI Agent  
**Archivo**: `api/forensic_api.py`

### Cambios aplicados

#### 1. Autenticación Bearer token
```python
# Variable de entorno: API_SECRET_KEY
# En modo dev sin key: acceso abierto con WARNING
dependencies=[Depends(require_auth)]  # en todos los endpoints /api/v1/
```

#### 2. Validación HMAC-SHA256 para webhooks
```python
# Header requerido: X-Vigilante-Signature: sha256=<hex>
# Variable de entorno: WEBHOOK_SECRET
POST /api/v1/webhook/trigger  → verifica firma antes de persistir evento
```

#### 3. Rate limiting (slowapi)
```
/api/v1/search  → 60 requests/minute por IP
/api/v1/events  → 60 requests/minute por IP
/api/v1/export  → 10 requests/minute por IP
```

#### 4. Otras mejoras
- `CORS_ORIGINS` configurable via env var (no más `*` hardcodeado en producción)
- Swagger UI desactivado por defecto (`ENABLE_DOCS=false`)
- Headers de seguridad HTTP en Nginx (`HSTS`, `X-Frame-Options`, `X-Content-Type-Options`)
- Panel de Operador montado como sub-app en `/operator`

---

## [2026-05-12] FEAT S4: Docker Compose + Dockerfiles

**Tipo**: FEAT  
**Autor**: AI Agent  
**Archivos**: `scripts/docker-compose.yml`, `scripts/Dockerfile.api`, `scripts/Dockerfile.runner`, `scripts/nginx.conf`, `.env.example`

### Arquitectura Docker
```
docker-compose up -d  →  levanta 4 servicios:

  nginx (ports 80/443)
    └── vigilante-api (:8000)
          └── postgres (:5432, solo local)
  vigilante-runner (acceso a GPU)
    └── postgres
```

### Características
- `timescale/timescaledb:latest-pg16` → PostgreSQL 16 + TimescaleDB
- Schema SQL inicializado automáticamente al primer `up`
- `vigilante-api`: Python 3.12 slim, usuario no root (UID 1001)
- `vigilante-runner`: base CUDA 12.3, descarga modelos YOLOv8 al buildear
- Nginx: TLS 1.2/1.3, HSTS, sin versión en headers
- Health checks en API y PostgreSQL
- Variables sensibles solo en `.env` (nunca en `docker-compose.yml`)

### `.env.example`
Plantilla completa documentada con todas las variables:
- Credenciales BD, API keys, SMTP, MQTT, streams RTSP
- Comentarios explicativos en cada variable
- Instrucción de generación de tokens seguros

---

## [2026-05-12] DOCS S4: THREAT_MODEL.md

**Tipo**: DOCS  
**Autor**: AI Agent  
**Archivo**: `THREAT_MODEL.md`

### Descripción
Modelo de amenazas completo basado en metodología STRIDE con:
- 8 activos identificados y clasificados (secreto / confidencial / datos personales)
- 20 amenazas mapeadas a los 6 vectores STRIDE
- Controles implementados y pendientes por amenaza
- Diagrama de superficie de ataque
- Tabla de compliance (Ley 21.663, Ley 21.459, Ley 19.303, ISO 27001)
- Plan de respuesta a incidentes en 3 niveles
- Checklist de hardening antes de puesta en producción

---

## Pendientes / Deuda técnica

| ID | Descripción | Prioridad | Estado |
|----|-------------|-----------|--------|
| TD-01 | Tests unitarios `tests/test_segmentation_detector.py` | Alta | Pendiente |
| TD-02 | Tests unitarios `tests/test_intrusion_detector.py` | Alta | Pendiente |
| TD-03 | Tests unitarios `tests/test_vehicle_detector.py` | Alta | Pendiente |
| TD-04 | Tests unitarios `tests/test_motion_detector.py` | Media | Pendiente |
| TD-05 | Integrar `IntrusionDetector` y `VehicleDetector` en `runner.py` | Alta | Pendiente |
| TD-06 | Actualizar `start_demo.bat` con `python -m uvicorn` | Media | Pendiente |
| TD-07 | Actualizar `CODE_INDEX.md` con módulos S3 y S4 | Alta | Pendiente |
| TD-08 | MQTT broker integration para bocina (`paho-mqtt`) | Media | Pendiente |
| TD-09 | ONVIF/RTSP connector — ✅ implementado en S4 | — | ✅ Resuelto |
| TD-10 | Búsqueda semántica / vectorial sobre ForensicDB | Sprint 5+ | Pendiente |
| TD-11 | `push_frame()` / `push_event()` del OperatorPanel integrados en runner.py | Alta | Pendiente |
| TD-12 | Certificados TLS para nginx en producción (Let's Encrypt / CA corporativa) | Alta | Pendiente |
| TD-13 | Cifrado en reposo de columna `metadata` JSONB (pgcrypto) | Media | Pendiente |
| TD-14 | Confirmación de protocolo FuenApa: RTSP puro vs ONVIF vs SDK propietario | Bloqueante | Pendiente |

---

## Convenciones del DEVLOG

### Tipos de entrada
| Tipo | Cuándo usar |
|------|-------------|
| `FEAT` | Nueva funcionalidad o módulo |
| `FIX` | Corrección de bug o error |
| `REFACTOR` | Reestructuración sin cambio de comportamiento |
| `ARCH` | Decisión de arquitectura |
| `ERROR` | Registro de error encontrado (sin fix aún) |
| `DEPS` | Instalación o actualización de dependencias |
| `DOCS` | Documentación únicamente |
| `PERF` | Optimización de rendimiento |
| `SECURITY` | Corrección de vulnerabilidad o compliance |

### Plantilla para nuevas entradas
```markdown
## [YYYY-MM-DD] TIPO: Título breve

**Tipo**: TIPO
**Autor**: Nombre / AI Agent
**Archivos afectados**: `ruta/al/archivo.py`

### Descripción
...

### Causa raíz (solo para FIX/ERROR)
...

### Solución aplicada
...
```
