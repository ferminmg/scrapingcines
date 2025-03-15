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
        
        # Crear el nombre del archivo que tendría
        partes = titulo.split(' de ')
        if len(partes) == 2:
            pelicula = partes[0].strip()
        else:
            pelicula = titulo
            
        nombre_archivo = f"posts/{pelicula.replace(' ', '_')}_{fecha[:10]}.json"
        
        # Verificar si ya existe
        if os.path.exists(nombre_archivo):
            logging.info(f"Post ya existente, saltando: {titulo}")
            return None
            
        # Si no existe, continuar con el scraping
        url_original = post.find('h2').find('a')['href']
        logging.info(f"Título del post: {titulo}")
        logging.info(f"Fecha del post: {fecha}")
        
        # Extraer película y director del título
        partes = titulo.split(' de ')
        if len(partes) == 2:
            pelicula = partes[0].strip()
            director = partes[1].strip()
        else:
            pelicula = titulo
            director = "Desconocido"
            logging.warning(f"No se pudo extraer director del título: {titulo}")
        
        # Obtener contenido del post completo
        logging.info(f"Obteniendo contenido completo de: {url_original}")
        response = requests.get(url_original, allow_redirects=True)
        response.raise_for_status()
        url_final = response.url
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extraer solo el contenido
        contenido_div = soup.find('div', class_='entry-content')
        if contenido_div:
            # Primero, reemplazar los <br> y </p> con marcadores temporales
            for br in contenido_div.find_all('br'):
                br.replace_with('||BR||')
            for p in contenido_div.find_all('p'):
                p.append('||P||')
            
            # Reemplazar los enlaces con su texto plano
            for a in contenido_div.find_all('a'):
                a.replace_with(a.get_text())
            
            # Obtener el texto y restaurar los saltos de línea
            contenido_completo = contenido_div.get_text()
            contenido_completo = contenido_completo.replace('||BR||', '\n')
            contenido_completo = contenido_completo.replace('||P||', '\n\n')
            
            # Limpiar espacios múltiples
            contenido_completo = ' '.join(line.strip() for line in contenido_completo.split('\n'))
            
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