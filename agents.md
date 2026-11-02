# Agentes y Automatización - Scraping Cines

## Arquitectura de Agentes

Este proyecto utiliza **GitHub Actions** como sistema de agentes automatizados que ejecutan tareas de scraping cada 4 horas.

## Workflow Principal (.github/workflows/main.yml)

### Schedule de Ejecución

| Trigger | Horario | Descripción |
|---------|---------|-------------|
| Scraping general | `0 */4 * * *` | Cada 4 horas |
| Próximos estrenos | `0 10,22 * * *` | 10:00 y 22:00 UTC |
| Manual | `workflow_dispatch` | Bajo demanda |

### Jobs del Workflow

```yaml
jobs:
  validate:
    # Valida si debe ejecutarse el job de próximos estrenos
    # (solo a las 10:00 y 22:00 UTC)

  scraping:
    # Job principal que ejecuta todos los scrapers
    steps:
      1. Checkout del repositorio
      2. Setup Python 3.11
      3. Instalar dependencias (requirements.txt)
      4. Crear .env con TMDB_API_KEY desde secrets
      5. Ejecutar scrapers:
         - scraping_golem.py
         - scraping_yelmo.py
         - scraper_modificado.py + integrador.py
         - scrape_ghostintheblog.py
         - proximos_estrenos.py (condicional)
      6. Limpiar archivos temporales
      7. Generar resumen de archivos
      8. Commit y push a main
      9. Deploy a GitHub Pages
```

## Agentes/Scripts de Scraping

### 1. Agente Filmoteca (scraper_modificado.py + integrador.py)

**Responsabilidad:** Obtener cartelera de Filmoteca de Navarra

**Flujo:**
```
filmotecanavarra.com → scraper_modificado.py → peliculas_filmoteca_scraping.json
                                    ↓
                              integrador.py
                                    ↓
                         peliculas_filmoteca.json (final)
```

**Características:**
- Extrae: título, director, duración, actores, sinopsis, horarios
- Busca en TMDB para obtener ID y póster
- Integra con películas añadidas manualmente
- Filtra horarios pasados automáticamente

### 2. Agente Golem (scraping_golem.py)

**Responsabilidad:** Obtener películas VOSE de Golem Cines

**Output:** `peliculas_vose.json`

**Características:**
- Extrae películas en versión original subtitulada
- Incluye enlaces de compra de entradas
- Enriquece datos con TMDB

### 3. Agente Yelmo (scraping_yelmo.py)

**Responsabilidad:** Obtener cartelera de Yelmo Cines

**Output:** `peliculas_filmaffinity.json`

**Características:**
- Scraping via FilmAffinity
- Enfocado en versiones VOSE

### 4. Agente Estrenos (proximos_estrenos.py)

**Responsabilidad:** Obtener próximos estrenos en España

**Output:** `proximos_estrenos.json`

**Schedule:** Solo 2 veces al día (10:00 y 22:00 UTC)

**Características:**
- Consulta API de TMDB directamente
- Paginación configurable (--max-pages)
- Descarga pósters automáticamente

### 5. Agente Críticas (scrape_ghostintheblog.py)

**Responsabilidad:** Indexar críticas de Ghost in the Blog

**Output:**
- `index.json` (índice general)
- `posts/*.json` (críticas individuales)

**Características:**
- Mantiene histórico de críticas
- Extrae: título, director, fecha, contenido
- Actualización incremental

## Flujo de Datos Entre Agentes

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Filmoteca Web  │     │   Golem Web     │     │   Yelmo Web     │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│scraper_modif.py │     │scraping_golem.py│     │scraping_yelmo.py│
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ _scraping.json  │     │peliculas_vose.  │     │peliculas_film   │
│  (temporal)     │     │     json        │     │  affinity.json  │
└────────┬────────┘     └─────────────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ integrador.py   │◄────│ Películas       │
│                 │     │ Manuales        │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│peliculas_       │
│filmoteca.json   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│            GitHub Pages                  │
│     (API JSON estática pública)          │
└─────────────────────────────────────────┘
```

## Configuración de Secrets en GitHub

```
Repository Settings → Secrets and variables → Actions

TMDB_API_KEY = <tu_api_key>
```

## Monitoreo y Logs

### GitHub Actions
- Ver ejecuciones: `Actions` tab en el repositorio
- Logs detallados de cada step
- Notificaciones de fallos

### Logs Locales
- Ubicación: `/logs/`
- Formato: `scraper_YYYYMMDD_HHMMSS.log`
- Retención: Últimos 5 archivos

## Ejecución Manual de Agentes

### Desde GitHub
1. Ir a Actions → Workflow
2. Click "Run workflow"
3. Seleccionar rama y ejecutar

### Desde Local
```bash
# Ejecutar todo el flujo
python ejecutar.py --completo

# Solo un agente específico
python scraping_golem.py
python scraping_yelmo.py
python proximos_estrenos.py
python scrape_ghostintheblog.py
```

## Manejo de Errores

Cada agente implementa:
- **Retry automático** en requests fallidos
- **Logging** de errores a archivo y consola
- **Fallback** de idioma en TMDB (ES → EN)
- **Validación** de datos antes de guardar

## Extensión de Agentes

Para agregar un nuevo cine/fuente:

1. Crear script `scraping_nuevo.py`
2. Implementar clase con método de scraping
3. Usar TMDbAPI para enriquecimiento
4. Guardar output en JSON
5. Agregar step en `.github/workflows/main.yml`
6. Opcionalmente integrar con `integrador.py`
