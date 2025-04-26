from dotenv import load_dotenv
import requests
import json
import os
import re
import urllib.request
import logging
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Carga variables de entorno
load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
if not TMDB_API_KEY:
    logger.error("No se ha encontrado la clave API de TMDB. Crea un archivo .env con TMDB_API_KEY=tu_clave")
    sys.exit(1)

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

    def search_movies(self, query: str, language: str = "es") -> list:
        """Busca películas en TMDB por título"""
        logger.info(f"Buscando en TMDB: {query}")
        results = self._make_request("search/movie", params={"query": query, "language": language})
        
        if not results or not results.get("results"):
            # Si no hay resultados en español, intentar en inglés
            if language == "es":
                logger.info(f"No se encontraron resultados en español. Intentando en inglés...")
                return self.search_movies(query, "en")
            else:
                logger.warning(f"No se encontraron resultados para: {query}")
                return []
        
        # Ordenar resultados por popularidad
        sorted_results = sorted(results["results"], key=lambda x: x.get("popularity", 0), reverse=True)
        return sorted_results

    def get_movie_details(self, movie_id: int, language: str = "es") -> dict:
        """Obtiene detalles de una película de TMDB por ID"""
        logger.info(f"Obteniendo detalles para la película ID: {movie_id}")
        
        details = self._make_request(f"movie/{movie_id}", params={"language": language})
        if not details:
            if language == "es":
                logger.info("Intentando obtener detalles en inglés...")
                return self.get_movie_details(movie_id, "en")
            return {}
        
        credits = self._make_request(f"movie/{movie_id}/credits", params={"language": language})
        if not credits and language == "es":
            credits = self._make_request(f"movie/{movie_id}/credits", params={"language": "en"})
        
        if not credits:
            credits = {"cast": [], "crew": []}
        
        return {
            "id": details.get("id"),
            "título": details.get("title"),
            "título_original": details.get("original_title"),
            "director": ", ".join(c["name"] for c in credits.get("crew", []) if c["job"] == "Director"),
            "duración": f"{details.get('runtime', 'Desconocido')} min",
            "actores": ", ".join(a["name"] for a in credits.get("cast", [])[:5]),
            "sinopsis": details.get("overview"),
            "año": details.get("release_date", "")[:4] if details.get("release_date") else "",
            "poster_path": details.get("poster_path"),
            "popularidad": details.get("popularity")
        }

    def download_poster(self, poster_path: str, title: str) -> str:
        """Descarga el póster de una película"""
        if not poster_path:
            return ""
            
        if not os.path.exists('imagenes_filmoteca'):
            os.makedirs('imagenes_filmoteca')
            
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
        nombre_archivo = f"tmdb_{re.sub(r'[^a-zA-Z0-9]', '_', title)}.jpg"
        ruta_imagen = os.path.join('imagenes_filmoteca', nombre_archivo)
        
        try:
            urllib.request.urlretrieve(poster_url, ruta_imagen)
            logger.info(f"Poster guardado en: {ruta_imagen}")
            return ruta_imagen
        except Exception as e:
            logger.error(f"Error al descargar el póster: {str(e)}")
            return ""

class PeliculasManager:
    def __init__(self, tmdb_api: TMDbAPI):
        self.tmdb_api = tmdb_api
        self.archivo_peliculas = 'peliculas_filmoteca.json'
        self.peliculas = self._cargar_peliculas()
        
    def _cargar_peliculas(self) -> List[Dict[str, Any]]:
        """Carga las películas del archivo JSON"""
        try:
            if os.path.exists(self.archivo_peliculas):
                with open(self.archivo_peliculas, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Error al cargar películas: {str(e)}")
            return []
            
    def guardar_peliculas(self):
        """Guarda las películas en el archivo JSON"""
        with open(self.archivo_peliculas, 'w', encoding='utf-8') as f:
            json.dump(self.peliculas, f, ensure_ascii=False, indent=4)
        logger.info(f"Se han guardado {len(self.peliculas)} películas en {self.archivo_peliculas}")
    
    def añadir_pelicula(self, pelicula: Dict[str, Any]):
        """Añade una película a la lista"""
        self.peliculas.append(pelicula)
        self.guardar_peliculas()
        
    def pelicula_existe(self, tmdb_id: int) -> bool:
        """Comprueba si una película ya existe en la lista por su ID de TMDB"""
        return any(p.get("tmdb_id") == tmdb_id for p in self.peliculas)
        
    def actualizar_pelicula(self, tmdb_id: int, nuevos_datos: Dict[str, Any]):
        """Actualiza los datos de una película existente"""
        for i, pelicula in enumerate(self.peliculas):
            if pelicula.get("tmdb_id") == tmdb_id:
                self.peliculas[i] = nuevos_datos
                self.guardar_peliculas()
                return True
        return False
        
    def eliminar_pelicula(self, tmdb_id: int) -> bool:
        """Elimina una película de la lista por su ID de TMDB"""
        for i, pelicula in enumerate(self.peliculas):
            if pelicula.get("tmdb_id") == tmdb_id:
                del self.peliculas[i]
                self.guardar_peliculas()
                return True
        return False
        
    def listar_peliculas(self):
        """Lista todas las películas"""
        for i, p in enumerate(self.peliculas):
            print(f"{i+1}. {p.get('título')} ({p.get('año')}) - {p.get('cine')}")


def validar_fecha(fecha_str: str) -> bool:
    """Valida que una fecha tenga el formato YYYY-MM-DD"""
    try:
        datetime.strptime(fecha_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False
        
def validar_hora(hora_str: str) -> bool:
    """Valida que una hora tenga el formato HH:MM"""
    try:
        datetime.strptime(hora_str, '%H:%M')
        return True
    except ValueError:
        return False

def crear_pelicula_manual():
    """Interfaz para crear una película manualmente"""
    tmdb_api = TMDbAPI(TMDB_API_KEY)
    manager = PeliculasManager(tmdb_api)
    
    print("\n=== ADMINISTRADOR DE PELÍCULAS ===\n")
    
    while True:
        print("\nMENÚ PRINCIPAL:")
        print("1. Buscar y añadir nueva película")
        print("2. Listar películas")
        print("3. Eliminar película")
        print("4. Salir")
        
        opcion = input("\nSelecciona una opción: ")
        
        if opcion == "1":
            # Buscar película
            query = input("\nIntroduce el título a buscar: ")
            if not query:
                print("Búsqueda cancelada.")
                continue
                
            resultados = tmdb_api.search_movies(query)
            
            if not resultados:
                print("No se encontraron resultados.")
                continue
                
            print("\nResultados de la búsqueda:")
            for i, movie in enumerate(resultados[:10]):  # Mostrar solo los 10 primeros resultados
                año = movie.get("release_date", "")[:4] if movie.get("release_date") else "Desconocido"
                print(f"{i+1}. {movie.get('title')} ({año}) - {movie.get('original_title')}")
                
            seleccion = input("\nSelecciona un número (0 para cancelar): ")
            try:
                indice = int(seleccion) - 1
                if indice == -1:
                    print("Selección cancelada.")
                    continue
                    
                if 0 <= indice < len(resultados):
                    pelicula_tmdb = resultados[indice]
                    detalles = tmdb_api.get_movie_details(pelicula_tmdb["id"])
                    
                    print("\nDetalles de la película:")
                    print(f"Título: {detalles.get('título')}")
                    print(f"Título original: {detalles.get('título_original')}")
                    print(f"Director: {detalles.get('director')}")
                    print(f"Duración: {detalles.get('duración')}")
                    print(f"Año: {detalles.get('año')}")
                    print(f"Actores: {detalles.get('actores')}")
                    print(f"Sinopsis: {detalles.get('sinopsis')[:100)}..." if detalles.get('sinopsis') else "No disponible")
                    
                    confirmar = input("\n¿Añadir esta película? (s/n): ").lower()
                    if confirmar != 's':
                        print("Operación cancelada.")
                        continue
                    
                    # Descargar póster
                    ruta_poster = tmdb_api.download_poster(detalles.get("poster_path"), detalles.get("título"))
                    
                    # Información del cine y horarios
                    cine = input("\nIntroduce el nombre del cine: ")
                    
                    horarios = []
                    while True:
                        print("\nAñadir horario (deja vacío para terminar):")
                        fecha = input("Fecha (YYYY-MM-DD): ")
                        if not fecha:
                            break
                            
                        if not validar_fecha(fecha):
                            print("Formato de fecha incorrecto. Usa YYYY-MM-DD.")
                            continue
                            
                        hora = input("Hora (HH:MM): ")
                        if not validar_hora(hora):
                            print("Formato de hora incorrecto. Usa HH:MM.")
                            continue
                            
                        enlace = input("Enlace para comprar entradas (opcional): ")
                        
                        horarios.append({
                            "fecha": fecha,
                            "hora": hora,
                            "enlace_entradas": enlace
                        })
                    
                    # Crear la estructura final de la película
                    nueva_pelicula = {
                        "título": detalles.get("título"),
                        "tmdb_id": detalles.get("id"),
                        "director": detalles.get("director"),
                        "duración": detalles.get("duración"),
                        "actores": detalles.get("actores"),
                        "sinopsis": detalles.get("sinopsis"),
                        "año": detalles.get("año"),
                        "cartel": ruta_poster,
                        "cine": cine,
                        "horarios": horarios
                    }
                    
                    # Añadir a la lista
                    manager.añadir_pelicula(nueva_pelicula)
                    print(f"\n¡Película '{detalles.get('título')}' añadida correctamente!")
                else:
                    print("Número inválido.")
            except ValueError:
                print("Por favor, introduce un número válido.")
                
        elif opcion == "2":
            # Listar películas
            if not manager.peliculas:
                print("\nNo hay películas guardadas.")
            else:
                print("\nLista de películas:")
                manager.listar_peliculas()
                
        elif opcion == "3":
            # Eliminar película
            if not manager.peliculas:
                print("\nNo hay películas para eliminar.")
                continue
                
            print("\nPelículas disponibles:")
            manager.listar_peliculas()
            
            seleccion = input("\nNúmero de la película a eliminar (0 para cancelar): ")
            try:
                indice = int(seleccion) - 1
                if indice == -1:
                    print("Eliminación cancelada.")
                    continue
                    
                if 0 <= indice < len(manager.peliculas):
                    pelicula = manager.peliculas[indice]
                    confirmar = input(f"\n¿Eliminar '{pelicula.get('título')}'? (s/n): ").lower()
                    
                    if confirmar == 's':
                        tmdb_id = pelicula.get("tmdb_id")
                        if manager.eliminar_pelicula(tmdb_id):
                            print("Película eliminada correctamente.")
                        else:
                            print("Error al eliminar la película.")
                    else:
                        print("Eliminación cancelada.")
                else:
                    print("Número inválido.")
            except ValueError:
                print("Por favor, introduce un número válido.")
                
        elif opcion == "4":
            # Salir
            print("\n¡Hasta pronto!")
            break
        else:
            print("\nOpción inválida. Inténtalo de nuevo.")

if __name__ == "__main__":
    crear_pelicula_manual()
