# Visión de Demo y Escalamiento del Producto

## Visión

Vigilante Digital es una plataforma modular de vigilancia inteligente. Su filosofía es simple: un guardia digital analiza cada cuadro o grupo de cuadros, todo el día, sin cansancio, y convierte video pasivo en eventos accionables.

No es solo CCTV. Es percepción operacional.

## Demo Actual

La maqueta debe demostrar tres ideas:

1. El sistema entiende eventos visuales.
2. El sistema actúa: alerta, documenta y dispara protocolos.
3. El sistema es modular: cada nuevo caso de uso es un módulo.

## Módulos de Demo

### Caída

Detecta postura compatible con caída usando pose humana y validación temporal.

Valor comercial:

- residencias,
- faenas industriales,
- bodegas,
- minería,
- instituciones con adultos mayores.

### Polera Roja por 1 Segundo

Detecta presencia persistente de color específico.

Valor comercial:

- control de uniforme/EPP,
- seguimiento de cuadrillas,
- pruebas de segmentación por atributos,
- demostración simple y muy visual.

### Cambio de Luz/Semáforo

Detecta cambios de color en una región fija.

Valor comercial:

- lectura de tableros,
- semáforos industriales,
- balizas,
- estados de máquinas,
- señales visuales en plantas.

### Perímetro

Detecta cruces de línea virtual.

Valor comercial:

- zonas restringidas,
- bodegas,
- parcelas,
- faenas,
- subestaciones eléctricas.

## Escalamiento del Producto

### Etapa 1 — Demo Local

- 2 cámaras IP/webcam.
- OpenCV + YOLO/MediaPipe.
- JSON local.
- PDF manual.
- Triggers opcionales.

### Etapa 2 — Piloto Real

- 4-8 cámaras IP.
- Guardado local con rotación.
- Dashboard web.
- WhatsApp/email/bocina por microservicio.
- Dataset real con revisión humana.

### Etapa 3 — Producto Operacional

- Microservicio por cámara o por zona.
- Bus de eventos.
- Inferencia GPU centralizada.
- Integración VMS/CCTV existente.
- Segmentación avanzada.
- Reportería ejecutiva.
- Cumplimiento Ley 21.663, ISO 27001 e IEC 62676.

### Etapa 4 — Producto Inteligente

- Aprendizaje continuo supervisado.
- Entrenamiento por cliente y por vertical.
- Detección térmica.
- Detección de armas.
- Detección de EPP.
- Detección de robo o manipulación.
- Modelos por zona crítica.

## Arquitectura Escalable Propuesta

```text
Cámaras IP/RTSP
    ↓
camera-agent
    ↓
vision-inference-service
    ↓
event-bus
    ↓
event-store + report-service + notification-service + dashboard
    ↓
human-review + dataset-service + training-pipeline
```

## Producto para Empresa de Seguridad

La empresa de seguridad no solo compra una IA. Puede transformarse en socio operativo:

- aporta instalaciones reales,
- define casos de uso,
- valida eventos con guardias,
- entrega datos para entrenar,
- abre acceso a clientes industriales.

La propuesta correcta es un piloto conjunto de 90 días:

1. Instalar en entorno real.
2. Documentar casos.
3. Medir precisión.
4. Crear dataset.
5. Entrenar modelo vertical.
6. Presentar primer producto comercial.

