#!/usr/bin/env python3
"""
Script modificado de scraping de filmotecanavarra.com
Esta versión guarda los resultados en un archivo temporal para su posterior integración
con las películas añadidas manualmente.
"""

from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import urllib.request
import re
import time
import logging
from difflib import SequenceMatcher
import argparse

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

        # Realizar una búsqueda con el título original
        search_results = self._make_request("search/movie", params={"query": title, "language": "es"})

        if not search_results or not search_results.get("results"):
            # Si no hay resultados, intentar en inglés
            logger.warning(f"No results found for '{title}' in Spanish. Trying English search...")
            search_results = self._make_request("search/movie", params={"query": title, "language": "en"})

        if not search_results or not search_results.get("results"):
            logger.warning(f"No results found for: {title} in any language.")
            return {}

        # Ordenar por fecha de lanzamiento (más reciente primero)
        results = sorted(search_results["results"], key=lambda x: x.get("release_date", "1900-01-01"), reverse=True)

        # Buscar el mejor match por similitud
        best_match = None
        highest_similarity = 0

        for result in results:
            similarity = self._title_similarity(title, result.get("title", ""))
            if similarity > highest_similarity:
                highest_similarity = similarity
                best_match = result

        if best_match and highest_similarity > 0.6:
            movie_id = best_match["id"]
            logger.info(f"Found match: {best_match.get('title')} (ID: {movie_id}, Similarity: {highest_similarity})")

            # Obtener detalles adicionales
            details = self._make_request(f"movie/{movie_id}", params={"language": "es"})
            if not details:
                details = self._make_request(f"movie/{movie_id}", params={"language": "en"})

            credits = self._make_request(f"movie/{movie_id}/credits", params={"language": "es"})
            if not credits:
                credits = self._make_request(f"movie/{movie_id}/credits", params={"language": "en"})

            if not details or not credits:
                return {}

            return {
                "tmdb_id": movie_id,
                "director": ", ".join(c["name"] for c in credits.get("crew", []) if c["job"] == "Director"),
                "duración": f"{details.get('runtime', 'Desconocido')} min",
                "actores": ", ".join(a["name"] for a in credits.get("cast", [])[:5]),
                "sinopsis": details.get("overview"),
                "año": details.get("release_date", "")[:4],
                "poster_path": details.get("poster_path")
            }

        logger.warning(f"No good match found for: {title}")
        return {}
    
    def get_movie_info_by_id(self, movie_id: int) -> dict:
        logger.info(f"Fetching movie by TMDb ID: {movie_id}")

        details = self._make_request(f"movie/{movie_id}", params={"language": "es"})
        if not details:
            details = self._make_request(f"movie/{movie_id}", params={"language": "en"})

        credits = self._make_request(f"movie/{movie_id}/credits", params={"language": "es"})
        if not credits:
            credits = self._make_request(f"movie/{movie_id}/credits", params={"language": "en"})

        if not details or not credits:
            return {}

        return {
            "tmdb_id": movie_id,
            "director": ", ".join(c["name"] for c in credits.get("crew", []) if c["job"] == "Director"),
            "duración": f"{details.get('runtime', 'Desconocido')} min",
            "actores": ", ".join(a["name"] for a in credits.get("cast", [])[:5]),
            "sinopsis": details.get("overview"),
            "año": details.get("release_date", "")[:4],
            "poster_path": details.get("poster_path")
        }

def scrapear_filmoteca():
    """Realiza el scraping de la web de Filmoteca de Navarra"""
    logger.info("Iniciando scraping de filmotecanavarra.com...")

    # Cargar equivalencias TMDB
    try:
        with open("equivalencias_peliculas.json", "r", encoding="utf-8") as f:
            equivalencias_tmdb = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        equivalencias_tmdb = {}
        logger.warning("No se encontró el archivo de equivalencias o está vacío. Se creará uno nuevo.")

    # Inicializar variables
    url = "https://www.filmotecanavarra.com/es/comprar-entradas.asp"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.find_all('a', href=True)

    processed_urls = set()
    peliculas = []
    sugerencias_equivalencias = {}

    # Función para resolver equivalencias TMDB
    def resolver_equivalencia_tmdb(titulo_original: str) -> dict:
        clave = titulo_original.strip().lower()
        return equivalencias_tmdb.get(clave, {})

    # Inicializar TMDbAPI
    load_dotenv()
    TMDB_API_KEY = os.getenv("TMDB_API_KEY")
    if not TMDB_API_KEY:
        logger.error("No se ha encontrado la clave API de TMDB. Crea un archivo .env con TMDB_API_KEY=tu_clave")
        return []
        
    tmdb_api = TMDbAPI(TMDB_API_KEY)

    # Crear directorio para imágenes si no existe
    if not os.path.exists('imagenes_filmoteca'):
        os.makedirs('imagenes_filmoteca')

    # Procesar cada enlace
    for link in links:
        if 'evento.asp' in link['href']:
            try:
                if link['href'] not in processed_urls:
                    processed_urls.add(link['href'])
                    response = requests.get(f"https://www.filmotecanavarra.com/es/{link['href']}")
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, 'html.parser')

                    title = soup.find('h1').text.strip()
                    divtxt22 = soup.find('div', class_='txt txt22')
                    idioma = ""

                    if divtxt22:
                        texto_completo = divtxt22.get_text()
                        if 'Idioma:' in texto_completo:
                            idioma = texto_completo.split('Idioma:')[-1].split('\n')[0].strip()

                        idioma_strong = divtxt22.find('strong', string=re.compile(r'Idioma', re.IGNORECASE))
                        if idioma_strong and idioma == "":
                            idioma = idioma_strong.find_next_sibling(string=True)
                            if idioma:
                                idioma = idioma.strip()

                        if idioma and ('V.O.S.E.' in idioma or 
                                    'subtítulos en español' in idioma.lower() or 
                                    'subtítulos en castellano' in idioma.lower() or
                                    'subtitulos en castellano' in idioma.lower() or
                                    'subtitulos en español' in idioma.lower()):
                            enlace_bacantix = soup.find('a', href=lambda x: x and 'bacantix.com' in x.lower())

                            logger.info(f"Procesando película: {title}")
                            logger.info(f"Idioma: {idioma}")

                            pelicula = {
                                "título": title,
                                "cartel": os.path.join('imagenes_filmoteca', re.sub(r'[^a-zA-Z0-9]', '_', title) + '.jpg'),
                                "horarios": [],
                                "cine": "Filmoteca de Navarra",
                            }

                            fecha_hora = soup.find('h2')
                            if fecha_hora:
                                texto_fecha = fecha_hora.get_text(separator=" ").strip()
                                try:
                                    meses = {
                                        'enero': '01', 'febrero': '02', 'marzo': '03',
                                        'abril': '04', 'mayo': '05', 'junio': '06',
                                        'julio': '07', 'agosto': '08', 'septiembre': '09',
                                        'octubre': '10', 'noviembre': '11', 'diciembre': '12'
                                    }

                                    partes_fecha = texto_fecha.split()
                                    dia = partes_fecha[1]
                                    mes = meses[partes_fecha[3].lower()]
                                    hora_match = re.search(r'\d{2}:\d{2}', texto_fecha)
                                    hora = hora_match.group(0) if hora_match else "00:00"
                                    año = datetime.now().year
                                    fecha_formateada = f"{año}-{mes}-{dia.zfill(2)}"

                                    logger.info(f"Fecha formateada: {fecha_formateada}, Hora: {hora}")

                                    horario = {
                                        "fecha": fecha_formateada,
                                        "hora": hora,
                                        "enlace_entradas": enlace_bacantix['href'] if enlace_bacantix else ""
                                    }
                                    pelicula["horarios"].append(horario)

                                except Exception as e:
                                    logger.error(f"Error procesando fecha: {str(e)}")

                            div_dcha = soup.find('div', class_='dcha')
                            if div_dcha:
                                imagen = div_dcha.find('img')
                                if imagen and 'src' in imagen.attrs:
                                    url_imagen = f"https://www.filmotecanavarra.com{imagen['src'].replace('..', '')}"
                                    nombre_archivo = re.sub(r'[^a-zA-Z0-9]', '_', title) + '.jpg'
                                    ruta_imagen = os.path.join('imagenes_filmoteca', nombre_archivo)
                                    try:
                                        urllib.request.urlretrieve(url_imagen, ruta_imagen)
                                        logger.info(f"Cartel guardado en: {ruta_imagen}")
                                    except Exception as e:
                                        logger.error(f"Error al descargar la imagen: {str(e)}")
                            
                            equivalencia = resolver_equivalencia_tmdb(title)
                            if "tmdb_id" in equivalencia:
                                logger.info(f"Usando equivalencia TMDB para '{title}': ID {equivalencia['tmdb_id']}")
                                tmdb_info = tmdb_api.get_movie_info_by_id(equivalencia["tmdb_id"])
                            else:
                                tmdb_info = tmdb_api.get_movie_info(title)
                                if not tmdb_info:
                                    sugerencias_equivalencias.setdefault(title.strip().lower(), {
                                        "tmdb_id": None,
                                        "titulo_original": "",
                                        "anio": None
                                    })

                            if tmdb_info:
                                if tmdb_info.get('poster_path'):
                                    tmdb_poster_url = f"https://image.tmdb.org/t/p/w500{tmdb_info['poster_path']}"
                                    tmdb_poster_filename = os.path.join('imagenes_filmoteca', f"tmdb_{re.sub(r'[^a-zA-Z0-9]', '_', title)}.jpg")
                                    urllib.request.urlretrieve(tmdb_poster_url, tmdb_poster_filename)
                                    pelicula['cartel'] = tmdb_poster_filename

                                pelicula['tmdb_id'] = tmdb_info.get('tmdb_id')
                                pelicula['director'] = tmdb_info.get('director')
                                pelicula['duración'] = tmdb_info.get('duración')
                                pelicula['actores'] = tmdb_info.get('actores')
                                pelicula['sinopsis'] = tmdb_info.get('sinopsis')
                                pelicula['año'] = tmdb_info.get('año')

                            peliculas.append(pelicula)
                            logger.info(f"Película añadida: {title}")

                time.sleep(1)  # Pausa para evitar saturar el servidor

            except Exception as e:
                logger.error(f"Error procesando {link['href']}: {str(e)}")

    # Guardar sugerencias de equivalencias
    if sugerencias_equivalencias:
        with open('equivalencias_peliculas.json', 'w', encoding='utf-8') as f:
            json.dump(sugerencias_equivalencias, f, ensure_ascii=False, indent=4)
        logger.info(f"Se han guardado {len(sugerencias_equivalencias)} sugerencias en equivalencias_peliculas.json")

    logger.info("Fin de scraping")
    return peliculas

def ejecutar_scraping():
    """Función principal para ejecutar el scraping"""
    parser = argparse.ArgumentParser(description='Scraper de Filmoteca de Navarra')
    parser.add_argument('--archivo_salida', default='peliculas_filmoteca_scraping.json',
                        help='Nombre del archivo de salida temporal (default: peliculas_filmoteca_scraping.json)')
    parser.add_argument('--integrar', action='store_true',
                        help='Integrar automáticamente con las películas manuales')
    
    args = parser.parse_args()
    
    # Ejecutar el scraping
    peliculas = scrapear_filmoteca()
    
    # Guardar resultados en el archivo temporal
    with open(args.archivo_salida, 'w', encoding='utf-8') as f:
        json.dump(peliculas, f, ensure_ascii=False, indent=4)
    
    logger.info(f"Se han guardado {len(peliculas)} películas en {args.archivo_salida}")
    
    # Integrar si se solicitó
    if args.integrar and os.path.exists('integrador.py'):
        logger.info("Integrando películas con las añadidas manualmente...")
        try:
            import integrador
            integrador.main()
        except ImportError:
            logger.error("No se pudo importar el módulo integrador.py")
            logger.info("Ejecuta manualmente: python integrador.py")
    elif args.integrar:
        logger.warning("No se encontró el archivo integrador.py. No se pudo integrar automáticamente.")
        logger.info("Ejecuta manualmente: python integrador.py")
    else:
        logger.info("Para integrar con películas manuales, ejecuta: python integrador.py")

if __name__ == "__main__":
    ejecutar_scraping()
