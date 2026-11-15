# Guía: Configuración de Envío de Reportes por Correo

El sistema **Vigilante Digital IA** puede enviar reportes PDF automáticamente cuando se detecta una caída. Esta guía explica cómo configurarlo de forma segura.

## Restricciones de Google (Políticas de Seguridad)

Desde mayo de 2022, Google implementó restricciones de seguridad para el acceso a SMTP.

**Métodos seguros recomendados:**

1. **App Password** (Fácil - Recomendado) ✅
   - Requiere: 2FA habilitado en tu cuenta Google
   - Genera una contraseña específica para esta aplicación
   - Válida únicamente para este sistema

2. **OAuth 2.0** (Máxima seguridad - Producción)
   - Más complejo pero sin guardar contraseñas
   - Recomendado para entornos corporativos

## Configuración con App Password (Pasos)

### 1. Habilitar Autenticación de Dos Factores (2FA)

1. Accede a [Google Account](https://myaccount.google.com/)
2. Selecciona **Seguridad** en el menú lateral
3. Busca "Verificación en dos pasos" y sigue los pasos

### 2. Generar App Password

1. Una vez 2FA habilitado, accede a [Contraseñas de aplicación](https://myaccount.google.com/apppasswords)
2. Selecciona:
   - App: **Mail**
   - Dispositivo: **Windows Computer**
3. Haz clic en **Generar**
4. Google mostrará una contraseña de 16 caracteres
5. **Cópiala exactamente** (incluye espacios)

### 3. Guardar Credenciales de Forma Segura

**IMPORTANTE:** No guardes credenciales en código fuente.

#### Opción A: Variables de Entorno Temporales (Para pruebas)

En PowerShell:
```powershell
$env:GMAIL_SENDER_EMAIL = "tu@gmail.com"
$env:GMAIL_APP_PASSWORD = "tu-contrasena-de-app"
```

#### Opción B: Variables de Sistema Permanentes (Recomendado)

En Windows:
1. Presiona `Win + Pause`
2. "Configuración avanzada del sistema"
3. "Variables de entorno"
4. Agrega nuevas variables:
   - `GMAIL_SENDER_EMAIL` = `tu@gmail.com`
   - `GMAIL_APP_PASSWORD` = `tu-contrasena-de-app`

### 4. Verificar Configuración

En PowerShell:
```powershell
Write-Host "Email: $env:GMAIL_SENDER_EMAIL"
Write-Host "Password configurada: $(if($env:GMAIL_APP_PASSWORD) { 'Sí' } else { 'No' })"
```

## Prueba de Configuración

Antes de usar en producción, valida tu setup:

```powershell
python .\scripts\test_email_send.py
```

El script:
- Verifica que las credenciales están configuradas
- Valida conexión al servidor SMTP
- Permite enviar un reporte de prueba (opcional)

## Uso Automático en el Sistema

Al ejecutar detección de caídas:

```powershell
python .\scripts\run_test.py --video .\tests\test_videos\fall_sample_01.mp4 --output .\test_outputs
```

**Flujo automático:**
1. Detecta caída → Genera reporte PDF
2. Pregunta: *¿Deseas enviar el reporte por correo? (s/n):*
3. Si respondes "s" → Solicita dirección destino
4. Envía automáticamente

## Buenas Prácticas de Seguridad

| ✅ Hacer | ❌ No hacer |
|---------|-----------|
| Usar variables de entorno | Guardar credenciales en código |
| Activar 2FA | Usar contraseña de cuenta principal |
| Usar App Password | Compartir credenciales en chat |
| Revisar logs regularmente | Dejar credenciales en archivos |

## Solución de Problemas

| Problema | Causa | Solución |
|----------|-------|----------|
| "Error de autenticación" | App Password incorrecta | Genera una nueva en Google Account |
| "SMTP connection refused" | Firewall/puerto bloqueado | Verifica conexión de red |
| "Module not found (reportlab)" | Dependencia no instalada | `pip install reportlab pillow` |
| "Credenciales no encontradas" | Variables de entorno vacías | Configura GMAIL_SENDER_EMAIL y GMAIL_APP_PASSWORD |

## Recursos Adicionales

- [Google Account Security](https://myaccount.google.com/security)
- [Crear App Passwords](https://support.google.com/accounts/answer/185833)
- [Gmail SMTP Configuration](https://support.google.com/mail/answer/7126229)
- [Mejores Prácticas de Seguridad](https://cloud.google.com/docs/authentication/best-practices)

---

**Versión:** 2.5.0  
**Última actualización:** Diciembre 2025
