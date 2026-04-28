# Instrucciones: Publicar VigilanteDigital v2.0 en GitHub

**Pasos paso-a-paso para subir tu versión optimizada a GitHub desde el local.**

---

## 📋 Pre-requisitos

```powershell
# 1. Verificar Git instalado
git --version

# 2. Verificar que estás en la carpeta correcta
cd C:\Users\Valen\OneDrive\Documentos\DetectorIA\VigilanteDigital_1.0
pwd  # Debería mostrar: C:\Users\Valen\OneDrive\Documentos\DetectorIA\VigilanteDigital_1.0

# 3. Verificar que tienes credenciales configuradas en GitHub
# (SSH key o Personal Access Token)
```

---

## 🔗 Paso 1: Vincular Repositorio Local a GitHub

Si aún no has subido el proyecto a GitHub:

```powershell
# 1.1 Crear repositorio en GitHub (sin inicializar)
# - Ve a https://github.com/new
# - Nombre: VigilanteDigital
# - Descripción: AI-powered fall detection system with 99% Firestore cost optimization
# - NO marques "Initialize with README" (ya lo tienes)
# - Crea el repo

# 1.2 Conectar repositorio local a GitHub
git remote add origin https://github.com/TU_USUARIO/VigilanteDigital.git
# (Reemplaza TU_USUARIO con tu usuario de GitHub)

# 1.3 Verificar que se agregó correctamente
git remote -v
# Debería mostrar:
# origin  https://github.com/TU_USUARIO/VigilanteDigital.git (fetch)
# origin  https://github.com/TU_USUARIO/VigilanteDigital.git (push)
```

Si ya tienes un repositorio vinculado pero es diferente:

```powershell
# Cambiar URL existente
git remote set-url origin https://github.com/TU_USUARIO/VigilanteDigital.git

# Verificar
git remote -v
```

---

## 📝 Paso 2: Verificar y Preparar Cambios

```powershell
# 2.1 Ver estado actual
git status

# Debería mostrar cambios en:
# - config.py (nuevos parámetros v2.0)
# - main.py (integración EventLogger)
# - scripts/run_test.py (soporte EventLogger)
# - outputs/event_logger.py (NUEVO archivo)
# - scripts/cleanup_firestore.py (NUEVO archivo)
# - scripts/deploy_to_github.ps1 (NUEVO archivo)
# - CHANGELOG.md (NUEVO archivo)
# - QUICKSTART.md (actualizado v2.0)
# - README.md (actualizado v2.0)

# 2.2 Ver diferencias en detalle (para un archivo)
git diff config.py

# 2.3 Ver qué archivos se agregarían
git status --short
```

---

## 🔐 Paso 3: Verificar .gitignore (Seguridad)

**CRÍTICO: Asegurar que credenciales NO se suban**

```powershell
# 3.1 Verificar contenido de .gitignore
cat .gitignore

# Debería contener:
# *.json          (credenciales Firebase)
# *.key           (claves SSH)
# .env            (variables sensibles)
# .venv/          (virtual environment)
# __pycache__/    (compilados Python)
# *.pyc
# .pytest_cache/
# test_outputs/   (resultados locales)
```

Si .gitignore falta o está incompleto, crear/actualizar:

```powershell
# 3.2 Ver si hay archivos sensibles pendientes
git status | Select-String -Pattern "\.json|\.key|\.env"

# Si ves archivos sensibles, DETENER y eliminarlos primero:
# rm alertas1-key.json
# git rm --cached alertas1-key.json
# Luego continuar
```

---

## ✅ Paso 4: Hacer Commit de los Cambios

```powershell
# 4.1 Agregar TODOS los cambios al staging
git add -A

# 4.2 Verificar qué se agregó
git status

# 4.3 Crear commit descriptivo
git commit -m "v2.0: EventLogger optimization - 99% Firestore cost reduction

- Add EventLogger state machine for event-based logging (vs frame-by-frame)
- New config parameters: MIN_FALL_DURATION_SEC, EVENT_DEDUP_WINDOW_SEC, USE_EVENT_LOGGER
- Integrate EventLogger into main.py and scripts/run_test.py
- Add scripts/cleanup_firestore.py for legacy data cleanup
- Add CHANGELOG.md with detailed v2.0 notes
- Update QUICKSTART.md and README.md for v2.0
- Reduce Firestore documents from 5,330 to 2 per 3-min video (700x cost reduction)

Performance metrics:
- Video (3 min @ 30fps): 5,400 frames -> 2 events
- Firestore writes: 5,330 -> 2 (99.96% reduction)
- Cost per video: $7.00 -> $0.01 (700x reduction)
"

# 4.4 Verificar el commit
git log -1 --pretty=fuller
```

---

## 🏷️ Paso 5: Crear Tag de Versión

```powershell
# 5.1 Crear etiqueta para la versión
git tag -a v2.0.0 -m "Release v2.0.0: EventLogger optimization

Major improvements:
- EventLogger: State machine for event-based logging
- 99% reduction in Firestore documents (5,330 -> 2 per video)
- 700x cost reduction ($7.00 -> $0.01 per video)
- Backward compatible with v1.0 via USE_EVENT_LOGGER flag
- New cleanup script for legacy data
- Comprehensive documentation and changelog

Breaking changes:
- JSONLogger is now LEGACY (still works but not recommended)
- Event structure changed: one doc per event instead of per frame

Files changed:
- config.py: +8 lines (new v2.0 params)
- main.py: +30 lines (EventLogger integration)
- scripts/run_test.py: +50 lines (EventLogger support)
- outputs/event_logger.py: +120 lines (NEW)
- scripts/cleanup_firestore.py: +200 lines (NEW)
- scripts/deploy_to_github.ps1: +150 lines (NEW)
- CHANGELOG.md: +200 lines (NEW)
- QUICKSTART.md: +30 lines (updated)
- README.md: complete rewrite for v2.0
"

# 5.2 Verificar la etiqueta
git tag -l
git show v2.0.0
```

---

## 🚀 Paso 6: Publicar en GitHub

```powershell
# 6.1 Verificar que estás en la rama principal
git branch

# Si ves algo diferente a 'main' o 'master', cambiar a la correcta:
git checkout main  # o git checkout master

# 6.2 Subir commits a GitHub
git push origin main

# Si sale error "Permission denied":
# Autenticarse con GitHub CLI o Git Credential Manager.
# No pegar tokens en la URL del remoto ni guardarlos en scripts.
# Ejemplo: gh auth login

# 6.3 Subir etiquetas (releases)
git push origin v2.0.0

# O subir TODAS las etiquetas:
git push origin --tags
```

---

## 📊 Paso 7: Verificar en GitHub

```powershell
# 7.1 Abrir navegador y verificar
# https://github.com/TU_USUARIO/VigilanteDigital

# Debería ver:
# ✓ Archivos subidos (config.py, main.py, scripts/, outputs/event_logger.py, etc)
# ✓ Commit message con descripción v2.0
# ✓ Branch 'main' actualizado hace poco
# ✓ CHANGELOG.md visible
# ✓ README.md con versión v2.0

# 7.2 Verificar Release (etiqueta)
# https://github.com/TU_USUARIO/VigilanteDigital/releases

# Debería ver:
# ✓ Release "v2.0.0" con descripción completa
# ✓ Opción de descargar código (.zip, .tar.gz)

# 7.3 Opcional: Ver commits
# https://github.com/TU_USUARIO/VigilanteDigital/commits/main

# Debería ver el último commit "v2.0: EventLogger optimization..."
```

---

## 🔄 Paso 8: Automatizar con Deploy Script (Opcional)

Para futuras actualizaciones, usa el script PowerShell que publica al repo Flucore
sin depender del `origin` local:

```powershell
# 8.1 Simular auditoria, commit y push
.\scripts\publish_flucore_repo.ps1 `
  -Message "Release v2.0.1: Fix EventLogger edge case" `
  -DryRun

# 8.2 Si DRY RUN se ve bien, ejecutar de verdad
.\scripts\publish_flucore_repo.ps1 `
  -Message "Release v2.0.1: Fix EventLogger edge case"

# 8.3 Verificar en GitHub nuevamente
```

---

## 🧹 Paso 9: Limpiar Datos de Prueba en Firestore (Opcional)

Si tienes datos viejos de v1.0 en Firestore:

```powershell
# 9.1 Contar documentos viejos
python scripts/cleanup_firestore.py --count

# 9.2 Exportar como backup
python scripts/cleanup_firestore.py --export backup_old_v1.json

# 9.3 Eliminar (simulación primero)
python scripts/cleanup_firestore.py --delete --dry-run

# 9.4 Eliminar de verdad
python scripts/cleanup_firestore.py --delete --force
```

---

## ✨ Paso 10: Anunciar la Nueva Versión (Opcional)

```powershell
# Si tienes redes sociales o comunidad:
# 📝 Publicar anuncio:

# "🎉 VigilanteDigital v2.0 released! 
# 🚀 99% reduction in Firestore costs via EventLogger
# 📊 5,330 docs -> 2 docs per video (700x cheaper)
# 🔗 https://github.com/TU_USUARIO/VigilanteDigital/releases/tag/v2.0.0
# #AI #FallDetection #Firebase #Optimization"
```

---

## 🔍 Troubleshooting

### Error: "fatal: not a git repository"

```powershell
# Estás fuera de la carpeta del repo, navega:
cd C:\Users\Valen\OneDrive\Documentos\DetectorIA\VigilanteDigital_1.0
git status  # Ahora debería funcionar
```

### Error: "Permission denied (publickey)"

```powershell
# Autenticarse con GitHub CLI o Git Credential Manager.
# Evitar tokens en texto plano dentro de la URL del remoto.
gh auth login
git push
```

### Error: "Updates were rejected because the tip of your current branch is behind"

```powershell
# Alguien más actualizó el repo, sincronizar primero
git pull origin main
# Resolver conflictos si hay (probablemente no)
git push origin main
```

### Cambios se vieron en GitHub pero no donde esperabas

```powershell
# Verificar rama correcta
git branch -a
git status

# Si estás en rama equivocada:
git checkout main
git pull origin main
```

---

## 📚 Comandos Útiles Post-Deploy

```powershell
# Ver historial de commits
git log --oneline -10

# Ver cambios entre versiones
git diff v1.0.0..v2.0.0

# Crear rama para desarrollo
git checkout -b develop
git push origin develop

# Fusionar rama a main cuando esté lista
git checkout main
git merge develop
git push origin main
```

---

## ✅ Checklist Final

Antes de marcar como "listo":

```
[ ] git remote -v muestra origin correcta
[ ] git status muestra "nothing to commit"
[ ] .gitignore excluye *.json, *.key, .env
[ ] commit message es descriptivo
[ ] tag v2.0.0 creado con mensaje
[ ] git push origin main ejecutado sin errores
[ ] git push origin --tags ejecutado sin errores
[ ] https://github.com/TU_USUARIO/VigilanteDigital se ve actualizado
[ ] Release v2.0.0 visible en GitHub
[ ] README.md muestra v2.0.0
[ ] CHANGELOG.md describe cambios
[ ] QUICKSTART.md tiene instrucciones actualizadas
[ ] Scripts cleanup_firestore.py y deploy_to_github.ps1 están subidos
```

---

## 🎉 ¡Listo!

Tu versión v2.0 está publicada en GitHub. 

**Próximos pasos:**
1. Compartir link con tu equipo
2. Solicitar feedback en GitHub Issues
3. Documentar bugs encontrados
4. Planear v2.1 con nuevas features

**Links importantes:**
- Repository: `https://github.com/TU_USUARIO/VigilanteDigital`
- Release: `https://github.com/TU_USUARIO/VigilanteDigital/releases/tag/v2.0.0`
- Issues: `https://github.com/TU_USUARIO/VigilanteDigital/issues`
- Discussions: `https://github.com/TU_USUARIO/VigilanteDigital/discussions`

---

**Tiempo total aproximado: 20-30 minutos**

**Necesitas ayuda?** Ejecuta:
```powershell
git --help
# o
.\scripts\deploy_to_github.ps1 -Help
```
