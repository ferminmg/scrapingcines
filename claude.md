# Claude Code - Proyecto Scraping Cines

## Resumen del Proyecto

Sistema automatizado de scraping y gestión de carteleras de cines en Navarra (España). Recopila información de películas de múltiples fuentes, las enriquece con datos de TMDB y las publica como API JSON estática via GitHub Pages.

## Estructura Principal

```
/
├── Scripts principales (Python 3.11+)
│   ├── ejecutar.py              # Controlador unificado (usar este)
│   ├── scraper_modificado.py    # Scraper Filmoteca Navarra
│   ├── integrador.py            # Fusiona datos scrapeados + manuales
│   ├── scraping_golem.py        # Scraper Golem Cines
│   ├── scraping_yelmo.py        # Scraper Yelmo Cines
│   ├── proximos_estrenos.py     # Próximos estrenos desde TMDB
│   ├── scrape_ghostintheblog.py # Scraper críticas de cine
│   ├── admin_web.py             # Interfaz web Flask (localhost:5000)
│   └── admin_tmdb.py            # Administrador CLI
│
├── Datos JSON (outputs)
│   ├── peliculas_filmoteca.json     # Filmoteca de Navarra
│   ├── peliculas_vose.json          # Golem VOSE
│   ├── peliculas_filmaffinity.json  # Yelmo
│   ├── proximos_estrenos.json       # Próximos estrenos España
│   ├── equivalencias_peliculas.json # Mapeo título→TMDB ID
│   └── index.json + posts/          # Críticas Ghost in the Blog
│
├── Imágenes (pósters)
│   ├── imagenes_filmoteca/
│   ├── imagenes_peliculas/
│   ├── imagenes_estrenos/
│   └── imagenes_filmaffinity/
│
└── Configuración
    ├── .github/workflows/main.yml   # GitHub Actions (cada 4h)
    ├── requirements.txt             # Dependencias Python
    └── .env                         # TMDB_API_KEY (crear localmente)
```

## Comandos Principales

```bash
# Ejecución completa (scraping + integración)
python ejecutar.py --completo

# Solo scraper Filmoteca
python ejecutar.py --scraper

# Solo integrador (fusiona datos)
python ejecutar.py --integrador

# Interfaz web para gestión manual
python ejecutar.py --admin-web

# Administrador por consola
python ejecutar.py --admin-consola

# Scripts individuales
python scraping_golem.py
python scraping_yelmo.py
python proximos_estrenos.py --max-pages=10
python scrape_ghostintheblog.py
```

## Fuentes de Datos

| Fuente | Script | Output | Descripción |
|--------|--------|--------|-------------|
| Filmoteca Navarra | scraper_modificado.py | peliculas_filmoteca.json | Cine de autor/VOSE |
| Golem Cines | scraping_golem.py | peliculas_vose.json | VOSE comercial |
| Yelmo Cines | scraping_yelmo.py | peliculas_filmaffinity.json | Cartelera comercial |
| TMDB | proximos_estrenos.py | proximos_estrenos.json | Próximos estrenos |
| Ghost in the Blog | scrape_ghostintheblog.py | index.json + posts/*.json | Críticas |

## Configuración Requerida

1. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Crear archivo `.env`:**
   ```
   TMDB_API_KEY=tu_api_key_de_themoviedb
   ```

## Estructura de Datos JSON

### Película (peliculas_*.json)
```json
{
  "título": "Nombre de la Película",
  "tmdb_id": 123456,
  "cartel": "imagenes_filmoteca/poster.jpg",
  "horarios": [
    {"fecha": "2025-11-28", "hora": "19:30", "enlace_entradas": ""}
  ],
  "cine": "Filmoteca de Navarra",
  "director": "Nombre Director",
  "duración": "120 min",
  "actores": "Actor 1, Actor 2",
  "sinopsis": "Descripción...",
  "año": "2024"
}
```

### Equivalencias (equivalencias_peliculas.json)
```json
{
  "titulo normalizado sin acentos": {
    "tmdb_id": 123456,
    "titulo_original": "",
    "anio": "2024"
  }
}
```

## Flujo de Automatización (GitHub Actions)

- **Schedule:** Cada 4 horas (`0 */4 * * *`)
- **Flujo:**
  1. Ejecuta scrapers de todos los cines
  2. Integra datos con películas manuales
  3. Descarga pósters de TMDB
  4. Commit automático si hay cambios
  5. Deploy a GitHub Pages

## Patrones de Código Importantes

### Normalización de títulos (para deduplicación)
```python
# Convierte "La Película (2024)" → "la pelicula 2024"
unicodedata.normalize('NFKD', title).encode('ASCII', 'ignore').decode('ASCII')
```

### Clase TMDbAPI (reutilizada en múltiples scripts)
- `get_movie_info(title)` - Busca película con fallback ES→EN
- `_title_similarity()` - Usa SequenceMatcher (threshold: 0.6)

## Notas para Claude

- **No crear archivos nuevos** salvo que sea estrictamente necesario
- **Preferir edición** de scripts existentes
- **Los JSON usan UTF-8** con indent=4
- **Imágenes se descargan** automáticamente de TMDB
- **Logs** se guardan en `/logs/` (solo últimos 5)
- **Backups** de equivalencias en `/backups/`
