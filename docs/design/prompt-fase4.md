/goal Implementa y completa EXCLUSIVAMENTE la Fase 4 de appian-harness 0.7 definida en la fuente normativa congelada por DESIGN FREEZE.

Estado confirmado:

- Fase 0 = DONE
- Fase 1 = DONE
- Fase 2 = DONE · DoD 3/3 PASS
- Fase 3 = DONE · DoD 5/5 PASS
- rama = phase-4-judge-matrix-skills
- base = b729359e6559395c60cf3ec93c9f780a6eed515b
- working tree limpio

NO implementes Fase 5 ni posteriores.

## FUENTE NORMATIVA

Antes de modificar código:

1. identifica la única fuente normativa vigente;
2. lee únicamente:
   - §16 Fase 4 y su Definition of Done;
   - las secciones normativas referenciadas desde Fase 4;
   - los resultados de Fase 3 que Fase 4 consume;
   - el tracker de implementación;
   - agentes, scripts, skills y tests directamente afectados.

No leas docs/archive/.
No vuelvas a auditar el diseño.
No recuperes decisiones históricas.

## OBJETIVO

Implementa exclusivamente el sistema de juicio proporcional definido para Fase 4.

### 1. JUEZ ÚNICO

Debe existir un único agente de juicio Appian.

Tres invocaciones independientes:

- design
- certify
- risk

Cada una debe:

- empezar con contexto fresco;
- tener rúbrica propia;
- recibir únicamente la evidencia necesaria;
- no recibir la conclusión del constructor;
- no recibir dumps completos;
- trabajar con rutas, hashes y señales derivadas.

Elimina o integra los antiguos verifier/reviewer según la norma.

No conviertas las tres fases en una misma sesión con contexto acumulado.

### 2. MATRIZ DE VEREDICTO

Implementa el contrato vigente de matriz objeto × puerta en validate_verdict.py.

Mantén cobertura completa.

Formato proporcional:

- PASS → compacto;
- FAIL / NOT_MEASURED / N/A → evidencia, impacto, remedio y referencia cuando corresponda.

No elimines celdas para ahorrar tokens.

### 3. GATES

Implementa exactamente las clases normativas:

- CARDINAL
- RECOMMENDED
- CONTEXTUAL

Respeta su comportamiento.

Especialmente:

- CARDINAL puede bloquear;
- RECOMMENDED sigue el comportamiento definido por la norma;
- CONTEXTUAL no convierte rendimiento o mantenibilidad en bloqueo duro si la norma los trata como deuda.

No inventes nuevas clases.

### 4. RE-EMISIONES

Implementa la protección contra re-emisiones inútiles.

Debe quedar demostrado que:

- un tercer veredicto sin finding nuevo ni evidencia nueva se rechaza;
- no existe re-emisión manual repetitiva del mismo juicio.

### 5. REMEDIACIÓN

Implementa el ciclo normativo:

hallazgos
→ aplicar todos los hallazgos del ciclo en un lote coherente
→ una única recertificación

Respeta:

- máximo de ciclos;
- extensiones permitidas;
- una recertificación por ciclo;
- no una por finding;
- no cadenas de subagentes.

### 6. SKILLS

La configuración final debe conservar únicamente estas cinco skills normativas:

- appian-specify
- appian-plan
- appian-build
- appian-review
- appian-best-practices

Retira:

- appian-verify
- appian-run

si siguen presentes.

No dupliques la skill oficial Appian.

Frontera:

skill oficial Appian = mecánica de construcción
harness = gobierno, criterio, evidencia y cierre

### 7. PROGRESSIVE DISCLOSURE

Implementa la profundidad gradual de referencias.

referencesLoaded debe representar realmente qué referencias fueron utilizadas.

No cargues toda appian-best-practices por defecto.

El juez debe empezar con contexto mínimo y profundizar solo en las referencias necesarias para las celdas que está evaluando.

### 8. APPIAN-PLAN

Incorpora lo que Fase 3 dejó explícitamente aplazado para Fase 4 cuando la norma lo exija:

- detección de pasos manuales (§ 8.8 pieza 1);
- alineación con la guidance oficial Appian;
- sin copiar mecánica cubierta por la skill oficial.

También revisa las demás piezas que Fase 3 dejó expresamente como entrada de Fase 4, pero implementa solo las que la norma asigna realmente a esta fase.

## COSTE Y CONTEXTO

Esta fase introduce juicio y por tanto es especialmente sensible al coste.

Reglas:

- juez solo cuando el kind/carril lo exige;
- cero jueces cuando el suelo determinista ya resuelve la garantía;
- no ejecutar design/certify/risk “por prudencia”;
- no pasar renders completos;
- no pasar logs completos;
- no pasar todos los objetos de golpe si puede trabajarse por bloques;
- no reemitir verdicts sin evidencia nueva;
- no usar varios agentes para votar;
- no usar Agent Teams;
- no usar advisor salvo necesidad real y explícita.

El objetivo no es maximizar revisión.
El objetivo es comprar únicamente el juicio que Fase 3 no puede comprar determinísticamente.

## CASO ÁCIDO

No rompas el caso ácido.

Debe seguir siendo cierto:

- cambio visual trivial puede permanecer micro;
- fallo de instrumento no cambia automáticamente el kind;
- NOT_MEASURED / REQUIRES_HUMAN tiene salida definida;
- no vuelven verifier/reviewer antiguos;
- no aparece una cadena de jueces para un micro que no los debe.

Fase 4 completa el certify donde corresponde, pero NO convierte todo en task ni obliga a judge universal.

## IMPLEMENTACIÓN

Trabaja incrementalmente:

unidad coherente
→ implementación
→ tests específicos
→ corrección
→ siguiente unidad

No ejecutes la suite completa después de cada cambio.

Cuando el código esté estable:
→ una única regresión final.

No polling.
No waits activos.
No trabajo repetido cuyo resultado no pueda haber cambiado.

## DESIGN FREEZE

No reabras decisiones por preferencia.

Solo si aparece:

- evidencia real;
- comportamiento de Claude Code/Appian distinto al esperado;
- test que demuestra defecto del diseño;
- riesgo de seguridad nuevo.

Si ocurre:

1. registra evidencia;
2. identifica decisión afectada;
3. aplica cambio mínimo;
4. documenta addendum;
5. continúa sin auditoría general.

## DEFINITION OF DONE

Antes de marcar DONE:

1. relee literalmente el "Hecha cuando" de Fase 4;
2. convierte cada condición en PASS / FAIL / NOT MEASURED;
3. demuestra cada PASS con evidencia;
4. ejecuta regresión final una sola vez sobre código estable;
5. comprueba que Fase 5 no se haya implementado accidentalmente;
6. actualiza el tracker.

Debe quedar demostrado, como mínimo según la norma vigente:

- ningún juez recibe dumps completos;
- los veredictos task se generan sin re-emisión manual;
- un tercer veredicto sin finding/evidencia nueva es rechazado;
- quedan exactamente las cinco skills normativas;
- lint_skills.py pasa;
- cualquier otra condición literal de §16 Fase 4.

Solo marca DONE si el DoD normativo está completamente demostrado.

## GIT

Trabaja únicamente en:

phase-4-judge-matrix-skills

Puedes hacer commits internos coherentes.

NO:
- push a main;
- push de la rama final todavía;
- abrir PR;
- mergear;
- empezar Fase 5.

## SALIDA FINAL

Devuélveme:

### Fase 4

- unidades implementadas;
- arquitectura final del juez;
- agentes eliminados/conservados;
- skills eliminadas/conservadas;
- matriz implementada;
- clases CARDINAL / RECOMMENDED / CONTEXTUAL;
- comportamiento de re-emisiones;
- ciclo de remediación;
- tests y resultados;
- DoD literal con PASS/FAIL;
- caso ácido;
- coste/contexto observado del judge;
- Design Freeze reabierto: sí/no;
- trabajo aplazado;
- Fase 5 implementada accidentalmente: sí/no;
- git status;
- git diff --stat;
- commits existentes en la rama;
- READY TO REVIEW o NOT READY TO REVIEW.

NO hagas push.
NO abras PR.
NO empieces Fase 5.