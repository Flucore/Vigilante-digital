# Vigilante Digital — Plan Maestro de Desarrollo

| Campo | Valor |
|---|---|
| Estado | **Vigente** |
| Versión | 3.0 |
| Fecha | 2026-08-16 |
| Dueño | FluCore |
| Reemplaza | Plan Maestro v2.0 (Mayo 2026) — contenido previo obsoleto respecto a Dual-Track + Memoria de Sitio |

> Este archivo es el **mapa ejecutivo**. El detalle vive en `docs/REFORMULACION/` y la ejecución de código en [`DESARROLLO_EJECUTABLE.md`](DESARROLLO_EJECUTABLE.md).

---

## 1. Qué es el producto

**Vigilante Digital** convierte cámaras existentes en sensores con **criterio de sitio**: alerta en el segundo cero, evidencia auditable y aprendizaje supervisado (HITL) — no “más clases COCO”.

> Una cámara con IA ve clases universales. Vigilante Digital acumula criterio de este sitio.

| Dolor | Módulo | Mercado |
|---|---|---|
| Autopsia visual | Perimeter Guard | Comercio VIP / bodegas |
| Riesgo hídrico / niños | Aqua & Risk (M0) | Parcelas Colina/Chicureo |
| Accidentes / compliance | Care & Fall + PDF | Faenas / ISO 45001 |

**SKU:** Criterio de Sitio = M0 + M1 + HITL + (opc) M2/M3.  
**Modelo:** Hybrid Edge-as-a-Service (CAPEX nodo + licencia + OPEX 8×5).

## 2. Dual-Track

| Track | Meta | Documento |
|---|---|---|
| **Comercial (F1)** | Piloto edge cobrable Verano 2026 | [06_PLAN…](docs/REFORMULACION/06_PLAN_DUAL_TRACK.md) · [DESARROLLO…](DESARROLLO_EJECUTABLE.md) |
| **Académico (F2)** | Proyecto de Título + MLOps | [07_PROYECTO_TITULO.md](docs/REFORMULACION/07_PROYECTO_TITULO.md) |
| **DOCS** | Gobierno documental | **Cerrado** 2026-08-16 |

**Regla:** no meter train job, bus de eventos, auto-promote ni microservicios en sprints de liquidez (C1–C6).

## 3. Memoria de Sitio (diferenciador)

| Memoria | Qué es | ¿Train? |
|---|---|---|
| M0 Geométrica | Zonas/máscaras por cámara (SAM solo anotación) | No |
| M1 Percepción | YOLO-seg/pose + tracker en edge | Pesos base estables |
| M2 Taxonomía | Cat vs Komatsu, etc. (clasificador fino) | Sí, domain mix |
| M3 Conductual | Eventos compuestos (reglas primero) | Secuencia después |

Detalle: [05_ARQUITECTURA…](docs/REFORMULACION/05_ARQUITECTURA_Y_MEMORIA_SITIO.md).

## 4. Arquitectura (inamovible)

```text
inputs/ → core/ → outputs/     runner.py = canónico     main.py = legado
config.py + env                api/ → core + outputs + config
Firebase opcional              event_schema_version "2.0" · ISO 8601 TZ
```

Índice de código: [`CODE_INDEX.md`](CODE_INDEX.md).  
Glosario: [`GLOSARIO.md`](GLOSARIO.md).  
Contexto IA: [`AI_CONTEXT.md`](AI_CONTEXT.md).

## 5. Roadmap ejecutivo

```text
DOCS ✓ → C1 M0 IoU → C2 Care → C3 Perimeter → C4 Aqua → C5 Empaque → C6 Tests
              └─► (cuando C1 estable) A1 HITL → A2 datos → A3 M2 → A4 promote → A8 tesis
```

Prompts listos: [`DESARROLLO_EJECUTABLE.md`](DESARROLLO_EJECUTABLE.md).

## 6. SLA / alertas (piloto controlado)

| Parámetro | Objetivo |
|---|---|
| Latencia alerta local | &lt; 1 s desde detección confirmada |
| Soporte | 8×5 remoto (no 24/7 salvo contrato) |
| Retención evidencia | Configurable; default orientativo 30 días |
| FAR contractual | **No prometido** hasta evidencia; se mide |
| Niveles | Silent → Notify → Critical |

Readiness de venta: [04_VISION_COMERCIAL…](docs/REFORMULACION/04_VISION_COMERCIAL_Y_VENTAS.md).

## 7. Cumplimiento

- Leyes Chile (datos, ciber, vigilancia) + ISO 27001/27701/45001 según vertical.  
- Guerrilla FluCore **excluida**.  
- Personas en dataset = biométrico; tenant isolation.  
- Ver `COMPLIANCE.md`, `THREAT_MODEL.md`, [09_REGISTRO…](docs/REFORMULACION/09_REGISTRO_RIESGOS_Y_DEUDA.md).

## 8. Lectura obligatoria antes de código

1. `AI_CONTEXT.md`  
2. `DESARROLLO_EJECUTABLE.md` (unidad activa, p. ej. C1)  
3. `CODE_INDEX.md` + `.cursor/rules/`  
4. `GLOSARIO.md`  

## 9. Qué quedó obsoleto del plan Mayo 2026

- Etapa 4 como “lista de detectores” (armas/térmico/EPP) sin plataforma de memorias.  
- Transfer learning = “cargar un .pt” sin gold-set/promote.  
- Microservicios como primer paso de liquidez.  
- Narrativa centrada solo en MediaPipe / maqueta FuenApa como único horizonte.  
- Cualquier promesa de auto-aprendizaje o auto-deploy.

Esos temas, si reaparecen, se reinterpretan vía M0–M3 + Dual-Track o se archivan.
