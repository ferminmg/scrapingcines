# Instrucciones para Claude Code

## Contexto Rápido

Este proyecto es un **sistema de scraping de carteleras de cines** en Navarra, España. Se ejecuta automáticamente cada 4 horas via GitHub Actions.

## Archivos Clave que Debo Conocer

| Si quieres... | Edita este archivo |
|--------------|-------------------|
| Modificar scraping Filmoteca | `scraper_modificado.py` |
| Cambiar integración de datos | `integrador.py` |
| Modificar scraping Golem | `scraping_golem.py` |
| Modificar scraping Yelmo | `scraping_yelmo.py` |
| Cambiar próximos estrenos | `proximos_estrenos.py` |
| Modificar críticas blog | `scrape_ghostintheblog.py` |
| Cambiar interfaz web admin | `admin_web.py` + `templates/` |
| Cambiar automatización | `.github/workflows/main.yml` |
| Añadir dependencia Python | `requirements.txt` |
| Mapear título→TMDB | `equivalencias_peliculas.json` |

## Comandos que Usaré Frecuentemente

```bash
# Ejecutar scraping completo
python ejecutar.py --completo

# Probar un scraper específico
python scraping_golem.py
python scraping_yelmo.py

# Iniciar admin web para pruebas
python ejecutar.py --admin-web
```

## Patrones que Debo Seguir

### Al crear/modificar scrapers:
1. Usar la clase `TMDbAPI` existente para búsquedas
2. Normalizar títulos con `unicodedata.normalize('NFKD', ...)`
3. Guardar JSON con `ensure_ascii=False, indent=4`
4. Implementar logging a `/logs/`

### Al modificar estructuras JSON:
- Mantener campos existentes para compatibilidad
- `horarios` siempre es array de `{fecha, hora, enlace_entradas}`
- `cartel` es ruta relativa a imagen local

### Al modificar GitHub Actions:
- El workflow está en `.github/workflows/main.yml`
- Secrets disponibles: `TMDB_API_KEY`, `GITHUB_TOKEN`
- Commit automático con mensaje "🔄 Actualización automática - fecha UTC"

## Dependencias del Proyecto

```
python-dotenv==1.0.0   # Variables de entorno
requests==2.31.0       # HTTP requests
beautifulsoup4==4.12.2 # Parsing HTML
flask==3.0.0           # Admin web
lxml==4.9.3            # Parser XML
```

## Variables de Entorno

Archivo `.env` debe contener:
```
TMDB_API_KEY=xxxxx
```

## Errores Comunes y Soluciones

| Error | Solución |
|-------|----------|
| `TMDB_API_KEY not found` | Crear archivo `.env` con la key |
| `ModuleNotFoundError` | `pip install -r requirements.txt` |
| Película no encontrada en TMDB | Añadir manualmente a `equivalencias_peliculas.json` |
| Horarios duplicados | `integrador.py` los deduplica automáticamente |

## Flujo de Trabajo Típico

1. **Modificar código** → Probar localmente con `python ejecutar.py --completo`
2. **Commit y push** → GitHub Actions ejecuta automáticamente
3. **Verificar** → Actions tab muestra logs de ejecución
4. **Datos publicados** → GitHub Pages sirve los JSON

## Notas Importantes

- **NO** crear archivos nuevos salvo que sea estrictamente necesario
- **Preferir** editar scripts existentes
- Los scrapers pueden fallar si los sitios web cambian su estructura HTML
- TMDB tiene rate limiting, las búsquedas incluyen `time.sleep(0.3)`
- El proyecto usa **worktrees de git** (directorio actual es un worktree)
