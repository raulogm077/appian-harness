# Auditoría final de consolidación · appian-harness 0.7 → 1.0

**Fecha:** 1-sep-2026 · **Encargo:** [`encargo-auditoria-consolidacion.md`](encargo-auditoria-consolidacion.md) ·
**Objeto auditado:** [`docs/design/appian-harness-0.7-1.0.md`](../design/appian-harness-0.7-1.0.md)

**Qué era esto.** No otra ronda de rediseño: una pasada de consolidación para dejar **una sola fuente
normativa sin contradicciones**, resolver lo que siguiera abierto de verdad, y cerrar con DESIGN
FREEZE. Este informe es su resultado y **no se repite**.

**Qué encontró, en una frase.** La documentación ya estaba casi consolidada; lo que no lo estaba era el
documento normativo **por dentro**. Sus dos apéndices de trazabilidad registraban decisiones de la
*primera* pasada de revisión como si siguieran vigentes, sin decir que la segunda las había revertido —
y desde ahí se habían filtrado al cuerpo. **Dos de esas filtraciones eran bloqueantes.**

---

## FASE 1 · Inventario documental

Barrido de todo el repositorio y de su directorio padre. Documentos que podían confundirse con diseño
vigente: **cuatro**. No había ningún `docs/harness-review/`, ningún borrador suelto y nada fuera del
repo.

| Documento | Fecha | Propósito | Estado | Sustituido por | Acción |
|---|---|---|---|---|---|
| `docs/design/plan-0.7-1.0.md` (2.250 l.) | 25-ago-2026 | Especificación de la 0.7 | **NORMATIVE** | — | **Reconstruido** → `appian-harness-0.7-1.0.md`; el original se elimina |
| ├─ su Apéndice A (finding → sección) | 25/27-ago | Trazabilidad de 63 hallazgos | **HISTORICAL** | — | **Extraído** a `docs/archive/` |
| ├─ su Apéndice B (autovalidación) | 25-ago | Validación de la ronda anterior | **OBSOLETE** | este informe | **Extraído** a `docs/archive/`, marcado como superado |
| `docs/design/decision-log.md` (802 l.) | 25-ago-2026 | El *porqué* de las reglas | **SUPPORTING** | — | **Corregido**: cabecera con rutas muertas y 5 decisiones revertidas |
| `docs/design/prompt.md` (489 l.) | 1-sep-2026 | El encargo de esta auditoría | **SUPPORTING** | — | **Movido** a `docs/audit/`: no es diseño y vivía en el directorio de diseño. Queda **lápida** en la ruta vieja — moverlo en silencio rompió una referencia viva, y esa es la regla de la casa |
| `docs/design-notes.md` (2.475 l.) | vigente | Por qué el **código 0.6.x** es como es | **SUPPORTING** | — | **Intacto.** No compite: es del código actual, lo citan 60+ líneas de fuente, y su propósito está declarado en su primera línea |
| `docs/{gates,workflow,installing,configuration,troubleshooting,when-the-harness-is-wrong}.md` | vigente | Manual de usuario de la 0.6.1 | **SUPPORTING** | — | **Intacto.** Documentan lo que el plugin hace **hoy**; se realinean en la Fase 5 de la 0.7 |

**Conclusión de la fase.** No sobrevive ningún fichero cuyo contenido pueda confundirse razonablemente
con el diseño vigente. El único que lo hacía —el `decision-log.md`, por su cabecera y por cinco
decisiones derogadas en silencio— ya no lo hace.

---

## FASE 2 · Reconstrucción de la fuente normativa

`docs/design/appian-harness-0.7-1.0.md`. **No es un parche sobre el anterior**, y tampoco un texto
nuevo escrito de memoria: el cuerpo del plan era correcto en el 95 % de su superficie y reescribirlo a
mano habría perdido contenido medido —cifras, trampas de plataforma, decisiones cerradas del dueño—
que ninguna auditoría puede recuperar. Lo que se reconstruyó es **la coherencia**:

1. **Los dos apéndices salen del documento normativo.** Eran la fuente de cuatro de las cinco
   contradicciones: histórico viviendo dentro de la norma, que es literalmente el defecto que este
   encargo venía a eliminar.
2. **Se resolvieron las cinco contradicciones** en las nueve secciones afectadas (F-01 … F-05).
3. **Se añadió § 21 · DESIGN FREEZE**, y § 0 lo indexa.

**Regla aplicada durante toda la fase:** eliminar, simplificar, corregir y consolidar — **cero piezas
arquitectónicas nuevas**. Ninguna de las correcciones añade un mecanismo; tres retiran uno.

---

## FASE 3-4 · Auditoría del documento consolidado

### Arquitectura

| Comprobación | Resultado |
|---|---|
| Una responsabilidad principal por componente | **Pasa.** § 7.1 declara la responsabilidad **única** de los siete subcomandos; § 13 la de las cinco skills, el agente y el comando. El único que tenía dos —`log-evidence-write`— la perdió y se renombró a `state-gate` |
| Ninguna duplicidad innecesaria | **Pasa.** § 3.1 reparte las seis zonas de solape con la skill oficial; en las seis gana la oficial |
| Frontera con la skill oficial | **Pasa.** R1 (§ 1.2): *si la skill oficial especifica cómo, el harness lo cita y exige su rastro*. Las dos divergencias deliberadas están declaradas con motivo (§ 3.2) |
| Frontera con Dev MCP | **Pasa.** § 3.4: no reimplementa ninguna operación ni cachea schemas |
| Frontera con Docs MCP | **Pasa.** § 3.4: no duplica su consulta |

### Proporcionalidad · los cuatro flujos

Ninguno activa un SDLC completo. El trivial cuesta **1 prompt** y, en 0.7, **0 o 1 jueces**.

### Skills · responsabilidad única

Las cinco tienen una sola, y `appian-best-practices` **no duplica la oficial**: conserva el criterio
(Definition of Done, los tres resultados, las clases de puerta, Cardinal Rules) y **no** la mecánica.
Su límite para no adelgazarla del todo está declarado y es real: es **el único material utilizable sin
MCP** (§ 3.3), porque la oficial es solo-MCP.

### Hooks · enforcement, no workflow

**Pasa, y con una corrección ya aplicada en la ronda anterior que conviene registrar:** `state-gate`
perdió la validación de formularios que el propio harness produce; `observe-reads` **acredita** y
declara explícitamente que *no decide nada y no puede parar nada*. Los siete aplican invariantes.

### Auditor · solo juicio no determinista

**Pasa, y es la mejora más grande del diseño.** § 9.2 reparte las siete puertas en tres naturalezas: 1
y 2 son **celdas importadas** del suelo determinista —el auditor no las juzga—, 3 y 5 son juicio *sobre
evidencia citada*, y solo 4, 6 y 7 son juicio pleno. El auditor ya no firma `PASS` en puertas que no
puede medir.

### Evidencia · consumidor y garantía

**Pasa.** Cinco artefactos sin consumidor fueron eliminados con su garantía perdida nombrada (§ 11.2), y
cuatro de las cinco garantías perdidas son literalmente **«ninguna»**.

### Contexto · progressive disclosure

**Pasa.** § 12: nada entra hasta que hace falta; ningún artefacto > 40 KB llega al contexto de nadie sin
pasar por un script que lo resuma; profundidad de referencia graduada por tamaño; schemas MCP diferidos.

### Agentes · solo cuando el aislamiento lo justifica

**Pasa.** **Un** agente desplegable, con tres invocaciones. § 1.5 lo declara como regla que el documento
se aplica a sí mismo: *si una comprobación es determinista, no lleva agente*. Todo el § 8 es
determinista y no compra ninguno.

### Appian · diseño genérico

**Pasa, y está sujeto por un test.** El caso ácido se define **por propiedades** (§ 17.2); § 18.3 exige
que `grep -rn "GDE_"` sobre el código devuelva cero.

### Decisiones problemáticas ya conocidas · las 21 del encargo

| # | Punto | Decisión vigente | Sección |
|---|---|---|---|
| 1 | ¿Dos o tres tamaños? | **Dos**: `micro`, `task` | § 5.1 |
| 2 | Qué significa `feature` | **No existe como tamaño.** Es un `task` con `tasks{}`; solo sobrevive leyendo alcances 0.6 | § 5.1, § 15 |
| 3 | ≥ 3 dependientes | **Retirado.** El conteo se conserva en el prompt del grant y en el comando de regresión | § 5.2 |
| 4 | Umbral del 30 % | **Retirado** | § 5.2 |
| 5 | ≥ 200 líneas | **Retirado** — ⚠️ **F-01, era la contradicción bloqueante** | § 5.2, § 5.6, § 17.2 |
| 6 | Interfaces publicadas en Site | Modula el **carril**, nunca el tamaño | § 5.5 |
| 7 | Fallo de `testInterface`/N2 | **Nunca cambia el `kind`.** Corroborar → distinguir de regresión → evidencia alternativa **por clase** | § 8.7 |
| 8 | `closed-pending-human` | Estado propio, no se pliega en `closed-with-debt` | § 4.2, § 4.4 fila 4 |
| 9 | `context-floor` | **Opt-in** tras `measure: true`, apagado por defecto | § 11.2, § 12.4 |
| 10 | `manualEstimateMinutes` | **Opt-in**, mismo interruptor; en el esquema | § 4.1, § 12.4 |
| 11 | `build.md` | **Eliminado.** Sin consumidor; el juez lo tiene prohibido | § 11.2 |
| 12 | `risk-downgrades` | **Eliminado.** Con `risk` observado no hay rebaja que registrar | § 5.3, § 11.2 |
| 13 | `leaseFile` | **Fuera de 0.7**; vuelve en 0.8 con la receta de paralelismo | § 11.2, § 15, § 18.1 |
| 14 | Anti-salami | **Tapón** en 0.7 (cuenta creaciones de tipos distintos); la **regla** solo en 0.8 y solo si la magnitud lo pide | § 5.7, § 17.4, § 18.1 |
| 15 | Quién escribe el registro de carga de la skill oficial | **El hook** (`observe-reads`), desde lo observado. Rama honesta: si no puede observarlo, el gate **se degrada a aviso** | § 7.5 |
| 16 | Quién escribe los estados | **El hook, los siete, firmados.** El agente solo pide vía `request` | § 4.3 |
| 17 | Quién puede modificar `grant` | El constructor lo abre; **`extensions[]` y `permissionMode` solo el hook**; toda edición posterior lo invalida entero | § 4.1, § 6.1 |
| 18 | Cuántos prompts humanos por alcance normal | **Uno.** Más, como mucho, **una** extensión por alcance — ⚠️ **F-02** | § 6.3, § 6.4, § 17.1 |
| 19 | Cuándo se ejecuta `design` | Por lo que el alcance **hace**, no por su etiqueta: obligatorio si crea o cambia estructura/seguridad/process model; opcional y **registrado** si solo modifica; exento en solo-borrado | § 5.6 |
| 20 | Cuándo se ejecuta `certify` | Al cerrar, **una vez por alcance** (por funcionalidad si hay `tasks{}`) | § 9.1 |
| 21 | Qué puertas pueden bloquear | **CARDINAL** bloquea · **RECOMENDADA** bloquea una vez · **CONTEXTUAL** (rendimiento, mantenibilidad) **no bloquea** | § 9.3 |

**Ninguna sección responde distinto a otra en ninguno de los 21 puntos** tras aplicar F-01 … F-05.
Verificado mecánicamente, no leyendo: la búsqueda de cada término contradictorio sobre el documento
final devuelve **solo** las ocurrencias que declaran la retirada.

---

## FASE 5 · Comparación contra el baseline

*Baseline: Claude Code + skill oficial `appian` + Appian Dev MCP + Appian Docs MCP.*
Pregunta aplicada a cada componente: **si lo elimino, ¿qué garantía concreta pierdo?**

| Componente | Veredicto | Garantía diferencial que se pierde sin él |
|---|---|---|
| `scope-gate` (`PreToolUse`) | **KEEP** | Una escritura sobre un objeto no concedido sale. `PreToolUse` **no existe en markdown** |
| `closure-gate` (`Stop`) | **KEEP** | Un agente declara terminado lo que no midió. No hay dónde enganchar un `Stop` |
| `state-gate` (`PostToolUse`) | **KEEP** | El estado terminal se escribe a mano y el cierre se aprueba solo. Sin firma no hay máquina de estados |
| `log-write` (`PostToolUse`) | **KEEP** | La caducidad de veredictos y el vínculo nombre↔UUID: sin `writeSeq`/`behavioural` observados, un veredicto vale para siempre |
| `observe-reads` (`PostToolBatch`) | **KEEP** | La cobertura por objeto (`checks.jsonl`) y el rastro de la skill oficial escrito por quien no es el interesado |
| `session-start` | **KEEP** | La memoria que sobrevive al compactado y **el aviso de perímetro**: sin él, «instalado y no gobierna nada» es indetectable |
| `failure-notice` | **KEEP** | El reintento a ciegas sobre una escritura fallida. Barato y sin sustituto |
| `appian-auditor` (agente único) | **KEEP** | Revisión con **contexto fresco**. La contraparte oficial es *Adversarial **Self**-Review*: el mismo contexto juzgando su propio plan |
| `appian-specify` | **KEEP** | Especificación. **Sin contraparte ninguna** en la capa oficial |
| `appian-plan` | **KEEP** | Partición con tope, criterios por tarea, olas paralelizables y **los tipos manuales en su posición del grafo** |
| `appian-build` | **KEEP** | El preflight, la apertura del alcance y **el grant por lote**: la capa oficial confirma por operación, sin memoria entre ellas |
| `appian-review` | **KEEP** | El despacho al juez **sin la conclusión del constructor**, y la petición de cierre |
| `appian-best-practices` | **KEEP, adelgazada** | El criterio, y **el único material utilizable sin MCP**. La mecánica ya la perdió (§ 3.1) |
| `/appian-init` | **KEEP** | Decir la verdad sobre la instalación: sonda de hooks y **sonda de perímetro**, con frase literal |
| `validate_verdict.py` | **KEEP** | Que un agente **no pueda auto-concederse** un aplazamiento, y el tope de re-emisiones como enforcement |
| `n2_interface_tree.py` (+N3) | **KEEP** | Distinguir poblado de vacío **sin volcar 218 KB**, accesibilidad automatizable y el grafo del process model |
| `sail_static_check.py` | **KEEP** | La ejecución **determinista** de un checkpoint que hoy solo se cumple si el modelo se acuerda |
| `measure_evidence.py` | **KEEP** | Las puertas de § 17 medidas, con las reglas de método que impiden que la cifra esté mal contada |
| `parallel_safety.py` | **KEEP** | `EXIT_NOT_MEASURED` y lo que un worktree **no** aísla: Appian es compartido |
| `build.md` · `risk-downgrades.jsonl` · `leaseFile` (0.7) | **REMOVE** | **Ninguna.** Ya eliminados en el diseño (§ 11.2) |
| `context-floor.json` · `manualEstimateMinutes` | **SIMPLIFY** | Ninguna para el usuario: pasan a opt-in |
| `appian-verify` · `appian-run` (skills) · `appian-verifier` · `appian-reviewer` (agentes) | **REMOVE** | **Ninguna.** Se funden en `appian-review` y en el juez único. Siguen en el repo: es trabajo de la Fase 4, no un defecto del diseño |

**No queda ningún KEEP sin garantía diferencial explícita.**

---

## FASE 6 · Control de complejidad

Búsqueda dirigida de los diez patrones de desperdicio del encargo sobre el documento consolidado.

| Patrón buscado | Encontrado |
|---|---|
| Misma validación varias veces | **No.** R3 lo prohíbe y `checks.jsonl` lo hace verificable; la caducidad exige escritura conductual entre medias |
| Varios agentes revisando lo mismo | **No.** Un agente, tres invocaciones con rúbricas disjuntas |
| Re-emisiones sin información nueva | **No, y es lo único que pasó de auditable a impedible**: `validate_verdict.py` rechaza el tercer veredicto sin `findings[].id` nuevo, comparando ficheros |
| Full regression cuando no corresponde | **No.** El `regressionCommand` va acotado al alcance; el barrido completo es opt-in |
| Polling | **No.** *«Ningún agente de este harness espera en bucle sondeando un fichero»* (§ 9.1) |
| Waits | **No.** Los jueces independientes se despachan **a la vez** |
| Artefactos nunca consumidos | **No.** Cinco eliminados; el resto tiene consumidor nombrado en § 11.1 |
| Prompts por errores internos | **No.** Tres de las ocho causas de `ask` pasaron a remedio al **modelo** (§ 7.3) |
| Duplicación de documentación oficial | **No.** Seis zonas repartidas, todas a favor de la oficial |
| Puertas que no protegen un riesgo | **No.** Las dos que solo protegían estilo dejaron de bloquear (§ 9.3) |

### Clasificación de cada pieza

**A** trabajo productivo · **B** garantía necesaria · **C** evidencia necesaria · **D** desperdicio.

| Pieza | Clase | Por qué esa clase |
|---|---|---|
| `appian-specify` | **A** | Produce la especificación: es trabajo, no ceremonia sobre el trabajo |
| `appian-plan` | **A** | Produce la partición en tareas y las olas |
| `appian-build` | **A** | Construye. Es el único punto de entrada |
| `appian-review` | **B** | Despacha al juez **sin la conclusión del constructor** y pide el cierre |
| `appian-best-practices` | **B** | El criterio, y el único material utilizable sin MCP |
| `appian-auditor` | **B** | El juicio independiente con contexto fresco |
| `scope-gate` | **B** | Impide la escritura fuera del alcance concedido |
| `closure-gate` | **B** | Impide que cierre lo que no se midió |
| `state-gate` | **B** | Hace cumplir la máquina de estados y revierte lo no firmado |
| `failure-notice` | **B** | Impide el reintento a ciegas sobre una escritura fallida |
| `/appian-init` | **B** | Las dos sondas que convierten «instalado y no gobierna nada» en visible |
| `validate_verdict.py` | **B** | Impide que un agente se auto-conceda un aplazamiento; tope de re-emisiones |
| `sail_static_check.py` | **B** | Ejecuta un checkpoint que hoy solo se cumple si el modelo se acuerda |
| `parallel_safety.py` | **B** | Lo que un worktree **no** aísla: el entorno Appian es compartido |
| `log-write` | **C** | `operations.jsonl`, el vínculo nombre↔UUID y la clasificación conductual |
| `observe-reads` | **C** | `checks.jsonl` y el rastro de la skill oficial |
| `session-start` | **C** | La memoria que sobrevive al compactado, leída en voz alta |
| `n2_interface_tree.py` (+N3) | **C** | Produce la señal que sustituye a 218 KB de árbol |
| `measure_evidence.py` | **C** | Mide las puertas de § 17 sin contaminar la medida |
| `dependents.json` · renders · `n2-*` · `render-signals.json` | **C** | La evidencia que el suelo acredita |
| `practices-{design,certify,risk}.json` | **C** | El veredicto y su trazabilidad |
| Los seis registros `*.jsonl` | **C** | Cobertura, decisiones, deuda y sesiones |
| `build.md` | **D** | **Ya eliminado.** Sin consumidor; el juez lo tiene prohibido |
| `risk-downgrades.jsonl` | **D** | **Ya eliminado.** Sin escritor ni lector |
| `leaseFile` en 0.7 | **D** | **Ya retirado.** Sin consumidor hasta que exista paralelismo |
| `context-floor.json` y `manualEstimateMinutes` **obligatorios** | **D** | **Ya opt-in.** Un prompt que no es una decisión, por una métrica que no puntúa |
| `risk: trivial` / `risk: standard` | **D** | **Ya eliminados.** Un enum de tres valores del que solo uno decide algo |
| Las 3 causas de `ask` retiradas | **D** | **Ya retiradas.** No eran decisiones de una persona |
| Los 4 umbrales de magnitud | **D** | **Ya retirados** — el cuarto, en esta auditoría (F-01) |
| `feature` como tercer tamaño | **D** | **Ya eliminado.** Era un `task` con partición |
| `appian-verify` · `appian-run` · `appian-verifier` · `appian-reviewer` | **D** | Eliminados **en el diseño**; siguen en el repo hasta la Fase 4 |

**Todo lo clasificado D está eliminado, y ninguna pieza viva quedó sin clase.** La única D que aún
existe como fichero son las dos skills y los dos agentes que la Fase 4 borra: es trabajo de
implementación pendiente, no una decisión abierta.

**Clase D superviviente en el diseño: cero.** Nada que eliminar que no estuviera ya eliminado.

---

## FASE 7 · Findings

Solo lo **nuevo o realmente abierto**. Los 63 hallazgos de las dos pasadas anteriores están cerrados y
**no se reabren ni se reformulan**: se comprobó que ninguno de estos cinco es un duplicado semántico de
aquellos — los cinco son **regresiones de la consolidación**, no defectos de diseño.

### BLOCKER — 2, ambos resueltos

**F-01 · El umbral de ≥ 200 líneas estaba retirado y vivo a la vez.**
*Evidencia:* § 5.2 lo retira con argumento completo y la 2ª pasada lo confirma; pero seguía decidiendo
en **cinco** sitios — § 5.2 párrafo final, § 5.6 (disparador de `design`), § 17.2 tabla y párrafo
(forzador de **tamaño**), § B.6, y A.3-F030 lo declaraba vigente.
*Impacto:* como «sustituidas» solo puede significar «enviadas» —la herramienta sustituye la expresión
entera—, el umbral **dispara en toda interfaz grande**. Vivo, convierte cualquier edición de una
pantalla grande en `task` con `design` obligatorio y **reabre el caso ácido**, que es el defecto que la
0.7 entera existe para arreglar. Y ninguna puerta lo habría detectado: miden escapes por instrumento y
por exposición, no por magnitud.
*Cambio mínimo aplicado:* retirado en todas partes. § 17.2 fila 3 pasa a **`micro` con revisor y
`design` opcional y registrado**, que es la pieza que **ya existía** en § 5.6 — no se añadió ninguna.
*Estado:* **RESUELTO.**

**F-02 · La extensión de grant tenía dos topes contradictorios.**
*Evidencia:* «una por **alcance**» en § 6.3 y § 9.4; «una por **ciclo**» en § 6.4-4, § 16 Fase 2, § 16
Fase 4 y A.3-F039.
*Impacto:* «una por ciclo» con el tope de 3 ciclos permite **tres prompts de extensión por alcance**
además del grant, lo que revoca en silencio una decisión cerrada del dueño (*«me pida permiso una vez
indicándome los objetos que va a tocar»*) y rompe la condición de salida § 17.1.
*Cambio mínimo aplicado:* **una por alcance** en los cuatro sitios; `decision-log.md` D-24 corregido
con el motivo de la reversión.
*Estado:* **RESUELTO.**

### HIGH — 1, resuelto

**F-03 · El histórico vivía dentro de la norma, y era la fuente de F-01, F-02 y F-05.**
*Evidencia:* los apéndices A y B registraban las decisiones de la 1ª pasada (A.3-F030 → «un solo umbral
≥ 200 líneas»; A.3-F039 → «una extensión por ciclo»; A.1-F036 → «≤ 1,5 M») **sin marcar** que A.4 las
había revertido.
*Impacto:* un lector que abría el documento normativo por el apéndice —lo natural para comprobar qué se
decidió sobre un defecto— leía la versión derogada como vigente. Es exactamente el modo de fallo que
este encargo describe, ocurriendo **dentro de un solo fichero**.
*Cambio mínimo aplicado:* extraídos a `docs/archive/trazabilidad-hallazgos-0.7.md`, con cabecera de no
normatividad y **una tabla de las cuatro filas superadas** — listadas en vez de editadas, porque un
archivo histórico que se reescribe deja de ser histórico.
*Estado:* **RESUELTO.**

### MEDIUM — 2, resueltos

**F-04 · La tabla de la Fase 3 estaba partida en dos, con dos «Hecha cuando» contradictorios.**
*Evidencia:* § 16 Fase 3 · el bloque de cierre corregido por A.4 #12 se **insertó en mitad de la
tabla** en vez de sustituir al antiguo; seis filas quedaron huérfanas debajo y la tabla no renderizaba.
*Impacto:* dos condiciones de terminación distintas para la misma fase, y la que quedaba al final era
la **derogada** — la que permitía declarar la Fase 3 hecha con un instrumento que entrega la Fase 4.
*Cambio mínimo aplicado:* tabla reunificada, un solo «Hecha cuando», el vigente.
*Estado:* **RESUELTO.**

**F-05 · `decision-log.md` se leía como norma y apuntaba a ficheros inexistentes.**
*Evidencia:* cabecera con `docs/harness-review/audit/` y `docs/harness-review/plan-0.7-1.0-revised.md`,
rutas retiradas al consolidar; D-28 nombraba la segunda como «*la* especificación»; y D-03, D-12, D-23,
D-24 y D-26 estaban derogadas sin decirlo.
*Impacto:* segunda fuente con aspecto de norma — el defecto declarado del encargo.
*Cambio mínimo aplicado:* cabecera de no normatividad, rutas corregidas, y las cinco decisiones
marcadas **en su sitio** con qué las revirtió y por qué.
*Estado:* **RESUELTO.**

### LOW — 1, resuelto

**F-06 · «≤ 1,5 M por objeto certificado» sobrevivía junto al umbral vigente de 2 M**, en § 17.5
(párrafo de cierre) y A.1-F036. Con 1,5 M la puerta suspende por construcción contra la estimación de
1-2 M del propio § 9.2. **RESUELTO.**

### Duplicados semánticos descartados

Se comprobó que **ninguno** de los seis repite un hallazgo ya cerrado con otras palabras. F-01 y F-02
son *regresiones* de A.4 #1 y A.4 #5 —el diseño ya los había decidido bien y el texto no lo reflejaba
entero—, no nuevas objeciones a esas decisiones. No se generó ningún finding sobre materia ya resuelta.

---

# RESULTADO

## 1 · Documentos eliminados

| Documento | Motivo |
|---|---|
| `docs/design/plan-0.7-1.0.md` | **Sustituido** por `appian-harness-0.7-1.0.md`. No se deja stub ni redirección: un segundo fichero legible como diseño es el defecto que se está cerrando |

Nada más se eliminó. No había borradores, copias ni documentos «por si acaso» que borrar.

## 2 · Documentos archivados

| Documento | Motivo de conservarlo |
|---|---|
| `docs/archive/trazabilidad-hallazgos-0.7.md` | **Trazabilidad real**: permite comprobar qué se decidió sobre cada uno de los 63 hallazgos sin reabrir ninguno. Aislado, con cabecera de no normatividad y con las cuatro filas superadas listadas al principio |

## 3 · Documentos conservados, y su función exacta

| Documento | Función |
|---|---|
| `docs/design/appian-harness-0.7-1.0.md` | **ÚNICA FUENTE NORMATIVA.** Lo que se implementa |
| `docs/design/decision-log.md` | El **porqué** de 28 decisiones. Se consulta; **no es autoridad** |
| `docs/audit/final-consolidation-audit.md` | Este informe |
| `docs/audit/encargo-auditoria-consolidacion.md` | El encargo que lo produjo |
| `docs/archive/trazabilidad-hallazgos-0.7.md` | Histórico aislado (§ 2 de esta lista) |
| `docs/design-notes.md` | Por qué el **código 0.6.x** es como es, y lo medido. Citado desde 60+ líneas de fuente |
| `docs/{gates,workflow,installing,configuration,troubleshooting,when-the-harness-is-wrong}.md` | Manual de usuario de lo que el plugin hace **hoy** |
| `CHANGELOG.md` · `CONTRIBUTING.md` · `README.md` · `SECURITY.md` | Sin cambios |

`docs/implementation/0.7-progress.md` **no se crea todavía**: se abre cuando empiece la implementación,
y crearlo vacío ahora sería un artefacto sin consumidor.

## 4 · Fuente normativa

```
docs/design/appian-harness-0.7-1.0.md
```

**Una. No hay ninguna otra.**

## 5 · Cambios introducidos por esta auditoría

Solo deltas reales. **Ninguno añade una pieza arquitectónica**; tres retiran una.

| # | Cambio | Secciones |
|---|---|---|
| 1 | El umbral de ≥ 200 líneas se retira **también** como disparador de `design` y como forzador de tamaño | § 5.2, § 5.6 |
| 2 | El rediseño completo de una interfaz es **`micro` con revisor**, con `design` opcional y registrado | § 17.2 |
| 3 | La extensión de grant es **una por alcance** en los cuatro sitios que decían «por ciclo» | § 6.4, § 16 (Fases 2 y 4) |
| 4 | La tabla de la Fase 3 se reunifica; queda **un** «Hecha cuando», el vigente | § 16 |
| 5 | El umbral por objeto certificado dice **2 M** en todas partes | § 17.5 |
| 6 | Los apéndices A y B salen a `docs/archive/`; § 0 deja de indexarlos | § 0 |
| 7 | Se añade **§ 21 · DESIGN FREEZE** | § 21 |
| 8 | `decision-log.md`: cabecera de no normatividad, rutas muertas corregidas, 5 decisiones derogadas marcadas en su sitio | D-03, D-12, D-23, D-24, D-26, D-28 |
| 9 | El encargo sale del directorio de diseño | `docs/audit/` |

## 6 · Findings finales

```
BLOCKER:  0 abiertos  (2 encontrados, 2 resueltos)
HIGH:     0 abiertos  (1 encontrado, 1 resuelto)
MEDIUM:   0 abiertos  (2 encontrados, 2 resueltos)
LOW:      0 abiertos  (1 encontrado, 1 resuelto)
```

## 7 · Componentes finales

Responsabilidad, garantía diferencial y motivo: **la tabla completa de la Fase 5**. Resumen de cardinales:

- **7 subcomandos de hook** sobre 6 eventos — *enforcement*
- **5 skills** — *workflow*
- **1 agente** (`appian-auditor`), 3 invocaciones independientes — *juicio*
- **1 comando** (`/appian-init`) — *adopción y verdad sobre la instalación*
- **5 scripts** — *comprobación determinista*

## 8 · Flujo final

| | Visual trivial | Funcional pequeño | Estructural | Aplicación / feature |
|---|---|---|---|---|
| **Tamaño** | `micro` | `micro` | `task` | `task` con `tasks{}` |
| **Carril** | sin revisor si `behavioural: false`; con revisor si toca expresión (0.7) | **con revisor** | — | — |
| **Prompts que ve la persona** | **1** | **1** | **1** | **1 por alcance** |
| **Jueces** | 0 · 1 en 0.7 | **1** (`certify`) | 2 (`design`+`certify`) · 3 si `high` | design + certify **por funcionalidad**, en paralelo |
| **Artefactos** | 1 · 7 | 7 | 8 | 8 por tarea |
| **Tokens** | ≤ 3 M · ≤ 8 M | ≤ 8 M | ≤ 20 M/objeto · techo `min(80 M, 20 M × objetos)` | ídem |
| **Comprobaciones repetidas** | **0** | **0** | **0** | **0** |

**Un cambio trivial no activa un SDLC completo.** La advertencia honesta de 0.7 se mantiene: mientras el
escáner de literales no exista, cambiar un label *es* tocar la expresión y paga un revisor — y ese
revisor cuesta hoy 1-2 M en vez de 9,2 M, y **ninguna de las tres vías por las que ese caso escalaba de
tamaño sigue en pie**.

## 9 · Trabajo aplazado

**0.8** — escáner de literales · matcher de `Bash` por rutas · receta de paralelismo y `leaseFile` ·
caducidad por fila de la matriz · mitad instaladora de `/appian-init` · regla anti-salami, solo si la
magnitud lo pide.

**1.0** — actualización de la documentación del proyecto al cerrar, y diagramas opt-in.

## 10 · Veredicto

# ✅ READY FOR IMPLEMENTATION

**DESIGN FREEZE realizado** — § 21 del documento normativo, 1-sep-2026, **0 bloqueantes abiertos**.

Lo que queda antes de escribir código **no es diseño**: son las **cinco sondas de la Fase 0** más la
comprobación de esquemas, que exigen entorno vivo y tienen salida escrita en los dos sentidos. Ninguna
es una decisión pendiente.

**Esta es la última auditoría general del diseño. No se genera otra propuesta ni otra ronda.**
