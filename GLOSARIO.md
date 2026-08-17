# Glosario — Vigilante Digital (FluCore)

| Campo | Valor |
|---|---|
| Estado | **Canónico** |
| Versión | 1.1 |
| Fecha | 2026-08-16 |
| Espejo en reformulación | [docs/REFORMULACION/03_GLOSARIO.md](docs/REFORMULACION/03_GLOSARIO.md) |
| Índice de código | [CODE_INDEX.md](CODE_INDEX.md) |
| Ejecución | [DESARROLLO_EJECUTABLE.md](DESARROLLO_EJECUTABLE.md) |

---

## Distinciones críticas

| Par | Significado |
|---|---|
| **Calibrar ≠ Entrenar** | Calibrar = geometría/zonas (M0). Entrenar = pesos en hub/GPU. Un borde de piscina **no** es un `.pt`. |
| **Curiosidad ≠ Alerta** | Curiosidad = encolar para HITL. Alerta = email/bocina/webhook. |
| **Detección ≠ Evento compuesto** | Clase gruesa vs receta (pose + zona + tiempo + track). |
| **BBox ≠ Máscara** | Ambos conviven; no se abandona el bbox. |
| **SAM ≠ Detector 24/7** | SAM/SAM2 solo anotación/commissioning. |
| **mAP ≠ FAR** | mAP interna; **FAR** = falsas alarmas/cámara-hora (negocio). |
| **runner ≠ main** | `runner.py` canónico; `main.py` legado. |

---

## Producto y negocio

| Término | Definición |
|---|---|
| **Criterio de Sitio** | SKU: M0 + M1 + HITL + (opc) M2 + M3. |
| **Hybrid Edge-as-a-Service** | CAPEX nodo + licencia + OPEX soporte. |
| **ICP** | Comercio VIP / bodega / parcela con dolor medible. |
| **Piloto controlado** | Venta con caveats; FAR no garantizado al inicio. |
| **Commissioning** | Puesta en marcha: cams, M0, triggers, retención, cartelería. |
| **Segundo cero** | Latencia local &lt; 1 s desde detección confirmada. |
| **Dual-Track** | F1 Comercial (liquidez) + F2 Académico (título/MLOps). |

---

## Cuatro memorias

| Código | Nombre | ¿Train? |
|---|---|---|
| **M0** | Geométrica — polígonos/máscaras por cámara | No |
| **M1** | Percepción genérica — YOLO-seg/pose + tracker | Pesos base estables |
| **M2** | Taxonomía del cliente — clasificador fino | Sí + domain mix |
| **M3** | Conductual — eventos compuestos | Reglas primero |

---

## MLOps

| Término | Definición |
|---|---|
| **Motor de Curiosidad** | Políticas combinadas (no umbral global único). |
| **CuriositySample** | Evidencia encolada con metadata completa + `curiosity_reason`. |
| **HITL** | Humano valida; la IA no se autocorrije. |
| **Gold-set** | Eval por sitio; nunca entra a train. |
| **ModelCard** | Clases, métricas, SHA256, parent, reviewer, tenant. |
| **Shadow / Canary / Promote / Rollback** | Cadena obligatoria antes de pesos en producción. |
| **Domain gap** | Catálogo ≠ CCTV; hace falta mezcla in-situ. |
| **FAR** | Falsas alarmas por cámara-hora. |
| **Tenant isolation** | Cliente A no entrena cliente B sin opt-in. |

---

## Entidades conceptuales

| Entidad | Rol |
|---|---|
| `SiteZoneMask` | Zona M0 versionada por cámara |
| `TaxonomyLabel` | Subclase M2 |
| `CompositeEventRecipe` | Receta M3 → `event_type` |
| `ModelCard` / `GoldSet` | Promote gobernado |

**Eventos compuestos (objetivo):** `intrusion_climb` · `predator_attack` · `machine_unlisted` · `zone_calibration_drift`

---

## Operación y código

| Término | Definición |
|---|---|
| **Evento canónico** | `event_schema_version: "2.0"` + ISO 8601 TZ |
| **EventLogger** | Frames → episodios (hoy centrado en `fall`) |
| **Silent / Notify / Critical** | Niveles de alerta |
| **IoU zona** | Intersección detección ∩ zona + persistencia |
| **Edge node** | Mini-PC/Jetson en sitio del cliente |

Capas: ver [CODE_INDEX.md](CODE_INDEX.md) §14.

---

## Anti-patrones

- Aprende solo · Abandonar bbox · SAM en cámara · 45%→N fotos→deploy  
- Clase YOLO “ladrón_saltando_muro” · Catálogo solo = prod · Train en edge  
- Microservicios MLOps antes del contrato de datos · Mezclar tenants  

---

## Cumplimiento (corto)

Imagen de persona = dato sensible/biométrico · Cadena de custodia · Cartelería fuera de código · Guerrilla FluCore excluida.
