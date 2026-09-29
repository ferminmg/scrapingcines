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

    def get_movie_info(self, title: str) -> dict:
        logger.info(f"Searching TMDb for title: {title}")

        search_results = self._make_request("search/movie", params={"query": title, "language": "es"})

        if not search_results or not search_results.get("results"):
            logger.warning(f"No results found for '{title}' in Spanish. Trying English search...")
            search_results = self._make_request("search/movie", params={"query": title, "language": "en"})

        if not search_results or not search_results.get("results"):
            logger.warning(f"No results found for: {title} in any language.")
            return {}

        results = sorted(search_results["results"], key=lambda x: x.get("release_date", "1900-01-01"), reverse=True)

        for result in results:
            similarity = self._title_similarity(title, result.get("title", ""))
            if similarity > 0.6:
                movie_id = result["id"]
                logger.info(f"Checking match: {result.get('title')} (ID: {movie_id}, Similarity: {similarity})")

                details = self._make_request(f"movie/{movie_id}", params={"language": "es"})
                if not details:
                    details = self._make_request(f"movie/{movie_id}", params={"language": "en"})

                credits = self._make_request(f"movie/{movie_id}/credits", params={"language": "es"})
                if not credits:
                    credits = self._make_request(f"movie/{movie_id}/credits", params={"language": "en"})

                if not details or not credits:
                    continue

                runtime = details.get('runtime')
                if runtime and runtime < 40:
                    logger.warning(f"Movie {title} with id: {movie_id} discarded because its a short film, duration of: {runtime} minutes")
                    continue

                logger.info(f"Found good match: {result.get('title')} (ID: {movie_id}, Similarity: {similarity})")
                return {
                    "director": ", ".join(c["name"] for c in credits.get("crew", []) if c["job"] == "Director"),
                    "duración": f"{details.get('runtime', 'Desconocido')} min",
                    "actores": ", ".join(a["name"] for a in credits.get("cast", [])[:5]),
                    "sinopsis": details.get("overview"),
                    "año": details.get("release_date", "")[:4],
                    "poster_path": details.get("poster_path")
                }

        logger.warning(f"No good match found for: {title}")
        return {}


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

class MovieScraper:
    def __init__(self, tmdb_api: TMDbAPI, image_downloader: ImageDownloader):
        self.tmdb_api = tmdb_api
        self.image_downloader = image_downloader
        # La misma película sale muchos días: una sola consulta a TMDb
        self._cache_tmdb: Dict[str, tuple] = {}

    def buscar_tmdb(self, titulo: str) -> tuple:
        """Devuelve (título a mostrar, info de TMDb). Si el título completo no
        se encuentra y lleva un prefijo de ciclo ('SSPNA: ...'), prueba sin él."""
        if titulo in self._cache_tmdb:
            return self._cache_tmdb[titulo]
        resultado = (titulo, self.tmdb_api.get_movie_info(titulo))
        if not resultado[1]:
            sin_prefijo = quitar_prefijo_ciclo(titulo)
            if sin_prefijo:
                info = self.tmdb_api.get_movie_info(sin_prefijo)
                if info:
                    resultado = (sin_prefijo, info)
        self._cache_tmdb[titulo] = resultado
        return resultado

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
                    
                    # Get TMDb information
                    titulo_golem = clean_title
                    clean_title, tmdb_info = self.buscar_tmdb(titulo_golem)
                    # Si se quitó el prefijo del ciclo, se guarda como nota
                    nota = titulo_golem.split(':', 1)[0].strip() if clean_title != titulo_golem else None
                    
                    # Get TMDb poster if available
                    image_path = fallback_image_path
                    if tmdb_info.get('poster_path'):
                        poster_url = f"https://image.tmdb.org/t/p/w500{tmdb_info['poster_path']}"
                        
                        # Generate a safe filename for the TMDb poster in lowercase
                        safe_filename = f"tmdb_{clean_title.lower()}.jpg"
                        
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
                        director=tmdb_info.get('director'),
                        duración=tmdb_info.get('duración'),
                        actores=tmdb_info.get('actores'),
                        sinopsis=tmdb_info.get('sinopsis'),
                        año=tmdb_info.get('año'),
                        nota=nota
                    ))
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error scraping {url}: {str(e)}")
                continue
                
        return movies

# Campos de metadatos que aporta TMDb (gana la primera aparición que traiga valor)
CAMPOS_TMDB = ('director', 'duración', 'actores', 'sinopsis', 'año', 'nota')

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