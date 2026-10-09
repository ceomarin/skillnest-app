# Twelve-Factor App aplicado a skillnest-app

> Fuente: *The Twelve-Factor App*, Adam Wiggins — https://12factor.net (última actualización del original: 2017).
> Resumen propio orientado a la acción: no reproduce el texto original.
> Última revisión: 2026-10-09

## Mapa rápido

| Factor | Prioridad | Dónde se materializa |
|---|---|---|
| III Config | **Crítica** | E0 (Settings) |
| IV Backing services | **Crítica** | E3–E5 (`LLMClient` + factory), Módulo 2 (base vectorial) |
| XI Logs | Alta | E7 / Módulo 2 (observabilidad) |
| X Dev/prod parity | Alta | E4 (contract tests), Módulo 3 (Docker) |
| II Dependencies | Alta | Ya vigente (uv) |
| V Build, release, run | Alta | Módulo 3 (Docker), entrega de cada Gate |
| VI Processes | Alta | Módulo 2 (memoria conversacional) |
| IX Disposability | Media | Módulo 3 (lifespan, apagado ordenado) |
| VII Port binding | Media | Módulo 3 (FastAPI) |
| XII Admin processes | Media | Módulo 2 (ingesta del corpus, evaluación) |
| I Codebase | Media | Ya vigente |
| VIII Concurrency | Baja | Módulo 3 |

---

## I. Codebase — un repositorio, muchos despliegues

- **Descripción:** una sola base de código versionada. Cada entorno (local, contenedor, demo) es un despliegue de ese mismo código.
- **Justificación:** el Gate 3 evalúa una versión etiquetada del repositorio. Si hay código que vive fuera del repo, la evaluación no es reproducible.
- **Cómo lo aplicamos:**
  - El backend, la UI de Streamlit y los scripts de administración viven en el mismo repositorio.
  - `.development/` es material personal, no forma parte de la aplicación.
  - Nada que la app necesite para ejecutarse puede depender de `.development/`.
- **Ejemplo:** las fixtures que usan los tests van en `tests/fixtures/`, no se leen desde `.development/pruebas/`. Si los tests apuntan a una carpeta ignorada, fallan apenas alguien clona el repo.

## II. Dependencies — declarar y aislar

- **Descripción:** todas las dependencias se declaran de forma explícita y se instalan en un entorno aislado, sin depender de nada instalado globalmente.
- **Justificación:** el Gate 1 exige un entorno reproducible y el Gate 3 una imagen que se levanta con un solo comando.
- **Cómo lo aplicamos:**
  - `pyproject.toml` + `uv.lock` son la única fuente de verdad.
  - `requirements*.txt` se generan desde el lock.
  - Ninguna herramienta del sistema (por ejemplo `curl` o `jq`) es requisito para ejecutar la app.
- **Ejemplo:** en el Dockerfile, `uv sync --frozen` falla si el lock no coincide con `pyproject.toml`. Así una dependencia no declarada se descubre en el build, no en la demo.

## III. Config — la configuración vive en el entorno

- **Descripción:** todo lo que cambia entre despliegues (credenciales, proveedor, URLs, límites) se lee de variables de entorno, nunca del código.
- **Justificación:** el repositorio es público. Una prueba rápida: si hoy hicieras público el código, ¿quedaría expuesta alguna credencial?
- **Cómo lo aplicamos:**
  - `Settings` tipados con `pydantic-settings`. `.env` solo existe en local y `.env.example` documenta cada variable sin valores reales.
  - **Distinción clave para GenAI:**

    | Es configuración (entorno) | Es código (versionado) |
    |---|---|
    | API key, proveedor, nombre del modelo, timeouts, límites | Prompts, parámetros de generación (`temperature`), schemas de salida |

    Los prompts y los parámetros de generación determinan la calidad de la salida y se validan con el golden set. Por eso se versionan con el código y no se cambian por entorno.
- **Ejemplo:** el mismo código corre con datos grabados o con la API real cambiando solo el entorno:

  ```bash
  LLM_PROVIDER=recorded uv run skillnest-app "..."   # sin red, sin costo
  LLM_PROVIDER=gemini   uv run skillnest-app "..."   # API real
  ```

## IV. Backing services — los servicios externos son recursos acoplables

- **Descripción:** los servicios externos (el LLM, la base vectorial, un caché) se tratan como recursos que se conectan por configuración y se pueden reemplazar sin tocar el código.
- **Justificación:** es la base del diseño `LLMClient` + factory. Además, la visión exige que cambiar de proveedor no cambie la arquitectura.
- **Cómo lo aplicamos:**
  - El núcleo depende de interfaces (`LLMClient`; en el Módulo 2, una interfaz para el vector store).
  - Qué implementación concreta se usa lo decide la configuración.
  - Solo los adaptadores conocen el SDK de cada proveedor.
- **Ejemplo:** en el Módulo 2, cambiar la base vectorial local por una remota es cambiar una variable de entorno (por ejemplo `VECTOR_STORE_URL`), no reescribir el servicio de RAG.

## V. Build, release, run — etapas separadas

- **Descripción:** *build* produce el artefacto, *release* lo combina con la configuración de un entorno y *run* lo ejecuta. El código no se modifica en ejecución.
- **Justificación:** en el Gate 3 se evalúa una versión etiquetada que debe levantarse "sin pasos manuales adicionales ni configuración de último minuto".
- **Cómo lo aplicamos:**
  - **Build:** imagen Docker construida desde el lock.
  - **Release:** imagen + `--env-file`, identificada por un tag de git y de imagen (`gate-1`, `gate-2`, `gate-3`).
  - **Run:** `docker run`. Nunca se edita código dentro del contenedor.
- **Ejemplo:**

  ```bash
  git tag gate-3 && docker build -t skillnest-app:gate-3 .
  docker run --env-file .env -p 8000:8000 skillnest-app:gate-3
  ```

## VI. Processes — procesos sin estado

- **Descripción:** cada proceso no guarda estado entre peticiones. Lo que tenga que persistir va a un servicio externo (IV).
- **Justificación:** la memoria conversacional (Módulo 2) es la trampa típica. Si vive en un diccionario dentro del proceso, se pierde al reiniciar y no se comparte entre réplicas.
- **Cómo lo aplicamos:**
  - La memoria conversacional se guarda detrás de una interfaz. Si se persiste o no se decide en el Módulo 2, pero nunca queda como estado global del módulo.
  - El `session_state` de Streamlit sirve solo para estado de la UI.
- **Ejemplo:**

  ```python
  # ❌ Estado global: se pierde al reiniciar y no escala
  conversations: dict[str, list[str]] = {}

  # ✅ Interfaz inyectada; la implementación decide dónde persiste
  class ConversationStore(Protocol):
      def append(self, conversation_id: str, message: Message) -> None: ...
  ```

## VII. Port binding — el servicio expone su propio puerto

- **Descripción:** la app es autocontenida: levanta su propio servidor HTTP en un puerto que llega por configuración.
- **Justificación:** el contenedor del Gate 3 debe responder sin infraestructura extra.
- **Cómo lo aplicamos:**
  - FastAPI se ejecuta con `fastapi run` en un puerto configurable.
  - En el Módulo 3, Streamlit consume la API como un servicio externo más, por una URL configurable (`API_BASE_URL`).
- **Ejemplo:** `CMD ["fastapi", "run", "src/skillnest_app/api/main.py", "--port", "8000"]`.

## VIII. Concurrency — escalar con procesos

- **Descripción:** se escala agregando procesos o contenedores, no agrandando un único proceso.
- **Justificación:** la guía oficial de FastAPI para contenedores recomienda un proceso por contenedor y dejar la replicación al orquestador.
- **Cómo lo aplicamos:**
  - Un proceso por contenedor.
  - Las tareas pesadas, como la ingesta del corpus, son procesos aparte (XII), no hilos dentro de la API.
- **Ejemplo:** la ingesta se ejecuta como `docker run ... python -m skillnest_app.admin.ingest`, no como un endpoint que bloquea el servidor varios minutos.

## IX. Disposability — arranque rápido y apagado ordenado

- **Descripción:** el proceso arranca rápido, se apaga limpio y tolera que lo maten de golpe.
- **Justificación:** en la demo el contenedor se levanta frente a los evaluadores. Una petición al LLM colgada no debe impedir que se detenga.
- **Cómo lo aplicamos:**
  - Nada pesado al importar los módulos. Los recursos compartidos, como el cliente del SDK, se crean en el `lifespan`.
  - Todas las llamadas al LLM tienen timeout.
  - El `CMD` usa forma *exec* para que el proceso reciba las señales de apagado.
  - La ingesta es idempotente: re-ejecutarla no duplica datos.
- **Ejemplo:** la ingesta identifica cada documento por el hash de su contenido. Si se interrumpe a la mitad, re-ejecutarla solo procesa lo que falta.

## X. Dev/prod parity — entornos lo más parecidos posible

- **Descripción:** reducir las diferencias de versiones, herramientas y servicios entre el desarrollo y la ejecución real.
- **Justificación:** "funciona en mi máquina" no basta en el Gate 3.
- **Cómo lo aplicamos:**
  - **Misma versión de Python:** `.python-version` (3.12) y la imagen base (`python:3.12-slim`) deben coincidir.
  - **Mismo lock** en local y en la imagen.
  - **Mismo tipo de backing service** en local y en el contenedor; por ejemplo, el mismo motor vectorial.
  - **Brecha deliberada:** `RecordedGeminiClient` difiere de la API real. Esa brecha se cierra con contract tests contra la API real (`-m integration`).
- **Ejemplo:** la guía de Docker de FastAPI usa una imagen de Python más nueva en su ejemplo. Nosotros fijamos la imagen en 3.12 para mantener la paridad con `.python-version`.

## XI. Logs — los logs son flujos de eventos

- **Descripción:** la app escribe eventos en `stdout` y el entorno decide qué hacer con ellos. La app no maneja archivos de log.
- **Justificación:** el Gate 2 exige logging estructurado y cálculo de costos. Los logs son la fuente de la trazabilidad (`interaction_id`, `usage`).
- **Cómo lo aplicamos:**
  - Un evento JSON por línea.
  - Campos estándar: `event`, `request_id`, `interaction_id`, `model`, `prompt_version`, tokens (entrada, salida, *thinking*, caché) y `latency_ms`.
  - **Nunca** se registran la API key ni el texto completo del usuario si puede contener datos sensibles; en su lugar, su largo o un hash.
- **Ejemplo:**

  ```json
  {"event":"llm.call","request_id":"7f3a…","interaction_id":"v1_Chd…","model":"gemini-3.8-flash","prompt_version":"test-design@1","tokens":{"in":8,"out":8,"thought":60,"cached":0},"latency_ms":1840}
  ```

## XII. Admin processes — tareas de administración como procesos puntuales

- **Descripción:** las tareas de mantenimiento corren como procesos de una sola ejecución, con el mismo código, configuración y dependencias que la app.
- **Justificación:** el proyecto tiene varias de estas tareas: ingestar el corpus, re-grabar fixtures, correr el golden set y estimar costos. Si son scripts sueltos, quedan desincronizados de la app.
- **Cómo lo aplicamos:** módulos dentro del paquete (por ejemplo `skillnest_app/admin/`), ejecutados con `uv run python -m ...` en local o con `docker run ... python -m ...` en la imagen.
- **Ejemplo:**

  ```bash
  uv run python -m skillnest_app.admin.record_fixture --prompt test-design@1
  uv run python -m skillnest_app.admin.eval_golden_set --runs 5
  ```
