# P1/P2 · Matriz de decisión y modos — evidencia resumida

Claude Code 2.1.248 · 2026-09-01 · sesiones `claude -p` hijas (modelo haiku), entorno saneado
(`env -u CLAUDECODE …`), sin MCP (`--strict-mcp-config` + config vacía).

## Ronda definitiva (lote 5)

Discriminador: `--allowedTools "Bash(echo*)"` (base ALLOW) + comando sin escritura.
`ejecutó` = el hook PostToolUse de control disparó para esa sesión.

| Variante (permissionDecision) | ¿Ejecutó? | permission_denials | Lectura |
|---|---|---|---|
| *(sin hook PreToolUse)* | sí | 0 | base: el allowlist gana |
| `allow` | sí | 0 | aceptado (≡ base) |
| **`ask`** | **no** | **1** | **aceptado y efectivo: fuerza la decisión pese al allowlist** |
| `escalate` | sí | 0 | **NO aceptado: ignorado en silencio** |
| `bananas` (inventado) | sí | 0 | ignorado en silencio (≡ escalate) |
| stdout malformado (`{no-json`) | sí | 0 | ignorado en silencio, sin error visible |

## P2 · modos con hook `ask` (mismo discriminador)

Modos válidos según el propio CLI (error de `--permission-mode` inválido):
`acceptEdits, auto, bypassPermissions, manual, dontAsk, plan`.

| Modo pasado | permission_mode visto por el hook | ¿Ejecutó? | permission_denials |
|---|---|---|---|
| `acceptEdits` | `acceptEdits` | no | 1 |
| `auto` | `default` (se normaliza) | no | 1 |
| `dontAsk` | `dontAsk` | no | 1 |

En headless ningún modo convirtió el `ask` en aprobación ni en espera: denegación inmediata,
sesión termina en `success`. `bypassPermissions` no se sondeó (desactiva el sistema de permisos).

## Rondas invalidadas (y por qué se conservan)

1. **Ronda 1:** bug propio en el hook de sonda (orden de argumentos): emitió como decisión la ruta
   del log → todo se comportó como «valor inválido». Detectado porque hasta `allow` denegaba.
2. **Ronda 2 (lote 2) y 3 (lote 3):** el marcador `echo OK > fichero` activa la capa de permisos
   de **escritura de fichero**, que un `allow` de hook PreToolUse sobre Bash **no** cubre
   (denegaba con «Permission required to write to this file» — primero por la guarda de
   `~/.claude`, después por la de creación de ficheros en headless). Hallazgo útil por sí mismo:
   la decisión del hook no es la única capa de permiso que un Bash con redirección paga.

Los ficheros crudos por variante (`out.json`, `err.txt`, `hook.jsonl`, `postuse.jsonl`) viven en
el tmp del job (efímero); las cifras de esta tabla son transcripción literal de
`batch5-summary.txt` y de los logs de hooks.

## Caso atendido — medido el 2-sep-2026 (cierre del único hueco)

Sesión interactiva real del dueño, lanzada con
`claude --settings "docs/design/fase-0/manual-prompt-check.settings.json"` desde el repo.
Registro del hook (saneado; el log temporal se borró tras copiarlo aquí):

```
---REGISTRO 2026-09-02 00:51:47--- {"session_id":"cf0af796-…","transcript_path":"~/.claude/projects/…/cf0af796-….jsonl","cwd":"<repo>","permission_mode":"auto","hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"echo hola"},"tool_use_id":"toolu_01T6e4javaL1EdfT5JohkSa3"}
```

Del transcript de esa sesión:

| Evento | Timestamp (UTC) |
|---|---|
| `tool_use` (Bash `echo hola`) emitido | 2026-09-01T22:51:46.965Z |
| `tool_result` → `"hola"` | 2026-09-01T22:52:04.635Z |

**17,7 s entre emisión y resultado de un `echo`** = la pausa humana de mirar y aprobar el diálogo
(el dueño confirma haberlo visto, citando la razón del hook). `permission_mode: "auto"` en el
input demuestra que era el modo `auto` real del usuario — en interactivo sí es efectivo (en
headless se normalizaba a `default`).

**Conclusión P2 completa:** atendido ⇒ prompt visible que espera a la persona y la aprobación
ejecuta; no atendido ⇒ denegación inmediata sin auto-aprobación. Los dos lados, medidos.
