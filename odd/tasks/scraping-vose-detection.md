# Feature: Detección VOSE e identificación fiable

- **Creado:** 2026-09-26
- **Ruta elegida:** delegada direct (trigger de escritor: 5+ ficheros no triviales). La exploración inicial y las dos correcciones de gate fueron inline (ver "Desviación de enrutado").
- **Rama:** `fix/scraping-vose-detection` (creada desde `main`, punto de partida `2c33c216`)
- **TDD efectivo:** OFF — el proyecto no tiene framework de tests (`tests/`, `pytest.ini`, `conftest.py` ausentes; `pytest` no instalado en `.venv`). Fuente: comprobación directa del repo el 2026-09-26.
  - Runner de verificación: `.venv\Scripts\python.exe` (Python 3.11.5)
  - Checks por tarea: `python -m py_compile <fichero>` + prueba funcional dirigida (fixture o lectura viva de solo lectura)

## Objetivo

Que la API publicada (GitHub Pages) no pierda sesiones VOSE reales y no identifique mal las películas, y que un fallo de scraping no pase inadvertido.

## Problema (evidencia, 2026-09-26)

1. **Filmoteca detecta 0 películas.** `scraper_modificado.py:200-204` exige `'V.O.S.E.'`/`'subtítulos en español'`/`'subtítulos en castellano'`; la web dice hoy `Voz original en inglés subtitulado al español`. 0 de 10 eventos pasan el filtro. `peliculas_filmoteca.json` = `[]` desde 2026-09-05 y los runs de Actions siguen en verde (`main.yml` traga errores con `|| echo`).
2. **Golem duplica en lugar de fusionar.** 36 entradas = 10 títulos distintos ("Bad Apples" ×8, "Cronos" ×8; La Morea 7 entradas → 1 película). `scraping_golem.py:188-265` crea un `Movie` por día.
3. **`equivalencias_peliculas.json` se destruye.** `scraper_modificado.py:296-300` sobrescribe el fichero con solo las sugerencias de la ejecución actual. De 25 claves curadas quedan 3, todas con `tmdb_id: null`.
4. **Identificación frágil.** Filmoteca usa el `<h1>` entero (`"Palestina 36 (Palestine36, Palestina, 2025)"`) como título de búsqueda TMDB. Yelmo y Filmoteca calculan el año con `datetime.now().year` (Yelmo ya entrega `FilterDate` con el año real; Filmoteca ya lista meses de 2027).
5. **Ghost in the Blog pierde el director en el 77,1% de los casos** (2082/2701) porque `titulo.split(' de ')` exige exactamente 2 partes (`scrape_ghostintheblog.py:71,90`); produce títulos contaminados como `'42 SEGUNDOS de Álex Murrull y Dani de la Orden'`.
6. **Yelmo descarta VOSI** por el filtro `'VOSE' in Language` (`scraping_yelmo.py:177`): hoy 4 sesiones. Es criterio de negocio (solo VOSE) → **se documenta, no se cambia**.

## Por qué

La web de Filmoteca cambió su redacción y nadie se enteró durante 3 semanas: el pipeline no tiene ninguna comprobación de "salida vacía". Los fallos de identificación son de formato de entrada, no del matching de TMDB (verificado: hoy Golem acierta `Cronos` → Fernando González Molina 2026 y es estable entre duplicados).

## Alcance (autorizado por el usuario: "lo que consideres")

- **In:**
  1. Filtro de idioma de Filmoteca tolerante a variantes reales + corte del `<h1>` en el primer `(`.
  2. Fusión en Golem por `(cine, título)` con todos los horarios de los 10 días.
  3. Fecha en Yelmo desde `FilterDate` (epoch .NET) en vez del año actual.
  4. Fusión (no sobrescritura) de `equivalencias_peliculas.json`.
  5. Parsing de director en Ghost: primera ` de ` cuya parte derecha parezca nombre propio, `Desconocido` en posts con dos películas, y respaldo desde `Dirección:` del contenido.
  6. Paso de verificación en el workflow que deje el run en ROJO si una salida queda vacía o inválida, **después** de commitear, para no bloquear los scrapers sanos.
- **Fuera de alcance:**
  - Limpieza histórica del repo (`.venv/` 2160 ficheros tracked, `backups/` 4090, pack 466 MB) → requiere autorización explícita por ser destructivo.
  - Añadir VOSI al criterio VOSE (decisión de negocio).
  - Incluir `scrape_ghostintheblog_resto.py` (backfill) en el workflow.
  - `git pull` / `git push` (operación remota → requiere autorización del usuario aparte).

## Tareas

- [x] **T1** `scraper_modificado.py` — filtro de idioma por variantes (`es_vose()` + `CADENAS_VOSE`, NFKD→ASCII) + guardia de película (`Idioma` **y** `Duración`) + corte de título en `(` (`limpiar_titulo_h1()`) + año con desplazamiento a futuro si la fecha ya pasó (>15 días) + enlace de entradas aceptando `bacantix.com` **o** `nicdo.es`
- [x] **T2** `scraping_golem.py` — `merge_movies()` agrupa por `(cine, título)`, concatena `horarios`, gana el primer valor no vacío de `cartel` y campos TMDb (`CAMPOS_TMDB`)
- [x] **T3** `scraping_yelmo.py` — `fecha_desde_filter_date()` convierte `/Date(1790398800000)/` a `YYYY-MM-DD` en UTC; `ShowtimeDate` queda como respaldo
- [x] **T4** `scraper_modificado.py` — las equivalencias se fusionan sobre las cargadas; las que ya tienen `tmdb_id` real no se pisan
- [x] **T5** `scrape_ghostintheblog.py` — `split_titulo_director()` prueba cada ` de ` de izquierda a derecha (máx. 8 palabras, sin dígitos ni `/`, mayúsculas o partículas); posts con ` / ` → `Desconocido` (deja actuar al respaldo `Dirección:` del contenido); `rutas_post()` comprueba también la ruta heredada para no renombrar ficheros históricos
      - **Corregido tras gate del padre:** la primera versión partía por la ÚLTIMA ` de ` y producía directores falsos (`la Orden`, `la Iglesia`, `Chauveron`). Re-medida sobre los títulos reales: 10 casos contaminados arreglados con el nombre completo, 0 nombres basura, posts con dos películas sin emparejar mal.
- [x] **T6** `verificar_salidas.py` (nuevo) + `.github/workflows/main.yml` — cada paso `|| echo` también deja constancia fuera del repo en `/tmp/fallos_scraper.txt` (antes `runner.temp`, ver T8); paso final `✅ Verificar salidas` con `if: always()` **después** del push y del deploy de Pages: comprueba que las 4 salidas obligatorias existen, parsean y tienen ≥1 elemento, compara con `git show HEAD:`, emite `::error::` y devuelve 1 → los datos igual se publican pero el run queda en rojo
      - **Corregido tras chequeo del padre:** `subprocess.run` sin `encoding='utf-8'` rompía en Windows (cp1252) al comparar `index.json`.
- [x] **T7** Verificación funcional + commits por unidad de trabajo
- [x] **T8** Ejecución real del workflow sobre la rama + tres arreglos de CI encontrados en caliente
      - `runner.temp` **no** es válido en `env` de job (solo dentro de `steps`): GitHub rechazaba el fichero entero y ningún job arrancaba (`startup_failure`). Le afectaba también a `main`.
      - El paso de commit hacía `git pull --rebase origin main` + `git push origin main`: desde otra rama el rebase choca con los datos que esa rama no tiene (add/add en binarios) y el push no puede funcionar. Ahora usan `$GITHUB_REF_NAME`, que en los schedules sigue siendo `main`.
      - El verificador elegía `.venv/Scripts/python.exe` con `-f`: ese binario de Windows está commiteado, existe en ubuntu y no es ejecutable (`Permission denied`) → el paso moría antes de validar nada. Ahora exige `-x`.

## Criterios de aceptación

- [x] Con el HTML vivo de Filmoteca, "Palestina 36" **sí** pasa el filtro y su título de búsqueda TMDB es `Palestina 36` (sin paréntesis).
- [x] `peliculas_vose.json` sin pérdida de sesiones — **ejecutado en CI** (run `36252376881`) y comparado con `main` en la misma ventana 26/09–02/10: **27 entradas → 7 entradas**, con los **7 pares (cine, título) y los 38 horarios idénticos**, 0 títulos perdidos y 0 nuevos. (La cifra "36 entradas / 10 títulos" del diagnóstico provenía de un ref local `origin/main` stale con datos del 09-24, no del tip.)
- [x] Yelmo asigna año correcto en una fecha de diciembre consultada en enero (prueba con `FilterDate` de diciembre y con desfase horario).
- [ ] `equivalencias_peliculas.json` conserva las claves previas tras una ejecución con nuevas sugerencias — **no ejecutado** (misma razón: requiere correr el scraper); la lógica de merge está cubierta por inspección del diff.
- [ ] El conteo de `director != "Desconocido"` en `index.json` no baja — **medido en frío** sobre los 2470 `posts/*.json`: 25 títulos cambian de comportamiento, 0 asignaciones incorrectas, 0 regresiones (los casos que el split antiguo resolvía siguen resueltos).
- [x] Workflow: una salida vacía marca `::error::` y el job termina en fallo **después** del commit (probado con fixtures: `[]` → exit 1; JSON inválido → exit 1; ficheros válidos → exit 0).

## Riesgos

- **R1 (medio):** el filtro más permisivo de Filmoteca puede colar eventos no-filmoteca. Mitigación: se exige además `Idioma` **y** `Duración` en la ficha; verificado en vivo, los 9 eventos que no son películas quedan fuera.
- **R2 (medio):** el nuevo director de Ghost puede asignar mal en títulos con ` de ` interno. Mitigación: nombre propio de 1-8 palabras sin dígitos ni `/`, posts con ` / ` → `Desconocido`, y respaldo `Dirección:`. Medido: 0 nombres basura.
- **R3 (bajo):** los consumidores de la API podrían depender del formato duplicado de Golem (36 entradas). Mitigación: documentar el cambio; es una corrección, no un cambio de esquema.
- **R4 (bajo):** un cine sin sesiones VOSE un día deja la salida vacía y el run en rojo. Es el comportamiento buscado (alarma visible), pero puede dar un falso positivo puntual.

## Desviación de enrutado

Trigger de escritor disparado (5+ ficheros no triviales). El 2026-09-26 la delegación inicial falló con:

```
OpenCode's free tier can only be used from within OpenCode
```

Por eso la exploración y el mapeo de lectura se hicieron inline. La delegación **sí funcionó** después para la implementación: `general` (sesión `ses_f22a7a4e0ffe...`) aplicó T1–T5 y `general` (sesión `ses_f2295a231ffe...`) aplicó la corrección de T5 y T6. Los dos gates del padre se corrigieron inline con evidencia medible.

## Progreso

- 2026-09-26: documento creado; exploración y contraste con webs vivas completados.
- 2026-09-26: T1–T6 implementados por delegación (`general`). Ruta: delegada direct.
- 2026-09-26: **Gate del padre (T5): FALLÓ → corrección aplicada.** El split por la última ` de ` daba directores falsos. Re-implementado y re-medido sobre los 2470 títulos crudos de `posts/*.json`: 25 comportamientos distintos, 0 nombres basura, 12 ficheros con nombre nuevo y **los 12 nombres heredados existen en disco** (guardia `rutas_post` cubierta).
- 2026-09-26: **Gate del padre (T6): FALLÓ → fix aplicado.** `git show HEAD:` usaba la codificación local en Windows (`index.json` quedaba sin comparar). Corregido con `encoding='utf-8'`.
- 2026-09-26: commits por unidad de trabajo en `fix/scraping-vose-detection`; espejo Engram guardado en `odd/scraping-vose-detection/tasks`.
- 2026-09-26: rama empujada; el usuario fusionó el **PR #2** en `main` a las 12:31 UTC — incluía el `runner.temp` roto, así que `main` quedó con el workflow inválido.
- 2026-09-26: **T8 — ejecución del action e iteración hasta verde.** Run 1 (`36251717069`) en rojo: los 5 scrapers en verde, pero `💾 Commitear cambios` (rebase contra `main`) y `✅ Verificar salidas` (`Permission denied`) fallan. Corregidos ambos defectos, run 2 (`36252376881`) → **`success`, 20/20 pasos**.
- 2026-09-26: **T8 cerrado.** Arreglos subidos a `main` (`030074e7`, solo el workflow, diff verificado antes de subir) y validados con el cron de producción de las 16:00 UTC → run `36254071841` **`success`**.

## Verificación observada (2026-09-26, ejecutada por el padre)

| Check | Comando | Resultado |
|---|---|---|
| Compila | `python -m py_compile` (5 ficheros) | exit 0 |
| Filtro Filmoteca vivo | fetch de los 10 eventos reales + `es_vose()`/`limpiar_titulo_h1()` | **1 pasa: `Palestina 36`**, idioma `Voz original en inglés subtitulado al español`, enlace `nicdo.es` presente; los 9 eventos que no son películas quedan fuera; **el filtro antiguo NO lo pasaba** |
| Unidades del escritor | 11 aserciones de split + 3 casos de `verificar_salidas.py` (fixtures en Temp) | 0 fallos; `[]` → exit 1 con `::error file=`; JSON inválido → exit 1 |
| Verificador contra el repo real | `python verificar_salidas.py` | exit 0; `index.json: antes=2571 ahora=2571` (ruta git verificada) |
| YAML del workflow | `yaml.safe_load` | parsea; paso final con `if: always()` tras push y deploy |
| Run completo en CI | `workflow_dispatch` → run [`36252376881`](https://github.com/ferminmg/scrapingcines/actions/runs/36252376881) | **`success`, 20/20 pasos**: 5 scrapers, `💾 Commitear cambios`, deploy de Pages y `✅ Verificar salidas` en verde |
| Golem sin pérdida | `main` (12:13, código antiguo) vs rama (15:36), misma ventana 26/09–02/10 | 27→7 entradas; **7 pares (cine,título) y 38 horarios idénticos**; 0 títulos perdidos |
| Filmoteca end-to-end | `main` vs rama en CI | `main` = `[]` (0), rama = **1 película** con sesión 30/09 y enlace `nicdo.es` |
| TDD | — | OFF (sin framework de tests en el repo) |

**Push a la rama:** hecho con permiso del usuario (2026-09-26: `07b1965c`, `a4a23734`).

**Arreglos llevados a `main`** (decisión del usuario: "subirlo a main ahora"): commit [`030074e7`](https://github.com/ferminmg/scrapingcines/commit/030074e7626e4687cf451ecdd4e18822e4dd2abf) vía API de Contents con **solo** `.github/workflows/main.yml`, previa verificación del diff (exactamente los 3 arreglos, 307 → 316 líneas). Validado con el cron real de producción: run [`36254071841`](https://github.com/ferminmg/scrapingcines/actions/runs/36254071841) (16:03 UTC) → **`success`** (validate 3/3; scraping 20/21, con el paso de próximos estrenos omitido por horario). **La tubería de `main` vuelve a estar operativa.**

**Resto pendiente:** el commit de datos `e9b34693` de la rama chocaría con los datos de `main` en un merge; la rama ya no aporta nada que no esté en `main` (código vía PR #2, workflow vía `030074e7`).

## Resultado del asesor de riesgos (RDD)

- Intento: `gentle-ai review assess --cwd <repo> --agent opencode --base-ref 2c33c216 --committed-only --json`
- Resultado: **`unavailable`** — exit 1, `the active runtime is not eligible for immutable receipt review ... supported immutable review runtimes: claude-code, codex`.
- Interpretación: es el contrato documentado del runtime (la revisión V2 de OpenCode está en espera de conformidad), **no** un defecto → sin handoff de proveedor.
- Consecuencia: el tier **no se rebaja** por el fallo, pero **tampoco existe recibo ni aprobación**. El trabajo queda verificado solo con las comprobaciones funcionales de la tabla anterior. Si quieres recibo, hay que ejecutar la rama desde claude-code o codex.

## Commits (unidades de trabajo, rama `fix/scraping-vose-detection`)

| Commit | Unidad |
|---|---|
| `e0a6b9e2` | fix(filmoteca): redacción VOSE actual, título limpio, enlace nicdo, equivalencias fusionadas |
| `9d5bbb76` | fix(golem): fusión por (cine, película) |
| `97f65a80` | fix(yelmo): año desde `FilterDate` |
| `07032188` | fix(blog): director robusto + rutas heredadas |
| `2f61e343` | ci: run en rojo si una salida queda vacía o el scraper crashea |
| `d3805a46` | docs(odd): documento de seguimiento |
| `c34fa335` | docs(odd): registro del resultado de RDD |
| `07b1965c` | ci: ruta literal en `env` de job (el contexto `runner.temp` rompía el fichero entero) |
| `a4a23734` | ci: commit de datos en la rama que dispara el run + Python ejecutable en el verificador |
| `e9b34693` | 🔄 Actualización automática — commit de datos creado por el run verde de CI |
