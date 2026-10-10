# Ingeniería en Python aplicada a skillnest-app (PEP 8 y PEP 20)

> Fuentes: *PEP 8 – Style Guide for Python Code* — https://peps.python.org/pep-0008/ · *PEP 20 – The Zen of Python* — https://peps.python.org/pep-0020/ (también disponible con `python -c "import this"`).
> Resumen propio orientado a la acción: no reproduce el texto original.
> Última revisión: 2026-10-09

**Regla general:** lo que una herramienta puede verificar, lo verifica la herramienta (§3). La revisión humana se reserva para lo que ninguna herramienta detecta: diseño, nombres con sentido y manejo de errores.

---

## 1. PEP 8 — Estilo y convenciones

### 1.1 Consistencia con criterio
- **Descripción:** la legibilidad manda. La consistencia dentro del proyecto pesa más que seguir una regla al pie de la letra, y una regla se puede romper si empeora la claridad.
- **Justificación:** el código se lee muchas más veces de lo que se escribe, y en el Gate 3 los evaluadores van a leer tu código en vivo.
- **Cómo lo aplicamos:** `ruff format` define el estilo y nadie lo discute. Largo de línea: 88, el valor por defecto de ruff, dentro del margen que PEP 8 permite acordar en un equipo. Una excepción se justifica con un comentario.
- **Ejemplo:** `uv run ruff format .` antes de cada commit. Cuando exista CI, `ruff format --check` hace fallar el pipeline si alguien no formateó.

### 1.2 Imports agrupados y absolutos
- **Descripción:** imports al inicio del archivo, en tres grupos: biblioteca estándar, terceros y propios. Se prefieren los imports absolutos y se evitan los comodines (`*`).
- **Justificación:** de un vistazo sabes de qué depende cada módulo. Eso permite verificar la regla de dependencias del plan: `services` nunca importa de `llm/gemini/`.
- **Cómo lo aplicamos:** imports absolutos desde el paquete (`from skillnest_app.llm.base import LLMClient`), ordenados por ruff (regla `I`). La documentación de FastAPI usa imports relativos; nosotros elegimos absolutos para tener **una sola forma** en todo el proyecto (PEP 20).
- **Ejemplo:**

  ```python
  import json
  from pathlib import Path

  from google.genai.interactions import Interaction

  from skillnest_app.llm.errors import LLMResponseError
  from skillnest_app.llm.models import LLMResponse
  ```

### 1.3 Convenciones de nombres
- **Descripción:** clases en `CapWords` (las siglas completas en mayúscula), funciones y variables en `snake_case`, constantes en `MAYÚSCULAS`, excepciones con sufijo `Error`.
- **Justificación:** el nombre comunica qué tipo de cosa es sin tener que abrir su definición.
- **Cómo lo aplicamos:** ruff (regla `N`) lo verifica. Las siglas van completas: `LLMClient`, `LLMRateLimitError`, `HTTPError`; no `LlmClient`.
- **Ejemplo:** `RESPONSE_FIXTURE_PATH` (constante), `to_llm_response()` (función), `RecordedGeminiClient` (clase), `LLMTimeoutError` (excepción).

### 1.4 Interfaz pública e interna
- **Descripción:** lo interno lleva `_` como prefijo. La API pública de un paquete se declara de forma explícita, por ejemplo con `__all__`.
- **Justificación:** sin esa frontera, cualquier módulo termina importando detalles internos del adaptador, y cambiar de proveedor deja de ser barato.
- **Cómo lo aplicamos:**
  - `skillnest_app/llm/__init__.py` exporta solo el contrato: `LLMClient`, los modelos y los errores.
  - Las funciones auxiliares del mapper son privadas (`_extract_text`).
  - Lo que no está en `__all__` se considera interno.
- **Ejemplo:** el servicio hace `from skillnest_app.llm import LLMClient, LLMResponse`. Un `from skillnest_app.llm.gemini.mapper import _extract_text` fuera de su paquete es una señal de alerta en la revisión.

### 1.5 Excepciones: jerarquía propia, captura específica y encadenamiento
- **Descripción:**
  - Las excepciones propias heredan de `Exception`.
  - Se capturan tipos específicos, nunca con `except:` desnudo.
  - El bloque `try` se mantiene mínimo.
  - Al traducir una excepción se encadena con `raise ... from ...`.
- **Justificación:** es el corazón del criterio crítico del Gate 1: manejar los errores de red y los *rate limits* sin caídas. Además, el encadenamiento conserva la causa original para depurar.
- **Cómo lo aplicamos:**
  - `LLMError(Exception)` es la raíz, y de ella heredan `LLMRateLimitError`, `LLMTimeoutError`, `LLMProviderError` y `LLMResponseError`.
  - El adaptador **traduce** las excepciones del SDK a las propias, siempre con `from err`.
  - Ruff detecta `except` sin tipo (`E722`), capturas demasiado amplias (`BLE`) y `raise` sin `from` dentro de un `except` (`B904`).
- **Ejemplo:**

  ```python
  try:
      interaction = self._client.interactions.create(...)
  except errors.ClientError as err:  # captura específica, try mínimo
      if err.code == 429:
          raise LLMRateLimitError("Gemini rate limit") from err
      raise LLMProviderError(str(err)) from err
  ```

  *(Verificar en E4 los atributos exactos de `ClientError` en el SDK.)*

### 1.6 Comparaciones con `None` y valores *falsy*
- **Descripción:** se compara con `is None` / `is not None`. No se usa `if x:` cuando lo que importa es si el valor existe, porque `0`, `""` y `[]` también son falsos.
- **Justificación:** en este proyecto **es un bug real esperando ocurrir**. Nuestra respuesta grabada trae `total_cached_tokens: 0`.
- **Cómo lo aplicamos:** los campos opcionales del `usage` (D1 del plan) se tratan con `is None`. Ruff verifica las comparaciones directas con `None` y con booleanos (`E711`, `E712`).
- **Ejemplo:**

  ```python
  if usage.cached_tokens:              # ❌ 0 y None se tratan igual
  if usage.cached_tokens is not None:  # ✅ 0 es un dato válido
  ```

### 1.7 Recursos con `with` y retornos consistentes
- **Descripción:**
  - Los recursos (archivos, clientes HTTP) se gestionan con `with` o con un mecanismo equivalente que garantice su cierre.
  - Una función o siempre retorna un valor o nunca lo hace; si alguna rama no tiene valor, retorna `None` de forma explícita.
- **Justificación:** las conexiones abiertas son un problema típico de los servicios de larga vida. Los retornos implícitos ocultan ramas olvidadas.
- **Cómo lo aplicamos:** `Path.read_text()` para archivos pequeños. El cliente del SDK se crea y se cierra en el `lifespan` de FastAPI. El mapper nunca "cae" al final sin retornar: o retorna `LLMResponse` o lanza un error.
- **Ejemplo:** si el mapper no encuentra un `model_output`, lanza `LLMResponseError`. No retorna `None` implícito.

---

## 2. PEP 20 — Principios de diseño

### 2.1 Explícito mejor que implícito (*Explicit is better than implicit*)
- **Descripción:** el comportamiento importante debe verse en el código, no ocurrir por efectos colaterales.
- **Justificación:** el `settings.py` original cargaba `.env` y fallaba **al importarse**. Era un efecto implícito que bloqueaba los tests.
- **Cómo lo aplicamos:** las dependencias se inyectan (el servicio recibe un `LLMClient`), no hay efectos al importar, los timeouts son explícitos y los valores por defecto están documentados.
- **Ejemplo:** `AssistantService(llm=client)` en lugar de un servicio que crea internamente su propio cliente de Gemini.

### 2.2 Simple mejor que complejo, complejo mejor que complicado (*Simple is better than complex*)
- **Descripción:** la solución más simple que resuelve el problema. Si la complejidad es inevitable, que sea ordenada.
- **Justificación:** es la versión de PEP 20 de YAGNI, que la visión declara como principio no negociable.
- **Cómo lo aplicamos:** un `Protocol` con un método antes que una jerarquía de clases abstractas. Una función pura (el mapper) antes que una clase. LangChain recién en el Módulo 2, cuando la orquestación lo justifique.
- **Ejemplo:** `LLMClient` es un `Protocol` con un solo método, `generate()`. No hay `BaseLLMClientFactoryProvider`.

### 2.3 Plano mejor que anidado (*Flat is better than nested*)
- **Descripción:** se evitan los niveles profundos de anidamiento.
- **Justificación:** recorrer una respuesta JSON del LLM invita a escribir `if` dentro de `for` dentro de `if`.
- **Cómo lo aplicamos:** *guard clauses* (validar y salir temprano) y helpers pequeños. Ruff (`SIM`) sugiere simplificaciones.
- **Ejemplo:**

  ```python
  outputs = [s for s in interaction.steps if s.type == "model_output"]
  if not outputs:
      raise LLMResponseError("no model_output step")
  ```

### 2.4 La legibilidad cuenta (*Readability counts*)
- **Descripción:** se escribe para quien lee.
- **Justificación:** en la defensa del Gate 3 te pueden pedir que expliques cualquier fragmento del código.
- **Cómo lo aplicamos:** nombres que describen la intención, funciones cortas, *type hints* en todas las firmas públicas (verificados con mypy) y docstrings solo donde el *por qué* no sea obvio.
- **Ejemplo:** `def to_llm_response(interaction: Interaction) -> LLMResponse:` se entiende sin leer el cuerpo.

### 2.5 Los errores nunca deben pasar en silencio (*Errors should never pass silently*)
- **Descripción:** un error se maneja o se propaga. Si se silencia, tiene que ser de forma explícita y visible.
- **Justificación:** con un LLM, un error silenciado se ve como una "respuesta vacía" que el usuario cree válida. Es una alucinación causada por nuestro propio código.
- **Cómo lo aplicamos:** prohibido `except Exception: pass`. Toda alternativa de respaldo (*fallback*) se registra en los logs con su causa. Ruff detecta los `try`/`except`/`pass` (`S110`) y las capturas demasiado amplias (`BLE`).
- **Ejemplo:** si un reintento tiene éxito después de un `429`, se registra un evento `llm.retry` con el intento y la espera. El error no desaparece del registro.

### 2.6 Ante la ambigüedad, no adivinar (*In the face of ambiguity, refuse the temptation to guess*)
- **Descripción:** si los datos no son claros, se falla de forma explícita en lugar de suponer.
- **Justificación:** el `status` de una interacción puede no ser `completed` (por ejemplo, una respuesta incompleta con `continuation_token`). Suponer que es texto válido produce salidas truncadas.
- **Cómo lo aplicamos:** el mapper solo acepta los estados conocidos. Uno desconocido o incompleto lanza un error tipado que el servicio decide cómo tratar.
- **Ejemplo:** `status != "completed"` → `LLMResponseError(f"unexpected status: {status}")`, y queda un test con una fixture de ese caso.

### 2.7 Una forma obvia de hacerlo (*There should be one obvious way to do it*)
- **Descripción:** para cada necesidad, una sola forma estándar dentro del proyecto.
- **Justificación:** dos formas de leer la configuración o de llamar al LLM terminan divergiendo, y una de las dos queda sin probar.
- **Cómo lo aplicamos:** una sola forma de obtener la configuración (`get_settings()`), de llamar al modelo (`LLMClient`), de gestionar dependencias (uv) y de importar (absoluto).
- **Ejemplo:** ningún módulo usa `os.getenv` directamente. Todo pasa por `Settings`.

### 2.8 Si es difícil de explicar, es mala idea (*If the implementation is hard to explain, it's a bad idea*)
- **Descripción:** la dificultad para explicar un diseño es una señal de alerta.
- **Justificación:** es la heurística de nuestra revisión antes de cada commit.
- **Cómo lo aplicamos:** si no puedes explicar en dos frases por qué existe una clase o una capa, se simplifica antes de commitear.
- **Ejemplo:** "¿Por qué existe `RecordedGeminiClient`?" → "Para probar todo el backend con respuestas reales sin depender de la red". Se explica en una frase, así que el diseño pasa la revisión.

### 2.9 Los namespaces son una gran idea (*Namespaces are one honking great idea*)
- **Descripción:** se organiza el código en espacios con nombre que agrupan lo relacionado.
- **Justificación:** los cajones de sastre (`utils.py`, `helpers.py`) crecen sin dueño y acoplan todo con todo.
- **Cómo lo aplicamos:** paquetes por responsabilidad (`config/`, `llm/`, `llm/gemini/`, `services/`, luego `api/` y `admin/`). No existe un `utils.py` genérico.
- **Ejemplo:** una función para contar tokens va en `llm/`, no en `utils.py`.

### 2.10 Ahora mejor que nunca, pero nunca mejor que *ya mismo* (*Now is better than never*)
- **Descripción:** avanzar en iteraciones, sin construir antes de tiempo.
- **Justificación:** es la tensión del proyecto: llegar a cada Gate sin sobreconstruir.
- **Cómo lo aplicamos:** una etapa del plan a la vez, cada una con tests y commit. FastAPI, Docker y LangChain entran cuando su etapa llega.
- **Ejemplo:** `api/` no se crea durante el Módulo 1, aunque ya sepamos que existirá.

---

## 3. Herramientas que hacen cumplir estos principios

Propuesta para incorporar en `pyproject.toml` (en E0):

```toml
[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = [
  "E", "W",  # pycodestyle: estilo PEP 8
  "F",       # pyflakes: nombres sin usar o no definidos
  "I",       # isort: orden de imports (1.2)
  "N",       # pep8-naming: convenciones de nombres (1.3)
  "B",       # bugbear: errores comunes, incluye B904 (1.5)
  "UP",      # pyupgrade: sintaxis moderna para 3.12
  "SIM",     # simplify: código más plano (2.3)
  "S",       # bandit: seguridad, por ejemplo secretos en el código
  "BLE",     # except demasiado amplio (2.5)
  "RUF",     # reglas propias de ruff
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]  # assert es el mecanismo de pytest

[tool.ruff.lint.isort]
known-first-party = ["skillnest_app"]

[tool.mypy]
strict = true
plugins = ["pydantic.mypy"]
```

| Comando | Cuándo |
|---|---|
| `uv run ruff format .` | Antes de cada commit |
| `uv run ruff check .` | Antes de cada commit (con `--fix` para lo automático) |
| `uv run mypy src` | Antes de cada commit |
| `pre-commit` | Cuando se configure: ejecuta los tres de forma automática |
