# 07 — Proyecto de Título (área académica)

| Campo | Valor |
|---|---|
| Estado | Borrador controlado (pendiente datos institucionales) |
| Versión | 1.0 |
| Fecha | 2026-08-16 |
| Producto ancla | Vigilante Digital · FluCore |
| Track | **F2 Académico** (ver [06_PLAN_DUAL_TRACK.md](06_PLAN_DUAL_TRACK.md)) |
| Protocolo | PROTOCOLO-FLUCORE-v1 · Vibe Coding · Guerrilla excluido |

> Completar con **DECISIÓN HUMANA**: universidad, carrera, profesor guía, rúbrica, fechas de hitos formales.

---

## 1. Título tentativo

**“Aprendizaje activo gobernado con memoria de sitio para videovigilancia inteligente: reducción de falsas alarmas sin degradar recall de eventos críticos”**

Alternativa corta:  
**“Memoria de sitio y Active Learning supervisado en un sistema edge de visión para seguridad”**

## 2. Problema

Las cámaras con IA de fábrica detectan clases universales (persona, vehículo) y líneas perimetrales simples, pero no acumulan criterio del sitio (borde irregular de piscina, flota del cliente, conducta “escala este muro”).  
Los enfoques ingenuos de “reentrenar YOLO con N fotos y desplegar” producen olvido de clases, domain gap y riesgo de seguridad (modelo malo en producción).

## 3. Hipótesis

Un loop de **curiosidad multi-política + HITL + gold-set + promote (shadow/canary/rollback)**, sobre una arquitectura de **cuatro memorias (M0–M3)**, reduce el **FAR (falsas alarmas/cámara-hora)** en un sitio piloto **sin degradar el recall** de al menos un evento crítico definido (caída **o** intrusión en zona calibrada), frente a un baseline de detector genérico + reglas fijas sin aprendizaje gobernado.

## 4. Objetivos

### General

Diseñar, implementar en servicios lógicos y evaluar un pipeline de Active Learning gobernado para Vigilante Digital, demostrando mejora medible de FAR con custodia y promote disciplinado.

### Específicos

1. Formalizar M0–M3 y el contrato de datos (CuriositySample, GoldSet, ModelCard).  
2. Implementar motor de curiosidad + interfaz HITL mínima operable.  
3. Implementar promote con shadow/canary/rollback y métrica FAR.  
4. Ejecutar experimento en sitio/dataset controlado con baseline vs sistema propuesto.  
5. Documentar compliance (biometría, tenant isolation) como parte del diseño.

## 5. No-objetivos (explícitos)

- Sustituir el VMS/CCTV del cliente.  
- Identificación facial como aporte central.  
- Auto-deploy sin gold-set / shadow.  
- Guerrilla o “aprende solo”.  
- Microservicios masivos antes del contrato de datos.  
- Garantizar FAR cero.  
- Entrenar en el nodo edge.

## 6. Aportes esperados

| Tipo | Aporte |
|---|---|
| Conceptual | Memoria de sitio (4 memorias) vs “más clases COCO” |
| Metodológico | Curiosidad multi-política + promote auditable (no umbral único) |
| Ingenieril | Integración sobre monolito modular existente (`runner`, `learning_dataset`) hacia servicios lógicos |
| Empírico | Tabla FAR/recall baseline vs post-HITL con evidencia reproducible |
| Ético/legal | Diseño con retención, purge y separación de tenants |

## 7. Metodología (resumen)

1. **Baseline:** M1 + reglas fijas (sin M0 fino / sin curiosidad).  
2. **Tratamiento:** M0 calibrado + curiosidad + HITL + (si aplica) M2 liviano con promote.  
3. **Métricas:** FAR/cámara-hora; recall evento crítico; latencia alerta; carga HITL (minutos revisor).  
4. **Controles:** mismo sitio/cámaras; gold-set fijo; sin fuga train↔gold.  
5. **Amenazas a validez:** domain gap, envenenamiento de labels, drift de cámara — documentar y mitigar (M0 drift, reviewer_id).

Mapa a backlog: **A1–A4 + A8** en `06_PLAN_DUAL_TRACK.md`.

## 8. Hitos académicos (plantilla)

| Hito | Entregable | Track ID | Fecha |
|---|---|---|---|
| H0 | Estado del arte + marco teórico (memoria de sitio, AL, edge CV) | Docs | DECISIÓN HUMANA |
| H1 | Diseño arquitectura M0–M3 + amenazas | `05` + threat | |
| H2 | Prototipo HITL + curiosidad | A1–A2 | |
| H3 | Promote pipeline + ModelCard | A3–A4 | |
| H4 | Experimento y análisis | A8 | |
| H5 | Memoria / informe final + defensa | — | |

## 9. Evidencia mínima de “nota máxima” (criterio interno FluCore)

- [ ] Hipótesis falsable y métricas definidas antes del experimento.  
- [ ] Código y configs versionados; reproducibilidad documentada.  
- [ ] Gold-set y promote con rollback demostrado (aunque sea en lab).  
- [ ] Discusión de limitaciones (domain gap, biometría, capacidad solo-founder).  
- [ ] Separación clara Track Comercial vs aporte académico (no vender la tesis como SLA).

## 10. Relación con el producto comercial

| Comercial (F1) | Título (F2) |
|---|---|
| Cobra piloto Care/Perimeter/M0 | Usa el mismo edge como banco de pruebas |
| No promete auto-learn | Estudia y demuestra el loop completo |
| Métrica de venta: demo + caveats | Métrica científica: FAR/recall + método |

Sin F1 estable (sobre todo C1 M0), el experimento de título pierde validez ecológica.

## 11. DECISIONES HUMANAS (bloquean formalización universitaria)

- Institución, carrera, profesor guía, formato de memoria.  
- Evento crítico elegido para recall (fall vs zone breach).  
- Sitio/datos permitidos para experimento (anonimización).  
- Calendario de hitos vs Verano 2026 comercial.
