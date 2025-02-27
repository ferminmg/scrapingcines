import os
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta
import logging
from pathlib import Path
from dataclasses import dataclass
import re
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
    enlace_entradas: Optional[str]

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
        import unicodedata
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

    def get_movie_info(self, title: str) -> Dict:
        """Get complete movie information from TMDb"""
        # Log the original title
        logger.info(f"Searching TMDb for title: {title}")
        
        # Search with different variants of the title
        search_variants = [
            title,  # Original title
            title.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u"),  # Without accents
            re.sub(r'\([^)]*\)', '', title).strip(),  # Remove text in parentheses
            ' '.join(title.split()),  # Remove extra spaces
        ]
        
        best_match = None
        highest_similarity = 0
        
        for variant in search_variants:
            logger.info(f"Trying variant: {variant}")
            search_results = self._make_request(
                "search/movie",
                params={"query": variant, "language": "es"}
            )
            
            if not search_results or not search_results.get("results"):
                continue
                
            # Check each result for the best match
            for result in search_results["results"]:
                # Check both original title and localized title
                titles_to_check = [
                    result.get("title", ""),
                    result.get("original_title", "")
                ]
                
                for result_title in titles_to_check:
                    similarity = self._title_similarity(title, result_title)
                    logger.info(f"Comparing '{title}' with '{result_title}': {similarity}")
                    
                    if similarity > highest_similarity:
                        highest_similarity = similarity
                        best_match = result
        
        # If we found a good match (similarity > 0.6)
        if best_match and highest_similarity > 0.6:
            movie_id = best_match["id"]
            logger.info(f"Found match: {best_match.get('title')} (ID: {movie_id}, Similarity: {highest_similarity})")
            
            # Get detailed information
            details = self._make_request(f"movie/{movie_id}", params={"language": "es"})
            credits = self._make_request(f"movie/{movie_id}/credits", params={"language": "es"})
            
            if not details or not credits:
                return {}
            
            return {
                "director": ", ".join(
                    c["name"] for c in credits.get("crew", [])
                    if c["job"] == "Director"
                ),
                "duración": f"{details.get('runtime', 'Desconocido')} min",
                "actores": ", ".join(
                    a["name"] for a in credits.get("cast", [])[:5]
                ),
                "sinopsis": details.get("overview"),
                "año": details.get("release_date", "")[:4],
                "poster_path": details.get('poster_path')
            }
        
        logger.warning(f"No good match found for: {title}")
        return {}

class ImageDownloader:
    def __init__(self, base_folder: str):
        self.base_folder = Path(base_folder)
        self.base_folder.mkdir(exist_ok=True)
    
    def download(self, url: str, filename: Optional[str] = None) -> Optional[str]:
        """Download an image and return its local path"""
        if not url.startswith("http"):
            url = f"https://golem.es{url}"
            
        try:
            if filename:
                filepath = self.base_folder / filename
            else:
                filepath = self.base_folder / os.path.basename(url)
            
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

class MovieScraper:
    def __init__(self, tmdb_api: TMDbAPI, image_downloader: ImageDownloader):
        self.tmdb_api = tmdb_api
        self.image_downloader = image_downloader

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
                    
                    # Filter VOSE movies: only those with "V.O.S.E" in the title
                    if "V.O.S.E" not in title:
                        continue
                        
                    clean_title = title.replace("(V.O.S.E.)", "").strip()
                    clean_title = clean_title.replace("(V.O.S.E)", "").strip()
                    
                    # Get poster from Golem
                    poster_elem = movie_table.find('img', {'class': 'bordeCartel'})
                    fallback_image_path = None
                    if poster_elem and 'src' in poster_elem.attrs:
                        fallback_image_path = self.image_downloader.download(poster_elem['src'])
                    
                    # Get TMDb information
                    tmdb_info = self.tmdb_api.get_movie_info(clean_title)
                    
                    # Get TMDb poster if available
                    image_path = fallback_image_path
                    if tmdb_info.get('poster_path'):
                        poster_url = f"https://image.tmdb.org/t/p/w500{tmdb_info['poster_path']}"
                        tmdb_image_path = self.image_downloader.download(
                            poster_url,
                            f"tmdb_{clean_title.lower().replace(' ', '_')}.jpg"
                        )
                        if tmdb_image_path:
                            image_path = tmdb_image_path
                    
                    # Get schedules
                    schedules = []
                    for schedule in movie_table.find_all('span', {'class': 'horaXXXL'}):
                        time = schedule.get_text(strip=True)
                        ticket_link = schedule.find('a', href=True)
                        ticket_url = None
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
                        año=tmdb_info.get('año')
                    ))
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error scraping {url}: {str(e)}")
                continue
                
        return movies

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
    DAYS_TO_SCRAPE = 10

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

    # Convert dataclass objects to dictionaries before JSON serialization
    movies_data = [dataclass_to_dict(movie) for movie in all_movies]

    # Save results
    output_path = Path(OUTPUT_FILE)
    with output_path.open('w', encoding='utf-8') as f:
        json.dump(movies_data, f, indent=4, ensure_ascii=False)
    
    logger.info(f"Results saved to {output_path}")

if __name__ == "__main__":
    main()