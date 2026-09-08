# Plan de ejecución · Fase 2 (documento de trabajo, no normativo)

> Estado vivo de la implementación. La norma es `../appian-harness-0.7-1.0.md` § 16 Fase 2;
> el encargo, `../promt fase2.md`. Al cerrar la fase, lo medido pasa a
> `../implementacion-0.7.md` § Fase 2 y este plan queda como rastro.
> **Contexto operativo: la API falla a ratos (2-sep). Cada unidad se termina y se comprueba
> antes de empezar la siguiente; este fichero registra el avance unidad a unidad.**

## Orden de unidades (revisado con la segunda opinión de codex, 2-sep)

| # | Unidad | Qué entrega | Test | Estado |
|---|---|---|---|---|
| U1 | **Perímetro declarado** | `appianMcpToolPrefixes[]` en config; `_is_write_tool`/`_is_destructive_tool` casan por prefijo declarado con el regex 0.6 como respaldo; **matcher de `hooks.json` ampliado a todo `mcp__*` con verbo de escritura** (estático no puede leer config — codex lo confirma como el defecto más peligroso si se omite); frase literal de § 7.2 en `session-start`; sin clave ⇒ primera escritura de la sesión `ask` (§ 15), una vez por sesión, registrada | `test_perimeter.py` (13 tests) + paridad en `test_matcher_parity.py` | **HECHA** (suite 518 en verde) |
| U2 | **Despacho por `schemaVersion` + esquema v2** | Despacho temprano: sin `schemaVersion` ⇒ **política 0.6 entera intacta** (el código actual, que cierra «bajo las reglas con las que se abrió», § 15); `schemaVersion: 2` ⇒ política 0.7. Dos rutas de decisión, infraestructura compartida (JSON, JSONL, paths, mensajes). Constantes de los 7 estados; validación del esquema v2 | `test_scope_schema.py` (12 tests) | **HECHA** — despacho en `scope_gate` (`_scope_policy`: v06/v07/unknown), `_scope_schema_errors` con esquema cerrado, 7 estados como constantes, cuerpo 0.6 extraído a `_scope_shared_reasons` del que v07 se irá separando |
| U3 | **`task_min_kind` + `risk` (clasificadores puros)** | `task_min_kind(tool, tool_input)` con § 5.2 y las 3 correcciones P6; constantes GROUP/USER/`USER_OR_GROUP`/`GROUP_TYPE`; lo desconocido ⇒ `task`; `risk` observado (§ 5.3) como salida separada (dos ejes, dos dueños); clasificación compartida del payload | `test_task_min_kind.py` (nuevo), corpus real `fase-0/appian-dev-tools-2026-09-01.json` | **HECHA** — `test_task_min_kind.py` (20 tests, con barrido de las 145 tools) |
| U4 | **Máquina de estados vertical**: `state-gate` + firma + proyección + recuperación | Renombrar `log-evidence-write`→`state-gate` (hooks.json, run_hook.sh, COMMANDS); tabla § 4.4 como datos; `request`→transición firmada (`statusWriteSeq`); **proyección propiedad del hook** (`scope-projection.json`, tmp+rename, snapshot completo del alcance firmado) como «lo que el hook recuerda haber escrito» — la validación compara contra la proyección, no contra filas greppables; fila `transition` en `gate-decisions.jsonl` como rastro (con estado anterior/nuevo y vínculo al evento); **contaminación**: un Write/Edit del agente observado sobre un fichero del hook invalida la confianza y degrada a `ask` (Bash queda detectable-no-impedible hasta 0.8, § 4.3 sin cambio); sin proyección ⇒ «el alcance no existe a efectos del gate» | `test_state_gate.py` (18 tests) | **HECHA** — proyección en `evidence/scope-projection.json`; transiciones por `request` (tabla § 4.4 como datos); reversión de estados a mano; `instance-swap` sobre alcance vivo no firma; tamper de journals → ask; 0.6 solo se observa; `closure_gate` v07 firma 3/5/13 con `never-closed`; `_v07_closure_missing()` como punto único que endurecen F3/F4. Renombrado `log-evidence-write`→`state-gate` en hooks.json, run_hook.sh, COMMANDS y tests |
| U5 | **Grant A: identidad y contrato** | `grant.instanceId` anclado (cambio de campos anclados ⇒ `ask` solo con escrituras entre medias, § 7.3); extractor de identidad objetivo-vs-contexto (`appUuid`, refs de relación/vista/acción = contexto); `creates[]` con tipo comparado contra la herramienta del create; `collisions[]` presentes; evaluación de `maxAllowedObjects` **por entrada de `tasks{}`** | `test_grant.py` (13 tests) | **HECHA** — `_target_keys` por herramienta contra los esquemas P6 (test de corpus: todo write tool declara un target que su schema tiene); grant: sin grant/instancia ajena/bypassPermissions ⇒ ask; creates con tipo; atomicidad por entrada de `tasks{}`; `task_min_kind` impuesto; sin `activeRunFile` ni `leaseFile` en v07 (§ 15) |
| U6 | **Grant B: irreversibles y extensión** | Borrados con dependientes reconsultados (anti-TOCTOU: la re-consulta observada en `checks.jsonl`/registro, difiere ⇒ re-preguntar); `deleteRecordData` sin conteo de filas ⇒ no pasa el grant; `grant.processStarts` como clase propia; `grant.permissionMode` registrado y `bypassPermissions` no cuenta como humano; `extensions[]` solo el hook, **una por alcance** | `test_grant_irreversibles.py` (9 tests) | **HECHA** — borrado concedido con dependientes frescos idénticos NO re-pregunta (esa es la autorización por lote); difieren/faltan ⇒ ask; `deleteRecordData` sin `{"rows": N}` en `grant.deletions` ⇒ ask (NO MEDIDO no pasa); arranques contra `processStarts` (sin falso ask por `allowedObjects`); extensiones amplían cobertura; `permissionMode` sellado por el hook al aparecer el grant. Interpretaciones: frescura por igualdad de contenido (no mtime, § 1.3 sin relojes); `removeGroupMember` va por la rama de borrado; cambios de `extensions[]` por el agente = deriva anclada (la extensión la escribe el hook en Fase 4) |
| U7 | **Vertical `pending`+`writeSeq`+resolución** | En `allow`: lock de instancia → `max(writeSeq)` del journal → reserva N+1 → fila `pending` persistida **antes** de devolver el allow → unlock. `log-write` resuelve **por `tool_use_id`** (nunca «último pending»), append-only (la resolución es otra fila; un reductor toma la última correlacionada); clasificador P3 (`ok`/`failed`/`ambiguous`, delete sin uuid, sobres string); vínculos nombre↔UUID; `pending` sin resolver ⇒ tratado como `ambiguous` al cerrar | `test_pending_and_classifier.py` (nuevo) | **HECHA** — 18 tests; resolución por `tool_use_id`, nunca «último pending» |
| U8 | **Caducidad `writeSeq`+`behavioural`** | `coversThroughWriteSeq` vs escrituras `inScope: true` + `behavioural: true` de la instancia; lista blanca (`description`, `documentation`); hash `expression`+`inputs[]` en PostToolUse, `expressionFilePath` leído de disco, ilegible ⇒ `behavioural: true`; solo interfaz y expression rule; `design` exenta | `test_verdict_freshness.py` (v07; el actual queda para la política 0.6) | **HECHA** — +8 tests v07; los 12 de la política 0.6 intactos |
| U9 | **`suspendedScope`** | `request: suspend/resume/abandon`; tope de uno; disjunción (solape ⇒ `ask`); reanudación sin re-grant; `sessionsSeen` con `sessions.jsonl` y caducidad del grant a la 3.ª sesión (§ 4.5) | `test_suspended_scope.py` (nuevo) | **HECHA** — 8 tests; caducidad por sesiones y `grant: null` al reanudar |
| U10 | **Cinco causas de `ask` + cierre v07 + E2E** | Cuatro campos en todo `ask` (helper común, castellano — las frases fijadas por la norma son en castellano); las tres causas retiradas a `additionalContext`; `closure_gate` v07 con transiciones 3/4/5/13 y bloqueo del tercer Stop (§ 7.1); E2E micro y task; compatibilidad 0.6 probada | `test_ask_causes.py` + E2E | **HECHA** — el fichero `test_ask_causes.py` no llegó a existir: las causas se comprueban en los tests de su unidad y el E2E quedó en `test_v07_end_to_end.py` (3 ciclos) |

### Avisos de codex incorporados como reglas de implementación

- La resolución PostToolUse correlaciona por `tool_use_id`; dos escrituras paralelas pueden invertir el orden de respuesta.
- `statusWriteSeq` no identifica una transición (varias transiciones pueden compartir secuencia sin escritura entre medias): la fila `transition` lleva estado anterior→nuevo y el vínculo al evento.
- La recuperación necesita el **alcance completo** en la proyección, no solo `status` (restaurar `grant`, `allowedObjects`, `kind`).
- La latencia por releer JSONL crece con el proyecto y el timeout de hooks.json son 15 s con degradación hacia permitir (P1): en 0.7 se acota con registros pequeños por instancia y la rotación llega en Fase 3; si la medición del caso ácido lo pide, la proyección se amplía a índice con offsets (cache reconstruible, nunca autoridad).

## DoD y cómo se medirá

- **Sonda de perímetro en verde y en rojo**: dos configs (`appianMcpToolPrefixes` correcta / servidor renombrado sin clave) — headless, automatizable.
- **Ningún `ask` falso sobre el corpus**: `task_min_kind` + extractor de identidad evaluados contra las 145 tools reales de `fase-0/appian-dev-tools-2026-09-01.json` — test determinista.
- **`micro` y `task` abren-escriben-cierran con un solo prompt**: exige sesión atendida (P2). Se prepara kit reproducible (settings + guion) y la parte atendida se ejecuta con Raúl delante o queda NOT MEASURED con el kit listo.

## Decisiones de implementación fijadas al arrancar (ninguna reabre el freeze)

- `writeSeq` vive como contador derivado de `operations.jsonl` filtrado por `instanceId` (el hook es el único escritor de ese registro), no como campo mutable aparte: un solo escritor, una sola fuente.
- La firma de § 4.4 («una transición que el hook recuerde haber escrito») se materializa como fila `transition` en `gate-decisions.jsonl` — el hook la escribe al firmar y la relee para validar; `statusWriteSeq` en el fichero debe casar con la última fila.
- El corte 0.6/0.7 es `schemaVersion`: ausente ⇒ toda la lógica 0.6 actual se conserva para cerrar alcances viejos «bajo las reglas con las que se abrieron» (§ 15); presente=2 ⇒ máquina nueva. Nada se reescribe al migrar.
- Los subcomandos nuevos/renombrados mantienen el contrato del lanzador degradado de `run_hook.sh` (rama sin intérprete), que también hay que actualizar al renombrar.

## Interpretaciones fijadas al codificar (ninguna reabre el freeze; van al registro al cerrar)

- **El motivo del abandono viaja en `request`**: `request: "abandon: <motivo>"`. El esquema § 4.1
  declara `request` y las filas 9-10 de § 4.4 exigen «motivo presente», pero ningún campo del
  esquema cerrado lo alberga; un `"abandon"` a secas se rechaza con remedio que enseña la forma.
- **Anclaje con enriquecimiento**: `instanceId`, `kind` y `risk` quedan anclados al firmar la
  apertura; `grant` y `allowedObjects` quedan anclados **desde que el grant existe** — rellenarlos
  de `null` a valor es el orden obligatorio de § 4.1 (preflight → alcance+grant), no una deriva.
- **Cierre v07 en Fase 2 = máquina de estados.** `_v07_closure_missing()` es el punto único que
  las fases siguientes endurecen: el suelo por secuencias llega en Fase 3 y los veredictos del
  juez en Fase 4 (§ 16 los sitúa ahí). El registro lo dirá con estas palabras para que nadie lea
  «cierra limpio» como «suelo satisfecho».
- **`sessions.jsonl` y `sessionsSeen`** llegan con U9 (suspendido); hasta entonces la caducidad
  por sesiones no cuenta.

## Cierre del plan (2026-09-02)

**Las diez unidades HECHAS** (U7: 18 tests · U8: +8 · U9: 8 · U10: 3 E2E + causas retiradas), suite
del repo en verde con **629 tests + 39 subtests** (336 en `hooks/`, 293 en `scripts/`; el tercer
ciclo E2E lo añadió la reconciliación del 2-sep). El registro normativo de lo hecho y medido, con
el DoD condición a condición, está en `../implementacion-0.7.md` § Fase 2 — este plan queda como
rastro de trabajo. Evidencia de la sonda: `sonda-perimetro.md`. Pasada atendida: `kit-atendido.md`.

## Revisión pendiente (relanzar cuando la API se estabilice)

Un agente con contexto limpio (sin las conclusiones del autor), encargo: leer la norma §§ 4-7,
`hooks/harness_hooks.py` entero, `hooks.json`, `run_hook.sh`, los 9 ficheros de test nuevos y el
corpus `fase-0/appian-dev-tools-2026-09-01.json`; buscar (A) rutas a `allow` sin grant o sin
firma, (B) terminales sin firma u orden de eventos que firme mal, (C) falsos `ask` contra el
corpus real, (D) clasificador P3 contra las formas documentadas, (E) excepciones que tumben un
subcomando / os.replace / bools, (F) inconsistencias proyección↔fichero (bucles de revert, asks
permanentes), (G) reducciones con `toolUseId` None o `writeSeq` duplicado, (H) tests que pasan por
accidente. Salida: lista numerada verificada contra el código (fichero:línea, escenario, gravedad,
corrección mínima). Cayó 3/3 por cortes de API el 2-sep; la batería `probe-adversarial.py` (0
fallos) cubre mientras tanto los invariantes de A/B por fuerza bruta.

**Pasada parcial ejecutada en la reconciliación (2-sep).** No es la revisión con contexto limpio —
quien la hizo ya había leído las conclusiones del autor—, así que **el encargo sigue en pie**. Cubrió
A, B, D, F y G leyendo el código, y dejó un hallazgo verificado:

> **G-1 · Un `pending` sin `tool_use_id` no se resuelve nunca.**
> `harness_hooks.py:2028` correlaciona la resolución solo `if tool_use_id:`; sin él,
> `_log_write_v07` reserva `_observed_write_seq + 1` y escribe una fila con **secuencia nueva**,
> mientras `_unresolved_pendings` (`:1763`) indexa la reserva por `"seq-N"` y la resolución por
> `"seq-N+1"`. Comprobado ejecutando el par reserva→resolución: con `tool_use_id` quedan 0 pendings;
> sin él, queda **1 colgado**, y `_v07_closure_missing` bloquea el cierre hasta que el tercer Stop lo
> fuerza a `closed-with-debt`.
> **Gravedad: baja-media, y fail-closed** — nunca permite una escritura, solo impide un cierre limpio.
> **Alcance real:** P2 y P5 midieron que el input de todos los hooks trae `tool_use_id`, así que hoy
> es latente, no vivo. **No se ha corregido a propósito:** la corrección obvia («resolver el último
> pending») es justo la regla que U7 prohíbe, así que elegir el criterio de correlación de respaldo
> es una decisión de diseño, no una corrección mínima.
> **Decisión de Raúl (2-sep): va a la Fase 3**, que ya toca el registro de operaciones y su
> rotación. No se corrige en Fase 2 y no bloquea su cierre.

**C · falsos `ask` sobre el corpus real, extremo a extremo.** Más fuerte que el test del repo (que
comprueba que el extractor conoce una clave): para cada una de las **herramientas de escritura** del corpus (78 en aquella pasada; **79** al recontarlas el 3-sep con `_is_write_tool`, que es la cifra buena)
del corpus se montó un payload sobre el objeto concedido y se ejecutó `scope_gate` entero. **41
allow limpios, 37 `ask` que el diseño exige** (creación no concedida, irreversible sin snapshot,
`task_min_kind`), **0 falsos `ask`**.

**H · tests que pasan por accidente — un hallazgo, ya corregido.** Se rompieron a propósito tres
invariantes y se comprobó si la suite lo notaba. `allow` sin grant y alcance sin firma: **detectados**.
Pero **resolver por «último pending» en vez de por `tool_use_id` dejaba la suite entera en verde**:
el test de fuera de orden resuelve `tu-2`, que *es* la última fila, así que las dos reglas coinciden
por casualidad; y para `tu-1` los tests solo comprobaban `result`, nunca `writeSeq`. Como `writeSeq`
es lo que caduca veredictos (§ 7.6), una resolución con la secuencia de otra escritura caducaría
veredictos que esa escritura no tocó. **Corregido** con
`TestResolutionIsByToolUseId::test_the_earlier_reservation_keeps_its_own_sequence`; repetida la
mutación, ahora **falla como debe**.

## Revisión con contexto limpio · EJECUTADA (2026-09-02/03)

Agente independiente, sin las conclusiones del autor y con `implementacion-0.7.md` y este plan
**vedados** hasta terminar su análisis. Leyó las 3.053 líneas del hook, la norma §§ 4-7,
`hooks.json`, `run_hook.sh`, el corpus de 145 herramientas y la evidencia de Fase 0.
**12 hallazgos, 4 de gravedad alta.** Los cuatro altos fueron **reverificados por el autor** con
sondas propias antes de aceptarlos.

| # | Hallazgo | Estado |
|---|---|---|
| **1** | `cmd_failure_notice` liga `_config` y usa `config` ⇒ **`NameError` en todo proyecto activo**, tragado por el `except` de `main()`, que emite `{}` y sale 0. El subcomando estaba **muerto**, no degradado. Como P5 midió que un fallo de herramienta va a `PostToolUseFailure` y **no** a `PostToolUse`, toda escritura fallida quedaba `pending`: sin aviso de no-reintentes, cierre bloqueado con diagnóstico falso, y **veredictos caducados** contra lo que § 7.6 dice (`failed` no caduca; `pending` sí) | **CORREGIDO** + test de subcomando (`test_the_subcommand_runs_it_not_just_the_function`), que falla si se reintroduce |
| **2** | `_handle_request` corre **antes** de la reimposición de `risk` y del cálculo de deriva, y `_sign_transition` firma el `dict(scope)` del agente. Un solo `Write` que lleve `request` **y** un contrato ampliado firma el contrato ampliado **sin registrar `anchored-drift`**. Reverificado: escritura sobre un objeto nunca concedido ⇒ `allow`; el mismo `Write` sin `request` ⇒ `ask` (control). Un `request` **ilegal** lava igual | **CORREGIDO** — la reimposición de `risk` y el cálculo de deriva corren **antes** de honrar el `request`; con deriva y escrituras aplicadas no se firma nada y el `request` queda sin consumir. 3 tests + mutación |
| **3** | `suspendedScope` no está entre los campos anclados. Tras abrir el hotfix, el agente reescribe el suspendido embebido y **la proyección lo adopta**; al cerrar el hotfix se firma la versión del agente. Reverificado: `allowedObjects` del suspendido sustituido por un objeto nunca concedido, adoptado. `sessionsSeen: 0` desactiva además la caducidad de § 4.5 | **CORREGIDO** — `suspendedScope` y `resumeFrom` entran en los campos anclados, y `_restore_suspended_if_any` recibe la copia **firmada**, no la del agente. Test + mutación |
| **4** | El sellado de `grant.permissionMode` solo dispara si el grant llega en una edición **posterior** (`signed.grant is None`). Un grant presente **ya en la apertura** —el flujo que la tabla de § 4.1 documenta— se firma sin `permissionMode` y la escritura sale `allow`. Reverificado | **CORREGIDO** — `_seal_permission_mode` sella en la apertura, en el hotfix y en la edición ordinaria; y un grant **sin** modo registrado ⇒ `ask` (fail-closed). 4 tests + 2 mutaciones |
| 5 | El aviso de perímetro ya está en `reasons` cuando se evalúa `if not reasons:`, así que `_scope_v07_reasons` **no se ejecuta**: el `ask` habla solo del perímetro y **no menciona** que la escritura está fuera de alcance | **CORREGIDO** — el aviso de perímetro viaja en lista aparte y se concatena al final: ambas razones llegan juntas. Test + mutación |
| 6 | `task_min_kind()` se llama sin `constant_type` y ese parámetro **no tiene llamador de producción**. § 5.2 dice que el tipo «lo aporta el grant desde el preflight» y **no existe el canal**: el esquema v2 es cerrado y solo tiene `creates[].type`. Falso `ask` sistemático en `updateConstant` sin `type` | **RESUELTO EN LA NORMA** — § 21 reabierto por la causa 1: el canal es la **llamada** (`type` es campo real y opcional de `updateConstant`), no el grant. `decision-log.md` D-29. El código no cambia |
| 7 | Reserva sin `toolUseId` nunca se resuelve | = **G-1**, ya decidido para Fase 3. Confirmación independiente |
| 8 | `verdict_expiry_errors` compara `writeSeq` sin excluir `bool`: `"writeSeq": true` caducaría veredictos. Único de los cinco sitios sin la guarda | **CORREGIDO** — guarda `not isinstance(seq, bool)`. Test + mutación |
| 9 | El bucle del lock de `_reserve_write` no tiene `else`: sin `fd`, el append se hace igual ⇒ `writeSeq` duplicado. § 7.3 declara que en 0.7 no hay paralelismo | **CORREGIDO** — la fila lleva `lockless: true` cuando no se obtuvo el lock; § 7.3 mantiene 0.7 secuencial |
| 10 | El test de `failure_notice` llamaba a la **función**, no al subcomando: verde mientras producción estaba muerta | **CERRADO** con el hallazgo 1 |
| 11 | Cobertura **cero** del sellado de `permissionMode` y del anclaje: mutar `drifted = []` dejaba **336 passed** | **CORREGIDO** — `TestTheAnchorSurvivesARequest` (4) y `TestThePermissionModeIsSealedWhereverTheGrantAppears` (3) |
| 12 | `unittest.main()` colocado antes de la última clase de `test_state_gate.py`: no corre como `__main__` (sí bajo pytest) | **CORREGIDO** — `unittest.main()` al final del fichero |

**Frentes que el revisor declaró limpios, explícitamente:** extracción de identidad (79/79 con hit
en el corpus real), clasificador P3 (acierta las 8 formas reales; la mutación lo tumba), orden de
firma de `_sign_transition` (fila → proyección → fichero, correcto), `os.replace`, y proyección↔
fichero sin bucles ni asks permanentes. La regla de `parentFolderUuid` no implementada es **vacua**,
no defecto.

**Límite que el propio revisor declaró:** su pasada H no es exhaustiva — leyó enteros seis ficheros
de test y cuatro por grep dirigido. Y su verificación de C fue estructural, complementaria a la
barrida por payload que hizo el autor.

**Barrido H completado sobre ese límite (3-sep).** Siete mutaciones más, dirigidas a las zonas que
el revisor no leyó enteras. **Seis detectadas** —`updateObjectSecurity` forzando `task`, la caducidad
exigiendo `inScope`, el esquema v2 cerrado, los dependientes de un borrado, el `pending` que bloquea
el cierre, y el perímetro declarado (122 fallos)— y **una superviviente**:

> **H-2 · La comparación central del grant no tenía cobertura propia.** Borrar entera la
> comprobación «¿está el objetivo entre los objetos concedidos?» (`_grant_reasons`) dejaba las 347
> pruebas **en verde**. Motivo: todos los tests que parecían ejercitarla quedaban satisfechos
> **antes**, por la comprobación de `allowedObjects` en `_scope_v07_reasons`. Las dos listas se
> anclan por separado y **pueden diferir** — y lo que la persona aprobó es el grant, no
> `allowedObjects`. **Corregido** con
> `TestAWriteWithoutAGrantAsks::test_an_object_in_scope_but_outside_the_grant_still_asks`, que pone
> un objeto en el alcance y fuera del grant; repetida la mutación, ahora falla.

**Dónde corrigió al registro:** «`permissionMode` sellado al aparecer el grant» era cierto solo
para la mitad tardía del flujo (4); «campos anclados» se esquiva con cualquier `request` en el mismo
`Write` (2) y no cubre `suspendedScope` (3); y el `ask` de `updateConstant` sin `type` se contaba
como exigido por `task_min_kind` cuando en realidad lo exige porque falta el canal del tipo (6).

## Avance

- 2026-09-02 · Norma releída entera; código actual leído; encargo escrito; este plan escrito.
- 2026-09-02 · Segunda opinión de codex incorporada (orden revisado, proyección del hook, contaminación).
- 2026-09-02 · **U1 HECHA**: matchers por perímetro declarado con respaldo 0.6, frase literal § 7.2 en
  session-start, ask de migración § 15 una vez por sesión (registrado en `gate-decisions.jsonl`),
  matchers de `hooks.json` ensanchados a `mcp__[a-zA-Z0-9_-]+__` (el estático no puede leer config).
  Consecuencias absorbidas: fixtures declaran el perímetro; el test 0.6 «el matcher JSON no rutea
  otros servidores» queda invertido a propósito; `docs/configuration.md` documenta la clave (lista
  cerrada: 10); contador de tests del README 212→225. Suite: 518 pass.
- Decisión de idioma (U1): los textos que lee la persona (asks, frase de perímetro) van en
  castellano — las frases que la norma fija literalmente lo están; lo que lee el modelo
  (`additionalContext`, remedios internos) sigue en inglés como el resto del código.
