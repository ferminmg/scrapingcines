from dotenv import load_dotenv
import requests
import time
# `requests` dice «Python» en la huella TLS de la conexión (JA3/JA4) y
# Cloudflare bloquea peticiones a la API de Cinépolis antes de recibir
# cabeceras. curl-cffi lanza curl compilado con huella de Chrome, que
# es lo que hace el navegador y lo único que ha pasado en las pruebas.
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import urllib.request
import urllib.parse
import re
from difflib import SequenceMatcher
import logging
import sys

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


# El nombre del cartel de TMDb sale de su ruta en TMDb (única por imagen), no
# del título: si el emparejamiento cambia, cambia también la URL y la app no
# sigue mostrando el cartel anterior que guarda en caché (21 días por URL).
def nombre_cartel_tmdb(poster_path: str) -> str:
    base = re.sub(r'[^A-Za-z0-9_-]', '', os.path.splitext(os.path.basename(poster_path or ''))[0])
    return f"tmdb_{base}.jpg"

def descargar_cartel(url, destino):
    """Descarga una imagen sin tumbar el scraper si falla (403, 404, timeout...).

    Devuelve True si el fichero queda disponible en 'destino'.
    """
    if os.path.exists(destino):
        return True
    try:
        # Las URLs de los carteles llevan caracteres no ASCII (p. ej.
        # .../assets/España/...) y urllib no los percent-encodea: falla con
        # 'ascii' codec can't encode. Se codifican solo los caracteres
        # fuera del safe, sin tocar los separadores ni lo ya codificado.
        peticion = urllib.request.Request(
            urllib.parse.quote(url, safe=':/?&=%#[]@!$\'()*+,;-._~'),
            headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(peticion, timeout=20) as respuesta, open(destino, 'wb') as f:
            f.write(respuesta.read())
        return True
    except Exception as e:
        print(f"No se pudo descargar el cartel {url}: {e}")
        if os.path.exists(destino):
            os.remove(destino)
        return False

# ---------------------------------------------------------------------------
# Yelmo pasó a finales de octubre de 2026 a la plataforma de Cinépolis
# (cineyelmo.com). El antiguo endpoint
#   https://www.yelmocines.es/now-playing.aspx/GetNowPlaying
# ahora redirige a la portada de cineyelmo.com, que devuelve 403 a los
# runners de GitHub. La web nueva saca la cartelera de la API GraphQL de
# Cinépolis; esa misma API es la que se consulta aquí.
#
# La clave x-apikey es la que la propia web envía desde el navegador (es
# pública). Si un día la cambian, basta con copiar la nueva desde las
# peticiones a api-g.cinepolis.com en las herramientas de desarrollo y
# guardarla en el secreto YELMO_API_KEY.
# ---------------------------------------------------------------------------

IMAGES_DIR = "imagenes_filmaffinity"
SALIDA = 'peliculas_filmaffinity.json'

API_URL = "https://api-g.cinepolis.com/v2/billboards/graphql"
API_KEY_POR_DEFECTO = "lQM6Mkvri1iHksKKCfpAiwGXq0YUZA7Nn6XAXRPr4i13LwXo"

# Cines de Yelmo en Navarra: id en la API -> nombre que ve la app
CINES = {
    "itaroa-navarra": "Yelmo Itaroa",
}

ENLACE_ENTRADAS = ("https://cineyelmo.com/es/asientos?country=es&cinema={cine}"
                   "&selected={cine}&movie={pelicula}&session={sesion}")

QUERY_BILLBOARD = """
query Billboard($countryId: String!, $cinemaId: String!, $timezone: String!, $isAbsoluteExperiencePath: Boolean) {
  billboardByCinema(countryId: $countryId, cinemaId: $cinemaId, timezone: $timezone, isAbsoluteExperiencePath: $isAbsoluteExperiencePath) {
    dates
    schedules {
      cinemaId
      movieId
      dates {
        date
        languages {
          language
          displayLanguage
          showtimes {
            format { name }
            sessionId
            datetime
            screen
            cinemaVistaId
          }
        }
      }
    }
  }
}
"""

QUERY_MOVIES = """
query Movies($countryId: String!, $category: String, $cinemas: String, $limit: Int, $isAbsoluteMediaPath: Boolean) {
  movies(countryId: $countryId, category: $category, cinemas: $cinemas, limit: $limit, isAbsoluteMediaPath: $isAbsoluteMediaPath) {
    edges {
      node {
        id
        name
        originalName
        languages
        media { type code sizes { large medium } }
      }
    }
  }
}
"""


def cuerpo_error(respuesta):
    """Resumen diagnóstico de una respuesta rechazada (sin secretos).

    'cf-mitigated' distingue el tipo de defensa de Cloudflare: 'challenge'
    (reto de JavaScript) vs bloqueo duro; el cuerpo confirma la página.
    """
    claves = ('server', 'cf-ray', 'cf-mitigated', 'content-type', 'retry-after')
    cabeceras = {k: respuesta.headers.get(k) for k in claves if respuesta.headers.get(k)}
    cuerpo = re.sub(r'\s+', ' ', (respuesta.text or ''))[:400]
    return f"status={respuesta.status_code} cabeceras={cabeceras} cuerpo={cuerpo!r}"


def consulta_graphql(operacion, query, variables):
    """Lanza una consulta a la API de Cinépolis y devuelve 'data'.

    La API va detrás de Cloudflare y su protección bloquea con 403 a las
    IP de datacenter (GitHub Actions), pese a la huella TLS de Chrome.
    Dos caminos:
    - Con YELMO_WORKER_URL definido: la llamada sale a través del Worker
      de Cloudflare (cloudflare/yelmo-proxy-worker.js), que consulta la
      API desde la propia red de Cloudflare. Ahí ni cookies ni
      reintentos aportan nada: una petición directa.
    - Sin proxy ( ejecución local ): sesión con huella de Chrome y una
      primera visita a la portada para recoger la cookie __cf_bm,
      reintentando tras el nuevo GET si contesta 403.
    Si la respuesta se rechaza, la excepción trae el diagnóstico (incluye
    cf-mitigated) para distinguir un reto resolvible de un bloqueo duro.
    Cualquier fallo (red, HTTP, JSON o errores GraphQL) se propaga como
    excepción: el script tiene que acabar en error para que el workflow lo
    marque en rojo en vez de dejar publicados los datos viejos.
    """
    destino = os.getenv("YELMO_WORKER_URL") or API_URL
    via_proxy = destino != API_URL
    token_proxy = os.getenv("YELMO_PROXY_TOKEN")
    cabeceras = {
        "accept": "*/*",
        "content-type": "application/json",
        "country-id": "ES",
        "language": "es",
        "x-apikey": os.getenv("YELMO_API_KEY") or API_KEY_POR_DEFECTO,
        "origin": "https://cineyelmo.com",
        "referer": "https://cineyelmo.com/",
    }
    if token_proxy:
        # El token no es de la API: es para que solo el scraper use nuestro
        # Worker (el Worker también lo comprueba contra su variable).
        cabeceras["x-proxy-token"] = token_proxy
    sesion = curl_requests.Session(impersonate="chrome")

    if not via_proxy:
        # el user-agent lo pone completo la impersonación de Chrome: así casa con la huella TLS
        try:
            portada = sesion.get("https://cineyelmo.com/es", timeout=30)
            print(f"  Portada cineyelmo.com: {portada.status_code}")
        except Exception as e:
            print(f"  Aviso: no se pudo precargar la portada de cineyelmo.com: {e}")

    respuesta = None
    for intento in (1, 2):
        if intento > 1:
            if via_proxy:
                break  # el proxy no mejora con reintentos de cookie
            time.sleep(3)
            try:
                sesion.get("https://cineyelmo.com/es", timeout=30)
            except Exception as e:
                print(f"  Aviso: no se pudo renovar la portada: {e}")
        respuesta = sesion.post(
            destino,
            headers=cabeceras,
            json={"operationName": operacion, "variables": variables, "query": query},
            timeout=30,
        )
        if respuesta.status_code != 403:
            break
        print(f"  Intento {intento}: la API devolvió 403: {cuerpo_error(respuesta)}")
    if respuesta.status_code >= 400:
        raise RuntimeError(f"La API de Cinépolis rechazó la petición ({operacion}): "
                           f"{cuerpo_error(respuesta)}")
    cuerpo = respuesta.json()
    if cuerpo.get("errors"):
        raise RuntimeError(f"Errores GraphQL en {operacion}: {cuerpo['errors']}")
    if not cuerpo.get("data"):
        raise RuntimeError(f"Respuesta de {operacion} sin 'data'")
    return cuerpo["data"]


def es_vose(idioma, titulo):
    """True si la sesión es en versión original subtitulada.

    La API marca el doblaje como 'ESP' / 'ESPAÑOL' y la VOSE como
    'SUB ESP' (o variantes con SUB / VOSE / VO). Algunas películas en VOSE
    vienen además como ficha aparte con '(VOSE)' en el título.
    """
    texto = (idioma or '').upper()
    if re.search(r'\bSUB\b|VOSE|\bV\.?O\b|ORIGINAL', texto):
        return True
    return bool(re.search(r'\(\s*VOSE?\s*\)', titulo or '', re.IGNORECASE))


def limpiar_titulo(titulo):
    """Quita la coletilla '(VOSE)' y arregla los títulos en mayúsculas."""
    titulo = re.sub(r'\s*\(\s*VOSE?\s*\)\s*$', '', titulo or '', flags=re.IGNORECASE).strip()
    if titulo.isupper():
        titulo = titulo.title()
    return titulo


def poster_de(nodo):
    for media in nodo.get('media') or []:
        if media.get('code') == 'poster' and media.get('sizes'):
            return media['sizes'].get('large') or media['sizes'].get('medium') or ''
    return ''


def peliculas_del_cine(cine_id):
    """Diccionario movieId -> ficha (título, cartel) del cine dado."""
    fichas = {}
    for categoria in ("now-playing", "coming-soon"):
        datos = consulta_graphql("Movies", QUERY_MOVIES, {
            "countryId": "ES", "category": categoria, "cinemas": cine_id,
            "limit": 100, "isAbsoluteMediaPath": True,
        })
        for arista in (datos.get('movies') or {}).get('edges') or []:
            nodo = arista.get('node') or {}
            if nodo.get('id') and nodo['id'] not in fichas:
                fichas[nodo['id']] = nodo
    return fichas


def generar_peliculas(tmdb_api):
    peliculas = []  # en el mismo formato que antes: lo lee la app tal cual

    for cine_id, nombre_cine in CINES.items():
        print(f"Consultando la cartelera de {nombre_cine} ({cine_id})...")
        fichas = peliculas_del_cine(cine_id)
        cartelera = consulta_graphql("Billboard", QUERY_BILLBOARD, {
            "countryId": "ES", "cinemaId": cine_id,
            "timezone": "Europe/Madrid", "isAbsoluteExperiencePath": True,
        })['billboardByCinema']

        schedules = cartelera.get('schedules') or []
        print(f"  {len(schedules)} películas con sesiones, {len(fichas)} fichas")

        for programa in schedules:
            movie_id = programa['movieId']
            ficha = fichas.get(movie_id, {})
            titulo_api = ficha.get('name') or movie_id.replace('-', ' ').capitalize()

            horarios = []
            for dia in programa.get('dates') or []:
                for idioma in dia.get('languages') or []:
                    if not es_vose(idioma.get('language'), titulo_api):
                        continue
                    for sesion in idioma.get('showtimes') or []:
                        # 'datetime' viene en hora local de Madrid: 2026-11-06T17:05:00
                        fecha, _, hora = (sesion.get('datetime') or '').partition('T')
                        horarios.append({
                            'fecha': fecha or dia['date'],
                            'hora': hora[:5],
                            'enlace_entradas': ENLACE_ENTRADAS.format(
                                cine=cine_id, pelicula=movie_id, sesion=sesion['sessionId']),
                        })

            if not horarios:
                continue

            titulo = limpiar_titulo(titulo_api)
            horarios.sort(key=lambda h: (h['fecha'], h['hora']))

            existente = next((p for p in peliculas
                              if p['título'] == titulo and p['cine'] == nombre_cine), None)
            if existente:
                existente['horarios'].extend(horarios)
                existente['horarios'].sort(key=lambda h: (h['fecha'], h['hora']))
                continue

            poster_filename = ''
            poster_url = poster_de(ficha)
            if poster_url:
                destino = os.path.join(IMAGES_DIR, f"{re.sub(r'[^A-Za-z0-9_-]', '', movie_id)}.jpg")
                if descargar_cartel(poster_url, destino):
                    poster_filename = destino

            tmdb_info = tmdb_api.get_movie_info(titulo)
            if not tmdb_info and ficha.get('originalName') and limpiar_titulo(ficha['originalName']) != titulo:
                tmdb_info = tmdb_api.get_movie_info(limpiar_titulo(ficha['originalName']))
            if tmdb_info.get('poster_path'):
                tmdb_poster_url = f"https://image.tmdb.org/t/p/w500{tmdb_info['poster_path']}"
                tmdb_poster_filename = os.path.join(IMAGES_DIR, nombre_cartel_tmdb(tmdb_info['poster_path']))
                if descargar_cartel(tmdb_poster_url, tmdb_poster_filename):
                    poster_filename = tmdb_poster_filename

            peliculas.append({
                'título': titulo,
                'cartel': poster_filename,
                'horarios': horarios,
                'cine': nombre_cine,
                'director': tmdb_info.get('director'),
                'duración': tmdb_info.get('duración'),
                'actores': tmdb_info.get('actores'),
                'sinopsis': tmdb_info.get('sinopsis'),
                'año': tmdb_info.get('año'),
                'tmdb_id': tmdb_info.get('tmdb_id'),
            })

    return peliculas


def main():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    load_dotenv()
    tmdb_api = TMDbAPI(os.getenv("TMDB_API_KEY"))

    print("Scraping cineyelmo.com (API de Cinépolis)...")
    try:
        peliculas = generar_peliculas(tmdb_api)
    except Exception as e:
        # Antes aquí se salía con código 0 y el fallo pasaba desapercibido:
        # la app seguía mostrando horarios viejos sin que nada avisara.
        # No se toca el JSON publicado, pero la ejecución queda en rojo.
        print(f"ERROR: no se ha podido leer la cartelera de Yelmo: {e}")
        sys.exit(1)

    with open(SALIDA, 'w', encoding='utf-8') as f:
        json.dump(peliculas, f, ensure_ascii=False, indent=4)

    total = sum(len(p['horarios']) for p in peliculas)
    print(f"Archivo JSON {SALIDA} creado con éxito: {len(peliculas)} películas VOSE, {total} sesiones.")
    print("Fin del scraping.")


if __name__ == '__main__':
    main()
