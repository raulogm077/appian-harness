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

## Fase 1 · Coste y consistencia

Estado: **DONE (2026-09-02)** — DoD comprobado condición a condición al final de esta sección.
**Claude Code:** 2.1.248 (Windows 11) · sesiones de medida: `claude -p`, `claude-haiku-4-5-20251001`,
entorno saneado, `--strict-mcp-config` con el servidor `appian` real (solo lecturas/denegaciones:
ninguna escritura tocó el entorno).

| # | Trabajo | Qué quedó en el código | Test propio |
|---|---|---|---|
| U1 | Caché del intérprete | `run_hook.sh` cachea el candidato ganador en `${XDG_CACHE_HOME:-$HOME/.cache}/appian-harness/interpreter.v1` (candidato + resolución de `command -v`). Solo los tres literales `python3`/`python`/`py -3` se ejecutan: una caché manipulada es un fallo de caché, nunca un comando. Re-sondea si la resolución cambia, el contenido no es de la allowlist o el arranque devuelve 126/127 — ahí el payload sigue sin leer, así que no hay doble ejecución del hook | `TestTheInterpreterCache` (4) en `test_run_hook_launcher.py`; los tests preexistentes quedaron herméticos (XDG por test) |
| U2 | `closed-pending-human` | Enum `STATUS_*` (§ 4.2); `closure_gate` clasifica el cierre limpio — ≥ 1 aplazamiento aceptado ⇒ `closed-pending-human`, sin ninguno ⇒ `closed`, y el approve forzado del Stop repetido se registra `closed-with-debt` — y lo escribe en `evidence/task-closures.jsonl` (`from`→`status`, dedupe por tarea+estado). El registro tiene consumidor (§ 17.5, `measure_evidence`) y **no es autoridad**: la firma del estado en el fichero de alcance llega con el `state-gate` de Fase 2. Migración § 15: sin `status` ⇒ `in-flight`, nada se reescribe — un fichero 0.6 cierra igual que antes | `test_close_states.py` (7) |
| U3 | Estimación manual | `measure` (solo el literal `true`) en la config; `manualEstimateMinutes` se ancla **write-once con anotación** en `evidence/manual-estimates.jsonl` desde los dos puntos de observación (edición del fichero de tarea vía `log_evidence_write`, y el cierre como respaldo); un valor posterior distinto se **anota y no sustituye**; los inválidos nunca anclan; sin `measure`, una fila declara el campo inerte. `measure_evidence.py` reporta el denominador anclado y deja el **ratio** en NOT MEASURED: su numerador necesita la cuchilla de espera humana de § 17.6 (Fase 6) | `test_manual_estimate.py` (8) + 2 en `test_measure_evidence.py` |
| U4 | Valor de decisión | `PERMISSION_ASK = "ask"` como única constante en los cinco puntos de emisión/comparación, con el porqué citando P1; `run_hook.sh` apunta a la misma evidencia junto a su rama degradada | `TestTheFailClosedValueIsThePlatformsOnlyPromptingValue` (4) en `test_destructive_guard.py`: falla si cualquier camino fail-closed deja de emitir el literal que produce prompt en 2.1.248 |
| U5 | Sobrecoste de hooks | `scripts/measure_evidence.py` (nuevo): cuota de reloj como **unión de intervalos** contra la ventana más ancha (transcript ∪ hooks), suma acumulada aparte, calibración del spawn **etiquetada estimación**, NOT MEASURED cuando falta el insumo — nunca estimado en silencio. Captura opt-in en `run_hook.sh` (`APPIAN_HARNESS_TIME_LOG`): coste cero sin la variable | `test_measure_evidence.py` (8) |

### El número (la mitad del «Hecha cuando» que es una medición)

Dos sesiones reales con los hooks del plugin activos (evidencia:
[`fase-1/sobrecoste-hook-times.jsonl`](fase-1/sobrecoste-hook-times.jsonl) y
[`fase-1/sobrecoste-medicion.json`](fase-1/sobrecoste-medicion.json), con el método dentro):

- **Caché caliente (régimen permanente): 427 ms de mediana por invocación; 4,6 % del reloj** de una
  sesión de 32,2 s (5,2 % ajustado con la calibración del spawn de `sh`, 68,3 ms/invocación,
  **estimación**). Subcomandos medidos: `session-start`, `scope-gate`, `closure-gate`.
- Caché fría (primera sesión tras instalar): mediana 439 ms, máximo 1039,8 ms (el `session-start`
  que paga sonda y escritura de caché); 12,7 % de 21,9 s (14,2 % ajustado). `failure-notice`
  también medido aquí.
- La caché deja la invocación caliente en ~2/5 de lo que costaba: en el banco del repo, la segunda
  invocación pasó de 646 a 320 ms; en sesión real, `session-start` de 1040 a 656 ms.
- Lectura honesta de la cuota: dispara por **evento**, no por segundo — en sesiones de trabajo
  largas la proporción baja; la fila de § 17.5 se re-medirá sobre el caso ácido (Fase 6) con este
  mismo instrumento. `log-write` y `log-evidence-write` no se ejercitaron (los `Write` del hijo los
  denegó la capa de permisos de fichero en headless — la trampa que Fase 0 ya documentó); comparten
  lanzador y arranque de intérprete con los medidos, y esa paridad es expectativa de ingeniería,
  no medición.

### Interpretaciones fijadas al codificar (ninguna reabre el freeze)

- **DEFERRED ≙ clase a de § 9.5.** Los cinco criterios de `DEFERRABLE_CRITERIA` (validate_verdict)
  son todos «juicio humano pendiente»; los ids de residuo de clase b son **inalcanzables hoy**
  (el validador los rechaza), así que la exclusión se escribirá cuando llegue ese vocabulario
  (Fase 4) — regla P6: no se codifican ramas muertas.
- **El mapeo `kind`→`task` de § 15 no se implementó**: no tiene consumidor hasta `task_min_kind`
  (Fase 2); implementarlo ahora sería código muerto.
- **«Write-once con anotación» = anclaje auditable por observación**: el hook 0.6 no es el escritor
  del fichero de alcance (eso es el `state-gate` de Fase 2), así que write-once se garantiza por
  registro — el primer valor válido es el denominador y los cambios quedan anotados sin sustituirlo.
  El esquema de § 4.1 muestra el campo escalar, sin campo compañero: la anotación es del registro,
  no del fichero.
- **`task-closures.jsonl` es registro, no autoridad** — puente hasta que el hook firme `status`.
- Pendiente de alinear en Fase 5 (documentación de la release): `docs/design-notes.md § run_hook.sh`
  aún describe la sonda pagada en cada llamada; sigue siendo cierto **en el fallo de caché**, pero
  la frase debe citar la caché.

### DoD de Fase 1

El «Hecha cuando» de § 16 Fase 1, releído literal antes de este veredicto:

| Condición del DoD | Veredicto | Evidencia |
|---|---|---|
| El sobrecoste de hooks está **medido en una sesión real** | **PASS** | Dos sesiones `claude -p` reales con los hooks activos; 8 invocaciones cronometradas dentro de la sesión (no en banco sintético) |
| …y **reportado como número** | **PASS** | 427 ms/invocación (mediana, caliente); 4,6 % del reloj (32,2 s); tabla completa en `fase-1/sobrecoste-medicion.json` y arriba |
| Los **cuatro cambios tienen test propio** | **PASS** | U1: 4 tests · U2: 7 · U3: 8+2 · U4: 4 — nombrados en la tabla; suite completa del repo en verde tras la fase |

Sin reaperturas del DESIGN FREEZE: ninguna evidencia contradijo una decisión congelada.

---

## Fase 2 · El núcleo: alcance, permiso, perímetro y gate

Estado: **código DONE (2026-09-02)** — las diez unidades con test propio, suite del repo en verde
(627 tests + 39 subtests: 334 en `hooks/`, 293 en `scripts/`). DoD: dos de sus tres condiciones
**PASS** con evidencia; la tercera
(la pasada atendida de «un solo prompt») queda **NOT MEASURED con kit preparado** — ver el DoD al
final de esta sección. Plan de ejecución y decisiones unidad a unidad:
[`fase-2/plan-ejecucion.md`](fase-2/plan-ejecucion.md). Segunda opinión del enfoque: codex
(la herramienta `advisor` volvió a colgar la API, como el 1-sep — no se usó).

| # | Trabajo (§ 16 Fase 2) | Qué quedó en el código | Test propio |
|---|---|---|---|
| U1 | Perímetro declarado | `appianMcpToolPrefixes[]`; matchers por prefijo con el regex 0.6 solo como respaldo; frase literal de § 7.2 en `session-start`; sin clave ⇒ primera escritura de la sesión `ask` una vez, registrada (§ 15); **matchers de `hooks.json` ensanchados a `mcp__[a-zA-Z0-9_-]+__`** — el matcher estático no puede leer config, así que rutea todo verbo de escritura MCP y Python filtra | `test_perimeter.py` (13) |
| U2 | Despacho + esquema v2 | `_scope_policy`: sin `schemaVersion` ⇒ **política 0.6 intacta** (cierra bajo sus reglas); `2` ⇒ v07; otro valor ⇒ nadie lo define, `ask`. `_scope_schema_errors` con esquema **cerrado** (un campo mal escrito falla, no cae al default); 7 estados como constantes | `test_scope_schema.py` (12) |
| U3 | `task_min_kind` + `risk` | Clasificadores puros con § 5.2 y las 3 correcciones P6 (`visibilityExpression` en vistas/filtros vs `visibilityExpr` en acciones, por **presencia de clave** — un null que limpia también cuenta; sin ramas muertas); constantes con `USER_OR_GROUP` y `GROUP_TYPE`; lo desconocido compra `task`; **ningún umbral de magnitud**; `risk` como salida separada, escrito por el hook al observarlo | `test_task_min_kind.py` (20, incluye barrido del corpus real de 145 tools) |
| U4 | Máquina de estados vertical | `state-gate` (renombrado desde `log-evidence-write` en hooks.json, run_hook.sh y COMMANDS); tabla § 4.4 como datos; **proyección propiedad del hook** (`evidence/scope-projection.json`, tmp+rename, snapshot completo) como «lo que el hook recuerda haber escrito» — la validación compara contra ella, no contra filas greppables; estados a mano se **revierten**; sin firma ⇒ el alcance **no existe** para el gate; **contaminación**: un Write/Edit del agente sobre un journal del hook ⇒ `ask` hasta abrir instancia nueva (Bash sigue detectable-no-impedible hasta 0.8, § 4.3); `closure-gate` v07 firma las transiciones 3/5/13 con deuda `never-closed` en el tercer Stop | `test_state_gate.py` (18) |
| U5 | Grant A: identidad y contrato | Extractor **por herramienta** contra los esquemas reales (`_target_keys`): `appUuid`, carpetas padre y refs de relación/vista son contexto — el test de corpus comprueba que **todo** write tool declara un target que su schema contiene; sin grant/instancia ajena/`bypassPermissions` ⇒ `ask`; `creates[]` con tipo comparado contra la herramienta («se aprueba una superficie, no una cadena»); `maxAllowedObjects` **por entrada de `tasks{}`** | `test_grant.py` (13) |
| U6 | Grant B: irreversibles | Borrado concedido con dependientes frescos **idénticos al snapshot** fluye sin re-prompt (esa es la autorización por lote); difieren o faltan ⇒ `ask` (anti-TOCTOU); `deleteRecordData` sin `{"rows": N}` ⇒ NO MEDIDO, no pasa el grant; arranques contra `grant.processStarts` (sin falso `ask` por `allowedObjects`); extensiones amplían cobertura; `permissionMode` sellado por el hook al aparecer el grant | `test_grant_irreversibles.py` (9) |
| U7 | Vertical `pending`+`writeSeq` | El `allow` reserva N+1 bajo lock best-effort y deja la fila de intención **antes** de que salga la llamada; `log-write` resuelve **por `tool_use_id`** (nunca «último pending») contra las formas reales de P3 — incluida la del delete sin uuid — y todo lo demás ⇒ `ambiguous`; `PostToolUseFailure` resuelve como `failed` (P5: el error no produce PostToolUse); vínculos nombre↔UUID corroborados por **dos registros** (§ 4.1) — el flujo crear-y-refinar-por-UUID no fabrica `ask`; `risk` alto observado se sella en fichero+proyección | `test_pending_and_classifier.py` (18) |
| U8 | Caducidad § 7.6 | `verdict_expiry_errors`: caduca solo ante escritura `inScope` + `behavioural` de **su instancia** con `writeSeq` mayor; lista blanca `description`/`documentation` (**`name` fuera**); hash `expression`+`inputs[]` en PostToolUse, `expressionFilePath` leído de disco, ilegible ⇒ conductual; `failed` no caduca (no cambió nada); `ambiguous`/`pending` caducan (lado caro); `design` exenta. Consumidor pleno: el certify de Fase 4 | `test_verdict_freshness.py` (+8; los 12 de la política 0.6 intactos) |
| U9 | `suspendedScope` | Tope de uno; el hotfix **re-embebe la copia firmada** (la del agente no se cree); solape ⇒ `ask` con el detalle (§ 4.5: sí es decisión); cerrar el hotfix restaura el suspendido `in-flight` **sin nuevo grant**; caducidad por **sesiones** (`sessions.jsonl` + `sessionsSeen`, incremento una vez por sesión): a la 3.ª se anuncia y el grant muere — materializado como `grant: null` al reanudar | `test_suspended_scope.py` (8) |
| U10 | Causas de `ask` + E2E | Los `ask` de persona llevan los cuatro campos de § 7.3 en castellano (qué se paró · por qué · arreglo ejecutable · qué pasa si no); las tres causas retiradas: `closing` ⇒ allow con remedio, deriva anclada **sin** escrituras ⇒ corrección registrada (error interno), **con** escrituras ⇒ `ask` (causa 5); E2E: micro y task con `tasks{}` abren-escriben-cierran **con cero `ask`** | `test_v07_end_to_end.py` (2) + mensajes en el resto |

### Interpretaciones fijadas al codificar (ninguna reabre el freeze)

- **El motivo del abandono viaja en `request`** (`"abandon: <motivo>"`): las filas 9-10 de § 4.4
  exigen motivo y el esquema cerrado de § 4.1 no le da campo; un `"abandon"` a secas se rechaza
  con el remedio que enseña la forma.
- **Anclaje con enriquecimiento**: `instanceId`/`kind`/`risk` anclados al firmar; `grant` y
  `allowedObjects` quedan anclados **desde que el grant existe** — rellenarlos después del
  preflight es el orden obligatorio de § 4.1, no deriva.
- **Cierre v07 en Fase 2 = máquina de estados + journal respetado** (`pending` sin resolver
  bloquea). `_v07_closure_missing()` es el punto único que endurecen las fases siguientes: el
  suelo por secuencias (F3) y los veredictos del juez (F4), donde § 16 los sitúa. «Cierra limpio»
  hoy **no** significa suelo satisfecho.
- **Idioma**: lo que lee la persona (asks, frase de perímetro, anuncios) en castellano — las
  frases fijadas por la norma lo están; lo que lee el modelo sigue en inglés como el código.
- **Frescura anti-TOCTOU por igualdad de contenido**, no por mtime: § 1.3 no admite relojes y la
  igualdad con el snapshot es la garantía real. `removeGroupMember` va por la rama de borrado.
- **Escritura sobre alcance `closed`** ⇒ `ask` por la causa 2 (el grant murió con la instancia),
  no por la causa retirada «alcance en closing/closed» — esa se retiró para `closing`, donde la
  escritura fluye con remedio y la protege la caducidad por `writeSeq`.
- **Una escritura `failed` no caduca veredictos** (no cambió el artefacto); `ambiguous` y
  `pending` sí — lado caro.
- La caducidad por sesiones **no cuenta** el estado transitorio «suspendido en raíz sin hotfix
  abierto»: el contador de § 4.5 vive en `suspendedScope.sessionsSeen`, que solo existe embebido.

### Consecuencias absorbidas fuera de `hooks/`

- `docs/configuration.md`: la clave 10 (`appianMcpToolPrefixes`) y la fila de `sessions.jsonl`
  en la tabla de evidencia (los checks de documentación los exigen en la misma release).
- `README.md`: contador de tests de hooks 212 → 334.
- El test 0.6 «el matcher JSON no rutea otros servidores» quedó **invertido a propósito**: ahora
  rutea cualquier verbo de escritura MCP y es Python quien no dice nada de los ajenos — sin eso,
  un servidor renombrado jamás llegaría al código y § 7.2 sería papel.

### Revisión independiente y hallazgos

- **Enfoque** (antes de codificar): codex — reordenó las unidades (verticales, no capas), confirmó
  `writeSeq` derivado del journal y el corte 0.6/0.7 como dos políticas, y encontró el hueco de la
  fila `transition` falsificable, cerrado con la proyección + contaminación (ver arriba).
- **Código** (después): la revisión con contexto limpio **quedó pendiente** — el agente revisor
  cayó 3 de 3 veces por los cortes de API del día (el mismo síntoma que inutilizó `advisor`), y
  codex no puede leer disco local en esta máquina. Se ejecutará cuando la API se estabilice; el
  encargo exacto para relanzarla está en el plan (`fase-2/plan-ejecucion.md § Revisión pendiente`).
- **Mitigación ejecutada en su lugar** (2-sep): una **batería adversarial automatizada**
  ([`fase-2/probe-adversarial.py`](fase-2/probe-adversarial.py), reproducible) martillea los gates
  con ~380 combinaciones hostiles — 6 formas de grant inválido × 5 herramientas × 12 payloads
  degenerados, más objetivo fuera de grant, creación no concedida, tipo cambiado, borrado sin
  `deletions`, arranque sin `processStarts`, `deleteRecordData` sin conteo, violación de
  `task_min_kind`, los 4 terminales nacidos y escritos a mano, y la falsificación de proyección +
  fichero vía `Write` observado. **Resultado: 0 fallos** — nunca `allow` sin grant válido, nunca
  terminal sin firma, la contaminación dispara, y ninguna combinación tumba un hook con excepción.
  No sustituye el juicio de un revisor (no ve diseño, solo invariantes), y por eso la revisión
  sigue pendiente y dicha con estas palabras.
- **Hallazgo propio durante la re-pasada** (corregido el 2-sep, con test): el sello de
  `risk: "high"` observado podía convertirse en `ask` permanente inmerecido — un agente que
  reescribiera el fichero de alcance desde una copia vieja (sin el `risk` sellado) disparaba
  «deriva anclada» para siempre. Corrección: `risk` es campo del hook (§ 5.3) y ante discrepancia
  se **re-impone** desde la proyección, nunca se cuenta como deriva del contrato; bajarlo a mano
  tampoco pega (`TestRiskIsReimposedNotDrifted`).

### DoD de Fase 2

El «Hecha cuando» de § 16 Fase 2, releído literal:

| Condición del DoD | Veredicto | Evidencia |
|---|---|---|
| La **sonda de perímetro falla en verde y en rojo** contra dos configuraciones distintas | **PASS** | [`fase-2/sonda-perimetro.md`](fase-2/sonda-perimetro.md): lanzador real, tres configs — declarada (sin frase), ausente (frase literal + ask de migración una vez por sesión), y servidor renombrado (invisible sin clave, gateado con ella) |
| **Ningún `ask` falso sobre el corpus** | **PASS** (mitad determinista) | `test_grant.py::TestTheExtractorKnowsTheRealCorpus` (todo write tool tiene target en su schema real — sin él, falso `ask` garantizado), `test_task_min_kind.py::TestAgainstTheRealCorpus` (145 tools clasifican), y el E2E con **cero** `ask` en ciclos completos |
| Un `micro` y un `task` (con y sin `tasks{}`) abren, escriben y cierran en un proyecto de pruebas con **un solo prompt cada uno** | **NOT MEASURED** (exige sesión atendida: P2 demostró que en headless un `ask` deniega sin preguntar) | Mecánica equivalente sin persona: `test_v07_end_to_end.py` (0 asks del harness, cierre firmado). Kit listo para la pasada con el dueño delante: [`fase-2/kit-atendido.md`](fase-2/kit-atendido.md) |

Sin reaperturas del DESIGN FREEZE: ninguna evidencia contradijo una decisión congelada. El hueco
que la segunda opinión (codex) encontró — la fila `transition` falsificable con `Write` — se cerró
**dentro** de la clase de garantía que § 4.3 ya declara (detectable): proyección propiedad del
hook + contaminación observable; Bash queda para 0.8 como estaba escrito.

---

## Estado de fases

| Fase | Estado |
|---|---|
| **0 · Sondas** | **DONE** (2026-09-01, DoD abajo) |
| **1 · Coste y consistencia** | **DONE** (2026-09-02, DoD en su sección) |
| **2 · Núcleo** | **código DONE** (2026-09-02); DoD 2/3 PASS, pasada atendida NOT MEASURED con kit |
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
