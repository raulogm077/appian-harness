# decision-log.md — qué cambia respecto al diseño anterior, y por qué

**Fecha:** 25-ago-2026, **revisado el 1-sep-2026** · **Origen:** las dos pasadas de revisión del
diseño (63 hallazgos, 11 bloqueantes) y la auditoría de consolidación del 1-sep ·
**Norma:** `docs/design/appian-harness-0.7-1.0.md`

> **Esto no es norma.** Guarda **por qué** algunas reglas son como son. Se consulta; no se cita como
> autoridad. Donde este registro y la norma discrepen, **manda la norma**.
>
> **Cinco decisiones de este registro fueron revertidas después de escribirse** —D-03, D-12, D-23,
> D-24 y D-26—. Están corregidas abajo **en su sitio**, con nota de qué las revirtió: un registro de
> decisiones que conserva la versión derogada sin decirlo es exactamente el defecto que esta serie ya
> pagó dos veces.

**Qué es este documento.** El plan revisado **afirma el diseño**: no narra cómo se llegó a él. Este
registro es el otro lado — **solo lo que cambia** respecto al diseño anterior, con quién lo motiva,
qué se rechazó y qué consecuencia tiene. Quien vaya a implementar lee el plan; quien quiera saber por
qué el plan dice lo que dice, lee esto.

**Lo que NO cambia, y conviene decirlo primero.** Las once decisiones cerradas el 25-ago siguen en
pie. La auditoría no abrió **decisiones**: abrió **defectos**. En particular siguen intactas: la serie
va **partida** (escáner de literales y gate de `Bash` en 0.8) · `Bash` se gatea **solo por rutas** y en
0.8 · la 0.7 se implementa **en paralelo a M5** · **no se escribe código hasta que el dueño lo diga** ·
el permiso por lote **es** el paso final del workflow oficial de borrado · las cuatro piezas de coste ·
el suelo proporcionado para escrituras no conductuales · la estimación manual write-once con anotación
· el sondeo de `ask`/`escalate` · el corpus oficial **por categoría demostrada**.

**Formato.** Cada decisión: qué se decide · qué sustituye · por qué · qué se rechazó · dónde vive.

---

## Índice

| # | Decisión | Clase | Hallazgos |
|---|---|---|---|
| D-01 | Dos tamaños, no tres: `feature` desaparece | **elimina** | F033, F025 |
| D-02 | `risk` se observa, no se declara, y solo tiene un valor útil | **elimina** | F002, F009 |
| D-03 | Los **cuatro** umbrales de tamaño se retiran | **elimina** | F030, F031, F032, +2ª pasada |
| D-04 | La exposición modula el carril, no el tamaño | **corrige** | F029 |
| D-05 | Un fallo del instrumento **nunca** cambia el tamaño | **corrige** | F019 |
| D-06 | Un solo escritor de estado, para los siete, con firma | **corrige** | F011, F012 |
| D-07 | `suspended` vive embebido, con tope de uno y caducidad | **completa** | F010, F011 |
| D-08 | Tabla de doce transiciones legales | **completa** | F012 |
| D-09 | El perímetro se declara en configuración, y cubre los **dos** servidores | **corrige** | F042 |
| D-10 | Cuarta sonda de Fase 0: `PostToolBatch`, con fallback declarado | **completa** | F013 |
| D-11 | El rastro de la skill oficial lo escribe el hook, o el gate se degrada | **corrige** | F008, F037 |
| D-12 | Presupuesto por objeto, techo por alcance, veredicto por tamaño de matriz | **corrige** | F036, F025 |
| D-13 | Los cinco workflows oficiales, repartidos por dueño único | **completa** | F003 |
| D-14 | Cinco causas de `ask`, no ocho | **elimina** | F014 |
| D-15 | Dos de las siete puertas del juez pasan a celdas importadas | **corrige** | F020, F022, F024 |
| D-16 | Las puertas se gradúan: cardinal · recomendada · contextual | **añade** | F034 |
| D-17 | El tope de re-emisiones pasa a enforcement | **corrige** | F027 |
| D-18 | Fila transversal de referencias cruzadas | **añade** | F007 |
| D-19 | Las comprobaciones de grafo del process model entran en el suelo | **añade** | F005 |
| D-20 | Los tipos sin herramienta de escritura entran en plan, suelo y deuda | **añade** | F041 |
| D-21 | Residuo simétrico, y tres clases de deuda que no se confunden | **corrige** | F021, F005 |
| D-22 | Cinco artefactos salen de 0.7 | **elimina** | F009, F016, F026, F028, F035 |
| D-23 | `design` se exige por lo que el alcance hace | **corrige** | F038 |
| D-24 | Una extensión de grant **por alcance** | **corrige** | F039, +2ª pasada |
| D-25 | Clase de exigibilidad declarada en toda garantía | **añade** | F018 |
| D-26 | El caso ácido se define por propiedades, no por el nombre del objeto | **corrige** | F041, R135/R136 |
| D-27 | `log-evidence-write` se renombra a `state-gate` y pierde media responsabilidad | **corrige** | F008 |
| D-28 | Este documento sustituye al trío como especificación | **corrige** | R143 |

---

## D-01 · Dos tamaños, no tres

**Se decide.** `kind` tiene **dos** valores: `micro` y `task`. `task` lleva `tasks{}` **opcional**:
ausente cuando es una tarea suelta, poblado cuando `appian-plan` la partió. El tope de
`maxAllowedObjects` se evalúa **por entrada de `tasks{}`**.

**Sustituye a.** `micro | task | feature`.

**Por qué.** Tres de las cuatro filas de la tabla que comparaba `task` con `feature` decían
literalmente *«igual»*: mismos jueces, misma ceremonia previa, mismo criterio de cierre. La única
diferencia real era que `feature` tenía un `tasks{}` con más de una entrada. Un tercer valor de enum
que no cambia ninguna ceremonia introducía: una decisión más que tomar y anunciar, un término más de
glosario, una fila más en cada tabla del diseño, de la documentación y de los tests, y **un riesgo que
el propio plan registraba** —«todo se declara `feature`, porque la ceremonia es fija por alcance y el
coste por objeto cae con el tamaño»— cuya mitigación eran tres mecanismos adicionales. Se pagaba
mitigación por un riesgo que solo existía porque la etiqueta existía.

**Qué se rechazó.** Conservar `feature` «por claridad de comunicación». No compensa: lo que se comunica
es *«un `task` partido en tareas»*, que es más corto y más cierto.

**Consecuencia colateral.** El presupuesto de tokens deja de tener dos precios para el mismo trabajo
(D-12), y un alcance 0.6 con `kind: "feature"` se lee como `task` con `tasks{}` sin que ninguna
ceremonia cambie.

**Vive en.** § 5.1 · § 15.

---

## D-02 · `risk` se observa, no se declara

**Se decide.** `risk` tiene dos valores, `null` y `"high"`, y **lo escribe el hook** desde lo observado
cuando el alcance toca **seguridad, datos o algo irreversible**. El agente no lo declara nunca.

**Sustituye a.** `risk: trivial | standard | high`, declarado en el fichero de alcance.

**Por qué.** El único uso real de `risk` en todo el diseño era `high` —fuerza `kind ≥ task` y añade la
fase `risk`—. Un enum de tres valores del que solo uno decide algo es un enum de un valor con dos
etiquetas. Y que lo declarase el agente lo convertía en una exención editable por quien constriñe, que
es el patrón que la propia doctrina del harness marca como red flag.

**Consecuencia.** `risk-downgrades.jsonl` **desaparece**: si el hook lo observa y nadie lo declara, no
hay rebaja que registrar. Eso cierra F009 sin escribir una línea sobre quién puede rebajar qué.

**Vive en.** § 5.3 · § 11.2.

---

## D-03 · Los cuatro umbrales de tamaño se retiran

**Se decide.** De los seis criterios que forzaban `task` **sobreviven solo los de tipo de objeto**.
Se retiran los cuatro umbrales de magnitud: **≥ 3 dependientes**, **≥ 30 % de las líneas** (y con él
*«sin línea base, `task`»*), **el segundo `create*` en menos de una hora** y —**revertido el
27-ago-2026 por la segunda pasada**, que es lo contrario de lo que esta decisión escribió—
**≥ 200 líneas sustituidas**.

**Por qué, uno a uno:**

- **≥ 3 dependientes** mide cuánto costaría una regresión, no cuánto riesgo introduce el cambio. Un
  literal en un objeto con 30 dependientes es inocuo; un `showWhen` en uno con 1 no lo es. No se citó
  ningún fallo observado que lo motivara, ni se justificó el 3 frente al 2 o al 5.
- **≥ 30 %** castiga a los objetos pequeños: en una expression rule de veinte líneas —el tamaño
  típico—, **seis líneas compraban `task`**, con su `design`, sus dos veredictos y su `build.md`. Es la
  definición operativa de «clasificar demasiado como `task`», sobre el tipo de objeto más numeroso de
  cualquier aplicación Appian. El umbral absoluto captura el caso real que motivó la regla —el rediseño
  de 1.767 líneas— sin ese daño.
- **El segundo `create*` en menos de una hora** es el **único** criterio de todo el diseño que depende
  de un reloj, en un documento que declara explícitamente no usar relojes; se evade **esperando**, que
  es enseñar a producir el desperdicio «tiempo parado»; y castiga trabajo legítimo (una carpeta y,
  veinte minutos después, un documento dentro).

**Qué se rechazó, y es una decisión de esta revisión.** `findings.md § F032` proponía **sustituir** la
ventana temporal por un criterio de referencia entre objetos («dos `micro` consecutivos cuyos objetos
se referencian son un solo trabajo»). **No se adopta.** El veredicto de la auditoría
(`final-review § H`) concluye que no se pierde ninguna garantía, porque *«el lote homogéneo y "el
segundo objeto compra `task`" ya lo cubren*». Añadir una regla nueva que exige cruzar
`gate-decisions.jsonl` con dependientes, para un fallo que **no se ha observado**, contradice la regla
de no crecer sin garantía nombrable. **En su lugar**, la magnitud se **reporta** en la puerta de
desperdicio: si el salami aparece, la regla se diseña en 0.8 con el dato delante.

**Por qué cayó también el de 200 líneas, que esta decisión había salvado.** Porque medía una proxy y
no lo que decía medir, igual que los otros tres. `updateInterface` y `updateExpressionRule`
**sustituyen la expresión entera** —no existe envío parcial—, así que «líneas sustituidas» solo puede
significar «líneas enviadas»: el umbral **dispara en toda interfaz grande**, y con él el caso ácido
—un cambio pequeño sobre la peor pantalla del proyecto— vuelve a ser imposible. Es el defecto que la
0.7 existe para arreglar, reintroducido por el eje de magnitud.

**Qué compra ahora un rediseño masivo.** Un `design` **opcional y registrado** (§ 5.6): el constructor
puede pedirlo, y su omisión queda en `gate-decisions.jsonl`. La pregunta *«¿es buena solución?»* se
conserva; lo que se retira es obligarla mediante una medida que siempre dispara.

**Vive en.** § 5.2 · § 5.6 · § 17.2 · § 17.4 · § 18.1.

---

## D-04 · La exposición modula el carril, no el tamaño

**Se decide.** «Alcanzable desde un Site publicado» **deja de forzar `kind ≥ task`**. Pasa a decidir
**carril**: un objeto publicado nunca va por el carril sin revisor cuando el cambio puede alterar lo
que se ve.

**Por qué.** La intuición era correcta —una pantalla que ve gente no es un arreglo privado— y la
variable elegida, equivocada: mide **dónde vive el objeto**, no **qué hace el cambio**. En una
aplicación real, casi toda interfaz útil es alcanzable desde un site, así que aplicada literalmente
**ninguna interfaz sería nunca `micro`** — y retiraba el carril rápido justo de la clase de objeto
donde se midieron las 4 h 19 min. Conservar la intuición cuesta **una invocación de `certify`**, que es
un orden de magnitud menos que subir de tamaño.

**Acotación que se añade, y sin la cual se reintroduce la contradicción por otra puerta.** La regla
aplica a escrituras `behavioural: true`, a las inclasificables y —desde 0.8— a las de presentación
renderizada. **Una escritura `behavioural: false` conserva su suelo proporcionado aunque el objeto esté
publicado**: `description` y `documentation` no pueden alterar la pantalla, y exigir renders ahí sería
comprobar de una forma que nunca puede fallar. Sin esta acotación, el caso negativo de la puerta de
desperdicio —un cambio solo de descripción que no debe reabrir nada— fallaría sobre cualquier pantalla
publicada.

**Vive en.** § 5.5 · § 8.6 · § 17.3.

---

## D-05 · Un fallo del instrumento nunca cambia el tamaño

**Se decide.** La regla única de § 8.7: corroborar el fallo · **distinguirlo de una regresión del
propio cambio** · buscar evidencia alternativa de la misma clase (otra superficie del mismo
instrumento → otro instrumento → un caso creado en el alcance) · si la hay, cierra `closed` **sin
cambiar de tamaño**; si no, `closed-pending-human` **siendo `micro`**.

**Sustituye a.** *«En esos casos el micro escala a `task`»*.

**Por qué.** Tres razones, y las tres son suficientes por separado:

1. **Contradecía al caso obligatorio.** El mismo documento exigía que el caso ácido cerrase «como
   `micro`, sin escalar», sobre el objeto que dispara el fallo.
2. **La escalada era incerrable.** El 500 se descubre **al verificar**, es decir **después de
   escribir**; `task` exige su `design` **antes** de la primera escritura. Un `micro` escalado no podía
   satisfacer la puerta de `task` por construcción, y sus dos únicas salidas eran `closed-with-debt` o
   dar vueltas: el bloqueo estructural que esta serie viene a eliminar, reintroducido por la válvula
   creada para evitarlo.
3. **Escalar no compraba ninguna medida nueva.** Lo que `task` añadía era `design` y `certify`, y
   **ninguno puede medir lo que `testInterface` no midió**: el auditor no tiene acceso MCP, así que no
   renderiza; y el `design` es anterior a la escritura.

**El motivo real por el que el diseño escalaba** estaba dicho en el propio texto: porque `micro` no
tenía canal de residuo. Eso es un defecto de `micro`, no un argumento para escalar — y el canal ya
existía: el closure gate escribe `closed-pending-human` **sin distinguir tamaño**.

**El paso que evita abrir un agujero peor.** Un 500 de serialización puede no ser un límite del entorno
sino **una regresión que el propio cambio acaba de introducir**. El diseño cubría media defensa
—«no admisible si el mismo objeto midió limpio antes»—, que **no caza el caso del caso ácido**: una
pantalla que ya llevaba gráficos y nunca midió limpio. El paso 1-bis completa la defensa con dos vías
más —reproducir el fallo **sin** el cambio, u observarlo en otro objeto de la misma familia— y, si no
puede distinguirse, **cierra `closed-pending-human`, nunca `closed`**.

**El dato que hace la regla operativa aquí.** El 500 de serialización es del **servlet**; la superficie
REST responde bien a la ejecución de casos. La evidencia alternativa del paso 2(a) **existe y está
documentada en este entorno**, así que el caso ácido pasa a ser satisfacible sin excepción ad-hoc.

**Vive en.** § 8.7 · § 17.2.

---

## D-06 · Un solo escritor de estado, para los siete, con firma

**Se decide.** El agente **nunca** escribe `status`. Escribe `request` (`close · suspend · abandon ·
resume`) y el hook escribe el estado, **firmado con `statusWriteSeq`**. **Todo `status` sin firma
válida se revierte al último firmado**, con remedio al modelo.

**Sustituye a.** «Las skills escriben `closing`; el hook escribe `closed`, `closed-pending-human` y
`closed-with-debt`; `suspended` y `abandoned` no tienen escritor declarado».

**Por qué.** La garantía nuclear —*«`closed` solo lo escribe el hook, validando el suelo»*— tenía una
**puerta lateral de un campo**: escribir `"status": "suspended"` y parar. El closure gate lo aprobaba,
no había evidencia que producir, no había deuda que registrar y el alcance dejaba de anunciarse. Era
**estrictamente más barato que `abandoned`**, que al menos exige motivo. Generalizar la firma que
`closed` ya tenía a los siete estados cierra esa puerta y, de paso, deja **un solo escritor** para toda
la máquina de estados.

**Qué se rechazó.** Dejar que la skill siguiera escribiendo `closing` «porque ya funcionaba». Dos
escritores sobre el mismo campo es exactamente lo que produce el hueco, y `request` cuesta lo mismo de
implementar.

**Clase de la garantía, declarada.** **Detectable**, no impedible, mientras `Bash` no esté gateado
(0.8): un `printf` sobre el fichero no lo ve ningún evento, pero la firma hace que el estado se
revierta en la siguiente comprobación.

**Vive en.** § 4.3 · § 4.4.

---

## D-07 · `suspended` vive embebido, con tope de uno y con caducidad

**Se decide.** El alcance suspendido va **íntegro** en `suspendedScope` dentro de `current.json`, con
`resumeFrom` apuntando a su `id`, **tope de uno**, objetos disjuntos comprobados por el hook, y
**caducidad por sesiones**: a la tercera sesión en que `session-start` lo encuentra, lo ofrece cerrar o
abandonar y **declara su grant muerto**.

**Sustituye a.** Un estado descrito en prosa y sin lugar de almacenamiento: con un solo fichero de
alcance activo, los dos alcances no cabían.

**Por qué esta opción y no la otra.** La auditoría ofrecía dos: mover el alcance a
`tasks/suspended/<id>.json`, o embeberlo con tope de uno. Se elige **embeber** porque conserva
literalmente la invariante «un solo fichero», mantiene el escritor único, hace la comprobación de
disjunción una lectura del mismo fichero, y **basta para el caso que motiva el estado**: un hotfix.

**Por qué caduca.** El «ok» del grant *caduca al cerrar*, y un alcance suspendido conservaba
`instanceId` y `grant` **indefinidamente**: una autorización humana cuya condición de muerte era un
cierre que no llegaba. Un permiso vivo sin condición de muerte no es un permiso acotado. La cuenta es
de **sesiones**, no de reloj, para no reintroducir el criterio que D-03 retira.

**Por qué no se elimina el estado.** Porque su justificación es la más fuerte del diseño: sin esta
salida, un bug de dos minutos cuesta cerrar o abandonar una funcionalidad entera, y la consecuencia
real es que **se opera por fuera del harness** — se pierde el registro precisamente del cambio que más
importa auditar.

**Vive en.** § 4.5 · § 4.1.

---

## D-08 · Tabla de doce transiciones legales

**Se decide.** Existe la tabla, con **disparador, escritor y condición** por transición.

**Sustituye a.** Un encargo —«validar transiciones ilegales»— sin la lista de transiciones legales.
Sin ella, «transición ilegal» no significaba nada y el hook no podía rechazar ninguna.

**Lo que la tabla decide y antes había que inventar.** `in-flight → closed` directo **no existe** (todo
cierre pasa por `closing`, que es donde se valida) · `closing → in-flight` es legal solo por el ciclo
de remediación y **no invalida veredictos vivos** · `abandoned` es **terminal** · `closed-with-debt` es
el único terminal reabrible, y reabrirlo exige **`instanceId` nuevo**, lo que impide heredar un
`design` PASS que además está exento de caducidad.

**Y una regla de trato.** Un `request` ilegal **no es un `ask`**: es coordinación interna, y el remedio
va al modelo por `additionalContext` (ver D-14).

**Vive en.** § 4.4.

---

## D-09 · El perímetro se declara, y cubre los dos servidores

**Se decide.** `.claude/appian-harness.json` gana **`appianMcpToolPrefixes[]`**, una **lista**.
`/appian-init` la rellena **desde lo que la sesión tiene registrado**; una **sonda de perímetro**
verifica con respuesta literal; `session-start` lo comprueba en cada sesión; el regex anterior queda
**solo como respaldo**.

**Sustituye a.** `^mcp__[A-Za-z0-9_-]*[Aa]ppian[A-Za-z0-9_-]*__` — es decir, a que el nombre que el
usuario le dio a su servidor MCP decidiera si el plugin gobierna algo.

**Por qué es el bloqueante más grave de los ocho.** (1) **Evapora las dos garantías nucleares a la vez
y sin síntoma**: no hay error, no hay aviso, no hay línea en ningún registro — todo se aprueba, y como
el hook contesta JSON, está vivo, así que es **indistinguible de una puerta que dejó de disparar**.
(2) **Cae justo sobre la condición de salida** «instalación limpia por un tercero»: esa persona
registra su MCP con el nombre que quiera. (3) **Ya ocurrió una vez en este repositorio**, en la 0.5.2,
y está documentado.

**Por qué es una lista y no una cadena.** Porque el perímetro cubre **dos** servidores: el de diseño
(escrituras de objetos) y el de **runtime**, que es el que gatea **arranques de proceso** e
invocaciones. Declarar solo el de diseño des-gatearía los irreversibles de runtime en silencio — el
mismo fallo con otra ropa.

**Vive en.** § 7.2 · § 14 · § 16 Fase 2 · § 17.1.

---

## D-10 · Cuarta sonda de Fase 0, con fallback declarado

**Se decide.** `PostToolBatch` entra en la Fase 0 como cuarta sonda: que **dispare**, que traiga
`tool_calls[]` con `tool_use_id` y `tool_result` por entrada, **y si dispara con lotes de una sola
llamada**. Fallback declarado: `PostToolUse` con la caché de intérprete de la Fase 1 ya aplicada.

**Sustituye a.** «Entra en la Fase 3, con `test_matcher_parity.py` asertando la asimetría entre
matchers» — que comprueba que dos listas de nombres son disjuntas, no que el evento dispare.

**Precisión sobre lo que se afirma.** No se afirma que el evento no exista ni que no dispare: la
documentación lo describe y se verificó en la fuente. Se afirma que **el diseño hace depender su
garantía nuclear de un evento que nunca ha ejecutado, y no lo puso en la fase que existe para eso**.
Sin `checks.jsonl` no hay cobertura por objeto, y sin cobertura ningún alcance cierra limpio: si el
evento no dispara como se espera, la Fase 3 entera queda sin base y el descubrimiento llega **después**
de las Fases 1 y 2.

**Por qué la pregunta del «lote de uno» importa.** Porque de ella depende también D-11: si
`PostToolBatch` no ve una lectura suelta, el registro de la skill necesita otro canal o el gate se
degrada.

**Vive en.** § 16 Fase 0 · § 7.4.

---

## D-11 · El rastro de la skill oficial lo escribe el hook

**Se decide.** `appian-skill-loaded.json` lo escribe el hook desde **lo observado**: la invocación de
la skill y las lecturas bajo su raíz. **Rama honesta declarada:** si el canal de observación no da para
esto, el gate **se degrada a aviso**.

**Sustituye a.** Un fichero escrito por el propio agente al que el gate constriñe, con tres campos
—nombre de la skill, nombre del MCP de documentación, `appianVersion`— que se pueden escribir sin haber
abierto un solo fichero de la skill.

**Por qué.** Es **el gate más caro que existe hoy**: *«registro de skill ausente o malformado»* causó
**97 de los 116 `ask`** medidos — el 84 % — para comprar la garantía de que un JSON tiene tres campos.
Máximo coste de fricción, mínimo contenido de garantía. La doctrina del propio harness nombra el patrón
—*«a skill, hook or gate whose exemption can be edited by whoever it constrains»*— y este es el caso
con el signo invertido: no es la exención lo que edita el constreñido, es la **prueba de cumplimiento**.

**Qué se rechazó.** Dejarlo como está «porque 0.7 ya convierte esos `ask` en avisos con remedio». Eso
arregla el síntoma y conserva la pregunta de arquitectura sin responder: si la forma de un fichero
interno solo la escribe el propio harness, **¿por qué es un fichero validable en vez de un registro que
el hook escribe?** El patrón ya existía en el diseño —los vínculos nombre↔UUID y `grant.extensions[]`
los escribe el hook—; solo no estaba aplicado aquí.

**No hay tercera opción.** O el hook lo observa, o el gate es un aviso. Un `ask` que cuesta 97
interrupciones no puede comprar una garantía que se satisface escribiendo tres campos.

**Vive en.** § 7.5 · § 16 Fase 0 y Fase 3.

---

## D-12 · Presupuesto por objeto, techo por alcance, veredicto por tamaño de matriz

**Se decide.**

| Magnitud | Umbral |
|---|---|
| Tokens por objeto — `micro` sin revisor | ≤ 3 M |
| Tokens por objeto — `micro` con revisor | ≤ 8 M |
| Tokens por objeto — dentro de `task` | ≤ 20 M |
| **Techo por alcance** | ≤ 80 M |
| Tokens por **objeto certificado** | ≤ **2 M** *(esta decisión fijó 1,5 M; la 2ª pasada lo subió — nota al pie)* |

**Sustituye a.** `micro ≤ 5 M · task ≤ 60 M · feature ≤ 25 M por tarea`, y «tokens por veredicto
≤ 12 M».

**Por qué era insatisfacible.** Un `micro` con revisor emite **un** veredicto, y la media medida por el
propio diseño era **9,2 M**: **1,8× el presupuesto total del alcance que lo contiene**, antes de contar
la construcción, el preflight, los renders y el cierre. Y no era un caso de esquina: sin el escáner,
**todo `micro` que toque una expresión paga `certify`**, y cambiar un label *es* tocar la expresión. La
0.7 no podía pasar su propia puerta en el carril que más le importa demostrar.

**Por qué por objeto y no por envoltorio.** Una `task` suelta y una tarea dentro de una feature hacían
exactamente el mismo trabajo con dos precios (60 M frente a 25 M): eso es un incentivo apuntando al
lado contrario del que el diseño quiere. Y **no había techo por feature**: 25 M × 5 tareas = 125 M sin
umbral que lo tope, cuando la sesión catastrófica que motiva todo el rediseño fueron 171,9 M.

**Por qué la aritmética cierra ahora.** Porque el coste del veredicto baja de verdad: D-15 quita dos de
las siete puertas, las celdas proporcionadas llevan un veredicto real de 49 KB a ~15 KB, y un `certify`
de un solo objeto cuesta **1-2 M** — la media de 9,2 M salía de veredictos de `task` con 53 celdas.

**Corregido el 27-ago-2026.** El umbral que esta decisión fijó —1,5 M— **contradecía a su propio
párrafo anterior**, que estima el `certify` de un objeto en 1-2 M: un umbral por debajo del extremo
alto de la propia estimación suspende la puerta por construcción. Queda en **2 M**.

**Vive en.** § 17.5 · § 9.2.

---

## D-13 · Los cinco workflows oficiales, repartidos por dueño único

**Se decide.** W1 (borrado) y **W2 (colisión de nombre)** → el grant, con el listado de objetos
existentes ejecutado por el **preflight** y las coincidencias en `grant.collisions[]`. W3 (UUID) → el
preflight. W4 (petición ambigua) → `appian-specify`. **W5 (trabajo derivado) → desactivado** en alcance
gobernado. Y la magnitud de la puerta pasa a **«prompts que ve la persona»**.

**Sustituye a.** «Los cuatro momentos en que una persona aparece, y son cuatro y no más», con la
magnitud definida como *«prompts **del harness** por alcance»*.

**Por qué.** `confirmation-patterns.md` no contiene un workflow de confirmación sino **cinco**. El
reparto anterior cerró el del **borrado** —6 casos sobre 120 escrituras medidas— y dejó abierto el de
**colisión de nombre**, que dispara en **toda creación**: la clase mayoritaria. El mismo razonamiento
—«los pasos oficiales son insumo; el prompt del harness es el paso final»— no estaba aplicado donde más
veces ocurre.

**Y por qué cambia la magnitud.** Porque *«prompts del harness»* **excluye por construcción** los
prompts que provoca la capa que el propio harness **obliga a cargar**. Medir el coste de ceremonia
excluyendo la ceremonia que uno mismo importa no es una medida: es una definición. Con la magnitud
antigua, la puerta podía salir verde con el usuario contestando tres preguntas.

**Por qué W5 se desactiva y no se reparte.** Porque proponer trabajo derivado es literalmente lo que
`allowedObjects` existe para impedir.

**Vive en.** § 6.2 · § 6.4 · § 17.1 · § 17.4.

---

## D-14 · Cinco causas de `ask`, no ocho

**Se decide.** Se retiran tres causas —alcance en `closing`/`closed`, lease de otro alcance, y «grant
manipulado» **cuando no ha habido escrituras del agente entre medias**— y pasan a `additionalContext`
con remedio al **modelo**. Y la definición de «`ask` falso» de la puerta se amplía a **toda causa que
no sea una decisión que la persona pueda tomar**.

**Por qué.** El propio diseño tenía la prueba escrita: *«un `ask` que no pueda escribirse con estos
cuatro campos es la señal de que el gate pregunta por un formulario: se arregla el gate, no el
mensaje»*. Las tres retiradas **no pasan el campo 3** —«el arreglo, ejecutable»—: la persona no tiene
ninguna orden que dar. Un alcance en `closing` es una carrera interna; un lease ajeno, en una release
sin paralelismo, es un residuo; y un `instanceId` que no casa **sin escrituras entre medias** es el
propio harness reescribiendo el fichero.

**Por qué la definición de «falso» tenía que ampliarse.** Porque estaba limitada a «formulario mal
cumplimentado o UUID de creación no vinculado», que es **más estrecha** que la regla del encargo, y
dejaría estos tres fuera del recuento: la puerta podría salir en verde con ellos presentes.

**Vive en.** § 7.3 · § 17.1.

---

## D-15 · Dos de las siete puertas pasan a celdas importadas

**Se decide.** Puertas 1 y 2 → **celda importada** (cita el `toolUseId` de la fila que la acredita; el
validador comprueba que existe, que es de esta instancia y que su clase no es `green-signal-only`).
Puertas 3 y 5 → **juicio sobre la evidencia**, citando la fila. Puertas 4, 6 y 7 → **juicio pleno**.
**Excepción:** si el caso de prueba se creó dentro del mismo alcance, la puerta 2 vuelve a ser celda de
juicio.

**Sustituye a.** Siete celdas de juicio por objeto, todas de la misma naturaleza.

**Por qué.** Dos hechos del propio diseño: las puertas 1 y 2 **ya las mide el suelo determinista** y las
acredita `checks.jsonl`; y el auditor **no tiene acceso MCP**, así que no puede validar un objeto, no
puede renderizar una pantalla, no puede ejecutar un caso y no puede leer una seguridad efectiva. Las
celdas 1 y 2 eran, necesariamente, **la transcripción de una medida que hizo otro**, en una cadena de
cuatro capas para una sola pregunta.

**Y lo peor no era el coste.** Una celda `PASS` en la puerta 1 firmada por alguien que no pudo medirla
**degrada el significado del veredicto entero** — el mismo defecto que el diseño cazaba en otro sitio
(*un veredicto sobre un árbol del que se leyó el 12,6 % es `NOT_MEASURED`, no `PASS`*), aplicado a la
puerta en vez de al árbol.

**La excepción cierra un hueco de autoría.** El suelo exige **≥ 1 caso ejecutado**, que es una condición
de conteo, y un caso que llama a la regla con nulos la satisface — **escrito por el mismo agente al que
ese caso le abre la puerta de cierre**. Es la única pierna del suelo cuya evidencia la fabrica el
interesado; todas las demás son lecturas del entorno. Llevar la pregunta *«¿este caso ejercita el
camino que el cambio tocó?»* a donde hay juicio cuesta **cero llamadas nuevas**.

**Se conserva íntegra la cobertura completa.** No se elimina ninguna comprobación: se cambia **quién la
firma**.

**Vive en.** § 9.2 · § 8.4.

---

## D-16 · Las puertas se gradúan: cardinal · recomendada · contextual

**Se decide.** CARDINAL (platform correctness, security, y las tres *never graded down*) **bloquea el
cierre**. RECOMENDADA (functional behavior, SAIL interfaces, operations) **bloquea una vez**; al segundo
Stop cierra como `closed-with-debt` con el hallazgo registrado. CONTEXTUAL (performance,
maintainability) **no bloquea**: va a `deferred-debt.jsonl` con dueño y aparece en `session-start`.

**Sustituye a.** Un solo efecto para las siete: *«FAIL blocks closure»*.

**Por qué.** Un FAIL de **mantenibilidad** —«esta lógica debería vivir en una expression rule»—
bloqueaba el cierre exactamente igual que una referencia inválida. Mantenibilidad y rendimiento son
juicios **contextuales** por naturaleza, y la propia doctrina lo reconoce (*measure before optimizing*,
*a reasonable local convention overrides the generic preference of these docs*). Que bloqueen convierte
una opinión de estilo en un `closed-with-debt`, y la salida disponible era la peor: **agotar tres
ciclos de remediación discutiendo con un juez** sobre si una regla debería estar partida en dos. El
encargo lo dice literalmente: el harness debe favorecer un buen desarrollo Appian, **no crear
burocracia alrededor de cualquier recomendación**.

**Decisión de esta revisión, y se marca como tal.** El veredicto de la auditoría dejaba esta
graduación en «0.7 si es barato, 0.8 si no». **Se adopta en 0.7**: es barata —una tabla en
`10-quality-gates.md`, el efecto en `validate_verdict.py` y en el closure gate— y es **la pieza que
impide que el bucle de remediación se consuma en las dos puertas que menos lo merecen**, que es
exactamente el riesgo de loops de validación que esta revisión tiene que cerrar.

**Vive en.** § 9.3 · § 16 Fase 4.

---

## D-17 · El tope de re-emisiones pasa a enforcement

**Se decide.** `validate_verdict.py` **rechaza** el tercer veredicto de una fase e instancia que no
aporte un `findings[].id` **ausente de todos los veredictos anteriores**, comparando ficheros y no por
declaración. Las otras siete magnitudes anti-desperdicio se etiquetan **auditables**.

**Por qué.** Las ocho magnitudes se medían a posteriori y **ninguna tenía mecanismo que la impidiera**.
Esta es la única impedible con lo que el diseño ya tiene —una comparación de conjuntos sobre ficheros
en disco— y merece serlo: **7 de 7 re-emisiones de la sesión medida se pidieron a mano**, y fue el
defecto más caro de esa sesión.

**Y por qué se etiquetan las demás.** Para que nadie lea «umbral 0» como «no puede pasar». La
honestidad aquí es barata, y el diseño ya la practica en otros sitios.

**Vive en.** § 9.4 · § 17.4.

---

## D-18 · Fila transversal de referencias cruzadas

**Se decide.** Una fila del suelo **no por tipo** que se activa cuando el alcance ha tocado dos objetos
que se referencian, con las cuatro comprobaciones oficiales —`processModelUuid` de una record action,
`startForm.interfaceUuid`, `interfaceExpression` de una summary view, `targetUuid` de cada página de
site— más **los dos lados** de toda relación. Obligatoria una vez por funcionalidad.

**Por qué.** Es exactamente la clase de defecto que un suelo **por tipo** no puede ver por
construcción: cada objeto pasa su fila y el conjunto está roto. Y es la que más aparece en el caso
donde el harness sitúa su mayor valor. Agrava además dos cosas que el propio diseño ya advertía:
`updateSite` **regenera los UUID de todas las páginas**, y el suelo de site era «relectura +
`listApplicationObjects`/`getSite` que enumera el contenido final» — **enumerar no comprueba que los
`targetUuid` resuelvan**.

**Coste.** Ninguno nuevo: son `get*` sobre UUIDs que ya están en `allowedObjects`, se acreditan como el
resto, y **no compran ningún agente**.

**Vive en.** § 8.2.

---

## D-19 · Las comprobaciones de grafo del process model entran en el suelo

**Se decide.** N3 incorpora, desde `listProcessModelNodes` y **sin arrancar nada**: alcanzabilidad de
todo nodo desde Start, `targetNodeId` de cada condición XOR resolviendo a un nodo existente, y ausencia
de huérfanos. El residuo se acota a lo que sí exige arrancar.

**Por qué.** El diseño declaraba que *«ningún otro instrumento evalúa gateways»* y por eso **todo**
cierre de process model arrastraba `instrument-limit-known`. Pero la fuente oficial especifica
**exactamente una comprobación de gateways que no exige arrancar un proceso**. Eso no prueba que la
condición sea *correcta*, pero sí que el gateway **no está roto** — que era la mitad del residuo.
Consecuencia práctica: cada `task` de process model nacía con deuda por una limitación **parcialmente
falsa**, y la deuda que se registra siempre es deuda que nadie lee.

**Y aplica aquí la regla que el propio diseño ya fijaba:** las señales del suelo se definen **por
referencia** a `change-review.md`. N3 era el contraejemplo de su propia regla.

**Vive en.** § 8.3.

---

## D-20 · Los tipos sin herramienta de escritura entran en plan, suelo y deuda

**Se decide.** `appian-plan` los planifica **por puntero** a `How to Handle Manual Steps`, en su
posición del grafo oficial; el suelo gana una fila —la lectura que sí exista, más el residuo
**`manual-step-not-tooled`** con dueño—; y **`Connected Systems` sale de la lista de manuales**, porque
el Dev MCP sí lo cubre.

**Por qué.** El grafo oficial marca varios tipos como `(manual)` y **manda incluirlos en el plan**. El
harness no los planificaba, no los verificaba y no los registraba — y su regla de defecto decía «un
tipo sin fila no cierra». Como no pasan por MCP, **ningún hook los ve**: no quedan bloqueados, quedan
**invisibles**, que es peor. En una funcionalidad real, el trabajo manual desaparecía de la evidencia,
del plan y de la deuda, y el `certify` certificaba el subconjunto que casualmente tenía herramienta.

**Y hay contradicción interna, que es lo que lo convierte en defecto y no en omisión:** la doctrina del
propio harness recomienda **Decision objects** en cuatro sitios. Un desarrollador que siga la doctrina
produce un objeto que el harness no sabe manejar.

**Lo que esto también corrige.** El eje de generalización: no hay dependencia de `GDE_*`, pero **sí la
había de que el proyecto usara solo los tipos que el MCP sabe escribir**. Gestión de Entrevistas los
usa; otra aplicación Appian, casi seguro que no.

**Vive en.** § 8.8 · § 8.1 · § 13.

---

## D-21 · Residuo simétrico, y tres clases de deuda que no se confunden

**Se decide.** Cada fila de `checks.jsonl` declara **`guaranteeClass`**. Todo tipo cuyo suelo sea solo
de persistencia **y que además escriba datos, llame a un sistema externo o cambie autorización**
arrastra residuo con dueño (`external-effect-not-exercised`). Y se separan **tres cosas** que antes
compartían etiqueta:

| | Efecto en el estado |
|---|---|
| **Residuo de clase de garantía** — el suelo del tipo compra menos de lo que su efecto merece | **Ninguno**: cierra `closed` |
| **Juicio pendiente** — el instrumento no midió y no hay vía alternativa, o hace falta juicio visual | **`closed-pending-human`** |
| **Deuda de hallazgo** — se agotaron los ciclos, o una puerta RECOMENDADA falló dos veces | **`closed-with-debt`** |

**Por qué el residuo simétrico.** La asimetría era llamativa: **process model**, que no toca nada fuera
de Appian, arrastraba deuda en **todo** cierre; **integración y connected system**, que son literalmente
la superficie contra sistemas de terceros, cerraban **limpios** con el suelo más débil de la tabla y
**sin residuo**. Un desarrollador concluía que su integración pasó las puertas; pasó **una**: que el
objeto persiste. La decisión de no invocar es correcta y se conserva —invocar una integración es una
escritura contra un tercero—; lo que faltaba era **sacar la consecuencia**.

**Por qué las tres clases.** Sin separarlas, aplicar D-19 y el residuo simétrico haría que **todo**
process model y **toda** integración cerrasen `closed-pending-human`, inflando justo la magnitud que la
puerta de salida usa para saber si el carril rápido existe. Un techo declarado por tipo **no es una
puerta que falló**.

**Consecuencia sobre `instrument-limit-known`:** deja de significar «este tipo tiene un techo
estructural» y significa **solo** «el instrumento que el suelo exige falló y no hay evidencia
alternativa». El cambio de semántica se declara porque cambia lo que el id significa en veredictos
antiguos.

**Y la consecuencia sobre la lista cerrada de `REQUIRES_HUMAN`, que es donde esto se hace cumplir.**
Los cinco ids **se reparten en dos clases declaradas**, porque llevan a estados distintos:

- **(a) Juicio pendiente** — `visual-judgement-on-rendered-screen`, `instrument-limit-known`. Son
  **entradas de veredicto** y **disparan** la transición a `closed-pending-human`.
- **(b) Residuo de clase de garantía** — `branch-not-exercisable-without-writing-data`,
  `manual-step-not-tooled`, `external-effect-not-exercised`. **No son entradas de veredicto**: son
  filas de `deferred-debt.jsonl` que escriben el hook y el suelo, y el alcance cierra **`closed`**.

Sin ese reparto, la transición «cualquier `REQUIRES_HUMAN` bien formado ⇒ `closed-pending-human`»
mandaría a ese estado **toda integración, todo tipo manual y todo user filter sin expresión** — es
decir, cegaría justo la magnitud que la puerta de salida usa para saber si el carril rápido existe. El
validador **rechaza** un veredicto que use un id de la clase (b) como aplazamiento.

**Vive en.** § 8.4 · § 9.5 · § 10.1 · § 4.4 (transición 4).

---

## D-22 · Cinco artefactos salen de 0.7

**Se decide.**

| Artefacto | Decisión | Garantía perdida |
|---|---|---|
| `context-floor.json` | **Opt-in** (`measure: true`, apagado por defecto) | Ninguna para el usuario |
| `manualEstimateMinutes` | **Opt-in**, con el mismo interruptor | Ninguna |
| `build.md` | **Eliminado**; el mecanismo de `micro` —una línea de `gate-decisions.jsonl`— se extiende a `task` | **Ninguna** |
| `risk-downgrades.jsonl` | **Eliminado** (ver D-02) | **Ninguna** |
| `leaseFile` en 0.7 | **Retirado**; vuelve en 0.8 con la receta de paralelismo | **Ninguna** hasta que exista paralelismo |

**Por qué, con el test aplicado.** *¿Quién lo consume? ¿Qué decisión permite tomar?*

- `context-floor.json` lo consume **una puerta de release**, y permite decidir si **la 0.7 se publica**.
  Ninguna de las dos cosas le importa a un equipo que instale el plugin en 2027: era un artefacto que
  todo alcance de todo usuario escribía **para siempre** para alimentar una medida que se toma **una
  vez**. `manualEstimateMinutes` es peor: además **pregunta**, y por una métrica que el propio diseño
  declara que *se reporta y no puntúa*.
- `build.md` **no tenía consumidor declarado**, y el único candidato plausible —el juez— lo tiene
  **prohibido por dos vías explícitas**: nunca recibe volcados ni la conclusión del constructor, que es
  exactamente lo que `build.md` es. Y el propio diseño demostraba que no hace falta: en `micro` ya lo
  sustituía una línea de log.
- `leaseFile` se conservaba **porque ya existía**, que es literalmente lo que el encargo de revisión
  prohíbe.

**Vive en.** § 11.2 · § 12.4 · § 18.1.

---

## D-23 · `design` se exige por lo que el alcance hace

**Se decide.** Obligatorio cuando el `task` **crea** un objeto, o cambia estructura de datos,
seguridad o un process model. **Opcional y registrado** cuando solo modifica objetos existentes sin
cambiar su contrato — y ahí cae también el rediseño masivo de una expresión, desde que cayó el umbral
de 200 líneas (D-03). Exento en solo-borrado.

**Por qué.** Era obligatorio en **todo** `task`, incluido el `task` **ad-hoc** de dos objetos: cambiar
el mismo filtro en dos interfaces —dos objetos, una intención, cero creaciones, cero estructura—
disparaba una fase `design` completa con su subagente, su contexto fresco y su artefacto. Es el salto
de coste más brusco de la escalera, y cae justo en la frontera entre el caso funcional pequeño y el
estructural. Y la pregunta que el `design` responde —*¿es buena solución?*— **no tiene contenido**
cuando no se está diseñando nada.

**Vive en.** § 5.6.

---

## D-24 · Una extensión de grant por alcance

**Se decide.** **Una extensión por alcance.** Con el mismo requisito: un hallazgo de juez que la
cite, `dependents.json` fresco, y escrita por el hook.

**Esta decisión se escribió al revés, y se revirtió el 27-ago-2026.** Decía *«el tope pasa de una por
alcance a una por ciclo de remediación»*, razonando que si el ciclo 1 gastaba la única extensión, un
hallazgo del ciclo 2 quedaba **inaplicable por fontanería**.

**Por qué se revirtió.** Porque «una por ciclo» con el tope de 3 ciclos permite **tres prompts de
extensión por alcance**, encima del prompt del grant — y eso cambia una decisión cerrada del dueño sin
declararlo: *«que se analice las cosas que hay que modificar y me pida permiso **una vez** indicándome
los objetos que va a tocar, para no tener que aceptar todos uno a uno»*. El problema que la decisión
veía es real, pero **su dueño es el preflight, no el tope**: un hallazgo que exige un objeto imprevisto
es la señal de que el análisis previo no fue bastante completo, y se corrige analizando mejor, no
comprando más permisos. Agotada la extensión, un hallazgo posterior **no reabre el alcance**: se
registra como deuda con dueño y se salda en un alcance nuevo.

**Vive en.** § 6.3 · § 6.4 · § 9.4 · § 17.1.

---

## D-25 · Clase de exigibilidad declarada en toda garantía

**Se decide.** Cada garantía declara si es **impedible** (un hook corta antes), **detectable** (ocurre,
queda registro y algo lo lee después) o **auditable** (queda registro y solo lo ve quien lo busca). En
la tabla de garantías y en la puerta de desperdicio.

**Por qué.** La distinción existía y estaba bien hecha en **dos** sitios; ninguna otra garantía decía a
qué clase pertenece. Es la distinción que decide **qué puede prometer el plugin a quien lo instala**:
hoy un lector no podía saber si «un juez nunca recibe la conclusión del constructor» es impedible
—**no lo es**: es una instrucción de despacho, y nada comprueba el prompt enviado—.

**Coste.** Cero líneas de código. Cambia lo que el plugin puede prometer honestamente.

**Vive en.** § 2 · § 17.4.

---

## D-26 · El caso ácido se define por propiedades, no por el nombre del objeto

**Se decide.** El caso ácido es *«un `micro` sobre la peor interfaz disponible del proyecto:
alcanzable desde un site publicado, servida solo por REST, con gráficos, y que arrastra el 500 de
serialización»*. `GDE_INT_Dashboard` es **la instancia disponible hoy**, no la definición. Y se añade
la tabla de semántica del objeto: cambio pequeño ⇒ `micro` con revisor, y **rediseño completo ⇒
`micro` con revisor** también, con `design` opcional y registrado. *(Esta decisión decía originalmente
«rediseño completo ⇒ `task` por el umbral de 200 líneas»; cayó con el umbral — D-03.)*

**Por qué.** Gestión de Entrevistas es **banco de pruebas, nunca dependencia**. La puerta exige que el
caso ácido se ejecute **también en un proyecto recién adoptado**; un caso definido por un nombre de
objeto no es reproducible allí. Y la tabla de semántica evita la ambigüedad que quedaba viva: el mismo
objeto admite dos trabajos de tamaño distinto, y el eje que los separa —cuánto se cambia— es
precisamente el que sobrevive a D-03.

**Se mantiene el test.** `grep -rn "GDE_"` sobre el código devuelve **cero**, y sigue siendo un test.

**Vive en.** § 17.2 · § 18.3.

---

## D-27 · `log-evidence-write` se renombra a `state-gate` y pierde media responsabilidad

**Se decide.** El subcomando conserva **una** responsabilidad: hacer cumplir la máquina de estados
—esquema, tabla de transiciones, escritura y firma del `status`, reversión de lo no firmado—. Pierde la
validación de formularios que el propio harness produce (que se va a D-11). Y `post-tool-batch` pasa a
`observe-reads`, cuya responsabilidad única es **acreditar lo observado**.

**Por qué.** El hook hacía dos cosas y **solo una era enforcement**. La regla del encargo es explícita:
*hook = enforcement, no workflow*, y hay que cuestionar «cualquier hook dedicado a corregir formularios
internos». Al quitarle la segunda, lo que queda es la máquina de estados, y el nombre debe decirlo: un
componente cuyo nombre no describe su única responsabilidad invita a que le añadan la siguiente.

**Vive en.** § 7.1.

---

## D-28 · El plan revisado sustituye al trío como especificación

**Se decide.** **`docs/design/appian-harness-0.7-1.0.md` es *la* especificación de la 0.7.** Los
documentos anteriores pasan a **histórico**: lo que conserva trazabilidad real vive aislado en
`docs/archive/` y **no se cita como norma**; el resto se eliminó.

*(Esta decisión nombraba `docs/harness-review/plan-0.7-1.0-revised.md`, ruta que dejó de existir al
consolidar. La auditoría del 1-sep la actualizó: una decisión que apunta a un fichero inexistente no
es trazabilidad, es una pista falsa.)*

**Por qué.** La precedencia anterior —«donde los tres discrepen, manda el plan de implementación»—
resolvía la contradicción **para quien leyera los tres**, no para quien leyera uno. Y la condición de
salida exige que **un tercero instale y opere sin leer ningún documento de diseño**: tres documentos
que se corrigen entre sí son, para esa persona, tres oportunidades de leer la versión equivocada.

**Y una regla de estilo que se hereda del anterior y se conserva.** El plan **afirma el diseño** y no
narra rondas ni errores previos. El relato del cambio vive **aquí** y en el apéndice A, que es donde
alguien lo busca a propósito.

**Vive en.** Cabecera de la norma · `docs/archive/trazabilidad-hallazgos-0.7.md`.

---

## Propuestas de la auditoría que **no** se adoptan

Tres, y las tres con motivo. Se registran para que nadie las dé por olvidadas.

| Propuesta | Origen | Por qué no |
|---|---|---|
| **Sustituir la ventana temporal por «dos `micro` consecutivos cuyos objetos se referencian»** | `findings.md § F032` | El veredicto de la auditoría (`final-review § H`) concluye que **no se pierde ninguna garantía** al eliminarla, porque el lote homogéneo y «el segundo objeto compra `task`» ya lo cubren. Añadir una regla nueva, que exige cruzar registros y consultar dependientes, para un fallo **no observado**, contradice la regla de no crecer sin garantía nombrable. **En su lugar se reporta la magnitud** (§ 17.4) y, si aparece, la regla se diseña en 0.8 con el dato delante |
| **Caducidad por fila de la matriz en 0.7** | `findings.md § F017` | Es una mejora real y no es bloqueante. El lote de remediación ya acota el coste a **un re-certify por ciclo**. Va a 0.8, y **mientras tanto se corrige la prosa** para que no prometa más de lo que el mecanismo entrega (§ 7.6) |
| **Adelantar el escáner de literales a 0.7** | Implícita en `final-review § F` y en `simplification.md § 2.A` | Contradice la decisión cerrada del dueño de **partir la serie**, y la auditoría **no la revoca**: la señala como consecuencia a medir. El carril trivial se hace ligero por la otra vía —un `certify` de 1-2 M en vez de 9,2 M (D-12, D-15)— y **la proporción se reporta**, que es lo que convierte la 0.8 en decisión informada |

---

## Cómo se lee este registro dentro de un año

Las decisiones de este documento se agrupan en cuatro clases, y esa agrupación es el resumen:

- **Se quita lo que no compraba nada** — D-01, D-02, D-03, D-14, D-22. Una taxonomía, tres umbrales,
  tres causas de `ask`, cinco artefactos.
- **Se corrige lo que se contradecía** — D-04, D-05, D-12, D-13, D-23, D-24. Ninguna de estas
  correcciones quita una garantía; todas quitan una imposibilidad.
- **Se completa lo que faltaba escribir** — D-06, D-07, D-08, D-10, D-25, D-28. Cinco bloqueantes que
  se resolvían **escribiendo media página**, y que costaban una fase entera si se descubrían
  implementando.
- **Se añade lo barato que faltaba** — D-09, D-11, D-15, D-16, D-17, D-18, D-19, D-20, D-21, D-26,
  D-27. Cuatro comprobaciones que no existían, un perímetro que decidía en silencio si el plugin
  gobierna algo, y la graduación que impide que el bucle de remediación se coma el trabajo.

---

## Addendum · 1-sep-2026 — Fase 0 ejecutada, freeze intacto

Las cinco sondas y la comprobación de esquemas de § 16 se ejecutaron contra Claude Code 2.1.248 y
el MCP real; el resultado completo vive en [`implementacion-0.7.md`](implementacion-0.7.md), junto
a la norma. **Ninguna activó la regla de reapertura de § 21**: `ask` es válido y efectivo
(`escalate` no existe y se ignora en silencio); un `ask` no atendido deniega, no auto-aprueba;
`PostToolBatch` dispara también con lotes de una llamada (campo real: `tool_response`, sin
`error`); la carga diferida ahorra ~86,6 K tokens/turno (el doble de lo estimado); las tres clases
de payload tienen ejemplar real. Las tres discrepancias de esquema (vistas/filtros usan
`visibilityExpression`, ningún `update*` lleva `parentFolderUuid`, `updateFolder` no tiene campos
de seguridad) caen en la fila «se corrige la regla antes de escribirla» de la tabla de supuestos
del propio freeze — salida prevista de la sonda, no reapertura.
