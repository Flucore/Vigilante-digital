# Visión de producto y escala

| Campo | Valor |
|---|---|
| Estado | Vigente (elevado Unidad 3 · 2026-08-16) |
| Charter | [REFORMULACION/01_CHARTER.md](REFORMULACION/01_CHARTER.md) |
| Arquitectura | [REFORMULACION/05_ARQUITECTURA_Y_MEMORIA_SITIO.md](REFORMULACION/05_ARQUITECTURA_Y_MEMORIA_SITIO.md) |
| Comercial | [REFORMULACION/04_VISION_COMERCIAL_Y_VENTAS.md](REFORMULACION/04_VISION_COMERCIAL_Y_VENTAS.md) |

## Visión

Vigilante Digital (FluCore) es una plataforma modular de vigilancia inteligente: un vigilante digital analiza el video 24/7, convierte lo pasivo en **eventos accionables y auditables**, y acumula **criterio de sitio** con supervisión humana.

> Una cámara con IA ve clases universales. Vigilante Digital acumula criterio de este sitio.

No es solo CCTV. Es percepción operacional + memoria de sitio.

## Dual-Track

| Track | Foco |
|---|---|
| **Comercial** | Edge: Care, Perimeter, Aqua (M0), triggers estables |
| **Académico** | MLOps HITL, promote, servicios lógicos, tesis medible |

## Demo / piloto: tres ideas

1. El sistema entiende **eventos** (no solo graba).  
2. El sistema **actúa** (log, PDF, email, bocina/webhook).  
3. El sistema es **modular** y puede **calibrarse al sitio** (M0), no solo detectar COCO.

### Módulos de entrada (mensaje)

| Módulo | Valor | Estado honesto |
|---|---|---|
| Care & Fall | Caídas / ISO 45001 / evidencia | Más maduro |
| Perimeter Guard | Intrusión horario no hábil | Línea hoy; muro irregular = M0+M3 |
| Aqua & Risk | Piscina / riesgo hídrico | Rojo hasta M0 usable |
| Demo color/luz | Explicabilidad comercial | HSV; no el diferenciador |

## Escalamiento (etapas reformuladas)

### Etapa 1 — Demo local (hoy)

- 1–2 cámaras / archivo.  
- `runner.py` + YOLO/MediaPipe.  
- JSONL / PDF / triggers opcionales.

### Etapa 2 — Piloto edge (Track Comercial)

- 2–8 cámaras.  
- Care + Perimeter estabilizados.  
- **Aprendizaje-A:** M0 zonas/máscara + IoU.  
- HITL mínimo (manifiesto / scripts).  
- Sin auto-deploy de pesos.

### Etapa 3 — Producto operacional

- Indexación forense + API.  
- Notificaciones confiables.  
- Cumplimiento explícito (retención, cartelería, threat model).  
- Desacople gradual a servicios lógicos (bus de eventos cuando el contrato de datos exista).

### Etapa 4 — Plataforma de las cuatro memorias (reemplaza “lista de detectores”)

La etapa inteligente **no** es “añadir armas + térmico + EPP a la lista”.  
Es la plataforma:

- M0 geometría · M1 percepción · M2 taxonomía · M3 conducta  
- Motor de Curiosidad · Dashboard HITL · Gold-set · Shadow/Canary/Promote  

Detectores verticales (térmico, armas, EPP) se agregan **sobre** esa plataforma, no en su lugar.

## Arquitectura escalable (lógica)

```text
Cámaras
  → camera-ingest
  → vision-inference (M1) + zones (M0) + recipes (M3)
  → event-bus (cuando corresponda)
  → event-store · notify · forensic · dashboard
  → HITL · dataset · training-pipeline (hub)
```

No exigir 4 microservicios en el primer sprint comercial.

## Socio: empresa de seguridad

- Aporta instalaciones y validación de guardias (HITL).  
- No “entrega datos para que el modelo aprenda solo”.  
- Piloto 90 días: instalar → medir FAR/recall → calibrar M0 → dataset auditado → (si aplica) M2 con promote disciplinado.

## Anti-promesas

- Aprende solo · Auto-deploy tras N fotos · Guerrilla en seguridad crítica · FAR cero garantizado.
