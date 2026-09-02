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
| U2 | **Despacho por `schemaVersion` + esquema v2** | Despacho temprano: sin `schemaVersion` ⇒ **política 0.6 entera intacta** (el código actual, que cierra «bajo las reglas con las que se abrió», § 15); `schemaVersion: 2` ⇒ política 0.7. Dos rutas de decisión, infraestructura compartida (JSON, JSONL, paths, mensajes). Constantes de los 7 estados; validación del esquema v2 | `test_scope_schema.py` (12 tests) | **HECHA** — despacho en `scope_gate` (`_scope_policy`: v06/v07/unknown), `_scope_schema_errors` con esquema cerrado, 7 estados como constantes, cuerpo 0.6 extraído a `_scope_shared_reasons` del que v07 se irá separando | pendiente→**HECHA** |
| U3 | **`task_min_kind` + `risk` (clasificadores puros)** | `task_min_kind(tool, tool_input)` con § 5.2 y las 3 correcciones P6; constantes GROUP/USER/`USER_OR_GROUP`/`GROUP_TYPE`; lo desconocido ⇒ `task`; `risk` observado (§ 5.3) como salida separada (dos ejes, dos dueños); clasificación compartida del payload | `test_task_min_kind.py` (nuevo), corpus real `fase-0/appian-dev-tools-2026-09-01.json` | pendiente |
| U4 | **Máquina de estados vertical**: `state-gate` + firma + proyección + recuperación | Renombrar `log-evidence-write`→`state-gate` (hooks.json, run_hook.sh, COMMANDS); tabla § 4.4 como datos; `request`→transición firmada (`statusWriteSeq`); **proyección propiedad del hook** (`scope-projection.json`, tmp+rename, snapshot completo del alcance firmado) como «lo que el hook recuerda haber escrito» — la validación compara contra la proyección, no contra filas greppables; fila `transition` en `gate-decisions.jsonl` como rastro (con estado anterior/nuevo y vínculo al evento); **contaminación**: un Write/Edit del agente observado sobre un fichero del hook invalida la confianza y degrada a `ask` (Bash queda detectable-no-impedible hasta 0.8, § 4.3 sin cambio); sin proyección ⇒ «el alcance no existe a efectos del gate» | `test_state_gate.py` (18 tests) | **HECHA** — proyección en `evidence/scope-projection.json`; transiciones por `request` (tabla § 4.4 como datos); reversión de estados a mano; `instance-swap` sobre alcance vivo no firma; tamper de journals → ask; 0.6 solo se observa; `closure_gate` v07 firma 3/5/13 con `never-closed`; `_v07_closure_missing()` como punto único que endurecen F3/F4. Renombrado `log-evidence-write`→`state-gate` en hooks.json, run_hook.sh, COMMANDS y tests | — |
| U5 | **Grant A: identidad y contrato** | `grant.instanceId` anclado (cambio de campos anclados ⇒ `ask` solo con escrituras entre medias, § 7.3); extractor de identidad objetivo-vs-contexto (`appUuid`, refs de relación/vista/acción = contexto); `creates[]` con tipo comparado contra la herramienta del create; `collisions[]` presentes; evaluación de `maxAllowedObjects` **por entrada de `tasks{}`** | `test_grant.py` (13 tests) | **HECHA** — `_target_keys` por herramienta contra los esquemas P6 (test de corpus: todo write tool declara un target que su schema tiene); grant: sin grant/instancia ajena/bypassPermissions ⇒ ask; creates con tipo; atomicidad por entrada de `tasks{}`; `task_min_kind` impuesto; sin `activeRunFile` ni `leaseFile` en v07 (§ 15) | — |
| U6 | **Grant B: irreversibles y extensión** | Borrados con dependientes reconsultados (anti-TOCTOU: la re-consulta observada en `checks.jsonl`/registro, difiere ⇒ re-preguntar); `deleteRecordData` sin conteo de filas ⇒ no pasa el grant; `grant.processStarts` como clase propia; `grant.permissionMode` registrado y `bypassPermissions` no cuenta como humano; `extensions[]` solo el hook, **una por alcance** | `test_grant_irreversibles.py` (9 tests) | **HECHA** — borrado concedido con dependientes frescos idénticos NO re-pregunta (esa es la autorización por lote); difieren/faltan ⇒ ask; `deleteRecordData` sin `{"rows": N}` en `grant.deletions` ⇒ ask (NO MEDIDO no pasa); arranques contra `processStarts` (sin falso ask por `allowedObjects`); extensiones amplían cobertura; `permissionMode` sellado por el hook al aparecer el grant. Interpretaciones: frescura por igualdad de contenido (no mtime, § 1.3 sin relojes); `removeGroupMember` va por la rama de borrado; cambios de `extensions[]` por el agente = deriva anclada (la extensión la escribe el hook en Fase 4) | — |
| U7 | **Vertical `pending`+`writeSeq`+resolución** | En `allow`: lock de instancia → `max(writeSeq)` del journal → reserva N+1 → fila `pending` persistida **antes** de devolver el allow → unlock. `log-write` resuelve **por `tool_use_id`** (nunca «último pending»), append-only (la resolución es otra fila; un reductor toma la última correlacionada); clasificador P3 (`ok`/`failed`/`ambiguous`, delete sin uuid, sobres string); vínculos nombre↔UUID; `pending` sin resolver ⇒ tratado como `ambiguous` al cerrar | `test_pending_and_classifier.py` (nuevo) | pendiente |
| U8 | **Caducidad `writeSeq`+`behavioural`** | `coversThroughWriteSeq` vs escrituras `inScope: true` + `behavioural: true` de la instancia; lista blanca (`description`, `documentation`); hash `expression`+`inputs[]` en PostToolUse, `expressionFilePath` leído de disco, ilegible ⇒ `behavioural: true`; solo interfaz y expression rule; `design` exenta | `test_verdict_freshness.py` (v07; el actual queda para la política 0.6) | pendiente |
| U9 | **`suspendedScope`** | `request: suspend/resume/abandon`; tope de uno; disjunción (solape ⇒ `ask`); reanudación sin re-grant; `sessionsSeen` con `sessions.jsonl` y caducidad del grant a la 3.ª sesión (§ 4.5) | `test_suspended_scope.py` (nuevo) | pendiente |
| U10 | **Cinco causas de `ask` + cierre v07 + E2E** | Cuatro campos en todo `ask` (helper común, castellano — las frases fijadas por la norma son en castellano); las tres causas retiradas a `additionalContext`; `closure_gate` v07 con transiciones 3/4/5/13 y bloqueo del tercer Stop (§ 7.1); E2E micro y task; compatibilidad 0.6 probada | `test_ask_causes.py` + E2E | pendiente |

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

**Las diez unidades HECHAS** (U7: 18 tests · U8: +8 · U9: 8 · U10: 2 E2E + causas retiradas), suite
del repo en verde con **627 tests + 39 subtests** (334 en `hooks/`, 293 en `scripts/`). El registro normativo de lo hecho y medido, con
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
