# COMPLIANCE — Marco Legal y Normativo
## Vigilante Digital IA — Sistema de Vigilancia Inteligente

**Versión:** 1.0  
**Fecha:** Abril 2026  
**Ámbito:** Chile — Aplicación en instalaciones privadas (parcelas, empresas, industria, minería)

---

## 1. Marco Legal Chileno Aplicable

### 1.1 Ley 19.628 — Protección de la Vida Privada (datos personales)

La ley establece que las imágenes de personas constituyen **datos personales**. Las imágenes que permiten identificar a una persona son consideradas **datos sensibles** bajo la jurisprudencia chilena.

**Obligaciones del operador del sistema:**

| Obligación | Requisito | Implementación en el sistema |
|---|---|---|
| Finalidad declarada | El sistema solo puede usarse para el fin declarado (seguridad) | `demo_config.json` → campo `purpose` |
| Información al titular | Cartelería visible en zona vigilada | Cartelería física (fuera del software) |
| Plazo de conservación | No superior al necesario para la finalidad | `config.DATA_RETENTION_DAYS` (default 30) |
| Seguridad de los datos | Proteger contra acceso no autorizado | Logs en EventLogger, Firebase con auth |
| Derecho de acceso | Titular puede solicitar sus datos | Procedimiento operacional (no automatizado aún) |

### 1.2 Ley 21.663 — Nueva Ley de Protección de Datos Personales (2024)

Actualiza y reemplaza parcialmente la Ley 19.628. Puntos clave:

- **Base de licitud**: el tratamiento de datos en contexto de vigilancia de seguridad se basa en el **interés legítimo** del responsable (Art. 13), siempre que se respeten los derechos del titular.
- **Datos biométricos**: las imágenes de rostros con capacidad de identificación son datos biométricos (categoría especial). Requieren medidas de seguridad reforzadas.
- **Evaluación de impacto (PIA)**: obligatoria para tratamientos que impliquen vigilancia sistemática de personas en espacios públicos o de trabajo.
- **Delegado de Protección de Datos**: recomendado para clientes industriales y mineros.
- **Notificación de brechas**: al Consejo para la Transparencia en caso de filtración de datos.

**Acciones requeridas en el sistema:**
```
[x] Timestamps ISO 8601 en todos los eventos
[x] Retención configurable (DATA_RETENTION_DAYS)
[ ] Proceso de eliminación automática de snapshots vencidos (TODO: scripts/cleanup_old_data.py)
[ ] Registro de accesos al sistema de consulta de eventos
[ ] Evaluación de impacto en privacidad (PIA) para cada cliente
```

### 1.3 Ley 19.303 — Establece Obligaciones a Entidades que Guarden Valores

Regula empresas de seguridad privada. La OS-10 de Carabineros de Chile supervisa:

- Instalación de sistemas CCTV en recintos comerciales e industriales
- Operadores deben contar con **autorización OS-10**
- Los eventos grabados son admisibles como prueba en proceso penal (cadena de custodia)

**Requisito para clientes del sistema:**
> El cliente que opera el sistema Vigilante Digital debe ser o contar con una empresa de seguridad autorizada por la OS-10, o el sistema debe operar bajo supervisión de dicha empresa.

### 1.4 Ley 21.459 — Delitos Informáticos (2022)

- Acceso no autorizado a sistemas: hasta 541 días de presidio
- Interceptación de comunicaciones: hasta 3 años
- El sistema debe protegerse con autenticación y no exponer streams a redes públicas

**Controles implementados:**
- Streams de cámara solo en red local (no expuestos a Internet)
- Firebase con autenticación via service account
- No transmisión de imágenes a terceros sin autorización

### 1.5 DFL N°1/2006 — Código del Trabajo (Art. 154 bis)

Cuando el sistema se instala en ambientes laborales:

- El empleador **debe informar** a los trabajadores sobre la existencia del sistema de vigilancia
- Esto se hace mediante el **Reglamento Interno** o comunicación directa
- No puede usarse como único medio para sancionar disciplinariamente
- El Comité Paritario de Seguridad debe ser informado (si aplica)

---

## 2. Normas ISO Aplicables

### 2.1 IEC 62676 — Video Surveillance Systems for Security Applications

La norma más relevante para sistemas CCTV con IA.

| Parte | Contenido | Relevancia |
|---|---|---|
| IEC 62676-1-1 | Requisitos del sistema y rendimiento | Alta — define calidad mínima de imagen |
| IEC 62676-1-2 | Compresión de video y streaming | Media — aplica a streams IP |
| IEC 62676-4 | Directrices de diseño de aplicaciones | Alta — diseño del sistema |

**Requisitos de imagen para identificación (IEC 62676-1-1):**
- Identificación de personas: mínimo 25 px/m (píxeles por metro)
- Reconocimiento facial: mínimo 80 px/m
- Detección general: mínimo 6 px/m

**Recomendación para el demo:** Cámaras a 720p, personas a no más de 5 metros de distancia.

### 2.2 ISO/IEC 27001:2022 — Seguridad de la Información

Sistema de Gestión de Seguridad de la Información (SGSI).

**Controles implementados en Vigilante Digital:**

| Control ISO 27001 | Implementación |
|---|---|
| A.8.2 Clasificación de información | Eventos de seguridad = Confidencial |
| A.8.3 Manejo de medios | Snapshots en carpeta protegida |
| A.8.5 Autenticación segura | Firebase service account + env vars |
| A.8.12 Prevención de fuga de datos | Sin transmisión externa de imágenes |
| A.8.15 Logging | EventLogger con timestamps |
| A.8.16 Monitoreo de actividades | Registro de eventos en Firestore |

**Pendiente para clientes corporativos:**
- Cifrado de snapshots en reposo (AES-256)
- Política de contraseñas para acceso al panel
- Plan de respuesta a incidentes documentado

### 2.3 ISO/IEC 27701:2019 — Gestión de Privacidad

Extensión de ISO 27001 para privacidad de datos. Establece:

- **PIMS (Privacy Information Management System)**: gestión de información personal
- Mapeo de flujos de datos personales (Data Flow Mapping)
- Evaluación de impacto en privacidad (DPIA/PIA)

**Para el sistema:**
```
Datos procesados: video en tiempo real, snapshots JPG, eventos JSON
Propósito: seguridad y protección de personas
Base legal: interés legítimo / contrato de servicio
Retención: configurable (default 30 días)
Transferencias: Firebase (Google Cloud) — requiere cláusulas contractuales
```

### 2.4 ISO 45001:2018 — Seguridad y Salud en el Trabajo

La detección de caídas es una medida de control de **riesgo laboral** en:
- Bodegas y maestranzas
- Plantas industriales y mineras
- Espacios de trabajo con riesgo de caída

**Posicionamiento del producto:**
> Vigilante Digital IA actúa como una **medida de control** del tipo "detección" en la jerarquía de controles del riesgo (ISO 45001 Cláusula 8.1.2), complementando barreras físicas y EPP.

El sistema debe integrarse con el **Plan de Emergencia** del cliente:
- Alerta al sistema → notificación al supervisor → protocolo de respuesta
- El tiempo de respuesta es auditable (timestamp del evento vs. acción tomada)

### 2.5 ISO 31000:2018 — Gestión de Riesgos

Marco para identificar, analizar y tratar riesgos. Aplicado al sistema:

| Riesgo | Probabilidad | Impacto | Tratamiento |
|---|---|---|---|
| Falso positivo (alarma innecesaria) | Alta (sin YOLO) | Bajo | Validación temporal N frames |
| Falso negativo (evento no detectado) | Media | Alto | Motor YOLO + monitoreo continuo |
| Falla de cámara IP | Media | Alto | VideoStream con reconexión automática |
| Pérdida de conectividad Firebase | Media | Bajo | Cola local JSON + sync posterior |
| Acceso no autorizado al sistema | Baja | Alto | Autenticación, red local, logs |

---

## 3. Cartelería Obligatoria (fuera del software)

Para cumplir con la Ley 19.628 y las directrices de OS-10, en cada zona vigilada debe instalarse señalética que indique:

```
┌─────────────────────────────────────────────────────┐
│  ZONA BAJO VIGILANCIA ELECTRÓNICA                   │
│                                                     │
│  Este recinto cuenta con sistema de cámaras de      │
│  seguridad con análisis inteligente de imágenes.    │
│                                                     │
│  Las imágenes son tratadas conforme a la            │
│  Ley 19.628 de Protección de Datos Personales.     │
│                                                     │
│  Responsable: [Nombre empresa / RUT]                │
│  Contacto:    [Email / Teléfono]                    │
└─────────────────────────────────────────────────────┘
```

---

## 4. Checklist de Compliance por Tipo de Cliente

### Parcelas y Propiedades Privadas
- [ ] Informar a trabajadores y visitantes habituales
- [ ] Retención máxima 30 días
- [ ] No cubrir zonas privadas (habitaciones, baños)

### Empresas e Instituciones
- [ ] Informar al Comité Paritario (si existe)
- [ ] Incluir en Reglamento Interno
- [ ] Designar Delegado de Protección de Datos
- [ ] PIA si hay vigilancia sistemática de empleados

### Industria y Minería
- [ ] Protocolo integrado con Plan de Emergencia
- [ ] Coordinación con Departamento de Prevención de Riesgos
- [ ] Cumplimiento con normas SERNAGEOMIN (si aplica)
- [ ] Auditoría anual del sistema

---

## 5. Roadmap de Compliance del Producto

| Hito | Plazo | Estado |
|---|---|---|
| Timestamps ISO 8601 en todos los eventos | Inmediato | Implementado |
| Retención configurable | Inmediato | Parcial (config.py) |
| Eliminación automática de datos vencidos | 30 días | Pendiente |
| Cifrado de snapshots en reposo | 60 días | Pendiente |
| Dashboard de auditoría (quién accedió a qué) | 90 días | Pendiente |
| PIA template para clientes | 30 días | Pendiente |
| Certificación ISO 27001 del servicio | 12 meses | Roadmap |

---

*Este documento es una guía de implementación. Para asesoría legal específica, consultar con abogado especialista en protección de datos y seguridad privada en Chile.*
