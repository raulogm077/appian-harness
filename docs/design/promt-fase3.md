/goal Implementa y completa EXCLUSIVAMENTE la Fase 3 de appian-harness 0.7 definida en la fuente normativa congelada por DESIGN FREEZE.

Estado de partida confirmado:

- Fase 0 = DONE
- Fase 1 = DONE
- Fase 2 = DONE · DoD 3/3 PASS
- rama actual = phase-3-floor-and-evidence
- base = 9e04d37fed6660fe2b426f37e7c5e52052634a5b
- working tree limpio
- CI de main verde

NO implementes Fase 4 ni posteriores.

## 1. FUENTE DE VERDAD

Antes de modificar código:

1. identifica la única fuente normativa vigente;
2. lee únicamente:
   - la definición de Fase 3;
   - su Definition of Done;
   - las secciones normativas referenciadas desde Fase 3;
   - los resultados de Fase 0 que condicionen Fase 3;
   - el tracker de implementación;
   - el código y tests directamente afectados.

NO leas docs/archive/ salvo necesidad explícita de migración.
NO reconstruyas decisiones desde documentos históricos.
NO vuelvas a auditar el diseño.

## 2. OBJETIVO

Implementa el suelo determinista y el sistema de evidencia definido para Fase 3.

La fuente normativa vigente decide el detalle exacto.

Debes cubrir únicamente lo que Fase 3 exija actualmente, incluyendo cuando aplique:

- observación/acreditación de lecturas de verificación;
- PostToolBatch o el fallback fijado por Fase 0;
- toolUseId;
- guaranteeClass / clase de garantía si forma parte del contrato vigente;
- registro observable de carga de la skill oficial o su fallback;
- suelo determinista por tipo de objeto;
- comportamiento por defecto para tipos no cubiertos;
- checks de referencias cruzadas;
- checks N3 para process models;
- suelo proporcional para escrituras non-behavioural;
- normalización de renders;
- garantías de render poblado/vacío;
- N2 por firma de propiedades;
- señales derivadas sin cargar árboles enormes al contexto;
- checker estático SAIL;
- tabla de cobertura por categorías;
- categorías NOT MEASURED;
- retención/rotación de evidencia si pertenece a esta fase según la norma vigente.

No recuperes requisitos antiguos que el DESIGN FREEZE haya eliminado.

## 3. PRINCIPIO DE IMPLEMENTACIÓN

Todo lo determinista debe resolverse con:

hook / script / test

y no con agentes.

No utilices un juez para comprobar algo que pueda demostrar código.

No lances auditor, reviewer, verifier, advisor o subagentes salvo que exista una necesidad real que no pueda resolverse determinísticamente.

No uses Agent Teams.

## 4. CONTROL DE COSTE Y CONTEXTO

Las Fases anteriores demostraron que el desperdicio puede dominar el trabajo.

Por tanto:

- no leas harness_hooks.py entero repetidamente;
- no reconstruyas contratos ya documentados;
- no cargues artefactos grandes al contexto;
- no vuelques renders completos al modelo;
- usa progressive disclosure;
- reutiliza evidencia persistida;
- no ejecutes la misma comprobación dos veces si nada que pueda afectar su resultado ha cambiado;
- no hagas full regression después de cada modificación;
- no hagas polling;
- no hagas waits activos;
- no sigas trabajando después de que el objetivo de una unidad esté demostrado.

Si detectas trabajo que no compra una garantía concreta, elimínalo del flujo.

## 5. IMPLEMENTACIÓN INCREMENTAL

Divide Fase 3 internamente en unidades coherentes siguiendo las dependencias de la fuente normativa.

Para cada unidad:

implementar
→ tests específicos
→ corregir
→ continuar

No hagas un gran cambio y pruebes todo al final.

No hagas refactors fuera del alcance salvo que sean imprescindibles para Fase 3.

## 6. DESIGN FREEZE

No reabras decisiones congeladas por preferencia arquitectónica.

Solo puedes reabrir una decisión si aparece evidencia nueva de:

- comportamiento real de Claude Code;
- comportamiento real de Appian/MCP;
- fallo de test/E2E que demuestre un defecto del diseño;
- riesgo de seguridad no contemplado.

Si ocurre:

1. registra la evidencia;
2. identifica exactamente la decisión afectada;
3. aplica el cambio mínimo;
4. documenta el addendum;
5. continúa sin abrir una auditoría general.

## 7. TESTS IMPORTANTES

Crea tests únicamente para garantías reales del contrato.

Debes comprobar, cuando corresponda según la norma:

- lectura de verificación acreditada al objeto correcto;
- toolUseId correcto;
- lectura antigua no puede acreditar una escritura nueva;
- failed/ambiguous no cuentan como evidencia válida;
- instrumento que falla no cambia automáticamente el kind;
- fallo del instrumento y regresión del objeto se distinguen;
- escrituras behavioural:false pagan únicamente el suelo proporcional;
- cross-reference detecta referencias rotas;
- process model graph check detecta los defectos definidos;
- normalización de render es estable para dos renders equivalentes;
- poblado y vacío se distinguen por las garantías normativas;
- datos aleatorios como _cId/nonces/duration no alteran el resultado normalizado;
- el checker SAIL devuelve NOT MEASURED donde no puede demostrar una categoría;
- ningún PASS se obtiene por ausencia de medición;
- tipos sin suelo definido siguen el comportamiento de defecto normativo.

No conviertas esta lista en requisitos nuevos: prevalece siempre la fuente normativa.

## 8. CASO ÁCIDO

La Fase 3 debe conservar el caso ácido definido por el DESIGN FREEZE.

Especialmente:

- un cambio visual trivial debe poder seguir siendo micro;
- estar publicado en Site no debe escalar por sí solo el kind si esa es la decisión vigente;
- un fallo conocido de testInterface/N2 no debe provocar escalada automática si la norma vigente lo prohíbe;
- un fallo del instrumento no debe confundirse con una regresión introducida por la escritura;
- no deben repetirse checks cuyo resultado no puede haber cambiado.

No adaptes el caso ácido para hacer que pase.

Adapta la implementación al contrato.

## 9. DEFINITION OF DONE

NO marques Fase 3 como DONE porque el código esté escrito.

Antes de terminar:

1. relee literalmente el "Hecha cuando" / Definition of Done de Fase 3;
2. convierte cada condición en PASS / FAIL / NOT MEASURED;
3. aporta evidencia concreta para cada PASS;
4. ejecuta los tests relevantes;
5. ejecuta la regresión final necesaria una única vez cuando el código esté estable;
6. comprueba que Fase 4 no se haya implementado accidentalmente;
7. actualiza el tracker.

Solo marca Fase 3 DONE si TODAS las condiciones normativas están demostradas.

## 10. GIT

Trabaja únicamente en:

phase-3-floor-and-evidence

NO hagas push a main.

Durante la implementación puedes hacer commits coherentes en esta rama si lo necesitas, pero:

- NO abras PR;
- NO hagas merge;
- NO empieces Fase 4.

El cierre mediante push de rama + PR se hará después de que yo revise el resultado final.

## AL TERMINAR

Devuélveme únicamente:

### Fase 3

- unidades implementadas;
- ficheros modificados;
- tests ejecutados y resultados;
- PASS/FAIL de cada condición literal del DoD;
- caso ácido: resultado;
- categorías NOT MEASURED;
- cualquier Design Freeze reabierto y evidencia;
- trabajo aplazado;
- trabajo de Fase 4 detectado accidentalmente: sí/no;
- git status;
- git diff --stat;
- commits creados en la rama si los hubiera;
- READY TO REVIEW o NOT READY TO REVIEW.

NO hagas push.
NO abras PR.
NO empieces Fase 4.