# Principios de GenAI aplicados a skillnest-app

> Fuente: ISTQB Certified Tester Testing with Generative AI (CT-GenAI) Syllabus v1.1.
> Complementa a [istqb-foundation-notes.md](../testing/istqb-foundation-notes.md): ese documento cubre *cómo probar*; este cubre *cómo construir* con LLMs.
> Cada sección separa **lo que dice el syllabus** de **cómo lo aplicamos**. Donde el syllabus no cubre un tema, se indica.
> Última revisión: 2026-10-08

---

## 1. Prompt Engineering

**Lo que dice el syllabus**
- Un prompt estructurado tiene 6 componentes: **rol, contexto, instrucción, datos de entrada, restricciones y formato de salida**.
- El **system prompt** fija rol, reglas y formato, y no cambia durante la conversación. El **user prompt** trae la tarea concreta de cada interacción.
- Hay tres técnicas base, combinables:

| Técnica | Cuándo usarla |
|---|---|
| **Few-shot** (dar ejemplos dentro del prompt) | Salidas repetitivas con un formato fijo |
| **Prompt chaining** (encadenar varios prompts) | Tareas complejas: se divide en pasos y se verifica cada resultado intermedio |
| **Meta prompting** (pedirle al LLM que redacte o mejore el prompt) | Diseñar el primer prompt de una tarea nueva |

**Cómo lo aplicamos**
- **Los prompts son código.** Se guardan como archivos versionados (por ejemplo, `src/skillnest_app/prompts/`), no como strings dispersos en el código. Cada uno tiene un identificador de versión que queda registrado en cada respuesta (§6).
- **System prompt:** contiene rol, restricciones y formato de salida. **User prompt:** contiene solo los datos de entrada, es decir, la historia de usuario y sus criterios. Esta separación también es una defensa contra *prompt injection* (§7).
- **Few-shot para el JSON estructurado (E6):** uno o dos ejemplos de caso de prueba bien formado reducen las salidas que no cumplen el schema.
- **Prompt chaining en el Módulo 2 (LangChain):** por ejemplo, analizar la historia, luego identificar particiones y al final generar los casos. Cada paso valida su salida antes de pasar al siguiente.
- **Meta prompting** solo para el borrador inicial. El prompt definitivo se valida con el golden set (§2).

---

## 2. Evaluación de respuestas

**Lo que dice el syllabus**
- Métricas: **accuracy, precision, recall, relevance/contextual fit, diversity, execution success rate y time efficiency**.
- Como el LLM no es determinista, las métricas deben basarse en **datos estadísticamente relevantes**: una sola ejecución no prueba nada.
- Formas de refinar un prompt: modificarlo de forma iterativa, comparar versiones (*A/B testing*), analizar los errores de la salida, incorporar feedback del usuario y ajustar el largo y el nivel de detalle.

**Cómo lo aplicamos** (al asistente de diseño de pruebas)

| Métrica | Cómo la medimos aquí | Automatizable |
|---|---|---|
| Execution success rate | % de respuestas que validan contra el schema Pydantic | Sí |
| Recall | % de las particiones esperadas (válidas e inválidas) que cubren los casos generados | Sí, con un golden set anotado |
| Relevance | % de casos que trazan a un criterio de aceptación existente (§6) | Sí |
| Diversity | Distribución por tipo de caso: positivo, negativo, borde, no funcional | Sí |
| Accuracy | Revisión experta contra los casos esperados | Parcial (revisión humana) |

- **Golden set:** de 10 a 20 historias de usuario con sus resultados esperados. Se corre **N veces** por versión de prompt para obtener una tasa, no un resultado puntual.
- **A/B de prompts:** solo se cambia un prompt si la nueva versión mejora las métricas sobre el golden set.
- Estas evaluaciones consumen tokens. Corren bajo demanda (marker `integration` o un script de evaluación), nunca en la suite rápida.

---

## 3. Manejo de contexto

**Lo que dice el syllabus**
- La *context window* se mide en **tokens**. Más contexto implica más costo y más latencia.
- **Dar un contexto completo** reduce las alucinaciones, pero un prompt más largo no siempre es mejor: hay que experimentar con el largo.
- Conviene usar **formatos claros y estructurados** y evitar los ambiguos.
- Para RAG, como punto de partida, se sugieren chunks de 256 a 512 tokens.

**Cómo lo aplicamos**
- **Presupuesto de tokens por petición:** límite máximo para la entrada del usuario y `max_output_tokens` explícito. Ambos se prueban con BVA.
- **Entrada estructurada:** la historia y los criterios se envían con delimitadores claros (por ejemplo, secciones etiquetadas), no como prosa mezclada con las instrucciones.
- **Memoria conversacional (Módulo 2):** una estrategia explícita de recorte (ventana de N turnos o resumen). La memoria nunca crece sin límite.
- **El contexto recuperado por RAG compite con la entrada por el mismo espacio:** `top_k` × tamaño de chunk tiene que caber dentro del presupuesto.

---

## 4. Alucinaciones

**Lo que dice el syllabus**
- Hay tres tipos de defectos:
  - **Alucinación:** contenido incorrecto o inventado.
  - **Error de razonamiento:** lógica, condiciones o cálculos equivocados.
  - **Sesgo:** se favorecen ciertos tipos de información o de enfoque.
- Un defecto puede parecer corregido y **reaparecer en otra ejecución**.
- **Detección:** verificación cruzada contra la fuente, chequeos de consistencia, validación lógica y ejecución de la salida.
- **Mitigación:** contexto completo, prompt chaining, formatos claros, el modelo adecuado y comparar entre modelos.
- **Para reducir la variabilidad:** bajar la `temperature` y fijar un *seed* si el proveedor lo permite.

**Cómo lo aplicamos**

| Defecto | Ejemplo en este proyecto | Defensa |
|---|---|---|
| Alucinación | Un caso de prueba para un criterio de aceptación que no existe | Cada caso referencia el `id` del criterio de origen, y el código **verifica** que ese `id` exista en la entrada |
| Error de razonamiento | El LLM prioriza o cuenta mal | Lo que se puede calcular **lo calcula el código**, no el LLM (conteos, prioridades por regla, totales) |
| Sesgo | Solo casos positivos; faltan los negativos o los no funcionales | Se mide la distribución por tipo (§2), y el prompt exige mínimos por tipo |

- `temperature` baja para la salida estructurada. Hay que verificar en el SDK si Gemini acepta *seed* antes de depender de eso.
- En RAG, la defensa principal es responder **solo con el contexto recuperado** y citar la fuente (§5).

---

## 5. RAG

**Lo que dice el syllabus**
- **Preprocesamiento:** los documentos se dividen en chunks, se limpian, se convierten en embeddings y se guardan en una base vectorial.
- **Inferencia:** la consulta se convierte en embedding, se recuperan los chunks por similitud semántica y la respuesta se genera **fundamentada** en esos chunks.
- **El back end hace post-procesamiento:** ajusta la salida cruda del LLM antes de mostrarla.
- El syllabus sugiere comparar la salida **con y sin RAG** para medir su aporte.

**Cómo lo aplicamos** (Módulo 2)
- **Pipeline separado por etapas** (chunking, embedding, retrieval, generación). Cada etapa es reemplazable y se prueba por separado (ver §5 de las notas de ISTQB Foundation).
- **El chunk es la unidad de trazabilidad:** cada chunk guarda el documento de origen, su posición y un `id`.
- **Prompt de generación:** "responde solo con el contexto; si no está, dilo".
- **Post-procesamiento obligatorio:** validar el schema, verificar que las citas existan y descartar los casos sin respaldo.
- **Experimento de línea base:** el golden set se corre con RAG y sin RAG. Si RAG no mejora las métricas, no se justifica su complejidad.
- **Corpus:** público o sintético, nunca datos confidenciales ni corporativos, porque el repositorio es público.

---

## 6. Trazabilidad

> El syllabus trata la trazabilidad solo de forma indirecta: fundamentación en RAG, revisión de la salida y LLMOps. Esta sección es una **aplicación propia**, basada en el principio de trazabilidad de CTFL (§1.4.4).

Hay cuatro vínculos que deben poder reconstruirse:

| Vínculo | Cómo se implementa |
|---|---|
| Caso generado → criterio de aceptación | Campo de referencia al criterio en el schema de salida, verificado por código (§4) |
| Respuesta → fuente | En RAG: `chunk_id` y documento citados en la respuesta |
| Respuesta → cómo se produjo | Registro por llamada: `interaction id`, modelo, **versión del prompt**, `usage` y latencia |
| Fixture grabada → origen | Metadatos de la grabación: modelo, fecha y versión del prompt usado |

El `id` de la interacción y el `model` ya vienen en la respuesta del proveedor (ver `response.json`). Solo hay que **conservarlos** en `LLMResponse` y no descartarlos en el mapper.

---

## 7. Seguridad

**Lo que dice el syllabus**
- **Riesgos de privacidad:** exposición accidental de datos sensibles, pérdida de control sobre su uso y riesgos de cumplimiento normativo (por ejemplo, GDPR).
- **Vectores de ataque:**
  - *Context manipulation*: sobrecargar la *context window* para extraer datos.
  - *Request manipulation*: entradas que desvían al modelo.
  - *Data poisoning*: contaminar los datos de entrenamiento o de evaluación.
  - Generación de código malicioso.
- **Mitigación:** minimizar los datos, anonimizarlos o seudonimizarlos, almacenarlos y transmitirlos de forma segura, revisar la salida de forma sistemática, comparar entre modelos y elegir un entorno operativo seguro.

**Cómo lo aplicamos**

| Amenaza | Defensa |
|---|---|
| *Prompt injection* directa, en la entrada del usuario | Separar system prompt y user prompt, delimitar la entrada, validar la salida contra el schema y tener casos adversariales en los tests |
| *Prompt injection* indirecta, en documentos del corpus | Tratar el contenido recuperado como **datos, no como instrucciones**, y poner delimitadores en el prompt |
| *Context manipulation* (entrada enorme) | Límite de largo de la entrada antes de llamar al LLM, probado con BVA |
| Salida maliciosa o ejecutable | **Nunca ejecutar** la salida del LLM. Se valida y se muestra como datos |
| Fuga de secretos | `SecretStr`, la key nunca va a los logs, la API no devuelve stack traces y no hay secretos en las fixtures |
| Datos sensibles | Corpus y ejemplos públicos o sintéticos. Minimización: solo se envía al LLM lo necesario |
| *Data poisoning* del golden set | El golden set se versiona en el repositorio y se revisa en cada cambio |

---

## 8. Costos y consumo de tokens

**Lo que dice el syllabus**
- El costo recurrente depende de los tokens de entrada y de salida, del prompt usado y de la frecuencia de la tarea. Debe **estimarse antes** de adoptar un modelo.
- El costo es uno de los criterios para elegir un modelo, junto con su desempeño en la tarea y el soporte disponible.
- **Impacto energético:** el consumo se acumula con el uso. Hay que evitar las interacciones innecesarias con el modelo.

**Cómo lo aplicamos**
- **Evidencia de nuestra propia respuesta grabada:** para "What is the capital of France?" se usaron **8 tokens de entrada, 8 de salida y 60 de *thinking***, sobre un total de 76. El razonamiento interno del modelo consumió casi el 80% del total. Por eso:
  - `TokenUsage` (E1) debe incluir los tokens de *thought* y los de caché, no solo los de entrada y salida.
  - Conviene evaluar si la tarea necesita un modelo de razonamiento o si basta con limitar su presupuesto de *thinking*. Hay que verificar en el SDK cómo se configura.
- **Registrar el `usage` en cada llamada** (§6). Es la base para estimar el costo real: tokens por petición × precio × frecuencia esperada. El precio se toma de la página oficial del proveedor al momento de calcularlo, no de memoria.
- **Los tests no consumen tokens por defecto:** respuestas grabadas en la suite rápida y llamadas reales solo con `-m integration`.
- **El golden set** se corre bajo demanda y con N acotado.
- **Más adelante (Módulo 2):** aprovechar el caché de contexto (la respuesta trae `total_cached_tokens`) para el system prompt y el contexto que se repiten.
