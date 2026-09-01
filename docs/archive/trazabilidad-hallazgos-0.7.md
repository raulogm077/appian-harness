# Trazabilidad de hallazgos · appian-harness 0.7 (HISTÓRICO)

> ## ⛔ Esto NO es norma
>
> **Este documento no decide nada.** Es el registro de qué se decidió sobre cada defecto durante las
> revisiones que produjeron el diseño de la 0.7. La norma vigente —la única— es
> **`docs/design/appian-harness-0.7-1.0.md`**. Si algo de aquí contradice a ese fichero, **aquí está
> mal, por definición**: esto es una foto de una decisión pasada, no la decisión vigente.
>
> Se conserva por una razón concreta y no por «si acaso»: permite comprobar **qué** se decidió sobre
> cada uno de los 63 hallazgos sin reabrir ninguno.

**Origen.** Apéndices A y B del plan de la 0.7, extraídos el 1-sep-2026 por la auditoría de
consolidación. Vivían dentro del documento normativo, y **ahí eran la causa de cuatro
contradicciones**: registraban decisiones de la *primera* pasada como si siguieran vigentes, sin decir
que la segunda las había revertido. Fuera del documento no pueden volver a hacerlo.

---

## Filas que quedaron superadas, y por qué

Se listan aquí **en vez de** editarlas abajo: un archivo histórico que se reescribe deja de ser
histórico. Al leer las tablas siguientes, estas cuatro filas se leen con esta corrección delante.

| Fila de abajo | Lo que decía | Lo que quedó vigente | Quién la revirtió |
|---|---|---|---|
| **A.3 · F030** | «Un solo umbral, absoluto: ≥ 200 líneas sustituidas» | **Ningún umbral de magnitud.** Ni de líneas, ni de dependientes, ni porcentual, ni temporal | A.4 #1 (segunda pasada) — la herramienta sustituye la expresión entera, luego «sustituidas» siempre son todas |
| **A.3 · F039** | «Una extensión de grant **por ciclo**, no una por alcance» | **Una extensión por alcance.** La obligación cae en el preflight: analizar antes para que el prompt único baste | A.4 #5 (segunda pasada), y la decisión cerrada del dueño |
| **A.1 · F036** | «≤ 1,5 M por objeto certificado» | **≤ 2 M por objeto certificado** | A.4 #9 — 1,5 M suspendía la puerta contra la estimación de 1-2 M del propio § 9.2 |
| **B.6** | «Rediseño completo ⇒ `task` por el umbral de 200 líneas» | **`micro` con revisor**, con `design` opcional y registrado | Auditoría de consolidación del 1-sep-2026 (§ 17.2 de la norma) |

**Y el apéndice B entero está superado** por `docs/audit/final-consolidation-audit.md`: era la
autovalidación de la ronda anterior, y encontró nueve contradicciones cerradas sin ver las cuatro de
arriba, que seguían abiertas dentro de él.

---

## Apéndice A · Finding → decisión → sección

Trazabilidad de las **dos pasadas de revisión** a las que se sometió el diseño — 42 hallazgos en la
primera y 21 en la segunda, **63 en total, todos resueltos en el cuerpo**. Los BLOQUEANTES y los de
prioridad ALTA van con su decisión completa; el resto, en las tablas resumen. Ningún hallazgo queda
sin fila.

Los documentos de trabajo de ambas pasadas se retiraron al consolidar: lo que sobrevivió de ellos es
el cuerpo de este documento y el `decision-log.md` de al lado. Este apéndice existe para que se pueda
comprobar **qué** se decidió sobre cada defecto, no para reabrirlo.

### A.1 · Los ocho BLOQUEANTES

| # | Hallazgo | **Decisión tomada** | Sección |
|---|---|---|---|
| **F003** | La capa oficial impone prompts humanos que el plan no contabiliza: `confirmation-patterns.md` tiene **cinco** workflows, no uno, y el W2 dispara en **toda creación** | **Repartir los cinco por dueño único y cambiar la magnitud de la puerta.** W1 y W2 → el grant (el listado de objetos existentes lo hace el preflight; las colisiones entran en `grant.collisions[]` y en el prompt). W3 → el preflight. W4 → `appian-specify`. W5 → **desactivado** en alcance gobernado. La puerta mide **«prompts que ve la persona»**, sin distinguir origen | **§ 6.2**, § 6.4, § 17.1, § 17.4 |
| **F010** | `suspended` no tiene dónde vivir: es incompatible con el modelo de fichero único | **Embebido, con tope de uno.** `suspendedScope` dentro de `current.json` + `resumeFrom`. La invariante «un solo fichero» se conserva literalmente, el escritor sigue siendo único, y la disjunción se comprueba leyendo el mismo fichero. Los dos campos entran en el esquema | **§ 4.5**, § 4.1 |
| **F011** | `suspended` y `abandoned` no tienen escritor ni firma: son la salida barata del cierre, y `suspended` conserva un grant vivo para siempre | **Un solo escritor de estado, para los siete.** El agente escribe `request`; el hook escribe y **firma** con `statusWriteSeq`; **todo estado sin firma válida se revierte** al último firmado. Y `suspended` **caduca**: a la tercera sesión, `session-start` lo ofrece cerrar o abandonar y **declara su grant muerto** | **§ 4.3**, § 4.5 |
| **F013** | Todo el cierre depende de `PostToolBatch`, un evento que este plugin **nunca ha ejecutado**, y la Fase 0 no lo sondea | **Cuarta sonda en la Fase 0, con fallback declarado.** La sonda comprueba que dispara, que trae `tool_calls[]` con `tool_use_id` y `tool_result`, **y si dispara con lotes de una sola llamada**. Si no: las lecturas se acreditan por `PostToolUse` con la caché de la Fase 1 ya aplicada, y el gate de skill se degrada a aviso | **§ 16 Fase 0**, § 7.4, § 7.5 |
| **F019** | *(caso obligatorio)* El fallo del instrumento escala `micro`→`task`; escalar no compra ninguna medida nueva, y la escalada es **incerrable** porque ocurre tras escribir | **Una sola semántica: un fallo del instrumento no cambia nunca el `kind`.** Corroborar el fallo · **distinguirlo de una regresión del propio cambio** (paso 1-bis) · buscar evidencia alternativa de la misma clase (otra superficie, otro instrumento, un caso creado) · si la hay, cierra `closed` sin cambiar de tamaño; si no, `closed-pending-human` **siendo `micro`**. La escalada se reserva para cuando el trabajo **toca más superficie** | **§ 8.7**, § 17.2 |
| **F029** | «Alcanzable desde un Site publicado» fuerza `task`, luego **ninguna interfaz es nunca `micro`** | **Retirada como forzador de tamaño; modula el carril.** Un objeto publicado nunca va por el carril sin revisor cuando el cambio puede alterar lo que se ve — al precio de **una invocación de `certify`**, no de subir de tamaño. **Acotación:** una escritura `behavioural: false` conserva su suelo proporcionado aunque el objeto esté publicado | **§ 5.5**, § 5.2, § 8.6 |
| **F036** | La puerta de tokens es aritméticamente insatisfacible: `micro ≤ 5 M` contra «veredicto ≤ 12 M (medido 9,2)» en la misma tabla | **Presupuesto por objeto, techo por alcance, y veredicto por tamaño de matriz.** `micro` sin revisor ≤ 3 M · `micro` con revisor ≤ 8 M · por objeto en `task` ≤ 20 M · techo por alcance ≤ 80 M · **≤ 1,5 M por objeto certificado**. Y el coste del veredicto baja de verdad, porque F020 quita dos puertas de siete y las celdas son proporcionadas | **§ 17.5**, § 9.2 |
| **F042** | El perímetro de los dos gates exige que el servidor MCP **se llame** `*appian*`. Con otro nombre los hooks corren, contestan y **no ven nada** | **El perímetro se declara, no se adivina.** `appianMcpToolPrefixes[]` —**lista**, porque cubre el servidor de diseño **y el de runtime**, que es el que gatea los arranques de proceso—, rellenada por `/appian-init` desde lo registrado; **sonda de perímetro** con frase literal; comprobación en cada `session-start`; regex anterior solo como respaldo | **§ 7.2**, § 14, § 17.1 |

### A.2 · Los trece de prioridad ALTA

| # | Hallazgo | **Decisión tomada** | Sección |
|---|---|---|---|
| **F002** | Cuatro taxonomías de proporcionalidad coexisten sin reconciliar | **Dos ejes y solo dos.** `kind` = cuánta ceremonia (hook, enforcement); `risk` = qué clase de daño, **observado por el hook**, con valores `null`/`high`. La taxonomía oficial se alinea por cortes; la de `appian-best-practices` se reescribe **en función de `kind`**. Desaparecen `risk: trivial` y `risk: standard` | **§ 5**, § 5.3, § 3.1 |
| **F004** | `D § 5.11` conserva la prosa de orden de dependencias que el propio plan ordena eliminar | **Cuatro reglas propias, el resto puntero.** El harness conserva solo lo que habla de **la unidad de alcance** —ola de grupos, volver a un record type cerrado, `updateSite` y los UUID de página, datos de prueba con su borrado en el mismo grant—; `change-planning.md` gana *in full* | **§ 5.7**, § 3.1 |
| **F005** | El suelo de process model es más pobre que la fuente oficial y arrastra **deuda perpetua** | **Las comprobaciones de grafo entran en N3**: alcanzabilidad desde Start, `targetNodeId` de cada XOR resolviendo a un nodo existente, ausencia de huérfanos — todo desde `listProcessModelNodes`, **sin arrancar nada**. El residuo queda acotado a lo que sí exige arrancar | **§ 8.3** |
| **F007** | La verificación de **referencias cruzadas** no tiene lugar en el suelo | **Fila transversal**, no por tipo, con las cuatro comprobaciones oficiales más los dos lados de toda relación. Obligatoria una vez por funcionalidad. Determinista: **no compra agente** | **§ 8.2** |
| **F012** | No existe tabla de transiciones legales, y un hook tiene que hacerla cumplir | **Tabla de doce transiciones**, cada una con disparador, escritor y condición. Explicita lo que había que inventar: `in-flight → closed` **no existe**; `abandoned` es terminal; `closed-with-debt` se reabre **con `instanceId` nuevo** | **§ 4.4** |
| **F014** | Tres de las ocho causas de `ask` son estado interno del harness | **Cinco causas, no ocho.** Alcance en `closing`, lease ajeno y «grant manipulado sin escrituras entre medias» pasan a `additionalContext` con remedio al **modelo**. Y la definición de «`ask` falso» de la puerta se amplía a **toda causa que no sea una decisión que la persona pueda tomar** | **§ 7.3**, § 17.1 |
| **F020** | La matriz hace al juez re-certificar lo que el suelo ya midió, y **sin poder medirlo** | **Tres naturalezas de celda.** Puertas 1 y 2 → **importadas**, citando `toolUseId` (el validador comprueba instancia y que no sea `green-signal-only`). Puertas 3 y 5 → juicio **sobre la evidencia**, citando la fila. Puertas 4, 6 y 7 → juicio pleno. **Excepción:** si el caso de prueba se creó en el mismo alcance, la puerta 2 vuelve a ser celda de juicio | **§ 9.2** |
| **F025** | La escalera de presupuesto es incoherente entre `task` y `feature`, y no hay techo por feature | **Resuelto con F036**: presupuesto por **objeto**, no por envoltorio, más techo por alcance. Agrupar deja de comprar presupuesto | **§ 17.5** |
| **F030** | El umbral del 30 % castiga a los objetos pequeños y contradice el eje de «lo barato es lo inocuo» | **Un solo umbral, absoluto: ≥ 200 líneas sustituidas.** Cae también *«sin línea base, `task`»*. Y se dice qué compra: **una fase `design`** | **§ 5.2**, § 5.6 |
| **F033** | `feature` no es un tercer nivel de ceremonia: es un `task` con partición | **Dos tamaños.** `task` con `tasks{}` **opcional**; el tope se evalúa por entrada. Desaparecen la etiqueta, el término del glosario, el riesgo que el plan registraba y sus tres mitigaciones. **Ninguna fila de la tabla cambia** | **§ 5.1**, § 15 |
| **F034** | Las siete puertas bloquean igual: un FAIL de mantenibilidad bloquea como una referencia inválida | **Tres clases con efecto distinto**: CARDINAL bloquea · RECOMENDADA bloquea una vez · CONTEXTUAL (rendimiento, mantenibilidad) **no bloquea** y va a deuda con dueño. **Se adopta en 0.7**, y es una decisión de esta revisión: el veredicto la dejaba en «0.7 si es barato». Es barata, y es la que impide que el bucle de remediación se consuma en las dos puertas que menos lo merecen | **§ 9.3** |
| **F037** | El gate más invocado —**97 de 116 `ask`**— comprueba un formulario que escribe el propio agente al que constriñe | **Lo escribe el hook desde lo observado.** De «el agente dice que la cargó» a «el hook vio cómo la cargaba». **Rama honesta declarada:** si el canal de observación no da, el gate **se degrada a aviso** — no hay tercera opción | **§ 7.5**, § 16 Fase 0 |
| **F041** | Los seis tipos «manuales» no tienen planificación, ni suelo, ni residuo — y la doctrina del harness recomienda uno de ellos en cuatro sitios | **Tres piezas:** `appian-plan` los planifica **por puntero** a `How to Handle Manual Steps`; **una fila más en el suelo** con residuo `manual-step-not-tooled`; y **`Connected Systems` sale de la lista**, porque el Dev MCP sí lo cubre y la fuente oficial está desactualizada ahí | **§ 8.8**, § 8.1 |

### A.3 · Los veintiuno restantes

| # | Prioridad | Decisión | Sección |
|---|---|---|---|
| F001 | MEDIA | Sexta zona de solape reconocida y **cortes alineados**: `micro` ↔ single-object · `task` ↔ multi-object · `task` con `tasks{}` ↔ full application build | § 3.1 |
| F006 | BAJA | Las dos divergencias con la mecánica oficial (lectura post-borrado, `name` conductual) **se declaran con su motivo** | § 3.2 |
| F008 | MEDIA | `state-gate` pierde la validación de formularios que el propio harness produce y **se queda con la máquina de estados**; el registro lo escribe el hook | § 7.1, § 7.5 |
| F009 | BAJA | **`risk-downgrades.jsonl` eliminado**: con `risk` observado por el hook no hay rebaja que registrar | § 5.3, § 11.2 |
| F015 | BAJA | `manualEstimateMinutes` **entra en el esquema** (y detrás de `measure`), junto con `request`, `suspendedScope`, `resumeFrom` y `statusWriteSeq`. El barrido se hace sobre **este** esquema | § 4.1 |
| F016 | BAJA | **`leaseFile` sale de 0.7** y vuelve en 0.8 con la receta de paralelismo | § 15, § 18.1 |
| F017 | MEDIA | La prosa se corrige para prometer lo que el mecanismo entrega (frente + clase de cambio, **no** celda); la **caducidad por fila llega en 0.8** | § 7.6, § 18.1 |
| F018 | BAJA | **Clase de exigibilidad declarada por garantía** —impedible · detectable · auditable— en § 2 y en la puerta de desperdicio | § 2, § 17.4 |
| F021 | MEDIA | **Residuo simétrico**: todo tipo con suelo solo de persistencia **y efecto externo** arrastra `external-effect-not-exercised` con dueño. Los inocuos, no | § 8.4 |
| F022 | MEDIA | `validateDesignObject` se marca **`green-signal-only`** y **no cuenta por sí sola como cobertura**, ni para el closure gate ni para la puerta 1 | § 8.4, § 9.2 |
| F023 | BAJA | La segunda comprobación de hash se declara **corolario** de la tercera: dos garantías y un corolario, no tres garantías | § 8.5 |
| F024 | MEDIA | Un caso creado en el mismo alcance se registra como `case-created-in-scope` y **convierte la puerta 2 en celda de juicio** | § 8.1, § 9.2 |
| F026 | MEDIA | `context-floor.json` y `manualEstimateMinutes` pasan a **opt-in** (`measure: true`, apagado por defecto) | § 12.4, § 11.2 |
| F027 | MEDIA | El **tope de re-emisiones pasa a enforcement** en `validate_verdict.py`; las otras siete magnitudes se etiquetan **auditables** | § 9.4, § 17.4 |
| F028 | MEDIA | Recuento de artefactos **por tamaño**, en tabla: 1 · 6 · 7 · 8 | § 11.1 |
| F031 | MEDIA | **Umbral «≥ 3 dependientes» eliminado.** El conteo se conserva donde sirve: el prompt del grant y el alcance del comando de regresión | § 5.2 |
| F032 | MEDIA | **Ventana temporal eliminada, sin regla sustitutiva** — el veredicto de la auditoría concluye que el lote homogéneo y «el segundo objeto compra `task`» ya lo cubren. La magnitud de salami **se reporta**, y si aparece, la regla se diseña en 0.8 con el dato delante | § 5.2, § 17.4, § 18.1 |
| F035 | MEDIA | **`build.md` eliminado.** El mecanismo de `micro` —una línea de `gate-decisions.jsonl` al cerrar— se extiende a `task` | § 11.1, § 11.2 |
| F038 | MEDIA | **`design` se exige por lo que el alcance hace**, no por su etiqueta; la omisión queda registrada | § 5.6 |
| F039 | BAJA | **Una extensión por ciclo**, no una por alcance: alinea los dos topes y evita que un hallazgo del segundo ciclo sea inaplicable por fontanería | § 6.3, § 9.4 |
| F040 | BAJA | El aviso de migración ofrece **el remedio que existe después de actualizar**; «ciérralo antes de actualizar» pasa al CHANGELOG | § 15 |

---

### A.4 · Los veintiuno de la segunda pasada

La segunda pasada revisó **este** documento —texto nuevo— con contexto limpio y sin haber participado
en su redacción. Sus tres bloqueantes tenían una raíz común: **el diseño razonaba sobre el
`tool_input` que le gustaría recibir, no sobre el que las herramientas mandan de verdad**. De ahí sale
la comprobación de esquemas de la Fase 0.

| # | Hallazgo | Decisión | Sección |
|---|---|---|---|
| 1 | **BLOQ** · El umbral de 200 líneas reabría el caso ácido: la herramienta sustituye la expresión entera, luego «sustituidas» siempre son todas | **Retirado.** Un rediseño masivo compra `design` por la vía de «crea un objeto o cambia estructura» | § 5.2 |
| 2 | **BLOQ** · Tres mecanismos leían una expresión que a menudo viaja como **ruta**, no como texto — y es la forma que el esquema recomienda para lo no trivial | El hook **abre el fichero local**; se declara que es lectura de disco, no llamada MCP | § 7.6 |
| 3 | **BLOQ** · El tope de re-emisiones comparaba contra ficheros que el propio diseño sobrescribe | **Veredictos versionados** (`.001`, `.002`, `.003`), con el nombre sin sufijo como copia del vigente | § 9.4, § 11.1 |
| 4 | El bloqueo del tercer Stop no tenía transición legal a la que llevar el alcance | **Fila 13** de la tabla: `in-flight → closed-with-debt`, deuda `never-closed` | § 4.4 |
| 5 | «Un prompt por alcance» y «una extensión por ciclo» no cabían a la vez, y ampliar el tope cambiaba una decisión del dueño sin declararlo | **Una extensión por alcance**, y la obligación cae en el preflight: analizar antes para que el prompt único baste | § 6.3, § 17.1 |
| 6 | El suelo aceptaba un caso de prueba **ejecutado**, no **en verde**: un test rojo compraba cobertura plena | «≥ 1 caso ejecutado **y en verde**»; un caso rojo es `FAIL` del suelo | § 8.1, § 8.4 |
| 7 | La migración no traía el perímetro — un proyecto ya adoptado heredaba el respaldo y quedaba sin gobierno, en silencio | `appianMcpToolPrefixes[]` obligatoria; sin ella, **`ask` en la primera escritura**. Clase declarada, asimétrica | § 15, § 7.2 |
| 8 | El techo de tokens era plano junto a un presupuesto por objeto: **partir** el trabajo compraba presupuesto 3:1 | Techo **función del contenido**: `min(80 M, 20 M × objetos)` | § 17.5 |
| 9 | «1-2 M por certify» contra un umbral de «≤ 1,5 M»: la propia estimación suspendía la puerta | Umbral a **2 M**, que cubre el extremo alto de la estimación | § 17.5 |
| 10 | La caducidad de `suspended` tenía dos comportamientos y el contador no tenía dónde vivir | Caducar **mata el grant y no cambia el estado**; `suspendedScope.sessionsSeen` entra en el esquema | § 4.5, § 4.4 |
| 11 | La regla del instrumento suponía que cada instrumento compra **una** clase de garantía | La búsqueda de alternativa se hace **por clase**, y el resultado se resuelve por clase | § 8.7 |
| 12 | La Fase 3 se declaraba hecha con un juez que entrega la Fase 4 | La Fase 3 cierra cuando el caso ácido **satisface su suelo**; el cierre con revisor es de la Fase 4 | § 16 |
| 13 | El lote homogéneo chocaba con «un objeto» y con `maxAllowedObjects` | La tabla lo dice: «uno, **o N del mismo tipo sin expresión propia**» | § 5.1, § 5.7 |
| 14 | Sobrevivía un reloj (24 h de frescura) en un documento que retira una regla **por depender de un reloj** | La frescura pasa a «misma sesión o re-consulta»; el principio se acota a tamaño y duración | § 6.1 |
| 15 | La mayor palanca de coste —la carga diferida de schemas MCP— era una suposición sin sonda | **Quinta sonda** en la Fase 0: si no baja el suelo, la fila de 120 K se recalcula antes de escribir código | § 16 |
| 16 | `observe-reads` enrutaba **dos** corpus y solo se declaraba uno | Los dos declarados —verificación MCP y rastro de la skill—, y el test de paridad cubre ambos | § 7.4 |
| 17 | Cuatro referencias cruzadas apuntaban a § 4.6 en vez de a § 4.5 | Corregidas | § 4.1, § 4.2, § 4.4 |
| 18 | La tabla del § 10.1 tenía dos cabeceras y no renderizaba | Corregida | § 10.1 |
| 19 | No había estado firmado al que revertir la primera vez | Sin ninguna transición firmada, **el alcance no existe** a efectos del gate | § 4.3 |
| 20 | Un tipo sin fila en el suelo no tenía estado terminal | Cierra `closed-with-debt` con la deuda `type-has-no-floor` | § 8.1, § 9.5 |
| 21 | **TOCTOU** sobre el fichero de expresión: el hook mide y Appian lee en instantes distintos | El hash se calcula en `PostToolUse`, sobre los bytes que la llamada consumió; `PreToolUse` no mide contenido | § 7.6 |

**Lo que la segunda pasada NO tocó**, y conviene que conste: la arquitectura de cuatro capas, el
reparto con la skill oficial, las ocho garantías y la decisión de dos tamaños. Los veintiuno son
defectos de borde, y catorce se resolvieron con una frase.

## Apéndice B · Validación de este documento

Siete comprobaciones, ejecutadas sobre el texto final. **Resultado de cada una, con la evidencia.**

### B.1 · ¿Hay contradicciones internas?

**No se conserva ninguna de las nueve que la auditoría identificó**, y las tres que este diseño podría
haber introducido están cerradas explícitamente.

| Contradicción | Estado |
|---|---|
| El instrumento escala el tamaño ↔ el caso ácido exige no escalar | **Cerrada.** Una sola semántica (§ 8.7); el umbral «interfaces que escapan por instrumento: 0» pasa a ser alcanzable por construcción |
| Site publicado ⇒ `task` ↔ el caso ácido es un `micro` sobre una pantalla publicada | **Cerrada.** La exposición modula el carril (§ 5.5) |
| 30 % de líneas ↔ «lo barato es el inocuo, no el pequeño» | **Cerrada.** Un solo umbral absoluto (§ 5.2) |
| Reloj de una hora ↔ «no hay límites de tiempo, y es una decisión» | **Cerrada.** Regla eliminada (§ 5.2) |
| Orden de dependencias propio ↔ *Which Source Wins* | **Cerrada.** Cuatro reglas propias, el resto puntero (§ 5.7) |
| `micro ≤ 5 M` ↔ «veredicto ≤ 12 M (medido 9,2)» | **Cerrada.** Presupuesto por objeto y por tamaño de matriz (§ 17.5) |
| «Cuatro momentos» ↔ los cinco workflows oficiales | **Cerrada.** Reparto por dueño y magnitud redefinida (§ 6.2, § 6.4) |
| Suelo de borrado ↔ *When to Skip Verification* | **Cerrada como divergencia declarada** (§ 3.2) |
| `closed-pending-human` usado y ausente del esquema | **Cerrada.** Está en el enum, en la tabla de transiciones y en el cierre (§ 4.2, § 4.4) |
| *(nueva, evitada)* Exposición ⇒ revisor ↔ suelo proporcionado del cambio no conductual | **Cerrada por acotación explícita** (§ 5.5, § 8.6), y la puerta de desperdicio la comprueba con el caso negativo de § 17.3 |
| *(nueva, evitada)* Residuo por tipo ⇒ `closed-pending-human` en toda integración y todo tipo manual | **Cerrada, y hecha cumplir.** Los ids se reparten en dos clases declaradas (§ 9.5 a/b), la transición 4 exige la clase «juicio pendiente» (§ 4.4), y **el validador rechaza** un veredicto que use un id de residuo como aplazamiento |
| *(nueva, evitada)* Recuento de artefactos discrepante entre dos documentos de la auditoría (3 vs 6/7) | **Cerrada** con el itemizado de § 11.1: 1 · 6 · 7 · 8 |

### B.2 · ¿Están definidos todos los estados que se usan?

**Sí, los siete**, y cada uno tiene: definición (§ 4.2), **escritor único** (§ 4.3), **firma** (§ 4.3),
**transiciones legales de entrada y de salida** (§ 4.4) y **efecto sobre «en vuelo»** (§ 4.2). Los dos
que antes no tenían escritor —`suspended` y `abandoned`— lo tienen; el que no tenía dónde vivir
—`suspended`— lo tiene (§ 4.5). Ningún estado aparece en el documento sin fila en § 4.2.

**Los estados terminales de residuo también están definidos** y no se confunden entre sí (§ 10.1).

### B.3 · ¿Toda responsabilidad tiene dueño, y uno solo?

Las **siete responsabilidades con más de un dueño** que la auditoría tabuló quedan con dueño único:

| Responsabilidad | Dueño único | Sección |
|---|---|---|
| Aclarar una petición ambigua | `appian-specify` | § 6.2 |
| Confirmar colisión de nombre al crear | **El grant** (insumo: el preflight) | § 6.2 |
| Resolver un UUID no verificado | **El preflight** | § 6.2 |
| Proponer trabajo derivado | **Nadie** — desactivado en alcance gobernado | § 6.2 |
| Orden de dependencias | **La skill oficial**, salvo las cuatro reglas de unidad de alcance | § 5.7, § 3.1 |
| Graduar por tamaño de cambio | **`kind`** (ceremonia) y **`risk`** (clase de daño). Dos ejes, no cuatro | § 5 |
| Escribir `status` | **El hook**, los siete, firmados. La skill solo **solicita** vía `request` | § 4.3 |

Y cada componente de § 13 declara **una** responsabilidad principal. El único que tenía dos
—`log-evidence-write`— la pierde y se renombra a `state-gate` (§ 7.1).

### B.4 · ¿Queda algún componente sin valor diferencial frente al baseline?

**No.** Cada componente que sobrevive tiene su garantía nombrada en § 2, § 13 o § 8, y los que no la
tenían están eliminados con su justificación en § 11.2 y en la lista final. La prueba se aplica en los
dos sentidos: lo que se conserva responde *«¿qué se pierde si esto no existe?»* con algo concreto, y lo
que se elimina responde **«nada»**.

Los tres casos frontera, dichos sin adornos: `validateDesignObject` se conserva porque es barata y
detecta el fallo grosero, **pero marcada como señal que no cuenta** (§ 8.4); la segunda comprobación de
hash se conserva como **aserción de sanidad de coste nulo**, declarada corolario (§ 8.5); y
`appian-best-practices` no se adelgaza del todo porque es **el único material utilizable sin MCP**
(§ 3.3).

### B.5 · ¿Es realmente ligero el flujo visual trivial?

**Sí, medido en lo que cuesta, y con una advertencia honesta sobre 0.7.**

| Magnitud | Cambio visual trivial |
|---|---|
| Prompts que ve la persona | **1** |
| Jueces | **0** si la escritura es `behavioural: false` — también sobre una pantalla publicada |
| Jueces si toca expresión, en 0.7 | **1**, y ese `certify` es de **3-5 celdas de juicio sobre un objeto**, no las 53 de un `task` |
| Artefactos | **1** en el caso no conductual · 7 con revisor |
| Tokens | ≤ 3 M · ≤ 8 M con revisor |
| Comprobaciones repetidas | **0** |
| Escalada de tamaño por estar publicado | **Ninguna** |
| Escalada de tamaño por fallo del instrumento | **Ninguna** |

**La advertencia, que forma parte de la respuesta:** mientras el escáner de literales no exista (0.8),
**cambiar un label es tocar la expresión y paga un revisor**. Eso está dicho aquí, está dicho en § 5.4,
y **se mide** en la puerta de salida como *proporción de `micro` que paga `certify`, por causa*. Lo que
hace que siga siendo proporcionado es que el revisor cuesta hoy 1-2 M en vez de 9,2 M, y que ninguna de
las tres vías por las que ese caso escalaba de tamaño sigue en pie.

### B.6 · ¿Tiene el caso `GDE_INT_Dashboard` una semántica coherente?

**Sí, y está escrita en una tabla** (§ 17.2) para que no haya que deducirla:

- **Cambio pequeño sobre esa pantalla** → `micro`, carril **con revisor** (la exposición compra
  revisor, no tamaño), y cierra `closed` por evidencia alternativa cuando el 500 de serialización
  aparece — **o `closed-pending-human` siendo `micro`** si no hay vía alternativa. Nunca escala.
- **Rediseño completo de sus 1.767 líneas** → `task` con `design` previo, por el umbral de 200 líneas.
  **Y es correcto**: son dos trabajos distintos sobre el mismo objeto.
- **Antes de admitir evidencia alternativa** se comprueba que el 500 **no sea una regresión del propio
  cambio** (§ 8.7, paso 1-bis). Sin ese paso, la regla que arregla el caso ácido abriría un agujero
  peor que el que cierra.
- **El caso está definido por propiedades, no por el nombre del objeto** (§ 17.2 y § 18.3): Gestión de
  Entrevistas es el banco de pruebas, nunca una dependencia del diseño.

### B.7 · ¿Están resueltos todos los BLOQUEANTES?

**Los ocho**, cada uno con sección que lo resuelve (§ A.1). Y los trece de prioridad ALTA también
(§ A.2). De los ocho, **cinco se resolvían escribiendo**, y están escritos aquí: F010, F011, F019,
F036 y —con F012— la tabla de transiciones. Los tres restantes exigen trabajo real y lo tienen
asignado: **F013** una sonda en la Fase 0 con fallback declarado, **F042** una clave de configuración y
dos sondas en la Fase 2 y en `/appian-init`, y **F003** el reparto de los cinco workflows entre
preflight, grant y `appian-specify`.

**Lo que queda vivo, y se declara:** dos hallazgos se aplazan **a propósito** a 0.8 —la caducidad por
fila (F017) y la regla anti-salami (F032)—, ambos con la prosa corregida para no prometer de más y con
su magnitud reportada en la puerta de salida. Ninguno es bloqueante y ninguno queda sin dueño.

