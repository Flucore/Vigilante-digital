---
documento: AI_CONTEXT
version: 1.1.0
estado: vigente
proyecto: Vigilante Digital
propietario: FluCore
ultima_actualizacion: 2026-08-16
fuentes_de_verdad:
  - DESARROLLO_EJECUTABLE.md
  - GLOSARIO.md
  - docs/REFORMULACION/00_PROMPT_MAESTRO.md
  - docs/REFORMULACION/README.md
  - docs/REFORMULACION/08_BACKLOG_HUMANOS_IA.md
  - CODE_INDEX.md
  - MASTER_DEVELOPMENT_PLAN.md
  - .cursor/rules/
  - C:/Users/Valen/Documents/Fundamentales/FluCore/ (por título; no pegar enteros)
---

# Contexto maestro — Vigilante Digital (FluCore)

> Para asistentes IA y humanos. Sin secretos ni datos de clientes reales.
> Lee este archivo primero. Luego `docs/REFORMULACION/README.md`.

## 1. Contexto

- **Problema:** Las cámaras tradicionales (y muchas “con IA”) son autopsias visuales o detectores genéricos de clases COCO. No acumulan criterio del sitio del cliente.
- **Usuarios/actores:** operador de seguridad, administrador de sitio, revisor HITL, instalador edge, fundador FluCore, (futuro) tribunal/auditor de evidencia.
- **Resultado esperado:** video → data auditable en tiempo real + **memoria de sitio** (geometría, taxonomía, conducta) con supervisión humana.
- **Fuera de alcance (por defecto hasta que se pida):** Guerrilla, auto-deploy de pesos, features no listadas en la unidad activa.
- **Posicionamiento:** *Una cámara con IA ve clases universales. Vigilante Digital acumula criterio de este sitio.*
- **Glosario mínimo:**
  - **Criterio de Sitio:** SKU = M0 + M1 + HITL + (opc) M2/M3.
  - **Calibrar ≠ Entrenar:** polígono/máscara de zona no es un `.pt`.
  - **Curiosidad ≠ Alerta:** encolar evidencia dudosa/valiosa ≠ disparar sirena.
  - **Gold-set:** set de evaluación por sitio; nunca entra a train.
  - **FAR:** falsas alarmas por cámara-hora (métrica de negocio).
  - **M0–M3:** geométrica / percepción genérica / taxonomía / conductual.

## 2. Tarea activa

- **Requisito/RFC:** Dual-Track + Memoria de Sitio (docs cerrados).
- **Objetivo único:** la unidad que declare el humano (`C1` por defecto post-DOCS).
- **Archivos permitidos:** los de esa unidad (ver `08_BACKLOG_HUMANOS_IA.md`).
- **Archivos prohibidos:** fuera de alcance de la unidad; secretos; train en edge.
- **Criterios de aceptación:** DoD de la unidad en §3 de `08_…` + verificación del prompt.
- **Criticidad:** media (edge / seguridad) salvo que se declare otra.

**Tracks (preguntar antes de código):**

| Track | Uso |
|---|---|
| `TRACK_DOCS` | Solo si hay corrección documental puntual |
| `TRACK_COMERCIAL` | **Siguiente por defecto:** C1 M0 IoU |
| `TRACK_ACADEMICO` | A1+ HITL/MLOps (no mezclar en C1–C6) |

## 3. Reglas técnicas

- **Stack vigente:** Python, OpenCV, YOLOv8/v11 (+seg/pose), MediaPipe fallback, FastAPI, JSONL/Postgres forense, Firebase opcional, Docker (scripts/).
- **Arquitectura:** `inputs/ → core/ → outputs/`; `runner.py` canónico; `main.py` legado; `config.py` + env; `api/` usa core+outputs+config.
- **Importación:** `core/` no importa inputs/outputs; inputs ↔ outputs prohibido.
- **Convenciones:** type hints públicos; eventos `event_schema_version: "2.0"`; timestamps ISO 8601 con TZ; escritura JSON atómica; Firebase en try/except.
- **Dependencias:** no agregar sin aprobación; preferir reutilizar `core/` y `learning_dataset.py`.
- **Antipatrones:**
  - “El sistema aprende solo.”
  - “Abandonamos los bounding boxes.”
  - “SAM corre en la cámara 24/7.”
  - “45% → N fotos → fine-tune → deploy automático.”
  - Clase YOLO tipo `ladron_saltando_muro` / `zorro_atacando`.
  - Fotos de catálogo solas = producción.
  - Un YOLO con decenas de clases custom por cliente.
  - Microservicios MLOps antes del contrato de datos.
  - Mezclar datasets entre clientes.
  - Fine-tuning en el edge.
  - Credenciales en código o prompts.

## 4. Gobernanza

- Protocolo base: **PROTOCOLO-FLUCORE-v1** (stack propio).
- Ejecución IA: **PROTOCOLO-VIBE-CODING-v1**.
- **Guerrilla: EXCLUIDO** (biometría, menores, seguridad crítica).
- Flujo: requisito → plan → docs/código → prueba → revisión → commit (solo si se pide).
- No inventar requisitos ni ampliar alcance.
- Prohibidos en prompts: secretos, PII, datos sensibles, producción no anonimizada.
- Usar: `BLOQUEADO: … — Falta: …` · `DECISIÓN HUMANA: …`

## 5. Verificación

- **Automática:** tests unitarios del módulo tocado; smoke runner file mode cuando aplique.
- **Manual:** escenario de aceptación de la unidad (ver prompt C1).
- **Seguridad/privacidad:** sin caras innecesarias en dataset; tenant isolation.
- **Regresión:** capas de importación; EventLogger/triggers no bloquean captura.
- **Rollback:** revertir commit / desactivar `modules_active`.

## 6. Estado del proyecto

- **Último hito completado:** **Unidad 5 — ola DOCS CERRADA.**
- **Paquete canónico:** `docs/REFORMULACION/00`–`09` + `AI_CONTEXT.md`.
- **Trabajo no comprometido:** sí — docs de reformulación pendientes de commit (si el humano lo pide).
- **Bloqueos:** DECISIONES HUMANAS (pricing, FAR, universidad, vertical primer piloto) — no bloquean C1 técnico.
- **Deuda / riesgos:** `09_REGISTRO_RIESGOS_Y_DEUDA.md`.
- **Siguiente paso:** **`TRACK=COMERCIAL · C1`** — prompt en [`DESARROLLO_EJECUTABLE.md`](DESARROLLO_EJECUTABLE.md) §3 (también en `08_BACKLOG_HUMANOS_IA.md` §6).

## 7. Formato de solicitud

```text
[CONTEXTO] TRACK=COMERCIAL · C1 · fuentes
[TAREA] Una unidad del plan
[REGLAS] Alcance y antipatrones
[GOBERNANZA] Criticidad + sin commit salvo pedido
[VERIFICACIÓN] DoD + pruebas
```

## Definition of Done (este archivo)

- [x] Ola DOCS cerrada y siguiente acción C1 explícita.
- [x] Tracks, memorias, antipatrones visibles.
- [x] Sin secretos ni PII.
