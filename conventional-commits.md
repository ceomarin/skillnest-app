# Conventional Commits — Guía práctica

> Los **ejemplos de commits están en inglés** (así se usan en la práctica) y las **explicaciones en español**.

---

## 1. ¿Qué son los Conventional Commits?

Es una **convención para escribir mensajes de commit** con un formato fijo. En vez de escribir cualquier cosa ("arreglos", "cambios varios", "listo"), todos los commits siguen la misma estructura.

**¿Para qué sirve?**

- El historial del proyecto se lee fácil: con solo mirar el título sabes qué tipo de cambio es.
- Se pueden **generar changelogs automáticos** (lista de cambios por versión).
- Se pueden **calcular versiones automáticamente** (Semantic Versioning).
- Todo el equipo escribe igual, sin depender de la memoria o el gusto de cada persona.

---

## 2. Formato general

Un commit tiene hasta 3 partes, separadas por **una línea en blanco**:

```
<type>(<scope>): <description>      ← título (obligatorio)

<body>                              ← cuerpo (opcional)

<footer>                            ← footer (opcional)
```

| Parte | ¿Obligatoria? | Qué contiene |
|---|---|---|
| `type` | Sí | El tipo de cambio (`feat`, `fix`, `docs`...) |
| `scope` | No | La zona del proyecto afectada, entre paréntesis |
| `description` | Sí | Resumen corto del cambio |
| `body` | No | Explicación del **qué** y el **porqué** |
| `footer` | No | Metadatos: issues, coautores, breaking changes |

### Reglas para el título

- Usa **verbo en imperativo**: `add`, `fix`, `update` (no `added`, `fixes`, `updating`).
- Escríbelo en **minúscula**.
- **Sin punto final**.
- Idealmente **máximo ~50 caracteres** (72 como límite duro).
- Debe completar la frase: *"Este commit va a... ___"*.

### Cuerpo (body)

Texto libre que explica **qué cambió y por qué**. El título dice *qué hiciste*; el cuerpo da el contexto que no cabe en una línea.

**Cuándo usarlo:** cuando el cambio no es obvio, se tomó una decisión importante, o alguien necesitará entender el motivo dentro de 6 meses. Si el título es suficiente (`docs: fix typo in README`), no hace falta.

```
fix(auth): prevent session timeout during active use

The session was expiring after 15 minutes even when the user
was interacting with the page. Now the timer resets on each request.
```

### Footer

Son **metadatos** al final del commit, normalmente con formato `Clave: valor`.

```
Closes #142                          ← cierra el issue 142 al hacer merge
Refs #98                             ← solo hace referencia, no lo cierra
Co-authored-by: Ana <ana@mail.com>   ← da crédito a otra persona
BREAKING CHANGE: the /users endpoint now requires a token
```

---

## 3. Los tipos de commit

### `feat` — Nueva funcionalidad

**¿Cuándo se usa?** Cuando agregas algo nuevo que antes no existía: una función, una pantalla, un endpoint, un nuevo test suite completo.

**¿Cómo se escribe?** `feat(scope): add <lo nuevo>`

```
feat(login): add two-factor authentication
feat(api): add endpoint to list user transactions
feat(tests): add checkout flow test suite
```

**Versión:** incrementa **MINOR** (1.0.0 → 1.1.0).

---

### `fix` — Corrección de un error

**¿Cuándo se usa?** Cuando arreglas un bug, es decir, algo que funcionaba mal. Si corriges un test que fallaba por un error en el propio test, también va como `fix`.

**¿Cómo se escribe?** `fix(scope): <verbo> <qué se arregló>`

```
fix(login): handle empty password field validation
fix(api): return 404 when user does not exist
fix(tests): correct wrong locator in checkout page
```

**Ejemplo con cuerpo y footer:**

```
fix(auth): prevent session timeout during active use

The session was expiring after 15 minutes even when the user
was interacting with the page. Now the timer resets on each request.

Closes #142
```

**Versión:** incrementa **PATCH** (1.0.0 → 1.0.1).

---

### `docs` — Documentación

**¿Cuándo se usa?** Cuando cambias **solo documentación**: README, comentarios, guías, wikis. No toca código que se ejecute.

```
docs(readme): add installation instructions
docs: fix typo in contributing guide
docs(api): document authentication endpoints
```

---

### `style` — Formato del código

**¿Cuándo se usa?** Cuando el cambio **no altera el comportamiento**, solo la apariencia: espacios, indentación, punto y coma, orden de imports. **No confundir con estilos CSS** (eso sería `feat` o `fix`).

```
style: format code with prettier
style(tests): remove trailing whitespace
style: fix indentation in login module
```

---

### `refactor` — Reestructurar sin cambiar el comportamiento

**¿Cuándo se usa?** Cuando mejoras la estructura interna del código (más limpio, más ordenado) pero **el resultado para el usuario es exactamente el mismo**. No agrega funciones ni corrige bugs.

```
refactor(pages): extract common locators into base page
refactor(auth): simplify token validation logic
refactor(utils): split helper file into smaller modules
```

---

### `perf` — Mejora de rendimiento

**¿Cuándo se usa?** Cuando el cambio hace que algo sea **más rápido o consuma menos recursos**.

```
perf(db): add index to transactions table
perf(tests): run independent tests in parallel
perf(api): cache user profile responses
```

---

### `test` — Pruebas

**¿Cuándo se usa?** Cuando **agregas o modificas tests** sin cambiar el código de la aplicación. Si eres QA, este será uno de tus tipos más frecuentes.

```
test(login): add test for invalid credentials
test(checkout): cover payment with expired card
test(api): add contract tests for users endpoint
```

> **Ojo:** si el commit agrega una *funcionalidad nueva de tu framework de testing* (por ejemplo, un nuevo helper reutilizable), puede ser `feat`. Si solo añade casos de prueba, es `test`.

---

### `build` — Sistema de construcción y dependencias

**¿Cuándo se usa?** Cuando cambias lo que afecta **cómo se construye o instala** el proyecto: `package.json`, `pom.xml`, `requirements.txt`, versiones de dependencias, configuración del bundler.

```
build(deps): upgrade playwright to 1.48.0
build: add pytest to requirements
build(maven): update selenium dependency version
```

---

### `ci` — Integración continua

**¿Cuándo se usa?** Cuando cambias la configuración de los **pipelines** (GitHub Actions, Jenkins, GitLab CI, Azure DevOps).

```
ci: add GitHub Actions workflow for test execution
ci(jenkins): run regression suite nightly
ci: cache npm dependencies to speed up pipeline
```

---

### `chore` — Tareas de mantenimiento

**¿Cuándo se usa?** Cambios de mantenimiento que **no encajan en ningún otro tipo** y no afectan el código de producción ni los tests: limpiar archivos, actualizar `.gitignore`, scripts auxiliares.

```
chore: update .gitignore
chore: remove unused screenshots folder
chore(release): bump version to 1.2.0
```

---

### `revert` — Deshacer un commit anterior

**¿Cuándo se usa?** Cuando **revierte un commit previo** porque causó problemas. Se indica en el cuerpo qué commit se deshizo.

```
revert: feat(login): add two-factor authentication

This reverts commit a1b2c3d because it broke the SSO integration.
```

---

## 4. Scope (alcance)

Es **la parte del proyecto que se modifica**, escrita entre paréntesis después del tipo. Es **opcional**, pero ayuda a ubicar el cambio rápidamente.

```
feat(login): add remember me checkbox
         ↑
       scope
```

**¿Cómo elegirlo?**

- Usa el **nombre del módulo, página o área**: `login`, `checkout`, `api`, `auth`, `db`.
- Que sea **corto y consistente**: el mismo scope siempre con el mismo nombre en todo el equipo.
- Si el cambio toca muchas áreas, **omite el scope**: `docs: update all guides`.

---

## 5. Breaking changes (cambios que rompen compatibilidad)

Un *breaking change* es un cambio que **obliga a los demás a modificar su código** para seguir funcionando (por ejemplo, un endpoint que cambia su respuesta o una función que cambia sus parámetros).

Hay **dos formas** de indicarlo (se pueden combinar):

**1) Con `!` después del tipo/scope:**

```
feat(api)!: change user endpoint response format
```

**2) Con `BREAKING CHANGE:` en el footer:**

```
feat(api): change user endpoint response format

The response now returns a "data" object instead of a flat array.

BREAKING CHANGE: clients must read users from response.data
```

**Versión:** incrementa **MAJOR** (1.4.2 → 2.0.0).

---

## 6. Buenas y malas prácticas

| ❌ Mal | ✅ Bien | Por qué |
|---|---|---|
| `fixed stuff` | `fix(login): handle empty password` | El primero no dice qué ni dónde |
| `Update` | `docs(readme): add setup steps` | Sin tipo ni descripción útil |
| `feat: Added new login.` | `feat(login): add new login page` | Imperativo, sin punto final |
| `fix: lots of changes in many files` | Dividir en varios commits pequeños | Un commit = un cambio lógico |
| `WIP` | Terminar el cambio antes de hacer commit | Ensucia el historial |
| `feat: add login and fix checkout and update docs` | 3 commits separados | Mezcla tipos distintos |

**Regla de oro:** un commit debe hacer **una sola cosa**. Si necesitas la palabra "y" para describirlo, probablemente son dos commits.

---

## 7. Ejemplos para QA y automatización

```
test(login): add negative scenarios for invalid credentials
test(transfer): validate error message when balance is insufficient
fix(tests): replace hardcoded wait with explicit wait in payment page
fix(locators): update selector after UI redesign of checkout
refactor(pages): apply page object pattern to account module
feat(fixtures): add reusable fixture for authenticated user
feat(utils): add helper to generate random test data
build(deps): upgrade playwright from 1.47.0 to 1.48.0
ci: run smoke tests on every pull request
ci: publish HTML test report as pipeline artifact
chore: remove obsolete test data files
docs(readme): add instructions to run tests locally
perf(tests): enable parallel execution with 4 workers
```

---

## 8. Tabla resumen (consulta rápida)

| Tipo | ¿Cuándo? | Versión | Ejemplo |
|---|---|---|---|
| `feat` | Funcionalidad nueva | MINOR | `feat(login): add 2FA` |
| `fix` | Corregir un bug | PATCH | `fix(api): return 404 on missing user` |
| `docs` | Solo documentación | — | `docs: update README` |
| `style` | Formato, sin cambiar lógica | — | `style: format with prettier` |
| `refactor` | Reestructurar sin cambiar resultado | — | `refactor: extract base page` |
| `perf` | Mejorar rendimiento | PATCH | `perf(db): add index` |
| `test` | Agregar/modificar tests | — | `test(login): add invalid case` |
| `build` | Dependencias / build | — | `build(deps): upgrade playwright` |
| `ci` | Pipelines | — | `ci: add workflow` |
| `chore` | Mantenimiento general | — | `chore: update .gitignore` |
| `revert` | Deshacer un commit | — | `revert: feat(login): add 2FA` |
| `!` o `BREAKING CHANGE` | Rompe compatibilidad | **MAJOR** | `feat(api)!: change response` |

---

## 9. Automatizar la validación: commitlint + husky

Son dos herramientas que se usan **juntas** para que nadie pueda hacer un commit mal escrito:

- **commitlint:** revisa que el mensaje cumpla el formato. Es el "corrector".
- **husky:** ejecuta acciones automáticas cuando haces `git commit` (*Git hooks*). Es el "guardia en la puerta" que llama a commitlint antes de aceptar el commit.

**Resultado en la práctica:**

```
$ git commit -m "fixed login"
✖ type may not be empty
✖ subject may not be empty
→ Commit rejected

$ git commit -m "fix(login): handle empty password field"
✔ Commit accepted
```

### Instalación (proyectos Node.js / npm, como Playwright + TypeScript)

**1) Instalar las dependencias:**

```bash
npm install --save-dev @commitlint/cli @commitlint/config-conventional husky
```

**2) Crear el archivo `commitlint.config.js`** en la raíz del proyecto:

```js
module.exports = {
  extends: ['@commitlint/config-conventional'],
};
```

> Si tu `package.json` tiene `"type": "module"`, usa `export default { extends: [...] };` en lugar de `module.exports`.

**3) Inicializar husky:**

```bash
npx husky init
```

**4) Crear el hook que valida el mensaje:**

```bash
echo "npx --no -- commitlint --edit \$1" > .husky/commit-msg
```

Listo: desde ahora, cada `git commit` pasará por commitlint.

### Para proyectos en Python

Husky y commitlint dependen de Node.js. En Python existen alternativas equivalentes:

- **pre-commit:** gestiona los Git hooks (equivale a husky).
- **commitizen:** valida el formato y además ofrece un asistente interactivo para escribir el commit (`cz commit`).

---

## Resumen final

1. Formato: `type(scope): description` + cuerpo y footer opcionales.
2. `feat` = algo nuevo, `fix` = arreglar un bug; el resto describe otros tipos de cambio.
3. Verbo en imperativo, minúscula, sin punto final.
4. Un commit = un cambio lógico.
5. `!` o `BREAKING CHANGE:` cuando se rompe compatibilidad.
6. Automatiza la validación con commitlint + husky (Node) o pre-commit + commitizen (Python).
