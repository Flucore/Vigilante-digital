# 06 — Plan Dual-Track

| Campo | Valor |
|---|---|
| Estado | Vigente · ola DOCS **cerrada** |
| Versión | 1.1 |
| Fecha | 2026-08-16 |
| Dueño | FluCore |
| Relacionado | [01_CHARTER.md](01_CHARTER.md) · [02_AUDITORIA_v25.md](02_AUDITORIA_v25.md) · [05_ARQUITECTURA…](05_ARQUITECTURA_Y_MEMORIA_SITIO.md) · [07_PROYECTO_TITULO.md](07_PROYECTO_TITULO.md) |

> **Regla de oro:** ninguna tarea F2/Académica (train job, bus de eventos, auto-promote, microservicios) entra en un sprint de liquidez comercial.  
> WIP FluCore: 1 proyecto principal + 1 entrega rápida + soporte.

---

## 1. Vista de tracks

| Track | Meta | Horizonte | DoD de track |
|---|---|---|---|
| **DOCS** | Gobierno documental en repo | Ola actual (U0–U5) | Paquete REFORMULACION Done |
| **F1 Comercial** | Piloto edge cobrable | Verano 2026 | Care + Perimeter estables; M0 usable; triggers; runbook |
| **F2 Académico** | Título + plataforma MLOps | Mediano plazo | Curiosidad→HITL→gold-set→promote; servicios lógicos; evidencia medible |

---

## 2. F1 — Backlog comercial (liquidez)

Orden obligatorio. Hecho > perfecto. Reutilizar `core/`.

| ID | Entrega | Deudas | Estado / fuera de alcance |
|---|---|---|---|
| **C0** | Cerrar ola DOCS (Unidad 5) | D09 | **Done** |
| **C1** | M0 zonas + IoU (`core/zone_geometry.py`) | D05 | **Done** (sin SAM/train/HITL UI) |
| **C2** | Care estable: EventLogger canónico; PDF/email async | D04 | **Done** |
| **C3** | Perimeter + fix capa TriggerManager↔speaker | D03 | **Done** |
| **C4** | Aqua `pool` + M0 + Notify | D05, D06 | **Done** |
| **C5** | Empaque Docker + runbook | D08 | **Siguiente** · sin K8s/bus |
| **C6** | Tests smoke Care + Perimeter + M0 | D10 | Pendiente · sin suite MLOps |

### Sprints Aprendizaje en F1

| Sprint aprendizaje | En F1 | Nota |
|---|---|---|
| **A** M0 + IoU | **Sí = C1** | Demo diferenciadora vs cámara con IA |
| **B** Curiosidad + HITL | Solo **mínimo**: manifiesto + script; UI completa → F2 | No bloquear liquidez |
| **C** M2 + ModelCard | **No** | Académico |
| **D** Train/shadow/canary | **No** | Académico |

---

## 3. F2 — Backlog académico / plataforma

| ID | Entrega | Depende de |
|---|---|---|
| **A1** | Aprendizaje-B completo: motor de curiosidad + cola + dashboard HITL | C1 (zonas), semilla LearningDataset |
| **A2** | Contrato de datos: GoldSet, labels ricos, tenant purge, reviewer_id | A1 |
| **A3** | Aprendizaje-C: clasificador M2 + enseñanza masiva domain-mix + ModelCard | A2 |
| **A4** | Aprendizaje-D: train job hub + shadow + canary + rollback FAR | A3 |
| **A5** | M3 recetas: `intrusion_climb`, `predator_attack`, `machine_unlisted` (reglas) | C1, C3 |
| **A6** | Servicios lógicos desacoplados: camera-ingest · inference · notify (Docker); bus MQTT/Redis cuando A2 exista | C5 opcional |
| **A7** | Registry pesos: `custom_model_loader` + checksum SHA256 (T-T04) | A4 |
| **A8** | Evidencia de título: experimento FAR/recall pre/post HITL | A4 |

### Microservicios — política

Documentar e implementar como **servicios lógicos** primero.  
Partir procesos/Docker cuando el contrato de datos (A2) esté cerrado.  
No abrir 4 repos en C1–C6.

---

## 4. Diagrama temporal (orientativo)

```text
NOW     U5 DOCS ──► C1 M0 ──► C2 Care ──► C3 Perimeter ──► C4 Aqua ✓ ──► C5 empaque
                      │                      │
                      └──────────┬───────────┘
                                 ▼
                    A1 HITL ◄── paralelo académico cuando C1 estable
                                 ▼
                         A2 datos → A3 M2 → A4 promote → A8 tesis
                                 ▼
                              A5 M3 · A6 bus · A7 registry
```

---

## 5. Dependencias y riesgos de plan

| Riesgo | Mitigación |
|---|---|
| Meter train en sprint de piloto | Rechazo en review; ver anti-patrones |
| Aqua prometido antes de C1 | Matriz readiness roja hasta IoU demo |
| GPU única vs N cámaras | C5: límite documentado de cams/nodo |
| WIP > capacidad FluCore | 1 F1 activo + soporte; F2 en bloques acotados |
| Datos de menores en Aqua | Protocolo legal antes de dataset |

## 6. Criterio “listo para código”

**Listo.** Primera unidad = **C1** (`TRACK_COMERCIAL`).  
Prompt canónico: [`DESARROLLO_EJECUTABLE.md`](../../DESARROLLO_EJECUTABLE.md) §3 (espejo en `08_BACKLOG_HUMANOS_IA.md` §6).

## 7. Verificación de este plan

- [x] Perimeter / Aqua / Care en F1  
- [x] Aprendizaje A en F1; B mínimo en F1; C–D solo F2  
- [x] Microservicios / bus / promote fuera de sprints de liquidez  
- [x] Ninguna tarea F2 listada como entregable C1–C6  

## 8. DECISIONES HUMANAS

- Orden de vertical de primer piloto de pago (Care vs Perimeter vs parcela).  
- ¿C4 Aqua antes o después de C5 empaque?  
- Horas semanales reservadas a F2 vs F1.
