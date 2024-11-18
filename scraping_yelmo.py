import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import urllib.parse


def interpretar_fecha(texto_fecha):
    """Convierte fechas relativas (hoy, mañana) o días de la semana a formato estándar (YYYY-MM-DD)."""
    texto_fecha = texto_fecha.strip().lower()
    dias_semana = {
        "lunes": 0,
        "martes": 1,
        "miércoles": 2,
        "jueves": 3,
        "viernes": 4,
        "sábado": 5,
        "domingo": 6
    }
    
    # Si el texto contiene "hoy" o "mañana"
    if "hoy" in texto_fecha:
        return datetime.now().strftime("%Y-%m-%d")
    elif "mañana" in texto_fecha:
        return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Si es un día de la semana
    for dia, numero in dias_semana.items():
        if dia in texto_fecha:
            hoy = datetime.now()
            delta_dias = (numero - hoy.weekday() + 7) % 7
            fecha_obj = hoy + timedelta(days=delta_dias)
            return fecha_obj.strftime("%Y-%m-%d")
    
    # Intentar convertir fechas absolutas como "20 de noviembre"
    try:
        return datetime.strptime(texto_fecha, "%d de %B").replace(year=datetime.now().year).strftime("%Y-%m-%d")
    except ValueError:
        return texto_fecha  # Devolver sin cambios si no se puede procesar


def scrape_filmaffinity_vos(url, images_folder):
    peliculas = []

    # Crear carpeta para guardar las imágenes
    if not os.path.exists(images_folder):
        os.makedirs(images_folder)
        print(f"Carpeta creada: {images_folder}")
    else:
        print(f"Carpeta existente: {images_folder}")

    # Hacer la solicitud HTTP
    print(f"Solicitando URL: {url}")
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Error al acceder a la URL: {url} (Código: {response.status_code})")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    print("Página cargada correctamente.")

    # Encontrar contenedores de películas
    peliculas_divs = soup.find_all('div', {'class': 'movie'})
    print(f"Encontradas {len(peliculas_divs)} películas en la página.")

    for i, pelicula_div in enumerate(peliculas_divs):
        print(f"\nProcesando película #{i + 1}...")

        # Título de la película
        titulo_element = pelicula_div.find('div', {'class': 'mc-title'})
        if titulo_element:
            titulo = titulo_element.get_text(strip=True)
            print(f"Título encontrado: {titulo}")
        else:
            print("No se encontró el título de la película.")
            continue

        # Buscar sesiones que contengan "(VOS)" en el título
        sesiones_vos_div = pelicula_div.find_all('div', {'class': 'movie-showtimes-n'})
        print(f"Encontrados {len(sesiones_vos_div)} bloques de sesiones para esta película.")

        horarios = []

        for j, sesion_vos in enumerate(sesiones_vos_div):
            print(f"  Procesando bloque de sesiones #{j + 1}...")
            titulo_sesion = sesion_vos.find('span', {'class': 'fs-5'})
            if titulo_sesion:
                titulo_sesion_text = titulo_sesion.get_text(strip=True)
                print(f"  Título de la sesión: {titulo_sesion_text}")
                if "(VOS)" not in titulo_sesion_text:
                    print("  No es una sesión VOS. Ignorando...")
                    continue
            else:
                print("  No se encontró el título de la sesión. Ignorando...")
                continue

            # Obtener horarios y fechas de sesiones VOS
            sesiones = sesion_vos.find_all('div', {'class': 'row g-0 mb-2'})
            print(f"  Encontradas {len(sesiones)} sesiones en este bloque.")

            for k, sesion in enumerate(sesiones):
                print(f"    Procesando sesión #{k + 1}...")
                # Fecha de la sesión
                fecha_element = sesion.find('span', {'class': 'wday'})
                if fecha_element:
                    fecha_texto = fecha_element.get_text(strip=True)
                    fecha = interpretar_fecha(fecha_texto)
                    print(f"    Fecha encontrada: {fecha_texto} -> {fecha}")
                else:
                    print("    No se encontró la fecha de la sesión.")
                    fecha = None

                # Horarios de la sesión
                horarios_elements = sesion.find_all('a', {'class': 'btn btn-sm btn-outline-secondary'})
                print(f"    Encontrados {len(horarios_elements)} horarios en esta sesión.")

                for horario in horarios_elements:
                    link = horario.get('href')
                    print(f"Enlace encontrado: {link}")  # Depuración
                    if link:
                        # Decodificar el enlace
                        decoded_link = urllib.parse.unquote(link)
                        print(f"Enlace decodificado: {decoded_link}")  # Depuración
                        
                        # Buscar "language=VOSE" en el enlace decodificado
                        if "language=VOSE" in decoded_link:
                            hora = horario.get_text(strip=True)
                            print(f"      Horario VOSE encontrado: {hora} (Link: {decoded_link})")
                            horarios.append({"fecha": fecha, "hora": hora})
                        else:
                            print(f"      Horario ignorado (enlace: {decoded_link})")
                    else:
                        print("      No se encontró enlace para este horario.")

        # Descargar la imagen solo si tiene horarios VOS
        if horarios:
            # Cartel de la película
            cartel_element = pelicula_div.find('img', {'class': 'lazyload'})
            if cartel_element:
                cartel_url = cartel_element['src']
                image_name = os.path.basename(cartel_url)
                image_path = os.path.join(images_folder, image_name)

                if not os.path.exists(image_path):
                    print(f"Descargando imagen: {cartel_url}")
                    img_response = requests.get(cartel_url)
                    if img_response.status_code == 200:
                        with open(image_path, 'wb') as img_file:
                            img_file.write(img_response.content)
                        print(f"Imagen descargada: {image_path}")
                    else:
                        print(f"Error al descargar la imagen: {cartel_url} (Código: {img_response.status_code})")
                        image_path = None
                else:
                    print(f"Imagen ya descargada: {image_path}")
            else:
                print("No se encontró el cartel de la película.")
                image_path = None

            # Agregar película a la lista
            print(f"Película '{titulo}' agregada con {len(horarios)} horarios VOS.")
            peliculas.append({
                "título": titulo,
                "cartel": image_path,
                "horarios": horarios,
                "cine": "Yelmo Itaroa",
            })
        else:
            print(f"No se encontraron horarios VOS para la película: {titulo}")

    print(f"\nTotal de películas con horarios VOS: {len(peliculas)}")
    return peliculas


def main():
    # URL de FilmAffinity para la cartelera
    url = "https://www.filmaffinity.com/es/theater-showtimes.php?id=428"
    images_folder = "imagenes_filmaffinity"  # Carpeta para las imágenes
    output_path = "peliculas_filmaffinity.json"  # Archivo JSON

    # Scraping
    peliculas = scrape_filmaffinity_vos(url, images_folder)

    # Guardar en JSON
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json.dump(peliculas, json_file, indent=4, ensure_ascii=False)
        print(f"Resultados guardados en {output_path}")


if __name__ == "__main__":
    main()
