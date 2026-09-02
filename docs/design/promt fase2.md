# Encargo · Implementar la Fase 2 de la 0.7 («El núcleo»)

> **Estado (2026-09-02): EJECUTADO.** Las diez unidades implementadas con test propio; suite del
> repo en verde (627 tests + 39 subtests); sonda de perímetro PASS en verde/rojo/renombrado;
> corpus sin falsos ask PASS; la pasada atendida «un solo prompt» queda NOT MEASURED con kit
> preparado (la ejecuta Raúl en interactivo). Registro normativo de lo hecho y medido:
> [`implementacion-0.7.md § Fase 2`](implementacion-0.7.md). Evidencia y plan:
> [`fase-2/`](fase-2/). Revisión independiente con contexto limpio: en curso al escribirse esto;
> sus hallazgos se triarán y quedarán en el registro. Commit: decisión de Raúl.

> **Esto no es diseño y no compite con la norma.** Es el encargo de arranque de la Fase 2,
> reconstruido el 2-sep-2026 desde § 16 de la única fuente normativa,
> [`appian-harness-0.7-1.0.md`](appian-harness-0.7-1.0.md). Si algo de aquí contradice la norma,
> manda la norma.

## El encargo

Implementar la **Fase 2 · El núcleo: alcance, permiso, perímetro y gate** tal y como la define
§ 16 de la norma, con las correcciones de campo que la Fase 0 dejó fijadas (P1-P6 en
[`implementacion-0.7.md`](implementacion-0.7.md)) y sin reabrir el DESIGN FREEZE. Depende de la
Fase 0 (valor de la decisión) y de nada más; la Fase 1 ya está DONE.

Los nueve frentes de la tabla de § 16 Fase 2, todos en `hooks/harness_hooks.py` +
`hooks/hooks.json` (+ `skills/appian-build/` para el contrato del grant):

1. **Perímetro declarado**: `appianMcpToolPrefixes[]`, matchers contra la clave, regex como
   respaldo, comprobación en `session-start` con la frase literal de § 7.2, y primera escritura
   `ask` sin la clave (§ 15).
2. **Unidad de alcance** con `schemaVersion: 2`, `instanceId`, los siete estados y la tabla de
   transiciones de § 4.4.
3. **Escritor único de `status`**: `request` del agente, escritura y firma del hook
   (`statusWriteSeq`), reversión de todo estado sin firma — subcomando **`state-gate`** (antes
   `log-evidence-write`).
4. **`suspendedScope`** embebido, disjunción, reanudación y caducidad por sesiones (§ 4.5).
5. **`task_min_kind(tool, tool_input)`** con las reglas de § 5.2 — tres umbrales menos, `risk`
   observado por el hook (§ 5.3), y las tres correcciones de esquema de P6.
6. **Permiso por lote** (§ 6): identidad canónica con extractor objetivo-vs-contexto, impacto por
   clase, colisiones de nombre, creaciones con tipo, anti-TOCTOU en borrados, extensión **una por
   alcance**.
7. **Fila de intención `pending`** en `PreToolUse` y su resolución en `PostToolUse`
   (`ok`/`failed`/`ambiguous` contra los payloads reales de P3).
8. **Caducidad por `writeSeq` y `behavioural`** con la lista blanca de metadatos (§ 7.6).
9. **Cinco causas de `ask`** con sus cuatro campos, y las tres retiradas a `additionalContext`
   (§ 7.3).

## Hecha cuando (DoD literal de § 16)

> Un `micro` y un `task` (con y sin `tasks{}`) abren, escriben y cierran en un proyecto de pruebas
> con **un solo prompt cada uno**, ningún `ask` falso sobre el corpus, y la sonda de perímetro
> falla en verde y en rojo contra dos configuraciones distintas.

Nota operativa: la mitad «un solo prompt» exige sesión atendida (P2: en headless un `ask` deniega,
no pregunta); lo que no pueda medirse sin el dueño delante se deja preparado como kit y se declara
NOT MEASURED, nunca estimado — el mismo trato que P2 recibió en la Fase 0.

## Reglas de la casa para esta ejecución

- Registro de lo hecho y medido: `implementacion-0.7.md` § Fase 2 (+ `fase-2/` para evidencia).
- Sin reaperturas del freeze salvo por las cinco causas de § 21, nombrándolas.
- Escrituras reales solo sobre apps `RGM_*`; borrados con confirmación uno a uno.
- Comentarios mínimos en el código (el porqué, no el histórico).
- Segunda opinión del enfoque vía `mcp__codex__codex` — **no** usar `advisor` (colgó 3/3 el 1-sep
  y volvió a fallar el 2-sep al arrancar esta fase).
- `git` lo ejecuta solo el coordinador, y el commit lo decide Raúl.
