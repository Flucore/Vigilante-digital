# 02 — Auditoría de código v2.5 · Vigilante Digital

| Campo | Valor |
|---|---|
| Estado | Vigente (snapshot reformulación) |
| Versión | 2.5-audit-1.0 |
| Fecha | 2026-08-16 |
| Alcance | Lectura de arquitectura y módulos; sin cambios de código |
| Relacionado | [01_CHARTER.md](01_CHARTER.md) · [CODE_INDEX.md](../../CODE_INDEX.md) |

---

## 1. Veredicto

Base **comercialmente aprovechable** (capas, `runner.py` multi-cámara, EventLogger, triggers async, seeds de seg/intrusión).  
**No** es aún un SKU edge empaquetado ni una plataforma MLOps de título.  
Orquestador canónico: **`runner.py`**. **`main.py`** = legado de demo caída/archivo.

## 2. Fortalezas (conservar)

| Activo | Evidencia | Valor |
|---|---|---|
| Separación Inputs / Core / Outputs | Estructura + `.cursor/rules` | Extensibilidad |
| Orquestación multi-cámara | `runner.py`: `CameraWorker`, `CameraState`, `queue.Queue` | Escala inicial N cams |
| Reducción de escrituras ~99% | `EventLogger` NORMAL↔FALLING | Costo Firestore / ruido |
| Factory de detectores | `detector_factory`: YOLO → MediaPipe; módulos seg/intrusión/vehículo/motion | Swap de motor |
| Semilla HITL | `core/learning_dataset.py` + `scripts/add_dataset_image.py` | Base M2/curiosidad |
| Triggers no bloqueantes | `TriggerManager` + `ThreadPoolExecutor` | Segundo cero sin matar FPS |
| Config por cliente | `ConfigLoader`, zonas, schedule after-hours | Multi-sitio |
| Indexación / forense | `MetadataIndexer`, `ForensicDB`, API forense | Diferenciador de *hoy* |
| Compliance documentado | `COMPLIANCE.md`, reglas Chile, threat model | Track serio |

## 3. Deudas técnicas (priorizadas)

| ID | Deuda | Impacto | Track natural |
|---|---|---|---|
| D01 | Heurísticas rígidas (ratio bbox, HSV, línea perímetro simple) | FP/FN en Perimeter/Aqua | Comercial |
| D02 | `main.py` legado vs `runner.py` canónico | Confusión IA/humanos | Docs + cleanup menor |
| D03 | `outputs/trigger_manager.py` importa `inputs/ip_speaker` | Viola regla de capas | Comercial (fix capa) |
| D04 | `EventLogger` centrado en `fall`; schema canónico incompleto al emitir | Care + auditabilidad multi-evento | Comercial |
| D05 | Perimeter = línea; no máscara irregular de piscina/muro (M0) | Aqua & Risk no vendible “día 1” | Comercial · Aprendizaje-A |
| D06 | Módulos seg/intrusión/vehículo poco cableados al runner de producto | Valor en `core/` sin SKU | Comercial |
| D07 | Sin motor de curiosidad ni gold-set ni promote | No hay “aprendizaje” real | Académico · B–D |
| D08 | Concurrencia: 1 hilo/cámara OK; sin política GPU/backpressure formal | Escala > pocas IP cams | Ambos |
| D09 | Docs raíz desalineadas (`EXECUTIVE_SUMMARY` habla MediaPipe-only) | Mensaje comercial erróneo | DOCS (esta ola) |
| D10 | Tests escasos (`tests/` mínimo) | Regresión al modularizar | Ambos |

## 4. Mapa dolor → módulo → gap → track

| Dolor | Módulo producto | Qué hay hoy | Gap crítico | Track |
|---|---|---|---|---|
| Autopsia visual / intrusión | **Perimeter Guard** | `PerimeterDetector` (línea) + pose/YOLO + triggers en `runner` | Línea ≠ muro irregular; WhatsApp/relé no estabilizados como paquete; tracking débil | **Comercial** |
| Riesgo hídrico / niños | **Aqua & Risk** | Zonas en config; `SegmentationDetector` / `IntrusionDetector` en factory | Sin producto “piscina”: M0 máscara + IoU persona∩agua; SAM solo como concepto | **Comercial** (M0) → Académico (seg fina) |
| Accidentes / compliance | **Care & Fall** | `YoloFallDetector` / MediaPipe, EventLogger, PDF/`ReportGenerator` | Eventos canónicos completos (`event_schema_version`, compliance); menos dependencia de ratio; cadena de custodia explícita | **Comercial** |
| “Mejor que cámara con IA” | **Criterio de Sitio** | `LearningDataset` (semilla), custom weights loader | M0–M3, curiosidad, HITL UI, gold-set, shadow/canary/rollback | **Académico** (+ M0 en Comercial) |
| Faena / flota | Taxonomía M2 + `machine_unlisted` | Detector vehículo/excavator parcial | Clasificador fino + domain mix + flota autorizada | **Académico** (demo Comercial limitada con reglas) |

## 5. Readiness de venta (honesto)

| Capacidad | ¿Se puede mostrar? | ¿Se puede vender como SLA? | Nota |
|---|---|---|---|
| Caída en video archivo / 1 cam | Sí | Con reservas (FAR no cerrado) | Más maduro del stack |
| Perímetro línea + alerta | Sí (demo) | Solo piloto controlado | No confundir con muro real |
| Piscina borde irregular | No (producto) | No | Requiere Aprendizaje-A (M0) |
| PDF + email de evento | Sí | Parcial | Depende SMTP/config |
| Bocina / webhook | Parcial | No sin commissioning | TriggerManager existe |
| “El sistema aprende solo” | — | **Nunca** | Anti-patrón |
| Fine-tune auto a cámaras | No | **No** | Solo tras sprints C–D |
| Multi-cliente cloud ML | No | No | Tenant isolation pendiente de diseño |

**Conclusión readiness:** vender **piloto Edge Care/Perimeter (línea) + roadmap M0 piscina**, no “IA que aprende sola” ni Aqua completo.

## 6. Stack observado (resumen)

```
Ingesta:     VideoStream / FileVideoReader / ONVIF seed / USB / ESP32
Inferencia:  detector_factory → YOLO-pose/seg | MediaPipe | color HSV | perimeter línea
Lógica:     ConfigLoader, after_hours, EventLogger (fall-centric)
Indexación: MetadataIndexer, ForensicDB (Postgres|JSONL)
Acción:     TriggerManager, ReportGenerator, Email, IpSpeaker (acoplamiento de capa)
Orquestación: runner.py (realtime|file|batch) · main.py legado
Aprendizaje: LearningDataset (manifiesto JSONL) — sin train/promote
```

## 7. Cumplimiento y amenaza (auditoría corta)

- Imágenes de personas = dato sensible/biométrico → datasets con retención y purge (diseño pendiente en Unidad 3/5).
- Pesos = activo (`THREAT_MODEL` A-07); checksum al cargar aún deuda (T-T04).
- Guerrilla excluida por selector FluCore.

## 8. Recomendación inmediata (post-ola DOCS)

1. Cerrar Unidades 2–5 (docs).
2. **C1 Comercial:** M0 usable (zona máscara + IoU) reutilizando perimeter/intrusion — sin pipeline de train.
3. Estabilizar Care + Perimeter línea como oferta piloto.
4. No abrir microservicios hasta contrato de datos (curiosidad + gold-set) documentado.

## 9. DECISIONES HUMANAS (desde auditoría)

- ¿El primer piloto de pago es Care, Perimeter o parcela/piscina?
- ¿JSONL basta en piloto o Postgres forense es obligatorio?
- ¿FAR objetivo interno (aunque no esté en contrato)?
