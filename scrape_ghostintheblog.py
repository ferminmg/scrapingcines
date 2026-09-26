# scrape all post from a blogger blog. every post should be saved in a json file.
# la estructura de la base de datos es la siguiente:
# {
#     "title": "title of the post",
#     "pelicula": "name of the movie",
#     "director": "name of the director",
#     "url": "url of the post",
#     "date": "date of the post",
#     "content": "content of the post"
# }
#
# El title del post tiene la siguiente estructura: "pelicula" + "de" + "director"
# La url del blog es: https://ghostintheblog.com/
# Este script se ejecutará una vez al día, por lo que antes de generar el json debes  comprobar si hay 
# posts nuevos, si no hay, no borrar los archivos json anteriores.
# 

import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime
import logging

# Configurar logging
script_dir = os.path.dirname(os.path.abspath(__file__))
log_filename = os.path.join(script_dir, 'logs', f"scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
os.makedirs(os.path.join(script_dir, 'logs'), exist_ok=True)

# Handler para archivo
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setLevel(logging.INFO)

# Handler para consola
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Formato para los logs
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Configurar el logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Partículas admitidas dentro del nombre del director
PARTICULAS_DIRECTOR = {'de', 'del', 'la', 'los', 'y', '&', 'el', 'las',
                       'con', 'por', 'para', 'sin', 'sobre', 'entre', 'un', 'una'}

def split_titulo_director(titulo):
    """Divide el título del post en (película, director).

    Se prueba cada ' de ' de izquierda a derecha y se acepta la primera cuya
    parte derecha parece un nombre propio: 1-8 palabras, sin dígitos, sin '/',
    cada palabra empezada por mayúscula o siendo partícula. Así los apellidos
    compuestos ('Dani de la Orden', 'Fernando León de Aranoa') se conservan
    enteros en lugar de cortarse por la última partícula.

    Los posts con dos películas (título con ' / ') no tienen una sola pareja
    título/director fiable: se devuelve el título completo y 'Desconocido',
    para que el respaldo del contenido (extraer_director_contenido) resuelva.
    """
    titulo = titulo.strip()
    if ' / ' in titulo:
        return titulo, "Desconocido"
    inicio = 0
    while True:
        indice = titulo.find(' de ', inicio)
        if indice <= 0:
            break
        pelicula = titulo[:indice].strip()
        director = titulo[indice + 4:].strip()
        palabras = director.split()
        if (1 <= len(palabras) <= 8
                and not any(c.isdigit() for c in director)
                and '/' not in director
                and all(p and (p[0].isupper() or p.lower() in PARTICULAS_DIRECTOR)
                        for p in palabras)):
            return pelicula, director
        inicio = indice + 1
    return titulo, "Desconocido"

def rutas_post(pelicula, titulo, fecha):
    """Ruta nueva (película ya separada) y ruta heredada (título completo)."""
    dia = fecha[:10]
    return (f"posts/{pelicula.replace(' ', '_')}_{dia}.json",
            f"posts/{titulo.replace(' ', '_')}_{dia}.json")

def extraer_director_contenido(contenido):
    """Respaldo: busca 'Dirección:'/'Direccion:' en el contenido del post.

    Devuelve el texto hasta el siguiente salto de línea o ';', como mucho 60
    caracteres, recortado. None si no aparece.
    """
    if not contenido:
        return None
    coincidencia = re.search(r'Direcci(?:ó|o)n\s*:', contenido)
    if not coincidencia:
        return None
    director = re.split(r'[;\n]', contenido[coincidencia.end():], maxsplit=1)[0].strip()[:60].strip()
    return director or None

def obtener_posts():
    url = "https://ghostintheblog.com/"
    logging.info(f"Intentando obtener posts desde: {url}")
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        posts = soup.find_all('article')
        logging.info(f"Se encontraron {len(posts)} posts")
        return posts
    except Exception as e:
        logging.error(f"Error al obtener posts: {str(e)}")
        return []

def extraer_info_post(post):
    logging.info("Comenzando extracción de información del post")
    try:
        # Obtener información básica primero
        titulo = post.find('h2').text.strip()
        fecha = post.find('time')['datetime']
        
        # Película y director se derivan con la misma división que la que
        # genera el nombre del archivo, para que no puedan divergir
        pelicula, director = split_titulo_director(titulo)
        if director == "Desconocido":
            logging.warning(f"No se pudo extraer director del título: {titulo}")
            
        # Crear el nombre del archivo que tendría (y la ruta heredada, con el
        # título completo, para no re-scrapear posts históricos guardados con
        # la división anterior título/director)
        nombre_archivo, nombre_heredado = rutas_post(pelicula, titulo, fecha)

        # Verificar si ya existe
        if os.path.exists(nombre_archivo) or os.path.exists(nombre_heredado):
            logging.info(f"Post ya existente, saltando: {titulo}")
            return None
            
        # Si no existe, continuar con el scraping
        url_original = post.find('h2').find('a')['href']
        logging.info(f"Título del post: {titulo}")
        logging.info(f"Fecha del post: {fecha}")
        
        # Obtener contenido del post completo
        logging.info(f"Obteniendo contenido completo de: {url_original}")
        response = requests.get(url_original, allow_redirects=True)
        response.raise_for_status()
        url_final = response.url
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extraer solo el contenido
        contenido_div = soup.find('div', class_='entry-content')
        if contenido_div:
            # Primero, reemplazar los enlaces con su texto plano
            for a in contenido_div.find_all('a'):
                a.replace_with(a.get_text())
            
            # Obtener párrafos individuales
            parrafos = contenido_div.find_all('p')
            contenido_completo = ''
            
            for p in parrafos:
                # Obtener el texto del párrafo y limpiar espacios extra
                texto_parrafo = ' '.join(p.get_text().split())
                contenido_completo += texto_parrafo + '\n\n'
            
            # Eliminar saltos de línea extra al final
            contenido_completo = contenido_completo.rstrip()
            
            # Buscar el índice de "Título Original"
            indice_inicio = contenido_completo.find("Título Original")
            
            if indice_inicio != -1:
                # Extraer desde "Título Original"
                contenido_parcial = contenido_completo[indice_inicio:].strip()
                
                # Buscar el final de la información técnica (después del último dato técnico)
                datos_tecnicos = ["Dirección", "Guion", "Intérpretes", "País", "Duración"]
                ultimo_indice = -1
                
                for dato in datos_tecnicos:
                    indice = contenido_parcial.find(dato)
                    if indice != -1:
                        ultimo_indice = max(ultimo_indice, 
                            contenido_parcial.find('\n', indice) if contenido_parcial.find('\n', indice) != -1 
                            else len(contenido_parcial))
                
                if ultimo_indice != -1:
                    # Extraer la ficha técnica
                    ficha_tecnica = contenido_parcial[:ultimo_indice].strip()
                    
                    # Extraer el resto del contenido (la crítica)
                    critica = contenido_parcial[ultimo_indice:].strip()
                    
                    # Combinar en formato estructurado
                    contenido = f"{ficha_tecnica}\n\nCRÍTICA:\n{critica}"
                    
                    logging.info(f"Contenido extraído y estructurado ({len(contenido)} caracteres)")
                    logging.debug(f"Ficha técnica: {ficha_tecnica[:200]}")
                else:
                    contenido = contenido_parcial
                    logging.warning("No se pudo separar la ficha técnica de la crítica")
            else:
                logging.warning("No se encontró 'Título Original' en el contenido")
                contenido = contenido_completo
                logging.info("Usando contenido completo como respaldo")
        else:
            logging.error("No se encontró el div de contenido")
            contenido = ""
        
        # Respaldo: si el título no llevaba el director, buscarlo en la ficha técnica
        if director == "Desconocido":
            director_respaldo = extraer_director_contenido(contenido)
            if director_respaldo:
                director = director_respaldo
                logging.info(f"Director obtenido del contenido: {director}")
        
        post_data = {
            "title": titulo,
            "pelicula": pelicula,
            "director": director,
            "url": url_final,
            "date": fecha,
            "content": contenido
        }
        
        # Verificar la estructura del post
        campos_requeridos = ["title", "pelicula", "director", "url", "date", "content"]
        for campo in campos_requeridos:
            if not post_data.get(campo):
                logging.warning(f"Campo {campo} vacío o no presente en el post")
        
        return post_data
        
    except Exception as e:
        logging.error(f"Error procesando post: {str(e)}")
        return None

def actualizar_indice(post_data):
    logging.info("Actualizando índice de películas")
    try:
        index_file = os.path.join(script_dir, 'index.json')
        logging.info(f"Archivo de índice: {index_file}")
        
        # Crear estructura del índice
        pelicula_index = {
            "título": post_data['pelicula'],
            "director": post_data['director'],
            "fecha_post": post_data['date'][:10],
            "archivo": f"posts/{post_data['pelicula'].replace(' ', '_')}_{post_data['date'][:10]}.json"
        }
        
        # Cargar índice existente o crear uno nuevo
        if os.path.exists(index_file):
            with open(index_file, 'r', encoding='utf-8') as f:
                index = json.load(f)
                logging.info(f"Índice existente cargado con {len(index)} películas")
        else:
            index = []
            logging.info("Creando nuevo índice")
            
        # Verificar si la película ya existe en el índice
        existe = False
        for item in index:
            if item['título'] == pelicula_index['título']:
                existe = True
                break
                
        # Agregar solo si no existe
        if not existe:
            index.append(pelicula_index)
            # Ordenar por título
            index.sort(key=lambda x: x['título'])
            
            # Guardar índice actualizado
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, ensure_ascii=False, indent=4)
            logging.info(f"Película agregada al índice: {pelicula_index['título']}")
        else:
            logging.info(f"La película ya existe en el índice: {pelicula_index['título']}")
            
    except Exception as e:
        logging.error(f"Error actualizando el índice: {str(e)}")
        raise

def guardar_post(post_data):
    try:
        filename = f"posts/{post_data['pelicula'].replace(' ', '_')}_{post_data['date'][:10]}.json"
        os.makedirs('posts', exist_ok=True)
        
        logging.info(f"Guardando post en: {filename}")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(post_data, f, ensure_ascii=False, indent=4)
        logging.info("Post guardado exitosamente")
        
        # Actualizar el índice después de guardar el post
        actualizar_indice(post_data)
        
    except Exception as e:
        logging.error(f"Error guardando post: {str(e)}")

def main():
    logging.info("Iniciando proceso de scraping")
    
    # Obtener posts existentes
    posts_existentes = set()
    if os.path.exists('posts'):
        for archivo in os.listdir('posts'):
            if archivo.endswith('.json'):
                posts_existentes.add(archivo)
    logging.info(f"Posts existentes encontrados: {len(posts_existentes)}")
    
    # Obtener posts nuevos
    posts = obtener_posts()
    
    posts_nuevos = 0
    for post in posts:
        info_post = extraer_info_post(post)
        if info_post:
            nombre_archivo = f"{info_post['pelicula'].replace(' ', '_')}_{info_post['date'][:10]}.json"
            
            # Solo guardar si es un post nuevo
            if nombre_archivo not in posts_existentes:
                guardar_post(info_post)
                posts_nuevos += 1
                logging.info(f"Nuevo post guardado: {info_post['title']}")
    
    logging.info(f"Proceso completado. Posts nuevos guardados: {posts_nuevos}")

if __name__ == "__main__":
    main()

# Fin del script