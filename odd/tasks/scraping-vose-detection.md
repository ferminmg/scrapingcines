# Feature: Detección VOSE e identificación fiable

- **Creado:** 2026-09-26
- **Ruta elegida:** delegada direct (trigger de escritor: 5+ ficheros no triviales) → *degradada a inline por fallo del runtime de sub-agentes (ver "Desviación de enrutado")*
- **Rama:** `fix/scraping-vose-detection` (creada desde `main`)
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
  5. Parsing de director en Ghost: split por el ÚLTIMO ` de ` con criterio de nombre propio + fallback al campo `Dirección:` del contenido.
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
- [x] **T6** `verificar_salidas.py` (nuevo) + `.github/workflows/main.yml` — cada paso `|| echo` también deja constancia en `${{ runner.temp }}/fallores` (fuera del repo); paso final `✅ Verificar salidas` con `if: always()` **después** del push y del deploy de Pages: comprueba que las 4 salidas obligatorias existen, parsean y tienen ≥1 elemento, compara con `git show HEAD:`, emite `::error::` y devuelve 1 → los datos igual se publican pero el run queda en rojo
      - **Corregido tras chequeo del padre:** `subprocess.run` sin `encoding='utf-8'` rompía en Windows (cp1252) al comparar `index.json`.
- [x] **T7** Verificación funcional + commits por unidad de trabajo

## Criterios de aceptación

- Con el HTML vivo de Filmoteca, "Palestina 36" **sí** pasa el filtro y su título de búsqueda TMDB es `Palestina 36` (sin paréntesis).
- `peliculas_vose.json` pasa de 36 entradas/10 títulos a 10 entradas/10 títulos con la suma de horarios intacta (36 sesiones-día conservadas).
- Yelmo asigna año correcto en una fecha de diciembre consultada en enero (prueba con `FilterDate` de diciembre).
- `equivalencias_peliculas.json` conserva las claves previas tras una ejecución con nuevas sugerencias.
- El conteo de `director != "Desconocido"` en `index.json` no baja (regresión) y mejora en los casos con `Dirección:` en el contenido.
- Workflow: una salida vacía marca `::error::` y el job termina en fallo **después** del commit.

## Riesgos

- **R1 (medio):** el filtro más permisivo de Filmoteca puede colar eventos no-filmoteca. Mitigación: exigir además que exista enlace de compra (`nicdo.es`/`bacantix`) o `Duración:` en la ficha.
- **R2 (medio):** el nuevo director de Ghost puede asignar mal en títulos con ` de ` interno. Mitigación: exigir que la parte derecha sea un nombre propio (1-4 palabras, sin dígitos, sin mayúsculas solo) y caer a `Desconocido` si no convence.
- **R3 (bajo):** los consumidores de la API podrían depender del formato duplicado de Golem (36 entradas). Mitigación: documentar el cambio; es una corrección, no un cambio de esquema.

## Desviación de enrutado

Trigger de escritor disparado (5+ ficheros no triviales). El 2026-09-26 la delegación a sub-agente falló con:

```
OpenCode's free tier can only be used from within OpenCode
```

Se ejecuta inline con este documento como registro de la ruta y la desviación. La delegación de exploración también falló con el mismo error, por eso el mapeo de lectura es inline.

## Progreso

- 2026-09-26: documento creado; exploración y contraste con webs vivas completados.
- 2026-09-26: T1–T6 implementados por delegación (`general`, sesión `ses_f22a7a4e0ffe...` para T1–T5 y `ses_f2295a231ffe...` para T5-corrección + T6). Ruta: delegada direct.
- 2026-09-26: **Gate del padre (T5): FALLÓ → corrección aplicada.** El split por la última ` de ` daba directores falsos. Re-implementado y re-medido sobre los 2470 títulos crudos de `posts/*.json`: 25 comportamientos distintos, 0 nombres basura, 12 ficheros con nombre nuevo y **los 12 nombres heredados existen en disco** (guardia `rutas_post` cubierta).
- 2026-09-26: **Gate del padre (T6): FALLÓ → fix aplicado.** `git show HEAD:` usaba la codificación local en Windows (`index.json` quedaba sin comparar). Corregido con `encoding='utf-8'`.

## Verificación observada (2026-09-26, ejecutada por el padre)

| Check | Comando | Resultado |
|---|---|---|
| Compila | `python -m py_compile` (5 ficheros) | exit 0 |
| Filtro Filmoteca vivo | fetch de los 10 eventos reales + `es_vose()`/`limpiar_titulo_h1()` | **1 pasa: `Palestina 36`**, idioma `Voz original en inglés subtitulado al español`, enlace `nicdo.es` presente; los 9 eventos que no son películas quedan fuera; **el filtro antiguo NO lo pasaba** |
| Unidades del escritor | 11 aserciones de split + 3 casos de `verificar_salidas.py` (fixtures en Temp) | 0 fallos; `[]` → exit 1 con `::error file=`; JSON inválido → exit 1 |
| Verificador contra el repo real | `python verificar_salidas.py` | exit 0; `index.json: antes=2571 ahora=2571` (ruta git verificada) |
| YAML del workflow | `yaml.safe_load` | parsea; paso final con `if: always()` tras push y deploy |
| TDD | — | OFF (sin framework de tests en el repo) |

**Pendiente de autorización:** `git push` (operación remota). **Pendiente de Engram:** espejo `odd/scraping-vose-detection/tasks` — el proyecto `scrapingcines` no está dado de alta en la tienda de Engram, así que el espejo queda **pendiente** y el documento local es la fuente de verdad.

## Resultado del asesor de riesgos (RDD)

- Intento: `gentle-ai review assess --cwd <repo> --agent opencode --base-ref 2c33c216 --committed-only --json`
- Resultado: **`unavailable`** — exit 1, `the active runtime is not eligible for immutable receipt review ... supported immutable review runtimes: claude-code, codex`.
- Interpretación: es el contrato documentado del runtime (la revisión V2 de OpenCode está en espera de conformidad), **no** un defecto → sin handoff de proveedor.
- Consecuencia: el tier **no se rebaja** por el fallo, pero **tampoco existe recibó ni aprobación**. El trabajo queda verificado solo con las comprobaciones funcionales de la tabla anterior. Si quieres recibo, hay que ejecutar la rama desde claude-code o codex.

## Commits (unidades de trabajo, rama `fix/scraping-vose-detection`)

| Commit | Unidad |
|---|---|
| `e0a6b9e2` | fix(filmoteca): redacción VOSE actual, título limpio, enlace nicdo, equivalencias fusionadas |
| `9d5bbb76` | fix(golem): fusión por (cine, película) |
| `97f65a80` | fix(yelmo): año desde `FilterDate` |
| `07032188` | fix(blog): director robusto + rutas heredadas |
| `2f61e343` | ci: run en rojo si una salida queda vacía o el scraper crashea |
| `d3805a46` | docs(odd): documento de seguimiento |

