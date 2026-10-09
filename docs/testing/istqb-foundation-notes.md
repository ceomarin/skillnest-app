# Notas ISTQB Foundation aplicadas a skillnest-app

> Fuente: ISTQB Certified Tester Foundation Level (CTFL) Syllabus v4.0.1.
> No es un resumen del syllabus: es la selección de lo que **usamos** en este proyecto y **cómo** lo usamos.
> Las secciones de LLM y RAG aplican técnicas de CTFL a un contexto que el syllabus no cubre.
> Última revisión: 2026-10-08

---

## 1. Principios aplicables al proyecto

| Principio | Qué significa aquí | Cómo lo aplicamos |
|---|---|---|
| **El testing muestra la presencia de defectos, no su ausencia** | Que un LLM pase 10 casos no prueba que sea correcto | Los tests reducen el riesgo; no lo eliminan. La demo del Gate 3 usa preguntas que no elegimos nosotros |
| **El testing exhaustivo es imposible** | El lenguaje natural es un espacio de entrada infinito | Elegimos casos con particiones y por riesgo (§2 y §6), no por volumen |
| **Probar temprano ahorra (shift left)** | Un defecto en el prompt o en el schema se propaga a todo lo que se construye después | Cada etapa del plan de implementación define sus tests antes que el código. `ruff`/`mypy` (análisis estático) corren antes que pytest. Los prompts y schemas se revisan como *work products* |
| **Los defectos se agrupan** | Se concentran en las fronteras con sistemas externos | Más tests en el adaptador Gemini, el *parsing* de la salida y el *retrieval* |
| **Los tests se desgastan** | Las respuestas grabadas envejecen cuando cambia el modelo | Re-grabar fixtures al cambiar de modelo. Correr periódicamente los *contract tests* contra la API real. Agregar casos adversariales nuevos |
| **El testing depende del contexto** | Un LLM no es determinista | Las aserciones verifican estructura y propiedades, no texto exacto (§4) |
| **Falacia de la ausencia de defectos** | Pasar todos los tests no garantiza que la app sirva | Además de verificar, validamos utilidad con casos reales del dominio elegido |

---

## 2. Técnicas de diseño de pruebas que utilizaremos

### Equivalence Partitioning (EP)
Se divide cada entrada o salida en particiones y se prueba **un valor por partición**, incluidas las inválidas. El criterio mínimo de cobertura es *Each Choice*: cada partición aparece en al menos un caso de prueba.

| Elemento | Particiones |
|---|---|
| Entrada del usuario | vacía · solo espacios · válida · excesivamente larga · otro idioma · contenido malicioso |
| Respuesta del proveedor | ok · error de cliente 4xx · `429` · error de servidor 5xx · timeout · sin `model_output` · JSON malformado |
| `LLM_PROVIDER` | `recorded` · `gemini` · valor inválido |

### Boundary Value Analysis (BVA)
Se prueba **en los bordes** de las particiones ordenadas, que es donde se concentran los errores *off-by-one*. Se usa la variante de 3 valores (el borde y sus dos vecinos) cuando el borde es crítico.
- Largo máximo de la entrada, tokens máximos de salida.
- Cantidad de reintentos (`attempts` = 0, 1, n) y timeout.
- `top_k` del retrieval, tamaño y solapamiento de los chunks (RAG).

Implementación: `@pytest.mark.parametrize` con un caso por partición o por borde.

### Decision Table Testing
Sirve para la lógica que **combina condiciones**. Ejemplo: la selección del cliente LLM.

| Regla | R1 | R2 | R3 | R4 |
|---|---|---|---|---|
| `provider = gemini` | V | V | F | inválido |
| API key presente | V | F | – | – |
| **Resultado** | `GeminiClient` | error claro | `RecordedGeminiClient` | error claro |

Se usa también para la política de reintentos (tipo de error × intentos restantes → reintentar o fallar).

### State Transition Testing
Se aplica cuando el comportamiento depende del estado: la memoria conversacional (Módulo 2) y el `status` de la interacción (por ejemplo, `completed` frente a una respuesta incompleta con `continuation_token`). El criterio de cobertura es *valid transitions*, más **una** transición inválida por test.

### White-box: Branch Coverage
Se mide con `uv run pytest --cov=skillnest_app --cov-branch`. Es una **medida objetiva para encontrar huecos**, no una meta en sí misma. Prioridad: el adaptador, el mapper y el manejo de errores. La cobertura de ramas incluye la de sentencias.

### Técnicas basadas en experiencia
- **Error guessing / fault attacks:** se mantiene una lista viva de fallas típicas de LLM (ver §4) y se diseña un test para cada una.
- **Exploratory testing por sesiones:** sesiones acotadas en tiempo, con un *charter* (objetivo de la sesión), antes de cada Gate, sobre todo antes de la demo en vivo.
- **Checklist:** para revisar prompts y schemas. Debe ser corto, sin ítems que ya se puedan verificar automáticamente.

### Enfoque colaborativo (ATDD ligero)
El "Listo cuando" de cada etapa funciona como criterios de aceptación y como *Definition of Done*. Se escriben en formato Given/When/Then cuando hay comportamiento de negocio. Orden de los casos: primero positivos, luego negativos y al final no funcionales.

---

## 3. Estrategia de pruebas para APIs (FastAPI, Módulo 3)

### Niveles y pirámide

| Nivel CTFL | Qué probamos | Herramienta | Red real |
|---|---|---|---|
| Component | Servicio y caso de uso con el cliente `recorded` | pytest | No |
| Component integration | Router + validación + servicio, inyectando el cliente `recorded` con `dependency_overrides` | `TestClient` | No |
| System | El contenedor levanta y responde (*smoke test*) | Docker + `/health` | No |
| System integration | Llamada real a Gemini | `-m integration` | **Sí** |

Muchos tests abajo y muy pocos arriba. Los tests de la base corren en cada cambio; los de integración, bajo demanda.

### Diseño de casos
- **EP/BVA sobre el schema de entrada:** Pydantic rechaza la entrada inválida con un `422`. Cada partición inválida tiene su test.
- **Los códigos de estado se tratan como particiones de salida:** `200` · `422` · `429`/`503` (traducidos desde los errores del LLM) · **nunca un `500` sin control**.
- **Contrato de errores consistente:** todos los errores tienen la misma forma, sin *stack traces* ni datos internos.

### No funcionales
- **Reliability:** con el proveedor caído, la API responde con un error controlado y no se cae.
- **Security:** no se filtran secretos en respuestas ni en logs, y la entrada se valida antes de llegar al LLM.
- **Performance efficiency:** timeouts explícitos y medición de latencia por endpoint.

### Regresión
La suite rápida, sin red, es la suite de regresión. Debe correr en CI cuando exista. Ante un cambio, primero se hace un *impact analysis* (qué partes afecta el cambio) para decidir qué más correr.

---

## 4. Estrategia de pruebas para LLMs

**Idea clave:** separar lo determinista de lo no determinista.

| Parte | Naturaleza | Cómo se prueba |
|---|---|---|
| Adaptador, mapper, errores, reintentos, parsing | Determinista | Component tests con **respuestas grabadas** (`RecordedGeminiClient`) |
| Comportamiento del modelo | No determinista | *Contract tests* contra la API real, pocos y bajo demanda |

### Oráculo por propiedades, no por igualdad
Un *test oracle* es la fuente que dice cuál es el resultado esperado. Con un LLM no se compara el texto exacto. Se verifican propiedades:
- valida contra el schema Pydantic;
- los campos obligatorios están presentes y dentro de sus rangos;
- la respuesta no está vacía y está en el idioma esperado;
- no contiene datos prohibidos (secretos, datos personales).

### Contract tests (diseño del plan)
La **misma suite** corre contra `RecordedGeminiClient` y `GeminiClient`. Si las dos pasan, el código intermedio quedó probado con datos reales.

### Regresión de prompts
- El prompt es un *work product* versionado: se revisa (testing estático) antes de cambiarlo.
- Un **golden set** pequeño (conjunto de casos de referencia) de entradas representativas, una por partición del dominio, se corre cuando cambia el prompt o el modelo.

### Lista de error guessing específica de LLM
- Respuesta truncada por límite de tokens.
- JSON envuelto en texto o en bloques ```` ```json ````.
- Campos inventados o faltantes.
- Rechazo por filtros de seguridad (*safety*).
- Cambio de idioma no pedido.
- *Prompt injection* en la entrada del usuario.
- Entrada vacía o fuera del dominio.

### Costo
Los tests reales llevan el marker `integration`, son pocos y registran los tokens consumidos usando el campo `usage` de la respuesta.

---

## 5. Estrategia de pruebas para RAG (Módulo 2)

### Probar cada etapa por separado (component)

| Etapa | Técnica | Ejemplo de caso |
|---|---|---|
| Chunking | BVA | documento vacío · menor que el chunk · exactamente igual · mayor · solapamiento en el límite |
| Embeddings | Fake determinista | en unit tests, los vectores son fijos y no se llama a la API |
| Retrieval | Oráculo conocido | corpus pequeño controlado: la consulta X debe recuperar el chunk Y dentro del top-k |
| Generación | Contexto fijo | dado un contexto conocido, la respuesta solo usa ese contexto |

### Particiones de consulta
- La respuesta está en el corpus.
- **No está en el corpus:** debe reconocerlo, no inventar.
- Ambigua.
- Requiere varios documentos.
- Documentos contradictorios.

### Verificaciones clave
- **Citación verificable:** cada fuente citada existe en los chunks recuperados.
- **Métricas simples sobre el golden set:** *hit rate@k* (fracción de consultas en que el chunk correcto aparece en el top-k) en lugar de una "precisión" difusa.
- **Regresión:** cambiar el tamaño de chunk, el modelo de embeddings o `k` obliga a correr de nuevo el golden set.

### Datos
Corpus público o sintético: nunca datos confidenciales ni corporativos, porque el repositorio es público.

---

## 6. Riesgos de calidad que debemos vigilar

Análisis cualitativo: nivel de riesgo = probabilidad × impacto. Los riesgos de mayor nivel se prueban primero.

| Riesgo | Característica (ISO 25010) | Prob. | Impacto | Mitigación por testing | Etapa |
|---|---|---|---|---|---|
| Caída por error de red, timeout o `429` | Reliability | Alta | **Crítico** (Gate 1) | EP de errores del proveedor, mapeo a errores propios, reintentos | E4 |
| Salida del LLM no parseable | Functional correctness | Alta | Alto | Validación con schema + fixtures inválidas o truncadas | E6 |
| Alucinación | Functional correctness | Alta | Alto | RAG con citas, casos fuera del corpus | Módulo 2 |
| Prompt injection | Security | Media | Alto | Casos adversariales, separación de los prompts de sistema y de usuario | E6 / Módulo 2 |
| Fuga de secretos o datos | Security | Baja | **Crítico** | `SecretStr`, sin key en logs, sin stack traces en la API, corpus sin datos confidenciales | E0 en adelante |
| Fixtures desactualizadas o deriva del modelo | Maintainability | Media | Medio | Contract tests reales periódicos, re-grabar al cambiar de modelo | E3–E4 |
| Costo de tokens descontrolado | (riesgo de proyecto) | Media | Medio | Integración bajo demanda, límites de uso | E7 / Módulo 2 |
| Latencia inaceptable | Performance efficiency | Media | Medio | Timeouts explícitos, medición por endpoint | E4 / Módulo 3 |
| No reproducible en el contenedor | Portability | Media | **Crítico** (Gate 3) | Smoke test sobre la imagen Docker | Módulo 3 |
| Pasa los tests pero no resuelve el problema | (validación) | Media | Alto | Exploratory testing con casos reales del dominio | Antes de cada Gate |

Se actualiza cuando aparece un riesgo nuevo o un defecto real lo confirma (*risk monitoring*).
