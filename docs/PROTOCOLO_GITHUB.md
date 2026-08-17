# Protocolo de colaboración — GitHub (Flucore / Vigilante Digital)

| Campo | Valor |
|---|---|
| Repo canónico | https://github.com/Flucore/Vigilante-digital |
| Rama por defecto | `main` |
| Audiencia | Equipo FluCore · Proyecto de Título · colaboradores |
| Última actualización | 2026-08-16 |

> Este protocolo define **cómo** compartir avance sin filtrar secretos, datos de clientes ni PII.

---

## 1. Objetivo del repositorio

Publicar el código y la documentación Dual-Track para que **cualquier compañero** entienda:

1. Contexto y posicionamiento del producto  
2. Alcance **comercial (F1)** vs **académico (F2)**  
3. Avance real (unidades C* / A*)  
4. Cómo ejecutar y contribuir sin romper capas ni compliance  

No es un dump de producción de un cliente.

---

## 2. Lectura obligatoria (onboarding)

Orden sugerido (30–60 min):

| # | Documento | Qué responde |
|---|---|---|
| 1 | [README.md](../README.md) | Arranque + mapa |
| 2 | [AI_CONTEXT.md](../AI_CONTEXT.md) | Contexto permanente, antipatrones, **estado actual** |
| 3 | [MASTER_DEVELOPMENT_PLAN.md](../MASTER_DEVELOPMENT_PLAN.md) | Visión Dual-Track ejecutiva |
| 4 | [DESARROLLO_EJECUTABLE.md](../DESARROLLO_EJECUTABLE.md) | Sprints, DoD, **unidad activa** |
| 5 | [GLOSARIO.md](../GLOSARIO.md) | Términos (M0–M3, FAR, calibrar ≠ entrenar) |
| 6 | [docs/REFORMULACION/01_CHARTER.md](REFORMULACION/01_CHARTER.md) | Charter FluCore |
| 7 | [docs/REFORMULACION/04_VISION_COMERCIAL_Y_VENTAS.md](REFORMULACION/04_VISION_COMERCIAL_Y_VENTAS.md) | Alcance comercial |
| 8 | [docs/REFORMULACION/07_PROYECTO_TITULO.md](REFORMULACION/07_PROYECTO_TITULO.md) | Alcance académico / título |
| 9 | [CODE_INDEX.md](../CODE_INDEX.md) | APIs, capas, eventos canónicos |

Índice del paquete de reformulación: [docs/REFORMULACION/README.md](REFORMULACION/README.md).

---

## 3. Qué NUNCA va al repo

| Prohibido | Alternativa |
|---|---|
| `.env` con valores reales | Solo `.env.example` con placeholders |
| JSON de Firebase / service accounts | Fuera del repo; variable `GOOGLE_APPLICATION_CREDENTIALS` |
| `client_config.json` de un cliente real | `client_config.example.json` / `client_config.aqua.example.json` |
| Videos, fotos, PDFs, pesos `.pt` | Local / almacenamiento privado |
| Correos, RUT, IPs reales de clientes | Anonimizar o inventar demo |
| Tokens, App Passwords, API keys | Secrets manager / env local |
| Datasets con menores / biometría | Fuera de alcance (Guerrilla excluido) |

Si un archivo sensible se subió por error: rotar credenciales + `git rm --cached` + commit; no confiar solo en “borrar del historial” sin decisión explícita.

---

## 4. Flujo de trabajo Git

```text
1. git pull origin main          # (o flucore main)
2. Crear rama: feat/c5-empaque · docs/… · fix/…
3. Un commit = una intención clara (C* / A* / docs)
4. Push de la rama → Pull Request hacia main
5. Revisión por al menos un compañero en cambios de core/outputs/api
```

### Mensajes de commit (estilo)

- `feat(c4): módulo aqua solo type=pool + Notify`  
- `docs: protocolo GitHub y onboarding título`  
- `fix(trigger): quitar import outputs→inputs`  

### Ramas

| Rama | Uso |
|---|---|
| `main` | Estable compartida con el equipo |
| `feat/*` | Unidades de código (C1–C6, A*) |
| `docs/*` | Solo documentación |
| `fix/*` | Correcciones acotadas |

No force-push a `main` salvo acuerdo explícito del equipo.

---

## 5. Reglas técnicas al contribuir

- Respetar capas: `inputs/` → `core/` → `outputs/` (ver `CODE_INDEX.md`).  
- Type hints en funciones públicas; eventos `event_schema_version: "2.0"`; timestamps ISO 8601 con TZ.  
- Firebase / email / hardware = **opcionales**.  
- Una unidad de `DESARROLLO_EJECUTABLE.md` por sesión de trabajo.  
- Actualizar `AI_CONTEXT.md` §6 y el tablero al cerrar una unidad C*/A*.  

---

## 6. Avance compartido (cómo reportar)

Al cerrar trabajo, en el PR o en el mensaje al equipo indicar:

1. **Unidad:** p. ej. C4 Done  
2. **Track:** COMERCIAL / ACADEMICO / DOCS  
3. **Verificación:** tests / smoke  
4. **Siguiente:** unidad del tablero  

Estado vivo: `AI_CONTEXT.md` §6 + `DESARROLLO_EJECUTABLE.md` §1.

---

## 7. Issues y PRs

- Issues para bugs, bloqueos (`DECISIÓN HUMANA`) y deuda (`docs/REFORMULACION/09_…`).  
- PRs con resumen + plan de prueba corto.  
- No pegar logs con IPs, correos o rutas de secretos.

---

## 8. Checklist pre-push

- [ ] No hay `.env`, `*firebase-adminsdk*`, ni `client_config.json` de cliente  
- [ ] `git status` no muestra `test_outputs/`, videos ni `.pt`  
- [ ] Placeholders en docs (sin project_id Firebase real ni rutas personales)  
- [ ] README / AI_CONTEXT reflejan el hito actual  
- [ ] Rama destino correcta (`main` en Flucore)

---

## Definition of Done (este protocolo)

- [x] Onboarding documental explícito para compañeros  
- [x] Lista de prohibidos / sensibles  
- [x] Flujo Git + checklist pre-push  
- [x] Sin secretos ni rutas personales en este archivo  
