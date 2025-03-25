import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import logging
import time

# Configurar logging similar al script original
script_dir = os.path.dirname(os.path.abspath(__file__))
log_filename = os.path.join(script_dir, 'logs', f"page_scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
os.makedirs(os.path.join(script_dir, 'logs'), exist_ok=True)

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def obtener_posts_de_pagina(url):
    """Obtener posts de una página específica"""
    logging.info(f"Intentando obtener posts desde: {url}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        posts = soup.find_all('article')
        logging.info(f"Se encontraron {len(posts)} posts en la página")
        return posts
    except Exception as e:
        logging.error(f"Error al obtener posts de {url}: {str(e)}")
        return []

def extraer_info_post(post):
    """Extracción de información de un post (igual que en el script original)"""
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
        response = requests.get(url_original, allow_redirects=True, timeout=10)
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

def guardar_post(post_data):
    """Guardar post en archivo JSON"""
    try:
        filename = f"posts/{post_data['pelicula'].replace(' ', '_')}_{post_data['date'][:10]}.json"
        os.makedirs('posts', exist_ok=True)
        
        logging.info(f"Guardando post en: {filename}")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(post_data, f, ensure_ascii=False, indent=4)
        logging.info("Post guardado exitosamente")
        
    except Exception as e:
        logging.error(f"Error guardando post: {str(e)}")

def actualizar_indice(post_data):
    """Actualizar índice de películas"""
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

def scrape_blog_pages():
    """Scrape páginas del blog comenzando desde la página 2"""
    base_url = "https://ghostintheblog.com/page/{}"
    pagina_num = 2  # Comenzar desde la página 2
    posts_totales = 0
    
    while True:
        url_actual = base_url.format(pagina_num)
        logging.info(f"Scrapeando página {pagina_num}: {url_actual}")
        
        # Obtener posts de la página actual
        posts = obtener_posts_de_pagina(url_actual)
        
        if not posts:
            logging.info(f"No se encontraron posts en la página {pagina_num}. Terminando scraping.")
            break
        
        # Procesar cada post
        for post in posts:
            info_post = extraer_info_post(post)
            if info_post:
                guardar_post(info_post)
                actualizar_indice(info_post)
                posts_totales += 1
        
        # Pausar brevemente para no sobrecargar el servidor
        time.sleep(1)
        
        # Incrementar número de página
        pagina_num += 1
    
    logging.info(f"Scraping completado. Total de posts guardados: {posts_totales}")

def main():
    logging.info("Iniciando scraping de páginas del blog")
    scrape_blog_pages()
    logging.info("Proceso de scraping finalizado")

if __name__ == "__main__":
    main()