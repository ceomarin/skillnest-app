# OWASP API Security Top 10 aplicado a skillnest-app

> Fuente: *OWASP API Security Top 10 — edición 2023* — https://owasp.org/API-Security/ (edición vigente al 2026-10-09; antes de cada Gate, verificar si se publicó una nueva).
> Resumen propio orientado a la acción: no reproduce el texto original.
> Complementa a [genai-principles.md §7](../genai/genai-principles.md), que cubre los riesgos propios de los LLM (*prompt injection*, fuga de datos).
> Última revisión: 2026-10-09

## Por qué esto importa más en una API generativa

Cada petición a nuestra API **gasta dinero**, porque consume tokens de Gemini, y procesa **texto que no controlamos**: el del usuario, el del modelo y el de los documentos recuperados. Por eso los riesgos de consumo de recursos (API4, API6) y de consumo de APIs de terceros (API10) pesan más aquí que en una API CRUD típica.

| Riesgo | Aplica | Prioridad | Etapa |
|---|---|---|---|
| API4 Consumo de recursos sin límites | Sí | **Crítica** | E4, E6, Módulo 3 |
| API10 Consumo inseguro de APIs | Sí (Gemini y corpus) | **Crítica** | E2–E4, Módulo 2 |
| API8 Configuración insegura | Sí | Alta | Módulo 3 |
| API3 Autorización a nivel de propiedad | Sí | Alta | E6, Módulo 3 |
| API6 Abuso de flujos de negocio | Sí (el flujo de generación) | Alta | Módulo 3 |
| API2 Autenticación rota | Sí, si la API se expone | Media | Módulo 3 |
| API9 Inventario de API deficiente | Sí | Media | Módulo 3 |
| API7 SSRF | Solo si hay herramientas o ingesta desde URLs | Media | Módulo 2 (agentes) |
| API1 Autorización a nivel de objeto | Solo si hay recursos por ID | Media | Módulo 2 (memoria) |
| API5 Autorización a nivel de función | Solo si hay endpoints de administración | Baja | Módulo 3 |

> Los valores numéricos de los ejemplos (largos, límites, cuotas) son **ilustrativos**. Los valores reales se deciden con datos al implementar.

---

## API1 — Broken Object Level Authorization (BOLA)

- **Descripción:** se puede acceder a objetos de otros (una conversación, un documento) cambiando el identificador en la petición.
- **Justificación:** en el Módulo 2, la memoria conversacional introduce recursos con ID (`/conversations/{id}`). Esas conversaciones pueden contener datos de otro usuario.
- **Cómo lo aplicamos:**
  - Cada recurso con ID tiene un dueño (el cliente o la API key).
  - El servicio **verifica la propiedad** en cada acceso, no solo en el router.
  - Los IDs son UUID4, pero un ID difícil de adivinar **no reemplaza** la verificación de propiedad.
- **Ejemplo (test):** el cliente A pide la conversación del cliente B y recibe `404`, no `403`. Así ni siquiera se revela que el recurso existe.

## API2 — Broken Authentication

- **Descripción:** mecanismos de autenticación débiles o mal implementados permiten suplantar a un cliente.
- **Justificación:** una API sin autenticación que llama a Gemini es **un proxy gratuito a tu cuenta**. Cualquiera puede gastar tus tokens.
- **Cómo lo aplicamos** (si la API se expone fuera de localhost, Módulo 3):
  - API key en un header (`APIKeyHeader` de FastAPI), cargada desde el entorno.
  - Comparación en tiempo constante (`secrets.compare_digest`).
  - **Nunca** en un query string, porque termina en los logs.
  - La rotación se hace cambiando la variable de entorno.
- **Ejemplo (test):** petición sin header → `401`; key incorrecta → `401`; la key nunca aparece en los logs.

## API3 — Broken Object Property Level Authorization (BOPLA)

- **Descripción:** se exponen campos que no deberían salir, o se aceptan campos que el cliente no debería poder modificar (*mass assignment*).
- **Justificación:** hay dos casos concretos en este proyecto.
  - **Salida:** devolver la `Interaction` cruda del SDK expondría su `signature`, el paso de *thinking* y metadatos internos.
  - **Entrada:** si el cliente puede mandar `model` o `max_output_tokens`, puede elegir el modelo más caro o anular nuestros límites.
- **Cómo lo aplicamos:**
  - Schemas de entrada y de salida **separados**. La salida se filtra con el tipo de retorno del endpoint.
  - Los schemas de entrada rechazan campos desconocidos (`extra="forbid"`).
  - El modelo y los límites **solo** vienen de la configuración del servidor.
- **Ejemplo:**

  ```python
  class GenerateRequest(BaseModel):
      model_config = ConfigDict(extra="forbid")
      user_story: str = Field(min_length=1, max_length=4000)
  # {"user_story": "...", "model": "gemini-ultra"}  →  422
  ```

## API4 — Unrestricted Resource Consumption

- **Descripción:** sin límites de tamaño, frecuencia o costo, la API puede saturarse o generar gastos inesperados.
- **Justificación:** es **el riesgo más caro del proyecto**. El costo escala con los tokens, y los tokens de *thinking* pueden superar varias veces a los de entrada y salida (ver la evidencia en genai-principles §8).
- **Cómo lo aplicamos**, en capas:

  | Límite | Dónde |
  |---|---|
  | Largo máximo de la entrada | Schema (`max_length`), validado antes de llamar al LLM |
  | `max_output_tokens` y presupuesto de *thinking* | Configuración del adaptador Gemini |
  | Timeout por llamada al LLM | Adaptador (`timeout`) |
  | `top_k` máximo en RAG | Configuración del servidor, no parámetro del cliente |
  | Peticiones por minuto por cliente | Módulo 3 (*rate limiting*) |
  | Presupuesto diario de tokens | Módulo 2 (límites de costo del cliente modular) |

- **Ejemplo (test BVA):** `user_story` con `max_length` caracteres → `200`; con `max_length + 1` → `422`, y **no hubo llamada al LLM**. Esto se verifica con el cliente grabado.

## API5 — Broken Function Level Authorization

- **Descripción:** funciones administrativas accesibles para clientes comunes.
- **Justificación:** es probable que aparezcan endpoints como "reindexar el corpus" o "ver métricas de costo". Reindexar consume tokens de embeddings.
- **Cómo lo aplicamos:**
  - Preferir tareas de administración como procesos puntuales (Twelve-Factor XII) antes que como endpoints.
  - Si existen como endpoints, van en un router separado con su propia dependencia de autorización, **denegado por defecto**.
- **Ejemplo:** `APIRouter(prefix="/admin", dependencies=[Depends(require_admin_key)])`. Test: la key de cliente común en `/admin/reindex` devuelve `403`.

## API6 — Unrestricted Access to Sensitive Business Flows

- **Descripción:** un flujo de negocio legítimo se abusa de forma automatizada.
- **Justificación:** nuestro flujo sensible es **"generar"**. Cada llamada es legítima por separado, pero miles de llamadas automatizadas agotan la cuota o el presupuesto.
- **Cómo lo aplicamos:** además del *rate limiting* técnico (API4), una **cuota de negocio** por cliente (generaciones o tokens por día) y un límite de peticiones concurrentes al LLM.
- **Ejemplo:** al superar la cuota diaria, se responde `429` con `Retry-After` y se registra un evento `quota.exceeded` para detectar el abuso.

## API7 — Server Side Request Forgery (SSRF)

- **Descripción:** el servidor hace peticiones a URLs que alguien manipuló, por ejemplo hacia la red interna.
- **Justificación:** en GenAI, la URL puede venir **del propio modelo**. Un agente con una herramienta tipo "descargar URL", o una ingesta que acepta enlaces, puede ser inducido por *prompt injection* a pedir `http://169.254.169.254/` u otros destinos internos.
- **Cómo lo aplicamos** (solo si existen herramientas o ingesta con URLs):
  - Lista de dominios permitidos.
  - Rechazar IP privadas y de *loopback*, también después de seguir redirecciones.
  - Timeout y tamaño máximo de descarga.
- **Ejemplo (test):** la herramienta recibe `http://localhost:8000/admin` → la rechaza sin hacer la petición.

## API8 — Security Misconfiguration

- **Descripción:** configuraciones inseguras por defecto, errores verbosos, CORS abierto, servicios innecesarios expuestos.
- **Justificación:** el contenedor del Gate 3 queda expuesto frente a los evaluadores, que pueden provocar errores a propósito.
- **Cómo lo aplicamos:**
  - Errores con un formato uniforme, **sin stack traces** ni detalles internos.
  - CORS con lista explícita de orígenes, o desactivado: Streamlit llama a la API desde el servidor, no desde el navegador.
  - El contenedor corre con un usuario sin privilegios (*non-root*).
  - Al arrancar, se registra la configuración efectiva **sin secretos**: proveedor, modelo y límites.
- **Ejemplo:** `LLM_PROVIDER=recorded` en un despliegue real sería un error de configuración silencioso. El log de arranque y `/health` muestran el proveedor activo, así que el error es visible de inmediato.

## API9 — Improper Inventory Management

- **Descripción:** endpoints o versiones olvidadas, sin documentar o expuestos por accidente.
- **Justificación:** los endpoints de depuración que se agregan durante el desarrollo tienden a quedarse.
- **Cómo lo aplicamos:**
  - Prefijo de versión (`/v1`).
  - OpenAPI como inventario oficial, y el README lista los mismos endpoints.
  - Decidir de forma explícita si `/docs` se expone en la demo.
  - Nada de endpoints "temporales".
- **Ejemplo:** un test compara las rutas registradas en `app.routes` con la lista esperada. Un endpoint nuevo sin documentar hace fallar la suite.

## API10 — Unsafe Consumption of APIs

- **Descripción:** se confía ciegamente en las respuestas de APIs de terceros.
- **Justificación:** **Gemini es una API de terceros**, y su salida es tan poco confiable como la entrada de un usuario. En RAG también lo son los documentos recuperados (*prompt injection* indirecta).
- **Cómo lo aplicamos:**
  - Toda respuesta del proveedor pasa por el mapper y la validación de schema.
  - Si la respuesta es inesperada, se lanza `LLMResponseError`; **nunca** se devuelve "vacío" como si fuera válido.
  - Timeouts y manejo explícito de errores (`429`, `5xx`, red).
  - La salida del modelo **nunca se ejecuta** y se presenta como datos.
  - El texto recuperado se trata como datos, no como instrucciones.
- **Ejemplo (test con fixture grabada):** una respuesta sin un paso `model_output` hace que el mapper lance `LLMResponseError`, y la API responde `502` con el error uniforme.

---

## Checklist mínimo por endpoint (antes de cada commit que agregue o modifique uno)

- [ ] Los schemas de entrada y salida están separados, la entrada tiene `extra="forbid"` y hay límites de largo.
- [ ] El tipo de retorno está declarado: no se devuelven objetos del SDK ni campos internos.
- [ ] Los errores del LLM se traducen a respuestas uniformes sin detalles internos.
- [ ] Hay tests de las particiones inválidas y de los bordes, y ninguno llama a la API real.
- [ ] Ningún secreto ni texto sensible llega a los logs.
- [ ] El endpoint está documentado en OpenAPI y en el README.
