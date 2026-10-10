# Prácticas de FastAPI aplicadas a skillnest-app

> Fuente: documentación oficial de FastAPI — https://fastapi.tiangolo.com. FastAPI **no publica una guía oficial titulada "Best Practices"**: estas prácticas se extraen de sus secciones oficiales (*Tutorial – User Guide*, *Advanced User Guide*, *Deployment*). Cuando una práctica no viene de la documentación oficial, se indica como **práctica propia**.
> Resumen propio orientado a la acción: no reproduce el texto original.
> Contexto: FastAPI entra en el **Módulo 3** como un adaptador más sobre el servicio ya construido. Este documento guía ese momento; no adelanta su construcción.
> Última revisión: 2026-10-09

---

## 1. Estructura por routers sobre el layout `src`
- **Descripción:** la app se organiza en un paquete con módulos por funcionalidad (`APIRouter`), un módulo de dependencias compartidas y un `main.py` que ensambla todo.
- **Justificación:** la API es **solo un adaptador HTTP**. La lógica ya vive en `services/`; si se filtra a los routers, se duplica entre la API y Streamlit.
- **Cómo lo aplicamos:** la estructura oficial, adaptada a `src/` y a nuestra regla de dependencias:

  ```
  src/skillnest_app/api/
  ├── main.py           # crea FastAPI(lifespan=...), registra routers y handlers
  ├── dependencies.py   # get_settings, get_llm_client, get_assistant_service
  ├── errors.py         # exception handlers: errores de dominio → HTTP
  ├── schemas.py        # modelos de entrada y salida HTTP
  └── routers/
      ├── health.py
      └── generation.py
  ```

  Los routers **solo** traducen HTTP ↔ servicio: validan, llaman y devuelven. El entrypoint se declara en `pyproject.toml` (`[tool.fastapi] entrypoint = "skillnest_app.api.main:app"`).
- **Ejemplo:** un endpoint de generación tiene unas 5 líneas: recibe `GenerateRequest`, llama a `service.generate(...)` y retorna `GenerateResponse`. Si crece más, la lógica pertenece al servicio.

## 2. Inyección de dependencias con `Depends` + `Annotated`
- **Descripción:** los endpoints declaran lo que necesitan como dependencias tipadas (`Annotated[T, Depends(fn)]`), y FastAPI las resuelve en cada petición.
- **Justificación:** es la misma inyección que usa el servicio con `LLMClient`, ahora en la capa HTTP. Permite que los tests reemplacen el cliente real por el grabado sin tocar el código.
- **Cómo lo aplicamos:** una cadena de dependencias `get_settings → get_llm_client → get_assistant_service`. Se definen alias reutilizables para no repetir la declaración.
- **Ejemplo:**

  ```python
  ServiceDep = Annotated[AssistantService, Depends(get_assistant_service)]


  @router.post("/v1/test-cases")
  def generate(request: GenerateRequest, service: ServiceDep) -> GenerateResponse: ...
  ```

## 3. Configuración con `pydantic-settings` + `lru_cache` + `Depends`
- **Descripción:** la configuración vive en una clase `BaseSettings`, se obtiene con una función cacheada y se entrega como dependencia. No se crea una instancia global.
- **Justificación:** es la recomendación oficial, y **coincide con la E0 del plan**: lo que construyes en el Módulo 1 se reutiliza tal cual en el Módulo 3.
- **Cómo lo aplicamos:** `get_settings()` con `@lru_cache`. Los endpoints la reciben por `Depends`, y los tests la sustituyen con `dependency_overrides`.
- **Ejemplo:** un test cambia el proveedor sin variables de entorno:
  `app.dependency_overrides[get_settings] = lambda: Settings(llm_provider="recorded", _env_file=None)`.

## 4. Recursos compartidos en el `lifespan`
- **Descripción:** lo que se crea una sola vez y se comparte entre peticiones (clientes, modelos cargados) se inicializa en el `lifespan` y se libera al apagar. Los eventos `startup` y `shutdown` están deprecados.
- **Justificación:** el cliente del SDK de Gemini no debe crearse en cada petición, por costo y por conexiones. Tampoco al importar el módulo, porque bloquearía los tests (Twelve-Factor IX).
- **Cómo lo aplicamos:** el `lifespan` construye el `LLMClient` con la factory y lo guarda en `app.state`. `get_llm_client` lo lee desde ahí. Al apagar, se cierra lo que haya que cerrar.
- **Ejemplo:**

  ```python
  @asynccontextmanager
  async def lifespan(app: FastAPI):
      app.state.llm_client = build_llm_client(get_settings())
      yield
      # cierre de recursos, si el cliente lo requiere
  ```

## 5. Schemas de entrada y salida separados; la salida se filtra por el tipo de retorno
- **Descripción:** se declara el tipo de retorno del endpoint (o `response_model`). FastAPI valida y **filtra** la salida para que solo salgan los campos declarados.
- **Justificación:** la documentación oficial destaca este filtrado como un mecanismo de **seguridad**. Es la defensa directa contra API3 (OWASP).
- **Cómo lo aplicamos:**
  - Los schemas HTTP (`api/schemas.py`) son distintos de los modelos de dominio (`llm/models.py`).
  - Nunca se retorna un objeto del SDK.
  - La entrada usa `extra="forbid"` (práctica propia, por API3).
- **Ejemplo:** `GenerateResponse` expone los casos generados y un `request_id`. No expone la `signature`, el paso de *thinking* ni el `usage` crudo; si el `usage` se expone, va resumido y de forma intencional.

## 6. Validación en el borde con restricciones del schema
- **Descripción:** las restricciones (largo, rangos, formatos) se declaran en el schema con `Field`, y una entrada inválida produce un `422` antes de ejecutar el endpoint.
- **Justificación:** una validación que falla **antes** de llamar al LLM no cuesta tokens. Es la primera línea contra API4.
- **Cómo lo aplicamos:** `min_length` y `max_length` en todo texto de entrada. Los límites salen de la configuración y se prueban con BVA.
- **Ejemplo:** `user_story: str = Field(min_length=1, max_length=4000)` → los tests con largo 0, 1, 4000 y 4001 verifican `422 · 200 · 200 · 422`.

## 7. `def` o `async def` según el cliente
- **Descripción:** un endpoint `async def` solo debe hacer `await` de operaciones asíncronas. Si dentro se hace una llamada bloqueante, se congela todo el servidor. Un endpoint `def` corre en un *threadpool* y puede bloquear sin afectar a los demás. La regla oficial: ante la duda, `def`.
- **Justificación:** **el error más fácil de cometer en este proyecto.** Si se llama al cliente síncrono del SDK desde un `async def`, mientras Gemini responde (segundos) el servidor no atiende a nadie más.
- **Cómo lo aplicamos:** el `LLMClient` del plan es síncrono, así que los endpoints que lo usan son `def`. Pasar a asíncrono es una decisión posterior y explícita: el SDK ofrece una variante asíncrona (verificar `client.aio` en el SDK), y adoptarla exige que el `Protocol` también sea asíncrono.
- **Ejemplo:**

  ```python
  @router.post("/v1/test-cases")
  def generate(...):              # ✅ cliente síncrono → def
  async def generate(...):        # ❌ con cliente síncrono bloquea el event loop
  ```

## 8. Errores de dominio → respuestas HTTP uniformes
- **Descripción:** las excepciones propias se registran con `@app.exception_handler`, que las traduce a respuestas HTTP. La documentación oficial advierte que no deben exponerse detalles internos en los errores.
- **Justificación:** el criterio crítico del Gate 1 ("sin caídas") se convierte en el Gate 3 en "ningún `500` sin control".
- **Cómo lo aplicamos:** un handler por familia de `LLMError`, con un formato de error único (`{"error": {"code": ..., "message": ..., "request_id": ...}}`). La elección del código HTTP (práctica propia, según la semántica HTTP):

  | Error de dominio | HTTP | Por qué |
  |---|---|---|
  | `LLMRateLimitError` | `503` + `Retry-After` | El que excedió la cuota fue **nuestro proveedor**, no el cliente; `429` culparía al cliente |
  | `LLMTimeoutError` | `504` | El servicio del que dependemos no respondió a tiempo |
  | `LLMResponseError` | `502` | El servicio del que dependemos respondió algo inválido |
  | `LLMProviderError` | `502` | Falla del proveedor |
  | Cuota propia excedida (API6) | `429` | Aquí **sí** fue el cliente |

- **Ejemplo (test):** el cliente grabado se configura para lanzar `LLMTimeoutError` → la respuesta es `504` con el formato uniforme, sin stack trace y con `request_id`.

## 9. Testing con `TestClient` y `dependency_overrides`
- **Descripción:** `TestClient` ejecuta la app en el mismo proceso, sin servidor. `dependency_overrides` reemplaza dependencias solo durante los tests.
- **Justificación:** permite probar la capa HTTP completa (validación, serialización, errores) con el cliente grabado, sin red y sin tokens.
- **Cómo lo aplicamos:**
  - Una fixture de pytest instala el override del `LLMClient` con `RecordedGeminiClient` y **limpia los overrides al terminar**, para que un test no contamine a otro.
  - Estos tests son de nivel *component integration* (ver istqb-foundation-notes §3).
- **Ejemplo:**

  ```python
  @pytest.fixture
  def client(recorded_llm_client):
      app.dependency_overrides[get_llm_client] = lambda: recorded_llm_client
      yield TestClient(app)
      app.dependency_overrides.clear()
  ```

## 10. OpenAPI como contrato documentado
- **Descripción:** FastAPI genera OpenAPI a partir de los tipos. Con `tags`, `summary` y `responses` se documentan también los errores.
- **Justificación:** el Gate 3 exige un README con ejemplos reales de cada endpoint, y OpenAPI es el inventario oficial (API9).
- **Cómo lo aplicamos:**
  - Cada router declara sus `tags` y sus `responses` de error (`502`, `503`, `504`).
  - Los ejemplos del README se validan contra el schema real.
  - Se decide de forma explícita si `/docs` queda activo en la demo.
- **Ejemplo:** `@router.post(..., responses={503: {"model": ErrorResponse, "description": "Proveedor LLM saturado"}})`.

## 11. Endpoint de salud que no consume tokens *(práctica propia)*
- **Descripción:** `/health` responde si el proceso está vivo y muestra la configuración efectiva, sin secretos y **sin llamar al LLM**.
- **Justificación:** Docker (`HEALTHCHECK`) y los evaluadores lo consultan seguido. Si llamara a Gemini, cada chequeo gastaría tokens. Además, hace visible la configuración incorrecta descrita en API8 (proveedor `recorded` activo).
- **Cómo lo aplicamos:** devuelve `{"status": "ok", "provider": "...", "model": "..."}`. Si hace falta comprobar el proveedor de verdad, eso es un chequeo aparte, manual o bajo demanda.
- **Ejemplo:** `HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"`.

## 12. Despliegue en contenedor
- **Descripción:** recomendaciones oficiales para Docker:
  - partir de una imagen oficial de Python;
  - copiar primero la definición de dependencias, para aprovechar la caché de capas;
  - usar `CMD` en forma *exec* (si no, el apagado ordenado y el `lifespan` no funcionan bien);
  - un proceso por contenedor si un orquestador replica;
  - usar `fastapi run`;
  - agregar `--proxy-headers` si hay un proxy TLS delante.
- **Justificación:** el contenedor del Gate 3 debe levantarse con un comando y apagarse limpio frente a los evaluadores.
- **Cómo lo aplicamos:** la guía oficial usa `pip` + `requirements.txt`; nosotros lo **adaptamos a uv** (la fuente de verdad es `uv.lock`).
  1. Copiar `pyproject.toml` y `uv.lock`.
  2. Instalar las dependencias sin el proyecto, para cachear esa capa.
  3. Copiar `src/`.
  4. Instalar el proyecto.
  5. Ejecutar como usuario sin privilegios.

  *(Verificar al implementar: el patrón exacto en la guía oficial de uv para Docker, y que el comando `fastapi run` esté disponible. Ese comando lo provee `fastapi-cli`, incluido en el extra `fastapi[standard]`; hoy el proyecto declara `fastapi` sin extras.)*
- **Ejemplo (estructura, no definitivo):**

  ```dockerfile
  FROM python:3.12-slim
  # ... instalar uv ...
  COPY pyproject.toml uv.lock ./
  RUN uv sync --frozen --no-dev --no-install-project   # capa cacheable
  COPY src/ ./src/
  RUN uv sync --frozen --no-dev
  USER app
  CMD ["fastapi", "run", "src/skillnest_app/api/main.py", "--port", "8000"]
  ```
