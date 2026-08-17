# 09 — Registro de riesgos y deuda (producto)

| Campo | Valor |
|---|---|
| Estado | Vigente · ola DOCS cerrada |
| Versión | 1.0 |
| Fecha | 2026-08-16 |
| Alcance | Vigilante Digital (espejo operativo; no copia FluCore entero) |
| Relacionado | [02_AUDITORIA_v25.md](02_AUDITORIA_v25.md) · [../../THREAT_MODEL.md](../../THREAT_MODEL.md) |

Leyenda severidad: **A** alta · **M** media · **B** baja.  
Estado: abierto | mitigando | aceptado | cerrado.

---

## 1. Riesgos

| ID | Riesgo | Severidad | Estado | Tratamiento |
|---|---|---|---|---|
| R01 | Prometer Aqua/aprendizaje antes de C1 | A | abierto | Matriz readiness; ventas con caveats |
| R02 | Domain gap (catálogo ≠ CCTV) → modelo frágil | A | abierto | Domain mix obligatorio; no promote sin in-situ |
| R03 | Envenenamiento de dataset (labels malos / insider) | A | abierto | reviewer_id; sample audit; gold-set separado |
| R04 | Supply-chain `.pt` adulterado (T-T04) | A | abierto | SHA256 + ModelCard antes de cargar; A7 |
| R05 | Drift de cámara invalida M0 sin aviso | M | abierto | `zone_calibration_drift`; recalibración |
| R06 | FAR alto tumba confianza del piloto | A | abierto | Medir FAR; M0+HITL; no SLA numérico prematuro |
| R07 | Datos de menores (piscina) sin base legal | A | abierto | Protocolo legal antes de dataset; cartelería |
| R08 | Mezcla multi-tenant en train | A | abierto | Tenant isolation; prohibido modelo global sin opt-in |
| R09 | Violación capas (`trigger`→`inputs`) | M | **cerrado** | Fix C3: `outputs/http_speaker.py` |
| R10 | Capacidad FluCore (WIP) vs 2 tracks | M | abierto | 1 F1 activo; F2 en bloques |
| R11 | main.py legado confunde agentes | B | mitigando | AI_CONTEXT + CODE_INDEX: runner canónico |
| R12 | Guerrilla en seguridad crítica | A | cerrado* | Selector: excluido (*mantener disciplina) |

---

## 2. Deuda técnica (desde auditoría)

| ID | Deuda | Track | Sprint/ID |
|---|---|---|---|
| D01 | Heurísticas rígidas | Comercial | C1–C4 |
| D02 | main.py legado | Docs/cleanup | Nota; no prioritario |
| D03 | TriggerManager importa inputs | Comercial | **C3 Done** |
| D04 | EventLogger fall-centric / schema | Comercial | C2 |
| D05 | Sin M0 máscara irregular | Comercial | **C1** |
| D06 | Módulos core poco cableados | Comercial | C1, **C4 Done** (aqua) |
| D07 | Sin curiosidad/gold-set/promote | Académico | A1–A4 |
| D08 | GPU/backpressure multi-cam | Ambos | C5 |
| D09 | Docs raíz desalineadas | DOCS | **Mitigado** por REFORMULACION |
| D10 | Tests escasos | Ambos | C6 + cada PR |

---

## 3. Amplificación threat model (notas)

Sin reescribir `THREAT_MODEL.md` completo en esta unidad:

| Activo / amenaza | Nota |
|---|---|
| A-07 Pesos | Ampliar a **pesos + datasets + adapters** |
| Nueva | Dataset poisoning (R03) |
| Nueva | Supply-chain `.pt` (R04 / T-T04) |
| A-02 Biométricos | CuriositySample y HITL heredan controles de retención/purge |

Actualización formal de `THREAT_MODEL.md`: tarea humana o unidad corta post-C1.

---

## 4. Excepciones

Ninguna excepción Guerrilla registrada.  
Toda desviación de promote disciplinado requiere registro escrito del fundador.

---

## 5. Revisión

- Revisar este registro al cerrar cada ID C* / A* o ante incidente.  
- Máx. 90 días sin revisión si hay piloto activo.
