# Registro de implementación · appian-harness 0.7

> **Este documento NO es normativo.** La norma de la 0.7 es
> [`appian-harness-0.7-1.0.md`](appian-harness-0.7-1.0.md) (DESIGN FREEZE del 1-sep-2026, § 21).
> Aquí solo se registra lo que la implementación **hizo y midió**, fase a fase. Si algo de aquí
> parece contradecir la norma, manda la norma — y si la evidencia obliga a cambiarla, el cambio se
> hace en la norma por la regla de reapertura de § 21, no aquí.

**Ejecutado el:** 2026-09-01 · **Claude Code:** 2.1.248 (Windows 11) ·
**Entorno Appian:** el de siempre, por la superficie del servlet del plug-in (basic auth) ·
**Sesiones hijas de sonda:** `claude -p`, modelo `claude-haiku-4-5-20251001`, entorno saneado
(`env -u CLAUDECODE …`), servidores MCP aislados por corrida (`--strict-mcp-config`).

**Evidencia:** cruda y saneada en [`fase-0/`](fase-0/) (rutas personales → `~`, URLs de diseño y
hostname del entorno → placeholders). Los originales sin sanear viven fuera de git, en el tmp
efímero del job que ejecutó la fase.

---

## Fase 0 · Las cinco sondas + la comprobación de esquemas

Estado: **DONE (2026-09-01)** — DoD comprobado condición a condición al final de este documento.

| # | Sonda | Resultado | Consecuencia para el código |
|---|---|---|---|
| P1 | Valor de decisión (`ask` vs `escalate`) | **`ask` aceptado y efectivo** (bloquea incluso con regla allow); **`escalate` no existe**: se ignora en silencio, igual que un valor inventado o un hook malformado | Se emite `ask` (lo que el código 0.6 ya hace); el test-guardia queda para la Fase 1. Un valor no reconocido **degrada hacia permitir**, exactamente el riesgo que § 16 señalaba |
| P2 | `ask` en modo `auto` / sesión no atendida | **No atendida: no llega como prompt y no se auto-aprueba** (denegación inmediata en `permission_denials`, en todos los modos). **Atendida en modo `auto` real (medido el 2-sep con el dueño delante): sí produce el prompt**, espera a la persona, y la aprobación ejecuta | El hook registra el modo (el input trae `permission_mode`) y el permiso solo cuenta como humano cuando lo fue; la plataforma degrada hacia denegar, que es el lado seguro |
| P3 | Payloads reales de escritura | **Las tres clases capturadas** con payload real: `ok` (×5 variantes de forma — la quinta, el delete de la limpieza), `failed` (×2 formas), `ambiguous` (×1, con relectura que la resuelve) | El clasificador de `log-write` se escribe contra estas formas; `ambiguous` como cajón por defecto queda confirmado como necesario |
| P4 | Carga diferida de schemas MCP | **La palanca existe, viene activada por defecto en 2.1.248 y ahorra ~86,6 K tokens/turno** con los tres servidores Appian (más del doble de los 40-45 K que estimaba § 12.4) | La fila de 120 K de § 17.5 es viable **con** carga diferida (suelo MCP ≈ +3 K); sin ella (+89,7 K) no lo sería. `/appian-init` debe comprobar/recomendar que la deferral esté activa (`ENABLE_TOOL_SEARCH` ≠ `false`) |
| P5 | `PostToolBatch` | **Dispara** en 2.1.248: con lotes paralelos y **con lotes de una sola llamada**; la invocación de `Skill` es observable; los errores de herramienta aparecen en el lote (y `PostToolUse` se los salta) | `observe-reads` va a `PostToolBatch` como diseñó § 7.4; el gate de skill de § 7.5 **no** se degrada a aviso. Ajuste de campo al codificar: la entrada trae `tool_response` (no `tool_result`) y **no hay campo `error`** |
| P6 | Esquemas de las herramientas de escritura vs § 5.2 | Volcadas las 145 tools; **3 discrepancias de nombre/alcance** que la fila 6 del freeze ya preveía («se corrige la regla antes de escribirla») y ninguna reapertura | Ver tabla § P6; `task_min_kind` se escribe con los nombres reales y sin las dos ramas inalcanzables |

---

### P1 · Valor de la decisión (`ask` frente a `escalate`)

- **Qué se comprobó:** qué valores de `hookSpecificOutput.permissionDecision` acepta la versión
  instalada. Diseño del discriminador: sesiones `claude -p` hijas con `--allowedTools
  "Bash(echo*)"` como línea base ALLOW y un comando **sin escritura** (`echo OK-…`), de modo que
  un valor aceptado se ve porque **cambia el resultado frente a la base** y un valor inválido se
  ve porque no lo cambia. Prueba de ejecución: un hook `PostToolUse` que solo dispara si la
  herramienta corrió. (Dos rondas previas quedaron invalidadas y documentadas: un `echo >
  fichero` activa la capa de permisos de escritura de fichero — que un `allow` de hook sobre Bash
  **no** cubre — y enmascara la decisión.)
- **Resultado real (matriz):** basal sin hook → ejecuta, 0 denials · `allow` → ejecuta, 0 denials
  · **`ask` → NO ejecuta, 1 denial** (fuerza la decisión pese al allowlist) · **`escalate` →
  ejecuta, 0 denials** · valor inventado (`bananas`) → ejecuta, 0 denials · hook con stdout
  malformado → ejecuta, 0 denials, sin error visible.
- **Evidencia:** `p1s-*.out.json`, `p1s-*.hook.jsonl`, `p1s-*.postuse.jsonl` (tmp del job);
  resumen [`fase-0/p1-p2-matriz.md`](fase-0/p1-p2-matriz.md).
- **Versión/entorno:** Claude Code 2.1.248, headless, modo default (`manual`).
- **Consecuencia:** el plugin emite **`ask`**, que es lo que `hooks/harness_hooks.py` ya emite;
  `escalate` no existe en esta versión. Ojo: un valor no reconocido **no da error — se ignora**,
  y la sesión degrada hacia permitir (la base allow gana). Ese es exactamente el riesgo que hace
  necesario el test-guardia de la Fase 1 («falla si no produce prompt»).
- **Fallback usado:** ninguno — `ask` es válido; no hubo que buscar valor alternativo.

### P2 · `ask` en modo `auto` (sesión no atendida)

- **Qué se comprobó:** si un `ask` de hook llega como prompt a una persona cuando la sesión no
  está atendida, o qué pasa en su lugar. Sesiones headless (`claude -p`) con el hook `ask` de P1
  y el allowlist como base, barriendo modos de permiso. El propio CLI enumeró los modos válidos:
  `acceptEdits, auto, bypassPermissions, manual, dontAsk, plan`.
- **Resultado real:** en **todos** los modos probados con sesión no atendida (`manual`/default,
  `acceptEdits`, `auto`, `dontAsk`) el `ask` **no espera a nadie y no se auto-aprueba**: la
  herramienta no se ejecuta y la denegación queda registrada en `permission_denials` del JSON de
  salida; la sesión termina en `success` sin bloqueo. Matiz: con `--permission-mode auto` el
  input del hook reporta `permission_mode: "default"` — el registro del modo debe tolerar esa
  normalización. (`bypassPermissions` no se sondeó: desactiva el sistema de permisos entero y no
  es un modo que el harness contemple.)
- **Evidencia:** `p2s-*.out.json`, `p2s.hook.jsonl` (tmp del job); resumen
  [`fase-0/p1-p2-matriz.md`](fase-0/p1-p2-matriz.md). El input de todos los hooks incluye
  `permission_mode`, `session_id`, `transcript_path`, `cwd`, `tool_use_id`.
- **Versión/entorno:** Claude Code 2.1.248, headless.
- **Consecuencia:** tal y como el diseño dejó escrito para este sentido de la sonda: el hook
  registra el modo (el campo existe en el input) y **el permiso no se trata como aprobado por una
  persona** — el alcance no puede cerrar como concedido. La plataforma además degrada hacia
  **denegar**, no hacia permitir, que es el lado que el diseño necesita.
- **Caso atendido — medido el 2026-09-02, con el dueño delante.** Kit
  `fase-0/manual-prompt-check.settings.json` en sesión interactiva real: el input del hook
  registró `permission_mode: "auto"` (el modo por defecto del usuario, efectivo de verdad en
  interactivo), **el diálogo de permiso apareció** citando la razón del hook, y entre el
  `tool_use` y el `tool_result` de un simple `echo` pasaron **17,7 s** — la pausa humana de mirar
  y aprobar; la aprobación ejecutó el comando (`"hola"`). Conclusión completa de P2: atendido ⇒
  prompt visible que espera a la persona; no atendido ⇒ denegación sin auto-aprobación. El
  test-guardia de Fase 1 queda como vigilante de regresión, no como medición pendiente.
- **Fallback usado:** el previsto por § 16 para este resultado (registro del modo + no contar el
  permiso como humano), que ya está en la norma; nada que improvisar.

### P3 · Payloads reales de escritura (`ok` / `failed` / `ambiguous`)

- **Qué se comprobó:** la forma real de las respuestas de escritura del MCP `appian-dev` contra el
  entorno vivo, con al menos un payload por clase, escribiendo solo en una app `RGM_*` de práctica
  (`RGM_Practice_Record`).
- **Resultado real:**
  - **`ok`**, cuatro variantes de forma: `createConstant` (objeto con `uuid` + `versionId`),
    `updateConstant` (ídem + `previousVersionId`), `addCustomRecordField` (objeto con `uuid` +
    `versionId` del record type), `updateObjectSecurity` (eco del role map con `uuid`, sin
    versión).
  - **`failed`**, dos formas: error de la API de Appian (`API error (HTTP 400): Parent folder not
    found: …`) y error de validación del **propio servidor MCP**, que nunca llegó a Appian
    (`Unexpected error: 'TIPO_INEXISTENTE' is not a valid CreateConstantRequestType`).
  - **`ambiguous`**, una real: `reorderRecordTypeViews` (no-op con el orden vigente) responde 200
    con un **eco de la lista de vistas sin `uuid` del objeto escrito, sin `versionId` y sin
    marcador de error** — y con `nameExpr` re-canonicalizado respecto a la lectura previa y a la
    posterior, así que la respuesta ni siquiera describe el estado final. Obliga a relectura, que
    es la semántica exacta de la clase. Relectura hecha: `listRecordTypeViews` confirmó estado
    intacto.
  - **Sobre (envelope) tal y como lo ve un hook:** las respuestas MCP llegan a los hooks como
    **string** — éxito = JSON serializado, fallo = texto plano con prefijo `API error (HTTP …)`,
    error de tool = `<tool_use_error>…</tool_use_error>`. El clasificador debe parsear el string,
    no esperar un objeto.
- **Evidencia:** [`fase-0/p3-payloads-escritura.jsonl`](fase-0/p3-payloads-escritura.jsonl) (las 7
  capturas) y el registro del sobre en [`fase-0/p5-posttoolbatch.jsonl`](fase-0/p5-posttoolbatch.jsonl)
  (sesión del envelope run con `validateExpression` + `getConstant` inexistente).
- **Versión/entorno:** servidor `appian-dev` local (`lcp_mcp_server` por servlet), 2026-09-01.
- **Consecuencia:** el clasificador se escribe contra estas formas: JSON parseable con
  `uuid`/`versionId` ⇒ `ok`; prefijos `API error (HTTP`, `Unexpected error:`, envoltorio
  `<tool_use_error>` ⇒ `failed`; **todo lo demás ⇒ `ambiguous`** (el eco-sin-identidad del reorder
  demuestra que esa cola existe de verdad).
- **Fallback usado:** ninguno — la sonda salió por el lado «sí».
- **Nota de entorno:** el `500` histórico de `addCustomRecordField` por el servlet (barrido del
  06-ago-2026) **ya no se reproduce**: hoy responde 200 y crea el campo.

### P4 · Carga diferida de schemas MCP

- **Qué se comprobó:** que registrar los tres servidores Appian con carga diferida baja de verdad
  el suelo de contexto por turno. Tres condiciones, dos repeticiones, mismo prompt («Reply with
  exactly: hi»), mismos settings, mismo cwd, solo los servidores bajo `--strict-mcp-config`.
- **Resultado real** (input + cache_creation + cache_read; estable entre repeticiones):
  - Sin MCP: **25 246** tokens.
  - Tres servidores Appian, **carga diferida** (comportamiento por defecto, `ENABLE_TOOL_SEARCH`
    sin fijar): **28 311** (+3 065 sobre el suelo).
  - Tres servidores Appian, **carga completa** (`ENABLE_TOOL_SEARCH=false`): **114 922**
    (+89 676 sobre el suelo).
  - **Ahorro de la palanca: 86 611 tokens por turno.**
- **Evidencia:** `p4-*-r{1,2}.out.json` en el tmp del job (números transcritos aquí; el JSON de
  salida de `claude -p` incluye `usage`). Medido con el tokenizador de
  `claude-haiku-4-5-20251001`: § 12.4 ya avisa de que un tokenizador nuevo mueve las cifras — el
  orden de magnitud es lo que la sonda decide, y es inequívoco.
- **Versión/entorno:** Claude Code 2.1.248; deferral activa por defecto (`unset`); se desactiva
  con `ENABLE_TOOL_SEARCH=false`; hay `alwaysLoad` por servidor según la documentación oficial.
- **Consecuencia:** la fila «suelo de contexto al abrir el alcance ≤ 120 K» de § 17.5 **no se
  recalcula** (la palanca existe y deja el coste MCP en ~3 K); `/appian-init` (Fase 5) debe
  verificar que la deferral no esté desactivada, y la guía de § 12.4 puede citar la cifra real.
- **Fallback usado:** ninguno — no hizo falta recalcular la fila antes de escribir código.

### P5 · `PostToolBatch`

- **Qué se comprobó:** que el evento dispara en 2.1.248, con qué payload, si dispara con lotes de
  una sola llamada, y si el canal sirve para observar la carga de la skill oficial (§ 7.5).
- **Resultado real:**
  - **Dispara.** Con un lote de dos `Bash` paralelos llega **una** invocación con `tool_calls[]`
    de longitud 2; con una llamada única llega igualmente, con `tool_calls[]` de longitud 1.
  - **Campos reales por entrada:** `tool_name`, `tool_input`, `tool_use_id`, `tool_response` — y
    **nada más**. No existe `tool_result` ni un campo `error` separado (§ 7.4 los nombraba así):
    un fallo ejecutado llega como string dentro de `tool_response` (p. ej. `"Exit code 2\nls:
    cannot access …"`), y un error de tool como `<tool_use_error>…</tool_use_error>`.
  - **La skill es observable:** la invocación `Skill{skill: appian}` aparece como entrada del
    lote con su respuesta («Launching skill: appian»). El payload no trae la ruta resuelta de la
    skill — el mapeo nombre→raíz lo pone el hook. Las lecturas `Read` bajo la raíz serían entradas
    ordinarias del mismo canal.
  - **El lote ve más que `PostToolUse`:** la llamada `Skill` que falló (skill inexistente en ese
    hijo) apareció en `PostToolBatch` y **no** generó `PostToolUse`. (Existe `PostToolUseFailure`
    como evento aparte; el canal del lote cubre ambos casos en una sola invocación.)
  - El input del lote incluye además `session_id`, `transcript_path`, `cwd`, `prompt_id` y
    `permission_mode`. El evento **no admite matcher** (se configura sin él).
- **Evidencia:** [`fase-0/p5-posttoolbatch.jsonl`](fase-0/p5-posttoolbatch.jsonl) y el control
  [`fase-0/p5-posttooluse-control.jsonl`](fase-0/p5-posttooluse-control.jsonl).
- **Versión/entorno:** Claude Code 2.1.248, sesiones `claude -p` hijas.
- **Consecuencia:** `observe-reads` se implementa sobre `PostToolBatch` tal y como diseñó § 7.4;
  el gate de skill de § 7.5 **no se degrada a aviso**. Al codificar: leer `tool_response` y
  detectar error por contenido/forma, no por un campo `error` que no existe.
- **Fallback usado:** ninguno — ni el peaje por `PostToolUse` ni la degradación del gate.

### P6 · Los esquemas de escritura frente a lo que § 5.2 lee

- **Qué se comprobó:** volcado real de las **145 tools** del servidor (`tools/list` por MCP stdio,
  con paginación) y verificación, campo a campo, de que lo que cada regla de `task_min_kind` lee
  existe y contiene lo que la regla supone. El volcado incluye descripciones y schemas anidados
  (`$ref`/`oneOf` resueltos buscando en el schema completo, no solo en el nivel superior).
- **Resultado real, por regla:**

| Regla de § 5.2 | Lo que dice el esquema real | Veredicto |
|---|---|---|
| Vistas/filtros/acciones con `visibilityExpr` | El campo existe en las seis tools, pero **con dos nombres**: `visibilityExpression` en `add/updateRecordTypeView` y `add/updateRecordTypeUserFilter`; `visibilityExpr` en `add/updateRecordTypeAction`. (La superficie de lectura, `listRecordTypeViews`, usa `visibilityExpr`.) | ✅ con corrección de nombre **por herramienta** al escribir la regla |
| `parentFolderUuid` como campo mutado de un `update*` | **Ningún `update*` lleva `parentFolderUuid`** (búsqueda profunda incluida). Solo lo llevan 7 `create*` (`createConstant`, `createExpressionRule`, `createFolder`, `createIntegration`, `createInterface`, `createProcessModel`, `uploadDocument`). Mover de carpeta no es expresable por esta superficie | ⚠️ rama inalcanzable: **se elimina** de la regla (la mitad «en un `create` es contexto» sí aplica) |
| `updateFolder` cuando toca campos de seguridad | `updateFolder` = `{uuid, name, description}` — **no tiene campos de seguridad**. La seguridad de carpeta va por `updateObjectSecurity`, que ya fuerza `task` por sí sola | ⚠️ rama inalcanzable: **se elimina** (la garantía la da la fila de `updateObjectSecurity`) |
| Constantes de tipo GROUP o USER | `type` existe en `createConstant` **y** en `updateConstant` (opcional), **sin enum en el schema**; el vocabulario vive en la descripción de la tool: …, `USER`, `EMAIL_ADDRESS`, `GROUP`, **`USER_OR_GROUP`**, `GROUP_TYPE`, … | ✅ con ampliación: la regla debe cubrir también `USER_OR_GROUP` (y valorar `GROUP_TYPE`); la ausencia de `type` en un `update` ya la cubre el diseño (grant/preflight, fail-closed) |
| `*CustomRecordField*` y `configureRecordEvents` no contienen «RecordType» | Confirmado: `addCustomRecordField`, `updateCustomRecordField`, `deleteCustomRecordField`, `configureRecordEvents` — ninguno casa con un glob `*RecordType*` | ✅ tal cual lo supone el diseño |
| Cualquier borrado | Corpus real: **23 tools `delete*`** | ✅ |
| `updateInterface`/`updateExpressionRule` sustituyen la expresión entera | `expression` y `expressionFilePath` presentes en ambas; la descripción de `expressionFilePath` confirma «the file content is read and submitted as the expression» | ✅ (sostiene la retirada de umbrales de magnitud) |
| Escrituras de datos / seguridad / reorder | `insertRecordData`, `updateRecordData`, `deleteRecordData`, `updateObjectSecurity`, `reorderRecordTypeViews` existen con los campos que el diseño supone (`reorder` = `uuid` + `urlStubs[]` + `versionId`) | ✅ |

- **Además:** el corpus de escritura por verbo (`create|update|delete|add|remove|replace|upload|insert|configure|reorder`)
  son **78 tools**, no «~30» como redondea § 16 — no cambia ninguna regla, pero el volcado de
  referencia cubre las 145 y la clasificación completa es más trabajo del estimado. Varios schemas
  usan `$ref`/`oneOf`/`anyOf`: el matcher de campos de los gates debe mirar el schema completo.
- **Evidencia:** [`fase-0/appian-dev-tools-2026-09-01.json`](fase-0/appian-dev-tools-2026-09-01.json)
  (volcado íntegro) y [`fase-0/p6-comprobacion-esquemas.json`](fase-0/p6-comprobacion-esquemas.json)
  (informe por regla).
- **Versión/entorno:** servidor `appian-dev` (plug-in servlet), 2026-09-01.
- **Consecuencia:** `task_min_kind` se escribe con los nombres reales y sin las dos ramas
  inalcanzables. **Ninguna discrepancia reabre el freeze:** las tres caen en la fila 6 de la tabla
  de supuestos de § 21 («se corrige la regla antes de escribirla, no después»), que es exactamente
  el caso que esta comprobación existía para cazar.

---

## Objetos sonda que quedaron en el entorno

**Borrados el 2026-09-01 con confirmación del dueño**, siguiendo el workflow de borrado de la
skill oficial (dependientes comprobados antes; verificación después):

| Objeto | Comprobación previa | Borrado y verificación |
|---|---|---|
| `PR_FASE0_PROBE_TEXT` (constante TEXT) | `getObjectDependents`: 1 dependiente, y es la membresía en la propia app — ninguna expresión la usaba | `deleteConstant` → `Deleted successfully`; read-back `getConstant` → `HTTP 403 Constant not found` |
| `fase0ProbeCalc` (campo calculado en `PR Rental Status`) | `titleExpression` usa `value`, sin relaciones, única vista la `summary` por defecto | `deleteCustomRecordField` → `Deleted successfully`; read-back `listRecordTypeFields` → 4 campos, sin el sonda |

**El entorno queda sin residuo de la Fase 0.** De regalo, el borrado aportó una forma más al
clasificador de P3: un delete exitoso responde `{"result":"Deleted successfully"}` — **sin `uuid`
ni `versionId`** — así que el clasificador debe reconocer también esa forma (está añadida a
`fase-0/p3-payloads-escritura.jsonl` como `ok-variant-delete`).

`reorderRecordTypeViews` y `updateObjectSecurity` fueron idempotentes (sin cambio persistido); los
dos intentos `failed` no crearon nada.

---

## Estado de fases

| Fase | Estado |
|---|---|
| **0 · Sondas** | **DONE** (2026-09-01, DoD abajo) |
| 1 · Coste y consistencia | pendiente |
| 2 · Núcleo | pendiente |
| 3 · Suelo y evidencia | pendiente |
| 4 · Juez, matriz y skills | pendiente |
| 5 · Onboarding y documentación | pendiente |
| 6 · Puerta de salida | pendiente |

---

## DoD de Fase 0

El «Hecha cuando» de § 16 Fase 0, releído literal antes de este veredicto, condición a condición:

| Condición del DoD | Veredicto | Evidencia |
|---|---|---|
| Las **cinco** respuestas escritas **junto a** la norma | **PASS** | Este fichero vive en `docs/design/`, al lado de `appian-harness-0.7-1.0.md`, con las cinco sondas respondidas (tabla y secciones P1-P5) |
| …con la **fecha** contra la que se midieron | **PASS** | 2026-09-01, en la cabecera y en cada sonda |
| …con la **versión de Claude Code** | **PASS** | 2.1.248, en la cabecera y en P1/P2/P4/P5 |
| La tercera con **≥ 1 payload real por clase** | **PASS** | `fase-0/p3-payloads-escritura.jsonl`: `ok` ×4 al cierre (×5 tras la limpieza posterior), `failed` ×2, `ambiguous` ×1 con relectura |

Además, del encargo de la fase: la **sexta comprobación** (esquemas vs § 5.2) está hecha y
tabulada; **ningún resultado contradijo una decisión congelada** — las tres discrepancias de campo
caen en la fila «se corrige la regla antes de escribirla» de la tabla de supuestos de § 21, que es
salida prevista, no reapertura; y los **fallbacks** usados fueron exactamente los que la norma
deja escritos (solo P2 necesitó el suyo).

**Fase 0: DONE.** La suite del repo se ejecutó tras añadir este registro (sin tocar código):
resultado en el log de la sesión de implementación.
