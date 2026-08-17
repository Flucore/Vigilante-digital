# GUÍA DE DESPLIEGUE: Vigilante Digital con Firebase (opcional)

## Resumen

El proyecto puede usar Firebase vía `GOOGLE_APPLICATION_CREDENTIALS`.  
**Las claves NUNCA van en el repositorio.** Ver también [docs/PROTOCOLO_GITHUB.md](docs/PROTOCOLO_GITHUB.md).

Orquestador vigente: `runner.py` ( `main.py` es legado ).

---

## Desarrollo local

### 1. Credenciales Firebase

- Firebase Console → Configuración del proyecto → Cuentas de servicio  
- Generar nueva clave privada → se descarga un JSON de service account  

### 2. Guardar FUERA del repo

```
C:\secrets\firebase-service-account.json
```

o en Linux: `/etc/firebase-service-account.json` (permisos 600).

### 3. Variable de entorno (PowerShell)

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\secrets\firebase-service-account.json"
# Persistente (reiniciar shell después):
setx GOOGLE_APPLICATION_CREDENTIALS "C:\secrets\firebase-service-account.json"
```

### 4. Verificar

```powershell
python -c "import os; print(os.getenv('GOOGLE_APPLICATION_CREDENTIALS'))"
```

### 5. Ejecutar

```powershell
python runner.py --mode file --source TU_VIDEO.mp4
```

Firebase es **opcional**: el pipeline local (JSONL / PDF) funciona sin él.

---

## Producción (cliente)

### Windows

1. Copiar el JSON a una ruta segura fuera del repo, p. ej. `C:\secrets\firebase-service-account.json`  
2. `setx GOOGLE_APPLICATION_CREDENTIALS "C:\secrets\firebase-service-account.json"`  
3. Restringir ACL del archivo al usuario del servicio  

### Linux

```bash
sudo cp firebase-service-account.json /etc/firebase-service-account.json
sudo chmod 600 /etc/firebase-service-account.json
export GOOGLE_APPLICATION_CREDENTIALS="/etc/firebase-service-account.json"
```

### Docker

El JSON **no** va en la imagen; montarlo como secreto/volumen de solo lectura:

```bash
docker run \
  -e GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/firebase.json \
  -v /host/path/firebase-service-account.json:/run/secrets/firebase.json:ro \
  vigilante-digital:latest
```

---

## Checklist de seguridad

- [ ] JSON fuera del repo (`C:\secrets\` o `/etc/`)  
- [ ] `.gitignore` cubre `*firebase-adminsdk*`, `.env`, `client_config.json`  
- [ ] Variable `GOOGLE_APPLICATION_CREDENTIALS` configurada solo en el host  
- [ ] Push a Git **sin** service account (revisar `git status`)  
- [ ] Colección Firestore configurable (`FIRESTORE_COLLECTION`); no hardcodear datos de cliente  

---

## Soporte

1. Verificar `$env:GOOGLE_APPLICATION_CREDENTIALS`  
2. Revisar logs de `outputs/firebase_connector.py`  
3. Confirmar que el flujo funciona **sin** Firebase (modo local)  
