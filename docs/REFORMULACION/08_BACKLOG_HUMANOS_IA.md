# 08 — Backlog humanos vs IA · prompts y pruebas

| Campo | Valor |
|---|---|
| Estado | Vigente · **ola DOCS cerrada** |
| Versión | 1.0 |
| Fecha | 2026-08-16 |
| Plan | [06_PLAN_DUAL_TRACK.md](06_PLAN_DUAL_TRACK.md) |
| Contexto IA | [../../AI_CONTEXT.md](../../AI_CONTEXT.md) |

---

## 1. Quién hace qué

| Rol | Calibra M0 | Audita HITL | Enseña M2 | Autoriza promote | Código | Cotiza / vende |
|---|---|---|---|---|---|---|
| Fundador FluCore | Aprueba | Spot-check | Prioriza | **Sí (piloto)** | Revisa diff crítico | **Sí** |
| Humano técnico | **Sí** | **Sí** | Valida muestras | Propone | Implementa + review | Apoya demo |
| Humano comercial | No | No | No | No | No | **Sí** (con matriz readiness) |
| IA (Cursor) | Propone config/docs | No decide labels | Scaffold | **Nunca** | Unidades acotadas | No |

**Regla:** la IA no hace promote, no inventa precios, no mezcla tenants, no commit sin pedido explícito.

---

## 2. Plantilla de prompt (obligatoria)

```text
[CONTEXTO]
TRACK=COMERCIAL|ACADEMICO|DOCS
Unidad/ID: (ej. C1)
Fuentes: AI_CONTEXT.md · docs/REFORMULACION/06_PLAN_DUAL_TRACK.md · CODE_INDEX.md
Estado: (1–3 líneas)

[TAREA]
Una unidad coherente. Archivos permitidos: …
Exclusiones: …

[REGLAS]
Type hints · try/except I/O · sin hardcode · capas inputs/core/outputs
Calibrar ≠ entrenar · SAM no en edge 24/7 · sin auto-deploy
Antipatrones del glosario: prohibidos

[GOBERNANZA]
Criticidad: baja|media|alta|crítica
Revisión humana: quién
Commit: solo si se pide
Guerrilla: excluido

[VERIFICACIÓN]
Pruebas: (ver §4)
Evidencia: …
Rollback: …
```

---

## 3. DoD por tipo de tarea

| Tipo | Done cuando |
|---|---|
| **Docs** | Archivo en REFORMULACION o doc elevado; sin contradicción con Prompt Maestro; README/AI_CONTEXT actualizados |
| **Feature edge** | Type hints; no rompe capas; config/env; try/except; prueba smoke; CODE_INDEX si interfaz pública |
| **Trigger/notify** | No bloquea hilo de captura; falla externa no tumba runner; log WARNING+ |
| **M0 / zonas** | Zona en config versionable; IoU + persistencia; drift documentado; sin `.pt` nuevo |
| **HITL / dataset** | reviewer_id; label permitido; no gold-set en train; purge/tenant pensado |
| **Promote (solo F2)** | ModelCard + SHA256 + eval gold-set + shadow + canary + criterio rollback FAR |

---

## 4. Pruebas mínimas

| Cambio | Prueba mínima |
|---|---|
| Detector / IoU M0 | Unit: IoU sintético; manual: 1 video/archivo con zona conocida |
| EventLogger / schema | `scripts/test_event_storage.py` o equivalente; JSON con `event_schema_version` |
| Triggers | Mock/disable red; verificar que el loop de frames sigue |
| Config zonas | Cargar config inválida → error claro, no crash silencioso |
| Dataset add | `add_dataset_image.py` escribe manifest; path existe |
| Capa imports | Grep: `outputs` no importa `inputs` (tras fix D03) |

Sin evidencia ≠ hecho.

---

## 5. Cola prioritaria (post-DOCS)

| Orden | ID | Dueño principal | IA puede scaffolding | Prompt listo |
|---|---|---|---|---|
| 1 | **C1** M0 máscara + IoU | Humano técnico + IA | Sí | §6 abajo |
| 2 | **C2** Care canónico | Humano + IA | Sí | Usar plantilla §2 |
| 3 | **C3** Perimeter + fix capa trigger | Humano + IA | Sí | Usar plantilla §2 |
| 4 | **C4** Aqua `pool` | Humano + IA | Sí | Tras C1 |
| 5 | **C5** Empaque Docker/runbook | Humano | Parcial | — |
| 6 | **A1+** HITL completo | Académico | Sí | Solo `TRACK_ACADEMICO` |

---

## 6. Prompt listo — Unidad Comercial C1

```text
[CONTEXTO]
TRACK=COMERCIAL
Unidad: C1 — Aprendizaje-A / Memoria geométrica M0 usable
Fuentes: AI_CONTEXT.md · 05_ARQUITECTURA_Y_MEMORIA_SITIO.md · 06_PLAN_DUAL_TRACK.md · CODE_INDEX.md
Estado: Ola DOCS cerrada. Reutilizar perimeter_detector / intrusion_detector / zones en config.
Objetivo de producto: persona ∩ zona (pool|wall|geofence) con IoU + persistencia temporal → evento; sin train.

[TAREA]
Implementar M0 mínimo:
1) Extender config de zona para polígono normalizado + type (pool|wall|geofence|custom) si aún no basta.
2) Función pura en core/ (o reutilizar intrusion) que calcule intersección bbox-o-máscara ∩ polígono y persistencia.
3) Cablear en runner.py (o worker) para emitir evento canónico cuando se cumpla umbral (umbral en config.py/env).
4) Actualizar CODE_INDEX.md solo si hay interfaz pública nueva.
Archivos esperados: core/* zone/intrusion relacionado, config_loader si aplica, runner.py, demo_config/client ejemplo sin secretos, CODE_INDEX si aplica.
Exclusiones: SAM en runtime cámara, dashboard HITL, train, microservicios, WhatsApp, auto-deploy, main.py legado salvo nota.

[REGLAS]
Type hints · I/O defensivo · cero credenciales · capas respetadas
Calibrar ≠ entrenar · bbox puede bastar para IoU v1 · máscara seg opcional si ya hay
No ampliar a M2/M3 compuestos en esta unidad

[GOBERNANZA]
Criticidad: media
Revisión: humano técnico antes de demo cliente
Commit: solo si el humano lo pide

[VERIFICACIÓN]
- Test unitario IoU con polígono sintético (dentro / fuera / borde).
- Smoke manual: runner --mode file con zona que cubra persona → 1 evento; zona vacía → 0.
- Logs con timestamp ISO 8601 TZ.
- Rollback: revertir commit / desactivar módulo en modules_active.
```

---

## 7. Arranque de sesión post-DOCS

```text
TRACK=COMERCIAL · C1
Lee AI_CONTEXT.md y docs/REFORMULACION/08_BACKLOG_HUMANOS_IA.md §6
Ejecuta solo C1. Sin train ni HITL UI.
```
