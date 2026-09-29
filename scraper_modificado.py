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
from datetime import datetime, timedelta
import urllib.request
import re
import time
import logging
import unicodedata
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

    def _buscar(self, consulta: str, anio: int = None) -> list:
        """Resultados de TMDb para una consulta, en español y en inglés.

        TMDb devuelve 20 resultados por página y los títulos comunes ('Black
        Water': 38 resultados) pueden dejar la película buena en la página 2.
        Con el año se busca además filtrando por él (y el anterior y el
        siguiente, por estrenos en festivales), que da solo unas pocas."""
        busquedas = [{"language": "es"}, {"language": "en"}]
        if anio:
            busquedas += [{"language": "es", "year": y} for y in (anio, anio - 1, anio + 1)]
        resultados = {}
        for extra in busquedas:
            datos = self._make_request("search/movie", params={"query": consulta, **extra})
            for r in (datos or {}).get("results", []):
                resultados.setdefault(r.get("id"), r)
        return [r for r in resultados.values() if r.get("id")]

    @staticmethod
    def _anio(resultado: dict):
        fecha = str(resultado.get("release_date") or "")[:4]
        return int(fecha) if fecha.isdigit() else None

    def get_movie_info(self, title: str, anio: int = None, titulo_original: str = None) -> dict:
        """Busca la película por título (y por el título original si se
        conoce). Con el año de la Filmoteca se descartan las que se desvían más
        de 2 años; los cortos (< 40 min) se descartan siempre. Entre las
        válidas gana la más parecida, la de año más cercano y la más popular
        (así 'El prado' es The Field de 1990 y no un corto de 2023)."""
        logger.info(f"Searching TMDb for title: {title} (original: {titulo_original}, año: {anio})")
        titulos = [t for t in (title, titulo_original) if t]

        candidatos = {}
        for consulta in titulos:
            for r in self._buscar(consulta, anio):
                candidatos.setdefault(r["id"], r)
        if not candidatos:
            logger.warning(f"No results found for: {title} in any language.")
            return {}

        puntuados = []
        for r in candidatos.values():
            nombres = [n for n in (r.get("title"), r.get("original_title")) if n]
            similitud = max((self._title_similarity(t, n) for t in titulos for n in nombres), default=0)
            if similitud <= 0.6:
                continue
            anio_r = self._anio(r)
            if anio and anio_r and abs(anio_r - anio) > 2:
                continue
            desvio = abs(anio_r - anio) if (anio and anio_r) else 3
            puntuados.append((round(similitud - 0.1 * min(desvio, 3), 3), r.get("popularity") or 0, r))
        puntuados.sort(key=lambda x: (x[0], x[1]), reverse=True)

        for puntuacion, _, r in puntuados[:6]:
            info = self.get_movie_info_by_id(r["id"])
            if not info:
                continue
            if info.get("runtime") and info["runtime"] < 40:
                logger.info(f"Descartado {r.get('title')} ({r['id']}): corto de {info['runtime']} min")
                continue
            logger.info(f"Found match: {r.get('title')} (ID: {r['id']}, puntuación: {puntuacion})")
            return info

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

        sinopsis_en = ""
        if not (details.get("overview") or "").strip():
            # Sin sinopsis en castellano: se guarda la inglesa como último recurso
            detalles_en = self._make_request(f"movie/{movie_id}", params={"language": "en"})
            sinopsis_en = ((detalles_en or {}).get("overview") or "").strip()

        return {
            "tmdb_id": movie_id,
            "director": ", ".join(c["name"] for c in credits.get("crew", []) if c["job"] == "Director"),
            "duración": f"{details['runtime']} min" if details.get("runtime") else "",
            "actores": ", ".join(a["name"] for a in credits.get("cast", [])[:5]),
            "sinopsis": details.get("overview"),
            "sinopsis_en": sinopsis_en,
            "año": details.get("release_date", "")[:4],
            "poster_path": details.get("poster_path"),
            "runtime": details.get("runtime"),
        }

# El nombre del cartel de TMDb sale de su ruta en TMDb (única por imagen), no
# del título: si el emparejamiento cambia, cambia también la URL y la app no
# sigue mostrando el cartel anterior que guarda en caché (21 días por URL).
def nombre_cartel_tmdb(poster_path: str) -> str:
    base = re.sub(r'[^A-Za-z0-9_-]', '', os.path.splitext(os.path.basename(poster_path or ''))[0])
    return f"tmdb_{base}.jpg"

# Formulaciones admitidas para sesiones en versión original subtitulada.
# El texto se normaliza a ASCII y minúsculas antes de comparar, así que aquí
# van sin acentos (tanto "V.O.S.E." como la redacción actual del sitio).
CADENAS_VOSE = (
    'v.o.s.e', 'vose', 'vo subs',
    'subtitulado al espanol', 'subtitulos al espanol',
    'subtitulado al castellano',
    'subtitulos en espanol', 'subtitulos en castellano',
    'version original',
)

def es_vose(idioma: str) -> bool:
    """Devuelve True si el valor de Idioma indica versión original subtitulada."""
    if not idioma:
        return False
    texto = unicodedata.normalize('NFKD', str(idioma)).encode('ascii', 'ignore').decode().lower()
    return any(cadena in texto for cadena in CADENAS_VOSE)

def separar_titulo_h1(titulo: str) -> tuple:
    """Separa el <h1> de Filmoteca en (título, nota): quita el '(título
    original, país, año)' y guarda aparte lo que venga detrás, p. ej.
    'Cowboy de medianoche (Midnight Cowboy, Estados Unidos, 1969) Sesión con
    concierto.' -> ('Cowboy de medianoche', 'Sesión con concierto')."""
    texto = ' '.join((titulo or '').split())
    nota = ''
    coincidencia = re.search(r'\s*\((?=[^)]*\b(?:18|19|20)\d{2}\b)[^)]*\)', texto)
    if coincidencia:
        nota = texto[coincidencia.end():].strip(' .-–—·')
        texto = texto[:coincidencia.start()]
    else:
        texto = re.sub(r'\s*\([^)]*\)\s*$', '', texto)
    texto = texto.strip()
    return (texto or ' '.join((titulo or '').split()), nota)

def datos_h1(titulo: str) -> tuple:
    """Título original y año del paréntesis del <h1>:
    'El prado (The Field, Irlanda, 1990)' -> ('The Field', 1990);
    'Almudena (España, 2025)' -> (None, 2025)."""
    coincidencia = re.search(r'\(([^)]*\b(?:18|19|20)\d{2}\b[^)]*)\)', titulo or '')
    if not coincidencia:
        return (None, None)
    partes = [p.strip() for p in coincidencia.group(1).split(',')]
    anio = re.search(r'\b(?:18|19|20)\d{2}\b', partes[-1]) if partes else None
    anio = int(anio.group(0)) if anio else None
    # (título original, país, año): el título original solo si hay 3+ partes
    original = ', '.join(partes[:-2]).strip() if len(partes) >= 3 else None
    return (original or None, anio)

def limpiar_titulo_h1(titulo: str) -> str:
    """Título del <h1> sin '(título original, país, año)' ni notas."""
    return separar_titulo_h1(titulo)[0]

def ficha_filmoteca(soup) -> dict:
    """Datos de la propia ficha de la Filmoteca, para completar lo que TMDb
    no tenga: 'div.txt22' trae campos etiquetados ('Dirección y guion: ...',
    'Intérpretes: ...', 'Duración: 84 min.') y el primer párrafo de
    'div.txt33' es la sinopsis (el siguiente, el comentario de la Filmoteca)."""
    datos = {}
    txt22 = soup.find('div', class_='txt22')
    if txt22:
        for parrafo in txt22.find_all('p'):
            texto = ' '.join(parrafo.get_text(' ', strip=True).split())
            coincidencia = re.match(r'^([^:]{2,40}):\s*(.+)$', texto)
            if not coincidencia:
                continue
            etiqueta = _sin_acentos(coincidencia.group(1)).strip()
            valor = coincidencia.group(2).strip().rstrip('.').strip()
            if etiqueta.startswith('direccion') and 'director' not in datos:
                datos['director'] = valor
            elif etiqueta in ('interpretes', 'reparto', 'con la participacion de', 'con') and 'actores' not in datos:
                datos['actores'] = valor
            elif etiqueta == 'duracion' and 'duración' not in datos:
                minutos = re.search(r'\d+', valor)
                if minutos:
                    datos['duración'] = f"{minutos.group(0)} min"
    txt33 = soup.find('div', class_='txt33')
    if txt33:
        for parrafo in txt33.find_all('p'):
            texto = ' '.join(parrafo.get_text(' ', strip=True).split())
            if len(texto) >= 60:
                datos['sinopsis'] = texto
                break
    return datos

def completar_datos(pelicula: dict, tmdb_info: dict, ficha: dict) -> None:
    """Rellena director, reparto, duración y sinopsis: primero TMDb (en
    castellano), si falta la ficha de la Filmoteca y, para la sinopsis, en
    último lugar la de TMDb en inglés."""
    for campo in ('director', 'actores', 'duración', 'sinopsis'):
        valor = (tmdb_info.get(campo) or '').strip() or (ficha.get(campo) or '').strip()
        if not valor and campo == 'sinopsis':
            valor = (tmdb_info.get('sinopsis_en') or '').strip()
        pelicula[campo] = valor or None

CINE_POR_DEFECTO = 'Filmoteca de Navarra'

# Sedes fuera de la Filmoteca. El sitio las indica al final del <h2> de la
# sesión ('Sábado, 3 de octubre 19:00 - CONDESTABLE') y en el <title>.
SEDES = (
    ('condestable', 'Civivox Condestable'),
    ('iturrama', 'Civivox Iturrama'),
    ('mendillorri', 'Civivox Mendillorri'),
    ('jus la rocha', 'Civivox Jus la Rocha'),
    ('milagrosa', 'Civivox Milagrosa'),
    ('san jorge', 'Civivox San Jorge'),
    ('ensanche', 'Civivox Ensanche'),
    ('baluarte', 'Baluarte'),
    ('planetario', 'Planetario de Pamplona'),
    ('museo de navarra', 'Museo de Navarra'),
)

def _sin_acentos(texto: str) -> str:
    return unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode().lower()

def detectar_sede(texto_h2: str, titulo_pagina: str = '') -> str:
    """Devuelve el cine/sede de la sesión (por defecto, la Filmoteca)."""
    candidatos = []
    # Lo que va tras el último ' - ' del h2 ('19:00 - CONDESTABLE')
    if texto_h2 and ' - ' in texto_h2:
        candidatos.append(texto_h2.rsplit(' - ', 1)[1])
    # El <title>: 'Película - Ciclo - CONDESTABLE - Filmoteca de Navarra'.
    # Solo los trozos en mayúsculas, para no confundir un nombre de ciclo.
    if titulo_pagina:
        candidatos.extend(t for t in titulo_pagina.split(' - ')[1:]
                          if t.strip() and t.strip() == t.strip().upper())
    for candidato in candidatos:
        texto = _sin_acentos(candidato)
        for clave, sede in SEDES:
            if clave in texto:
                return sede
    return CINE_POR_DEFECTO

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
    correcciones_equivalencias = {}

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

                    texto_h1 = soup.find('h1').text.strip()
                    title, nota = separar_titulo_h1(texto_h1)
                    titulo_original, anio_h1 = datos_h1(texto_h1)
                    divtxt22 = soup.find('div', class_='txt txt22')
                    idioma = ""
                    texto_completo = ""

                    if divtxt22:
                        texto_completo = divtxt22.get_text()
                        if 'Idioma:' in texto_completo:
                            idioma = texto_completo.split('Idioma:')[-1].split('\n')[0].strip()

                        idioma_strong = divtxt22.find('strong', string=re.compile(r'Idioma', re.IGNORECASE))
                        if idioma_strong and idioma == "":
                            idioma = idioma_strong.find_next_sibling(string=True)
                            if idioma:
                                idioma = idioma.strip()

                        # Debe ser una película: requiere Idioma y Duración en el mismo
                        # div (los actos de venta de libros no traen ninguno de los dos)
                        if (idioma and
                                    ('Duración' in texto_completo or 'Duracion' in texto_completo) and
                                    es_vose(idioma)):
                            enlace_entradas = soup.find('a', href=lambda x: x and
                                                        any(h in x.lower() for h in ('bacantix.com', 'nicdo.es')))

                            logger.info(f"Procesando película: {title}")
                            logger.info(f"Idioma: {idioma}")

                            fecha_hora = soup.find('h2')
                            texto_fecha = fecha_hora.get_text(separator=" ").strip() if fecha_hora else ""
                            titulo_pagina = soup.title.get_text().strip() if soup.title else ""
                            cine = detectar_sede(texto_fecha, titulo_pagina)
                            logger.info(f"Sede: {cine}")

                            pelicula = {
                                "título": title,
                                "cartel": os.path.join('imagenes_filmoteca', re.sub(r'[^a-zA-Z0-9]', '_', title) + '.jpg'),
                                "horarios": [],
                                "cine": cine,
                            }
                            if nota:
                                # Detalle de la sesión: 'Sesión con concierto'...
                                pelicula["nota"] = nota

                            if fecha_hora:
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
                                    # Si la fecha ya quedó muy atrás en el año, es del año siguiente
                                    hoy = datetime.now()
                                    fecha_clase = datetime(hoy.year, int(mes), int(dia))
                                    año = hoy.year + 1 if fecha_clase < hoy - timedelta(days=15) else hoy.year
                                    fecha_formateada = f"{año}-{mes}-{dia.zfill(2)}"

                                    logger.info(f"Fecha formateada: {fecha_formateada}, Hora: {hora}")

                                    horario = {
                                        "fecha": fecha_formateada,
                                        "hora": hora,
                                        "enlace_entradas": enlace_entradas['href'] if enlace_entradas else "",
                                        "cine": cine,
                                    }
                                    if nota:
                                        horario["nota"] = nota
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
                            tmdb_info = {}
                            if equivalencia.get("tmdb_id"):
                                logger.info(f"Usando equivalencia TMDB para '{title}': ID {equivalencia['tmdb_id']}")
                                tmdb_info = tmdb_api.get_movie_info_by_id(equivalencia["tmdb_id"])
                                # Una equivalencia de otra época es un emparejamiento
                                # erróneo (p. ej. un corto homónimo): se vuelve a buscar
                                anio_equiv = str(tmdb_info.get("año") or "")
                                if anio_h1 and anio_equiv.isdigit() and abs(int(anio_equiv) - anio_h1) > 2:
                                    logger.warning(f"Equivalencia de '{title}' descartada: TMDb {anio_equiv}, Filmoteca {anio_h1}")
                                    tmdb_info = {}
                                elif tmdb_info.get("runtime") and tmdb_info["runtime"] < 40:
                                    logger.warning(f"Equivalencia de '{title}' descartada: es un corto de {tmdb_info['runtime']} min")
                                    tmdb_info = {}
                            if not tmdb_info:
                                tmdb_info = tmdb_api.get_movie_info(title, anio_h1, titulo_original)
                                if tmdb_info and equivalencia.get("tmdb_id") and equivalencia["tmdb_id"] != tmdb_info["tmdb_id"]:
                                    # Corregir la equivalencia guardada
                                    correcciones_equivalencias[title.strip().lower()] = {
                                        "tmdb_id": tmdb_info["tmdb_id"],
                                        "titulo_original": titulo_original or "",
                                        "anio": tmdb_info.get("año") or None
                                    }
                                if not tmdb_info:
                                    sugerencias_equivalencias.setdefault(title.strip().lower(), {
                                        "tmdb_id": None,
                                        "titulo_original": "",
                                        "anio": None
                                    })

                            if tmdb_info:
                                if tmdb_info.get('poster_path'):
                                    tmdb_poster_url = f"https://image.tmdb.org/t/p/w500{tmdb_info['poster_path']}"
                                    tmdb_poster_filename = os.path.join('imagenes_filmoteca', nombre_cartel_tmdb(tmdb_info['poster_path']))
                                    if not os.path.exists(tmdb_poster_filename):
                                        urllib.request.urlretrieve(tmdb_poster_url, tmdb_poster_filename)
                                    pelicula['cartel'] = tmdb_poster_filename

                                pelicula['tmdb_id'] = tmdb_info.get('tmdb_id')
                                pelicula['año'] = tmdb_info.get('año')

                            # Lo que TMDb no tenga (o todo, si no la encuentra),
                            # desde la ficha de la propia Filmoteca
                            completar_datos(pelicula, tmdb_info or {}, ficha_filmoteca(soup))
                            if not pelicula.get('año') and anio_h1:
                                pelicula['año'] = str(anio_h1)

                            peliculas.append(pelicula)
                            logger.info(f"Película añadida: {title}")

                time.sleep(1)  # Pausa para evitar saturar el servidor

            except Exception as e:
                logger.error(f"Error procesando {link['href']}: {str(e)}")

    # Guardar sugerencias de equivalencias sin borrar las ya existentes:
    # se parte de las cargadas y solo se añaden/sobrescriben las nuevas,
    # conservando siempre las que ya tienen un tmdb_id resuelto
    if sugerencias_equivalencias or correcciones_equivalencias:
        for clave, valor in sugerencias_equivalencias.items():
            existente = equivalencias_tmdb.get(clave)
            if existente and existente.get('tmdb_id'):
                continue
            equivalencias_tmdb[clave] = valor
        # Las equivalencias erróneas detectadas por el año se sobrescriben
        equivalencias_tmdb.update(correcciones_equivalencias)
        with open('equivalencias_peliculas.json', 'w', encoding='utf-8') as f:
            json.dump(equivalencias_tmdb, f, ensure_ascii=False, indent=4)
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
