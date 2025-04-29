#!/usr/bin/env python3
"""
Script mejorado para obtener los próximos estrenos de películas en España usando la API de TMDB.
Genera un archivo JSON con la información estructurada de los próximos estrenos,
descarga los pósters de las películas, y evita descargas y actualizaciones innecesarias.
"""

import os
import json
import logging
import argparse
from datetime import datetime
import requests
import urllib.request
import re
import hashlib
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
if not TMDB_API_KEY:
    logger.error("No se ha encontrado la clave API de TMDB. Crea un archivo .env con TMDB_API_KEY=tu_clave")
    exit(1)

class TMDbAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json;charset=utf-8"
        }
        self.base_url = "https://api.themoviedb.org/3"
    
    def _make_request(self, endpoint, params=None):
        """Realiza una petición a la API de TMDB"""
        try:
            url = f"{self.base_url}/{endpoint}"
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error en la petición a TMDB: {str(e)}")
            return {}
    
    def get_upcoming_movies(self, region="ES", language="es-ES", page=1):
        """Obtiene los próximos estrenos para una región específica"""
        params = {
            "region": region,
            "language": language,
            "page": page
        }
        return self._make_request("movie/upcoming", params)
    
    def get_movie_details(self, movie_id, language="es-ES"):
        """Obtiene detalles completos de una película"""
        params = {"language": language, "append_to_response": "credits,release_dates"}
        return self._make_request(f"movie/{movie_id}", params)
    
    def get_movie_images(self, movie_id, language="es-ES"):
        """Obtiene imágenes de una película"""
        params = {
            "language": language,
            "include_image_language": f"{language},null"
        }
        return self._make_request(f"movie/{movie_id}/images", params)
    
    def download_poster(self, poster_path, movie_title, folder="imagenes_estrenos", size="w500"):
        """Descarga el póster de una película si no existe ya"""
        if not poster_path:
            return ""
        
        # Asegurar que existe el directorio
        if not os.path.exists(folder):
            os.makedirs(folder)
        
        # Crear nombre del archivo sanitizando el título
        sanitized_title = re.sub(r'[^a-zA-Z0-9]', '_', movie_title)
        file_name = f"{sanitized_title}_{poster_path.split('/')[-1]}"
        file_path = os.path.join(folder, file_name)
        
        # Solo descargar si no existe
        if os.path.exists(file_path):
            logger.info(f"Póster ya existe: {file_path}")
            return file_path
        
        # Descargar el póster
        poster_url = f"https://image.tmdb.org/t/p/{size}{poster_path}"
        try:
            urllib.request.urlretrieve(poster_url, file_path)
            logger.info(f"Póster descargado: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Error al descargar el póster: {str(e)}")
            return ""
    
    def download_backdrop(self, backdrop_path, movie_title, folder="imagenes_estrenos", size="w1280"):
        """Descarga el backdrop de una película si no existe ya"""
        if not backdrop_path:
            return ""
        
        # Asegurar que existe el directorio
        if not os.path.exists(folder):
            os.makedirs(folder)
        
        # Crear nombre del archivo sanitizando el título
        sanitized_title = re.sub(r'[^a-zA-Z0-9]', '_', movie_title)
        file_name = f"{sanitized_title}_backdrop_{backdrop_path.split('/')[-1]}"
        file_path = os.path.join(folder, file_name)
        
        # Solo descargar si no existe
        if os.path.exists(file_path):
            logger.info(f"Backdrop ya existe: {file_path}")
            return file_path
        
        # Descargar el backdrop
        backdrop_url = f"https://image.tmdb.org/t/p/{size}{backdrop_path}"
        try:
            urllib.request.urlretrieve(backdrop_url, file_path)
            logger.info(f"Backdrop descargado: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Error al descargar el backdrop: {str(e)}")
            return ""

def load_existing_data(filename):
    """Carga los datos existentes si el archivo existe"""
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"El archivo {filename} existe pero no es un JSON válido")
    return []

def get_movie_hash(movie):
    """Genera un hash basado en los datos de la película para detectar cambios"""
    key_data = f"{movie.get('id')}-{movie.get('fecha_estreno')}-{movie.get('título')}"
    return hashlib.md5(key_data.encode()).hexdigest()

def should_update_movie(new_movie, existing_movie):
    """Determina si una película debe ser actualizada basado en los cambios"""
    # Verificar cambios en datos críticos
    if (new_movie.get('fecha_estreno') != existing_movie.get('fecha_estreno') or
        new_movie.get('título') != existing_movie.get('título') or
        new_movie.get('sinopsis') != existing_movie.get('sinopsis')):
        return True
    
    # Si la puntuación o popularidad ha cambiado significativamente
    if (abs(new_movie.get('puntuación', 0) - existing_movie.get('puntuación', 0)) > 0.5 or
        abs(new_movie.get('popularidad', 0) - existing_movie.get('popularidad', 0)) > 5):
        return True
    
    return False

def process_upcoming_movies(api, existing_movies=None, max_pages=5, region="ES", language="es-ES", 
                           download_images=True, images_folder="imagenes_estrenos"):
    """Procesa los próximos estrenos teniendo en cuenta datos existentes"""
    if existing_movies is None:
        existing_movies = []
    
    # Crear un mapa de películas existentes por ID para búsqueda rápida
    existing_map = {movie.get('id'): movie for movie in existing_movies if 'id' in movie}
    
    all_movies = []
    updated_count = 0
    new_count = 0
    unchanged_count = 0
    total_pages = 1
    
    for page in range(1, max_pages + 1):
        if page > total_pages:
            break
            
        logger.info(f"Obteniendo página {page} de próximos estrenos...")
        upcoming_data = api.get_upcoming_movies(region, language, page)
        
        if not upcoming_data or "results" not in upcoming_data:
            logger.warning(f"No se pudieron obtener datos para la página {page}")
            break
        
        # Actualizar el total de páginas
        total_pages = min(upcoming_data.get("total_pages", 1), max_pages)
        
        # Procesar cada película
        for movie in upcoming_data["results"]:
            try:
                movie_id = movie["id"]
                
                # Verificar si la película ya existe
                if movie_id in existing_map:
                    existing_movie = existing_map[movie_id]
                    
                    # Determinar si necesita actualización
                    if not should_update_movie(movie, existing_movie):
                        logger.info(f"La película {movie['title']} (ID: {movie_id}) no ha cambiado, se mantiene existente")
                        all_movies.append(existing_movie)
                        unchanged_count += 1
                        continue
                    
                    logger.info(f"Actualizando película: {movie['title']} (ID: {movie_id})")
                    updated_count += 1
                else:
                    logger.info(f"Nueva película: {movie['title']} (ID: {movie_id})")
                    new_count += 1
                
                # Obtener detalles completos
                details = api.get_movie_details(movie_id, language)
                if not details:
                    continue
                
                # Obtener imágenes
                images = api.get_movie_images(movie_id, language)
                
                # Extraer directores
                directors = []
                if "credits" in details and "crew" in details["credits"]:
                    directors = [
                        {"name": crew_member["name"], "id": crew_member["id"]}
                        for crew_member in details["credits"]["crew"]
                        if crew_member["job"] == "Director"
                    ]
                
                # Extraer actores principales (primeros 5)
                cast = []
                if "credits" in details and "cast" in details["credits"]:
                    cast = [
                        {
                            "name": cast_member["name"],
                            "id": cast_member["id"],
                            "character": cast_member["character"],
                            "profile_path": cast_member["profile_path"]
                        }
                        for cast_member in details["credits"]["cast"][:5]
                    ]
                
                # Extraer fecha de estreno en España
                release_date_es = None
                if "release_dates" in details:
                    for country in details["release_dates"]["results"]:
                        if country["iso_3166_1"] == "ES":
                            for date_type in country["release_dates"]:
                                if date_type["type"] == 3:  # Tipo 3 es estreno en cines
                                    release_date_es = date_type["release_date"]
                                    break
                            if release_date_es:
                                break
                
                # Si no hay fecha específica para España, usar la fecha general
                if not release_date_es:
                    release_date_es = details.get("release_date")
                
                # Usar las rutas de imágenes existentes o descargar nuevas
                poster_local_path = ""
                backdrop_local_path = ""
                
                if movie_id in existing_map and existing_map[movie_id].get("poster_local"):
                    poster_local_path = existing_map[movie_id]["poster_local"]
                    if not os.path.exists(poster_local_path):
                        poster_local_path = ""  # Resetear si el archivo ya no existe
                
                if movie_id in existing_map and existing_map[movie_id].get("backdrop_local"):
                    backdrop_local_path = existing_map[movie_id]["backdrop_local"]
                    if not os.path.exists(backdrop_local_path):
                        backdrop_local_path = ""  # Resetear si el archivo ya no existe
                
                # Descargar póster y backdrop si es necesario
                if download_images:
                    if details.get("poster_path") and not poster_local_path:
                        poster_local_path = api.download_poster(
                            details["poster_path"], 
                            details["title"], 
                            folder=images_folder
                        )
                    
                    if details.get("backdrop_path") and not backdrop_local_path:
                        backdrop_local_path = api.download_backdrop(
                            details["backdrop_path"], 
                            details["title"], 
                            folder=images_folder
                        )
                
                # Crear estructura de datos para la película
                movie_data = {
                    "id": details["id"],
                    "tmdb_id": details["id"],  # Para mantener consistencia con otros scripts
                    "título": details["title"],
                    "título_original": details["original_title"],
                    "sinopsis": details["overview"],
                    "poster_path": details["poster_path"],
                    "poster_local": poster_local_path,
                    "backdrop_path": details["backdrop_path"],
                    "backdrop_local": backdrop_local_path,
                    "fecha_estreno": release_date_es,
                    "duración": f"{details.get('runtime', 0)} min",
                    "director": ", ".join(d["name"] for d in directors),
                    "directores": directors,
                    "actores": cast,
                    "géneros": details.get("genres", []),
                    "popularidad": details.get("popularity", 0),
                    "puntuación": details.get("vote_average", 0),
                    "votos": details.get("vote_count", 0),
                    "adulto": details.get("adult", False),
                    "video": details.get("video", False),
                    "año": details.get("release_date", "")[:4] if details.get("release_date") else "",
                    "imágenes": {
                        "backdrops": images.get("backdrops", [])[:5] if images else [],
                        "posters": images.get("posters", [])[:5] if images else []
                    },
                    "última_actualización": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                all_movies.append(movie_data)
                
            except Exception as e:
                logger.error(f"Error procesando película {movie.get('id')}: {str(e)}")
    
    # Incluir películas existentes que ya no aparecen en los resultados de la API
    # pero que tienen fecha de estreno en el futuro
    today = datetime.now().strftime("%Y-%m-%d")
    for movie_id, movie in existing_map.items():
        # Si la película no ha sido incluida ya
        if not any(m["id"] == movie_id for m in all_movies):
            release_date = movie.get("fecha_estreno", "").split("T")[0] if movie.get("fecha_estreno") else ""
            
            # Solo mantener las películas con fecha de estreno en el futuro
            if release_date and release_date >= today:
                logger.info(f"Manteniendo película existente: {movie.get('título')} (ID: {movie_id})")
                all_movies.append(movie)
    
    # Ordenar por fecha de estreno
    all_movies.sort(key=lambda x: x.get("fecha_estreno", "9999-99-99"))
    
    logger.info(f"Resumen de procesamiento: {new_count} nuevas, {updated_count} actualizadas, {unchanged_count} sin cambios")
    
    return all_movies

def save_to_json(movies, filename):
    """Guarda los datos de películas en un archivo JSON"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(movies, f, ensure_ascii=False, indent=2)
        logger.info(f"Se han guardado {len(movies)} películas en {filename}")
        return True
    except Exception as e:
        logger.error(f"Error al guardar archivo JSON: {str(e)}")
        return False

def main():
    """Función principal del script"""
    parser = argparse.ArgumentParser(description="Obtener próximos estrenos de películas en España")
    parser.add_argument("--region", default="ES", help="Código de región (default: ES para España)")
    parser.add_argument("--language", default="es-ES", help="Código de idioma (default: es-ES)")
    parser.add_argument("--output", default="proximos_estrenos.json", help="Nombre del archivo de salida (default: proximos_estrenos.json)")
    parser.add_argument("--no-images", action="store_true", help="No descargar imágenes")
    parser.add_argument("--force-update", action="store_true", help="Forzar actualización de todas las películas")
    parser.add_argument("--images-folder", default="imagenes_estrenos", help="Carpeta para guardar las imágenes (default: imagenes_estrenos)")
    parser.add_argument("--max-pages", type=int, default=5, help="Número máximo de páginas a obtener (default: 5)")
    
    args = parser.parse_args()
    
    # Inicializar API de TMDB
    tmdb_api = TMDbAPI(TMDB_API_KEY)
    
    # Cargar datos existentes si el archivo existe
    existing_movies = [] if args.force_update else load_existing_data(args.output)
    if existing_movies:
        logger.info(f"Se han cargado {len(existing_movies)} películas existentes")
    
    # Obtener próximos estrenos
    logger.info(f"Obteniendo próximos estrenos para la región {args.region} en idioma {args.language}")
    upcoming_movies = process_upcoming_movies(
        tmdb_api, 
        existing_movies=existing_movies,
        max_pages=args.max_pages,
        region=args.region, 
        language=args.language,
        download_images=not args.no_images,
        images_folder=args.images_folder
    )
    
    # Guardar resultados
    if save_to_json(upcoming_movies, args.output):
        logger.info(f"Proceso completado. Se han procesado {len(upcoming_movies)} próximos estrenos.")
    
if __name__ == "__main__":
    main()