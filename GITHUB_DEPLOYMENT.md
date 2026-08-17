# Publicar / actualizar en GitHub (Flucore)

> Guía corta. Protocolo completo del equipo: **[docs/PROTOCOLO_GITHUB.md](docs/PROTOCOLO_GITHUB.md)**.

## Repo canónico

https://github.com/Flucore/Vigilante-digital  
Rama por defecto: **`main`**

## Remoto

```powershell
git remote -v
# Si falta el remoto Flucore:
git remote add flucore https://github.com/Flucore/Vigilante-digital.git
```

## Publicar avance (desde rama local `master` o feature)

```powershell
# 1. Checklist de secretos (PROTOCOLO_GITHUB.md §8)
git status

# 2. Commit solo lo permitido
git add -A
git status   # verificar que NO aparece .env, client_config.json, videos, .pt

# 3. Push hacia main de Flucore
git push flucore HEAD:main
# o, desde una feature branch:
# git push -u flucore feat/mi-unidad
# luego abrir PR hacia main
```

## Pull Request

```powershell
gh pr create --repo Flucore/Vigilante-digital --base main --title "…" --body "…"
```

## Prohibido

- Force-push a `main` sin acuerdo del equipo  
- Tokens en la URL del remoto  
- Subir `*firebase-adminsdk*`, `.env`, configs de cliente real  

## Documentación histórica

Las guías `QUICKSTART.md` / `DEPLOYMENT.md` pueden referirse a flujos v2.x; el **mapa vigente** es Dual-Track (`README.md` + `DESARROLLO_EJECUTABLE.md`).
