# 05 — Arquitectura y Memoria de Sitio

| Campo | Valor |
|---|---|
| Estado | Vigente (ola DOCS) |
| Versión | 1.0 |
| Fecha | 2026-08-16 |
| Dueño | FluCore |
| Relacionado | [01_CHARTER.md](01_CHARTER.md) · [03_GLOSARIO.md](03_GLOSARIO.md) · [CODE_INDEX.md](../../CODE_INDEX.md) |

> **Calibrar ≠ Entrenar.** SAM/SAM2 **nunca** en el loop 24/7 de cámara. BBox **no** se abandona.

---

## 1. Diferenciador

| Hoy (vendible / demo) | Definitivo (producto) |
|---|---|
| Video → data auditable (indexación, eventos, PDF) | **Memoria de sitio** (M0–M3 + HITL + promote) |

Una cámara con IA ve clases. Vigilante Digital acumula **criterio de este sitio**.

---

## 2. Arquitectura actual (monolito modular edge)

```text
┌─────────────────────────────────────────────────────────────┐
│  runner.py  (canónico)  ·  main.py = legado                 │
├──────────────┬──────────────────┬───────────────────────────┤
│  INPUTS      │  CORE            │  OUTPUTS                  │
│  VideoStream │  detector_factory│  EventLogger              │
│  FileReader  │  YOLO-pose/seg   │  MetadataIndexer          │
│  ONVIF/USB…  │  MediaPipe       │  ForensicDB               │
│              │  Perimeter/Intr. │  TriggerManager           │
│              │  LearningDataset │  Report/Email/HUD         │
│              │  (semilla HITL)  │  api/ forensic + operator │
└──────────────┴──────────────────┴───────────────────────────┘
         config.py + client_config / demo_config + .env
```

**Reglas de importación (inamovibles):**

- `core/` → no importa `inputs/` ni `outputs/`
- `inputs/` ↔ `outputs/` prohibido
- `api/` puede usar `core/` + `outputs/` + `config`
- Loop de aprendizaje (lógico): `outputs/` (dataset/cola) + `api/` (HITL) + `scripts/` (train job)
- `core/` solo **consume** pesos ya promovidos y zonas ya calibradas

**Deuda de capa conocida:** `TriggerManager` → `inputs/ip_speaker` (corregir en Track Comercial).

---

## 3. Arquitectura objetivo (servicios LÓGICOS — no microservicios prematuros)

```text
[Edge]  camera-ingest → inference(M1) → rules(M0∩mask, M3) → events + curiosity enqueue
                                    ↓
[Local/Hub]  event-store · trigger-service · forensic-index
                                    ↓
[HITL]  curiosity queue · alert review · SAM assist (anotación) · gold-set
                                    ↓
[Train job GPU]  dataset versionado → eval gold-set → model card → shadow → canary → promote
```

Despliegue (lib → proceso → contenedor → bus MQTT/Redis) = decisión **después** de cerrar el contrato de datos. Track Académico documenta el desacople; Track Comercial no lo exige para el primer piloto.

---

## 4. Cuatro memorias (contrato)

### M0 — Geométrica (día 1, sin train)

- **Herramienta:** SAM/SAM2 en backend de commissioning/anotación.
- **Persistencia:** `SiteZoneMask` por cámara (extensión de `zones[]`), versionada.
- **Tipos de zona:** `geofence | pool | wall | coop | machine_yard | custom`.
- **Inferencia:** detector genérico + máscara-instancia ∩ zona (IoU + persistencia).
- **Drift:** alerta `zone_calibration_drift` → recalibrar.
- SAM **recorta píxeles**; no clasifica.

### M1 — Percepción genérica (estable en edge)

- YOLOv8/v11-seg + pose + tracker.
- Clases gruesas: person, vehicle, animal, excavator…
- BBox + polígono + máscara (RLE) en forense.
- Pose para caída y trepada; seg no reemplaza pose.

### M2 — Taxonomía del cliente (segundo piso)

- Cat vs Komatsu, zorro vs perro, EPP…
- Flujo: crop por máscara → clasificador liviano / LoRA / prototipos.
- **Prohibido** reentrenar todo YOLO-seg por cada marca.
- Domain mix obligatorio (catálogo + CCTV sitio) o no hay promote.

### M3 — Conductual (eventos compuestos)

| `event_type` | Receta |
|---|---|
| `intrusion_climb` | person + pose/trepada + zona_muro + track (+ after_hours) |
| `predator_attack` | animal + zona_gallinero + persistencia + patrón de track |
| `machine_unlisted` | excavator + TaxonomyLabel ∉ flota_autorizada |
| `zone_calibration_drift` | encuadre inválido / M0 obsoleto |

Primero reglas espacial-temporales (explicables). Luego secuencia corta solo con clips auditados.

**Entidad:** `CompositeEventRecipe`.

---

## 5. Loop de aprendizaje (MLOps lógico)

### 5.1 Motor de Curiosidad

Políticas **combinadas** (no umbral global único):

1. Incertidumbre — banda por clase y por cámara  
2. Desacuerdo — seg vs clasificador vs open-vocab hub  
3. Novedad — embedding lejos de prototipos  
4. Frontera de regla — IoU en zona gris  
5. FN humano — “esto debió alertar”  
6. Exploración programada — muestreo aunque confianza alta  
7. Override operador — máxima prioridad  

Cada `CuriositySample` lleva: media, cámara, timestamp ISO 8601 TZ, clase, confianza, máscara, zona, track_id, `curiosity_reason`, `model_version`.

### 5.2 Dataset Service (evolución de `learning_dataset.py`)

- Manifiesto versionado → luego DB.
- Splits + **GoldSet** por sitio (nunca en train).
- Labels: correcto | FP | FN | ambiguo | nueva_clase | zona_mal_calibrada.
- SAM acelera máscaras; SAM2 video propaga anotación.
- Purge por tenant (Ley 21.663). Personas = biométrico.

### 5.3 Dashboard HITL

Colas: curiosidad + alertas.  
Acciones: confirmar, rechazar (motivo), corregir máscara, subclase, FN, gold-set, “problema de cámara” (→ calibración, **no** train).  
`reviewer_id` obligatorio.

### 5.4 Promoción de pesos (innegociable)

```text
dataset versionado
  → train en hub/GPU   (edge NUNCA entrena)
  → eval vs GoldSet
  → ModelCard + SHA256
  → shadow (sin triggers)
  → canary 1 cámara
  → promote
  → rollback si FAR empeora
```

**Prohibido:** N fotos → fine-tune → `.pt` a todas las cámaras.

Open-vocab = siembra en hub, no edge 24/7 salvo piloto.

### 5.5 Métricas

- Negocio: **FAR** / cámara-hora + recall de eventos críticos.  
- Interna: mAP, confusion por clase.  
- No prometer mAP al cliente.

---

## 6. Relación con el stack actual

| Pieza actual | Rol en la arquitectura nueva |
|---|---|
| `runner.py` | Edge orchestrator hasta desacople |
| `detector_factory` | Entrada M1 + módulos |
| `perimeter_detector` / `intrusion_detector` | Semilla M0/M3 (línea → máscara) |
| `segmentation_detector` | M1 máscaras |
| `learning_dataset.py` | Semilla Dataset Service |
| `custom_model_loader` | Último eslabón de registry (`ModelCard`, checksum, tenant) |
| `EventLogger` | Episodios; generalizar más allá de `fall` |
| `TriggerManager` | Acción; desacoplar de `inputs/` |
| `ForensicDB` / indexer | Evidencia + futuros campos máscara/IoU/model_version |
| Firebase | Sigue opcional; aprendizaje on-prem primero |

### Schema de evento (evolución documental)

Campos futuros a contemplar: `mask_polygon`, `zone_iou`, `model_version`, `curiosity_reason`, `taxonomy_label`, `composite_event_recipe`, `event_schema_version: "2.0"`.

---

## 7. Compliance (diseño)

- Samples con personas: retención, base legal, borrado.
- Preferir máscara sin rostro si el objetivo no es identidad.
- HITL y promote auditables (Ley 21.459 / ISO 27001).
- Pesos/datasets/adapters = activos; integridad SHA256 (cerrar T-T04).
- Sin opt-in: no modelo global multi-cliente con datos de sitios.

---

## 8. Sprints Aprendizaje (orden fijo)

| Sprint | Entrega | Track |
|---|---|---|
| **A** | M0 + IoU zonas (demo vendible) | Comercial C1 |
| **B** | Curiosidad + HITL + manifiesto rico | Comercial parcial → Académico |
| **C** | M2 + domain mix + ModelCard | Académico |
| **D** | Train job + shadow/canary/rollback | Académico |

No meter A+B+C+D+auto-deploy en un solo sprint.

---

## 9. Anti-patrones (rechazar en revisión de docs/código)

- Aprende solo · Abandonar bbox · SAM en cámara · 45%→N fotos→deploy  
- Clase YOLO “ladrón_saltando_muro” · Catálogo solo · YOLO 80 clases custom  
- Microservicios MLOps antes del contrato de datos · Mezclar tenants · Train en edge  

## 10. Verificación de este documento

- [x] Calibrar ≠ entrenar explícito  
- [x] SAM fuera del edge 24/7  
- [x] BBox complementado, no eliminado  
- [x] Promote con gold-set/shadow/canary/rollback  
- [x] Cero anti-patrones prescritos como “buen diseño”  
