# DESARROLLO EJECUTABLE — Sprints, tareas y prompts

| Campo | Valor |
|---|---|
| Estado | **Vigente — listo para código** |
| Versión | 1.0 |
| Fecha | 2026-08-16 |
| Unidad activa por defecto | **C1** |
| Plan | [MASTER_DEVELOPMENT_PLAN.md](MASTER_DEVELOPMENT_PLAN.md) · [06_PLAN…](docs/REFORMULACION/06_PLAN_DUAL_TRACK.md) |
| Contexto | [AI_CONTEXT.md](AI_CONTEXT.md) · [GLOSARIO.md](GLOSARIO.md) · [CODE_INDEX.md](CODE_INDEX.md) |

> **Cómo usar:** un chat = una unidad. Pegar el prompt de la sección correspondiente. No mezclar C* con A*.

---

## 0. Arranque de sesión (copiar)

```text
Lee AI_CONTEXT.md, GLOSARIO.md, CODE_INDEX.md y DESARROLLO_EJECUTABLE.md.
Ejecuta SOLO la unidad indicada abajo. Sin ampliar alcance.
TRACK=COMERCIAL · Unidad C1
```

Tras C1 Done, cambiar a C2, etc.

---

## 1. Tablero de sprints

### F1 Comercial (liquidez)

| ID | Sprint | Estado | Dependencia |
|---|---|---|---|
| C0 | Ola DOCS | **Done** | — |
| **C1** | M0 zonas + IoU | **Siguiente** | C0 |
| C2 | Care evento canónico | Pendiente | C1 recomendado |
| C3 | Perimeter + fix capa trigger | Pendiente | C2 o paralelo tras C1 |
| C4 | Aqua `pool` + M0 | Pendiente | **C1** |
| C5 | Empaque Docker + runbook | Pendiente | C2–C4 parcial |
| C6 | Tests smoke | Pendiente | C1–C3 |

### F2 Académico (no en liquidez)

| ID | Sprint | Estado | Dependencia |
|---|---|---|---|
| A1 | Curiosidad + HITL UI | Bloqueado hasta C1 estable | C1 |
| A2 | Gold-set + contrato datos | Pendiente | A1 |
| A3 | M2 + ModelCard | Pendiente | A2 |
| A4 | Train/shadow/canary/rollback | Pendiente | A3 |
| A5 | Recetas M3 | Pendiente | C1, C3 |
| A6 | Servicios lógicos + bus | Pendiente | A2 |
| A7 | Registry SHA256 pesos | Pendiente | A4 |
| A8 | Experimento título FAR/recall | Pendiente | A4 |

---

## 2. Plantilla base (todas las unidades)

```text
[CONTEXTO] TRACK=… · Unidad … · AI_CONTEXT · CODE_INDEX · GLOSARIO
[TAREA] … archivos permitidos … exclusiones …
[REGLAS] type hints · I/O defensivo · capas · calibrar≠entrenar · sin auto-deploy · sin secretos
[GOBERNANZA] criticidad … · commit solo si se pide · Guerrilla excluido
[VERIFICACIÓN] pruebas … · evidencia … · rollback …
```

---

## 3. Prompts F1 (comercial)

### C1 — M0 máscara/polígono + IoU (EJECUTAR PRIMERO)

```text
[CONTEXTO]
TRACK=COMERCIAL · Unidad C1 — Memoria geométrica M0 usable
Fuentes: AI_CONTEXT.md · DESARROLLO_EJECUTABLE.md · CODE_INDEX.md · docs/REFORMULACION/05_ARQUITECTURA_Y_MEMORIA_SITIO.md
Estado: DOCS cerrado. Reutilizar perimeter_detector / intrusion_detector / ZoneConfig.
Objetivo: persona ∩ zona (pool|wall|geofence|custom) con IoU + persistencia → evento canónico. Sin train.

[TAREA]
1) Extender zonas en config (type + points normalizados 0–1 o píxeles documentados) si hace falta.
2) API pura en core/ para intersección bbox (o máscara) ∩ polígono + ventana temporal (umbral en config/env).
3) Cablear en runner.py CameraWorker: si modules_active incluye zone/geofence/pool (definir nombre en CODE_INDEX), emitir evento.
4) Ejemplo en demo_config.json sin secretos.
5) Actualizar CODE_INDEX.md (interfaz pública) + test unitario IoU.
Exclusiones: SAM runtime, HITL UI, train, microservicios, WhatsApp, auto-deploy, reescribir main.py.

[REGLAS]
Type hints · try/except · cero hardcode de umbrales · capas inputs/core/outputs
BBox basta para v1 · Calibrar ≠ entrenar

[GOBERNANZA]
Criticidad: media · Revisión humana antes de demo · Commit solo si se pide

[VERIFICACIÓN]
- tests/: IoU dentro/fuera/borde
- smoke: runner --mode file con zona que cubra persona → ≥1 evento; zona vacía → 0
- timestamp ISO 8601 TZ · event_schema_version 2.0
- Rollback: desactivar módulo en modules_active
```

### C2 — Care & Fall canónico

```text
[CONTEXTO]
TRACK=COMERCIAL · Unidad C2 — Care estable / EventLogger canónico
Fuentes: AI_CONTEXT · CODE_INDEX §4 eventos · outputs/event_logger.py

[TAREA]
Asegurar que eventos de caída emitidos incluyan campos canónicos (event_schema_version, timestamp, camera_id, zone, compliance retention) y reduzcan dependencia de ratio crudo cuando YOLO ya trae is_falling.
Cablear PDF/email vía TriggerManager sin bloquear captura.
Actualizar CODE_INDEX si cambia schema emitido.
Exclusiones: fine-tune, M2, microservicios.

[REGLAS] Capas · Firebase opcional · escritura atómica JSONL
[GOBERNANZA] Criticidad media · commit si se pide
[VERIFICACIÓN] scripts/test_event_storage.py · un PDF de prueba · runner file mode con caída simulada
```

### C3 — Perimeter Guard + fix capas

```text
[CONTEXTO]
TRACK=COMERCIAL · Unidad C3 — Perimeter piloto + deuda D03
Fuentes: perimeter_detector · trigger_manager · CODE_INDEX reglas importación

[TAREA]
1) Estabilizar perimeter (línea) + after_hours → Notify/Critical según config.
2) Eliminar import outputs→inputs: IpSpeaker accesible sin violar capas (inyección/callback/adapter en runner o outputs sin importar inputs).
3) Tests/smoke de breach.
Exclusiones: intrusion_climb completo (A5), SAM, train.

[REGLAS] outputs NUNCA importa inputs
[GOBERNANZA] Criticidad media-alta (seguridad)
[VERIFICACIÓN] grep verifica capas · demo perimeter · trigger no bloquea FPS
```

### C4 — Aqua mínimo (`pool`)

```text
[CONTEXTO]
TRACK=COMERCIAL · Unidad C4 — Aqua & Risk mínimo
Dependencia: C1 Done

[TAREA]
Tipo zona pool + evento al IoU persona∩pool con persistencia; alert Notify; HUD claro.
No clasificar “niño”; no dataset de menores sin protocolo.
Exclusiones: demografía, train, SAM edge.

[VERIFICACIÓN] file mode zona pool · 0 eventos fuera de agua · logs ISO8601
```

### C5 — Empaque edge

```text
[CONTEXTO]
TRACK=COMERCIAL · Unidad C5 — Docker/compose runner + runbook
[TAREA] Documentar y endurecer scripts/docker-compose + runbook commissioning M0 (sin secretos en repo).
[VERIFICACIÓN] compose up smoke en entorno local · README/runbook actualizado
```

### C6 — Tests smoke

```text
[CONTEXTO]
TRACK=COMERCIAL · Unidad C6
[TAREA] Suite mínima: IoU M0 · EventLogger · perimeter · (opcional) trigger mock.
[VERIFICACIÓN] pytest o scripts equivalentes en CI local documentado
```

---

## 4. Prompts F2 (académico) — solo con TRACK_ACADEMICO

### A1 — Curiosidad + HITL

```text
[CONTEXTO] TRACK=ACADEMICO · A1 · Dependencia C1
[TAREA] Motor de curiosidad (multi-política) + cola + UI/API mínima HITL; extender learning_dataset; reviewer_id.
Exclusiones: auto-promote, train en edge, mezclar tenants.
[VERIFICACIÓN] encolar sample sintético · label humano en manifest · no dispara sirena por curiosidad
```

### A2 — Gold-set + contrato datos

```text
[CONTEXTO] TRACK=ACADEMICO · A2
[TAREA] Splits train/val/gold; gold nunca en train; purge por sitio; labels ricos.
[VERIFICACIÓN] intento de export que excluya gold · doc de contrato en LEARNING_WORKFLOW
```

### A3 — M2 taxonomía + ModelCard

```text
[CONTEXTO] TRACK=ACADEMICO · A3
[TAREA] Clasificador fino sobre crop; domain mix; ModelCard; NO reentrenar YOLO-seg completo.
[VERIFICACIÓN] métricas en gold-set · ModelCard con SHA256 placeholder
```

### A4 — Promote disciplinado

```text
[CONTEXTO] TRACK=ACADEMICO · A4
[TAREA] Pipeline: train hub → eval gold → shadow → canary → promote → rollback FAR.
PROHIBIDO deploy masivo tras N fotos.
[VERIFICACIÓN] shadow no dispara triggers · rollback documentado
```

### A5 / A6 / A7 / A8

Usar plantilla §2 con IDs de [06_PLAN…](docs/REFORMULACION/06_PLAN_DUAL_TRACK.md): recetas M3, servicios lógicos, registry pesos, experimento título.

---

## 5. Definition of Done (código)

- [ ] Type hints en API pública  
- [ ] Capas de importación intactas  
- [ ] Sin secretos  
- [ ] CODE_INDEX actualizado si cambió interfaz  
- [ ] Prueba de la unidad en verde o evidencia manual registrada  
- [ ] AI_CONTEXT §6 actualizado (último hito / siguiente)  

## 6. Anti-alcance permanente

SAM en cámara · auto-deploy · Guerrilla · train en edge · clase YOLO “ladrón_saltando_muro” · mezclar datasets de clientes.
