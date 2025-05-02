# Sistema de Gestión de Películas Adicionales

Este sistema permite scrapear automáticamente las películas en versión original subtitulada (V.O.S.E.) de la Filmoteca de Navarra, así como añadir manualmente otras películas utilizando la API de TMDB.

## Componentes del Sistema

El sistema consta de varios scripts que trabajan juntos:

1. **scraper_modificado.py**: Realiza scraping a la web de Filmoteca de Navarra para extraer películas en V.O.S.E. y guarda la información en un archivo temporal.
2. **integrador.py**: Integra las películas del scraper con las añadidas manualmente, preservando ambas fuentes.
3. **admin_web.py**: Interfaz web para buscar y añadir películas manualmente usando la API de TMDB.
4. **admin_tmdb.py**: Herramienta de línea de comandos para buscar y añadir películas manualmente.
5. **ejecutar.py**: Script principal que permite iniciar cualquiera de los componentes anteriores.

## Requisitos

- Python 3.6+
- Clave API de TMDB (The Movie Database)
- Paquetes: `python-dotenv`, `requests`, `beautifulsoup4`, `flask`

## Instalación

1. Clona este repositorio o descarga todos los archivos.
2. Instala las dependencias requeridas:

```bash
pip install python-dotenv requests beautifulsoup4 flask
```

3. Crea un archivo `.env` en el directorio raíz con tu clave API de TMDB:

```
TMDB_API_KEY=tu_clave_api_de_tmdb
```

Puedes obtener una clave API gratuita registrándote en [The Movie Database](https://www.themoviedb.org/settings/api).

## Uso

### Script Unificado

La forma más sencilla de usar el sistema es a través del script `ejecutar.py`:

```bash
# Ver opciones disponibles
python ejecutar.py --help

# Ejecutar solo el scraper (actualizar películas de la filmoteca)
python ejecutar.py --scraper

# Ejecutar solo el integrador (combinar películas automáticas y manuales)
python ejecutar.py --integrador

# Ejecutar el proceso completo (scraper + integrador)
python ejecutar.py --completo

# Iniciar el administrador web
python ejecutar.py --admin-web

# Iniciar el administrador por consola
python ejecutar.py --admin-consola
```

### Uso del Administrador Web

1. Inicia el administrador web:

```bash
python ejecutar.py --admin-web
```

2. Abre tu navegador web y ve a `http://127.0.0.1:5000/`
3. Desde la interfaz podrás:
   - Ver las películas existentes
   - Buscar películas en TMDB
   - Añadir nuevas películas con información de cine y horarios
   - Editar o eliminar películas existentes

### Uso del Administrador por Consola

Si prefieres una interfaz de línea de comandos:

```bash
python ejecutar.py --admin-consola
```

Sigue las instrucciones en pantalla para buscar y añadir películas.

## Flujo de Trabajo Recomendado

1. Ejecuta el proceso completo para actualizar las películas de la filmoteca:

```bash
python ejecutar.py --completo
```

2. Utiliza el administrador web para añadir manualmente películas adicionales:

```bash
python ejecutar.py --admin-web
```

3. Repite el proceso cuando necesites actualizar las películas.

## Estructura de Archivos

- `scraper_modificado.py`: Script de scraping para la web de la filmoteca
- `integrador.py`: Integrador de películas automáticas y manuales
- `admin_web.py`: Administrador web basado en Flask
- `admin_tmdb.py`: Administrador de línea de comandos
- `ejecutar.py`: Script unificado para ejecutar todos los componentes
- `peliculas_filmoteca.json`: Archivo principal con todas las películas
- `equivalencias_peliculas.json`: Archivo para mapeo de títulos a IDs de TMDB
- `imagenes_filmoteca/`: Directorio donde se guardan los carteles de películas

## Notas Adicionales

- Las películas añadidas manualmente se preservarán incluso después de ejecutar el scraper.
- El sistema detecta y elimina automáticamente las sesiones con fechas pasadas.
- Para cada película, el sistema intentará encontrar información detallada en TMDB.
- Si el sistema no encuentra una película en TMDB, se añadirá a `equivalencias_peliculas.json` para mapeo manual.
