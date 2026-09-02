# Sonda de perímetro · Fase 2 (2026-09-02)

Ejecutada por el **lanzador real** (`sh hooks/run_hook.sh <root> <subcomando>` con el payload por
stdin) — la misma superficie que invoca Claude Code —, contra **tres configuraciones** en
directorios de proyecto limpios. Respuestas literales, sin editar (los `\uXXXX` son el escape
JSON de `json.dumps`).

## Verde · `appianMcpToolPrefixes` declarada (`mcp__appian-dev__`, `mcp__appian__`)

`session-start` → **sin frase de perímetro**:

```json
{"hookSpecificOutput": {"additionalContext": "appian-harness: all three requirements are present (design MCP, official Appian skill, documentation MCP). [...]", "hookEventName": "SessionStart"}}
```

## Rojo · clave ausente

`session-start` → **la frase literal de § 7.2**, con remedio:

```json
{"hookSpecificOutput": {"additionalContext": "[...]\n\nPERÍMETRO (§ 7.2): la configuración no declara appianMcpToolPrefixes[]. Los hooks se están ejecutando pero no ven tus herramientas de Appian: el plugin está instalado y no gobierna nada. Rellénala con /appian-init --adopt; mientras falte, los gates usan el respaldo por nombre de servidor y la primera escritura de cada sesión pedirá permiso.", "hookEventName": "SessionStart"}}
```

Primera escritura de la sesión (`scope-gate`, `mcp__appian-dev__updateConstant`) → **`ask` de
migración de § 15**, nombrando la clave y el arreglo; **la segunda escritura de la misma sesión ya
no lo repite** (solo queda el motivo ordinario `no active task`):

```json
{"permissionDecision": "ask", "permissionDecisionReason": "appian-harness ha parado mcp__appian-dev__updateConstant: este proyecto no declara appianMcpToolPrefixes[] [...] · no active task: nothing has been scoped and approved for this session"}
{"permissionDecision": "ask", "permissionDecisionReason": "no active task: nothing has been scoped and approved for this session"}
```

## El caso que motiva § 7.2 · servidor renombrado (`mcp__lcp__`)

| Configuración | `scope-gate` sobre `mcp__lcp__updateConstant` | Lectura |
|---|---|---|
| Sin la clave (respaldo por nombre) | `allow · "not a write tool"` | **Invisible**: el fallo de la 0.5.2 — pero ya no silencioso, porque session-start dijo la frase |
| Con `["mcp__lcp__", "mcp__lcp-runtime__"]` | `ask · "no active task: …"` | **Gateada**: el perímetro declarado gobierna un servidor con cualquier nombre |

**Veredicto: la sonda falla en verde y en rojo contra dos configuraciones distintas** — la
condición tercera del DoD de § 16 Fase 2 — y además contra la tercera configuración que demuestra
el porqué de la clave.
