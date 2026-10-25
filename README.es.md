# Be-Ambitious Harness — un flujo planificador / ejecutor / verificador para tareas ambiciosas de IA

> Haz que los agentes de IA apunten más alto sin perder el control: dos listones para cada tarea, una comprobación de entrada (gate) barata antes del trabajo caro y un verificador independiente que nunca ve el razonamiento del ejecutor.

[English](README.md) · [Русский](README.ru.md) · [简体中文](README.zh-CN.md) · **Español**

![Escenarios](https://img.shields.io/badge/escenarios-6-blue) ![Roles](https://img.shields.io/badge/roles-planificador%20%7C%20ejecutor%20%7C%20verificador-informational) ![Evaluaciones](https://img.shields.io/badge/evaluaciones-2%20de%208%20tareas-yellow) ![Idiomas](https://img.shields.io/badge/archivos-EN%20%7C%20RU-informational) ![Licencia](https://img.shields.io/badge/licencia-MIT-lightgrey)

---

## Qué es: un framework de ingeniería de prompts, una skill de Claude Code, un flujo multiagente

La mayoría de los prompts de IA piden un paso: *corrige este bug, haz esta pantalla, analiza este CSV.* El resultado que de verdad buscabas (*la app deja de fallar, los usuarios completan el pago, sabes por qué aumentó la pérdida de clientes*) queda implícito, así que el modelo entrega el paso y se detiene.

Be-Ambitious Harness es un **framework de ingeniería de prompts y un flujo de trabajo multiagente** que convierte cualquier tarea en un prompt con:

- **Dos listones**: el resultado base y uno más ambicioso, con el trabajo adicional y la incertidumbre principal nombrados.
- **Una comprobación de entrada**: una prueba barata y observable que decide si vale la pena emprender el camino ambicioso, con un criterio de superación fijado *antes* de ejecutar la prueba y tres resultados posibles: superada, no superada, datos insuficientes.
- **Aislamiento de roles**: un planificador escribe el prompt, un ejecutor lo lleva a cabo y un verificador evalúa el resultado viendo solo los requisitos, los criterios de aceptación y el registro de evidencias. Nadie evalúa su propio trabajo.
- **Seis guías de escenario**: diseño/UX, análisis de datos, código, redacción/investigación, decisiones/planes y genérico, cada una con controles y trampas propios de su dominio.
- **Un conjunto de evaluaciones**: 8 tareas de prueba y una tabla de puntuación de 30 criterios, para saber cuándo falla el propio harness (arnés o marco de trabajo). Hasta ahora se han ejecutado dos de las tareas; consulta [Estado](#estado-qué-se-ha-probado).

Se distribuye como **skill de Claude Code** (`/be-ambitious-harness`) en **inglés y ruso**, y funciona con cualquier agente capaz de leer una carpeta de archivos markdown.

**Instalación:** `git clone https://github.com/alexpiar/be-ambitious-harness.git ~/.claude/skills/be-ambitious-harness` y luego `/be-ambitious-harness` en Claude Code. Detalles y la versión en ruso — en [Instalación](#instalación).

---

## Por qué existe

El 13 de octubre de 2026, Felix Rieseberg, gerente de ingeniería (engineering manager) en Anthropic que ha dirigido la ingeniería de Claude.ai, Cowork y Claude Code Desktop, publicó [*How to be more ambitious: A tutorial for humans with models*](https://felixrieseberg.com/how-to-be-more-ambitious-a-tutorial-for-humans-with-models/). Las ideas centrales: pensar en el resultado y no en la tarea aislada; exigir los instrumentos que usan los mejores del sector; incorporar otras disciplinas; y no pedirle al modelo que se juzgue a sí mismo, sino exigir una validación externa. Compartió un prompt breve: *"Quiero una versión más profunda de esta tarea, no una más grande…"*

En pocos días aparecieron skills de la comunidad: [`be-ambitious` de DannyMac180](https://github.com/DannyMac180/skills) envuelve ese prompt, y [robonuggets/be-ambitious](https://github.com/robonuggets/be-ambitious) convierte la altitud, la profundidad y la amplitud en pasos y después hace el trabajo.

El prompt es excelente y tiene un límite: es un solo prompt. En cuanto añades las reglas que hacen segura la ambición (criterios fijos, límites de presupuesto, verificación obligatoria), te topas con tres modos de fallo descritos en investigaciones recientes sobre LLM:

| Modo de fallo | Qué dice la investigación | Qué hace el harness al respecto |
|---|---|---|
| **Saturación de restricciones** | El seguimiento fiable de instrucciones se viene abajo por encima de 5–6 restricciones simultáneas en una sola generación; en 15 modelos con k=8, cada restricción por separado se sigue cumpliendo ~41% de las veces, pero las ocho se cumplen a la vez solo el 5.7% de las veces ([Vasileva, arXiv:2608.12426](https://arxiv.org/abs/2608.12426); póster en un taller de ICML 2026) | Cada rol recibe solo los archivos de su paso (250–630 palabras cada uno); la estructura sale de plantillas, no de reglas mantenidas en el contexto |
| **Las instrucciones negativas resultan contraproducentes** | Nombrar una palabra prohibida predispone al modelo a producirla; en los fallos, la señal de supresión es 4.4× más débil ([Rana, preprint de 2026](https://arxiv.org/abs/2601.08070); un solo modelo, Qwen2.5-7B-Instruct) | Las instrucciones son positivas: "incluye solo las secciones de la plantilla" en lugar de "no incluyas el análisis" |
| **Sesgo de autopreferencia** | Los jueces LLM puntúan más alto el texto de baja perplejidad que los evaluadores humanos, sin importar quién lo haya escrito ([Wataoka et al., NeurIPS 2024 Safe Generative AI Workshop](https://arxiv.org/abs/2410.21819)) | El verificador solo ve requisitos, criterios, resultado y evidencias, y preferiblemente se ejecuta en otro modelo, que es lo que realmente cambia la perplejidad del juez |

Cada uno de estos hallazgos se apoya en un único estudio reciente, y aplicarlos a las instrucciones de agentes es una extrapolación propia del harness. El harness es un intento de que "sé más ambicioso" siga funcionando dentro de estos límites, y su conjunto de evaluaciones está ahí para mostrar dónde no lo consigue.

---

## Los principios

### 1. El resultado por encima del paso (altitud)

Todo análisis empieza con *¿qué debería ser posible después de este resultado?* Corregir un bug es un paso; "este tipo de fallo no se repite" es un resultado. Una presentación es un paso; "la dirección detecta los problemas un trimestre antes" es un resultado. El planificador nombra ambos y construye el prompt en torno al resultado.

### 2. Dos listones, siempre

El **listón base** es una ejecución de calidad dentro del alcance original. El **listón ambicioso** es uno de tres movimientos: un umbral de calidad más alto, eliminar la causa en lugar del síntoma, o una forma más útil de alcanzar el objetivo. Para cada listón ambicioso, el planificador indica la ganancia esperada, el trabajo adicional y la incertidumbre principal. Si no existe un listón ambicioso útil, el planificador lo dice: ambición no es inflar la tarea.

### 3. Objetivos de aprendizaje para tareas nuevas

La investigación sobre fijación de objetivos muestra que los objetivos específicos y difíciles superan al "haz lo mejor que puedas" ([Locke & Latham, 2002](https://med.stanford.edu/content/dam/sm/s-spire/documents/PD.locke-and-latham-retrospective_Paper.pdf)). Pero cuando una tarea exige primero adquirir conocimientos o estrategias nuevas, un objetivo de *rendimiento* específico y difícil puede funcionar peor que "haz lo mejor que puedas", mientras que un objetivo de *aprendizaje* específico y difícil funciona mejor (Seijts & Latham, 2001; 2005). Los críticos añaden que los objetivos muy exigentes estrechan el foco e invitan a tomar atajos (Ordóñez et al., 2009). Por eso, en tareas desconocidas, el listón ambicioso se formula como un **objetivo de aprendizaje** ("averiguar en qué se va el tiempo"), y cualquier cifra asociada es una **hipótesis** ("p95 ≤ 300 ms"), no una promesa. El truco de Rieseberg, "¿necesitas 5 s en lugar de 10 s? Pide 200 ms", tiene su lugar aquí: como objetivo experimental con una prueba de viabilidad, para que deje de descartarse por "infundado".

### 4. La comprobación de entrada: evidencia barata antes del trabajo caro

Antes de que arranque la rama ambiciosa, una **comprobación de entrada** responde dos preguntas: ¿el resultado adicional tiene un valor real? ¿Y es alcanzable con los medios disponibles? Una comprobación de entrada solo está completamente especificada cuando tiene cinco atributos:

1. una acción concreta y los materiales que necesita,
2. un resultado observable (una cifra, un hecho, un artefacto; no una opinión),
3. un criterio de superación fijado *antes* de ejecutar la comprobación,
4. un límite de costo, **sustancialmente menor que el trabajo que desbloquea** (una prueba de 20 minutos que ahorra una semana está bien, aunque la tarea base dure 5 minutos),
5. acciones para los tres resultados: **superada, no superada, datos insuficientes.**

La ambigüedad es el tercer resultado, nunca el primero. El criterio se lee, no se revisa: si resulta inaplicable, eso es "datos insuficientes", no un motivo para cambiar las reglas a mitad del partido. Y si faltan materiales, se solicitan a la persona *antes* de empezar el trabajo; eso no es un resultado de la comprobación de entrada.

### 5. La persona decide el alcance y el presupuesto

Una comprobación de entrada puede mostrar que 200 ms es alcanzable y que los usuarios lo notarían. Si eso vale una semana depende del presupuesto y de las prioridades, y eso el harness nunca lo decide. Si la comprobación de entrada se supera y no se fijó presupuesto para la rama ambiciosa, el ejecutor entrega el resultado base **más** los resultados de la comprobación de entrada y una estimación de costo, y la decisión vuelve a la persona. Un modo "ambitious extension" (ampliación ambiciosa) es una *preferencia*, no un sustituto de la evidencia.

### 6. Tres roles, estrictamente separados

| Rol | Lee | Produce |
|---|---|---|
| **Planificador** | tarea, contexto, modo, un archivo de escenario | un prompt de siete secciones con la comprobación de entrada dentro |
| **Ejecutor** | el prompt, los materiales, el bloque "para el ejecutor" del escenario, sus archivos de instrucciones | el resultado y un registro de evidencias |
| **Verificador** | las secciones 1, 2, 4 y 6 del prompt, el resultado, los materiales, el registro de evidencias | un veredicto: aceptar / aceptar con observaciones / rechazar |

El verificador no corrige. El ejecutor no se evalúa a sí mismo en lugar del verificador. El verificador se ejecuta preferiblemente en un **modelo distinto**: la verificación con el mismo modelo es parcial por construcción.

### 7. Las plantillas por encima de las reglas

El prompt del ejecutor tiene **siete secciones fijas** (objetivo y resultado; requisitos obligatorios copiados literalmente; materiales; comprobación de entrada; enfoque; criterios de aceptación y verificación; finalización e informe). La estructura la impone un esqueleto, no una lista de reglas del tipo "asegúrate de…" que el modelo tenga que mantener en su atención. Antes de la entrega se aplica una lista de control previa; antes de que la persona vea nada, una lista de control posterior.

### 8. La verificación es independiente o no es verificación

Los criterios de aceptación miden el objetivo, no un indicador indirecto cómodo. Cada prompt incluye una prueba de falsación ("¿qué observación demostraría que esto es falso?") y nombra qué cuenta como manipular la métrica. Independencia, por orden de preferencia: una herramienta o prueba que el ejecutor pueda lanzar; un benchmark externo; datos reservados; un método de medición distinto; la reproducción. Otro agente es útil **si realiza un control de ese tipo**: estar de acuerdo con la respuesta no es un control.

### 9. Los escenarios aportan el conocimiento del dominio

Las seis guías se asignan según *dónde vive el resultado*, no según el tema. Cada una da pistas para los cuatro puntos del análisis, trampas típicas, un bloque "para el ejecutor" y un ejemplo resuelto de dos listones. La guía de diseño/UX parte de los datos del embudo antes del primer píxel; la de datos reserva un conjunto de prueba como primera acción registrada del ejecutor; la de código escribe la prueba que falla antes de la corrección.

### 10. El harness se pone a prueba a sí mismo

`evals/` contiene seis tareas (una por escenario) y dos trampas: materiales que faltan y una comprobación de entrada que no alcanza su umbral por poco (AUC 0.60 frente a 0.65; 8 frente a 9 de 10 ejecuciones). Las tareas revisan lo que no se ve con solo leer: ¿empezó el ejecutor por la comprobación de entrada? ¿Se escribió la prueba antes de la corrección (T3)? ¿Alguien bajó el criterio sin decirlo (L2)?

---

## Cómo fluye una tarea

```
 persona ──▶ tarea + contexto + modo
               │
               ▼
         ┌──────────────┐   scenarios/_index.md
         │ PLANIFICADOR │──▶ elige un escenario
         └──────────────┘
               │  análisis (≤500 palabras) → preguntas (≤3) → prompt (7 secciones)
               ▼
         checklists/pre-flight.md       ◀── cualquier "no" → de vuelta al planificador
               │
               ▼
         ┌──────────────┐   sesión nueva: prompt, materiales, sus archivos de instrucciones — nunca el análisis
         │   EJECUTOR   │──▶ primero la comprobación de entrada → resultado registrado → rama → trabajo → informe
         └──────────────┘
               │
               ▼
         ┌──────────────┐   sesión nueva, otro modelo si es posible
         │ VERIFICADOR  │──▶ mide los criterios por sí mismo → prueba de falsación → veredicto
         └──────────────┘
               │
               ▼
         checklists/post-run.md ──▶ cinco líneas a la persona ──▶ aceptar / rehacer / detener
```

---

## Escenarios

| Escenario | Dónde vive el resultado | Ejemplo de comprobación de entrada |
|---|---|---|
| `design-ux` | una pantalla, un flujo, un prototipo, un sistema de diseño | embudo por pasos a partir de la analítica; 3–5 grabaciones de sesiones |
| `data-analysis` | un hallazgo, una métrica, un modelo, un informe de datos | un modelo base sobre un 20% de datos reservados alcanza AUC ≥ 0.6 |
| `code-engineering` | código que funciona, una corrección, una funcionalidad, infraestructura | el bug se reproduce en ≥9/10 ejecuciones; una función acapara ≥50% del tiempo del perfil |
| `writing-research` | un artículo, una revisión, documentación, una charla | se encuentran ≥2 fuentes primarias dentro del límite de tiempo |
| `decision-plan` | una decisión, un plan, una hoja de ruta, una priorización | la suposición clave, contrastada con 5 conversaciones o con los datos del último mes |
| `generic` | cualquier otra cosa | la acción más barata tras la cual queda claro si el camino caro vale la pena, o "sin comprobación de entrada, listón base" |

---

## Estado: qué se ha probado

**Comprobación de entrada, 21 oct. 2026** — [registro completo](evals/runs/2026-10-21-gate/). Dos tareas de evaluación (T3: código; L2: la trampa "criterio frente a datos" sobre un conjunto de datos de pérdida de clientes), el harness frente a la skill individual [robonuggets/be-ambitious](https://github.com/robonuggets/be-ambitious) en el mismo modelo, con la puntuación a cargo de un evaluador a ciegas en un modelo distinto. El protocolo y el criterio de superación quedaron registrados en un commit antes de la primera ejecución.

- El harness no activó **ninguna condición de fallo** en ninguna de las dos tareas. La skill individual activó **dos de tres en T3**: un plan ambicioso de varios escalones en modo "keep scope" (mantener el alcance) y la edición del código fuente antes de escribir las pruebas.
- En L2, la comprobación de entrada no alcanzó su umbral fijado (ROC AUC 0.548 frente a 0.65). El ejecutor registró "no superada", no tocó el criterio y entregó el modelo base (0.740 frente a 0.537 de los atributos estáticos); el verificador recalculó todas las cifras a partir de su propia copia de los datos: diferencia cero.
- **Salvedad importante:** la skill individual dio el resultado técnicamente más profundo las dos veces: un parser de locales más completo en T3 y un análisis más rico en L2. Donde ganó el harness fue en disciplina (la prueba antes de la corrección, el alcance tal como se pidió, el criterio leído en lugar de revisado), no en profundidad.
- Dos tareas, una ejecución cada una: una prueba de humo, no un benchmark. La evaluación a ciegas fue parcial. Las ejecuciones usaron los archivos en ruso; la traducción al inglés aún no se ha ejecutado para probar su comportamiento.
- La ejecución sacó a la luz un defecto del harness: el verificador no recibe el criterio de la comprobación de entrada (sección 4 del prompt), así que no puede contrastarlo con el prompt. La corrección está pendiente.

**Aún sin ejecutar:** T1, T2 como tarea independiente, T4–T6, L1.

**Carencias conocidas** (de las notas originales):
- No hay escenario para tareas multimodales (video, audio, 3D).
- No hay mecanismo para tareas de varios días con varias comprobaciones de entrada seguidas.
- El verificador en otro modelo es una recomendación; cómo elegir el modelo depende de tu entorno.

---

## Instalación

**Claude Code, archivos en inglés**: clona directamente en tu directorio de skills:

```bash
git clone https://github.com/alexpiar/be-ambitious-harness.git ~/.claude/skills/be-ambitious-harness
```

Los archivos del harness están disponibles en inglés y en ruso; este README está traducido al español.

**Claude Code, archivos en ruso**: los originales están en `ru/`:

```bash
git clone https://github.com/alexpiar/be-ambitious-harness.git /tmp/be-ambitious-harness
cp -r /tmp/be-ambitious-harness/ru ~/.claude/skills/be-ambitious-harness
```

Para un solo proyecto, usa en su lugar `.claude/skills/be-ambitious-harness/` dentro del proyecto. Después, en cualquier sesión: `/be-ambitious-harness`, o simplemente di *"make this task deeper"* ("haz esta tarea más profunda"). Si también tienes instalada alguna de las skills `be-ambitious` de la comunidad, llama a esta por su nombre completo: `/be-ambitious` irá a la suya.

**Cualquier otro agente**: indícale `SKILL.md` como punto de entrada. Todo es markdown plano; no hay código que ejecutar.

---

## Inicio rápido

1. Dale al planificador cuatro cosas: la **tarea**; el **contexto** (para quién es el resultado, materiales, plazo, requisitos obligatorios); el **modo**: `keep scope` (mantener el alcance), `ambitious extension` o `recommend` (recomendar), por defecto `recommend`; y **detenerse tras el análisis** (`yes` / `no`, por defecto `no`).
2. Lee el análisis y las preguntas (≤3). Responde o acepta las suposiciones marcadas con `[...]`.
3. Entrega el prompt a un ejecutor en una sesión nueva, junto con los materiales.
4. Entrega las secciones 1, 2, 4 y 6, el resultado y el registro de evidencias a un verificador en otra sesión nueva.
5. Aplica `checklists/post-run.md`. Decide.

**Así es la primera llamada** (Claude Code):

```
/be-ambitious-harness

Task: La página del catálogo tarda 5 segundos en cargar. Hazla más rápida.
Context: monolito Node/Postgres, repositorio adjunto, puedo darte una copia de la BD de producción. Plazo: este sprint.
Mode: recommend
Stop after analysis: yes
```

El planificador responde con un análisis de ≤500 palabras (tipo de tarea, dos listones, diseño de la comprobación de entrada, esquema elegido), hasta tres preguntas y un bloque de prompt con siete secciones numeradas. Con `Stop after analysis: yes`, espera tu respuesta antes de terminar el prompt.

Salidas reales de las ejecuciones registradas (en ruso): [el análisis y el prompt de un planificador](evals/runs/2026-10-21-gate/T3-A/planner-output.md), [el registro de un ejecutor con el bloque de la comprobación de entrada](evals/runs/2026-10-21-gate/L2-A/journal.md), [el veredicto de un verificador](evals/runs/2026-10-21-gate/L2-A/verdict.md). Una pasada por los tres roles tomó unos 15 minutos y ~245 mil tokens de subagentes en la tarea de código, y unos 50 minutos y ~350 mil tokens en la tarea de datos.

No todas las tareas lo necesitan: para una tarea de cinco minutos, prescinde del harness. Compensa su costo cuando la rama ambiciosa costaría un día o más.

---

## Ejemplo: una tarea, dos listones

**Tarea:** "La página del catálogo tarda 5 segundos en cargar. Hazla más rápida."

**Listón base:** perfilar, eliminar el principal cuello de botella, medir antes/después en el mismo banco de pruebas (≥5 ejecuciones, mediana y p95, en frío y en caliente por separado), añadir una prueba de regresión sobre el tiempo de respuesta.

**Listón ambicioso (como objetivo de aprendizaje):** averiguar en qué se va el tiempo lo bastante bien como para llegar a p95 ≤ 300 ms en frío; la cifra es una hipótesis.

**Comprobación de entrada:** perfilar una copia de producción; **criterio de superación:** una capa (BD, serialización, renderizado) acapara ≥70% del tiempo *y* puede sustituirse sin cambiar la API en ≤2 días; **límite de costo:** 2 horas.
- Superada y con presupuesto fijado → rama ambiciosa.
- Superada y sin presupuesto fijado → resultado base + perfil + estimación de costo; decide la persona.
- No superada o datos insuficientes → resultado base; informar de lo aprendido.

**Verificación:** el verificador vuelve a ejecutar el benchmark, revierte la corrección para confirmar que la prueba de regresión falla y revisa que la cifra "en caliente" no se haya presentado como la "en frío".

---

## Estructura del repositorio

```
be-ambitious-harness/
├── SKILL.md                 enrutador: recepción + seis pasos (0–6), reglas, mapa de archivos
├── agents/
│   ├── planner.md           análisis en cuatro puntos → prompt
│   ├── worker.md            orden de ejecución, registro de evidencias
│   └── verifier.md          orden de verificación, veredicto
├── core/
│   ├── gate.md              la comprobación de entrada: 5 atributos, 3 resultados, orden
│   ├── prompt-template.md   7 secciones + esqueleto
│   └── report-format.md     informe del ejecutor, veredicto del verificador, resumen de 5 líneas para la persona
├── scenarios/               _index.md + seis guías
├── checklists/              pre-flight.md, post-run.md
├── evals/                   tasks.md (6 + 2 trampas), scorecard.md (30 criterios)
│   └── runs/                ejecuciones registradas: protocolo, datos de prueba, registros, puntuaciones
├── ru/                      los originales en ruso — la misma estructura
├── README.md · README.ru.md · README.zh-CN.md · README.es.md
└── LICENSE · CITATION.cff
```

---

## Preguntas frecuentes

**¿Cómo hago que un agente de IA sea más ambicioso sin que se descontrole?**
Nombra dos listones, pon entre ellos una comprobación de entrada barata con un criterio fijo y deja la decisión sobre el presupuesto en manos de la persona. Ese es todo el harness en una frase.

**¿Por qué un LLM no debería evaluar su propio trabajo?**
Porque en el estudio de Wataoka et al., los jueces LLM puntuaron más alto que los evaluadores humanos el texto de baja perplejidad, es decir, familiar para el juez, lo hubieran escrito ellos o no; GPT-4 mostró la autopreferencia más fuerte ([Wataoka et al.](https://arxiv.org/abs/2410.21819)). Aquí el verificador nunca ve el razonamiento del ejecutor e, idealmente, se ejecuta en otro modelo.

**¿No es demasiado largo un prompt de siete secciones?**
Es largo para la persona y corto para el modelo: cada rol lee unos pocos archivos breves (250–630 palabras cada uno) más sus entradas. La alternativa, un único prompt con todas las reglas, cruza el umbral de 5–6 restricciones a partir del cual el seguimiento de instrucciones se viene abajo.

**¿Qué es un "harness" para agentes de IA?**
Un conjunto de archivos y listas de control que fijan *quién lee qué, en qué orden y qué cuenta como terminado*, para que la calidad del resultado dependa del proceso y no de que el modelo lo recuerde todo a la vez.

**¿Funciona con GPT / Gemini / modelos locales?**
Los archivos son markdown plano, sin sintaxis específica de ningún proveedor. El punto de entrada `/skill` es una convención de Claude Code; cualquier agente que sepa leer una carpeta puede seguir `SKILL.md`. Hasta ahora, las ejecuciones registradas usaron solo modelos Claude.

**¿En qué se diferencia de las skills `/be-ambitious` de la comunidad?**
Rieseberg publicó un prompt, no una skill. `be-ambitious` de DannyMac180 (15 oct. 2026) envuelve ese prompt: responde cuatro preguntas sobre el campo de la tarea y reescribe tu prompt. robonuggets/be-ambitious (17 oct. 2026) convierte la altitud, la profundidad y la amplitud en pasos y después hace el trabajo. Este harness añade la comprobación de entrada con sus tres resultados, el aislamiento de roles con un verificador separado, las guías de escenario, las listas de control y un conjunto de evaluaciones con ejecuciones registradas.

**¿Qué idioma debería usar?**
Ambas versiones tienen la misma estructura. Los archivos en ruso de `ru/` son los originales, y las primeras ejecuciones registradas los usaron; los archivos en inglés son una traducción verificada en cuanto a paridad estructural. En cualquier caso, las tareas y los resultados pueden estar en cualquier idioma.

---

## La investigación detrás del diseño

- F. Rieseberg — [How to be more ambitious: A tutorial for humans with models](https://felixrieseberg.com/how-to-be-more-ambitious-a-tutorial-for-humans-with-models/) (13 oct. 2026). Altitud / profundidad / amplitud; juez externo; el prompt original.
- M. I. Vasileva — [Large Language Models Can Follow Instructions, But Not Many at Once: Phase Transitions in Compositional Constraint Satisfaction](https://arxiv.org/abs/2608.12426) (arXiv, 2026; póster en el 2nd Workshop on Compositional Learning, ICML 2026). La fiabilidad se viene abajo por encima de 5–6 restricciones simultáneas.
- S. Rana — [Semantic Gravity Wells: Why Negative Constraints Backfire](https://arxiv.org/abs/2601.08070) (preprint de arXiv, 2026). Nombrar una palabra prohibida la vuelve más probable.
- K. Wataoka, T. Takahashi, R. Ri — [Self-Preference Bias in LLM-as-a-Judge](https://arxiv.org/abs/2410.21819) (NeurIPS 2024 Safe Generative AI Workshop). Los jueces favorecen el texto de baja perplejidad.
- E. Locke, G. Latham — *Building a practically useful theory of goal setting and task motivation: A 35-year odyssey* (American Psychologist, 2002).
- G. Seijts, G. Latham — *The effect of distal learning, outcome, and proximal goals on a moderately complex task* (Journal of Organizational Behavior, 2001); *Learning versus performance goals: When should each be used?* (Academy of Management Executive, 2005).
- L. Ordóñez, M. Schweitzer, A. Galinsky, M. Bazerman — *Goals Gone Wild: The Systematic Side Effects of Overprescribing Goal Setting* (Academy of Management Perspectives, 2009); cuestionado por Locke & Latham en el mismo número.
- N. Edwards, S. Schuster — [Ask or Assume? Uncertainty-Aware Clarification-Seeking in Coding Agents](https://arxiv.org/abs/2603.26233) (arXiv, 2026). En una versión subespecificada de SWE-bench Verified, separar la detección de la subespecificación de la ejecución del código elevó la tasa de resolución de un agente consciente de la incertidumbre del 61.2% al 69.4% (OpenHands + Claude Sonnet 4.5); una línea base interactiva más simple, basada en prompts, alcanzó el 70.4%.

---

## Cómo contribuir

Los issues y pull requests son bienvenidos. Las contribuciones más útiles, por orden:

1. **Ejecuciones de evaluación.** Ejecuta cualquier tarea de `evals/tasks.md`, completa la tabla de puntuación y abre un issue titulado `eval: T3 — <qué se rompió>`. Los fallos reales valen más que las opiniones. `evals/runs/` muestra cómo se registra una ejecución.
2. **Escenarios nuevos.** Si `generic.md` se queda claramente corto para tu dominio, esa es la señal para una guía nueva: sigue la estructura de `scenarios/_index.md`.
3. **Traducciones.** Los idiomas nuevos son bienvenidos; `ru/` sigue siendo la fuente de verdad hasta que una traducción haya superado las evaluaciones.
4. **Investigación.** Un artículo que cambie alguno de los principios anteriores merece un issue con un resumen de una línea de lo que cambia.

Por favor, mantén los archivos breves: el harness se basa en dar a cada rol pocas instrucciones a la vez.

---

## Hoja de ruta

- [x] Traducción al inglés de todos los archivos del harness
- [ ] Ejecuciones de evaluación registradas para las ocho tareas: T3 y L2 hechas, consulta [Estado](#estado-qué-se-ha-probado)
- [ ] Escenario para tareas multimodales (video, audio, 3D)
- [ ] Soporte de varias comprobaciones de entrada para tareas que abarcan varios días
- [ ] Receta de verificador en otro modelo para subagentes de Claude Code

---

## Autor

Creado por **Chernov Alexandr** (@alexpr). Si tu trabajo se basa en el harness, el botón "Cite this repository" de GitHub genera una cita lista para usar a partir de `CITATION.cff`.

Si el harness te ahorra un día perdido de trabajo con IA, una ⭐ ayuda a que otros lo encuentren: muchas clasificaciones de GitHub y la sección Explore dependen de las estrellas.

---

## Licencia

MIT — consulta [`LICENSE`](LICENSE).

No está afiliado a Anthropic ni cuenta con su respaldo. Claude y Claude Code son marcas comerciales de Anthropic, PBC.
