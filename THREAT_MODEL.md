# THREAT MODEL — Vigilante Digital v2.0

> **Propósito**: Identificar activos, amenazas y controles de seguridad del sistema.
> Revisión requerida ante: nuevas integraciones, cambios de topología, incidentes.
> Marco de referencia: ISO/IEC 27001:2022 · STRIDE · OWASP API Security Top 10

---

## 1. Alcance del sistema

| Componente | Descripción |
|------------|-------------|
| `vigilante-runner` | Proceso de detección de video (nodo edge) |
| `vigilante-api` | API REST FastAPI + Panel de Operador + WebSocket |
| `postgres` | Base de datos de detecciones y eventos |
| `nginx` | Reverse proxy TLS |
| Cámaras IP | Fuentes RTSP/ONVIF (hardware del cliente) |
| Hub Curicó | Servidor central de FuenApa (externo) |
| Operadores | Usuarios del panel web |

---

## 2. Activos a proteger

| ID | Activo | Clasificación | Valor |
|----|--------|---------------|-------|
| A-01 | Streams de video en vivo | Confidencial | Alto |
| A-02 | Metadatos de detección (quién, cuándo, dónde) | Datos personales biométricos | Muy Alto |
| A-03 | Eventos de seguridad y alertas | Confidencial | Alto |
| A-04 | Credenciales de cámaras (RTSP/ONVIF) | Secreto | Crítico |
| A-05 | API_SECRET_KEY y WEBHOOK_SECRET | Secreto | Crítico |
| A-06 | Base de datos PostgreSQL | Confidencial | Alto |
| A-07 | Pesos de modelos ML custom del cliente | Propietario | Alto |
| A-08 | Configuración del cliente (client_config.json) | Confidencial | Medio |

---

## 3. Modelo de amenazas (STRIDE)

### 3.1 Spoofing (Suplantación de identidad)

| ID | Amenaza | Componente afectado | Probabilidad | Impacto |
|----|---------|---------------------|-------------|---------|
| T-S01 | Acceso a API sin token válido | `/api/v1/*` | Media | Alto |
| T-S02 | WebSocket con token falso | `/operator/ws/live/{cam}` | Baja | Medio |
| T-S03 | Webhook falso sin firma HMAC | `/api/v1/webhook/trigger` | Media | Medio |
| T-S04 | Cámara IP suplantada en red local (ARP spoofing) | Runner / RTSP | Baja | Alto |

**Controles implementados:**
- Bearer token (`API_SECRET_KEY`) en todos los endpoints `/api/v1/` ✅
- Token en query param para WebSocket ✅
- HMAC-SHA256 (`WEBHOOK_SECRET`) para webhooks ✅
- _Pendiente_: autenticación mutual TLS para cámaras ONVIF críticas

---

### 3.2 Tampering (Manipulación de datos)

| ID | Amenaza | Componente afectado | Probabilidad | Impacto |
|----|---------|---------------------|-------------|---------|
| T-T01 | Modificación de registros en PostgreSQL | BD forense | Baja | Crítico |
| T-T02 | Inyección en parámetros de búsqueda (SQL injection) | `/api/v1/search` | Baja | Alto |
| T-T03 | Modificación del client_config.json | Configuración | Media | Alto |
| T-T04 | Reemplazo de pesos del modelo ML | `models/*.pt` | Baja | Muy Alto |

**Controles implementados:**
- Escritura atómica JSONL (mkstemp + os.replace) ✅
- Parámetros de búsqueda tipados y validados por Pydantic/FastAPI ✅
- psycopg2 usa prepared statements (no concatenación de SQL) ✅
- _Pendiente_: firma hash de client_config.json al iniciar
- _Pendiente_: checksum SHA256 de pesos `.pt` al cargar (custom_model_loader)

---

### 3.3 Repudiation (Repudio)

| ID | Amenaza | Componente afectado |
|----|---------|---------------------|
| T-R01 | Operador niega haber visto un evento | Panel de Operador |
| T-R02 | Sin registro de quién realizó una búsqueda forense | `/api/v1/search` |

**Controles implementados:**
- `audit_queries` table en PostgreSQL — registra endpoint, params, IP, user_id, timestamp ✅
- `acknowledge_event` endpoint — trazabilidad de eventos revisados ✅
- EventLogger con timestamps ISO 8601 + zona horaria ✅

---

### 3.4 Information Disclosure (Fuga de información)

| ID | Amenaza | Componente afectado | Probabilidad | Impacto |
|----|---------|---------------------|-------------|---------|
| T-I01 | API expuesta sin TLS en red externa | Nginx / API | Media | Crítico |
| T-I02 | Logs con imágenes o biometría de personas | Runner / API | Baja | Alto |
| T-I03 | .env con credenciales en repositorio git | Repositorio | Media | Crítico |
| T-I04 | Swagger UI expuesto en producción | `/docs` | Baja | Medio |
| T-I05 | Frames JPEG en logs del servidor | API | Baja | Alto |

**Controles implementados:**
- TLS forzado via Nginx (HTTP → HTTPS redirect) ✅
- `server_tokens off` en Nginx ✅
- Logs del servidor NO incluyen frames ni imágenes completas ✅
- `.env` en `.gitignore` ✅
- Swagger UI desactivado por defecto (`ENABLE_DOCS=false`) ✅
- Ley 21.663: biometría solo con consentimiento documentado ✅

**Controles pendientes:**
- Cifrado en reposo de la columna `metadata` JSONB (PostgreSQL pgcrypto)
- Rotación automática de `API_SECRET_KEY` cada 90 días

---

### 3.5 Denial of Service (Denegación de servicio)

| ID | Amenaza | Componente afectado | Probabilidad |
|----|---------|---------------------|-------------|
| T-D01 | Flood de requests a endpoints de búsqueda | `/api/v1/search` | Media |
| T-D02 | Múltiples conexiones WebSocket desde un cliente | Panel de Operador | Baja |
| T-D03 | Cámara IP desconectada bloquea el runner | VideoStream / runner | Alta |

**Controles implementados:**
- Rate limiting: 60 req/min por IP en `/api/v1/search`, 10/min en export ✅
- `VideoStream` con reconexión automática y timeout ✅
- EdgeHubRouter con cola con backpressure (no bloquea loop principal) ✅
- `CameraWorker` en hilo separado por cámara ✅

---

### 3.6 Elevation of Privilege (Escalada de privilegios)

| ID | Amenaza | Componente afectado |
|----|---------|---------------------|
| T-E01 | Contenedor runner con acceso root | Docker |
| T-E02 | Acceso directo a PostgreSQL desde internet | DB |

**Controles implementados:**
- Dockerfiles crean usuario `vigilante` (UID 1001), no root ✅
- PostgreSQL expuesto solo en `127.0.0.1:5432` (no accesible desde internet) ✅
- Red Docker interna `vigilante_net` (los servicios no están en el host network) ✅

---

## 4. Superficie de ataque

```
Internet
   │
   ▼
[Nginx :443 TLS] ──── /api/v1/* ────► [FastAPI :8000]
                 ──── /operator/* ──► [FastAPI :8000]
                                           │
                                    ┌──────┴──────┐
                                    ▼             ▼
                              [PostgreSQL]   [Runner RTSP]
                                                   │
                                            [Cámaras IP]
                                            [Hub Curicó]
```

---

## 5. Controles de compliance (Chile)

| Ley / Norma | Requisito | Control implementado |
|-------------|-----------|----------------------|
| Ley 21.663 (Datos personales biométricos) | Consentimiento + retención limitada | `data_retention_days` en config; NO capturar rostros sin consent |
| Ley 21.459 (Delitos informáticos) | Logs de acceso al sistema | `audit_queries` en PostgreSQL; `event_logger.py` |
| Ley 19.303 (Seguridad privada) | Cadena de custodia de registros | Timestamps ISO 8601, `audit_queries`, exports CSV |
| ISO 27001:2022 | Cifrado en tránsito | TLS 1.2/1.3 via Nginx |
| ISO 27001:2022 | Control de acceso | Bearer token + rate limiting |
| ISO 27001:2022 | Trazabilidad | `audit_queries` con IP, user_id, timestamp |
| ISO 27701 (Privacidad) | Mapeo de datos personales | `detections` table — no almacena imágenes de rostros |

---

## 6. Plan de respuesta a incidentes

### Nivel 1 — Alerta de seguridad
- Trigger: múltiples `401 Unauthorized` desde misma IP
- Acción: revisar logs, bloquear IP en Nginx si es necesario

### Nivel 2 — Brecha sospechosa
- Trigger: acceso a datos fuera de horario laboral
- Acción: notificar al administrador vía email, revocar `API_SECRET_KEY`, regenerar token

### Nivel 3 — Brecha confirmada
- Trigger: datos de detecciones exfiltrados o BD comprometida
- Acción: detener servicios, preservar evidencia (`docker logs`), notificar a titular de datos (Ley 21.663 art. 37), restaurar desde backup

---

## 7. Checklist de hardening antes de producción

- [ ] `API_SECRET_KEY` generada con `secrets.token_urlsafe(32)`
- [ ] `WEBHOOK_SECRET` diferente al `API_SECRET_KEY`
- [ ] `POSTGRES_PASSWORD` de alta entropía (min 24 chars)
- [ ] Certificado TLS válido instalado (Let's Encrypt o CA corporativa)
- [ ] `.env` en `.gitignore` ✅ — verificar que no está en ningún commit
- [ ] `ENABLE_DOCS=false` en producción
- [ ] `CORS_ORIGINS` restringido al dominio del cliente
- [ ] Backup automático de PostgreSQL (pg_dump diario)
- [ ] Rotación de logs del runner (logrotate o Docker logging driver)
- [ ] Firewall: solo puertos 80/443 abiertos al exterior
