import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import urllib.parse


def interpretar_fecha(texto_fecha):
    """Convierte fechas relativas (hoy, mañana) o absolutas a formato estándar (YYYY-MM-DD)."""
    texto_fecha = texto_fecha.strip().lower()
    if "hoy" in texto_fecha:
        return datetime.now().strftime("%Y-%m-%d")
    elif "mañana" in texto_fecha:
        return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        try:
            # Manejar fechas absolutas como "20 de noviembre"
            return datetime.strptime(texto_fecha, "%d de %B").replace(year=datetime.now().year).strftime("%Y-%m-%d")
        except ValueError:
            return texto_fecha  # Devolver sin cambios si no se puede procesar


def download_image(image_url, images_folder):
    """Descarga una imagen si no existe en la carpeta especificada."""
    image_name = os.path.basename(image_url)
    image_path = os.path.join(images_folder, image_name)

    if not os.path.exists(image_path):
        print(f"Descargando imagen: {image_url}")
        img_response = requests.get(image_url)
        if img_response.status_code == 200:
            with open(image_path, 'wb') as img_file:
                img_file.write(img_response.content)
            print(f"Imagen descargada: {image_path}")
        else:
            print(f"Error al descargar la imagen: {image_url} (Código: {img_response.status_code})")
            image_path = None
    else:
        print(f"Imagen ya descargada: {image_path}")

    return image_path


def scrape_golem(url, images_folder):
    """Scraping para el cine Golem."""
    peliculas = []

    # Hacer la solicitud HTTP
    print(f"Solicitando URL: {url}")
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Error al acceder a la URL: {url} (Código: {response.status_code})")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    print("Página Golem cargada correctamente.")

    # Ejemplo: Extraer películas del cine Golem
    peliculas_divs = soup.find_all('div', {'class': 'movie'})  # Ajustar al selector de Golem
    for pelicula_div in peliculas_divs:
        titulo = pelicula_div.find('h3').get_text(strip=True)  # Ajustar al selector del título
        cartel_element = pelicula_div.find('img')  # Ajustar al selector del cartel
        horarios = []  # Rellenar con el scraping de los horarios para Golem

        if cartel_element:
            cartel_url = cartel_element['src']
            cartel_path = download_image(cartel_url, images_folder)
        else:
            cartel_path = None

        peliculas.append({
            "título": titulo,
            "cartel": cartel_path,
            "horarios": horarios
        })

    return peliculas


def scrape_yelmo(url, images_folder):
    """Scraping para el cine Yelmo."""
    peliculas = []

    # Hacer la solicitud HTTP
    print(f"Solicitando URL: {url}")
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Error al acceder a la URL: {url} (Código: {response.status_code})")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    print("Página Yelmo cargada correctamente.")

    # Encontrar contenedores de películas
    peliculas_divs = soup.find_all('div', {'class': 'movie'})
    for pelicula_div in peliculas_divs:
        titulo_element = pelicula_div.find('div', {'class': 'mc-title'})
        if not titulo_element:
            continue
        titulo = titulo_element.get_text(strip=True)

        sesiones_vos_div = pelicula_div.find_all('div', {'class': 'movie-showtimes-n'})
        horarios = []
        for sesion_vos in sesiones_vos_div:
            titulo_sesion = sesion_vos.find('span', {'class': 'fs-5'})
            if not titulo_sesion or "(VOS)" not in titulo_sesion.get_text(strip=True):
                continue

            sesiones = sesion_vos.find_all('div', {'class': 'row g-0 mb-2'})
            for sesion in sesiones:
                fecha_element = sesion.find('span', {'class': 'wday'})
                if fecha_element:
                    fecha = interpretar_fecha(fecha_element.get_text(strip=True))
                else:
                    fecha = None

                horarios_elements = sesion.find_all('a', {'class': 'btn btn-sm btn-outline-secondary'})
                for horario in horarios_elements:
                    link = urllib.parse.unquote(horario.get('href', ''))
                    if "language=VOSE" in link:
                        hora = horario.get_text(strip=True)
                        horarios.append({"fecha": fecha, "hora": hora})

        if horarios:
            cartel_element = pelicula_div.find('img', {'class': 'lazyload'})
            if cartel_element:
                cartel_url = cartel_element['src']
                cartel_path = download_image(cartel_url, images_folder)
            else:
                cartel_path = None

            peliculas.append({
                "título": titulo,
                "cartel": cartel_path,
                "horarios": horarios
            })

    return peliculas


def main():
    # Configuración
    images_folder = "imagenes_cines"  # Carpeta común para las imágenes
    output_path = "peliculas_unificadas.json"  # Archivo JSON unificado

    # URLs
    golem_urls = [
        "https://golem.es/golem/golem-yamaguchi",
        "https://golem.es/golem/golem-la-morea"
    ]
    yelmo_url = "https://www.filmaffinity.com/es/theater-showtimes.php?id=428"

    # Unificar datos
    peliculas = []

    for url in golem_urls:
        peliculas.extend(scrape_golem(url, images_folder))

    peliculas.extend(scrape_yelmo(yelmo_url, images_folder))

    # Guardar en JSON
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json.dump(peliculas, json_file, indent=4, ensure_ascii=False)
        print(f"Resultados guardados en {output_path}")


if __name__ == "__main__":
    main()
