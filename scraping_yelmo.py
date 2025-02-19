import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import urllib.request
import re
from difflib import SequenceMatcher
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Clase para consultar TMDb
class TMDbAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json;charset=utf-8"
        }
        self.base_url = "https://api.themoviedb.org/3"

    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        try:
            url = f"{self.base_url}/{endpoint}"
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to TMDb: {str(e)}")
            return {}

    def _normalize_title(self, title: str) -> str:
        import unicodedata
        title = unicodedata.normalize('NFKD', title).encode('ASCII', 'ignore').decode('ASCII')
        title = re.sub(r'[^a-zA-Z0-9\s]', '', title)
        return ' '.join(title.lower().split())

    def _title_similarity(self, title1: str, title2: str) -> float:
        return SequenceMatcher(None, self._normalize_title(title1), self._normalize_title(title2)).ratio()

    def get_movie_info(self, title: str) -> dict:
        logger.info(f"Searching TMDb for title: {title}")
        search_results = self._make_request("search/movie", params={"query": title, "language": "es"})

        best_match = None
        highest_similarity = 0

        for result in search_results.get("results", []):
            similarity = self._title_similarity(title, result.get("title", ""))
            if similarity > highest_similarity:
                highest_similarity = similarity
                best_match = result

        if best_match and highest_similarity > 0.6:
            movie_id = best_match["id"]
            details = self._make_request(f"movie/{movie_id}", params={"language": "es"})
            credits = self._make_request(f"movie/{movie_id}/credits", params={"language": "es"})

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

# Crear directorio para las imágenes si no existe
IMAGES_DIR = "imagenes_filmaffinity"
if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)

print("Scraping yelmocines.es...")

headers = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "accept-language": "es-ES,es;q=0.9,de;q=0.8",
    "content-type": "application/json; charset=UTF-8",
    "x-requested-with": "XMLHttpRequest"
}

data = {"cityKey": "navarra"}

response = requests.post(
    "https://www.yelmocines.es/now-playing.aspx/GetNowPlaying",
    headers=headers,
    json=data
)

datos = response.json()

peliculas_filmaffinity = []

MESES = {
    'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
    'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
    'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
}

# Inicializar TMDbAPI
TMDB_API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJiNzAwZmIzYzJlYTU1MTg4YzIzNDMzNjc4NmNiMzhkYSIsIm5iZiI6MTUyMzM1MTY5MS4wMzksInN1YiI6IjVhY2M4MDhiOTI1MTQxMGMwNjAwODMwMiIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.xuYDKvo7dLijGNkJJGidiFj6o2OHWi_FcJJPsQAM2ds"
tmdb_api = TMDbAPI(TMDB_API_KEY)

for cine in datos['d']['Cinemas']:
    for fecha in cine['Dates']:
        fecha_str = fecha['ShowtimeDate']
        dia, mes = fecha_str.split()
        mes_numero = MESES[mes.lower()]
        anoActual = datetime.now().year
        fecha_iso = f"{anoActual}-{mes_numero}-{dia.zfill(2)}"

        for pelicula in fecha['Movies']:
            for formato in pelicula['Formats']:
                if 'VOSE' in formato['Language']:
                    poster_url = pelicula['Poster']
                    poster_filename = os.path.join(IMAGES_DIR, f"{pelicula['Key']}.jpg")

                    if not os.path.exists(poster_filename):
                        urllib.request.urlretrieve(poster_url, poster_filename)

                    tmdb_info = tmdb_api.get_movie_info(pelicula['Title'])
                    if tmdb_info.get('poster_path'):
                        tmdb_poster_url = f"https://image.tmdb.org/t/p/w500{tmdb_info['poster_path']}"
                        tmdb_poster_filename = os.path.join(IMAGES_DIR, f"tmdb_{pelicula['Key']}.jpg")
                        urllib.request.urlretrieve(tmdb_poster_url, tmdb_poster_filename)
                        poster_filename = tmdb_poster_filename

                    pelicula_existente = next(
                        (p for p in peliculas_filmaffinity if p['título'] == pelicula['Title']),
                        None
                    )

                    horarios = [
                        {
                            'fecha': fecha_iso,
                            'hora': s['Time'],
                            'enlace_entradas': f"https://compra.yelmocines.es/?cinemaVistaId={s['VistaCinemaId']}&showtimeVistaId={s['ShowtimeId']}"
                        } for s in formato['Showtimes']
                    ]

                    if pelicula_existente:
                        pelicula_existente['horarios'].extend(horarios)
                    else:
                        info = {
                            'título': pelicula['Title'],
                            'cartel': poster_filename,
                            'horarios': horarios,
                            'cine': f"Yelmo {cine['Name']}",
                            'director': tmdb_info.get('director'),
                            'duración': tmdb_info.get('duración'),
                            'actores': tmdb_info.get('actores'),
                            'sinopsis': tmdb_info.get('sinopsis'),
                            'año': tmdb_info.get('año')
                        }
                        peliculas_filmaffinity.append(info)

with open('peliculas_filmaffinity.json', 'w', encoding='utf-8') as f:
    json.dump(peliculas_filmaffinity, f, ensure_ascii=False, indent=4)

print("Archivo JSON peliculas_filmaffinity.json creado con éxito.")
print("Fin del scraping.")