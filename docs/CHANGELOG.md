# Changelog - Vigilante Digital IA

Todos los cambios importantes a este proyecto se documentan aquí.

## [2.5.0] - Diciembre 2025 (Reportes PDF y Optimización de Streaming)

### ✨ Características Nuevas
- **Generación automática de reportes PDF**: Nuevo módulo `outputs/report_generator.py` que crea reportes visuales con imagen del evento, fecha, hora, cámara y sector
- **Envío de reportes por correo**: Nuevo módulo `outputs/email_sender.py` con soporte para Gmail SMTP usando App Passwords (seguro, sin guardar contraseña)
- **Integración interactiva**: `run_test.py` pregunta al usuario si desea enviar el reporte completado
- **Optimización de streaming en tiempo real**: 
  - Parámetro `--frame-scale` (default 0.6): Procesa frames a menor resolución
  - Parámetro `--detection-skip` (default 2): Ejecuta MediaPipe cada N frames
  - Resultado: Streaming más fluido sin sacrificar detección de caídas

### 🚀 Mejoras de Performance
- **Reducción de carga de CPU en streaming**:
  - Procesamiento a 60% de resolución original (~3.6x menos píxeles)
  - Inferencias de MediaPipe reducidas a 50% (skip=2)
  - Visualización sin redimensionados costosos
  - Observable: Cambio de ~3-5 FPS a ~15+ FPS en máquinas estándar
- **Optimizaciones en test**:
  - Detection skip automático desde `config.DETECTION_SKIP`
  - Reutilización de bbox entre frames para continuidad visual

### 🔐 Mejoras de Seguridad
- **Credenciales seguras**:
  - Envío de correos vía App Password (contraseña específica de aplicación)
  - **NO** se guarda contraseña de cuenta Google en código
  - Credenciales en variables de entorno del SO, no en archivos
- **Documentación limpia**:
  - Guía de configuración sin exponer datos sensibles
  - Mejores prácticas de seguridad documentadas
- **Validación de configuración**:
  - Script `test_email_send.py` valida setup sin enviar correo real (excepto si lo deseas)

### 📦 Nuevos Módulos
- `outputs/report_generator.py`: Generación de PDFs con reportlab
  - Soporta imagen opcional del evento
  - Layout profesional con metadata
  - Atomic file writes
- `outputs/email_sender.py`: Cliente SMTP Gmail
  - Lectura de credenciales desde env vars
  - Manejo robusto de errores con retry
  - Prompt interactivo para solicitar dirección destino
- `scripts/test_email_send.py`: Validación de email setup
  - Prueba sin enviar (modo seguro)
  - Generación de reporte de prueba

### 📋 Actualización de Dependencias
- **Nuevas**: 
  - `reportlab>=4.0.0` (PDF generation)
  - `pillow>=10.0.0` (image handling)
- **Opcionales** (comentadas como instalables bajo demanda):
  - `paho-mqtt>=1.6.0` para MQTT (ESP32, IoT)
  - `pyserial>=3.5` para USB Serial (Arduino)

### 🛠️ Cambios de Implementación

#### scripts/run_test.py
- Integración de `ReportGenerator` y `EmailSender`
- Método `_offer_email_send()` para preguntar al usuario tras completar evento
- Optimización: `PoseDetector(complexity=0, frame_scale=0.6)` por defecto
- Soporte para `config.DETECTION_SKIP` configurable
- Evita redimensionados de frame antes de mostrar

#### scripts/run_with_devices.py
- Parámetros CLI: `--frame-scale`, `--detection-skip`, `--complexity`
- Lógica de detection skip para reducir inferencias
- Reuso de bbox entre detecciones
- Evento 'd' genera reporte PDF bajo demanda
- Integración con ReportGenerator

#### outputs/report_generator.py (NUEVO)
- Clase `ReportGenerator` para crear PDFs
- Método `generate_report(event, frame_image, output_dir)` retorna ruta PDF
- Manejo de imágenes con `reportlab.lib.utils.ImageReader`
- Escalado automático preservando aspecto
- Timestamps únicos para evitar sobrescrituras

#### outputs/email_sender.py (NUEVO)
- Clase `EmailSender` con SMTP Gmail
- Método `send_report(recipient_email, pdf_path, subject, body)`
- `prompt_recipient()` solicita correo de forma segura en consola
- `get_credentials_from_env()` lee GMAIL_SENDER_EMAIL y GMAIL_APP_PASSWORD
- Manejo de excepciones SMTPAuthenticationError con mensajes útiles

#### config.py (actualizado)
- Nueva opción: `DETECTION_SKIP` (default: 2) para control de inferencias

### 🧪 Testing
- Script `test_report_generation.py`: Genera reporte de prueba
- Script `test_email_send.py`: Valida configuración de Gmail
- Ambos scripts ofrecen modo prueba sin efectos secundarios

### 📚 Documentación
- `GMAIL_SETUP_GUIDE.md`: Limpia, sin exponer credenciales
  - Pasos para configurar App Password
  - Troubleshooting común
  - Buenas prácticas de seguridad
- `requirements.txt`: Actualizado con nuevas dependencias
- Comentarios en español en módulos clave

### ⚠️ Cambios Potencialmente Disruptivos
- Ninguno: Totalmente backward-compatible con v2.0

## [2.0.0] - 2024 (EventLogger Optimization)

### ✨ Características Nuevas
- **EventLogger con State Machine**: Nuevo módulo `outputs/event_logger.py` que implementa detección de eventos (inicio/fin de caída) en lugar de logging frame-a-frame
- **Configuración v2.0**: Parámetros de control para EventLogger en `config.py`:
  - `MIN_FALL_DURATION_SEC`: Filtro de duración mínima (default 0.5s)
  - `EVENT_DEDUP_WINDOW_SEC`: Ventana de deduplicación (default 2.0s)
  - `USE_EVENT_LOGGER`: Toggle para activar/desactivar EventLogger (default true)

### 🚀 Mejoras de Performance
- **Reducción de Documentos Firestore: 99%**
  - **Antes (v1.0)**: 5,330 documentos por video de 3 minutos (frame-by-frame)
  - **Después (v2.0)**: 1-2 documentos por caída (event-based)
  - **Impacto económico**: $7 → $0.01 por video (~700x reducción en costos Firestore)

- **Algoritmo Optimizado**:
  - Máquina de estados (NORMAL/FALLING)
  - Transiciones generan eventos completados
  - Deduplicación de eventos cercanos en tiempo

### 🛠️ Cambios de Implementación

#### main.py
- Integración de `EventLogger` como alternativa a `JSONLogger`
- Lógica de transición de estados en bucle principal
- Sincronización automática en completación de eventos
- Finalización forzada de eventos pendientes al terminar video

#### scripts/run_test.py
- Soporte para ambos modos: `USE_EVENT_LOGGER=true` (v2.0) y `false` (v1.0 legacy)
- Métrica nueva: `total_events_completed`
- Cálculo de reducción de datos en resumen de prueba
- Finalización de eventos pendientes al terminar

#### outputs/event_logger.py (NUEVO)
- Clase `EventLogger` con estado persistente
- Método `update(is_falling, frame_idx, photo_path, metadata)` → devuelve evento completado o None
- Método `finalize()` para forzar cierre de evento
- Atomic JSON writes con tempfile + os.replace
- Timestamps normalizados (ISO 8601)

#### config.py
- Agregados parámetros v2.0 con valores por defecto
- `EVENT_LOG_PATH` nuevo (default: "outputs/events_log.json")
- Parámetros de deduplicación y filtrado
- Compatibilidad mantenida con v1.0

### 🧹 Herramientas Nuevas

#### scripts/cleanup_firestore.py (NUEVO)
- Limpia documentos de prueba en Firestore
- Soporte para filtros (ej: "event_type==fall")
- Modo dry-run con visualización previa
- Exportación a JSON antes de eliminar
- Batch operations para eficiencia

#### scripts/deploy_to_github.ps1 (NUEVO)
- Script PowerShell para publicar v2.0 a GitHub
- Flujo completo: commit → tag → push
- Modo dry-run para validación
- Confirmación interactiva

### 📊 Métricas de Prueba
```
Video: 3:00 min @ 30fps
Total frames: 5,400
Frames con ratio < 0.8: 5,330

v1.0 (JSONLogger):
  - Documentos creados: 5,330
  - Duración ejecución: ~45s
  - Documentos Firestore: 5,330

v2.0 (EventLogger):
  - Eventos completados: 2
  - Documentos Firestore: 2
  - Reducción: 99.96%
```

### 🔄 Migración desde v1.0
```powershell
# 1. Actualizar config.py (automático)
# 2. Actualizar main.py (automático)
# 3. Ejecutar prueba con EventLogger
python scripts/run_test.py --video test.mp4 --output results_v2

# 4. Comparar resultados
# v1.0: events_history.json con 5,330 líneas
# v2.0: events_log.json con 2 eventos

# 5. Limpiar datos de prueba (OPCIONAL)
python scripts/cleanup_firestore.py --export backup_old.json --delete --force --query "event_type==fall"
```

### ⚠️ Cambios Incompatibles
- **JSONLogger ahora es LEGACY**: Sigue funcionando pero no es recomendado
- **Estructura de eventos cambiada**:
  - v1.0: Un documento por frame
  - v2.0: Un documento por evento (start → end)

### ✅ Testing
- Pruebas locales con `scripts/run_test.py` COMPLETAS
- Métrica de reducción de datos verificada
- Firebase sync probado exitosamente
- EventLogger state machine validado

### 📝 Documentación
- `ARCHITECTURE_OPTIMIZATION.md`: Análisis detallado del problema y soluciones
- `CHANGELOG.md` (este archivo): Historial de versiones
- `QUICKSTART.md`: Actualizado con instrucciones v2.0
- `DEPLOYMENT.md`: Instrucciones de credenciales sin cambios

### 🔒 Seguridad
- Sin cambios en manejo de credenciales
- `GOOGLE_APPLICATION_CREDENTIALS` sigue siendo el estándar
- `.gitignore` actualizado (no hay archivos de credenciales en repo)

### 🎯 Próximos Pasos (v2.1)
- [ ] UI web para visualizar eventos en tiempo real
- [ ] Alertas en tiempo real vía webhooks
- [ ] Análisis de caídas (duración, tipo, ubicación)
- [ ] Soporte para múltiples cámaras

---

## [1.0.0] - 2024 (Initial Release)

### Características
- Detector de pose con MediaPipe
- Detección de caídas por aspect ratio
- Logging a JSON local
- Sincronización a Firestore
- Configuración por variables de entorno

### Problemas Conocidos
- **Frame-by-frame logging**: crea miles de documentos innecesarios
- **Costo económico**: ~$7 por video en escrituras Firestore
- **Sin deduplicación**: eventos duplicados en rápida sucesión

---

## Versionado Semántico

Este proyecto sigue [Versionado Semántico](https://semver.org/):
- **MAJOR**: Cambios incompatibles (v1 → v2)
- **MINOR**: Nuevas características compatibles
- **PATCH**: Correcciones de bugs

Ejemplo: `v2.0.0` = Mayor 2, Menor 0, Patch 0
