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

            # Asegurarnos de obtener todos los detalles usando el ID encontrado
            return self.get_movie_info_by_id(movie_id)

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

# Función para cargar equivalencias existentes
def cargar_equivalencias():
    try:
        if os.path.exists("equivalencias_peliculas.json"):
            with open("equivalencias_peliculas.json", "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            return []
    except Exception as e:
        logger.error(f"Error al cargar equivalencias: {str(e)}")
        return []

# Función para buscar una película por título en las equivalencias
def buscar_equivalencia_por_titulo(equivalencias, titulo):
    titulo_normalizado = titulo.strip().lower()
    for pelicula in equivalencias:
        if pelicula.get("título", "").strip().lower() == titulo_normalizado:
            return pelicula
    return None

# Función para guardar las equivalencias
def guardar_equivalencias(equivalencias):
    with open("equivalencias_peliculas.json", "w", encoding="utf-8") as f:
        json.dump(equivalencias, f, ensure_ascii=False, indent=4)
    logger.info(f"Se han guardado {len(equivalencias)} películas en equivalencias_peliculas.json")

# Inicio del script
print("Scraping filmotecanavarra.com...")

# Cargar equivalencias existentes
equivalencias_peliculas = cargar_equivalencias()

url = "https://www.filmotecanavarra.com/es/comprar-entradas.asp"
response = requests.get(url)
soup = BeautifulSoup(response.text, 'html.parser')
links = soup.find_all('a', href=True)

processed_urls = set()
peliculas = []
nuevas_equivalencias = []

# Inicializar TMDbAPI
load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
tmdb_api = TMDbAPI(TMDB_API_KEY)

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

                        print("Título: ", title)
                        print("Idioma:", idioma)

                        # Inicializar nueva película
                        pelicula = {
                            "título": title,
                            "cartel": os.path.join('imagenes_filmoteca', re.sub(r'[^a-zA-Z0-9]', '_', title) + '.jpg'),
                            "horarios": [],
                            "cine": "Filmoteca de Navarra",
                        }

                        # Procesar fecha y hora
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

                                print(f"Fecha formateada: {fecha_formateada}, Hora: {hora}")

                                horario = {
                                    "fecha": fecha_formateada,
                                    "hora": hora,
                                    "enlace_entradas": enlace_bacantix['href'] if enlace_bacantix else ""
                                }
                                pelicula["horarios"].append(horario)

                            except Exception as e:
                                print(f"Error procesando fecha: {str(e)}")

                        # Descargar imagen
                        div_dcha = soup.find('div', class_='dcha')
                        if div_dcha:
                            imagen = div_dcha.find('img')
                            if imagen and 'src' in imagen.attrs:
                                url_imagen = f"https://www.filmotecanavarra.com{imagen['src'].replace('..', '')}"
                                if not os.path.exists('imagenes_filmoteca'):
                                    os.makedirs('imagenes_filmoteca')
                                nombre_archivo = re.sub(r'[^a-zA-Z0-9]', '_', title) + '.jpg'
                                ruta_imagen = os.path.join('imagenes_filmoteca', nombre_archivo)
                                try:
                                    urllib.request.urlretrieve(url_imagen, ruta_imagen)
                                    print(f"Cartel guardado en: {ruta_imagen}")
                                except Exception as e:
                                    print(f"Error al descargar la imagen: {str(e)}")
                        
                        # Buscar en equivalencias existentes
                        equivalencia = buscar_equivalencia_por_titulo(equivalencias_peliculas, title)
                        
                        if equivalencia:
                            # Si existe en equivalencias, usarla siempre sin intentar buscar en TMDb
                            logger.info(f"Usando equivalencia existente para '{title}'")
                            
                            # Si tiene ID pero le faltan datos, intentar completarlos directamente con ese ID
                            if equivalencia.get("tmdb_id") and not all([
                                equivalencia.get("director"), 
                                equivalencia.get("duración"), 
                                equivalencia.get("actores"),
                                equivalencia.get("sinopsis")
                            ]):
                                logger.info(f"La película '{title}' tiene ID ({equivalencia['tmdb_id']}) pero le faltan datos. Recuperando información...")
                                
                                tmdb_info = tmdb_api.get_movie_info_by_id(equivalencia["tmdb_id"])
                                
                                if tmdb_info:
                                    # Actualizar los datos manteniendo el mismo ID
                                    pelicula = {
                                        "título": title,
                                        "cartel": equivalencia.get("cartel", pelicula["cartel"]),
                                        "horarios": pelicula["horarios"],
                                        "cine": "Filmoteca de Navarra",
                                        "tmdb_id": equivalencia["tmdb_id"],  # Mantener el ID original
                                        "director": tmdb_info.get("director", ""),
                                        "duración": tmdb_info.get("duración", ""),
                                        "actores": tmdb_info.get("actores", ""),
                                        "sinopsis": tmdb_info.get("sinopsis", ""),
                                        "año": tmdb_info.get("año", "")
                                    }
                                    
                                    # Descargar poster de TMDb si está disponible
                                    if tmdb_info.get('poster_path'):
                                        tmdb_poster_url = f"https://image.tmdb.org/t/p/w500{tmdb_info['poster_path']}"
                                        tmdb_poster_filename = os.path.join('imagenes_filmoteca', f"tmdb_{re.sub(r'[^a-zA-Z0-9]', '_', title)}.jpg")
                                        try:
                                            urllib.request.urlretrieve(tmdb_poster_url, tmdb_poster_filename)
                                            pelicula['cartel'] = tmdb_poster_filename
                                        except Exception as e:
                                            logger.error(f"Error al descargar poster de TMDb: {str(e)}")
                                    
                                    # Actualizar la equivalencia para futuras ejecuciones
                                    equivalencia_index = next((i for i, eq in enumerate(equivalencias_peliculas) 
                                                              if eq.get("título", "").strip().lower() == title.strip().lower()), -1)
                                    if equivalencia_index >= 0:
                                        # Actualizar todos los campos excepto el ID y los horarios
                                        for key, value in pelicula.items():
                                            if key != "horarios" and key != "tmdb_id":  # NO sobrescribimos el ID ni los horarios
                                                equivalencias_peliculas[equivalencia_index][key] = value
                                        # Marcar como actualizada para guardar cambios al final
                                        equivalencias_peliculas[equivalencia_index]["_actualizada"] = True
                                        logger.info(f"Equivalencia para '{title}' completada manteniendo ID original: {equivalencia['tmdb_id']}")
                                else:
                                    # Si no puede obtener datos, usar la equivalencia tal cual
                                    logger.warning(f"No se pudieron recuperar los detalles para el ID {equivalencia['tmdb_id']}")
                                    pelicula = equivalencia.copy()
                                    pelicula["horarios"] = pelicula["horarios"]
                            else:
                                # Usar la equivalencia tal cual (tiene ID completo o no tiene ID)
                                pelicula = equivalencia.copy()
                                pelicula["horarios"] = pelicula["horarios"]
                                # Si existe en equivalencias pero le faltan datos y no tiene ID, intentar actualizarla
                                logger.info(f"La película '{title}' existe en equivalencias pero le faltan datos. Intentando actualizar...")
                                
                                # Buscar en TMDb (incluyendo título entre paréntesis)
                                tmdb_info = tmdb_api.get_movie_info(title)
                                if not tmdb_info:
                                    match = re.search(r'\((.*?)\)', title)
                                    if match:
                                        titulo_original = match.group(1).strip()
                                        logger.info(f"Intentando buscar con título original: {titulo_original}")
                                        tmdb_info = tmdb_api.get_movie_info(titulo_original)
                                
                                if tmdb_info:
                                    # Actualizar la película con la información de TMDb
                                    pelicula["tmdb_id"] = tmdb_info.get("tmdb_id")
                                    pelicula["director"] = tmdb_info.get("director")
                                    pelicula["duración"] = tmdb_info.get("duración")
                                    pelicula["actores"] = tmdb_info.get("actores")
                                    pelicula["sinopsis"] = tmdb_info.get("sinopsis")
                                    pelicula["año"] = tmdb_info.get("año")
                                    
                                    # Descargar poster de TMDb si está disponible
                                    if tmdb_info.get('poster_path'):
                                        tmdb_poster_url = f"https://image.tmdb.org/t/p/w500{tmdb_info['poster_path']}"
                                        tmdb_poster_filename = os.path.join('imagenes_filmoteca', f"tmdb_{re.sub(r'[^a-zA-Z0-9]', '_', title)}.jpg")
                                        try:
                                            urllib.request.urlretrieve(tmdb_poster_url, tmdb_poster_filename)
                                            pelicula['cartel'] = tmdb_poster_filename
                                        except Exception as e:
                                            logger.error(f"Error al descargar poster de TMDb: {str(e)}")
                                    
                                    # Actualizar la equivalencia para futuras ejecuciones
                                    equivalencia_index = next((i for i, eq in enumerate(equivalencias_peliculas) 
                                                              if eq.get("título", "").strip().lower() == title.strip().lower()), -1)
                                    if equivalencia_index >= 0:
                                        for key, value in pelicula.items():
                                            if key != "horarios":  # No sobrescribimos los horarios en el archivo de equivalencias
                                                equivalencias_peliculas[equivalencia_index][key] = value
                                        # Marcar como actualizada para guardar cambios al final
                                        equivalencias_peliculas[equivalencia_index]["_actualizada"] = True
                                        logger.info(f"Equivalencia para '{title}' actualizada con datos de TMDb")
                                else:
                                    # Si no la encuentra, mantener la equivalencia existente
                                    nueva_pelicula = equivalencia.copy()
                                    nueva_pelicula["horarios"] = pelicula["horarios"]
                                    pelicula = nueva_pelicula
                        else:
                            # Si no hay equivalencia, buscar en TMDb
                            tmdb_info = tmdb_api.get_movie_info(title)
                            
                            # Si no encuentra resultados, intentar buscar con el título original (entre paréntesis)
                            if not tmdb_info:
                                # Buscar título entre paréntesis que podría ser el título original
                                match = re.search(r'\((.*?)\)', title)
                                if match:
                                    titulo_original = match.group(1).strip()
                                    logger.info(f"Intentando buscar con título original: {titulo_original}")
                                    tmdb_info = tmdb_api.get_movie_info(titulo_original)
                            
                            if tmdb_info:
                                # Actualizar la película con la información de TMDb
                                pelicula["tmdb_id"] = tmdb_info.get("tmdb_id")
                                pelicula["director"] = tmdb_info.get("director")
                                pelicula["duración"] = tmdb_info.get("duración")
                                pelicula["actores"] = tmdb_info.get("actores")
                                pelicula["sinopsis"] = tmdb_info.get("sinopsis")
                                pelicula["año"] = tmdb_info.get("año")
                                
                                # Descargar poster de TMDb si está disponible
                                if tmdb_info.get('poster_path'):
                                    tmdb_poster_url = f"https://image.tmdb.org/t/p/w500{tmdb_info['poster_path']}"
                                    tmdb_poster_filename = os.path.join('imagenes_filmoteca', f"tmdb_{re.sub(r'[^a-zA-Z0-9]', '_', title)}.jpg")
                                    try:
                                        urllib.request.urlretrieve(tmdb_poster_url, tmdb_poster_filename)
                                        pelicula['cartel'] = tmdb_poster_filename
                                    except Exception as e:
                                        logger.error(f"Error al descargar poster de TMDb: {str(e)}")
                            else:
                                # Si no se encuentra en TMDb, agregar a las nuevas equivalencias para edición manual
                                logger.warning(f"No se encontró información en TMDb para: {title}")
                                pelicula["tmdb_id"] = None
                                pelicula["director"] = ""
                                pelicula["duración"] = ""
                                pelicula["actores"] = ""
                                pelicula["sinopsis"] = ""
                                pelicula["año"] = ""
                                
                                # Agregar a nuevas equivalencias solo si no existe ya
                                if not buscar_equivalencia_por_titulo(equivalencias_peliculas, pelicula["título"]):
                                    nuevas_equivalencias.append(pelicula.copy())

                        # Agregar la película procesada a la lista
                        peliculas.append(pelicula)
                        print("--------------------------------")

            time.sleep(1)  # Pausa para no sobrecargar el servidor

        except Exception as e:
            print(f"Error procesando {link['href']}: {str(e)}")

# Actualizar equivalencias con las nuevas encontradas
equivalencias_actualizadas = False
if nuevas_equivalencias:
    for nueva in nuevas_equivalencias:
        # Verificar que no existe ya
        if not buscar_equivalencia_por_titulo(equivalencias_peliculas, nueva["título"]):
            equivalencias_peliculas.append(nueva)
            equivalencias_actualizadas = True
    
    if equivalencias_actualizadas:
        # Guardar equivalencias actualizadas
        guardar_equivalencias(equivalencias_peliculas)
        print(f"Se han agregado {len(nuevas_equivalencias)} nuevas películas a las equivalencias")

# Guardar equivalencias si se han actualizado películas existentes
elif any(pelicula.get("_actualizada", False) for pelicula in equivalencias_peliculas):
    guardar_equivalencias(equivalencias_peliculas)
    print("Se han actualizado películas existentes en las equivalencias")

print("Fin de scraping")

# Guardar películas procesadas
with open('peliculas_filmoteca.json', 'w', encoding='utf-8') as f:
    json.dump(peliculas, f, ensure_ascii=False, indent=4)

print(f"Se han guardado {len(peliculas)} películas en peliculas_filmoteca.json")