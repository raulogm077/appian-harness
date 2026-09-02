# Kit de la pasada atendida · DoD de Fase 2 (mitad «un solo prompt»)

> La condición del DoD que exige a una persona delante: «un `micro` y un `task` (con y sin
> `tasks{}`) abren, escriben y cierran en un proyecto de pruebas con **un solo prompt cada
> uno**». P2 demostró que en headless un `ask` deniega sin preguntar, así que esta mitad solo se
> mide en sesión interactiva. Hasta ejecutarla queda **NOT MEASURED** — la mecánica equivalente
> sin persona (0 asks del harness en todo el ciclo) está cubierta por
> `hooks/test_v07_end_to_end.py`.

## Preparación (una vez)

1. Un directorio de pruebas con `.claude/appian-harness.json`:

   ```json
   {
     "evidenceDir": "evidence",
     "activeTaskFile": "tasks/current.json",
     "appianMcpToolPrefixes": ["mcp__appian-dev__", "mcp__appian__"],
     "officialAppianSkillPath": "~/.claude/skills/appian"
   }
   ```

2. El plugin appian-harness cargado (los hooks de este repo) y los MCP de Appian registrados.
3. Objetivos reales solo de la app de práctica (`RGM_Practice_Record` o similar `RGM_*`).

## La pasada `micro` (Raúl delante)

1. Frase: *«cambia la descripción de la constante `RGM_…` a “…”»* (o un label de interfaz).
2. Lo que debe verse: preflight de lecturas → `tasks/current.json` v2 con `grant` → **UN**
   `AskUserQuestion` con la lista completa → escritura → `request: "close"` → Stop cierra
   `closed` firmado.
3. Contar los prompts que ve la persona. **Pasa si es exactamente 1** (el del grant; los prompts
   de la capa de permisos de plataforma sobre herramientas MCP se dejan en allowlist para no
   contaminar la cuenta, § 6.2 cuenta los de confirmación importados, no los del sistema de
   permisos de Claude Code sobre cada tool).
4. Repetir como `task` con `tasks{}` (dos objetos RGM_* en dos entradas).

## Qué registrar al terminar

En `implementacion-0.7.md` § Fase 2, tabla del DoD: la fila «un solo prompt» pasa de NOT
MEASURED a PASS/FAIL con: fecha, nº de prompts contados por origen (harness / capa oficial /
plataforma), y el transcript o su ruta como evidencia.
