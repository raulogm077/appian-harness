Quiero hacer una ÚLTIMA auditoría de consolidación de `appian-harness 0.7 → 1.0` porque las revisiones anteriores han dejado documentación histórica mezclada con documentación normativa y eso ha provocado contradicciones sobre qué diseño debe implementarse.

IMPORTANTE:

Esta NO es otra ronda abierta de rediseño.

Su objetivo es:

1. regularizar toda la documentación;
2. reconstruir una única fuente normativa coherente;
3. verificar una última vez que esa fuente cumple los principios del proyecto;
4. resolver exclusivamente problemas reales todavía abiertos;
5. eliminar o archivar todo lo que ya no aplique;
6. terminar con DESIGN FREEZE y READY FOR IMPLEMENTATION.

NO quiero volver a entrar en un ciclo infinito de auditorías.

---

# PRINCIPIO RECTOR

El baseline es:

Claude Code

* skill oficial Appian
* Appian Dev MCP
* Appian Docs MCP

Principio:

**Appian oficial para construir; el harness para gobernar únicamente lo que Appian no gobierna.**

El harness debe aportar:

* calidad;
* seguridad;
* consistencia;
* mantenibilidad;
* evidencia;
* gobierno del workflow;

sin provocar:

* duplicidad;
* ceremonia innecesaria;
* múltiples agentes sin valor;
* verificaciones repetidas;
* loops;
* prompts falsos;
* exceso de contexto;
* exceso de tokens;
* ralentización desproporcionada.

Una modificación sencilla de Appian debe seguir siendo sencilla.

---

# FASE 1 — INVENTARIO DOCUMENTAL

Antes de analizar el diseño:

Localiza TODOS los documentos relacionados con:

* diseño del harness;
* auditorías;
* planes;
* workflow;
* arquitectura;
* implementación 0.7;
* decisiones;
* findings;
* revisiones.

Crea una tabla:

| Documento | Fecha | Propósito | Estado | Sustituido por | Acción |
| --------- | ----- | --------- | ------ | -------------- | ------ |

Estados permitidos:

* NORMATIVE
* SUPPORTING
* AUDIT
* HISTORICAL
* OBSOLETE

Debe existir finalmente:

**UNA Y SOLO UNA fuente normativa del diseño.**

Los documentos históricos pueden conservarse únicamente si existe una razón de trazabilidad clara.

Si no aportan trazabilidad necesaria:
eliminarlos.

No debe quedar ningún fichero cuyo contenido pueda confundirse razonablemente con el diseño vigente.

---

# FASE 2 — RECONSTRUIR LA FUENTE NORMATIVA

A partir de:

* las decisiones vigentes;
* findings resueltos;
* auditorías anteriores;
* plan revisado;
* segunda revisión;

construye UN documento consolidado final.

No hagas un parche sobre un documento antiguo.

Reconstruye el diseño vigente de forma coherente.

Nombre recomendado:

docs/design/appian-harness-0.7-1.0.md

Este será el único documento NORMATIVE.

Todos los demás documentos deberán apuntar explícitamente hacia él o quedar marcados como históricos.

---

# FASE 3 — AUDITORÍA FINAL

Audita exclusivamente el documento consolidado.

No revises documentos históricos como si siguieran siendo propuestas.

Comprueba:

## Arquitectura

* una responsabilidad principal por componente;
* ninguna duplicidad innecesaria;
* frontera clara con skill oficial Appian;
* frontera clara con Dev MCP;
* frontera clara con Docs MCP.

## Proporcionalidad

Comprobar los flujos de:

1. cambio visual trivial;
2. cambio funcional pequeño;
3. cambio estructural;
4. construcción de aplicación/funcionalidad amplia.

Un cambio trivial no puede activar un SDLC completo.

## Skills

Comprobar responsabilidades únicas de:

* appian-specify
* appian-plan
* appian-build
* appian-review
* appian-best-practices

En especial:

`appian-best-practices` NO debe duplicar la skill oficial Appian.

## Hooks

Los hooks deben aplicar invariantes.

No deben actuar como workflow ni repetir trabajo de skills.

Principio:

hook = enforcement
skill = workflow
script = comprobación determinista
agent = juicio

## Auditor

Solo debe realizar juicio que no pueda realizarse determinísticamente.

No debe volver a comprobar cosas que scripts/MCP ya han demostrado.

## Evidencia

Cada artefacto debe tener consumidor y garantía clara.

Eliminar artefactos sin consumidor.

## Contexto

Aplicar progressive disclosure.

No cargar contexto o schemas "por si acaso".

No volcar artefactos grandes al contexto.

## Agentes

No crear subagentes porque técnicamente sea posible.

Usarlos solo cuando el aislamiento o juicio independiente justifique coste adicional.

## Appian

El diseño debe ser genérico para cualquier proyecto Appian.

Gestión de Entrevistas es únicamente banco de pruebas.

---

# FASE 4 — COMPROBAR DECISIONES PROBLEMÁTICAS YA CONOCIDAS

Verifica expresamente que la fuente normativa NO haya reintroducido accidentalmente decisiones descartadas.

Comprueba al menos:

* si existen realmente dos o tres tamaños;
* qué significa `feature`;
* reglas de ≥3 dependientes;
* umbral del 30 %;
* ≥200 líneas;
* interfaces publicadas en Site;
* comportamiento ante fallo de testInterface/N2;
* closed-pending-human;
* context-floor;
* manualEstimateMinutes;
* build.md;
* risk-downgrades;
* leaseFile;
* anti-salami;
* quién escribe el registro de carga de la skill oficial;
* quién escribe los estados;
* quién puede modificar grant;
* cuántos prompts humanos puede producir un alcance normal;
* cuándo se ejecuta design;
* cuándo se ejecuta certify;
* qué puertas pueden bloquear.

Para cada uno:

Decisión vigente

* razón
* sección normativa.

No permitas que dos secciones respondan diferente.

---

# FASE 5 — COMPARACIÓN CONTRA BASELINE

Para cada componente que sobreviva pregunta:

> Si elimino este componente y utilizo únicamente skill oficial Appian + Dev MCP + Docs MCP, ¿qué garantía concreta pierdo?

Resultados posibles:

* KEEP
* SIMPLIFY
* REMOVE

No puede existir ningún KEEP sin garantía diferencial explícita.

---

# FASE 6 — CONTROL DE COMPLEJIDAD

Clasifica cada pieza como:

A. Trabajo productivo
B. Garantía necesaria
C. Evidencia necesaria
D. Desperdicio

Todo D se elimina.

Busca específicamente:

* misma validación ejecutada varias veces;
* múltiples agentes revisando lo mismo;
* re-emisiones sin nueva información;
* full regression cuando no corresponde;
* polling;
* waits;
* artefactos nunca consumidos;
* prompts por errores internos;
* duplicación de documentación oficial;
* gates que no protegen un riesgo.

---

# FASE 7 — FINDINGS

Solo crea findings si son NUEVOS o siguen realmente abiertos.

Cada finding:

ID
Severidad
Evidencia
Impacto
Cambio mínimo recomendado

Severidades:

BLOCKER
HIGH
MEDIUM
LOW

No vuelvas a generar findings que ya están resueltos simplemente con wording diferente.

Detecta duplicados semánticos.

---

# REGLA PARA MODIFICAR EL DISEÑO

Durante esta auditoría:

Puedes:

* eliminar;
* simplificar;
* corregir contradicciones;
* consolidar;
* cerrar huecos.

NO puedes añadir una nueva pieza arquitectónica salvo que:

1. exista un BLOCKER demostrado;
2. ninguna pieza actual pueda resolverlo;
3. el baseline oficial no lo resuelva;
4. puedas explicar qué garantía nueva compra;
5. sea la solución mínima.

Prefiere siempre simplificar antes que añadir.

---

# DOCUMENTACIÓN FINAL

Al acabar quiero una estructura documental simple.

Ejemplo:

docs/
design/
appian-harness-0.7-1.0.md        ← ÚNICA FUENTE NORMATIVA
decision-log.md                  ← decisiones relevantes

implementation/
0.7-progress.md                  ← se creará/actualizará durante implementación

audit/
final-consolidation-audit.md     ← resultado de ESTA auditoría

Los históricos solo se conservan si aportan trazabilidad real y deben estar claramente aislados, por ejemplo:

docs/archive/

No pueden quedar mezclados con documentos normativos actuales.

No conserves documentos solo "por si acaso".

---

# DESIGN FREEZE

Cuando hayas resuelto los findings aceptados, añade al documento normativo:

## DESIGN FREEZE — 0.7

Debe incluir:

* fecha;
* versión;
* fuente normativa;
* BLOCKERS abiertos: 0;
* decisiones aplazadas a 0.8;
* decisiones aplazadas a 1.0;
* supuestos pendientes exclusivamente de validación real en Fase 0;
* regla de cambio posterior.

Regla:

Después del DESIGN FREEZE el diseño solo puede reabrirse por:

1. evidencia nueva obtenida durante implementación;
2. comportamiento real de Claude Code distinto al esperado;
3. comportamiento real de Appian MCP distinto al esperado;
4. fallo de un test/E2E que demuestre un defecto del diseño;
5. riesgo de seguridad descubierto.

No puede reabrirse únicamente porque aparezca otra idea arquitectónica.

---

# RESULTADO OBLIGATORIO

Termina con:

## 1. Documentos eliminados

Lista y motivo.

## 2. Documentos archivados

Lista y motivo.

## 3. Documentos conservados

Y función exacta.

## 4. Fuente normativa

Una única ruta.

## 5. Cambios introducidos por esta auditoría

Solo deltas reales.

## 6. Findings finales

BLOCKER:
HIGH:
MEDIUM:
LOW:

## 7. Componentes finales

Para cada skill, agent, hook y script:

Responsabilidad
Garantía diferencial
Motivo para conservarlo

## 8. Flujo final

Representa:

visual trivial
funcional pequeño
estructural
aplicación/feature amplia

## 9. Trabajo aplazado

0.8
1.0

## 10. Veredicto

Solo uno:

READY FOR IMPLEMENTATION

o

NOT READY FOR IMPLEMENTATION

Si es READY:
realiza DESIGN FREEZE y NO vuelvas a auditar.

Si es NOT READY:
indica exclusivamente los BLOCKERS que lo impiden.

---

# REGLA FINAL

Esta es la última auditoría general del diseño.

No generes otra propuesta para posteriormente volver a auditarla.

El resultado debe ser:

documentación limpia
→ una fuente normativa
→ cero contradicciones conocidas
→ cero blockers
→ design freeze
→ implementación.

No implementes código del harness durante esta tarea.
