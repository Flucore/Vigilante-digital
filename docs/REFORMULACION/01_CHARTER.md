# 01 — Project Charter · Vigilante Digital

| Campo | Valor |
|---|---|
| Estado | Vigente (ola DOCS) |
| Versión | 1.0 |
| Fecha | 2026-08-16 |
| Dueño | FluCore |
| Protocolo | PROTOCOLO-FLUCORE-v1 · Vibe Coding · Guerrilla **excluido** |
| Relacionado | [AI_CONTEXT.md](../../AI_CONTEXT.md) · [00_PROMPT_MAESTRO.md](00_PROMPT_MAESTRO.md) |

---

## 1. Propósito

Convertir cámaras existentes en sensores con **criterio técnico de sitio**: detectar, indexar y actuar en el segundo cero, y aprender —con supervisión humana— qué es *este* lugar y *este* cliente.

No vendemos cámaras. Vendemos continuidad operativa, compliance y prevención activa.

## 2. Posicionamiento

> Una cámara con IA ve clases universales. Vigilante Digital acumula criterio de este sitio.

| Ellos (cámara con IA) | Nosotros |
|---|---|
| Clases COCO / línea recta | Memoria geométrica del sitio (M0) |
| Alerta genérica | Eventos compuestos + triggers (M3 + TriggerManager) |
| Firmware cerrado | HITL + dataset versionado + promote disciplinado |
| Autopsia o “person detected” | Video → data auditable + FAR medible |

**SKU conceptual:** *Criterio de Sitio* = M0 + M1 + HITL + (opcional) M2 taxonomía + M3 conducta.

## 3. Dual-Track

| Track | Horizonte | Objetivo | Regla |
|---|---|---|---|
| **Comercial** | Verano 2026 · liquidez | Edge vendible (Mini-PC/Jetson): Perimeter, Aqua & Risk, Care & Fall | Hecho > perfecto; reutilizar `core/`; sin auto-deploy de pesos |
| **Académico** | Mediano plazo · Proyecto de Título | Arquitectura escalable + MLOps Active Learning gobernado | Servicios lógicos → luego despliegue; gold-set + shadow/canary |
| **DOCS** | Ola actual | Congelar gobierno documental en este repo | Sin features de código hasta Unidad 5 Done |

Antes de cualquier cambio `.py`: el humano declara `TRACK_COMERCIAL` o `TRACK_ACADEMICO`.

## 4. Dolores que resolvemos

| # | Dolor | Solución de producto | Mercado inicial |
|---|---|---|---|
| 1 | Cámaras = autopsia visual | **Perimeter Guard** — detección + webhook/relé en segundo cero | Comercio VIP, bodegas |
| 2 | Riesgo vital sin vigilancia humana (piscinas, niños) | **Aqua & Risk** — borde irregular (M0) + persona/máscara ∩ zona | Parcelas Colina/Chicureo |
| 3 | Riesgo legal / accidentes no reportados | **Care & Fall** + PDF auditable (ISO 8601, custodia) | Faenas, salud/ISO 45001 |

## 5. Éxito (Definition of Success)

### Comercial (piloto vendible)

- Demo estable 1–2 cámaras: caída **o** perímetro **o** zona piscina con IoU.
- Alerta no bloqueante (email/webhook/bocina según config) + evidencia local.
- Commissioning M0 en minutos (polígono/máscara por cámara), sin reentrenar.
- FAR no prometido numéricamente hasta DECISIÓN HUMANA; se **mide** y se reporta.
- Firebase opcional; el piloto funciona on-prem.

### Académico (nota máxima / aporte)

- Hipótesis medible: curiosidad + HITL + promote reduce FAR sin degradar recall crítico.
- Contrato de datos (gold-set, tenant isolation, model card, rollback).
- Documentación reproducible de M0–M3 y del loop (no solo demos).
- Desacoplamiento hacia servicios lógicos demostrable (no hace falta 4 repos el día 1).

## 6. Límites (fuera de alcance explícito)

- Guerrilla / atajos incompatibles con biometría, menores o seguridad crítica.
- Prometer “el sistema aprende solo” o auto-deploy sin shadow/canary/gold-set.
- Sustituir la infraestructura de cámaras del cliente.
- Identidad facial como producto (salvo base legal y alcance contractual explícitos).
- Mezclar datasets de clientes para “subir mAP”.
- Fine-tuning en el nodo edge.
- Cobertura 24/7 de soporte sin capacidad FluCore contratada.

## 7. Principios inamovibles

1. Calibrar ≠ entrenar.
2. Detectar grueso → clasificar fino → componer el evento.
3. El humano es fuente de verdad; el modelo es hipótesis versionada.
4. Sin gold-set no hay promote.
5. El edge infiere y encola; el hub (o job GPU) entrena.
6. Capas de código: `inputs/ → core/ → outputs/`; `runner.py` canónico.
7. Cumplimiento Chile (datos, ciber, vigilancia) es diseño, no anexo.

## 8. Actores

| Rol | Responsabilidad |
|---|---|
| Fundador FluCore | Prioridad comercial, pricing, excepciones, promote final en pilotos |
| Operador / instalador | Commissioning M0, salud del nodo |
| Revisor HITL | Auditar curiosidad y alertas; etiquetar; no envenenar dataset |
| Cliente admin | Validar alertas de negocio; no opera pesos sin acuerdo |
| IA asistente | Unidades acotadas bajo Vibe Coding; sin commits no pedidos |

## 9. Relación con documentos

| Documento | Rol |
|---|---|
| Este Charter | Qué somos y qué es éxito |
| `02_AUDITORIA_v25.md` | Dónde estamos hoy |
| Unidades 2–5 | Comercial, arquitectura, plan, título, operación equipo |
| `MASTER_DEVELOPMENT_PLAN.md` | Planificación previa; vigencia formal en Unidad 5 |

## 10. DECISIONES HUMANAS (abiertas)

- FAR máximo aceptable por vertical (comercio / parcela / faena).
- Quién autoriza promote en piloto vs producción.
- Empaquetado y precio del SKU Criterio de Sitio.
- Alcance y calendario del Proyecto de Título (institución/rúbrica).
