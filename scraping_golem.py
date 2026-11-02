import os
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta
import logging
from pathlib import Path
from dataclasses import dataclass
import re
import unicodedata
from typing import List, Dict, Optional
from dotenv import load_dotenv


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class MovieSchedule:
    fecha: str
    hora: str
    enlace_entradas: str

@dataclass
class Movie:
    título: str
    cartel: str
    horarios: List[MovieSchedule]
    cine: str
    director: Optional[str] = None
    duración: Optional[str] = None
    actores: Optional[str] = None
    sinopsis: Optional[str] = None
    año: Optional[str] = None
    tmdb_id: Optional[int] = None
    # Ciclo o detalle de la sesión ('KLASIKOAK 2026', 'SSPNA'...)
    nota: Optional[str] = None

class TMDbAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json;charset=utf-8"
        }
        self.base_url = "https://api.themoviedb.org/3"
    
    def _make_request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        """Make a request to TMDb API with error handling"""
        try:
            url = f"{self.base_url}/{endpoint}"
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to TMDb: {str(e)}")
            return None

    def _normalize_title(self, title: str) -> str:
        """Normalize title for better matching"""
        # Normalize unicode characters
        title = unicodedata.normalize('NFKD', title).encode('ASCII', 'ignore').decode('ASCII')
        # Remove special characters but keep spaces
        title = re.sub(r'[^a-zA-Z0-9\s]', '', title)
        # Convert to lowercase and remove extra spaces
        return ' '.join(title.lower().split())

    def _title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles"""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, 
                             self._normalize_title(title1), 
                             self._normalize_title(title2)).ratio()

    @staticmethod
    def _nombre(texto: str) -> str:
        texto = unicodedata.normalize('NFKD', texto or '').encode('ASCII', 'ignore').decode('ASCII')
        return ' '.join(re.sub(r'[^a-zA-Z0-9\s]', ' ', texto).lower().split())

    def _mismo_director(self, directores_golem: str, directores_tmdb: List[str]) -> bool:
        """¿Coincide algún director de Golem con alguno de TMDb? Se compara el
        nombre normalizado (sin acentos ni puntuación) y, si no, el apellido."""
        # Los nombres en otros alfabetos quedan vacíos al normalizar: fuera,
        # porque una cadena vacía 'estaría contenida' en cualquier nombre
        tmdb = [n for n in (self._nombre(d) for d in directores_tmdb if d) if n]
        for director in re.split(r',| y | and |&', directores_golem or ''):
            nombre = self._nombre(director)
            if not nombre:
                continue
            for candidato in tmdb:
                if nombre == candidato or nombre in candidato or candidato in nombre:
                    return True
                if nombre.split()[-1] == candidato.split()[-1] and len(nombre.split()[-1]) > 3:
                    return True
        return False

    def get_movie_info(self, titulos, director: str = None, duracion: int = None) -> dict:
        """Busca la película en TMDb por uno o varios títulos (el de Golem, el
        original...). Si se conoce el director (ficha de Golem), solo se acepta
        un resultado con ese director: así no se confunde 'The Debut' con
        'K-Pop: The Debut' ni el Casablanca de 1942 con un documental de 2023.
        Sin director, se descartan los cortos y se prefiere la duración
        parecida y la película más popular (antes ganaba la más reciente)."""
        if isinstance(titulos, str):
            titulos = [titulos]
        titulos = [t for t in dict.fromkeys(t.strip() for t in titulos if t and t.strip())]
        logger.info(f"Searching TMDb for: {titulos} (director: {director}, duración: {duracion})")

        candidatos = {}
        for consulta in titulos:
            for idioma in ("es", "en"):
                datos = self._make_request("search/movie", params={"query": consulta, "language": idioma})
                for r in (datos or {}).get("results", []):
                    if r.get("id"):
                        candidatos.setdefault(r["id"], r)
        if not candidatos:
            logger.warning(f"No results found for: {titulos}")
            return {}

        puntuados = []
        for r in candidatos.values():
            nombres = [n for n in (r.get("title"), r.get("original_title")) if n]
            similitud = max((self._title_similarity(t, n) for t in titulos for n in nombres), default=0)
            if similitud > 0.6:
                puntuados.append((round(similitud, 2), r.get("popularity") or 0, r))
        puntuados.sort(key=lambda x: (x[0], x[1]), reverse=True)

        reserva = None
        for similitud, _, r in puntuados[:10]:
            movie_id = r["id"]
            details = self._make_request(f"movie/{movie_id}", params={"language": "es"})
            credits = self._make_request(f"movie/{movie_id}/credits", params={"language": "es"})
            if not details or not credits:
                continue
            runtime = details.get('runtime') or 0
            if 0 < runtime < 40:
                logger.info(f"Descartado {r.get('title')} ({movie_id}): corto de {runtime} min")
                continue
            directores = [c["name"] for c in credits.get("crew", []) if c.get("job") == "Director"]
            if director:
                if not self._mismo_director(director, directores):
                    logger.info(f"Descartado {r.get('title')} ({movie_id}): director {directores}, Golem dice {director}")
                    continue
            elif duracion and runtime and abs(runtime - duracion) > 15:
                # Sin director, una duración muy distinta queda solo como reserva
                reserva = reserva or (r, details, credits, directores)
                continue

            logger.info(f"Found good match: {r.get('title')} (ID: {movie_id}, similitud: {similitud})")
            return self._info(movie_id, details, credits, directores)

        if reserva and not director:
            r, details, credits, directores = reserva
            return self._info(r["id"], details, credits, directores)
        logger.warning(f"No good match found for: {titulos}")
        return {}

    def _info(self, movie_id, details, credits, directores) -> dict:
        sinopsis = (details.get("overview") or "").strip()
        sinopsis_en = ""
        if not sinopsis:
            detalles_en = self._make_request(f"movie/{movie_id}", params={"language": "en"})
            sinopsis_en = ((detalles_en or {}).get("overview") or "").strip()
        runtime = details.get('runtime') or 0
        return {
            "tmdb_id": movie_id,
            "director": ", ".join(directores),
            "duración": f"{runtime} min" if runtime else "",
            "actores": ", ".join(a["name"] for a in credits.get("cast", [])[:5]),
            "sinopsis": sinopsis,
            "sinopsis_en": sinopsis_en,
            "año": (details.get("release_date") or "")[:4],
            "poster_path": details.get("poster_path")
        }


# El nombre del cartel de TMDb sale de su ruta en TMDb (única por imagen), no
# del título: si el emparejamiento cambia, cambia también la URL y la app no
# sigue mostrando el cartel anterior que guarda en caché (21 días por URL).
def nombre_cartel_tmdb(poster_path: str) -> str:
    base = re.sub(r'[^A-Za-z0-9_-]', '', os.path.splitext(os.path.basename(poster_path or ''))[0])
    return f"tmdb_{base}.jpg"

class ImageDownloader:
    def __init__(self, base_folder: str):
        self.base_folder = Path(base_folder)
        self.base_folder.mkdir(exist_ok=True)
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to remove special characters and accents, convert to lowercase"""
        # Normalize unicode characters (convert accented chars to their basic form)
        filename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore').decode('ASCII')
        # Convert to lowercase
        filename = filename.lower()
        # Replace spaces with underscores
        filename = filename.replace(' ', '_')
        # Remove any remaining non-alphanumeric characters except underscore
        filename = re.sub(r'[^a-z0-9_.]', '', filename)
        # Ensure the filename isn't too long
        if len(filename) > 200:
            filename = filename[:200]
        return filename
    
    def download(self, url: str, filename: Optional[str] = None) -> Optional[str]:
        """Download an image and return its local path"""
        if not url.startswith("http"):
            url = f"https://golem.es{url}"
            
        try:
            if filename:
                # Sanitize the provided filename
                sanitized_filename = self.sanitize_filename(filename)
                filepath = self.base_folder / sanitized_filename
            else:
                # Get filename from URL and sanitize it
                url_filename = os.path.basename(url)
                sanitized_filename = self.sanitize_filename(url_filename)
                filepath = self.base_folder / sanitized_filename
            
            # Check if image already exists
            if filepath.exists():
                logger.info(f"Image already downloaded: {filepath}")
                return str(filepath)
            
            logger.info(f"Downloading image: {url}")
            response = requests.get(url)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            return str(filepath)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading image: {str(e)}")
            return None

# Marca de versión original subtitulada en el título de Golem:
# '(V.O.S.E.)', '(V.O.S.E)', '(VOSE)', '(V.O.S.E. + V.O.S.E.U.)'...
PATRON_VOSE = re.compile(r'\bV\.?\s*O\.?\s*S\.?\s*E\b', re.IGNORECASE)
PATRON_PARENTESIS_VOSE = re.compile(r'\s*\([^)]*\bV\.?\s*O\.?\s*S\.?\s*E[^)]*\)', re.IGNORECASE)

def es_vose(titulo: str) -> bool:
    return bool(PATRON_VOSE.search(titulo or ''))

def limpiar_titulo(titulo: str) -> str:
    """Quita la marca de VOSE: 'Casablanca (V.O.S.E.)' -> 'Casablanca'."""
    limpio = PATRON_PARENTESIS_VOSE.sub('', titulo)
    limpio = PATRON_VOSE.sub('', limpio)
    return ' '.join(limpio.split()).strip(' -') or titulo.strip()

def quitar_prefijo_ciclo(titulo: str) -> Optional[str]:
    """'SSPNA: Fatherland' -> 'Fatherland', 'KLASIKOAK 2026: Casablanca' ->
    'Casablanca'. Devuelve None si no hay un prefijo corto de ciclo."""
    if ':' not in titulo:
        return None
    prefijo, resto = titulo.split(':', 1)
    prefijo, resto = prefijo.strip(), resto.strip()
    if not resto or len(prefijo.split()) > 4:
        return None
    # Solo prefijos con pinta de ciclo ('SSPNA', 'KLASIKOAK 2026', 'Doc del
    # mes'), no subtítulos de la propia película ('Vengadores Endgame: Encore')
    if prefijo != prefijo.upper() and not re.match(r'(docs?|ciclo|cine|klasikoak|sspna)\b', prefijo, re.IGNORECASE):
        return None
    return resto

ETIQUETAS_FICHA = ('Ficha Técnica', 'Estreno', 'Título original', 'Dirigida por',
                   'Duración', 'Nacionalidad', 'Ficha Artística')

def parsear_ficha_golem(html: str) -> dict:
    """Datos de la ficha de una película en golem.es ('/golem/pelicula/...'):
    '.txtNegL' trae 'Título original: ... Dirigida por: ... Duración: 105 min.
    Nacionalidad: ... Ficha Artística: ...' y '.txtNegLJust' la sinopsis."""
    soup = BeautifulSoup(html, 'html.parser')
    datos = {}
    ficha = soup.find(class_='txtNegL')
    if ficha:
        texto = ' '.join(ficha.get_text(' ', strip=True).split())
        patron = '|'.join(re.escape(e) for e in ETIQUETAS_FICHA)
        for coincidencia in re.finditer(rf'({patron}):\s*(.*?)(?=\s*(?:{patron}):|$)', texto):
            etiqueta, valor = coincidencia.group(1), coincidencia.group(2).strip().rstrip('.').strip()
            if not valor:
                continue
            if etiqueta == 'Título original':
                datos['titulo_original'] = valor
            elif etiqueta == 'Dirigida por':
                datos['director'] = valor
            elif etiqueta == 'Duración':
                minutos = re.search(r'\d+', valor)
                if minutos and int(minutos.group(0)) > 0:
                    datos['duracion'] = int(minutos.group(0))
            elif etiqueta == 'Ficha Artística' and valor.upper() != 'DOCUMENTAL':
                datos['actores'] = valor
    sinopsis = soup.find(class_='txtNegLJust')
    if sinopsis:
        texto = ' '.join(sinopsis.get_text(' ', strip=True).split())
        texto = re.sub(r'^Sinopsis( corta)?\s*:?\s*', '', texto, flags=re.IGNORECASE)
        # 'Presenta: FULANO, Director de...' (ciclos con presentación)
        texto = re.split(r'\s*Presenta\s*:', texto)[0].strip()
        if len(texto) >= 60:
            datos['sinopsis'] = texto
    return datos

class MovieScraper:
    def __init__(self, tmdb_api: TMDbAPI, image_downloader: ImageDownloader):
        self.tmdb_api = tmdb_api
        self.image_downloader = image_downloader
        # La misma película sale muchos días: una sola consulta por película
        self._cache_tmdb: Dict[str, tuple] = {}
        self._cache_fichas: Dict[str, dict] = {}

    def ficha(self, href: Optional[str]) -> dict:
        """Ficha de la película en golem.es (vacía si no hay enlace o falla)."""
        if not href:
            return {}
        url = href if href.startswith('http') else f"https://golem.es{href if href.startswith('/') else '/' + href}"
        if url not in self._cache_fichas:
            try:
                respuesta = requests.get(url, timeout=30)
                respuesta.raise_for_status()
                self._cache_fichas[url] = parsear_ficha_golem(respuesta.text)
            except requests.exceptions.RequestException as e:
                logger.warning(f"No se pudo leer la ficha {url}: {e}")
                self._cache_fichas[url] = {}
        return self._cache_fichas[url]

    def buscar_tmdb(self, titulo: str, ficha: Optional[dict] = None) -> tuple:
        """Devuelve (título a mostrar, info de TMDb). Un prefijo de ciclo
        ('SSPNA: ...', 'KLASIKOAK 2026: ...') se quita del título a mostrar;
        se busca por ese título y por el original de la ficha de Golem, y el
        director de la ficha confirma que es la película correcta."""
        ficha = ficha or {}
        if titulo in self._cache_tmdb:
            return self._cache_tmdb[titulo]
        mostrado = quitar_prefijo_ciclo(titulo) or titulo
        consultas = [mostrado, ficha.get('titulo_original'), titulo]
        info = self.tmdb_api.get_movie_info(consultas, ficha.get('director'), ficha.get('duracion'))
        self._cache_tmdb[titulo] = (mostrado, info)
        return self._cache_tmdb[titulo]

    def scrape_cinema(self, base_url: str, cinema_name: str, days: int) -> List[Movie]:
        """Scrape movie information for a specific cinema"""
        movies = []
        
        for i in range(days):
            date = datetime.now() + timedelta(days=i)
            date_str = date.strftime('%Y%m%d')
            formatted_date = date.strftime('%Y-%m-%d')
            
            url = f"{base_url}/{date_str}"
            try:
                logger.info(f"Processing URL: {url}")
                response = requests.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all movies in the page
                for movie_table in soup.find_all('table', {'background': '#AEAEAE'}):
                    title_elem = movie_table.find('a', {'class': 'txtNegXXL'})
                    if not title_elem:
                        continue
                        
                    title = title_elem.get_text(strip=True)
                    
                    # Solo películas en VOSE (Golem lo indica en el título)
                    if not es_vose(title):
                        continue

                    clean_title = limpiar_titulo(title)
                    
                    # Get poster from Golem
                    poster_elem = movie_table.find('img', {'class': 'bordeCartel'})
                    fallback_image_path = None
                    if poster_elem and 'src' in poster_elem.attrs:
                        fallback_image_path = self.image_downloader.download(poster_elem['src'])
                    
                    # Ficha de Golem (título original, director, sinopsis...) y TMDb
                    titulo_golem = clean_title
                    ficha = self.ficha(title_elem.get('href'))
                    clean_title, tmdb_info = self.buscar_tmdb(titulo_golem, ficha)
                    # Si se quitó el prefijo del ciclo, se guarda como nota
                    nota = titulo_golem.split(':', 1)[0].strip() if clean_title != titulo_golem else None
                    
                    # Get TMDb poster if available
                    image_path = fallback_image_path
                    if tmdb_info.get('poster_path'):
                        poster_url = f"https://image.tmdb.org/t/p/w500{tmdb_info['poster_path']}"
                        
                        # Generate a safe filename for the TMDb poster in lowercase
                        safe_filename = nombre_cartel_tmdb(tmdb_info['poster_path'])
                        
                        tmdb_image_path = self.image_downloader.download(
                            poster_url,
                            safe_filename
                        )
                        if tmdb_image_path:
                            image_path = tmdb_image_path
                    
                    # Get schedules
                    schedules = []
                    for schedule in movie_table.find_all('span', {'class': 'horaXXXL'}):
                        time = schedule.get_text(strip=True)
                        ticket_link = schedule.find('a', href=True)
                        # Siempre texto: las versiones publicadas de la app
                        # descartan la película entera si llega null
                        ticket_url = ""
                        if ticket_link and 'href' in ticket_link.attrs:
                            ticket_url = f"https://golem.es{ticket_link['href']}"
                        
                        schedules.append(MovieSchedule(
                            fecha=formatted_date,
                            hora=time,
                            enlace_entradas=ticket_url
                        ))
                    
                    # Add movie to results
                    movies.append(Movie(
                        título=clean_title,
                        cartel=image_path or "",
                        horarios=schedules,
                        cine=cinema_name,
                        # Primero TMDb en castellano; si falta, la ficha de Golem;
                        # la sinopsis de TMDb en inglés, como último recurso
                        director=tmdb_info.get('director') or ficha.get('director'),
                        duración=tmdb_info.get('duración') or (f"{ficha['duracion']} min" if ficha.get('duracion') else None),
                        actores=tmdb_info.get('actores') or ficha.get('actores'),
                        sinopsis=tmdb_info.get('sinopsis') or ficha.get('sinopsis') or tmdb_info.get('sinopsis_en') or None,
                        año=tmdb_info.get('año'),
                        tmdb_id=tmdb_info.get('tmdb_id'),
                        nota=nota
                    ))
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error scraping {url}: {str(e)}")
                continue
                
        return movies

# Campos de metadatos que aporta TMDb (gana la primera aparición que traiga valor)
CAMPOS_TMDB = ('director', 'duración', 'actores', 'sinopsis', 'año', 'nota', 'tmdb_id')

def merge_movies(movies: List[Movie]) -> List[Movie]:
    """Fusiona duplicados por (cine, título): junta los horarios de todos los
    días y conserva los metadatos de la primera aparición (el cartel y los
    campos de TMDb solo se rellenan si la primera vez venían vacíos)."""
    fusionadas: Dict[tuple, Movie] = {}
    for movie in movies:
        clave = (movie.cine, movie.título)
        existente = fusionadas.get(clave)
        if existente is None:
            fusionadas[clave] = movie
            continue
        existente.horarios.extend(movie.horarios)
        if not existente.cartel and movie.cartel:
            existente.cartel = movie.cartel
        for campo in CAMPOS_TMDB:
            if not getattr(existente, campo) and getattr(movie, campo):
                setattr(existente, campo, getattr(movie, campo))
    return list(fusionadas.values())

def dataclass_to_dict(obj):
    """Convert a dataclass instance to a dictionary"""
    if hasattr(obj, '__dataclass_fields__'):
        return {k: dataclass_to_dict(v) for k, v in vars(obj).items()}
    elif isinstance(obj, list):
        return [dataclass_to_dict(item) for item in obj]
    return obj

def main():
    # Configuration
    load_dotenv()
    TMDB_API_KEY = os.getenv("TMDB_API_KEY")
    if not TMDB_API_KEY:
        raise ValueError("TMDB_API_KEY environment variable is required")

    CINEMAS = [
        {"base_url": "https://golem.es/golem/golem-baiona", "name": "Golem Baiona"},
        {"base_url": "https://golem.es/golem/golem-yamaguchi", "name": "Golem Yamaguchi"},
        {"base_url": "https://golem.es/golem/golem-la-morea", "name": "Golem La Morea"}
    ]
    
    IMAGES_FOLDER = "imagenes_peliculas"
    OUTPUT_FILE = "peliculas_vose.json"
    # Golem publica la programación de unas tres semanas (ciclos, clásicos...)
    DAYS_TO_SCRAPE = 21

    # Initialize components
    tmdb_api = TMDbAPI(TMDB_API_KEY)
    image_downloader = ImageDownloader(IMAGES_FOLDER)
    scraper = MovieScraper(tmdb_api, image_downloader)

    # Scrape all cinemas
    all_movies = []
    for cinema in CINEMAS:
        logger.info(f"Scraping {cinema['name']}...")
        movies = scraper.scrape_cinema(
            cinema["base_url"],
            cinema["name"],
            DAYS_TO_SCRAPE
        )
        all_movies.extend(movies)

    # Una sola entrada por (cine, película) con todas las sesiones
    all_movies = merge_movies(all_movies)

    # Convert dataclass objects to dictionaries before JSON serialization
    movies_data = [dataclass_to_dict(movie) for movie in all_movies]

    # Save results
    output_path = Path(OUTPUT_FILE)
    with output_path.open('w', encoding='utf-8') as f:
        json.dump(movies_data, f, indent=4, ensure_ascii=False)
    
    logger.info(f"Results saved to {output_path}")

if __name__ == "__main__":
    main()