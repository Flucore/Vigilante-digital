# 04 — Visión comercial y ventas · Vigilante Digital

| Campo | Valor |
|---|---|
| Estado | Vigente (ola DOCS) |
| Versión | 1.0 |
| Fecha | 2026-08-16 |
| Dueño | FluCore |
| Tipo de venta actual | **Piloto controlado** (no producción estándar 24/7) |
| Relacionado | [01_CHARTER.md](01_CHARTER.md) · [02_AUDITORIA_v25.md](02_AUDITORIA_v25.md) · [03_GLOSARIO.md](03_GLOSARIO.md) |

> Alineado a FluCore `operaciones/MATRIZ-READINESS-VENTA.md`: verde solo con evidencia; sin evidencia = amarillo/rojo.

---

## 1. Oferta en una frase

**FluCore / Vigilante Digital** convierte las cámaras que el cliente ya tiene en un vigilante con criterio de sitio: alerta en el segundo cero, evidencia auditable y calibración del lugar —no solo “person detected”.

## 2. ICP (cliente ideal)

### Primario (Verano 2026)

| Segmento | Dolor dominante | Módulo de entrada |
|---|---|---|
| Comercio VIP / bodega de alto valor | Intrusión / horario no hábil | Perimeter Guard |
| Parcela lujo (Colina/Chicureo) o comunidad | Piscina / niños sin vigilancia | Aqua & Risk (tras M0) |
| Faena / instalación con ISO 45001 o RC | Caídas / incidentes no reportados | Care & Fall |

### Señales de buen encaje

- Decisor accesible y presupuesto para nodo edge + OPEX.
- Cámaras IP existentes (o disposición a 1–2 cams de piloto).
- Acepta piloto con caveats escritos (FAR no garantizado al inicio).
- Responsable interno para validar alertas / HITL liviano.

### No encaje / pausar

- “Garanticen cero falsas alarmas” o “aprende solo sin humanos”.
- Expectativa de sustitución total del sistema de CCTV.
- Menores + biometría sin base legal y proceso de consentimiento.
- Guerrilla / entrega overnight en seguridad crítica.
- Sin cartelería ni acuerdo de tratamiento de datos.

## 3. SKUs (qué se vende)

### Modelo económico (cerrado en plan maestro)

| Componente | Tipo | Nota |
|---|---|---|
| Nodo edge (Mini-PC/Jetson) | CAPEX | Preconfigurado |
| Licencia software por nodo | CAPEX / perpetua por instalación | Módulos activos según contrato |
| Soporte y actualizaciones | OPEX mensual | 8×5 remoto salvo contrato distinto |
| Commissioning Criterio de Sitio (M0) | Servicio | Calibración de zonas; **no** es train de modelo |
| Pack taxonomía / aprendizaje (M2) | Roadmap / académico→producto | Solo con HITL y domain mix; no auto-deploy |

### Paquetes de mensaje comercial

| Paquete | Incluye hoy (honesto) | No incluye |
|---|---|---|
| **Care Piloto** | Caída (YOLO-pose/MediaPipe), EventLogger, PDF/email opc., 1–2 cams | FAR contractual cerrado; identidad facial |
| **Perimeter Piloto** | Línea virtual + persona + triggers config | Muro irregular tipo “escaló el coronamiento” (eso es M0+M3) |
| **Aqua Roadmap** | Compromiso de M0 piscina en backlog comercial | Borde irregular listo para vender *ahora* |
| **Criterio de Sitio** | Narrativa + commissioning M0 cuando exista C1 | “Aprendizaje automático en cámaras” |

Precios numéricos: **DECISIÓN HUMANA** (no inventar en docs).

## 4. Qué se vende HOY vs qué no se promete

### Se puede ofrecer (piloto controlado · amarillo→verde con evidencia)

- Detección de caída en sitio controlado + log/PDF.
- Perímetro por **línea** + alerta Silent/Notify/(Critical si hardware listo).
- Edge local; Firebase opcional.
- Retención configurable (default orientativo 30 días).
- Soporte 8×5, no 24/7.

### No se promete (rojo)

- “El sistema aprende solo.”
- Auto-deploy de pesos a todas las cámaras tras N fotos.
- Aqua piscina irregular como feature entregada **hoy**.
- Distinguir Cat vs Komatsu en producción sin M2 + gold-set.
- Evento “zorro ataca gallinero” como clase mágica YOLO.
- Disponibilidad 99.5% **sin** medición ni runbook en ese sitio.
- Guerrilla / plazos incompatibles con datos sensibles.

## 5. Protocolo de alerta (mensaje al cliente)

| Nivel | Qué ocurre |
|---|---|
| Silent | Registro e indexación |
| Notify | Email/PDF / UI |
| Critical | Bocina/relé/webhook (si commissioning lo incluye) |

WhatsApp: roadmap; no vender como entregado salvo integración cerrada.

## 6. Matriz de readiness de venta (1 página)

```text
Oferta: Vigilante Digital — Piloto Edge v2.5
Segmento: comercio VIP / parcela / faena (elegir uno por propuesta)
Entorno: on-prem edge · Chile
Responsable: FluCore fundador + operador sitio
Fecha: 2026-08-16 · Reevaluar ≤ 90 días
Tipo: piloto controlado
```

| Dimensión | Estado | Evidencia / caveat |
|---|---|---|
| Alcance y exclusiones | Amarillo | Charter + esta matriz en la propuesta |
| Demo Care (caída) | Verde* | Demo reproducible; *FAR no SLA |
| Demo Perimeter (línea) | Amarillo | Funciona en runner; no = muro irregular |
| Aqua borde irregular (M0) | Rojo | Pendiente Aprendizaje-A / C1 código |
| Triggers email/PDF | Amarillo | Depende SMTP/config del cliente |
| Triggers bocina/webhook | Amarillo | Hardware/comisión requerida |
| Multi-cámara estable (N>2) | Amarillo | Runner existe; sin política GPU formal |
| Firebase | N/A u Amarillo | Opcional; piloto no depende |
| Cumplimiento datos / cartelería | Amarillo | Proceso cliente + contrato; no solo software |
| HITL / aprendizaje continuo | Rojo→Roadmap | Semilla `LearningDataset`; sin promote |
| Taxonomía flota (M2) | Rojo | Académico / post C–D |
| Auto-promote pesos | Rojo | Prohibido documentar/vender |
| Soporte 8×5 | Amarillo | Capacidad FluCore WIP; no 24/7 |
| Soporte 24/7 | Rojo | Fuera de capacidad salvo contrato nuevo |
| Seguridad supply-chain `.pt` | Amarillo | Threat model; checksum T-T04 pendiente |
| Precio / margen | DECISIÓN HUMANA | Completar antes de cotizar |

**Regla FluCore:** un demo no prueba operación. Cada celda verde exige evidencia fechada en el expediente del piloto.

## 7. Motions de venta (eficientes)

1. **Diagnóstico 30 min:** dolor (1–3), cams, horario, quién responde alertas.
2. **Demo acotada:** Care **o** Perimeter — no los tres a la vez.
3. **Propuesta piloto:** alcance, exclusiones, matriz readiness, hito M0 si parcela.
4. **Cobro:** anticipo commissioning + nodo; OPEX desde go-live piloto.
5. **No regalar** diseño de zonas/taxonomía complejo en preventa (FluCore F0/F1).

## 8. Objeciones frecuentes

| Objeción | Respuesta |
|---|---|
| “Mi cámara ya tiene IA” | Detecta clases; no calibra *tu* piscina ni *tu* flota ni deja evidencia/HITL gobernado. |
| “Quiero que aprenda solo” | Aprendizaje sin humano envenena el sitio. Vendemos HITL + criterio. |
| “Garantice 0 falsas alarmas” | Medimos FAR; lo reducimos con M0 y auditoría. No garantizamos cero. |
| “Subo 300 fotos del catálogo” | Sin crops CCTV del sitio no hay promote (domain gap). |

## 9. DECISIONES HUMANAS (comerciales)

- Precio CAPEX/OPEX y markup por vertical.
- FAR interno objetivo (aunque no esté en contrato).
- Primer vertical de liquidez: comercio vs parcela vs faena.
- Quién firma acta de aceptación del piloto.
